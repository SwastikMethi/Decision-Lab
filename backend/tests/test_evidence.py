import asyncio
import io
import json
import zipfile

import pytest
from test_contracts import case
from test_integrity import seeded_run
from test_metrics import prediction


@pytest.mark.parametrize("mismatch", [False, True])
async def test_retries_produce_one_outcome_and_version_mismatch_is_failure(tmp_path, mismatch):
    from decisionlab.adapters import FakeAdapter, ProviderFailure
    from decisionlab.runner import Runner, environment, make_schedule
    from decisionlab.schemas import EvaluationCase, RunConfiguration
    from decisionlab.store import Store

    class RetryingAdapter(FakeAdapter):
        calls = 0

        async def predict_questions(self, value, batch_size):
            self.calls += 1
            if self.calls == 1 and not mismatch:
                raise ProviderFailure("rate_limit", "Try again", retryable=True)
            result = await super().predict_questions(value, batch_size)
            result["model"] = "jev-wrong" if mismatch else "jev-1.13.0"
            return result

    value = EvaluationCase.model_validate(case())
    config = RunConfiguration(dataset_ref="demo", mode="live", acknowledge_remote=True)
    store = Store(tmp_path)
    runner = Runner(store)
    schedule = make_schedule(config, [value])
    run_id = store.create_run(config.model_dump(), [value], schedule)["run_id"]
    runner.cancellations[run_id] = asyncio.Event()
    adapter = RetryingAdapter("jev", delay=0)
    await runner.evaluate(run_id, config, value, adapter, schedule[0], None, environment())
    records = store.records(run_id, "predictions")
    assert len(records) == 1
    assert records[0]["status"] == ("failed" if mismatch else "success")
    assert len(records[0]["attempts"]) == (1 if mismatch else 2)
    assert records[0]["retry_count"] == (0 if mismatch else 1)


def test_frozen_threshold_is_applied_without_refitting():
    from decisionlab.calibration import calibrate_answer
    from decisionlab.metrics import compute_metrics

    raw = prediction()
    raw["answer"] = calibrate_answer(raw["answer"], {"temperature": 1, "threshold": 0.9}, "choice")
    summary = compute_metrics([case()], [raw], bootstrap_samples=10)
    frozen = summary["systems"]["jev-default"]["selective_automation"]["frozen_policy"]
    assert frozen["accepted"] == 0
    assert frozen["risk"] is None
    assert frozen["coverage"] == 0


def test_bundle_roundtrip_checksums_and_safe_structured_html(tmp_path):
    from decisionlab.datasets import digest_bytes
    from decisionlab.reports import bundle, write_reports
    from decisionlab.runner import Runner
    from decisionlab.store import Store

    store = Store(tmp_path)
    run_id = seeded_run(store, predictions=[prediction()])
    store.update(run_id, name="<script>alert(1)</script>")
    summary = Runner(store).rescore(run_id)
    write_reports(store, run_id, summary)
    with zipfile.ZipFile(io.BytesIO(bundle(store, run_id))) as archive:
        checksums = json.loads(archive.read("checksums.json"))
        assert all(digest_bytes(archive.read(name)) == digest for name, digest in checksums.items())
        document = archive.read("report.html").decode()
        assert "<table>" in document
        assert "<script>" not in document
        assert json.loads(archive.read("summary.v1.0.0.json")) == summary


def test_ordinal_metrics_and_semantic_opaque_alignment():
    from decisionlab.metrics import compute_metrics

    ordinal = case(
        primitive="score",
        question={
            "id": "q",
            "type": "score",
            "instructions": "Grade",
            "criteria": ["low", "medium", "high"],
        },
        expected={"value": 1},
    )
    value = prediction("score-base", probabilities={"0": 0.2, "1": 0.3, "2": 0.5}, selected="2")
    result = compute_metrics([ordinal], [value], bootstrap_samples=10)["systems"]["jev-default"]
    assert result["correctness"]["ordinal_mae"]["value"] == pytest.approx(0.3)
    assert result["correctness"]["ranked_probability_score"]["value"] == pytest.approx(0.145)
    opaque = case(
        id="opaque",
        variant="opaque_labels",
        label_map={"X": "billing", "Y": "technical"},
        expected={"value": "X"},
        transformation={"source_case_id": "choice-base", "expected_relation": "invariant"},
        question={
            "id": "q",
            "type": "choice",
            "instructions": "Route",
            "criteria": {"X": "Bill", "Y": "Technical"},
        },
    )
    result = compute_metrics(
        [case(), opaque],
        [prediction(), prediction("opaque", {"X": 0.8, "Y": 0.2}, "X")],
        bootstrap_samples=10,
    )
    robust = result["systems"]["jev-default"]["robustness"][0]
    assert robust["answer_flip_rate"] == 0
    assert robust["probability_drift"]["value"] == pytest.approx(0)


