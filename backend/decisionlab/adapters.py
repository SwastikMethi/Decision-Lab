from __future__ import annotations

import asyncio
import hashlib
import json
import math
import os
import re
import time
from typing import Protocol

from .schemas import EvaluationCase


def sanitize(value, secrets=(), *, redact_keys=True):
    secrets = tuple(
        s for s in (*secrets, os.getenv("TYPESAFE_API_KEY"), os.getenv("HF_TOKEN")) if s
    )
    if isinstance(value, dict):
        return {
            k: "[REDACTED]"
            if redact_keys
            and re.search(
                r"authorization|api[_-]?key|access[_-]?token|secret|password", str(k), re.I
            )
            else sanitize(v, secrets, redact_keys=redact_keys)
            for k, v in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [sanitize(v, secrets, redact_keys=redact_keys) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
        return re.sub(r"(?i)Bearer\s+[A-Za-z0-9._~+/\-=]+", "Bearer [REDACTED]", value)
    return value


def normalize(case: EvaluationCase, raw: dict) -> dict:
    answers = raw.get("answers") if isinstance(raw, dict) else None
    answer = answers.get(case.question.id) if isinstance(answers, dict) else None
    if not isinstance(answer, dict):
        raise ValueError("Missing answer for the requested question")
    if case.primitive == "noul":
        p = answer.get("noul")
        if (
            isinstance(p, bool)
            or not isinstance(p, (float, int))
            or not math.isfinite(p)
            or not 0 <= p <= 1
        ):
            raise ValueError("Noul must be a finite probability")
        probabilities = {"false": 1 - p, "true": p}
        selected = "true" if p >= 0.5 else "false"
    else:
        values = answer.get("probabilities")
        if not isinstance(values, dict):
            raise ValueError("Missing complete probability distribution")
        probabilities = {str(k): v for k, v in values.items()}
        if set(probabilities) != set(case.options):
            raise ValueError("Probability outcomes do not match the answer space")
        if any(
            isinstance(v, bool)
            or not isinstance(v, (int, float))
            or not math.isfinite(v)
            or not 0 <= v <= 1
            for v in probabilities.values()
        ):
            raise ValueError("Probabilities must be finite numbers within [0, 1]")
        total = sum(probabilities.values())
        if abs(total - 1) > 1e-5:
            raise ValueError("Probability distribution does not sum to one")
        probabilities = {k: probabilities[k] / total for k in case.options}
        selected = (
            str(answer.get("choice"))
            if case.primitive == "choice"
            else max(case.options, key=lambda key: probabilities[key])
        )
        if selected not in probabilities:
            raise ValueError("Selected answer is outside the answer space")
    confidence = answer.get("confidence")
    if confidence is not None and (
        isinstance(confidence, bool)
        or not isinstance(confidence, (int, float))
        or not math.isfinite(confidence)
        or not 0 <= confidence <= 1
    ):
        raise ValueError("Provider confidence is invalid")
    score = sum(int(k) * p for k, p in probabilities.items()) if case.primitive == "score" else None
    return {
        "selected": selected,
        "score": score,
        "probabilities": probabilities,
        "provider_score": answer.get("score"),
        "provider_confidence": confidence,
        "decision_probability": probabilities[selected],
    }


class DecisionAdapter(Protocol):
    adapter_id: str

    async def readiness(self) -> dict: ...
    async def warmup(self, cases: list[EvaluationCase]) -> dict: ...
    async def predict(self, case: EvaluationCase) -> dict: ...
    async def predict_questions(self, case: EvaluationCase, batch_size: int) -> dict: ...
    async def close(self) -> None: ...


class ProviderFailure(Exception):
    def __init__(self, category, message, retryable=False, retry_after=0, status=None, body=None):
        super().__init__(message)
        self.category, self.retryable = category, retryable
        self.retry_after, self.status = retry_after, status
        self.body = body


def provider_metadata(raw):
    """Optional provider telemetry cannot invalidate an otherwise valid decision."""
    envelope = raw if isinstance(raw, dict) else {}
    warnings = []
    values = []
    for name, numeric_fields in (
        ("usage", ("input_tokens", "output_tokens", "total_tokens", "provider_cost_usd")),
        ("_runtime", ("queue_ms", "inference_ms", "accelerator_memory_bytes")),
    ):
        value = envelope.get(name, {})
        if not isinstance(value, dict):
            warnings.append(f"{name} metadata unavailable: expected an object")
            value = {}
        value = dict(value)
        for key in numeric_fields:
            if key in value and (
                isinstance(value[key], bool)
                or not isinstance(value[key], (float, int))
                or not math.isfinite(value[key])
                or value[key] < 0
            ):
                value.pop(key)
                warnings.append(f"{name}.{key} unavailable: invalid numeric metadata")
        values.append(value)
    return values[0], values[1], warnings


class FakeAdapter:
    """Deterministic simulation for the offline workflow; never benchmark evidence."""

    def __init__(self, adapter_id, delay=0.006):
        self.adapter_id, self.delay = adapter_id, delay

    async def readiness(self):
        return {"ready": True, "simulation": True}

    async def warmup(self, cases):
        return {"cold_start_ms": 0, "simulation": True}

    async def predict(self, case):
        await asyncio.sleep(self.delay)
        # No labels are read: the simulation hashes public input and chooses an outcome.
        seed = int(
            hashlib.sha256((self.adapter_id + json.dumps(case.request())).encode()).hexdigest()[:8],
            16,
        )
        options = case.options
        chosen = options[seed % len(options)]
        peak = 0.56 + (seed % 40) / 100
        probs = {key: peak if key == chosen else (1 - peak) / (len(options) - 1) for key in options}
        answer = {"type": case.primitive, "probabilities": probs, "confidence": peak * 0.8}
        if case.primitive == "choice":
            answer["choice"] = chosen
        elif case.primitive == "noul":
            answer = {"type": "noul", "noul": probs["true"]}
        else:
            answer["score"] = sum(int(k) * p for k, p in probs.items())
        return {
            "model": f"simulated-{self.adapter_id}",
            "answers": {case.question.id: answer},
            "usage": {},
            "simulation": True,
        }

    async def close(self):
        pass

    async def predict_questions(self, case, batch_size):
        raw = await self.predict(case)
        answer = raw["answers"][case.question.id]
        raw["answers"].update({f"{case.question.id}_{i}": answer for i in range(1, batch_size)})
        return raw


class JevAdapter:
    adapter_id = "jev"

    def __init__(self, config):
        self.config = config
        self.client = None

    async def readiness(self):
        return {"ready": bool(os.getenv("TYPESAFE_API_KEY")), "model": self.config.model}

    async def warmup(self, cases):
        from typesafe_sdk import AsyncTypeSafeClient, RetryPolicy

        start = time.perf_counter()
        self.client = AsyncTypeSafeClient(
            model=self.config.model,
            retry=RetryPolicy(max_retries=0),
            timeout=self.config.timeout_seconds,
        )
        representatives = {c.primitive: c for c in cases}
        responses = [await self.predict(c) for c in representatives.values()]
        return {
            "cold_start_ms": (time.perf_counter() - start) * 1000,
            "responses": responses,
            "model": self.config.model,
        }

    async def predict(self, case):
        return await self.predict_questions(case, 1)

    async def predict_questions(self, case, batch_size):
        import httpx2
        from typesafe_sdk import TypeSafeAPIError, TypeSafeAPIResponseValidationError

        try:
            if self.client is None:
                raise ProviderFailure("runtime", "Jev client has not been warmed")
            request = case.request()
            question = request["questions"][case.question.id]
            request["questions"].update(
                {f"{case.question.id}_{i}": question for i in range(1, batch_size)}
            )
            response = await self.client.system_one(**request, model=self.config.model)
            return response.model_dump(mode="json")
        except ProviderFailure:
            raise
        except Exception as exc:
            status = exc.status if isinstance(exc, TypeSafeAPIError) else None
            headers = exc.headers if isinstance(exc, TypeSafeAPIError) else {}
            category = {
                401: "authentication",
                403: "authentication",
                429: "rate_limit",
                400: "invalid_request",
                413: "context_limit",
                422: "invalid_request",
            }.get(status or 0)
            if isinstance(exc, TypeSafeAPIResponseValidationError):
                category = "normalization"
            if category is None:
                category = (
                    "timeout"
                    if isinstance(exc, httpx2.TimeoutException)
                    else "network"
                    if isinstance(exc, (httpx2.RequestError, ConnectionError))
                    else "invalid_request"
                    if isinstance(exc, ValueError)
                    else "runtime"
                )
            retry_after = 0.0
            try:
                retry_after = min(30, max(0, float(headers.get("retry-after", 0))))
            except (AttributeError, ValueError, TypeError):
                pass
            raise ProviderFailure(
                category,
                str(sanitize(str(exc))),
                category in ("rate_limit", "timeout", "network") or bool(status and status >= 500),
                retry_after,
                status,
                getattr(exc, "body", None),
            ) from exc

    async def close(self):
        if self.client:
            await self.client.aclose()
