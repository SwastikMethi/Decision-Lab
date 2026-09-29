import json

import pytest
from test_contracts import case


def dataset_bytes(*values):
    return ("\n".join(json.dumps(value) for value in values) + "\n").encode()


def workflow_cases():
    return (
        case(id="dev", family_id="dev-family", split="development"),
        case(id="eval", family_id="eval-family", split="evaluation"),
    )


class FakeRunner:
    def __init__(self, store):
        self.store = store
        self.created = []
        self.cancelled = []

    async def create(self, config):
        from decisionlab.governance import register_protocol_run

        config.systems.laya.checkpoint_revision = "a" * 40
        _, cases = self.store.dataset(config.dataset_ref)
        manifest = self.store.create_run(config.model_dump(), cases, [])
        register_protocol_run(self.store, config, manifest["run_id"])
        self.created.append(manifest["run_id"])
        return manifest

    async def cancel(self, run_id):
        self.cancelled.append(run_id)
        return self.store.update(run_id, status="cancelled", partial=True)

    def summary(self, run_id):
        manifest = self.store.manifest(run_id)
        track = manifest["track"]
        suffix = track
        return {
            "status": "completed",
            "partial": False,
            "systems": {
                f"jev-{suffix}": system_metrics(0.75),
                f"laya-{suffix}": system_metrics(0.70),
            },
            "comparisons": [
                {
                    "metric": "accuracy",
                    "left": f"jev-{suffix}",
                    "right": f"laya-{suffix}",
                    "difference": 0.05,
                    "ci95": [-0.02, 0.12],
                    "families": 10,
                }
            ],
        }


def system_metrics(accuracy):
    return {
        "correctness": {
            "accuracy": {"value": accuracy},
            "macro_f1": {"value": accuracy - 0.01},
        },
        "calibration": {"brier": {"value": 0.1}, "ece": {"value": 0.03}},
        "failures": {"count": 0, "rate": 0.0},
        "performance": {"warm_p50_ms": 10.0, "warm_p95_ms": 20.0, "load_tests": []},
        "cost": {"provider_reported_total_usd": 0.01, "per_1000_decisions_usd": 0.1},
        "robustness": [],
        "repeatability": [],
        "selective_automation": {"frozen_policy": None},
    }


def complete_development(store, workflow, run_id, adapters=("jev", "laya")):
    for adapter in adapters:
        store.append(
            run_id,
            "predictions",
            {
                "case_id": "dev",
                "adapter_id": adapter,
                "system_id": f"{adapter}-default",
                "suite": "quality",
                "status": "success",
                "answer": {
                    "selected": "billing",
                    "probabilities": {"billing": 0.8, "technical": 0.2},
                },
            },
        )
    store.update(run_id, status="completed", partial=False)


def test_prepare_partitions_dataset_and_writes_blind_review_packet(tmp_path):
    from decisionlab.store import Store
    from decisionlab.workflows import BenchmarkWorkflowManager

    store = Store(tmp_path)
    manager = BenchmarkWorkflowManager(store, FakeRunner(store))
    dev, evaluation = workflow_cases()

    prepared = manager.create("Routing benchmark", dataset_bytes(dev, evaluation))

    assert prepared["stage"] == "prepared"
    assert prepared["profile"] == "standard"
    assert prepared["publication"] is False
    assert prepared["estimates"]["development"]["requests"] == 2
    assert store.dataset(prepared["datasets"]["development"])[1][0].id == "dev"
    assert store.dataset(prepared["datasets"]["evaluation"])[1][0].id == "eval"
    packet = store.read_json(prepared["review"]["packet_path"])
    assert packet["cases"][0]["id"] == "eval"
    assert "expected" not in packet["cases"][0]
    assert "metadata" not in packet["cases"][0]
    assert manager.get(prepared["workflow_id"])["workflow_id"] == prepared["workflow_id"]
    assert [item["workflow_id"] for item in manager.list()] == [prepared["workflow_id"]]


def test_prepare_requires_development_and_evaluation_partitions(tmp_path):
    from decisionlab.store import Store
    from decisionlab.workflows import BenchmarkWorkflowManager

    store = Store(tmp_path)
    manager = BenchmarkWorkflowManager(store, FakeRunner(store))

    with pytest.raises(ValueError, match="development and evaluation"):
        manager.create("Incomplete", dataset_bytes(workflow_cases()[0]))


