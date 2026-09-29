import json

from fastapi.testclient import TestClient
from test_contracts import case


def dataset_jsonl():
    values = [
        case(id="dev", family_id="dev-family", split="development"),
        case(id="eval", family_id="eval-family", split="evaluation"),
    ]
    return "\n".join(json.dumps(value) for value in values) + "\n"


def test_workflow_api_prepares_lists_gets_and_cancels(tmp_path):
    from decisionlab.api import create_app

    app = create_app(tmp_path)
    with TestClient(app) as client:
        response = client.post(
            "/api/v1/benchmark-workflows",
            json={"name": "Support routing", "dataset_jsonl": dataset_jsonl()},
        )
        assert response.status_code == 201
        prepared = response.json()
        assert prepared["stage"] == "prepared"
        assert prepared["profile"] == "standard"
        workflow_id = prepared["workflow_id"]

        listing = client.get("/api/v1/benchmark-workflows").json()
        assert listing["total"] == 1
        assert listing["items"][0]["workflow_id"] == workflow_id
        assert client.get(f"/api/v1/benchmark-workflows/{workflow_id}").json()[
            "next_action"
        ].startswith("Confirm")

        cancelled = client.post(f"/api/v1/benchmark-workflows/{workflow_id}/cancel")
        assert cancelled.status_code == 200
        assert cancelled.json()["stage"] == "cancelled"


def test_workflow_api_validates_dataset_consent_and_report_state(tmp_path):
    from decisionlab.api import create_app

    app = create_app(tmp_path)
    with TestClient(app) as client:
        invalid = client.post(
            "/api/v1/benchmark-workflows",
            json={"name": "Broken", "dataset_jsonl": json.dumps(case())},
        )
        assert invalid.status_code == 400
        assert "development and evaluation" in invalid.json()["detail"]

        workflow_id = client.post(
            "/api/v1/benchmark-workflows",
            json={"name": "Support routing", "dataset_jsonl": dataset_jsonl()},
        ).json()["workflow_id"]
        advance = client.post(
            f"/api/v1/benchmark-workflows/{workflow_id}/advance", json={}
        )
        assert advance.status_code == 400
        assert "confirm" in advance.json()["detail"].lower()
        unavailable = client.get(f"/api/v1/benchmark-workflows/{workflow_id}/report")
        assert unavailable.status_code == 400
        assert "both frozen tracks" in unavailable.json()["detail"]
        assert client.get("/api/v1/benchmark-workflows/missing").status_code == 404


def test_workflow_api_returns_structured_no_clear_winner_report(tmp_path):
    from decisionlab.api import create_app

    app = create_app(tmp_path)
    with TestClient(app) as client:
        prepared = client.post(
            "/api/v1/benchmark-workflows",
            json={
                "name": "Support routing",
                "dataset_jsonl": dataset_jsonl(),
                "profile": "full",
                "publication": False,
            },
        ).json()
        record_path = app.state.workflow_manager._workflow_path(prepared["workflow_id"])
        record = app.state.store.read_json(record_path)
        record["stage"] = "completed"
        app.state.store.write_json(record_path, record)
        expected = {
            "workflow_id": prepared["workflow_id"],
            "default": {"winner": "no_clear_winner", "ci95": [-0.02, 0.12]},
            "production_tuned": {"winner": "jev", "ci95": [0.01, 0.10]},
            "markdown": "# DecisionLab benchmark report",
        }
        app.state.store.write_json(record["report_path"], expected)

        response = client.get(
            f"/api/v1/benchmark-workflows/{prepared['workflow_id']}/report"
        )
        assert response.status_code == 200
        assert response.json() == expected


def test_workflow_api_maps_active_run_conflict_to_409(tmp_path, monkeypatch):
    from decisionlab.api import create_app

    app = create_app(tmp_path)
    with TestClient(app) as client:
        workflow_id = client.post(
            "/api/v1/benchmark-workflows",
            json={"name": "Support routing", "dataset_jsonl": dataset_jsonl()},
        ).json()["workflow_id"]

        async def busy(*args, **kwargs):
            raise ValueError("An evaluation is already active")

        monkeypatch.setattr(app.state.workflow_manager, "advance", busy)
        response = client.post(
            f"/api/v1/benchmark-workflows/{workflow_id}/advance",
            json={"confirm_live_calls": True, "confirm_remote_data": True},
        )
        assert response.status_code == 409
