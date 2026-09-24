# API and Data Contract Specification

## 1. Contract goals

- One canonical representation for Jev and Laya inputs and outputs.
- Strong validation before provider calls.
- Complete evidence for every metric.
- Stable backend/frontend integration.
- Reproducible run artifacts without a database.

All timestamps use ISO 8601 UTC. Durations use milliseconds. Costs use USD unless another currency is explicitly named.

## 2. Evaluation case

```json
{
  "schema_version": "1.0",
  "id": "support-001-option-order",
  "family_id": "support-001",
  "split": "evaluation",
  "domain": "customer_support",
  "primitive": "choice",
  "variant": "option_order",
  "state": {
    "message": "I was charged twice. Please return the extra payment."
  },
  "question": {
    "id": "department",
    "type": "choice",
    "instructions": "Which department should handle this request?",
    "criteria": {
      "technical": "Bugs, outages, or system errors",
      "other": "Everything else",
      "billing": "Invoices, payments, charges, or refunds"
    }
  },
  "expected": {
    "kind": "hard_label",
    "value": "billing"
  },
  "transformation": {
    "source_case_id": "support-001-base",
    "expected_relation": "invariant"
  },
  "metadata": {
    "author": "project",
    "review_status": "approved",
    "difficulty": "standard",
    "tags": ["billing", "duplicate-charge"]
  }
}
```

### Required validation

- `id` is unique.
- `family_id` exists for robustness variants.
- `primitive` matches `question.type`.
- `choice` criteria contain at least two options.
- `score` criteria are an ordered list with at least two levels.
- `noul` expected value is boolean.
- Hard-label expectation belongs to the available answer space.
- State is valid JSON and within configured size limits.
- A sealed split is not displayed through ordinary dataset-preview endpoints.

## 3. Run configuration

```json
{
  "name": "Default comparison — publishable set",
  "track": "default",
  "dataset_ref": "evals/publishable.jsonl",
  "dataset_digest": "sha256:...",
  "seed": 20260924,
  "systems": {
    "jev": {
      "enabled": true,
      "model": "jev-1.13.0",
      "timeout_seconds": 30,
      "max_retries": 2
    },
    "laya": {
      "enabled": true,
      "mode": "router",
      "device": "auto",
      "preload": true,
      "checkpoint_revision": "pinned-revision"
    }
  },
  "suites": {
    "quality": true,
    "calibration": true,
    "robustness": true,
    "repeatability": {
      "enabled": true,
      "repetitions": 5,
      "sample_size": 30
    },
    "performance": {
      "enabled": true,
      "concurrency": [1, 4, 8],
      "batch_sizes": [1, 5, 10, 50]
    }
  },
  "metrics": {
    "ece_bins": 10,
    "confidence_thresholds": [0.6, 0.7, 0.8, 0.9],
    "bootstrap_samples": 2000,
    "bootstrap_seed": 20260924
  }
}
```

The backend stores the submitted and effective configurations. Effective configuration includes all defaults and resolved versions.

## 4. Canonical prediction

```json
{
  "schema_version": "1.0",
  "run_id": "01J...",
  "case_id": "support-001-option-order",
  "family_id": "support-001",
  "system_id": "jev-default",
  "adapter_id": "jev",
  "track": "default",
  "attempt": 1,
  "status": "success",
  "answer": {
    "selected": "billing",
    "score": null,
    "probabilities": {
      "technical": 0.03,
      "other": 0.02,
      "billing": 0.95
    },
    "provider_confidence": 0.93,
    "decision_probability": 0.95
  },
  "correctness": {
    "is_correct": true,
    "error_type": null
  },
  "timing": {
    "started_at": "2026-09-24T12:00:00Z",
    "ended_at": "2026-09-24T12:00:00.381Z",
    "latency_ms": 381.0,
    "inference_ms": null,
    "is_warm": true
  },
  "usage": {
    "input_tokens": 142,
    "output_tokens": 0,
    "provider_cost_usd": 0.000005964,
    "estimated_compute_cost_usd": null
  },
  "model": {
    "requested": "jev-1.13.0",
    "resolved": "jev-1.13.0",
    "checkpoint": null,
    "route": null,
    "device": "remote-api"
  },
  "retry_count": 0,
  "warnings": [],
  "error": null,
  "raw_response": {}
}
```

### Prediction invariants

- Successful probabilities are finite and within `[0, 1]`.
- Choice and Score probability distributions sum to 1 within configured tolerance.
- Noul is normalized to `false` and `true` probabilities.
- Probability keys align with canonical criteria, not display order.
- `decision_probability` is the probability of the selected outcome.
- Failed predictions contain no fabricated probability distribution.
- Raw responses are sanitized before persistence.

## 5. Error object

```json
{
  "category": "rate_limit",
  "code": "JEV_429",
  "message": "Provider rate limit reached.",
  "retryable": true,
  "provider_status": 429,
  "details": {
    "retry_after_ms": 1000
  }
}
```

Valid categories:

- `authentication`
- `rate_limit`
- `timeout`
- `network`
- `invalid_request`
- `context_limit`
- `runtime`
- `normalization`
- `cancelled`
- `unknown`

## 6. Run manifest

The manifest contains:

- run ID and name;
- lifecycle status;
- submitted/effective configuration;
- dataset digest and counts;
- scoring version;
- application commit/version;
- system versions;
- environment reference;
- timestamps;
- partial/final flags;
- warnings;
- artifact index.

## 7. Summary contract

