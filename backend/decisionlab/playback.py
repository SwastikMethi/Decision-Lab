"""Read-only, paired visual projections of saved evaluation evidence."""

import json
from typing import Literal

from pydantic import BaseModel, Field

from .metrics import gold
from .schemas import Primitive
from .store import TERMINAL, Store


class PlaybackOption(BaseModel):
    id: str
    label: str


class PlaybackCase(BaseModel):
    id: str
    primitive: Primitive
    variant: str
    instructions: str
    input_preview: str
    options: list[PlaybackOption]
    expected_key: str


class PlaybackOutcome(BaseModel):
    evaluation_id: str
    state: Literal["pending", "success", "failed", "not_completed"]
    selected: str | None = None
    probabilities: dict[str, float] = Field(default_factory=dict)
    correctness: bool | None = None
    latency_ms: float | None = None
    retry_count: int = 0
    error: str | None = None


class PlaybackFrame(BaseModel):
    key: str
    ordinal: int
    sealed: bool
    suite: str
    repetition: int
    concurrency: int
    batch_size: int
    case: PlaybackCase | None
    systems: dict[str, PlaybackOutcome]


class PlaybackPage(BaseModel):
    items: list[PlaybackFrame]
    next_cursor: int | None
    total_frames: int
    withheld_frames: int
    latest_available: int | None
    run_status: str


def case_projection(case):
    question = case["question"]
    if case["primitive"] == "choice":
        options = [{"id": key, "label": value} for key, value in question["criteria"].items()]
    elif case["primitive"] == "noul":
        options = [{"id": "false", "label": "No"}, {"id": "true", "label": "Yes"}]
    else:
        options = [{"id": str(i), "label": value} for i, value in enumerate(question["criteria"])]
    state = case["state"]
    # Prefer the literal message over a JSON envelope; never generate a new summary.
    preview = state
    if isinstance(state, dict):
        record = state.get("record", state)
        preview = (
            record.get("text", record.get("message", record))
            if isinstance(record, dict)
            else record
        )
    text = preview if isinstance(preview, str) else json.dumps(preview, ensure_ascii=False)
    return PlaybackCase(
        id=case["id"],
        primitive=case["primitive"],
        variant=case["variant"],
        instructions=question["instructions"],
        input_preview=text[:480] + ("…" if len(text) > 480 else ""),
        options=[PlaybackOption(**option) for option in options],
        expected_key=gold(case),
    )


def playback_page(store: Store, run_id: str, after: int = -1, limit: int = 20) -> PlaybackPage:
    manifest = store.manifest(run_id)
    schedule = store.read_json(store.run_dir(run_id) / "schedule.json")
    cases = {case["id"]: case for case in store.records(run_id, "cases.snapshot")}
    predictions = {p["evaluation_id"]: p for p in store.records(run_id, "predictions")}
    # ponytail: local JSONL projection; index evaluation IDs if large-run polling becomes slow.
    groups: dict[tuple, dict] = {}
    for job in schedule:
        key = tuple(
            job[field] for field in ("case_id", "suite", "repetition", "concurrency", "batch_size")
        )
        groups.setdefault(key, {})[job["adapter_id"]] = job
    items = []
    withheld = 0
    latest = None
    terminal = manifest["status"] in TERMINAL
    for ordinal, (identity, jobs) in enumerate(groups.items()):
        case_id, suite, repetition, concurrency, batch_size = identity
        case = cases[case_id]
        sealed = case["split"] == "sealed" and not manifest.get("sealed_released")
        withheld += sealed
        if not sealed and (
            terminal or all(j["evaluation_id"] in predictions for j in jobs.values())
        ):
            latest = ordinal
        if not after < ordinal <= after + limit:
            continue
        systems = {}
        if not sealed:
            for adapter_id, job in jobs.items():
                prediction = predictions.get(job["evaluation_id"])
                outcome = PlaybackOutcome(
                    evaluation_id=job["evaluation_id"],
                    state="not_completed" if terminal else "pending",
                )
                if prediction:
                    answer = prediction.get("answer")
                    success = prediction["status"] == "success" and bool(answer)
                    outcome = PlaybackOutcome(
                        evaluation_id=job["evaluation_id"],
                        state="success" if success else "failed",
                        selected=answer["selected"] if success else None,
                        probabilities=answer["probabilities"] if success else {},
                        correctness=answer["selected"] == gold(case) if success else None,
                        latency_ms=prediction.get("timing", {}).get("latency_ms"),
                        retry_count=prediction.get("retry_count", 0),
                        error=str(
                            (prediction.get("error") or {}).get("message", "No valid response")
                        )[:500]
                        if not success
                        else None,
                    )
                systems[adapter_id] = outcome
        items.append(
            PlaybackFrame(
                key=f"{run_id}:{ordinal}",
                ordinal=ordinal,
                sealed=sealed,
                suite=suite,
                repetition=repetition,
                concurrency=concurrency,
                batch_size=batch_size,
                case=None if sealed else case_projection(case),
                systems=systems,
            )
        )
    return PlaybackPage(
        items=items,
        next_cursor=items[-1].ordinal if items and items[-1].ordinal < len(groups) - 1 else None,
        total_frames=len(groups),
        withheld_frames=withheld,
        latest_available=latest,
        run_status=manifest["status"],
    )
