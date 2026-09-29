from __future__ import annotations

import json
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, StrictStr, model_validator

Primitive = Literal["choice", "noul", "score"]
Track = Literal["default", "production-tuned"]


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)


class ChoiceQuestion(Contract):
    id: str = Field(min_length=1, max_length=128)
    type: Literal["choice"]
    instructions: str = Field(min_length=1, max_length=65536)
    criteria: dict[str, str] = Field(min_length=2, max_length=100)


class NoulQuestion(Contract):
    id: str = Field(min_length=1, max_length=128)
    type: Literal["noul"]
    instructions: str = Field(min_length=1, max_length=65536)
    criteria: dict[str, str] | str | None = None


class ScoreQuestion(Contract):
    id: str = Field(min_length=1, max_length=128)
    type: Literal["score"]
    instructions: str = Field(min_length=1, max_length=65536)
    criteria: list[str] = Field(min_length=2, max_length=10)


Question = Annotated[ChoiceQuestion | NoulQuestion | ScoreQuestion, Field(discriminator="type")]


class ExpectedAnswer(Contract):
    kind: Literal["hard_label"] = "hard_label"
    value: StrictStr | StrictBool | StrictInt


class Transformation(Contract):
    source_case_id: str
    expected_relation: Literal["invariant", "changed", "diagnostic"] = "invariant"


class EvaluationCase(Contract):
    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,159}$")
    family_id: str = Field(min_length=1, max_length=160)
    split: Literal["development", "evaluation", "sealed"]
    domain: str = Field(min_length=1, max_length=128)
    primitive: Primitive
    variant: Literal[
        "base",
        "paraphrase",
        "paraphrase_2",
        "state_key_order",
        "option_order",
        "opaque_labels",
        "distractor",
        "adversarial_state",
        "context_length",
        "option_cardinality",
    ]
    state: Any
    question: Question
    expected: ExpectedAnswer
    transformation: Transformation | None = None
    label_space_id: str = ""
    label_map: dict[str, str] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_answer_space(self):
        if self.primitive != self.question.type:
            raise ValueError("primitive must match question.type")
        raw = json.dumps(self.state, allow_nan=False, ensure_ascii=False)
        if len(raw.encode()) > 1024 * 1024:
            raise ValueError("state exceeds the 1 MiB limit")
        if not isinstance(self.state, (dict, list, str)):
            raise ValueError("state must be a JSON object, array, or string")
        answer = self.expected.value
        if self.question.type == "choice":
            if not isinstance(answer, str) or answer not in self.question.criteria:
                raise ValueError("expected.value must be a Choice criterion key")
            if any(not k.strip() or not v.strip() for k, v in self.question.criteria.items()):
                raise ValueError("Choice criteria keys and descriptions must be nonempty")
        elif self.question.type == "noul" and type(answer) is not bool:
            raise ValueError("Noul expected.value must be boolean")
        elif self.question.type == "score":
            if type(answer) is not int or not 0 <= answer < len(self.question.criteria):
                raise ValueError("Score expected.value must be an ordinal level index")
            if len(set(self.question.criteria)) != len(self.question.criteria):
                raise ValueError("Score descriptions must distinguish every ordered level")
        if self.primitive != "choice" and self.variant in ("option_order", "opaque_labels"):
            raise ValueError("This transformation applies only to Choice")
        if self.label_map and (
            set(self.label_map) != set(self.options)
            or len(set(self.label_map.values())) != len(self.label_map)
        ):
            raise ValueError("label_map must bijectively cover every outcome")
        if self.variant == "opaque_labels" and not self.label_map:
            raise ValueError("opaque_labels requires a semantic label_map")
        return self

    @property
    def options(self) -> list[str]:
        if self.question.type == "choice":
            return list(self.question.criteria)
        if self.question.type == "noul":
            return ["false", "true"]
        return [str(i) for i in range(len(self.question.criteria))]

    @property
    def expected_key(self) -> str:
        value = self.expected.value
        return str(value).lower() if isinstance(value, bool) else str(value)

    def request(self) -> dict:
        question = self.question.model_dump(exclude={"id"}, exclude_none=True)
        if self.primitive == "noul" and isinstance(question.get("criteria"), str):
            question["criteria"] = {
                "true": question["criteria"],
                "false": "The statement is not true under the supplied criteria.",
            }
        return {"state": self.state, "questions": {self.question.id: question}}


class JevConfiguration(Contract):
    enabled: bool = True
    model: str = "jev-1.13.0"
    timeout_seconds: float = Field(default=30, ge=1, le=300)
    max_retries: int = Field(default=2, ge=0, le=5)


