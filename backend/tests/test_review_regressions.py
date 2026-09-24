import asyncio
import copy
import json

import pytest
from test_contracts import case


async def test_lane_exception_cancels_and_awaits_siblings(tmp_path, monkeypatch):
    from decisionlab import runner as module
    from decisionlab.adapters import FakeAdapter
    from decisionlab.schemas import RunConfiguration
    from decisionlab.store import Store

    class FailingLane(FakeAdapter):
        async def predict_questions(self, value, batch_size):
            if self.adapter_id == "jev":
                raise RuntimeError("Unexpected lane failure")
            await asyncio.sleep(0.06)
            return await super().predict_questions(value, batch_size)

    monkeypatch.setattr(module, "FakeAdapter", FailingLane)
    store = Store(tmp_path)
    dataset = store.add_dataset(json.dumps(case()).encode())
    runner = module.Runner(store)
    run_id = (
        await runner.create(RunConfiguration(dataset_ref=dataset["dataset_id"], mode="fake"))
    )["run_id"]
    await runner.tasks[run_id]
    before = store.records(run_id, "predictions")
    await asyncio.sleep(0.1)
    assert store.records(run_id, "predictions") == before


async def test_sensitive_looking_label_keys_survive_persistence(tmp_path, monkeypatch):
    from decisionlab.runner import Runner
    from decisionlab.schemas import EvaluationCase, RunConfiguration
    from decisionlab.store import Store

    value = case(
        expected={"value": "password"},
        question={
            "id": "decision",
            "type": "choice",
            "instructions": "Route requests",
            "criteria": {"password": "Reset password", "api_key": "Rotate API key"},
        },
    )
    store = Store(tmp_path)
    secret = "test-provider-credential"
    monkeypatch.setenv("TYPESAFE_API_KEY", secret)
    credential_path = tmp_path / "redaction-check.json"
    store.write_json(credential_path, {"api_key": secret, "Authorization": f"Bearer {secret}"})
    assert secret not in credential_path.read_text()
    assert "[REDACTED]" in credential_path.read_text()
    dataset = store.add_dataset(json.dumps(value).encode())
    runner = Runner(store)
    run_id = (
        await runner.create(
            RunConfiguration(
                dataset_ref=dataset["dataset_id"], mode="fake", metrics={"bootstrap_samples": 10}
            )
        )
    )["run_id"]
    await runner.tasks[run_id]
    assert store.manifest(run_id)["status"] == "completed"
    for record in store.records(run_id, "predictions"):
        assert all(isinstance(v, float) for v in record["answer"]["probabilities"].values())
        assert record["request"] == EvaluationCase.model_validate(value).request()
        from decisionlab.datasets import digest_bytes

        assert record["request_digest"] == digest_bytes(
            json.dumps(record["request"], ensure_ascii=False).encode()
        )


@pytest.mark.parametrize(
    "status,expected,retry",
    [
        (401, "authentication", False),
        (400, "invalid_request", False),
        (413, "context_limit", False),
        (429, "rate_limit", True),
        (503, "runtime", True),
        (200, "normalization", False),
    ],
)
async def test_jev_uses_actual_sdk_error_contract(status, expected, retry):
    from decisionlab.adapters import JevAdapter, ProviderFailure
    from decisionlab.schemas import EvaluationCase, JevConfiguration
    from typesafe_sdk import TypeSafeAPIError, TypeSafeAPIResponseValidationError

    error = (
        TypeSafeAPIResponseValidationError(status, {}, {}, "answers")
        if status == 200
        else TypeSafeAPIError(status, {}, {"retry-after": "4"})
    )

    class Client:
        async def system_one(self, **kwargs):
            raise error

    adapter = JevAdapter(JevConfiguration())
    adapter.client = Client()
    with pytest.raises(ProviderFailure) as caught:
        await adapter.predict(EvaluationCase.model_validate(case()))
    assert caught.value.category == expected
    assert caught.value.retryable == retry
    assert caught.value.status == status
    if status == 429:
        assert caught.value.retry_after == 4


