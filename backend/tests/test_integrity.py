import asyncio
import json

import httpx
import pytest
from test_contracts import case
from test_metrics import prediction


def seeded_run(store, cases=None, predictions=None, **changes):
    from decisionlab.runner import environment
    from decisionlab.schemas import RunConfiguration

    config = RunConfiguration(
        dataset_ref="demo", mode="fake", metrics={"bootstrap_samples": 10}, **changes
    )
    cases = cases or [case()]
    manifest = store.create_run(config.model_dump(), cases, [])
    run_id = manifest["run_id"]
    store.write_json(store.run_dir(run_id) / "environment.json", environment())
    for p in predictions or []:
        store.append(run_id, "predictions", p)
    store.update(
        run_id,
        status="completed",
        progress={"completed": len(predictions or []), "total": 2, "systems": {}},
    )
    return run_id


def test_performance_throughput_counts_questions_not_batches():
    from decisionlab.metrics import compute_metrics

    batch = prediction(
        suite="performance",
        batch_size=10,
        concurrency=1,
        timing={"latency_ms": 1000, "started_at_epoch": 1, "ended_at_epoch": 2},
    )
    summary = compute_metrics([case()], [prediction(), batch], bootstrap_samples=10)
    assert (
        summary["systems"]["jev-default"]["performance"]["load_tests"][0]["questions_per_second"]
        == 10
    )


def test_empty_and_missing_outcomes_have_explicit_denominators():
    from decisionlab.metrics import compute_metrics

    summary = compute_metrics(
        [case()], [], system_ids=["jev-default", "laya-default"], bootstrap_samples=10
    )
    assert summary["counts"]["missing_predictions"] == 2
    assert summary["systems"]["jev-default"]["correctness"]["accuracy"]["value"] == 0


def test_confidence_histogram_is_aggregated_on_the_backend():
    from decisionlab.metrics import compute_metrics

    summary = compute_metrics([case()], [prediction()], bootstrap_samples=10)
    bins = summary["systems"]["jev-default"]["calibration"]["confidence_histogram"]
    assert sum(b["correct"] for b in bins) == 1
    assert sum(b["incorrect"] for b in bins) == 0


def test_filtering_variants_retains_base_evidence_without_reweighting():
    from decisionlab.metrics import compute_metrics

    base = case()
    variant = case(
        id="variant",
        variant="paraphrase",
        transformation={"source_case_id": base["id"], "expected_relation": "invariant"},
    )
    predictions = [prediction(), prediction("variant")]
    summary = compute_metrics(
        [variant],
        [predictions[1]],
        reference_cases=[base, variant],
        reference_predictions=predictions,
        bootstrap_samples=10,
    )
    metrics = summary["systems"]["jev-default"]
    assert metrics["correctness"]["accuracy"]["denominator"] == 1
    assert metrics["robustness"][0]["comparable_count"] == 1
    assert metrics["robustness"][0]["answer_flip_rate"] == 0


async def test_runner_shutdown_stops_inflight_writes(tmp_path):
    from decisionlab.runner import Runner
    from decisionlab.schemas import RunConfiguration
    from decisionlab.store import Store

    store = Store(tmp_path)
    runner = Runner(store)
    manifest = await runner.create(
        RunConfiguration(dataset_ref="demo", mode="fake", metrics={"bootstrap_samples": 10})
    )
    await asyncio.sleep(0.05)
    await runner.close()
    before = store.records(manifest["run_id"], "predictions")
    await asyncio.sleep(0.05)
    assert store.records(manifest["run_id"], "predictions") == before


async def test_terminal_event_stream_tolerates_torn_final_line(tmp_path):
    from decisionlab.api import create_app

    app = create_app(tmp_path)
    run_id = seeded_run(app.state.store)
    with (app.state.store.run_dir(run_id) / "events.jsonl").open("ab") as file:
        file.write(b'{"torn":')
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await asyncio.wait_for(client.get(f"/api/v1/runs/{run_id}/events"), 1)
    assert response.status_code == 200
    assert "run.created" in response.text


async def test_final_summary_is_not_provisional(tmp_path):
    from decisionlab.runner import Runner
    from decisionlab.schemas import RunConfiguration
    from decisionlab.store import Store

    store = Store(tmp_path)
    metadata = store.add_dataset(json.dumps(case()).encode(), "Tiny")
    runner = Runner(store)
    run = await runner.create(
        RunConfiguration(
            dataset_ref=metadata["dataset_id"], mode="fake", metrics={"bootstrap_samples": 10}
        )
    )
    await runner.tasks[run["run_id"]]
    summary = store.read_json(store.run_dir(run["run_id"]) / "summary.v1.0.0.json")
    assert summary["provisional"] is False
    assert summary["status"] == "completed"


async def test_live_run_rejects_simulation_calibration_before_provider_calls(tmp_path):
    from decisionlab.runner import Runner
    from decisionlab.schemas import RunConfiguration
    from decisionlab.store import Store

    store = Store(tmp_path)
    store.write_json(
        store.path("calibrations", "fake-fit.json"),
        {
            "source_mode": "fake",
            "dataset_digest": "sha256:different",
            "family_ids": [],
            "parameters": {},
        },
    )
    config = RunConfiguration(
        dataset_ref="demo",
        mode="live",
        acknowledge_remote=True,
        track="production-tuned",
        calibration_id="fake-fit",
    )
    with pytest.raises(ValueError, match="Simulation"):
        await Runner(store).create(config)


def test_unreviewed_protocol_and_mutated_tuning_artifact_are_rejected(tmp_path):
    from decisionlab.calibration import inference_signature
    from decisionlab.governance import freeze_protocol, import_reviews, validate_protocol
    from decisionlab.schemas import RunConfiguration
    from decisionlab.store import Store

    store = Store(tmp_path)
    value = case(split="sealed")
    metadata = store.add_dataset(json.dumps(value).encode(), "Sealed")
    dataset_id = metadata["dataset_id"]
    import_reviews(
        store,
        dataset_id,
        [
            {
                "case_id": value["id"],
                "reviewer": "independent person",
                "answer": "billing",
                "rationale": "The explicit billing policy applies.",
            }
        ],
    )
    store.write_json(
        store.path("calibrations", "fit.json"),
        {
            "source_mode": "live",
            "dataset_digest": "sha256:development",
            "family_ids": [],
            "parameters": {},
        },
    )
    configurations = {
        track: RunConfiguration(
            dataset_ref=dataset_id,
            dataset_digest=metadata["digest"],
            track=track,
            mode="live",
            acknowledge_remote=True,
            systems={"laya": {"checkpoint_revision": "a" * 40}},
            calibration_id="fit" if track == "production-tuned" else None,
        )
        for track in ("default", "production-tuned")
    }
    fit = store.read_json(store.path("calibrations", "fit.json"))
    fit["inference_signature"] = inference_signature(configurations["production-tuned"])
    store.write_json(store.path("calibrations", "fit.json"), fit)
    protocol = freeze_protocol(store, dataset_id, configurations)
    config = configurations["production-tuned"]
    config.protocol_id = protocol["protocol_id"]
    store.write_json(
        store.path("calibrations", "fit.json"),
        {"source_mode": "live", "parameters": {"changed": True}},
    )
    with pytest.raises(ValueError, match="artifact"):
        validate_protocol(store, config)
