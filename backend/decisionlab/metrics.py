from __future__ import annotations

import json
import math
from collections import defaultdict

import numpy as np
from sklearn.metrics import f1_score, roc_auc_score

SCORING_VERSION = "1.0.0"
DEFINITIONS = {
    "accuracy": "Correct primary outcomes / all scheduled primary outcomes; failures count as incorrect.",
    "brier": "Mean squared probability error: binary P(true) for Noul; sum across outcomes for Choice/Score.",
    "log_loss": "Mean -ln P(gold), clipped only for scoring at 1e-15.",
    "ece": "Equal-width top-label confidence bins weighted by valid prediction count.",
    "ranked_probability_score": "Sum of squared cumulative probability errors / (number of levels - 1).",
    "coverage": "Accepted primary predictions / all scheduled primary predictions, including failures.",
    "risk": "Incorrect accepted predictions / accepted predictions; confidence ties stay together.",
    "bootstrap": "Paired percentile 95% intervals, resampling complete families with replacement.",
    "js_divergence": "Jensen–Shannon divergence using natural logarithms after semantic outcome alignment.",
}


def metric(value=None, numerator=None, denominator=0, reason=None, **extra):
    return {
        "value": value,
        "numerator": numerator,
        "denominator": denominator,
        "unavailable_reason": reason if value is None else None,
        **extra,
    }


def mean_metric(values, **extra):
    return metric(
        float(np.mean(values)) if values else None,
        float(sum(values)) if values else None,
        len(values),
        "No eligible predictions",
        **extra,
    )


def risk_coverage(confidences, correct, total):
    rows = sorted(zip(confidences, correct), key=lambda p: -p[0])
    points, count, errors = [], 0, 0
    for i, (confidence, good) in enumerate(rows):
        count += 1
        errors += not good
        if i + 1 < len(rows) and rows[i + 1][0] == confidence:
            continue
        points.append(
            {
                "threshold": confidence,
                "accepted": count,
                "errors": int(errors),
                "denominator": total,
                "coverage": count / total if total else 0,
                "risk": errors / count,
                "unstable": count < 30,
            }
        )
    return points


def js_divergence(left, right):
    keys = sorted(set(left) | set(right))
    p, q = np.array([left.get(k, 0) for k in keys]), np.array([right.get(k, 0) for k in keys])
    m = (p + q) / 2
    return float(sum(float(np.sum(x[x > 0] * np.log(x[x > 0] / m[x > 0]))) for x in (p, q)) / 2)


def semantic(case, answer):
    mapping = case.get("label_map", {})
    return {mapping.get(k, k): v for k, v in answer["probabilities"].items()}


def gold(case):
    value = case["expected"]["value"]
    return str(value).lower() if isinstance(value, bool) else str(value)


def outcome(case, prediction):
    valid = (
        prediction is not None and prediction["status"] == "success" and prediction.get("answer")
    )
    answer = prediction["answer"] if valid else None
    return {
        "case": case,
        "prediction": prediction,
        "answer": answer,
        "correct": bool(answer and answer["selected"] == gold(case)),
    }


def confidence_interval(values):
    return (
        [float(np.percentile(values, 2.5)), float(np.percentile(values, 97.5))] if values else None
    )


def bootstrap_accuracy(rows, samples, seed):
    families = defaultdict(list)
    for row in rows:
        families[row["case"]["family_id"]].append(float(row["correct"]))
    groups = list(families.values())
    if len(groups) < 2:
        return None
    counts = np.array([len(g) for g in groups])
    successes = np.array([sum(g) for g in groups])
    rng = np.random.default_rng(seed)
    # ponytail: O(samples × families), chunked draws if very large datasets need it.
    values = []
    for _ in range(samples):
        indices = rng.integers(0, len(groups), len(groups))
        values.append(float(successes[indices].sum() / counts[indices].sum()))
    return confidence_interval(values)


