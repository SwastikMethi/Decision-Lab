# Product Requirements Document

## 1. Product summary

**Product:** DecisionLab  
**Type:** Local, single-user evaluation platform  
**Initial comparison:** Jev versus Laya  
**Primary interface:** Professional React web application

DecisionLab runs controlled, paired evaluations of typed decision systems. Both systems receive equivalent state, instructions, criteria, and answer options. The platform then measures correctness, calibration, robustness, safe automation coverage, latency, throughput, cost, resource use, and operational tradeoffs.

## 2. Problem

Existing comparisons often mix different prompts, versions, datasets, hardware, tuning levels, or deployment paths. A single accuracy number hides important behavior such as:

- high confidence on wrong answers;
- sensitivity to option order or label wording;
- failure as context or option count grows;
- instability across equivalent phrasings;
- differences between local latency and remote API latency;
- the real cost of self-hosted computation;
- a model that is accurate but cannot safely automate many decisions.

Developers therefore lack a transparent way to decide which system fits their workload.

## 3. Product goal

Build an understandable and reproducible evaluation environment that answers:

> Where is each system strong, where does it fail, and how much work can it automate at an acceptable error rate?

## 4. Goals

- Run byte-equivalent typed decisions through Jev and Laya.
- Support `choice`, `noul`, and `score` primitives.
- Compare default and production-tuned configurations without mixing them.
- Preserve raw responses and complete probability distributions.
- Test semantic quality and behavioral robustness.
- Present every stage of the evaluation clearly in a professional React UI.
- Make results reproducible through version, configuration, dataset, and environment records.
- Export both a human-readable report and machine-readable artifacts.

## 5. Non-goals for the prototype

- Declaring a universal winner.
- Training a new decision model.
- Automatically creating ground truth with an LLM.
- Comparing general chat or reasoning ability.
- Multi-user collaboration, authentication, or permissions.
- Hosted SaaS deployment.
- Large-scale experiment scheduling.
- Supporting arbitrary providers beyond the Jev and Laya adapters.
- A production database.

## 6. Users

### Primary user: AI engineer

Wants to evaluate both systems for routing, moderation, guardrails, triage, or scoring before integrating one into a product.

### Secondary user: technical decision-maker

Wants a concise answer about quality, reliability, cost, privacy, and operating requirements without reading model implementation details.

### Secondary user: model or framework maintainer

Wants to inspect failures, calibration, and behavior under controlled transformations.

## 7. Product principles

1. **Paired evidence over marketing claims.** Compare the same case whenever possible.
2. **Probability quality matters.** Accuracy without calibration is incomplete.
3. **No hidden tuning.** Every threshold, prompt, checkpoint, and calibration file is recorded.
4. **No misleading free-cost claim.** Local inference has compute and operational cost even when it has no API fee.
5. **Raw evidence remains accessible.** Every summary links back to case-level responses.
6. **Animations explain state.** Motion communicates progress and change; it never disguises waiting or uncertainty.
7. **Conditional conclusions.** Report the workload where each system is preferable.

## 8. User journey

### 8.1 Create an evaluation

The user opens **New Evaluation** and:

1. selects a bundled dataset or imports JSONL;
2. sees schema, label, and ground-truth validation;
3. selects Default or Production-tuned track;
4. confirms the pinned Jev and Laya configurations;
5. selects quality, robustness, repeatability, and performance suites;
6. reviews estimated request count and expected runtime;
7. starts the evaluation.

### 8.2 Monitor execution

The Live Run page shows:

- current phase;
- completed and remaining cases;
- Jev and Laya status independently;
- warm-up versus measured requests;
- failures and retries;
- live elapsed time;
- preliminary metrics clearly marked as provisional;
- cancel control.

### 8.3 Understand results

After completion, the user sees:

- an executive summary;
- comparison by primitive, domain, variant, option count, and context size;
- confidence and calibration charts;
- risk–coverage curves;
- latency, throughput, cost, and resource metrics;
- a robustness heatmap;
- a searchable disagreement explorer;
- explicit limitations and evaluation metadata.

### 8.4 Export

The user can export:

- Markdown report;
- standalone HTML report;
- summary JSON;
- prediction JSONL;
- run configuration and environment metadata.

## 9. Functional requirements

### FR-1: Environment readiness

The system must show whether:

- the Jev credential is configured;
- the selected Jev model is reachable;
- Laya and its required checkpoint are installed;
- the local device is CPU, CUDA, or MPS;
- the dataset passes validation.

Secrets must never be returned to the frontend.

