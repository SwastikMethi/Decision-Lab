# DecisionLab MCP design

## Design summary

The server exposes the durable benchmark workflow rather than the lower-level DecisionLab resources it coordinates. One workflow validates and partitions `dataset.jsonl`, estimates three runs, fits calibration on development data, pauses for independent review, freezes the default and production-tuned tracks, runs them in order, releases sealed results, and returns a deterministic KPI report. Six tools cover that lifecycle and stay below the 12-tool soft cap.

## Generated tools

| Tool | Purpose | API mapping | Risk | Included |
| --- | --- | --- | --- | --- |
| `prepare_benchmark` | Read `<folder>/dataset.jsonl`, validate its local path, and prepare a workflow with estimates and a review packet. | `POST /api/v1/benchmark-workflows` | Write | Yes |
| `list_benchmarks` | List workflow ids, stages, and next actions. | `GET /api/v1/benchmark-workflows` | Read | Yes |
| `get_benchmark_status` | Get estimates, review progress, current run, blocker, and next action for one workflow. | `GET /api/v1/benchmark-workflows/{workflow_id}` | Read | Yes |
| `advance_benchmark` | Advance local transitions and start at most one live provider run. | `POST /api/v1/benchmark-workflows/{workflow_id}/advance` | Destructive | Yes |
| `cancel_benchmark` | Stop the active run and retain existing evidence. | `POST /api/v1/benchmark-workflows/{workflow_id}/cancel` | Destructive | Yes |
| `get_benchmark_report` | Return default and tuned verdicts, confidence intervals, KPIs, and Markdown. | `GET /api/v1/benchmark-workflows/{workflow_id}/report` | Read | Yes |

## Endpoint-to-tool mappings

| Operation | Tool | Notes |
| --- | --- | --- |
| `create_benchmark_workflow_api_v1_benchmark_workflows_post` | `prepare_benchmark` | The custom tool reads the fixed local filename and sends its UTF-8 contents to the backend. |
| `benchmark_workflows_api_v1_benchmark_workflows_get` | `list_benchmarks` | Direct read. |
| `benchmark_workflow_api_v1_benchmark_workflows__workflow_id__get` | `get_benchmark_status` | Direct read by workflow id. |
| `advance_benchmark_workflow_api_v1_benchmark_workflows__workflow_id__advance_post` | `advance_benchmark` | Explicit confirmation fields are forwarded; one call can create at most one provider run. |
| `cancel_benchmark_workflow_api_v1_benchmark_workflows__workflow_id__cancel_post` | `cancel_benchmark` | Cancels only the workflow's active run. |
| `benchmark_workflow_report_api_v1_benchmark_workflows__workflow_id__report_get` | `get_benchmark_report` | Available after both tracks complete. |

## Excluded operations

| Operation | Risk | Reason |
| --- | --- | --- |
| `health_api_v1_health_get` | Internal | Backend diagnostic, outside the benchmark workflow. |
| `readiness_api_v1_readiness_get` | Read | Live creation already enforces readiness and returns the failure. |
| `datasets_api_v1_datasets_get` | Read | Raw dataset administration is owned by preparation. |
| `upload_api_v1_datasets_validate_post` | Write | It bypasses workflow partitioning and MCP path controls. |
| `dataset_api_v1_datasets__dataset_id__get` | Read | Workflow status contains the relevant dataset references. |
| `packet_api_v1_datasets__dataset_id__review_packet_get` | Read | Preparation returns the packet path. |
| `reviews_api_v1_datasets__dataset_id__reviews_post` | Write | Review import is driven by the workflow submission file. |
| `estimate_api_v1_runs_estimate_post` | Write | Preparation returns all three estimates. |
| `runs_api_v1_runs_get` | Read | Raw runs are workflow implementation details. |
| `start_run_api_v1_runs_post` | Write | It bypasses consent, review, and frozen ordering. |
| `run_api_v1_runs__run_id__get` | Read | Workflow status includes the active run. |
| `cancel_api_v1_runs__run_id__cancel_post` | Write | Workflow cancellation must update both records. |
| `rescore_api_v1_runs__run_id__rescore_post` | Write | Rescoring is outside the fixed workflow. |
| `summary_api_v1_runs__run_id__summary_get` | Read | The workflow report is the curated summary. |
| `cases_api_v1_runs__run_id__cases_get` | Read | Large case inspection belongs to the website. |
| `playback_api_v1_runs__run_id__playback_get` | Read | Visual playback belongs to the website. |
| `case_detail_api_v1_runs__run_id__cases__case_id__get` | Read | Per-case inspection belongs to the website. |
| `chart_api_v1_runs__run_id__charts__chart_id__get` | Read | Chart payloads are website presentation details. |
| `compare_runs_api_v1_runs__run_id__comparison__other_id__get` | Read | The report compares its paired tracks. |
| `export_api_v1_runs__run_id__exports__format__get` | Read | Large or binary exports are outside the concise MCP report. |
| `events_api_v1_runs__run_id__events_get` | Read | SSE streaming does not fit the polling workflow. |
| `calibrations_api_v1_calibrations_get` | Read | Calibration is managed automatically. |
| `calibrate_api_v1_calibrations_post` | Write | Direct fitting could bypass the development-only rule. |
| `calibration_api_v1_calibrations__calibration_id__get` | Read | The report includes calibration identity and policy KPIs. |
| `protocols_api_v1_protocols_get` | Read | Protocols are internal workflow evidence. |
| `freeze_api_v1_protocols_post` | Write | Direct freezing could bypass review and paired-config checks. |
| `protocol_api_v1_protocols__protocol_id__get` | Read | Workflow status and report expose the useful protocol state. |

## Risk and approval behavior

`prepare_benchmark` writes local DecisionLab records but makes no provider calls. `advance_benchmark` is destructive because it can incur provider usage and send case state to Jev's hosted API. The first advance remains blocked until `confirm_live_calls=true` and `confirm_remote_data=true`; later calls use the stored authorization fingerprint. Each call starts no more than one run. `cancel_benchmark` is destructive because it stops active work, while retaining completed artifacts.

Tests call mutating tools only against mock HTTP endpoints. Verification never starts a live provider run.

## Required environment variables

| Variable | Required | Purpose |
| --- | --- | --- |
| `TARGET_API_BASE_URL` | No | DecisionLab backend URL; defaults to `http://127.0.0.1:8768`. |
| `DECISIONLAB_DATASET_ROOT` | Yes | Absolute trusted root containing selectable dataset folders. |

Provider credentials stay in the separately started DecisionLab backend and are never passed to the MCP process.