```json
{
  "run_id": "01J...",
  "status": "completed",
  "scoring_version": "1.0.0",
  "counts": {
    "cases": 360,
    "families": 60,
    "successful_predictions": 718,
    "failed_predictions": 2
  },
  "systems": {
    "jev-default": {
      "correctness": {},
      "calibration": {},
      "selective_automation": {},
      "robustness": {},
      "repeatability": {},
      "performance": {},
      "cost": {},
      "resources": {}
    },
    "laya-router-default": {}
  },
  "slices": [],
  "comparisons": [],
  "findings": [],
  "limitations": []
}
```

`findings` must include metric references and filter definitions. Generated natural-language summaries cannot introduce unsupported conclusions.

## 8. REST API

Base path: `/api/v1`

### Health and readiness

#### `GET /health`

Returns service health without loading model weights.

#### `GET /readiness`

Returns:

- Jev configured/reachable status;
- Laya installed/checkpoint/device status;
- storage writability;
- version metadata;
- sanitized warnings.

### Datasets

#### `GET /datasets`

Lists bundled and imported datasets with counts and validation state.

#### `POST /datasets/validate`

Accepts an uploaded JSONL file or staged dataset reference. Returns line-level issues, counts, digest, and whether the dataset can run.

#### `GET /datasets/{dataset_id}`

Returns metadata and non-sealed preview records.

### Runs

#### `POST /runs`

Creates a run from `RunConfiguration`.

Response: `202 Accepted`

```json
{
  "run_id": "01J...",
  "status": "validating",
  "events_url": "/api/v1/runs/01J.../events"
}
```

#### `GET /runs`

Lists runs with pagination and filters for status, track, dataset, and date.

#### `GET /runs/{run_id}`

Returns current manifest snapshot, progress, warnings, and artifact availability.

#### `POST /runs/{run_id}/cancel`

Requests cancellation. It is idempotent.

#### `POST /runs/{run_id}/rescore`

Recomputes derived metrics from immutable predictions using a selected scoring version. It never calls providers.

#### `GET /runs/{run_id}/summary`

Returns final or provisional summary. Provisional status is explicit.

#### `GET /runs/{run_id}/cases`

Paginated case comparison endpoint. Supports filters for:

- domain;
- primitive;
- variant;
- system correctness;
- disagreement;
- confidence range;
- error category;
- free-text query.

#### `GET /runs/{run_id}/cases/{case_id}`

Returns canonical case, all system predictions, family variants, and metadata.

#### `GET /runs/{run_id}/charts/{chart_id}`

Returns normalized chart data for complex visualizations. Initial chart IDs:

- `accuracy-by-primitive`
- `domain-heatmap`
- `calibration`
- `risk-coverage`
- `confidence-distribution`
- `robustness-heatmap`
- `context-length`
- `option-cardinality`
- `latency-distribution`
- `quality-latency-scatter`

#### `GET /runs/{run_id}/exports/{format}`

Formats: `markdown`, `html`, `summary-json`, `predictions-jsonl`, and `bundle`.

### Events

#### `GET /runs/{run_id}/events`

SSE stream. Supports `Last-Event-ID`.

## 9. Event contract

```text
id: 42
event: case.completed
data: {"run_id":"01J...","system_id":"jev-default","case_id":"support-001","completed":81,"total":360}
```

Event types:

- `run.created`
- `validation.started`
- `validation.completed`
- `warmup.started`
- `warmup.completed`
- `suite.started`
- `case.started`
- `case.completed`
- `case.failed`
- `metrics.provisional`
- `scoring.started`
- `scoring.completed`
- `run.completed`
- `run.cancelling`
- `run.cancelled`
- `run.failed`

Events never contain credentials or unsanitized raw provider payloads.

## 10. Run statuses

| Status | Meaning |
|---|---|
| `validating` | Dataset and configuration checks are running |
| `warming` | Adapters are preparing and warm-up requests are running |
| `running` | Primary or diagnostic suites are executing |
| `scoring` | Provider calls are complete and final metrics are building |
| `completed` | Final artifacts are available |
| `partial` | Execution stopped with usable but incomplete artifacts |
| `cancelling` | No new work is scheduled; in-flight work is settling |
| `cancelled` | User-requested cancellation completed |
| `failed` | A blocking failure prevented a usable completion |

## 11. Artifact layout

```text
runs/<run-id>/
├── manifest.json
├── effective-config.json
├── cases.snapshot.jsonl
├── predictions.jsonl
├── events.jsonl
├── errors.jsonl
├── summary.v1.0.0.json
├── report.md
├── report.html
└── environment.json
```

`environment.json` includes:

- operating system;
- Python and package versions;
- Node/frontend build version;
- CPU model and core count;
- RAM;
- accelerator and VRAM when available;
- Laya device and checkpoint revision;
- Jev endpoint class and resolved model;
- network-latency caveat;
- cost assumptions.

## 12. Pagination and limits

- Default case page size: 50.
- Maximum page size: 500.
- Dataset upload limit for prototype: configurable, default 25 MiB.
- Raw state preview is truncated in list endpoints but complete in authorized local case detail.
- Chart endpoints return aggregated data, not raw predictions.

## 13. Versioning

Version separately:

- API contract;
- case schema;
- prediction schema;
- scoring implementation;
- report template.

Backward-compatible fields may be added. Breaking changes require a new major schema or API version. Stored artifacts retain the version used to create them.

## 14. API acceptance criteria

- OpenAPI generation succeeds with no unresolved schemas.
- Frontend TypeScript types are generated or checked against the API schema.
- Fake-adapter run completes entirely through public endpoints.
- SSE reconnect restores correct progress.
- Case totals, prediction totals, and summary denominators reconcile.
- Sealed case content is not returned through preview APIs.
- Secret-scanning tests find no credentials in responses or persisted artifacts.

