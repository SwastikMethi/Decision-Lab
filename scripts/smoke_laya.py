"""Opt-in local-provider contract check: no gold labels enter the model request."""

import asyncio
import json

from decisionlab.adapters import normalize
from decisionlab.benchmark import build_datasets
from decisionlab.laya_runtime import LayaAdapter
from decisionlab.schemas import EvaluationCase, LayaConfiguration


async def smoke():
    development, _ = build_datasets()
    cases = [
        EvaluationCase.model_validate(
            next(c for c in development if c["primitive"] == p and c["variant"] == "base")
        )
        for p in ("choice", "noul", "score")
    ]
    adapter = LayaAdapter(LayaConfiguration(timeout_seconds=180), "./models/lock.json")
    try:
        warmup = await adapter.warmup(cases)
        print(
            json.dumps({"device": warmup["device"], "cold_start_ms": warmup["cold_start_ms"]}),
            flush=True,
        )
        for case in cases:
            raw = await adapter.predict(case)
            answer = normalize(case, raw)
            assert abs(sum(answer["probabilities"].values()) - 1) < 1e-8
            print(
                json.dumps(
                    {
                        "primitive": case.primitive,
                        "selected": answer["selected"],
                        "probabilities": answer["probabilities"],
                        "runtime": {
                            k: raw["_runtime"][k]
                            for k in ("device", "revision", "route", "inference_ms")
                        },
                    }
                ),
                flush=True,
            )
    finally:
        await adapter.close()


if __name__ == "__main__":
    asyncio.run(smoke())
