import json

import pytest
from pydantic import ValidationError


def case(primitive="choice", **changes):
    criteria = {"billing": "Payments", "technical": "Software"}
    expected = "billing"
    if primitive == "noul":
        criteria, expected = None, True
    if primitive == "score":
        criteria, expected = ["Low", "Medium", "High"], 1
    value = {
        "schema_version": "1.0",
        "id": f"{primitive}-base",
        "family_id": primitive,
        "split": "development",
        "domain": "customer_support",
        "primitive": primitive,
        "variant": "base",
        "state": {"message": "Please refund a duplicate payment"},
        "question": {
            "id": "decision",
            "type": primitive,
            "instructions": "Apply the policy",
            "criteria": criteria,
        },
        "expected": {"kind": "hard_label", "value": expected},
        "label_space_id": primitive,
        "metadata": {"review_status": "draft"},
    }
    value.update(changes)
    return value


@pytest.mark.parametrize(
    "raw", [{"answers": None}, {"answers": []}, [], {"answers": {"decision": None}}]
)
def test_malformed_provider_answer_is_a_normalization_error(raw):
    from decisionlab.adapters import normalize
    from decisionlab.schemas import EvaluationCase

    with pytest.raises(ValueError, match="answer"):
        normalize(EvaluationCase.model_validate(case()), raw)


def test_invalid_seed_and_duplicate_load_settings_fail_validation():
    from decisionlab.schemas import RunConfiguration

    for changes in (
        {"metrics": {"bootstrap_seed": -1}},
        {"suites": {"performance": {"concurrency": [1, 1]}}},
    ):
        with pytest.raises(ValidationError):
            RunConfiguration(dataset_ref="demo", mode="fake", **changes)


def test_case_validation_and_answer_spaces():
    from decisionlab.schemas import EvaluationCase

    for primitive in ("choice", "noul", "score"):
        assert EvaluationCase.model_validate(case(primitive)).primitive == primitive
    for primitive, bad in (("choice", "missing"), ("noul", "true"), ("score", True), ("score", 9)):
        with pytest.raises(ValidationError):
            EvaluationCase.model_validate(
                case(primitive, expected={"kind": "hard_label", "value": bad})
            )


def test_loader_preserves_order_and_rejects_duplicates():
    from decisionlab.datasets import validate_jsonl

    value = case()
    value["state"] = {"z": 1, "a": 2}
    result = validate_jsonl(json.dumps(value).encode())
    assert result["valid"]
    assert list(result["cases"][0].state) == ["z", "a"]
    assert not validate_jsonl(b'{"id":"one","id":"two"}')["valid"]
    duplicate = (json.dumps(value) + "\n" + json.dumps(value)).encode()
    assert "Duplicate" in validate_jsonl(duplicate)["issues"][0]["message"]


def test_family_validation_and_opaque_mapping():
    from decisionlab.datasets import validate_jsonl

    value = case(
        id="choice-opaque",
        variant="opaque_labels",
        transformation={"source_case_id": "choice-base", "expected_relation": "invariant"},
    )
    assert not validate_jsonl(json.dumps(value).encode())["valid"]
    value["question"]["criteria"] = {"A": "Payments", "B": "Software"}
    value["expected"]["value"] = "A"
    value["label_map"] = {"A": "billing", "B": "technical"}
    assert validate_jsonl((json.dumps(case()) + "\n" + json.dumps(value)).encode())["valid"]


def test_normalization_and_redaction():
    from decisionlab.adapters import normalize, sanitize
    from decisionlab.schemas import EvaluationCase

    for primitive, answer, selected in [
        (
            "choice",
            {
                "choice": "billing",
                "probabilities": {"billing": 0.8, "technical": 0.2},
                "confidence": 0.6,
            },
            "billing",
        ),
        ("noul", {"noul": 0.5}, "true"),
        ("score", {"score": 0.9, "probabilities": {"0": 0.3, "1": 0.5, "2": 0.2}}, "1"),
    ]:
        result = normalize(
            EvaluationCase.model_validate(case(primitive)), {"answers": {"decision": answer}}
        )
        assert result["selected"] == selected
        assert sum(result["probabilities"].values()) == pytest.approx(1)
    with pytest.raises(ValueError):
        normalize(
            EvaluationCase.model_validate(case()),
            {
                "answers": {
                    "decision": {
                        "choice": "billing",
                        "probabilities": {"billing": 1.2, "technical": -0.2},
                    }
                }
            },
        )
    assert sanitize({"Authorization": "Bearer secret", "nested": ["token secret"]}, ["secret"]) == {
        "Authorization": "[REDACTED]",
        "nested": ["token [REDACTED]"],
    }


def test_noul_request_uses_the_shared_provider_criteria_contract():
    from decisionlab.schemas import EvaluationCase

    value = case("noul")
    value["question"]["criteria"] = "An explicit refund request is required."
    request = EvaluationCase.model_validate(value).request()
    criteria = request["questions"]["decision"]["criteria"]
    assert isinstance(criteria, dict)
    assert criteria["true"] == "An explicit refund request is required."
    assert "expected" not in request
