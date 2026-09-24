from __future__ import annotations

import asyncio
import json
import os
import platform
import random
import subprocess
import time

import psutil

from .adapters import (
    DecisionAdapter,
    FakeAdapter,
    JevAdapter,
    ProviderFailure,
    normalize,
    provider_metadata,
    sanitize,
)
from .benchmark import diagnostic_cases
from .calibration import calibrate_answer, inference_signature
from .datasets import digest_bytes
from .governance import (
    register_protocol_run,
    release_protocol,
    runtime_signature,
    validate_protocol,
)
from .laya_runtime import LayaAdapter
from .metrics import compute_metrics
from .schemas import EvaluationCase, RunConfiguration
from .store import TERMINAL, now


def stratified_sample(cases, count, rng):
    groups = [
        [c for c in cases if c.primitive == primitive] for primitive in ("choice", "noul", "score")
    ]
    for group in groups:
        rng.shuffle(group)
    result: list[EvaluationCase] = []
    while len(result) < min(count, len(cases)):
        for group in groups:
            if group and len(result) < count:
                result.append(group.pop())
    return result


def make_schedule(config, cases):
    rng = random.Random(config.seed)
    primary = [c for c in cases if c.variant not in ("context_length", "option_cardinality")]
    ordered = list(primary)
    rng.shuffle(ordered)
    jobs = []

    def add(case, suite, repetition=0, concurrency=1, batch_size=1):
        for adapter in ("jev", "laya"):
            jobs.append(
                {
                    "evaluation_id": f"{adapter}:{suite}:{case.id}:{repetition}:{concurrency}:{batch_size}",
                    "adapter_id": adapter,
                    "system_id": f"{adapter}-{config.track}",
                    "case_id": case.id,
                    "suite": suite,
                    "repetition": repetition,
                    "concurrency": concurrency,
                    "batch_size": batch_size,
                }
            )

    for case in ordered:
        add(case, "quality")
    if config.suites.repeatability.enabled:
        for case in stratified_sample(primary, config.suites.repeatability.sample_size, rng):
            for repetition in range(config.suites.repeatability.repetitions):
                add(case, "repeatability", repetition)
    for case in cases:
        if case.variant in ("context_length", "option_cardinality"):
            add(case, case.variant)
    if config.suites.performance.enabled:
        sample = stratified_sample(primary, config.suites.performance.sample_size, rng)
        for concurrency in config.suites.performance.concurrency:
            for batch_size in config.suites.performance.batch_sizes:
                for index, case in enumerate(sample):
                    add(case, "performance", index, concurrency, batch_size)
    return jobs


def environment():
    try:
        commit = (
            subprocess.run(
                ["git", "rev-parse", "HEAD"], capture_output=True, text=True, timeout=3
            ).stdout.strip()
            or None
        )
    except (OSError, subprocess.TimeoutExpired):
        commit = None
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "machine": platform.machine(),
        "cpu": platform.processor(),
        "cpu_count": psutil.cpu_count(),
        "ram_bytes": psutil.virtual_memory().total,
        "application_commit": commit,
        "application_version": "0.1.0",
        **runtime_signature(),
        "timing_note": "Jev includes API/network time; Laya is local end-to-end inference.",
        "peak_process_ram_bytes": 0,
        "accelerator_memory_bytes": None,
    }