def _system_metrics(rows, all_predictions, bins, thresholds, samples, seed):
    valid = [r for r in rows if r["answer"]]
    total, successes = len(rows), sum(r["correct"] for r in rows)
    briers, losses, ordinal, ranked = [], [], [], []
    confidence, correct = [], []
    label_spaces = defaultdict(list)
    nouls = []
    for row in valid:
        case, answer = row["case"], row["answer"]
        probs, expected = answer["probabilities"], gold(case)
        brier = (
            (probs["true"] - (expected == "true")) ** 2
            if case["primitive"] == "noul"
            else sum((v - (k == expected)) ** 2 for k, v in probs.items())
        )
        briers.append(brier)
        losses.append(-math.log(max(1e-15, probs[expected])))
        confidence.append(probs[answer["selected"]])
        correct.append(row["correct"])
        if case["primitive"] == "score":
            keys = sorted(probs, key=int)
            score = sum(int(k) * probs[k] for k in keys)
            ordinal.append(abs(score - int(expected)))
            ranked.append(
                sum(
                    (sum(probs[k] for k in keys[: i + 1]) - (int(expected) <= i)) ** 2
                    for i in range(len(keys) - 1)
                )
                / (len(keys) - 1)
            )
        if case["primitive"] == "noul":
            nouls.append((expected == "true", probs["true"]))
    # Include failures as a distinct predicted class, within each semantic label space.
    for row in rows:
        case = row["case"]
        if case["primitive"] == "choice":
            mapping = case.get("label_map", {})
            key = case.get("label_space_id") or json.dumps(
                sorted(mapping.get(k, k) for k in case["question"]["criteria"])
            )
            expected = mapping.get(gold(case), gold(case))
            selected = (
                mapping.get(row["answer"]["selected"], row["answer"]["selected"])
                if row["answer"]
                else "__failure__"
            )
            label_spaces[key].append((expected, selected))
    f1s = [
        float(
            f1_score(
                [x[0] for x in group],
                [x[1] for x in group],
                labels=sorted({x[0] for x in group}),
                average="macro",
                zero_division=0,
            )
        )
        for group in label_spaces.values()
    ]
    reliability = []
    for index in range(bins):
        entries = [i for i, c in enumerate(confidence) if min(int(c * bins), bins - 1) == index]
        reliability.append(
            {
                "lower": index / bins,
                "upper": (index + 1) / bins,
                "count": len(entries),
                "correct": sum(correct[i] for i in entries),
                "incorrect": sum(not correct[i] for i in entries),
                "confidence": float(np.mean([confidence[i] for i in entries])) if entries else None,
                "accuracy": float(np.mean([correct[i] for i in entries])) if entries else None,
            }
        )
    ece = (
        sum(b["count"] * abs(b["confidence"] - b["accuracy"]) for b in reliability if b["count"])
        / len(valid)
        if valid
        else None
    )
    risk_points = risk_coverage(confidence, correct, total)
    operating_points = []
    for target in (0.01, 0.02):
        eligible = [p for p in risk_points if p["risk"] <= target]
        best = max(eligible, key=lambda p: p["coverage"]) if eligible else None
        operating_points.append({"target_risk": target, "point": best})
    threshold_rows = []
    for threshold in thresholds:
        indices = [i for i, v in enumerate(confidence) if v >= threshold]
        errors = sum(not correct[i] for i in indices)
        accepted = len(indices)
        threshold_rows.append(
            {
                "threshold": threshold,
                "accepted": accepted,
                "errors": errors,
                "coverage": accepted / total if total else 0,
                "denominator": total,
                "risk": errors / accepted if accepted else None,
                "escalations": total - accepted,
                "unstable": accepted < 30,
            }
        )
    latency = [
        r["prediction"]["timing"]["latency_ms"]
        for r in valid
        if r["prediction"].get("timing", {}).get("is_warm", True)
    ]
    costs = [p.get("usage", {}).get("provider_cost_usd") for p in all_predictions]
    estimates = [p.get("usage", {}).get("estimated_api_cost_usd") for p in all_predictions]
    known_costs, estimated = (
        [c for c in costs if c is not None],
        [c for c in estimates if c is not None],
    )
    question_count = sum(p.get("batch_size", 1) for p in all_predictions)
    failures = [r for r in rows if not r["answer"]]
    auroc = (
        float(roc_auc_score([x[0] for x in nouls], [x[1] for x in nouls]))
        if len({x[0] for x in nouls}) == 2
        else None
    )
    frozen_policy = None
    if any("frozen_accepted" in row["answer"] for row in valid):
        frozen_accepted = [row for row in valid if row["answer"].get("frozen_accepted")]
        errors = sum(not row["correct"] for row in frozen_accepted)
        frozen_policy = {
            "accepted": len(frozen_accepted),
            "denominator": total,
            "errors": errors,
            "coverage": len(frozen_accepted) / total if total else 0,
            "risk": errors / len(frozen_accepted) if frozen_accepted else None,
            "unstable": len(frozen_accepted) < 30,
        }
    return {
        "correctness": {
            "accuracy": metric(
                successes / total if total else None,
                successes,
                total,
                "No primary cases",
                ci95=bootstrap_accuracy(rows, samples, seed) if samples else None,
            ),
            "answered_accuracy": metric(
                successes / len(valid) if valid else None, successes, len(valid), "No valid answers"
            ),
            "macro_f1": mean_metric(f1s, scope="Mean across compatible Choice label spaces"),
            "ordinal_mae": mean_metric(ordinal),
            "ranked_probability_score": mean_metric(ranked),
            "auroc": metric(auroc, denominator=len(nouls), reason="Requires both Noul classes"),
        },
        "calibration": {
            "brier": mean_metric(briers),
            "log_loss": mean_metric(losses),
            "ece": metric(ece, denominator=len(valid), reason="No valid probability distributions"),
            "bins": reliability,
            "excluded": total - len(valid),
            "confidence_histogram": [
                {k: b[k] for k in ("lower", "upper", "count", "correct", "incorrect")}
                for b in reliability
            ],
            "confidence_distribution": [
                {"confidence": c, "correct": good} for c, good in zip(confidence, correct)
            ],
        },
        "selective_automation": {
            "curve": risk_points,
            "operating_points": operating_points,
            "frozen_policy": frozen_policy,
            "thresholds": threshold_rows,
            "signal": "selected-outcome probability",
        },
        "performance": {
            "warm_p50_ms": float(np.percentile(latency, 50)) if latency else None,
            "warm_p95_ms": float(np.percentile(latency, 95)) if latency else None,
            "warm_p99_ms": float(np.percentile(latency, 99)) if latency else None,
            "warm_count": len(latency),
            "latencies": latency,
            "timing_basis": "End-to-end logical decision, including retries; queue time separate",
        },
        "cost": {
            "provider_reported_total_usd": sum(known_costs) if known_costs else None,
            "estimated_api_total_usd": sum(estimated) if estimated else None,
            "observed_requests": len(all_predictions),
            "reported_cost_count": len(known_costs),
            "observed_questions": question_count,
            "missing_usage_requests": sum(not p.get("usage") for p in all_predictions),
            "unpriced_failed_attempts": sum(
                a.get("status") == "failed" for p in all_predictions for a in p.get("attempts", [])
            ),
            "note": "Recorded usage only; failed attempts without usage may incur additional cost. Warm-up is reported separately.",
            "estimated_cost_count": len(estimated),
            "per_1000_decisions_usd": (sum(known_costs) if known_costs else sum(estimated))
            / question_count
            * 1000
            if (known_costs or estimated) and question_count
            else None,
        },
        "failures": {
            "count": len(failures),
            "denominator": total,
            "rate": len(failures) / total if total else None,
            "retries": sum(p.get("retry_count", 0) for p in all_predictions),
            "categories": dict(
                _count(
                    r["prediction"].get("error", {}).get("category", "unknown")
                    if r["prediction"]
                    else "missing"
                    for r in failures
                )
            ),
        },
    }


