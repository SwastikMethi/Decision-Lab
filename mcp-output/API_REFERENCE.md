# DecisionLab API reference

- Discovery method: OpenAPI runtime export
- Discovery source: `docs/openapi.json`
- Base URL: Unknown in the OpenAPI document; the local CLI defaults to `http://127.0.0.1:8768`
- Authentication: No HTTP authentication scheme is declared. The backend is local-only and restricts trusted hosts and cross-origin mutations.
- Confidence: 33 High, 0 Medium, 0 Low
- Unresolved questions: None

## Health

- Method: GET
- Path: `/api/v1/health`
- Authentication: None declared
- Risk: Internal
- Confidence: High
- Source: `docs/openapi.json` — `health_api_v1_health_get`

### Inputs

None.

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Health and application version | Object |

## Readiness

- Method: GET
- Path: `/api/v1/readiness`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `readiness_api_v1_readiness_get`

### Inputs

None.

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Jev, Laya, storage, and simulation readiness | Object |

## List benchmark workflows

- Method: GET
- Path: `/api/v1/benchmark-workflows`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `benchmark_workflows_api_v1_benchmark_workflows_get`

### Inputs

None.

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Workflow items and total | Object |

## Create benchmark workflow

- Method: POST
- Path: `/api/v1/benchmark-workflows`
- Authentication: None declared
- Risk: Write
- Confidence: High
- Source: `docs/openapi.json` — `create_benchmark_workflow_api_v1_benchmark_workflows_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| name | JSON body | string | Yes | Workflow display name, 1–160 characters |
| dataset_jsonl | JSON body | string | Yes | UTF-8 DecisionLab JSONL, up to 25 MiB after encoding |
| profile | JSON body | `standard` or `full` | No | Evaluation depth; defaults to `standard` |
| publication | JSON body | boolean | No | Whether the frozen runs are intended for publication; defaults to false |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 201 | Prepared workflow with estimates and review paths | Object |
| 400 | Invalid dataset or methodology split | Error object |
| 422 | Request validation failed | HTTPValidationError |

## Estimate run

- Method: POST
- Path: `/api/v1/runs/estimate`
- Authentication: None declared
- Risk: Write
- Confidence: High
- Source: `docs/openapi.json` — `estimate_api_v1_runs_estimate_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| dataset_ref | JSON body | string | Yes | Managed dataset identifier |
| name, track, seed, mode | JSON body | mixed | No | Run identity and execution mode |
| systems, suites, metrics | JSON body | objects | No | Provider, suite, and metric configuration |
| calibration_id, protocol_id | JSON body | string or null | No | Frozen evidence references |
| publication, acknowledge_remote | JSON body | boolean | No | Publication and remote-data acknowledgements |
| instruction_overrides | JSON body | object | No | Production-tuned instructions by label space |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Request, question, warm-up, and retry counts | Object |
| 422 | Request validation failed | HTTPValidationError |

## List runs

- Method: GET
- Path: `/api/v1/runs`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `runs_api_v1_runs_get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| page | Query | integer | No | One-based page, default 1 |
| page_size | Query | integer | No | Rows per page, 1–500 |
| status | Query | string | No | Filter by run status |
| track | Query | string | No | Filter by default or production-tuned track |
| dataset | Query | string | No | Filter by dataset id |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Paginated run manifests | Object |
| 422 | Query validation failed | HTTPValidationError |

## Start run

- Method: POST
- Path: `/api/v1/runs`
- Authentication: None declared
- Risk: Write
- Confidence: High
- Source: `docs/openapi.json` — `start_run_api_v1_runs_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| dataset_ref | JSON body | string | Yes | Managed dataset identifier |
| name, track, seed, mode | JSON body | mixed | No | Run identity and execution mode |
| systems, suites, metrics | JSON body | objects | No | Provider, suite, and metric configuration |
| calibration_id, protocol_id | JSON body | string or null | No | Frozen evidence references |
| publication, acknowledge_remote | JSON body | boolean | No | Publication and remote-data acknowledgements |
| instruction_overrides | JSON body | object | No | Production-tuned instructions by label space |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 202 | Run id, initial status, and events URL | Object |
| 400 | Runtime, readiness, or evidence validation failed | Error object |
| 422 | Request validation failed | HTTPValidationError |

