from __future__ import annotations

import json
import os
import re
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from uuid6 import uuid7

from .adapters import sanitize
from .benchmark import build_datasets
from .datasets import digest_bytes, encode_cases, validate_jsonl

TERMINAL = {"completed", "partial", "cancelled", "failed"}


def now():
    return datetime.now(timezone.utc).isoformat()


def identifier():
    return str(uuid7())


class Store:
    def __init__(self, root, recover=True):
        self.root = Path(root).resolve()
        self.lock = threading.RLock()
        self.event_ids = {}
        for directory in (
            "datasets",
            "runs",
            "calibrations",
            "protocols",
            "reviews",
            "workflows",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        development, evaluation = build_datasets()
        for name, cases in (("demo", development), ("benchmark", evaluation)):
            if not (self.root / "datasets" / name / "metadata.json").exists():
                self.add_dataset(encode_cases(cases), name, name)
        if recover:
            self.recover()

    @contextmanager
    def exclusive(self):
        import fcntl

        with (self.root / ".writer.lock").open("a") as lock:
            try:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError as exc:
                raise ValueError("A backend is already using this data folder") from exc
            try:
                yield
            finally:
                fcntl.flock(lock, fcntl.LOCK_UN)

    def path(self, category, name):
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9_.-]{0,159}", name):
            raise ValueError("Invalid managed resource ID")
        path = (self.root / category / name).resolve()
        if not path.is_relative_to(self.root / category):
            raise ValueError("Path escapes the managed storage root")
        return path

    def run_dir(self, run_id):
        return self.path("runs", run_id)

    @staticmethod
    def read_json(path):
        with Path(path).open(encoding="utf-8") as file:
            return json.load(file)

    def write_json(self, path, data):
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(
            sanitize(data, redact_keys=False), ensure_ascii=False, indent=2, allow_nan=False
        ).encode()
        with self.lock:
            temp = path.with_name(path.name + ".tmp")
            with temp.open("wb") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())
            os.replace(temp, path)

    def add_dataset(self, raw, name="Imported dataset", dataset_id=None):
        result = validate_jsonl(raw)
        if not result["valid"]:
            return {k: v for k, v in result.items() if k != "cases"}
        dataset_id = dataset_id or identifier()
        directory = self.path("datasets", dataset_id)
        directory.mkdir(exist_ok=False)
        (directory / "cases.jsonl").write_bytes(raw)
        metadata = {
            "dataset_id": dataset_id,
            "name": name[:160],
            "created_at": now(),
            "digest": result["digest"],
            "counts": result["counts"],
            "valid": True,
            "issues": [],
            "review_status": "draft",
        }
        self.write_json(directory / "metadata.json", metadata)
        return metadata

    def datasets(self):
        return [self.read_json(p) for p in sorted((self.root / "datasets").glob("*/metadata.json"))]

    def dataset(self, dataset_id):
        directory = self.path("datasets", dataset_id)
        metadata = self.read_json(directory / "metadata.json")
        raw = (directory / "cases.jsonl").read_bytes()
        if digest_bytes(raw) != metadata["digest"]:
            raise ValueError("Dataset changed since import; import it as a new dataset")
        result = validate_jsonl(raw)
        if not result["valid"]:
            raise ValueError("Stored dataset no longer validates")
        return metadata, result["cases"]

    def create_run(self, config, cases, schedule):
        run_id = identifier()
        directory = self.run_dir(run_id)
        directory.mkdir()
        for artifact in ("predictions", "errors"):
            (directory / (artifact + ".jsonl")).touch()
        serialized = [c.model_dump() if hasattr(c, "model_dump") else c for c in cases]
        (directory / "cases.snapshot.jsonl").write_bytes(encode_cases(serialized))
        self.write_json(directory / "effective-config.json", config)
        self.write_json(directory / "schedule.json", schedule)
        manifest = {
            "run_id": run_id,
            "name": config["name"],
            "status": "validating",
            "created_at": now(),
            "started_at": now(),
            "ended_at": None,
            "track": config.get("track", "default"),
            "mode": config.get("mode", "fake"),
            "submitted_config": config,
            "effective_config": config,
            "dataset_digest": config.get("dataset_digest"),
            "scoring_version": "1.0.0",
            "snapshot_digest": digest_bytes(encode_cases(serialized)),
            "progress": {"completed": 0, "total": len(schedule), "systems": {}},
            "warnings": [],
            "artifacts": [],
            "partial": False,
            "sealed_released": False,
            "publication": False,
        }
        self.write_json(directory / "manifest.json", manifest)
        self.event_ids[run_id] = 0
        self.event(run_id, "run.created", {"status": "validating"})
        return manifest

    def manifest(self, run_id):
        return self.read_json(self.run_dir(run_id) / "manifest.json")

    def update(self, run_id, **changes):
        with self.lock:
            manifest = self.manifest(run_id)
            manifest.update(changes)
            self.write_json(self.run_dir(run_id) / "manifest.json", manifest)
            return manifest

    def append(self, run_id, artifact, record):
        if artifact not in ("predictions", "events", "errors"):
            raise ValueError("Unknown append-only artifact")
        with self.lock:
            payload = (
                json.dumps(
                    sanitize(record, redact_keys=False),
                    ensure_ascii=False,
                    allow_nan=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode()
            with (self.run_dir(run_id) / (artifact + ".jsonl")).open("ab") as file:
                file.write(payload)
                file.flush()
                os.fsync(file.fileno())

    def records(self, run_id, artifact):
        if artifact not in ("predictions", "events", "errors", "cases.snapshot"):
            raise ValueError("Unknown artifact")
        path = self.run_dir(run_id) / (artifact + ".jsonl")
        if not path.exists():
            return []
        lines = path.read_bytes().splitlines(keepends=True)
        result = []
        for index, line in enumerate(lines):
            try:
                result.append(json.loads(line))
            except (json.JSONDecodeError, UnicodeDecodeError):
                if index == len(lines) - 1 and not line.endswith(b"\n"):
                    break
                raise ValueError("Artifact is corrupt before its final record")
        return result

    def event(self, run_id, kind, payload):
        with self.lock:
            if run_id not in self.event_ids:
                self.event_ids[run_id] = max(
                    (e["id"] for e in self.records(run_id, "events")), default=0
                )
            self.event_ids[run_id] += 1
            event = {
                "id": self.event_ids[run_id],
                "event": kind,
                "timestamp": now(),
                "data": {"run_id": run_id, **payload},
            }
            self.append(run_id, "events", event)
            return event

    def runs(self):
        return sorted(
            [self.read_json(p) for p in (self.root / "runs").glob("*/manifest.json")],
            key=lambda r: r["created_at"],
            reverse=True,
        )

    def recover(self):
        for manifest in self.runs():
            if manifest["status"] in TERMINAL:
                continue
            run_id = manifest["run_id"]
            predictions = self.records(run_id, "predictions")
            self.update(
                run_id,
                status="partial",
                partial=True,
                ended_at=now(),
                progress={**manifest["progress"], "completed": len(predictions)},
                warnings=manifest["warnings"]
                + ["Backend interrupted. Saved outcomes are intact; rerun as a new evaluation."],
            )
            # Preserve interrupted log bytes. Recovery never appends to a possibly torn file.
