import copy
import json

import httpx
import pytest
from decisionlab.api import create_app
from decisionlab.runner import make_schedule
from decisionlab.schemas import EvaluationCase, RunConfiguration
from test_contracts import case


def playback_run(store, values=None, extra=False):
    cases = [EvaluationCase.model_validate(c) for c in (values or [case()])]
    config = RunConfiguration(
        dataset_ref="demo",
        mode="fake",
        suites={
            "repeatability": {"enabled": extra, "sample_size": 1, "repetitions": 2},
            "performance": {
                "enabled": extra,
                "sample_size": 1,
                "concurrency": [1, 4],
                "batch_sizes": [1, 5],
            },
        },
    )
    jobs = make_schedule(config, cases)
    run_id = store.create_run(config.model_dump(), cases, jobs)["run_id"]
    return run_id, jobs


def save_answer(store, run_id, job, selected="billing", probabilities=None, failed=False):
    store.append(
        run_id,
        "predictions",
        {
            **job,
            "status": "failed" if failed else "success",
            "answer": None
            if failed
            else {
                "selected": selected,
                "probabilities": probabilities or {"billing": 0.8, "technical": 0.2},
                "score": None,
            },
            "timing": {"latency_ms": 42},
            "retry_count": 1,
            "error": {"message": "Provider unavailable"} if failed else None,
            "raw_response": {"private_payload": "must not appear in playback"},
            "request": {"private_request": "must not appear in playback"},
        },
    )


async def test_playback_pairs_every_scheduled_request_and_keeps_cursor_stable(tmp_path):
    app = create_app(tmp_path)
    store = app.state.store
    run_id, jobs = playback_run(store, extra=True)
    save_answer(store, run_id, jobs[0])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        response = await client.get(f"/api/v1/runs/{run_id}/playback?limit=2")
        assert response.status_code == 200
        page = response.json()
        assert page["total_frames"] == 7
        assert page["next_cursor"] == 1
        frame = page["items"][0]
        assert frame["ordinal"] == 0
        assert frame["systems"]["jev"]["correctness"] is True
        assert frame["systems"]["laya"]["state"] == "pending"
        assert frame["systems"]["laya"]["correctness"] is None
        assert frame["systems"]["jev"]["evaluation_id"] == jobs[0]["evaluation_id"]
        assert "private_payload" not in response.text and "private_request" not in response.text
        original = copy.deepcopy(page)
        save_answer(store, run_id, jobs[1], selected="technical")
        refreshed = (await client.get(f"/api/v1/runs/{run_id}/playback?limit=2")).json()
        assert refreshed["items"][0]["key"] == original["items"][0]["key"]
        assert refreshed["items"][0]["systems"]["laya"]["correctness"] is False
        rest = (await client.get(f"/api/v1/runs/{run_id}/playback?after=1&limit=100")).json()
        all_frames = refreshed["items"] + rest["items"]
        assert len({f["key"] for f in all_frames}) == 7
        assert [f["batch_size"] for f in all_frames] == [1, 1, 1, 1, 5, 1, 5]
        assert rest["next_cursor"] is None
        assert (await client.get(f"/api/v1/runs/{run_id}/playback?limit=101")).status_code == 422


async def test_sealed_frames_are_opaque_until_release_and_missing_is_not_wrong(tmp_path):
    app = create_app(tmp_path)
    store = app.state.store
    run_id, jobs = playback_run(store, [case(split="sealed")])
    save_answer(store, run_id, jobs[0])
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        page = (await client.get(f"/api/v1/runs/{run_id}/playback")).json()
        assert "items" in page
        assert page["withheld_frames"] == 1
        assert page["items"][0]["case"] is None
        assert page["items"][0]["systems"] == {}
        assert "billing" not in json.dumps(page)
        store.update(run_id, status="cancelled", sealed_released=True)
        before = {p.name: p.read_bytes() for p in store.run_dir(run_id).iterdir() if p.is_file()}
        released = (await client.get(f"/api/v1/runs/{run_id}/playback")).json()
        assert released["withheld_frames"] == 0
        assert released["items"][0]["systems"]["laya"]["state"] == "not_completed"
        assert released["items"][0]["systems"]["laya"]["correctness"] is None
        assert before == {
            p.name: p.read_bytes() for p in store.run_dir(run_id).iterdir() if p.is_file()
        }


@pytest.mark.parametrize(
    "primitive,criteria,expected,selected,probabilities,labels",
    [
        ("noul", "Is it urgent?", True, "false", {"false": 0.8, "true": 0.2}, ["No", "Yes"]),
        (
            "score",
            ["Low", "Medium", "High"],
            2,
            "2",
            {"0": 0.1, "1": 0.2, "2": 0.7},
            ["Low", "Medium", "High"],
        ),
    ],
)
async def test_native_options_and_failures(
    tmp_path, primitive, criteria, expected, selected, probabilities, labels
):
    app = create_app(tmp_path)
    store = app.state.store
    value = case(
        primitive=primitive,
        question={"id": "q", "type": primitive, "instructions": "Decide", "criteria": criteria},
        expected={"value": expected},
    )
    run_id, jobs = playback_run(store, [value])
    save_answer(store, run_id, jobs[0], selected, probabilities)
    save_answer(store, run_id, jobs[1], failed=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://testserver"
    ) as client:
        page = (await client.get(f"/api/v1/runs/{run_id}/playback")).json()
        assert "items" in page
        frame = page["items"][0]
        assert [o["label"] for o in frame["case"]["options"]] == labels
        assert frame["systems"]["jev"]["probabilities"] == probabilities
        assert frame["systems"]["jev"]["correctness"] is (primitive == "score")
        assert frame["systems"]["laya"]["state"] == "failed"
        assert frame["systems"]["laya"]["correctness"] is None
        assert page["latest_available"] == 0