async def test_second_backend_cannot_recover_an_active_first_backend(tmp_path):
    from decisionlab.api import create_app

    first = create_app(tmp_path)
    async with first.router.lifespan_context(first):
        run_id = seeded_run(first.state.store)
        first.state.store.update(run_id, status="running")
        second = create_app(tmp_path)
        with pytest.raises(ValueError, match="already"):
            async with second.router.lifespan_context(second):
                pass
        assert first.state.store.manifest(run_id)["status"] == "running"


async def test_optional_memory_telemetry_failure_does_not_abort_a_run(tmp_path, monkeypatch):
    import psutil
    from decisionlab.runner import Runner
    from decisionlab.schemas import RunConfiguration
    from decisionlab.store import Store

    def denied(*args, **kwargs):
        raise PermissionError("Process inspection restricted")

    monkeypatch.setattr(psutil.Process, "children", denied)
    store = Store(tmp_path)
    metadata = store.add_dataset(json.dumps(case()).encode())
    runner = Runner(store)
    run_id = (
        await runner.create(
            RunConfiguration(
                dataset_ref=metadata["dataset_id"], mode="fake", metrics={"bootstrap_samples": 10}
            )
        )
    )["run_id"]
    await runner.tasks[run_id]
    assert store.manifest(run_id)["status"] == "completed"
    assert (
        "unavailable"
        in store.read_json(store.run_dir(run_id) / "environment.json")["resource_warning"]
    )


async def test_calibration_requires_matching_inference_configuration(tmp_path):
    from decisionlab.calibration import inference_signature
    from decisionlab.runner import Runner
    from decisionlab.schemas import RunConfiguration
    from decisionlab.store import Store

    store = Store(tmp_path)
    original = RunConfiguration(dataset_ref="demo", mode="fake")
    fit = {
        "source_mode": "fake",
        "dataset_digest": "sha256:development",
        "family_ids": [],
        "inference_signature": inference_signature(original),
        "parameters": {},
    }
    store.write_json(store.path("calibrations", "fit.json"), fit)
    config = RunConfiguration(
        dataset_ref="demo",
        mode="fake",
        track="production-tuned",
        calibration_id="fit",
        instruction_overrides={"choice": "A new decision policy"},
    )
    with pytest.raises(ValueError, match="configuration"):
        await Runner(store).create(config)


def test_ten_thousand_cases_are_paginated_and_sse_replays(tmp_path):
    from decisionlab.api import create_app
    from fastapi.testclient import TestClient

    app = create_app(tmp_path)
    values = [case(id=f"row-{i:05}", family_id=f"family-{i}") for i in range(10000)]
    run_id = seeded_run(app.state.store, cases=values)
    app.state.store.event(run_id, "run.completed", {"status": "completed"})
    with TestClient(app) as client:
        result = client.get(f"/api/v1/runs/{run_id}/cases", params={"page": 200}).json()
        assert result["total"] == 10000
        assert len(result["items"]) == 50
        assert result["items"][0]["case"]["id"] == "row-09950"
        assert all("state" not in row["case"] for row in result["items"])
        replay = client.get(f"/api/v1/runs/{run_id}/events", headers={"Last-Event-ID": "1"})
        assert "run.created" not in replay.text
        assert "run.completed" in replay.text


def test_sealed_results_and_exports_release_only_after_both_tracks(tmp_path):
    from decisionlab.api import create_app
    from decisionlab.governance import release_protocol
    from fastapi.testclient import TestClient

    app = create_app(tmp_path)
    store = app.state.store
    sealed = case(split="sealed")
    first = seeded_run(store, cases=[sealed], predictions=[prediction()])
    second = seeded_run(store, cases=[sealed], track="production-tuned")
    store.update(second, status="running")
    protocol = {"runs": {"default": first, "production-tuned": second}, "sealed_released": False}
    store.write_json(store.path("protocols", "pair.json"), protocol)
    release_protocol(store, "pair")
    assert not store.manifest(first)["sealed_released"]
    with TestClient(app) as client:
        assert client.get(f"/api/v1/runs/{first}/cases").json()["total"] == 0
        assert client.get(f"/api/v1/runs/{first}/exports/bundle").status_code == 403
        store.update(second, status="completed")
        release_protocol(store, "pair")
        assert client.get(f"/api/v1/runs/{first}/cases").json()["total"] == 1
        assert client.get(f"/api/v1/runs/{first}/exports/bundle").status_code == 200