def _count(items):
    from collections import Counter

    return Counter(items)


def _robustness(rows, reference_rows):
    indexed = {r["case"]["id"]: r for r in reference_rows}
    groups = defaultdict(list)
    for row in rows:
        case = row["case"]
        relation = case.get("transformation") or {}
        if case["variant"] == "base" or relation.get("expected_relation") != "invariant":
            continue
        base = indexed.get(relation.get("source_case_id"))
        flip, drift = None, None
        if base is not None and base["answer"] and row["answer"]:
            mapping = case.get("label_map", {})
            base_mapping = base["case"].get("label_map", {})
            flip = mapping.get(
                row["answer"]["selected"], row["answer"]["selected"]
            ) != base_mapping.get(base["answer"]["selected"], base["answer"]["selected"])
            drift = js_divergence(
                semantic(base["case"], base["answer"]), semantic(case, row["answer"])
            )
        groups[(case["variant"], case["primitive"])].append(
            {
                "case_id": case["id"],
                "family_id": case["family_id"],
                "comparable": flip is not None,
                "flip": flip,
                "harmful": bool(base and base["correct"] and not row["correct"]),
                "beneficial": bool(base and not base["correct"] and row["correct"]),
                "base_correct": bool(base and base["correct"]),
                "variant_correct": row["correct"],
                "drift": drift,
            }
        )
    result = []
    for (variant, primitive), items in sorted(groups.items()):
        comparable = [p for p in items if p["comparable"]]
        result.append(
            {
                "variant": variant,
                "primitive": primitive,
                "count": len(items),
                "comparable_count": len(comparable),
                "missing_pairs": len(items) - len(comparable),
                "answer_flip_rate": sum(p["flip"] for p in comparable) / len(comparable)
                if comparable
                else None,
                "harmful_flip_rate": sum(p["harmful"] for p in items) / len(items),
                "beneficial_flip_rate": sum(p["beneficial"] for p in items) / len(items),
                "accuracy_delta": sum(
                    int(p["variant_correct"]) - int(p["base_correct"]) for p in items
                )
                / len(items),
                "probability_drift": mean_metric([p["drift"] for p in comparable]),
                "case_ids": [p["case_id"] for p in items],
            }
        )
    return result