def test_prepare_requires_development_coverage_for_evaluation_primitives(tmp_path):
    from decisionlab.store import Store
    from decisionlab.workflows import BenchmarkWorkflowManager

    store = Store(tmp_path)
    manager = BenchmarkWorkflowManager(store, FakeRunner(store))
    development = case(id="dev", family_id="dev-family", split="development")
    evaluation = case(primitive="score", id="eval", family_id="eval-family", split="evaluation")

    with pytest.raises(ValueError, match="score"):
        manager.create("Missing coverage", dataset_bytes(development, evaluation))


async def test_advance_requires_consent_and_starts_at_most_one_run(tmp_path):
    from decisionlab.store import Store
    from decisionlab.workflows import BenchmarkWorkflowManager

    store = Store(tmp_path)
    runner = FakeRunner(store)
    manager = BenchmarkWorkflowManager(store, runner)
    workflow = manager.create("Routing benchmark", dataset_bytes(*workflow_cases()))

    with pytest.raises(ValueError, match="confirm"):
        await manager.advance(workflow["workflow_id"])
    assert runner.created == []

    started = await manager.advance(
        workflow["workflow_id"], confirm_live_calls=True, confirm_remote_data=True
    )
    assert started["stage"] == "development_running"
    assert len(runner.created) == 1
    same = await manager.advance(workflow["workflow_id"])
    assert same["stage"] == "development_running"
    assert len(runner.created) == 1
    assert started["authorization"]["fingerprint"].startswith("sha256:")


async def test_workflow_pauses_for_review_then_completes_both_tracks(tmp_path):
    from decisionlab.store import Store
    from decisionlab.workflows import BenchmarkWorkflowManager

    store = Store(tmp_path)
    runner = FakeRunner(store)
    manager = BenchmarkWorkflowManager(store, runner)
    workflow = manager.create("Routing benchmark", dataset_bytes(*workflow_cases()))
    workflow_id = workflow["workflow_id"]
    started = await manager.advance(workflow_id, confirm_live_calls=True, confirm_remote_data=True)
    dev_run = started["runs"]["development"]
    complete_development(store, workflow, dev_run)

    waiting = await manager.advance(workflow_id)
    assert waiting["stage"] == "waiting_for_review"
    assert len(runner.created) == 1
    assert waiting["review"]["approved"] == 0

    store.write_json(
        waiting["review"]["submission_path"],
        [
            {
                "case_id": "eval",
                "reviewer": "Independent reviewer",
                "answer": "billing",
                "rationale": "The policy sends payment issues to Billing.",
            }
        ],
    )
    default_running = await manager.advance(workflow_id)
    assert default_running["stage"] == "default_running"
    assert default_running["calibration_id"]
    assert default_running["protocol_id"]
    assert len(runner.created) == 2

    store.update(default_running["runs"]["default"], status="completed", partial=False)
    tuned_running = await manager.advance(workflow_id)
    assert tuned_running["stage"] == "tuned_running"
    assert len(runner.created) == 3

    store.update(tuned_running["runs"]["production-tuned"], status="completed", partial=False)
    completed = await manager.advance(workflow_id)
    assert completed["stage"] == "completed"
    assert len(runner.created) == 3
    report = manager.report(workflow_id)
    assert report["default"]["winner"] == "no_clear_winner"
    assert report["production_tuned"]["winner"] == "no_clear_winner"
    assert "No clear winner" in report["markdown"]


async def test_missing_provider_calibration_blocks_before_evaluation(tmp_path):
    from decisionlab.store import Store
    from decisionlab.workflows import BenchmarkWorkflowManager

    store = Store(tmp_path)
    runner = FakeRunner(store)
    manager = BenchmarkWorkflowManager(store, runner)
    workflow = manager.create("Missing calibration", dataset_bytes(*workflow_cases()))
    started = await manager.advance(
        workflow["workflow_id"], confirm_live_calls=True, confirm_remote_data=True
    )
    complete_development(store, workflow, started["runs"]["development"], adapters=("jev",))

    blocked = await manager.advance(workflow["workflow_id"])

    assert blocked["stage"] == "blocked"
    assert "laya:choice" in blocked["blocker"]
    assert len(runner.created) == 1
    assert manager.get(workflow["workflow_id"])["blocker"] == blocked["blocker"]