## Get run

- Method: GET
- Path: `/api/v1/runs/{run_id}`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `run_api_v1_runs__run_id__get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | Run identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Run manifest | Object |
| 404 | Run not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## Cancel run

- Method: POST
- Path: `/api/v1/runs/{run_id}/cancel`
- Authentication: None declared
- Risk: Write
- Confidence: High
- Source: `docs/openapi.json` — `cancel_api_v1_runs__run_id__cancel_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | Run identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Updated cancelled run manifest | Object |
| 404 | Run not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## Rescore run

- Method: POST
- Path: `/api/v1/runs/{run_id}/rescore`
- Authentication: None declared
- Risk: Write
- Confidence: High
- Source: `docs/openapi.json` — `rescore_api_v1_runs__run_id__rescore_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | Terminal run identifier |
| scoring_version | JSON body | string | No | Installed scoring version, default `1.0.0` |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Run id and scoring version | Object |
| 400 | Run is active or version is unavailable | Error object |
| 422 | Request validation failed | HTTPValidationError |

## Get run summary

- Method: GET
- Path: `/api/v1/runs/{run_id}/summary`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `summary_api_v1_runs__run_id__summary_get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | Run identifier |
| domain, primitive, variant, split | Query | string | No | Case dimension filters |
| disagreement, jev_correct, laya_correct | Query | boolean | No | Outcome filters |
| confidence_min, confidence_max | Query | number | No | Inclusive probability range from 0 to 1 |
| error_category | Query | string | No | Provider error category |
| q | Query | string | No | Free-text case search, max 500 characters |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Metrics, comparisons, slices, and limitations | Object |
| 404 | Run not found | Error object |
| 422 | Query validation failed | HTTPValidationError |

## List run cases

- Method: GET
- Path: `/api/v1/runs/{run_id}/cases`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `cases_api_v1_runs__run_id__cases_get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | Run identifier |
| page, page_size | Query | integer | No | One-based page and size from 1 to 500 |
| domain, primitive, variant, split | Query | string | No | Case dimension filters |
| disagreement, jev_correct, laya_correct | Query | boolean | No | Outcome filters |
| confidence_min, confidence_max | Query | number | No | Inclusive probability range from 0 to 1 |
| error_category | Query | string | No | Provider error category |
| q | Query | string | No | Free-text case search, max 500 characters |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Paginated case comparisons with state previews | Object |
| 404 | Run not found | Error object |
| 422 | Query validation failed | HTTPValidationError |

## Get run playback

- Method: GET
- Path: `/api/v1/runs/{run_id}/playback`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `playback_api_v1_runs__run_id__playback_get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | Run identifier |
| after | Query | integer | No | Return frames after this index, default -1 |
| limit | Query | integer | No | Frame limit from 1 to 100 |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Playback frames and cursor metadata | PlaybackPage |
| 404 | Run not found | Error object |
| 422 | Query validation failed | HTTPValidationError |

## Get run case detail

- Method: GET
- Path: `/api/v1/runs/{run_id}/cases/{case_id}`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `case_detail_api_v1_runs__run_id__cases__case_id__get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | Run identifier |
| case_id | Path | string | Yes | Case identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Case, paired predictions, family rows, and all attempts | Object |
| 404 | Run or case not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## Get run chart

- Method: GET
- Path: `/api/v1/runs/{run_id}/charts/{chart_id}`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `chart_api_v1_runs__run_id__charts__chart_id__get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | Run identifier |
| chart_id | Path | string | Yes | Supported chart identifier |
| domain, primitive, variant, split | Query | string | No | Case dimension filters |
| disagreement, jev_correct, laya_correct | Query | boolean | No | Outcome filters |
| confidence_min, confidence_max | Query | number | No | Inclusive probability range from 0 to 1 |
| error_category, q | Query | string | No | Error and free-text filters |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Chart-ready data | Object |
| 404 | Run or chart not found | Error object |
| 422 | Query validation failed | HTTPValidationError |