def _repeatability(predictions):
    grouped = defaultdict(list)
    for p in predictions:
        if p.get("suite") == "repeatability":
            grouped[p["case_id"]].append(p)
    result = []
    for case_id, group in sorted(grouped.items()):
        valid = [p for p in group if p["status"] == "success"]
        answers = [p["answer"]["selected"] for p in valid]
        matrix = np.array([list(p["answer"]["probabilities"].values()) for p in valid])
        drifts = [
            js_divergence(a["answer"]["probabilities"], b["answer"]["probabilities"])
            for i, a in enumerate(valid)
            for b in valid[i + 1 :]
        ]
        result.append(
            {
                "case_id": case_id,
                "calls": len(group),
                "valid": len(valid),
                "modal_agreement": max(_count(answers).values()) / len(valid) if valid else None,
                "any_flip": len(set(answers)) > 1 if len(valid) > 1 else None,
                "mean_probability_std": float(matrix.std(axis=0).mean())
                if len(valid) > 1
                else None,
                "max_probability_std": float(matrix.std(axis=0).max()) if len(valid) > 1 else None,
                "mean_js_divergence": float(np.mean(drifts)) if drifts else None,
            }
        )
    return result


def compute_metrics(
    cases,
    predictions,
    scoring_version=SCORING_VERSION,
    bootstrap_samples=2000,
    bootstrap_seed=20260924,
    ece_bins=10,
    confidence_thresholds=None,
    system_ids=None,
    reference_cases=None,
    reference_predictions=None,
):
    if scoring_version != SCORING_VERSION:
        raise ValueError("Scoring version is not installed")
    cases = [c.model_dump() if hasattr(c, "model_dump") else c for c in cases]
    reference_cases = (
        cases
        if reference_cases is None
        else [c.model_dump() if hasattr(c, "model_dump") else c for c in reference_cases]
    )
    reference_predictions = predictions if reference_predictions is None else reference_predictions
    primary = [c for c in cases if c["variant"] not in ("context_length", "option_cardinality")]
    systems = sorted(system_ids or {p["system_id"] for p in predictions})
    thresholds = confidence_thresholds or [0.6, 0.7, 0.8, 0.9]
    summary = {
        "scoring_version": scoring_version,
        "definitions": DEFINITIONS,
        "systems": {},
        "slices": [],
        "comparisons": [],
        "findings": [],
        "limitations": [
            "Synthetic, policy-derived cases may not represent production traffic.",
            "Observed risk is descriptive; small accepted samples cannot establish a safety guarantee.",
            "Local and remote latency measure different deployment paths.",
            "Intervals resample base families; transformed rows are not independent.",
        ],
        "counts": {
            "cases": len(primary),
            "families": len({c["family_id"] for c in primary}),
            "successful_predictions": sum(
                p["status"] == "success"
                for p in predictions
                if p.get("suite", "quality") == "quality"
            ),
            "failed_predictions": sum(
                p["status"] != "success"
                for p in predictions
                if p.get("suite", "quality") == "quality"
            ),
        },
    }
    rows_by_system = {}
    summary["counts"]["missing_predictions"] = 0
    for system in systems:
        selected = [p for p in predictions if p["system_id"] == system]
        indexed = {p["case_id"]: p for p in selected if p.get("suite", "quality") == "quality"}
        rows = [outcome(c, indexed.get(c["id"])) for c in primary]
        summary["counts"]["missing_predictions"] += sum(r["prediction"] is None for r in rows)
        rows_by_system[system] = rows
        data = _system_metrics(
            rows, selected, ece_bins, thresholds, bootstrap_samples, bootstrap_seed
        )
        reference_index = {
            p["case_id"]: p
            for p in reference_predictions
            if p["system_id"] == system and p.get("suite", "quality") == "quality"
        }
        data["robustness"] = _robustness(
            rows, [outcome(c, reference_index.get(c["id"])) for c in reference_cases]
        )
        data["repeatability"] = _repeatability(selected)
        data["diagnostics"] = []
        for variant in ("context_length", "option_cardinality"):
            values = defaultdict(list)
            for c in cases:
                if c["variant"] == variant:
                    key = c["metadata"].get(
                        "context_bucket" if variant == "context_length" else "option_count"
                    )
                    matching = next((p for p in selected if p["case_id"] == c["id"]), None)
                    values[key].append(outcome(c, matching))
            for bucket, grouped in sorted(values.items()):
                data["diagnostics"].append(
                    {
                        "variant": variant,
                        "bucket": bucket,
                        "accuracy": sum(r["correct"] for r in grouped) / len(grouped),
                        "count": len(grouped),
                        "failures": sum(not r["answer"] for r in grouped),
                    }
                )
        load = defaultdict(list)
        for p in selected:
            if p.get("suite") == "performance":
                load[(p.get("concurrency", 1), p.get("batch_size", 1))].append(p)
        data["performance"]["load_tests"] = []
        for (concurrency, batch_size), group in sorted(load.items()):
            starts = [p["timing"]["started_at_epoch"] for p in group]
            ends = [p["timing"]["ended_at_epoch"] for p in group]
            duration = max(ends) - min(starts)
            data["performance"]["load_tests"].append(
                {
                    "concurrency": concurrency,
                    "batch_size": batch_size,
                    "count": len(group),
                    "questions_per_second": sum(p.get("batch_size", 1) for p in group) / duration
                    if duration > 0
                    else None,
                    "failures": sum(p["status"] != "success" for p in group),
                    "queue_p50_ms": float(
                        np.median([p["timing"].get("queue_ms", 0) for p in group])
                    ),
                }
            )
        summary["systems"][system] = data
        for dimension in ("primitive", "domain", "variant", "split"):
            for key in sorted({r["case"][dimension] for r in rows}):
                subset = [r for r in rows if r["case"][dimension] == key]
                result = _system_metrics(
                    subset,
                    [r["prediction"] for r in subset if r["prediction"]],
                    ece_bins,
                    thresholds,
                    0,
                    bootstrap_seed,
                )
                summary["slices"].append(
                    {
                        "system_id": system,
                        "dimension": dimension,
                        "value": key,
                        "count": len(subset),
                        "metrics": result,
                    }
                )
    if len(systems) == 2:
        left, right = systems
        families = defaultdict(list)
        for lrow, rrow in zip(rows_by_system[left], rows_by_system[right]):
            families[lrow["case"]["family_id"]].append(int(lrow["correct"]) - int(rrow["correct"]))
        groups = list(families.values())
        diffs = []
        if len(groups) > 1:
            rng = np.random.default_rng(bootstrap_seed)
            sums, lengths = np.array([sum(g) for g in groups]), np.array([len(g) for g in groups])
            for _ in range(bootstrap_samples):
                indices = rng.integers(0, len(groups), len(groups))
                diffs.append(float(sums[indices].sum() / lengths[indices].sum()))
        delta = sum(sum(g) for g in groups) / sum(map(len, groups)) if groups else None
        summary["comparisons"].append(
            {
                "metric": "accuracy",
                "left": left,
                "right": right,
                "difference": delta,
                "ci95": confidence_interval(diffs),
                "families": len(groups),
            }
        )
        for primitive in ("choice", "noul", "score"):
            slices = [
                s
                for s in summary["slices"]
                if s["dimension"] == "primitive" and s["value"] == primitive
            ]
            if len(slices) == 2 and slices[0]["count"]:
                first, second = slices
                a, b = (s["metrics"]["correctness"]["accuracy"]["value"] for s in slices)
                summary["findings"].append(
                    {
                        "text": f"On {primitive.title()}, {first['system_id']} answered {a:.1%} correctly and {second['system_id']} {b:.1%}.",
                        "metric_ref": "correctness.accuracy",
                        "filters": {"primitive": primitive},
                        "exploratory": True,
                    }
                )
    return summary
