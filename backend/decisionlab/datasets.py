from __future__ import annotations

import hashlib
import json
from collections import Counter

from pydantic import ValidationError

from .schemas import EvaluationCase

MAX_UPLOAD = 25 * 1024 * 1024


def digest_bytes(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def encode_cases(cases) -> bytes:
    return (
        "\n".join(
            json.dumps(
                c.model_dump() if isinstance(c, EvaluationCase) else c,
                ensure_ascii=False,
                allow_nan=False,
                separators=(",", ":"),
            )
            for c in cases
        )
        + "\n"
    ).encode()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def validate_jsonl(raw: bytes) -> dict:
    issues, cases, lines = [], [], {}
    if len(raw) > MAX_UPLOAD:
        return {
            "valid": False,
            "issues": [{"line": 0, "field": "file", "message": "Upload exceeds 25 MiB"}],
            "cases": [],
            "counts": {},
        }
    try:
        content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return {
            "valid": False,
            "issues": [{"line": 0, "field": "file", "message": "Use UTF-8 JSONL"}],
            "cases": [],
            "counts": {},
        }
    for number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(
                line,
                object_pairs_hook=unique_object,
                parse_constant=lambda x: (_ for _ in ()).throw(ValueError(f"Invalid number: {x}")),
            )
            item = EvaluationCase.model_validate(value)
            if item.id in lines:
                raise ValueError(f"Duplicate case ID: {item.id}")
            lines[item.id] = number
            cases.append(item)
        except ValidationError as exc:
            for err in exc.errors():
                issues.append(
                    {"line": number, "field": ".".join(map(str, err["loc"])), "message": err["msg"]}
                )
        except (ValueError, TypeError, RecursionError) as exc:
            issues.append({"line": number, "field": "record", "message": str(exc)})
    by_id = {c.id: c for c in cases}
    bases = {}
    for item in cases:
        error = None
        if item.variant == "base":
            if item.family_id in bases:
                error = "A family must have exactly one base"
            bases[item.family_id] = item.id
        else:
            source = by_id.get(item.transformation.source_case_id) if item.transformation else None
            if source is None or source.variant != "base":
                error = "Variant requires a valid base source_case_id"
            elif (source.family_id, source.split, source.primitive) != (
                item.family_id,
                item.split,
                item.primitive,
            ):
                error = "Base and variant must share family, split, and primitive"
            elif item.transformation and item.transformation.expected_relation == "invariant":
                base_answer = source.label_map.get(source.expected_key, source.expected_key)
                answer = item.label_map.get(item.expected_key, item.expected_key)
                if base_answer != answer:
                    error = "Invariant variant changes the expected semantic outcome"
                elif set(item.label_map.get(k, k) for k in item.options) != set(
                    source.label_map.get(k, k) for k in source.options
                ):
                    error = "Invariant answer spaces must align with the base"
        if error:
            issues.append({"line": lines[item.id], "field": "transformation", "message": error})
    if not cases and not issues:
        issues.append({"line": 0, "field": "file", "message": "Dataset contains no cases"})
    return {
        "valid": not issues,
        "issues": issues,
        "cases": cases,
        "digest": digest_bytes(raw),
        "counts": {
            "cases": len(cases),
            "families": len({c.family_id for c in cases}),
            **{
                key: dict(Counter(getattr(c, key) for c in cases))
                for key in ("primitive", "domain", "split", "variant")
            },
        },
    }