@pytest.mark.parametrize("change", ["list", "usage_null", "tokens_string", "runtime_null", "nan"])
async def test_malformed_envelopes_are_retained_per_decision(tmp_path, change):
    from decisionlab.adapters import FakeAdapter
    from decisionlab.runner import Runner, environment, make_schedule
    from decisionlab.schemas import EvaluationCase, RunConfiguration
    from decisionlab.store import Store

    class Malformed(FakeAdapter):
        async def predict_questions(self, value, batch_size):
            raw = await super().predict_questions(value, batch_size)
            if change == "list":
                return [raw]
            if change == "usage_null":
                raw["usage"] = None
            if change == "tokens_string":
                raw["usage"] = {"input_tokens": "3"}
            if change == "runtime_null":
                raw["_runtime"] = None
            if change == "nan":
                raw["answers"]["decision"]["probabilities"]["billing"] = float("nan")
            return raw

    store = Store(tmp_path)
    runner = Runner(store)
    value = EvaluationCase.model_validate(case())
    config = RunConfiguration(dataset_ref="demo", mode="fake")
    schedule = make_schedule(config, [value])
    run_id = store.create_run(config.model_dump(), [value], schedule)["run_id"]
    runner.cancellations[run_id] = asyncio.Event()
    await runner.evaluate(
        run_id, config, value, Malformed("jev", delay=0), schedule[0], None, environment()
    )
    records = store.records(run_id, "predictions")
    assert len(records) == 1
    assert records[0]["status"] == ("failed" if change in ("list", "nan") else "success")
    if change == "tokens_string":
        assert "input_tokens" not in records[0]["usage"]


def test_cardinality_diagnostic_does_not_put_every_gold_first():
    from decisionlab.benchmark import build_datasets, diagnostic_cases
    from decisionlab.schemas import EvaluationCase

    dev, _ = build_datasets()
    inputs = [EvaluationCase.model_validate(c) for c in dev]
    values = diagnostic_cases(inputs, cardinality=True)
    positions = [list(c["question"]["criteria"]).index(c["expected"]["value"]) for c in values]
    assert len(set(positions)) > 2
    assert all("option_order_seed" in c["metadata"] for c in values)
    assert diagnostic_cases(inputs, cardinality=True) == values


def test_new_protocol_cannot_make_seen_evaluation_publishable(tmp_path):
    from decisionlab.governance import (
        freeze_protocol,
        import_reviews,
        register_protocol_run,
        validate_protocol,
    )
    from decisionlab.schemas import RunConfiguration
    from decisionlab.store import Store

    store = Store(tmp_path)
    value = case(split="sealed")
    dataset = store.add_dataset(json.dumps(value).encode())
    dataset_id = dataset["dataset_id"]
    import_reviews(
        store,
        dataset_id,
        [
            {
                "case_id": value["id"],
                "reviewer": "Reviewer",
                "answer": "billing",
                "rationale": "Policy.",
            }
        ],
    )
    configs = {
        track: RunConfiguration(
            dataset_ref=dataset_id,
            dataset_digest=dataset["digest"],
            track=track,
            mode="live",
            publication=True,
            acknowledge_remote=True,
            systems={"laya": {"checkpoint_revision": "a" * 40}},
        )
        for track in ("default", "production-tuned")
    }
    first = freeze_protocol(store, dataset_id, configs)
    # Even a second protocol frozen before execution cannot later supersede the first run.
    alternate = freeze_protocol(store, dataset_id, configs)
    configs["default"].protocol_id = first["protocol_id"]
    run = store.create_run(configs["default"].model_dump(), [value], [])
    register_protocol_run(store, configs["default"], run["run_id"])
    store.update(run["run_id"], status="completed")
    stale = copy.deepcopy(configs["default"])
    stale.protocol_id = alternate["protocol_id"]
    with pytest.raises(ValueError, match="exploratory"):
        validate_protocol(store, stale)
    with pytest.raises(ValueError, match="exploratory"):
        freeze_protocol(store, dataset_id, configs)
    for config in configs.values():
        config.publication = False
        config.protocol_id = None
    exploratory = freeze_protocol(store, dataset_id, configs)
    assert exploratory["exploratory"] is True
