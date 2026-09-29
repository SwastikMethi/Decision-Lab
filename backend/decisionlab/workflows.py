from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .benchmark import diagnostic_cases
from .calibration import fit_calibration, inference_signature
from .datasets import encode_cases, validate_jsonl
from .governance import (
    freeze_protocol,
    import_reviews,
    release_protocol,
    review_packet,
    review_status,
)
from .runner import make_schedule
from .schemas import EvaluationCase, RunConfiguration
from .store import TERMINAL, identifier, now

FINAL_STAGES = {"completed", "blocked", "cancelled"}
RUNNING_STAGES = {
    "development_running": "development",
    "default_running": "default",
    "tuned_running": "production-tuned",
}


def comparison_verdict(comparison):
    interval = comparison.get("ci95")
    winner = "no_clear_winner"
    if interval and len(interval) == 2:
        if interval[0] > 0:
            winner = comparison["left"].split("-", 1)[0]
        elif interval[1] < 0:
            winner = comparison["right"].split("-", 1)[0]
    return {
        "winner": winner,
        "accuracy_difference": comparison.get("difference"),
        "ci95": interval,
        "families": comparison.get("families"),
        "left": comparison.get("left"),
        "right": comparison.get("right"),
    }


class BenchmarkWorkflowManager:
    def __init__(self, store, runner):
        self.store = store
        self.runner = runner

    def create(self, name, raw, profile="standard", publication=False):
        if profile not in ("standard", "full"):
            raise ValueError("Profile must be standard or full")
        if isinstance(raw, str):
            raw = raw.encode()
        result = validate_jsonl(raw)
        if not result["valid"]:
            issue = result["issues"][0]
            raise ValueError(
                f"Dataset is invalid at line {issue['line']} ({issue['field']}): {issue['message']}"
            )
        development = [case for case in result["cases"] if case.split == "development"]
        evaluation = [case for case in result["cases"] if case.split in ("evaluation", "sealed")]
        if not development or not evaluation:
            raise ValueError("Dataset must contain both development and evaluation cases")
        if {case.family_id for case in development} & {case.family_id for case in evaluation}:
            raise ValueError("Development and evaluation families must be disjoint")

        workflow_id = identifier()
        dataset_ids = {
            "development": f"{workflow_id}-development",
            "evaluation": f"{workflow_id}-evaluation",
        }
        development_meta = self.store.add_dataset(
            encode_cases(development), f"{name} — development", dataset_ids["development"]
        )
        evaluation_meta = self.store.add_dataset(
            encode_cases(evaluation), f"{name} — evaluation", dataset_ids["evaluation"]
        )
        development_config = self._configuration(
            workflow_id,
            name,
            "development",
            dataset_ids["development"],
            "standard",
            publication=False,
        )
        default_preview = self._configuration(
            workflow_id, name, "default", dataset_ids["evaluation"], profile, publication
        )
        tuned_preview = self._configuration(
            workflow_id, name, "production-tuned", dataset_ids["evaluation"], profile, publication
        )
        packet_path = self._artifact_path(workflow_id, "review-packet")
        submission_path = self._artifact_path(workflow_id, "reviews")
        self.store.write_json(packet_path, review_packet(self.store, dataset_ids["evaluation"]))
        created = now()
        workflow = {
            "workflow_id": workflow_id,
            "name": name[:160],
            "stage": "prepared",
            "profile": profile,
            "publication": bool(publication),
            "created_at": created,
            "updated_at": created,
            "datasets": dataset_ids,
            "dataset_digests": {
                "development": development_meta["digest"],
                "evaluation": evaluation_meta["digest"],
            },
            "estimates": {
                "development": self._estimate(development_config, development),
                "default": self._estimate(default_preview, evaluation),
                "production-tuned": self._estimate(tuned_preview, evaluation),
            },
            "configurations": {"development": development_config.model_dump()},
            "runs": {},
            "calibration_id": None,
            "protocol_id": None,
            "authorization": None,
            "review": {
                "packet_path": str(packet_path),
                "submission_path": str(submission_path),
                "approved": 0,
                "total": len(evaluation),
                "complete": False,
            },
            "blocker": None,
            "report_path": str(self._artifact_path(workflow_id, "report")),
        }
        self._save(workflow)
        return self.get(workflow_id)

    def list(self):
        items = []
        for path in sorted((self.store.root / "workflows").glob("*.json")):
            if any(
                path.name.endswith(suffix)
                for suffix in (".review-packet.json", ".reviews.json", ".report.json")
            ):
                continue
            items.append(self._status(self.store.read_json(path)))
        return sorted(items, key=lambda item: item["created_at"], reverse=True)

    def get(self, workflow_id):
        return self._status(self.store.read_json(self._workflow_path(workflow_id)))

    async def advance(self, workflow_id, confirm_live_calls=False, confirm_remote_data=False):
        workflow = self.store.read_json(self._workflow_path(workflow_id))
        if workflow["stage"] in FINAL_STAGES:
            return self._status(workflow)
        if not workflow["authorization"]:
            if not (confirm_live_calls and confirm_remote_data):
                raise ValueError("Explicitly confirm live provider calls and remote case data")
            confirmed_at = now()
            signed = json.dumps(
                {
                    "workflow_id": workflow_id,
                    "dataset_digest": workflow["dataset_digests"]["evaluation"],
                    "confirmed_at": confirmed_at,
                    "live_calls": True,
                    "remote_data": True,
                },
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
            workflow["authorization"] = {
                "confirmed_at": confirmed_at,
                "live_calls": True,
                "remote_data": True,
                "fingerprint": "sha256:" + hashlib.sha256(signed).hexdigest(),
            }
            self._save(workflow)

        while True:
            stage = workflow["stage"]
            if stage == "prepared":
                return await self._start(workflow, "development", "development_running")
            if stage in RUNNING_STAGES:
                phase = RUNNING_STAGES[stage]
                run_id = workflow["runs"][phase]
                manifest = self.store.manifest(run_id)
                if manifest["status"] not in TERMINAL:
                    return self._status(workflow)
                if manifest["status"] != "completed":
                    workflow["stage"] = "blocked"
                    workflow["blocker"] = (
                        f"{phase} run {run_id} ended as {manifest['status']}; evidence was retained"
                    )
                    self._save(workflow)
                    return self._status(workflow)
                if phase == "development":
                    workflow["calibration_id"] = self._fit_calibration(workflow, run_id)
                    workflow["stage"] = "waiting_for_review"
                    self._save(workflow)
                    continue
                if phase == "default":
                    workflow["stage"] = "ready_for_tuned"
                    self._save(workflow)
                    continue
                release_protocol(self.store, workflow["protocol_id"])
                workflow["stage"] = "completed"
                self._save(workflow)
                self._write_report(workflow)
                return self.get(workflow_id)
            if stage == "waiting_for_review":
                submission = Path(workflow["review"]["submission_path"])
                if not submission.exists():
                    return self._status(workflow)
                raw_reviews = self.store.read_json(submission)
                reviews = (
                    raw_reviews.get("reviews") if isinstance(raw_reviews, dict) else raw_reviews
                )
                if not isinstance(reviews, list) or not reviews:
                    raise ValueError("Review submission must be a non-empty JSON array")
                status = import_reviews(self.store, workflow["datasets"]["evaluation"], reviews)
                workflow["review"].update(status)
                if not status["complete"]:
                    self._save(workflow)
                    return self._status(workflow)
                self._freeze(workflow)
                workflow["stage"] = "ready_for_default"
                self._save(workflow)
                continue
            if stage == "ready_for_default":
                return await self._start(workflow, "default", "default_running")
            if stage == "ready_for_tuned":
                return await self._start(workflow, "production-tuned", "tuned_running")
            raise ValueError(f"Unknown workflow stage: {stage}")

    async def cancel(self, workflow_id):
        workflow = self.store.read_json(self._workflow_path(workflow_id))
        if workflow["stage"] in FINAL_STAGES:
            return self._status(workflow)
        phase = RUNNING_STAGES.get(workflow["stage"])
        if phase and phase in workflow["runs"]:
            run_id = workflow["runs"][phase]
            if self.store.manifest(run_id)["status"] not in TERMINAL:
                await self.runner.cancel(run_id)
        workflow["stage"] = "cancelled"
        workflow["blocker"] = "Cancelled by the operator; completed evidence was retained"
        self._save(workflow)
        return self._status(workflow)

    def report(self, workflow_id):
        workflow = self.store.read_json(self._workflow_path(workflow_id))
        if workflow["stage"] != "completed":
            raise ValueError("The report is available after both frozen tracks complete")
        path = Path(workflow["report_path"])
        if not path.exists():
            self._write_report(workflow)
        return self.store.read_json(path)

    async def _start(self, workflow, phase, running_stage):
        existing = workflow["runs"].get(phase) or self._find_run(workflow, phase)
        if existing:
            workflow["runs"][phase] = existing
            workflow["stage"] = running_stage
            self._save(workflow)
            return self._status(workflow)
        config = RunConfiguration.model_validate(workflow["configurations"][phase])
        manifest = await self.runner.create(config)
        workflow["runs"][phase] = manifest["run_id"]
        workflow["configurations"][phase] = config.model_dump()
        workflow["stage"] = running_stage
        self._save(workflow)
        return self._status(workflow)

    def _find_run(self, workflow, phase):
        name = self._run_name(workflow["workflow_id"], workflow["name"], phase)
        return next((run["run_id"] for run in self.store.runs() if run.get("name") == name), None)

    def _fit_calibration(self, workflow, run_id):
        calibration_id = f"{workflow['workflow_id']}-calibration"
        path = self.store.path("calibrations", calibration_id + ".json")
        if path.exists():
            return calibration_id
        manifest = self.store.manifest(run_id)
        cases = self.store.records(run_id, "cases.snapshot")
        result = fit_calibration(
            cases, self.store.records(run_id, "predictions"), manifest["dataset_digest"]
        )
        result.update(
            calibration_id=calibration_id,
            run_id=run_id,
            created_at=now(),
            inference_signature=inference_signature(
                RunConfiguration.model_validate(manifest["effective_config"])
            ),
            source_mode=manifest["mode"],
            family_ids=sorted({case["family_id"] for case in cases}),
        )
        self.store.write_json(path, result)
        return calibration_id

    def _freeze(self, workflow):
        existing = next(
            (
                self.store.read_json(path)
                for path in (self.store.root / "protocols").glob("*.json")
                if self.store.read_json(path).get("dataset_id")
                == workflow["datasets"]["evaluation"]
            ),
            None,
        )
        if existing:
            protocol = existing
        else:
            development = self.store.manifest(workflow["runs"]["development"])["effective_config"]
            revision = development["systems"]["laya"]["checkpoint_revision"]
            default = self._configuration(
                workflow["workflow_id"],
                workflow["name"],
                "default",
                workflow["datasets"]["evaluation"],
                workflow["profile"],
                workflow["publication"],
                revision=revision,
            )
            tuned = self._configuration(
                workflow["workflow_id"],
                workflow["name"],
                "production-tuned",
                workflow["datasets"]["evaluation"],
                workflow["profile"],
                workflow["publication"],
                revision=revision,
                calibration_id=workflow["calibration_id"],
            )
            protocol = freeze_protocol(
                self.store,
                workflow["datasets"]["evaluation"],
                {"default": default, "production-tuned": tuned},
            )
        workflow["protocol_id"] = protocol["protocol_id"]
        workflow["configurations"].update(
            {
                track: {
                    **protocol["tracks"][track]["configuration"],
                    "protocol_id": protocol["protocol_id"],
                }
                for track in ("default", "production-tuned")
            }
        )

    def _configuration(
        self,
        workflow_id,
        name,
        phase,
        dataset_id,
        profile,
        publication,
        revision=None,
        calibration_id=None,
    ):
        track = "production-tuned" if phase == "production-tuned" else "default"
        suites = {}
        if profile == "full":
            suites = {
                "repeatability": {"enabled": True, "repetitions": 5, "sample_size": 30},
                "performance": {
                    "enabled": True,
                    "concurrency": [1, 4, 8],
                    "batch_sizes": [1, 5, 10, 50],
                    "sample_size": 30,
                },
                "context_length": True,
                "option_cardinality": True,
            }
        return RunConfiguration.model_validate(
            {
                "name": self._run_name(workflow_id, name, phase),
                "track": track,
                "dataset_ref": dataset_id,
                "mode": "live",
                "acknowledge_remote": True,
                "publication": publication,
                "calibration_id": calibration_id,
                "systems": {"laya": {"checkpoint_revision": revision}},
                "suites": suites,
            }
        )

    @staticmethod
    def _run_name(workflow_id, name, phase):
        prefix = f"DL:{workflow_id}:{phase}"
        return f"{prefix} {name}"[:160]

    @staticmethod
    def _estimate(config, cases):
        expanded = list(cases) + [
            EvaluationCase.model_validate(value)
            for value in diagnostic_cases(
                cases, config.suites.context_length, config.suites.option_cardinality
            )
        ]
        schedule = make_schedule(config, expanded)
        return {
            "requests": len(schedule),
            "questions": sum(job["batch_size"] for job in schedule),
            "warmup_requests": 2 * len({case.primitive for case in expanded}),
            "maximum_jev_retries": sum(job["adapter_id"] == "jev" for job in schedule)
            * config.systems.jev.max_retries,
            "runtime_estimate_seconds": None,
            "cost_estimate_usd": None,
        }

    def _write_report(self, workflow):
        default = self.runner.summary(workflow["runs"]["default"])
        tuned = self.runner.summary(workflow["runs"]["production-tuned"])
        default_verdict = comparison_verdict(default["comparisons"][0])
        tuned_verdict = comparison_verdict(tuned["comparisons"][0])
        report = {
            "workflow_id": workflow["workflow_id"],
            "dataset_digest": workflow["dataset_digests"]["evaluation"],
            "profile": workflow["profile"],
            "generated_at": now(),
            "default": {**default_verdict, "systems": self._kpis(default)},
            "production_tuned": {**tuned_verdict, "systems": self._kpis(tuned)},
            "calibration_id": workflow["calibration_id"],
            "protocol_id": workflow["protocol_id"],
        }
        report["markdown"] = self._markdown(report)
        self.store.write_json(Path(workflow["report_path"]), report)

    @staticmethod
    def _kpis(summary):
        result = {}
        for system, values in summary["systems"].items():
            result[system] = {
                "accuracy": values["correctness"]["accuracy"]["value"],
                "macro_f1": values["correctness"]["macro_f1"]["value"],
                "brier": values["calibration"]["brier"]["value"],
                "ece": values["calibration"]["ece"]["value"],
                "failure_count": values["failures"]["count"],
                "failure_rate": values["failures"]["rate"],
                "p50_latency_ms": values["performance"]["warm_p50_ms"],
                "p95_latency_ms": values["performance"]["warm_p95_ms"],
                "total_cost_usd": values["cost"].get("provider_reported_total_usd")
                or values["cost"].get("estimated_api_total_usd"),
                "cost_per_1000_decisions_usd": values["cost"]["per_1000_decisions_usd"],
                "robustness": values["robustness"],
                "repeatability": values["repeatability"],
                "load_tests": values["performance"].get("load_tests", []),
                "frozen_policy": values["selective_automation"]["frozen_policy"],
            }
        return result

    @staticmethod
    def _markdown(report):
        lines = ["# DecisionLab benchmark report", ""]
        for key, label in (("default", "Default"), ("production_tuned", "Production tuned")):
            result = report[key]
            winner = (
                "No clear winner"
                if result["winner"] == "no_clear_winner"
                else f"{result['winner'].title()} leads"
            )
            lines.extend(
                [
                    f"## {label}",
                    "",
                    f"{winner} on paired accuracy (difference {result['accuracy_difference']}; "
                    f"95% CI {result['ci95']}).",
                    "",
                ]
            )
        lines.append(
            "Results apply to this dataset and frozen configuration; they do not establish a universal model ranking."
        )
        return "\n".join(lines)

    def _status(self, workflow):
        phase = RUNNING_STAGES.get(workflow["stage"])
        workflow["current_run"] = None
        if phase and workflow["runs"].get(phase):
            manifest = self.store.manifest(workflow["runs"][phase])
            workflow["current_run"] = {
                "phase": phase,
                "run_id": manifest["run_id"],
                "status": manifest["status"],
                "progress": manifest["progress"],
            }
        if workflow["stage"] == "waiting_for_review":
            workflow["review"].update(review_status(self.store, workflow["datasets"]["evaluation"]))
        workflow["next_action"] = {
            "prepared": "Confirm live calls and remote data to start development",
            "development_running": "Wait for development to finish, then advance",
            "waiting_for_review": "Complete the blind review file, then advance",
            "ready_for_default": "Advance to start the default track",
            "default_running": "Wait for the default track to finish, then advance",
            "ready_for_tuned": "Advance to start the production-tuned track",
            "tuned_running": "Wait for the production-tuned track to finish, then advance",
            "completed": "Retrieve the report",
            "blocked": "Inspect the retained run evidence",
            "cancelled": "Inspect the retained run evidence",
        }[workflow["stage"]]
        return workflow

    def _save(self, workflow):
        workflow["updated_at"] = now()
        self.store.write_json(self._workflow_path(workflow["workflow_id"]), workflow)

    def _workflow_path(self, workflow_id):
        return self.store.path("workflows", workflow_id + ".json")

    def _artifact_path(self, workflow_id, kind):
        return self.store.path("workflows", f"{workflow_id}.{kind}.json")
