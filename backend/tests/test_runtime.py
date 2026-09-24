import asyncio
import json

import pytest
from test_contracts import case


def test_store_recovers_partial_and_does_not_escape_root(tmp_path):
    from decisionlab.store import Store

    store = Store(tmp_path)
    manifest = store.create_run({"name": "Interrupted"}, [case()], [])
    run_id = manifest["run_id"]
    store.append(run_id, "predictions", {"case_id": "saved", "status": "success"})
    with (store.run_dir(run_id) / "predictions.jsonl").open("ab") as file:
        file.write(b'{"torn":')
    reopened = Store(tmp_path)
    assert reopened.manifest(run_id)["status"] == "partial"
    assert reopened.records(run_id, "predictions") == [{"case_id": "saved", "status": "success"}]
    with pytest.raises(ValueError):
        reopened.run_dir("../outside")


async def test_fake_run_persists_results_and_cancellation(tmp_path):
    from decisionlab.runner import Runner
    from decisionlab.schemas import RunConfiguration
    from decisionlab.store import Store

    store = Store(tmp_path)
    runner = Runner(store)
    config = RunConfiguration(dataset_ref="demo", mode="fake", metrics={"bootstrap_samples": 10})
    manifest = await runner.create(config)
    await runner.tasks[manifest["run_id"]]
    run_id = manifest["run_id"]
    assert store.manifest(run_id)["status"] == "completed"
    predictions = store.records(run_id, "predictions")
    primary = [p for p in predictions if p["suite"] == "quality"]
    assert len(primary) == 288
    assert len({p["evaluation_id"] for p in primary}) == 288
    assert store.read_json(store.run_dir(run_id) / "summary.v1.0.0.json")["counts"]["cases"] == 144
    event_ids = [e["id"] for e in store.records(run_id, "events")]
    assert event_ids == list(range(1, len(event_ids) + 1))
    new = await runner.create(config)
    await asyncio.sleep(0.04)
    await runner.cancel(new["run_id"])
    await runner.tasks[new["run_id"]]
    assert store.manifest(new["run_id"])["status"] == "cancelled"
    assert len(store.records(new["run_id"], "predictions")) < 288
    await runner.close()


def test_calibration_refuses_evaluation_data():
    from decisionlab.calibration import fit_calibration

    with pytest.raises(ValueError, match="development"):
        fit_calibration([case(split="evaluation")], [], "sha256:example")


def test_publication_requires_independent_reviews(tmp_path):
    from decisionlab.governance import freeze_protocol, import_reviews
    from decisionlab.store import Store

    store = Store(tmp_path)
    with pytest.raises(ValueError, match="review"):
        freeze_protocol(store, "benchmark", {})
    with pytest.raises(ValueError):
        import_reviews(
            store, "demo", [{"case_id": "missing", "reviewer": "author", "answer": "billing"}]
        )


def test_api_import_security_and_export(tmp_path):
    from decisionlab.api import create_app
    from fastapi.testclient import TestClient

    with TestClient(create_app(tmp_path)) as client:
        assert client.get("/api/v1/health").status_code == 200
        response = client.post(
            "/api/v1/datasets/validate",
            files={"file": ("cases.jsonl", json.dumps(case()).encode())},
        )
        assert response.status_code == 200
        assert response.json()["valid"]
        assert response.json()["dataset_id"]
        preview = client.get("/api/v1/datasets/benchmark").json()
        assert all(c["split"] != "sealed" for c in preview["preview"])
        response = client.post(
            "/api/v1/runs",
            json={"dataset_ref": "demo", "mode": "fake"},
            headers={"origin": "https://evil.example"},
        )
        assert response.status_code == 403
        assert client.get("/api/v1/runs/..%2Foutside").status_code in (400, 404)
