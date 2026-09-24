import hashlib
import importlib.metadata
import json
import re
from pathlib import Path

from .calibration import inference_signature
from .datasets import digest_bytes
from .schemas import RunConfiguration
from .store import identifier, now


def runtime_signature():
    code = b"".join(
        path.name.encode() + path.read_bytes()
        for path in sorted(Path(__file__).parent.glob("*.py"))
    )
    packages: dict[str, str | None] = {}
    for name in ("laya", "typesafe-sdk", "torch", "transformers", "numpy", "scipy", "scikit-learn"):
        try:
            packages[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            packages[name] = None
    return {"implementation_digest": digest_bytes(code), "packages": packages}


def configuration_fingerprint(config):
    value = config.model_dump() if hasattr(config, "model_dump") else dict(config)
    # Presentation labels and protocol association cannot alter the evaluated configuration.
    for key in ("name", "protocol_id", "publication", "acknowledge_remote"):
        value.pop(key, None)
    return (
        "sha256:"
        + hashlib.sha256(
            json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
    )


def review_packet(store, dataset_id):
    metadata, cases = store.dataset(dataset_id)
    return {
        "dataset_id": dataset_id,
        "dataset_digest": metadata["digest"],
        "instructions": "Independently label every presentation from its policy. Return reviewer, case_id, answer, and rationale. Do not consult proposed labels.",
        "cases": [
            {k: v for k, v in c.model_dump().items() if k not in ("expected", "metadata")}
            for c in cases
        ],
    }


def import_reviews(store, dataset_id, reviews):
    metadata, cases = store.dataset(dataset_id)
    indexed = {c.id: c for c in cases}
    path = store.path("reviews", dataset_id + ".json")
    existing = (
        store.read_json(path) if path.exists() else {"digest": metadata["digest"], "reviews": {}}
    )
    if existing["digest"] != metadata["digest"]:
        raise ValueError("Review digest no longer matches the dataset")
    # Validate the complete upload before changing any review state.
    validated = []
    for review in reviews:
        case = indexed.get(review.get("case_id"))
        reviewer = review.get("reviewer", "").strip()
        if case is None or not reviewer or reviewer == case.metadata.get("author"):
            raise ValueError("A review needs a valid case and independent named reviewer")
        if not review.get("rationale", "").strip():
            raise ValueError("Review rationale is required")
        answer = review.get("answer")
        if type(answer) is not type(case.expected.value):
            raise ValueError("Reviewer answer type must match the primitive")
        key = str(answer).lower() if isinstance(answer, bool) else str(answer)
        if key not in case.options:
            raise ValueError("Reviewer answer is outside the answer space")
        agreed = answer == case.expected.value
        if not agreed:
            adjudicator = review.get("adjudicator", "").strip()
            if (
                not adjudicator
                or adjudicator in (reviewer, case.metadata.get("author"))
                or not review.get("adjudication_rationale")
            ):
                raise ValueError(
                    "Disagreement requires a distinct adjudicator and rationale; incorrect gold labels require a new dataset"
                )
            if review.get("adjudicated_answer") != case.expected.value:
                raise ValueError(
                    "Correct the case by importing a new dataset, then review its new digest"
                )
        validated.append({**review, "approved": True, "reviewed_at": now()})
    for review in validated:
        existing["reviews"][review["case_id"]] = review
    store.write_json(path, existing)
    approved = len(existing["reviews"])
    return {"approved": approved, "total": len(cases), "complete": approved == len(cases)}


def review_status(store, dataset_id):
    metadata, cases = store.dataset(dataset_id)
    path = store.path("reviews", dataset_id + ".json")
    record = store.read_json(path) if path.exists() else {"reviews": {}}
    valid = record.get("digest") == metadata["digest"]
    count = len(record["reviews"]) if valid else 0
    return {"approved": count, "total": len(cases), "complete": count == len(cases)}


def prior_evaluation(store, digest, protocol_id=None):
    return any(
        run.get("dataset_digest") == digest
        and run.get("mode") == "live"
        and (protocol_id is None or run["effective_config"].get("protocol_id") != protocol_id)
        for run in store.runs()
    )


def freeze_protocol(store, dataset_id, configurations):
    metadata, cases = store.dataset(dataset_id)
    if not review_status(store, dataset_id)["complete"]:
        raise ValueError("Independent review of every evaluation presentation is required")
    if any(c.split == "development" for c in cases):
        raise ValueError("Publication protocol requires an evaluation dataset")
    if set(configurations) != {"default", "production-tuned"}:
        raise ValueError("Freeze both default and production-tuned configurations together")
    frozen = {}
    exploratory = prior_evaluation(store, metadata["digest"])
    for track, value in configurations.items():
        config = RunConfiguration.model_validate(value)
        if exploratory and config.publication:
            raise ValueError(
                "This dataset was already evaluated; subsequent protocols must be explicitly exploratory (publication=false)"
            )
        if config.mode != "live" or config.track != track or config.dataset_ref != dataset_id:
            raise ValueError(
                "Protocol configurations must be paired live tracks on the same dataset"
            )
        if not re.fullmatch(r"jev-\d+\.\d+\.\d+", config.systems.jev.model):
            raise ValueError("Freeze an explicit versioned Jev model")
        if not re.fullmatch(r"[0-9a-f]{40}", config.systems.laya.checkpoint_revision or ""):
            raise ValueError("Freeze a pinned 40-character Laya checkpoint revision")
        calibration_digest = None
        if config.calibration_id:
            artifact = store.path("calibrations", config.calibration_id + ".json")
            calibration = store.read_json(artifact)
            if calibration.get("source_mode") != "live":
                raise ValueError("Publication requires a live development calibration artifact")
            if calibration.get("inference_signature") != inference_signature(config):
                raise ValueError(
                    "Calibration artifact requires the same inference configuration as development"
                )
            if calibration.get("dataset_digest") == metadata["digest"] or set(
                calibration.get("family_ids", [])
            ) & {c.family_id for c in cases}:
                raise ValueError("Development and evaluation families must be disjoint")
            calibration_digest = digest_bytes(artifact.read_bytes())
        config.dataset_digest = metadata["digest"]
        frozen[track] = {
            "configuration": config.model_dump(),
            "calibration_digest": calibration_digest,
            "fingerprint": configuration_fingerprint(config),
        }
    protocol_id = identifier()
    protocol = {
        "protocol_id": protocol_id,
        "dataset_id": dataset_id,
        "dataset_digest": metadata["digest"],
        "created_at": now(),
        "tracks": frozen,
        "runs": {},
        "sealed_released": False,
        "exploratory": exploratory,
        "rerun_rule": "Interrupted or operationally failed execution is retained. Any rerun is a new, explicitly exploratory evaluation.",
        "scoring_version": "1.0.0",
    }
    protocol["runtime_signature"] = runtime_signature()
    protocol["reviews_digest"] = digest_bytes(
        store.path("reviews", dataset_id + ".json").read_bytes()
    )
    store.write_json(store.path("protocols", protocol_id + ".json"), protocol)
    return protocol


def validate_protocol(store, config):
    if not config.protocol_id:
        if config.publication:
            raise ValueError("Publication requires a frozen protocol")
        return None
    protocol = store.read_json(store.path("protocols", config.protocol_id + ".json"))
    if (protocol.get("exploratory") and config.publication) or (
        prior_evaluation(store, config.dataset_digest, config.protocol_id)
        and (config.publication or not protocol.get("exploratory"))
    ):
        raise ValueError(
            "Previously evaluated data requires an explicitly exploratory protocol; publication is unavailable"
        )
    if protocol.get("runtime_signature") != runtime_signature():
        raise ValueError("Implementation or dependency versions changed after protocol freeze")
    if protocol.get("reviews_digest") != digest_bytes(
        store.path("reviews", config.dataset_ref + ".json").read_bytes()
    ):
        raise ValueError("Review artifact changed after protocol freeze")
    if protocol["dataset_digest"] != config.dataset_digest:
        raise ValueError("Protocol dataset digest mismatch")
    if protocol["tracks"][config.track]["fingerprint"] != configuration_fingerprint(config):
        raise ValueError("Configuration differs from the frozen track")
    if config.calibration_id:
        artifact = store.path("calibrations", config.calibration_id + ".json")
        if digest_bytes(artifact.read_bytes()) != protocol["tracks"][config.track].get(
            "calibration_digest"
        ):
            raise ValueError("Calibration artifact differs from the frozen track")
    if config.track in protocol["runs"]:
        raise ValueError(
            "This frozen track was already executed; retain evidence and create an exploratory run"
        )
    return protocol


def register_protocol_run(store, config, run_id):
    if config.protocol_id:
        path = store.path("protocols", config.protocol_id + ".json")
        protocol = store.read_json(path)
        protocol["runs"][config.track] = run_id
        store.write_json(path, protocol)


def release_protocol(store, protocol_id):
    if not protocol_id:
        return
    path = store.path("protocols", protocol_id + ".json")
    protocol = store.read_json(path)
    if set(protocol["runs"]) != {"default", "production-tuned"}:
        return
    if all(store.manifest(run_id)["status"] == "completed" for run_id in protocol["runs"].values()):
        protocol["sealed_released"] = True
        store.write_json(path, protocol)
        for run_id in protocol["runs"].values():
            store.update(run_id, sealed_released=True)