## Compare runs

- Method: GET
- Path: `/api/v1/runs/{run_id}/comparison/{other_id}`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `compare_runs_api_v1_runs__run_id__comparison__other_id__get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | First run identifier |
| other_id | Path | string | Yes | Second compatible run identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Left and right summaries | Object |
| 400 | Tracks, datasets, scoring, or modes differ | Error object |
| 404 | Run not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## Export run

- Method: GET
- Path: `/api/v1/runs/{run_id}/exports/{format}`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `export_api_v1_runs__run_id__exports__format__get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | Terminal run identifier |
| format | Path | string | Yes | `markdown`, `html`, `summary-json`, `predictions-jsonl`, or `bundle` |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Requested report, data, or ZIP bundle | File or stream |
| 403 | Sealed results have not been released | Error object |
| 404 | Run or format not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## Stream run events

- Method: GET
- Path: `/api/v1/runs/{run_id}/events`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `events_api_v1_runs__run_id__events_get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | Path | string | Yes | Run identifier |
| after | Query | integer | No | Last numeric event id already observed |
| Last-Event-ID | Header | integer | No | SSE replay cursor; combined with `after` |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Server-sent event stream through the terminal state | `text/event-stream` |
| 400 | Invalid event cursor | Error object |
| 404 | Run not found | Error object |
| 422 | Query validation failed | HTTPValidationError |

## Get benchmark workflow

- Method: GET
- Path: `/api/v1/benchmark-workflows/{workflow_id}`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `benchmark_workflow_api_v1_benchmark_workflows__workflow_id__get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| workflow_id | Path | string | Yes | Workflow identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Durable stage, estimates, review state, current run, blocker, and next action | Object |
| 404 | Workflow not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## Advance benchmark workflow

- Method: POST
- Path: `/api/v1/benchmark-workflows/{workflow_id}/advance`
- Authentication: None declared
- Risk: Destructive
- Confidence: High
- Source: `docs/openapi.json` — `advance_benchmark_workflow_api_v1_benchmark_workflows__workflow_id__advance_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| workflow_id | Path | string | Yes | Workflow identifier |
| confirm_live_calls | JSON body | boolean | No | Explicitly approve live Jev and Laya execution; defaults to false |
| confirm_remote_data | JSON body | boolean | No | Explicitly approve sending case state to Jev's hosted API; defaults to false |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Updated workflow; at most one provider run was started | Object |
| 400 | Consent, review, calibration, or workflow invariant failed | Error object |
| 404 | Workflow not found | Error object |
| 409 | Another evaluation is active | Error object |
| 422 | Request validation failed | HTTPValidationError |

## Cancel benchmark workflow

- Method: POST
- Path: `/api/v1/benchmark-workflows/{workflow_id}/cancel`
- Authentication: None declared
- Risk: Destructive
- Confidence: High
- Source: `docs/openapi.json` — `cancel_benchmark_workflow_api_v1_benchmark_workflows__workflow_id__cancel_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| workflow_id | Path | string | Yes | Workflow identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Cancelled workflow with retained run references | Object |
| 404 | Workflow not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## Get benchmark workflow report

- Method: GET
- Path: `/api/v1/benchmark-workflows/{workflow_id}/report`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `benchmark_workflow_report_api_v1_benchmark_workflows__workflow_id__report_get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| workflow_id | Path | string | Yes | Completed workflow identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Default and tuned verdicts, KPIs, and Markdown report | Object |
| 400 | Both frozen tracks have not completed | Error object |
| 404 | Workflow not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## List datasets

- Method: GET
- Path: `/api/v1/datasets`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `datasets_api_v1_datasets_get`

### Inputs

None.

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Dataset metadata list | Object |

## Validate and import dataset

- Method: POST
- Path: `/api/v1/datasets/validate`
- Authentication: None declared
- Risk: Write
- Confidence: High
- Source: `docs/openapi.json` — `upload_api_v1_datasets_validate_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| file | Multipart body | binary | Yes | UTF-8 JSONL dataset, up to 25 MiB |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Validation result and imported dataset metadata | Object |
| 413 | Upload exceeds the configured limit | Error object |
| 422 | Request validation failed | HTTPValidationError |