class LayaConfiguration(Contract):
    enabled: bool = True
    mode: Literal["router"] = "router"
    device: Literal["auto", "cpu", "mps", "cuda"] = "auto"
    preload: Literal[True] = True
    timeout_seconds: float = Field(default=120, ge=5, le=600)
    checkpoint_revision: str | None = None
    checkpoint: Literal["router", "english", "multilingual", "typed-decisions"] = "router"


class Systems(Contract):
    jev: JevConfiguration = Field(default_factory=JevConfiguration)
    laya: LayaConfiguration = Field(default_factory=LayaConfiguration)


class Repeatability(Contract):
    enabled: bool = False
    repetitions: int = Field(default=5, ge=2, le=20)
    sample_size: int = Field(default=30, ge=1, le=500)


class Performance(Contract):
    enabled: bool = False
    concurrency: list[int] = Field(default_factory=lambda: [1, 4, 8], min_length=1, max_length=3)
    batch_sizes: list[int] = Field(
        default_factory=lambda: [1, 5, 10, 50], min_length=1, max_length=4
    )
    sample_size: int = Field(default=30, ge=1, le=1000)

    @model_validator(mode="after")
    def limits(self):
        if len(set(self.concurrency)) != len(self.concurrency) or len(set(self.batch_sizes)) != len(
            self.batch_sizes
        ):
            raise ValueError("Load test settings must not contain duplicates")
        if any(v not in (1, 4, 8) for v in self.concurrency):
            raise ValueError("concurrency must use 1, 4, or 8")
        if any(v not in (1, 5, 10, 50) for v in self.batch_sizes):
            raise ValueError("batch_sizes must use 1, 5, 10, or 50")
        return self


class Suites(Contract):
    quality: Literal[True] = True
    calibration: Literal[True] = True
    robustness: Literal[True] = True
    repeatability: Repeatability = Field(default_factory=Repeatability)
    performance: Performance = Field(default_factory=Performance)
    context_length: bool = False
    option_cardinality: bool = False


class MetricConfiguration(Contract):
    ece_bins: int = Field(default=10, ge=2, le=50)
    confidence_thresholds: list[float] = Field(default_factory=lambda: [0.6, 0.7, 0.8, 0.9])
    bootstrap_samples: int = Field(default=2000, ge=10, le=10000)
    bootstrap_seed: int = Field(default=20260924, ge=0)
    local_hourly_cost_usd: float | None = Field(default=None, ge=0)
    local_cost_basis: str | None = None
    jev_usd_per_million_input_tokens: float = Field(default=0.042, ge=0)

    @model_validator(mode="after")
    def thresholds_valid(self):
        if not self.confidence_thresholds or any(
            not 0 <= t <= 1 for t in self.confidence_thresholds
        ):
            raise ValueError("confidence thresholds must be within [0, 1]")
        if self.local_hourly_cost_usd is not None and not self.local_cost_basis:
            raise ValueError("Local cost estimates require an explicit hardware/utilization basis")
        return self


class RunConfiguration(Contract):
    name: str = Field(default="Paired evaluation", min_length=1, max_length=160)
    track: Track = "default"
    dataset_ref: str
    dataset_digest: str | None = None
    seed: int = 20260924
    mode: Literal["live", "fake"] = "live"
    systems: Systems = Field(default_factory=Systems)
    suites: Suites = Field(default_factory=Suites)
    metrics: MetricConfiguration = Field(default_factory=MetricConfiguration)
    calibration_id: str | None = None
    protocol_id: str | None = None
    publication: bool = False
    acknowledge_remote: bool = False
    # Matched overrides are keyed by label_space_id and applied to both adapters.
    instruction_overrides: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def integrity(self):
        if not self.systems.jev.enabled or not self.systems.laya.enabled:
            raise ValueError("Paired comparisons require both systems")
        if self.track == "default" and (
            self.calibration_id
            or self.instruction_overrides
            or self.systems.laya.checkpoint != "router"
        ):
            raise ValueError("Default track cannot use tuning artifacts or checkpoint overrides")
        if self.publication and self.mode != "live":
            raise ValueError("Simulated runs cannot be publishable")
        if self.mode == "live" and not self.acknowledge_remote:
            raise ValueError("Confirm that Jev-bound state leaves this machine")
        return self


class BenchmarkWorkflowRequest(Contract):
    name: str = Field(min_length=1, max_length=160)
    dataset_jsonl: str = Field(min_length=1)
    profile: Literal["standard", "full"] = "standard"
    publication: bool = False


class BenchmarkAdvanceRequest(Contract):
    confirm_live_calls: bool = False
    confirm_remote_data: bool = False
