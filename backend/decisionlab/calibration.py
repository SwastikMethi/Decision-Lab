import math
from collections import defaultdict

import numpy as np
from scipy.optimize import minimize_scalar

from .metrics import gold, risk_coverage


def inference_signature(config):
    return {
        "mode": config.mode,
        "jev_model": config.systems.jev.model,
        "laya_checkpoint": config.systems.laya.checkpoint,
        "laya_revision": config.systems.laya.checkpoint_revision,
        "laya_device": config.systems.laya.device,
        "instruction_overrides": config.instruction_overrides,
    }


def apply_temperature(probabilities, temperature):
    keys = list(probabilities)
    logits = np.log(np.clip([probabilities[k] for k in keys], 1e-15, 1)) / temperature
    scaled = np.exp(logits - logits.max())
    scaled /= scaled.sum()
    return dict(zip(keys, map(float, scaled)))


def fit_calibration(cases, predictions, dataset_digest):
    if any(c["split"] != "development" for c in cases):
        raise ValueError("Calibration requires development data only")
    indexed = {c["id"]: c for c in cases}
    groups = defaultdict(list)
    for prediction in predictions:
        if prediction["status"] == "success" and prediction.get("suite") == "quality":
            case = indexed.get(prediction["case_id"])
            if case:
                groups[(prediction["adapter_id"], case["primitive"])].append((case, prediction))
    if not groups:
        raise ValueError("No eligible development predictions")
    fitted = {}
    for (adapter, primitive), group in sorted(groups.items()):

        def loss(log_temperature):
            temperature = math.exp(log_temperature)
            return float(
                np.mean(
                    [
                        -math.log(
                            max(
                                1e-15,
                                apply_temperature(p["answer"]["probabilities"], temperature)[
                                    gold(c)
                                ],
                            )
                        )
                        for c, p in group
                    ]
                )
            )

        optimized = minimize_scalar(
            loss, bounds=(math.log(0.05), math.log(10)), method="bounded", options={"xatol": 1e-8}
        )
        temperature = math.exp(optimized.x)
        confidences, correct = [], []
        for case, prediction in group:
            probs = apply_temperature(prediction["answer"]["probabilities"], temperature)
            selected = prediction["answer"]["selected"]
            confidences.append(probs[selected])
            correct.append(selected == gold(case))
        points = [p for p in risk_coverage(confidences, correct, len(group)) if p["risk"] <= 0.02]
        best = max(points, key=lambda p: p["coverage"]) if points else None
        fitted[f"{adapter}:{primitive}"] = {
            "temperature": temperature,
            "threshold": best["threshold"] if best else None,
            "accepted": best["accepted"] if best else 0,
            "samples": len(group),
            "families": len({c["family_id"] for c, _ in group}),
            "unstable": best is None or best["unstable"],
        }
    return {
        "dataset_digest": dataset_digest,
        "method": "Probability temperature scaling; bounded development NLL fit",
        "target_observed_risk": 0.02,
        "parameters": fitted,
        "warnings": [
            "Small development sets can overfit; operating risk must be measured independently."
        ],
    }


def calibrate_answer(answer, parameters, primitive):
    probabilities = apply_temperature(answer["probabilities"], parameters["temperature"])
    selected = answer["selected"]
    return {
        **answer,
        "raw_probabilities": answer["probabilities"],
        "frozen_threshold": parameters["threshold"],
        "frozen_accepted": parameters["threshold"] is not None
        and probabilities[selected] >= parameters["threshold"],
        "probabilities": probabilities,
        "decision_probability": probabilities[selected],
        "score": sum(int(k) * v for k, v in probabilities.items())
        if primitive == "score"
        else None,
    }
