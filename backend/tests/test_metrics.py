import copy

import pytest
from test_contracts import case


def prediction(case_id="choice-base", probabilities=None, selected="billing", **changes):
    p = probabilities or {"billing": 0.8, "technical": 0.2}
    value = {
        "evaluation_id": case_id,
        "case_id": case_id,
        "system_id": "jev-default",
        "adapter_id": "jev",
        "suite": "quality",
        "repetition": 0,
        "status": "success",
        "answer": {
            "selected": selected,
            "probabilities": p,
            "decision_probability": p.get(selected, 0),
            "score": None,
        },
        "timing": {"latency_ms": 10, "is_warm": True},
        "usage": {},
        "retry_count": 0,
    }
    value.update(changes)
    return value


def test_hand_calculated_scores_and_failure_denominators():
    from decisionlab.metrics import compute_metrics

    cases = [case(), case(id="second", family_id="second")]
    predictions = [prediction(), prediction("second", status="failed", answer=None)]
    summary = compute_metrics(cases, predictions, bootstrap_samples=50)
    metrics = summary["systems"]["jev-default"]
    assert metrics["correctness"]["accuracy"]["value"] == 0.5
    assert metrics["correctness"]["accuracy"]["denominator"] == 2
    assert metrics["calibration"]["brier"]["value"] == pytest.approx(0.08)
    assert metrics["calibration"]["ece"]["value"] == pytest.approx(0.2)
    assert metrics["failures"]["count"] == 1
    assert summary == compute_metrics(cases, predictions, bootstrap_samples=50)


def test_tied_confidence_is_not_cherry_picked():
    from decisionlab.metrics import risk_coverage

    points = risk_coverage([0.9, 0.9, 0.6], [True, False, True], total=4)
    assert points[0]["accepted"] == 2
    assert points[0]["coverage"] == 0.5
    assert points[0]["risk"] == 0.5
    assert points[-1]["accepted"] == 3


def test_repetitions_do_not_reweight_quality_and_all_failed_is_unavailable():
    from decisionlab.metrics import compute_metrics

    raw = prediction()
    repeated = prediction(suite="repeatability", selected="technical")
    snapshot = copy.deepcopy([raw, repeated])
    result = compute_metrics([case()], [raw, repeated], bootstrap_samples=10)
    assert result["systems"]["jev-default"]["correctness"]["accuracy"]["value"] == 1
    assert [raw, repeated] == snapshot
    result = compute_metrics(
        [case()], [prediction(status="failed", answer=None)], bootstrap_samples=10
    )
    assert result["systems"]["jev-default"]["calibration"]["brier"]["value"] is None


def test_benchmark_splits_and_transforms():
    from decisionlab.benchmark import build_datasets
    from decisionlab.datasets import encode_cases, validate_jsonl

    dev, evaluation = build_datasets()
    assert len(dev) == 144
    assert len(evaluation) == 360
    assert len({v["family_id"] for v in evaluation if v["split"] == "sealed"}) == 15
    assert not {v["family_id"] for v in dev} & {v["family_id"] for v in evaluation}
    for values in (dev, evaluation):
        assert validate_jsonl(encode_cases(values))["valid"]
        assert all(v["metadata"]["review_status"] == "draft" for v in values)
        assert all(
            v["variant"] not in ("option_order", "opaque_labels")
            for v in values
            if v["primitive"] != "choice"
        )