async def test_no_usable_calibration_blocks_before_evaluation(tmp_path):
    from decisionlab.store import Store
    from decisionlab.workflows import BenchmarkWorkflowManager

    store = Store(tmp_path)
    runner = FakeRunner(store)
    manager = BenchmarkWorkflowManager(store, runner)
    workflow = manager.create("No calibration", dataset_bytes(*workflow_cases()))
    started = await manager.advance(
        workflow["workflow_id"], confirm_live_calls=True, confirm_remote_data=True
    )
    store.update(started["runs"]["development"], status="completed", partial=False)

    blocked = await manager.advance(workflow["workflow_id"])

    assert blocked["stage"] == "blocked"
    assert "No eligible development predictions" in blocked["blocker"]
    assert len(runner.created) == 1


async def test_advance_recovers_protocol_frozen_before_workflow_save(tmp_path, monkeypatch):
    from decisionlab import governance
    from decisionlab.store import Store
    from decisionlab.workflows import BenchmarkWorkflowManager

    timestamps = iter(["2026-01-01T00:00:00Z", "2026-01-01T00:00:01Z", "2026-01-01T00:00:02Z"])
    monkeypatch.setattr(governance, "now", lambda: next(timestamps))
    store = Store(tmp_path)
    runner = FakeRunner(store)
    manager = BenchmarkWorkflowManager(store, runner)
    workflow = manager.create("Recover freeze", dataset_bytes(*workflow_cases()))
    workflow_id = workflow["workflow_id"]
    started = await manager.advance(workflow_id, confirm_live_calls=True, confirm_remote_data=True)
    complete_development(store, workflow, started["runs"]["development"])
    waiting = await manager.advance(workflow_id)
    store.write_json(
        waiting["review"]["submission_path"],
        [
            {
                "case_id": "eval",
                "reviewer": "Independent reviewer",
                "answer": "billing",
                "rationale": "The policy sends payment issues to Billing.",
            }
        ],
    )
    save = manager._save

    def interrupt(workflow_state):
        if workflow_state["stage"] == "ready_for_default":
            raise RuntimeError("simulated interruption")
        save(workflow_state)

    monkeypatch.setattr(manager, "_save", interrupt)
    with pytest.raises(RuntimeError, match="simulated interruption"):
        await manager.advance(workflow_id)
    review_path = store.path("reviews", waiting["datasets"]["evaluation"] + ".json")
    frozen_review = review_path.read_bytes()
    monkeypatch.setattr(manager, "_save", save)

    resumed = await manager.advance(workflow_id)

    assert resumed["stage"] == "default_running"
    assert resumed["protocol_id"]
    assert resumed["review"]["complete"] is True
    assert review_path.read_bytes() == frozen_review
    assert len(runner.created) == 2


async def test_failed_run_blocks_reruns_and_cancel_preserves_run(tmp_path):
    from decisionlab.store import Store
    from decisionlab.workflows import BenchmarkWorkflowManager

    store = Store(tmp_path)
    runner = FakeRunner(store)
    manager = BenchmarkWorkflowManager(store, runner)
    workflow = manager.create("Failure case", dataset_bytes(*workflow_cases()))
    started = await manager.advance(
        workflow["workflow_id"], confirm_live_calls=True, confirm_remote_data=True
    )
    run_id = started["runs"]["development"]
    store.update(run_id, status="partial", partial=True)

    blocked = await manager.advance(workflow["workflow_id"])
    assert blocked["stage"] == "blocked"
    assert blocked["runs"]["development"] == run_id
    assert len(runner.created) == 1

    other = manager.create("Cancelled case", dataset_bytes(*workflow_cases()))
    active = await manager.advance(
        other["workflow_id"], confirm_live_calls=True, confirm_remote_data=True
    )
    cancelled = await manager.cancel(other["workflow_id"])
    assert cancelled["stage"] == "cancelled"
    assert runner.cancelled == [active["runs"]["development"]]
    assert cancelled["runs"]["development"] == active["runs"]["development"]


@pytest.mark.parametrize(
    ("interval", "winner"),
    [([-0.01, 0.08], "no_clear_winner"), ([0.01, 0.08], "jev"), ([-0.08, -0.01], "laya")],
)
def test_accuracy_verdict_requires_confidence_interval_to_exclude_zero(interval, winner):
    from decisionlab.workflows import comparison_verdict

    assert (
        comparison_verdict(
            {
                "metric": "accuracy",
                "left": "jev-default",
                "right": "laya-default",
                "difference": 0.04,
                "ci95": interval,
                "families": 10,
            }
        )["winner"]
        == winner
    )