### FR-2: Dataset management

The user must be able to:

- use a bundled demonstration dataset;
- import JSONL;
- inspect validation errors by line and field;
- filter cases by domain, primitive, and variant;
- see base-family relationships;
- distinguish development and sealed evaluation splits.

### FR-3: Configuration

The user must be able to configure:

- comparison track;
- pinned model/package/checkpoint versions;
- included suites;
- repetition count;
- confidence thresholds;
- concurrency for a separate load test;
- output directory.

The UI must warn when a configuration would make the comparison unfair.

### FR-4: Paired execution

For each case, both adapters must receive the same canonical state and question. Adapter-specific serialization may differ only where required by the provider contract and must be logged.

### FR-5: Progress reporting

The backend must stream structured run events to the React UI. The UI must recover the current state after refresh.

### FR-6: Result normalization

Every provider result must be converted into a canonical prediction containing:

- selected answer or score;
- complete probability distribution;
- derived confidence when available;
- latency;
- provider-reported usage and cost when available;
- route/checkpoint metadata;
- raw response;
- error details.

### FR-7: Metrics

The platform must calculate the metrics defined in `EVALUATION-SPEC.md`, including correctness, calibration, safe automation, robustness, repeatability, performance, cost, and failures.

### FR-8: Case explorer

The user must be able to inspect any case and compare:

- input state;
- question and criteria;
- expected answer;
- Jev and Laya outputs;
- probability distributions;
- latency and cost;
- sibling variants;
- why the case counts as correct, incorrect, or abstained.

### FR-9: Reproducibility

Every run must record:

- dataset digest;
- application commit when available;
- model/package/checkpoint versions;
- track and thresholds;
- hardware and operating system;
- start/end times;
- scoring-version identifier;
- warnings and failures.

### FR-10: Reporting

Reports must describe conditional tradeoffs. A single composite score may be offered only as an optional, user-configurable view and may not replace the underlying dimensions.

## 10. Non-functional requirements

### Accuracy and integrity

- Raw responses must be immutable after a completed run.
- Metric calculations must be deterministic from stored artifacts.
- Invalid or missing predictions count as failures and are never silently excluded.

### Performance

- Normal UI interactions should respond within 150 ms after data is loaded.
- Progress events should normally appear within one second of the underlying event.
- Charts should remain usable with at least 10,000 prediction records.

### Reliability

- A failed request must not terminate the entire run.
- Interrupted runs must retain completed results.
- Cancellation must stop scheduling new cases and save partial artifacts.

### Security and privacy

- API keys remain backend-only environment variables.
- State data is clearly labeled as leaving the machine when sent to Jev.
- Imported datasets are not transmitted anywhere except the explicitly selected providers.
- Raw responses are stored locally by default.

### Accessibility

- Keyboard navigation for all core workflows.
- WCAG AA contrast targets.
- Charts have text summaries and accessible labels.
- Reduced-motion preferences are respected.
- Color is never the only indicator of correctness or model identity.

## 11. MVP scope

### Must have

- Jev and Laya adapters.
- `choice`, `noul`, and `score` support.
- Bundled demonstration dataset.
- JSONL import and validation.
- Default comparison track.
- Quality, calibration, robustness, and latency metrics.
- Live run view using server-sent events.
- Overview dashboard, robustness view, reliability view, and case explorer.
- Markdown/JSON/JSONL export.
- Professional responsive React design with meaningful motion.

### Should have

- Production-tuned track.
- Risk–coverage curves.
- Repeatability suite.
- Separate throughput test.
- HTML report export.
- Run comparison view.

### Later

- More providers.
- Team collaboration.
- Cloud execution workers.
- Automated human-labeling workflow.
- Dataset version registry.
- Fine-tuning orchestration.

## 12. Success criteria

- A new user can configure and start a bundled evaluation in under three minutes.
- All completed predictions can be traced from a chart to their raw evidence.
- Re-running metric computation over stored predictions produces identical results.
- The UI distinguishes default, calibrated, and fine-tuned configurations everywhere.
- A user can identify at least one workload where each system is preferable.
- No credential appears in browser state, exported reports, or logs.
- The complete demo can be understood in a 30–45 second product video.

## 13. Acceptance scenario

Given a valid Jev credential and an installed Laya checkpoint, the user imports or selects an evaluation set, starts a Default-track comparison, watches both systems process the same cases, opens the final dashboard, finds a disagreement caused by option reordering, examines both probability distributions, changes the acceptable error target on the risk–coverage chart, and exports a report containing the run configuration and limitations.