class Runner:
    def __init__(self, store, model_lock=None):
        self.store = store
        self.model_lock = model_lock or os.getenv("DECISIONLAB_MODEL_LOCK", "./models/lock.json")
        self.tasks, self.cancellations = {}, {}
        self.creation_lock = asyncio.Lock()

    async def create(self, config: RunConfiguration):
        async with self.creation_lock:
            if any(not task.done() for task in self.tasks.values()):
                raise ValueError("An evaluation is already active")
            if (
                config.mode == "fake"
                and os.getenv("DECISIONLAB_ALLOW_FAKE", "true").lower() != "true"
            ):
                raise ValueError("Simulation is disabled")
            metadata, cases = self.store.dataset(config.dataset_ref)
            if config.dataset_digest and config.dataset_digest != metadata["digest"]:
                raise ValueError("Dataset digest changed")
            config.dataset_digest = metadata["digest"]
            if any(c.split == "sealed" for c in cases) and not config.protocol_id:
                raise ValueError("Sealed cases require a frozen, independently reviewed protocol")
            if config.calibration_id:
                calibration = self.store.read_json(
                    self.store.path("calibrations", config.calibration_id + ".json")
                )
                if calibration.get("source_mode") != config.mode:
                    raise ValueError("Simulation and live calibration artifacts cannot be mixed")
                if calibration["dataset_digest"] == metadata["digest"]:
                    raise ValueError("Calibration and evaluation datasets must differ")
                development_families = set(calibration.get("family_ids", []))
                if development_families & {c.family_id for c in cases}:
                    raise ValueError("Development and evaluation families overlap")
            if config.mode == "live":
                if not os.getenv("TYPESAFE_API_KEY"):
                    raise ValueError("TYPESAFE_API_KEY is not configured")
                readiness = await LayaAdapter(config.systems.laya, self.model_lock).readiness()
                if not readiness["ready"]:
                    raise ValueError(readiness.get("reason", "Laya checkpoints are unavailable"))
                if (
                    config.systems.laya.checkpoint_revision
                    and config.systems.laya.checkpoint_revision != readiness["revision"]
                ):
                    raise ValueError("Prepared Laya checkpoint does not match requested revision")
                config.systems.laya.checkpoint_revision = readiness["revision"]
            if config.calibration_id and calibration.get(
                "inference_signature"
            ) != inference_signature(config):
                raise ValueError(
                    "Calibration requires the same inference configuration as its development run"
                )
            validate_protocol(self.store, config)
            for case in cases:
                override = config.instruction_overrides.get(case.label_space_id)
                if override:
                    case.question.instructions = override
            cases += [
                EvaluationCase.model_validate(c)
                for c in diagnostic_cases(
                    cases, config.suites.context_length, config.suites.option_cardinality
                )
            ]
            schedule = make_schedule(config, cases)
            manifest = self.store.create_run(config.model_dump(), cases, schedule)
            run_id = manifest["run_id"]
            if config.calibration_id:
                self.store.write_json(
                    self.store.run_dir(run_id) / "calibration.snapshot.json", calibration
                )
            if config.protocol_id:
                protocol = self.store.read_json(
                    self.store.path("protocols", config.protocol_id + ".json")
                )
                reviews = self.store.read_json(
                    self.store.path("reviews", config.dataset_ref + ".json")
                )
                self.store.write_json(
                    self.store.run_dir(run_id) / "protocol.snapshot.json", protocol
                )
                self.store.write_json(self.store.run_dir(run_id) / "reviews.snapshot.json", reviews)
            register_protocol_run(self.store, config, run_id)
            self.cancellations[run_id] = asyncio.Event()
            self.tasks[run_id] = asyncio.create_task(self.execute(run_id, config, cases, schedule))
            return manifest

    async def cancel(self, run_id):
        manifest = self.store.manifest(run_id)
        if manifest["status"] in TERMINAL:
            return manifest
        if run_id not in self.cancellations:
            raise ValueError("Run is not active in this process")
        self.cancellations[run_id].set()
        self.store.update(run_id, status="cancelling")
        self.store.event(run_id, "run.cancelling", {})
        return self.store.manifest(run_id)

    async def execute(self, run_id, config, cases, schedule):
        indexed = {c.id: c for c in cases}
        cancelled = self.cancellations[run_id]
        adapters: dict[str, DecisionAdapter] = (
            {key: FakeAdapter(key) for key in ("jev", "laya")}
            if config.mode == "fake"
            else {
                "jev": JevAdapter(config.systems.jev),
                "laya": LayaAdapter(config.systems.laya, self.model_lock),
            }
        )
        env = environment()
        self.store.write_json(self.store.run_dir(run_id) / "environment.json", env)
        calibration = (
            self.store.read_json(self.store.run_dir(run_id) / "calibration.snapshot.json")
            if config.calibration_id
            else None
        )
        try:
            self.store.event(run_id, "validation.completed", {"cases": len(cases)})
            self.store.update(run_id, status="warming")
            self.store.event(run_id, "warmup.started", {})
            warming = {}
            for key, adapter in adapters.items():
                if cancelled.is_set():
                    break
                warm_task = asyncio.create_task(adapter.warmup(cases))
                await self._settle(run_id, [warm_task])
                if not warm_task.cancelled():
                    warming[key] = warm_task.result()
            self.store.write_json(self.store.run_dir(run_id) / "warmup.json", warming)
            self.store.event(run_id, "warmup.completed", {"systems": list(warming)})
            if not cancelled.is_set():
                self.store.update(run_id, status="running")

            async def lane(adapter_id, jobs):
                adapter = adapters[adapter_id]
                for job in jobs:
                    if cancelled.is_set():
                        return
                    await self.evaluate(
                        run_id, config, indexed[job["case_id"]], adapter, job, calibration, env
                    )

            # Quality, repeatability, and diagnostics have one logical request per adapter.
            baseline = [job for job in schedule if job["suite"] != "performance"]
            await self._settle(
                run_id,
                [lane(key, [j for j in baseline if j["adapter_id"] == key]) for key in adapters],
            )
            for concurrency in config.suites.performance.concurrency:
                for batch_size in config.suites.performance.batch_sizes:
                    if cancelled.is_set():
                        break
                    jobs = [
                        j
                        for j in schedule
                        if j["suite"] == "performance"
                        and j["concurrency"] == concurrency
                        and j["batch_size"] == batch_size
                    ]
                    if not jobs:
                        continue
                    self.store.event(
                        run_id,
                        "suite.started",
                        {
                            "suite": "performance",
                            "concurrency": concurrency,
                            "batch_size": batch_size,
                        },
                    )
                    for key in adapters:
                        group = [j for j in jobs if j["adapter_id"] == key]
                        await self._settle(
                            run_id,
                            [lane(key, group[i::concurrency]) for i in range(concurrency)],
                        )
            self.store.update(run_id, status="scoring" if not cancelled.is_set() else "cancelling")
            self.store.event(run_id, "scoring.started", {})
            summary = await asyncio.to_thread(self.rescore, run_id)
            status = "cancelled" if cancelled.is_set() else "completed"
            warnings = []
            for warm in warming.values():
                for response in warm.get("responses", []):
                    _, runtime, metadata_warnings = provider_metadata(response)
                    warnings.extend(runtime.get("warnings", []))
                    warnings.extend(metadata_warnings)
            warnings = sorted(set(warnings))
            if config.protocol_id and self.store.read_json(
                self.store.run_dir(run_id) / "protocol.snapshot.json"
            ).get("exploratory"):
                warnings.append(
                    "Exploratory rerun of a previously evaluated dataset; not publication-qualified."
                )
            if config.mode == "fake":
                warnings.append(
                    "SIMULATED outcomes. These values are for product demonstration, not model comparison."
                )
            if (
                any(c.metadata.get("review_status") != "approved" for c in cases)
                and not config.publication
            ):
                warnings.append(
                    "Illustrative draft dataset; independent review has not been verified for publication."
                )
            self.store.update(
                run_id,
                status=status,
                ended_at=now(),
                partial=status != "completed",
                warnings=warnings,
                publication=config.publication and status == "completed",
                artifacts=["summary-json", "markdown", "html", "predictions-jsonl", "bundle"],
            )
            summary.update(status=status, provisional=False, partial=status != "completed")
            self.store.write_json(self.store.run_dir(run_id) / "summary.v1.0.0.json", summary)
            self.store.event(
                run_id, "scoring.completed", {"scoring_version": summary["scoring_version"]}
            )
            self.store.event(
                run_id,
                "run.cancelled" if cancelled.is_set() else "run.completed",
                {"status": status},
            )
            release_protocol(self.store, config.protocol_id)
            from .reports import write_reports

            write_reports(self.store, run_id, summary)
        except asyncio.CancelledError:
            self.store.update(
                run_id,
                status="partial",
                partial=True,
                ended_at=now(),
                warnings=[
                    "Backend shutdown interrupted execution. Stored predictions are retained."
                ],
            )
        except Exception as exc:
            error = {
                "category": getattr(exc, "category", "runtime"),
                "message": str(sanitize(str(exc))),
            }
            # A failed disk write must never be presented as a completed evaluation.
            try:
                self.store.append(run_id, "errors", error)
                has_results = bool(self.store.records(run_id, "predictions"))
                self.store.update(
                    run_id,
                    status="partial" if has_results else "failed",
                    partial=has_results,
                    ended_at=now(),
                    warnings=[error["message"]],
                )
                self.store.event(run_id, "run.failed", error)
            except OSError:
                pass
        finally:
            for adapter in adapters.values():
                await adapter.close()

    async def _settle(self, run_id, coroutines):
        tasks = [asyncio.ensure_future(coroutine) for coroutine in coroutines]
        work = asyncio.gather(*tasks)
        cancelled = asyncio.create_task(self.cancellations[run_id].wait())
        try:
            done, _ = await asyncio.wait([work, cancelled], return_when=asyncio.FIRST_COMPLETED)
            if work in done:
                await work
            else:
                try:
                    await asyncio.wait_for(work, 5)
                except TimeoutError:
                    work.cancel()
                    await asyncio.gather(work, return_exceptions=True)
        finally:
            for task in tasks:
                if not task.done():
                    task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            if not work.done():
                work.cancel()
            await asyncio.gather(work, return_exceptions=True)
            cancelled.cancel()
            await asyncio.gather(cancelled, return_exceptions=True)

    async def evaluate(self, run_id, config, case, adapter, job, calibration, env):
        self.store.event(
            run_id,
            "case.started",
            {"case_id": case.id, "system_id": job["system_id"], "suite": job["suite"]},
        )
        started, epoch = time.perf_counter(), time.time()
        raw, answer, error, attempts = None, None, None, []
        maximum = config.systems.jev.max_retries if adapter.adapter_id == "jev" else 0
        for attempt in range(maximum + 1):
            before = time.perf_counter()
            try:
                raw = await adapter.predict_questions(case, job["batch_size"])
                answer = normalize(case, raw)
                for i in range(1, job["batch_size"]):
                    normalize(
                        case,
                        {
                            "answers": {
                                case.question.id: raw["answers"].get(f"{case.question.id}_{i}")
                            }
                        },
                    )
                if (
                    config.mode == "live"
                    and adapter.adapter_id == "jev"
                    and raw.get("model") != config.systems.jev.model
                ):
                    raise ProviderFailure(
                        "runtime", "Returned Jev model does not match the requested frozen version"
                    )
                attempts.append(
                    {
                        "attempt": attempt + 1,
                        "latency_ms": (time.perf_counter() - before) * 1000,
                        "status": "success",
                        "usage": provider_metadata(raw)[0],
                    }
                )
                break
            except (ProviderFailure, ValueError) as exc:
                answer = None
                error = {
                    "category": getattr(exc, "category", "normalization"),
                    "message": str(sanitize(str(exc))),
                    "retryable": getattr(exc, "retryable", False),
                    "provider_status": getattr(exc, "status", None),
                    "provider_response": getattr(exc, "body", None),
                }
                attempts.append(
                    {
                        "attempt": attempt + 1,
                        "latency_ms": (time.perf_counter() - before) * 1000,
                        "status": "failed",
                        "error": error,
                    }
                )
                if (
                    not error["retryable"]
                    or attempt == maximum
                    or self.cancellations[run_id].is_set()
                ):
                    break
                try:
                    await asyncio.wait_for(
                        self.cancellations[run_id].wait(),
                        max(getattr(exc, "retry_after", 0), min(0.5 * 2**attempt, 5)),
                    )
                    break
                except TimeoutError:
                    pass
        if answer and calibration:
            parameters = calibration["parameters"].get(f"{adapter.adapter_id}:{case.primitive}")
            if parameters is None:
                error, answer = (
                    {
                        "category": "normalization",
                        "message": "Calibration parameters missing for this primitive",
                    },
                    None,
                )
            else:
                answer = calibrate_answer(answer, parameters, case.primitive)
        ended = time.time()
        usage, runtime, metadata_warnings = provider_metadata(raw)
        envelope = raw if isinstance(raw, dict) else {}
        if adapter.adapter_id == "jev" and usage.get("input_tokens") is not None:
            usage["estimated_api_cost_usd"] = (
                usage["input_tokens"] * config.metrics.jev_usd_per_million_input_tokens / 1_000_000
            )
            usage["price_basis"] = (
                f"{config.metrics.jev_usd_per_million_input_tokens} USD per million input tokens"
            )
        retained_request = sanitize(case.request(), redact_keys=False)
        record = {
            **job,
            "schema_version": "1.0",
            "run_id": run_id,
            "family_id": case.family_id,
            "track": config.track,
            "status": "success" if answer else "failed",
            "answer": answer,
            "retry_count": len(attempts) - 1,
            "attempts": attempts,
            "usage": usage,
            "metadata_warnings": metadata_warnings,
            "error": None if answer else error,
            "raw_response": raw,
            "request": retained_request,
            "request_digest": digest_bytes(
                json.dumps(retained_request, ensure_ascii=False).encode()
            ),
            "request_redacted": retained_request != case.request(),
            "timing": {
                "started_at": now(),
                "started_at_epoch": epoch,
                "ended_at_epoch": ended,
                "latency_ms": (time.perf_counter() - started) * 1000,
                "is_warm": True,
                "queue_ms": runtime.get("queue_ms", 0),
                "inference_ms": runtime.get("inference_ms"),
            },
            "model": {
                "requested": config.systems.jev.model
                if adapter.adapter_id == "jev"
                else config.systems.laya.checkpoint,
                "resolved": envelope.get("model"),
                "route": runtime.get("route"),
                "device": runtime.get(
                    "device", "remote-api" if adapter.adapter_id == "jev" else "simulation"
                ),
                "checkpoint_revision": runtime.get("revision"),
                "effective_settings": runtime.get("effective_settings"),
            },
        }
        self.store.append(run_id, "predictions", record)
        if not answer:
            self.store.append(
                run_id, "errors", {"evaluation_id": job["evaluation_id"], **(error or {})}
            )
        manifest = self.store.manifest(run_id)
        progress = manifest["progress"]
        progress["completed"] += 1
        lane = progress["systems"].setdefault(
            job["system_id"], {"completed": 0, "failures": 0, "retries": 0}
        )
        lane["completed"] += 1
        lane["failures"] += answer is None
        lane["retries"] += len(attempts) - 1
        lane["latency_ms"] = record["timing"]["latency_ms"]
        self.store.update(run_id, progress=progress)
        try:
            process = psutil.Process()
            ram = process.memory_info().rss + sum(
                p.memory_info().rss for p in process.children() if p.is_running()
            )
            env["peak_process_ram_bytes"] = max(env["peak_process_ram_bytes"], ram)
        except (OSError, psutil.Error):
            env["resource_warning"] = (
                "Process RAM telemetry unavailable for one or more observations"
            )
        if runtime.get("accelerator_memory_bytes") is not None:
            env["accelerator_memory_bytes"] = max(
                env.get("accelerator_memory_bytes") or 0, runtime["accelerator_memory_bytes"]
            )
        self.store.write_json(self.store.run_dir(run_id) / "environment.json", env)
        self.store.event(
            run_id,
            "case.completed" if answer else "case.failed",
            {
                "case_id": case.id,
                "system_id": job["system_id"],
                "suite": job["suite"],
                "completed": progress["completed"],
                "total": progress["total"],
                "error": record["error"],
            },
        )

    def summary(self, run_id, cases=None, predictions=None):
        manifest = self.store.manifest(run_id)
        config = RunConfiguration.model_validate(manifest["effective_config"])
        reference_cases = self.store.records(run_id, "cases.snapshot")
        reference_predictions = self.store.records(run_id, "predictions")
        cases = reference_cases if cases is None else cases
        predictions = reference_predictions if predictions is None else predictions
        summary = compute_metrics(
            cases,
            predictions,
            **config.metrics.model_dump(
                exclude={
                    "local_hourly_cost_usd",
                    "local_cost_basis",
                    "jev_usd_per_million_input_tokens",
                }
            ),
            system_ids=[f"{key}-{config.track}" for key in ("jev", "laya")],
            reference_cases=reference_cases,
            reference_predictions=reference_predictions,
        )
        summary.update(
            run_id=run_id,
            track=config.track,
            simulation=config.mode == "fake",
            provisional=manifest["status"] not in TERMINAL,
            dataset_digest=config.dataset_digest,
            status=manifest["status"],
            partial=manifest["partial"],
            filter_options={"domains": sorted({c["domain"] for c in reference_cases})},
        )
        env_path = self.store.run_dir(run_id) / "environment.json"
        env = self.store.read_json(env_path) if env_path.exists() else {}
        warm_path = self.store.run_dir(run_id) / "warmup.json"
        warming = self.store.read_json(warm_path) if warm_path.exists() else {}
        for system, values in summary["systems"].items():
            values["resources"] = env
            warm = warming.get(system.split("-")[0], {})
            values["performance"]["warmup"] = {
                "cold_start_ms": warm.get("cold_start_ms"),
                "requests": len(warm.get("responses", [])),
            }
            if system.startswith("jev"):
                warm_usage = [
                    provider_metadata(r)[0].get("input_tokens") for r in warm.get("responses", [])
                ]
                known_tokens = [v for v in warm_usage if v is not None]
                values["cost"]["warmup_estimated_api_usd"] = (
                    sum(known_tokens) * config.metrics.jev_usd_per_million_input_tokens / 1_000_000
                    if known_tokens
                    else None
                )
                values["cost"]["warmup_usage_complete"] = len(known_tokens) == len(warm_usage)
            if system.startswith("laya") and config.metrics.local_hourly_cost_usd is not None:
                local = [p for p in predictions if p["adapter_id"] == "laya"]
                seconds = (
                    sum(
                        max(0, p["timing"]["latency_ms"] - p["timing"].get("queue_ms", 0))
                        for p in local
                    )
                    / 1000
                )
                values["cost"]["estimated_local_total_usd"] = (
                    seconds / 3600 * config.metrics.local_hourly_cost_usd
                )
                values["cost"]["local_basis"] = config.metrics.local_cost_basis
                values["cost"]["warmup_estimated_local_usd"] = (
                    warm.get("cold_start_ms", 0) / 3_600_000 * config.metrics.local_hourly_cost_usd
                )
        return summary

    def rescore(self, run_id):
        summary = self.summary(run_id)
        self.store.write_json(self.store.run_dir(run_id) / "summary.v1.0.0.json", summary)
        return summary

    async def close(self):
        for task in self.tasks.values():
            if not task.done():
                task.cancel()
        await asyncio.gather(*self.tasks.values(), return_exceptions=True)