## Get dataset

- Method: GET
- Path: `/api/v1/datasets/{dataset_id}`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `dataset_api_v1_datasets__dataset_id__get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| dataset_id | Path | string | Yes | Managed dataset identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Metadata, non-sealed preview, and review progress | Object |
| 404 | Dataset not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## Get dataset review packet

- Method: GET
- Path: `/api/v1/datasets/{dataset_id}/review-packet`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `packet_api_v1_datasets__dataset_id__review_packet_get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| dataset_id | Path | string | Yes | Managed dataset identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Cases without expected answers or author metadata | Object |
| 404 | Dataset not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## Import dataset reviews

- Method: POST
- Path: `/api/v1/datasets/{dataset_id}/reviews`
- Authentication: None declared
- Risk: Write
- Confidence: High
- Source: `docs/openapi.json` — `reviews_api_v1_datasets__dataset_id__reviews_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| dataset_id | Path | string | Yes | Managed dataset identifier |
| reviews | JSON body | array of objects | Yes | Independent reviewer labels and rationales |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Approved, total, and complete review counts | Object |
| 400 | Review independence or answer validation failed | Error object |
| 422 | Request validation failed | HTTPValidationError |

## List calibrations

- Method: GET
- Path: `/api/v1/calibrations`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `calibrations_api_v1_calibrations_get`

### Inputs

None.

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Calibration artifacts | Object |

## Fit calibration

- Method: POST
- Path: `/api/v1/calibrations`
- Authentication: None declared
- Risk: Write
- Confidence: High
- Source: `docs/openapi.json` — `calibrate_api_v1_calibrations_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| run_id | JSON body | string | Yes | Completed uncalibrated development run |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 201 | Frozen calibration artifact | Object |
| 400 | Run is ineligible or has no usable development predictions | Error object |
| 422 | Request validation failed | HTTPValidationError |

## Get calibration

- Method: GET
- Path: `/api/v1/calibrations/{calibration_id}`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `calibration_api_v1_calibrations__calibration_id__get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| calibration_id | Path | string | Yes | Calibration identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Calibration parameters, source, signature, and warnings | Object |
| 404 | Calibration not found | Error object |
| 422 | Path validation failed | HTTPValidationError |

## List protocols

- Method: GET
- Path: `/api/v1/protocols`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `protocols_api_v1_protocols_get`

### Inputs

None.

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Frozen protocol records | Object |

## Freeze protocol

- Method: POST
- Path: `/api/v1/protocols`
- Authentication: None declared
- Risk: Write
- Confidence: High
- Source: `docs/openapi.json` — `freeze_api_v1_protocols_post`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| dataset_id | JSON body | string | Yes | Fully reviewed evaluation dataset |
| configurations | JSON body | object | Yes | Exactly `default` and `production-tuned` live configurations |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 201 | Frozen protocol and configuration fingerprints | Object |
| 400 | Review, pinning, calibration, or configuration invariant failed | Error object |
| 422 | Request validation failed | HTTPValidationError |

## Get protocol

- Method: GET
- Path: `/api/v1/protocols/{protocol_id}`
- Authentication: None declared
- Risk: Read
- Confidence: High
- Source: `docs/openapi.json` — `protocol_api_v1_protocols__protocol_id__get`

### Inputs

| Name | Location | Type | Required | Description |
| --- | --- | --- | --- | --- |
| protocol_id | Path | string | Yes | Protocol identifier |

### Responses

| Status | Meaning | Schema |
| --- | --- | --- |
| 200 | Frozen tracks, registered runs, and sealed-release state | Object |
| 404 | Protocol not found | Error object |
| 422 | Path validation failed | HTTPValidationError |
