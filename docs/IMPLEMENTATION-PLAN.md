# Implementation and Testing Plan

## 1. Delivery strategy

Build a narrow end-to-end path first:

> one valid case → both adapters → normalized predictions → stored artifacts → one comparison screen

Then add metrics, robustness suites, live progress, and visual polish. This avoids creating an impressive dashboard around unverified evaluation logic.

## 2. Milestones

## Milestone 0 — Repository foundation

### Build

- Python and React workspaces.
- Formatting, linting, and test commands.
- Environment example without secrets.
- Shared development commands.
- Basic FastAPI health endpoint.
- React application shell.

### Exit criteria

- Backend and frontend start locally.
- Unit-test commands run in CI without provider access.
- No API key is committed.

## Milestone 1 — Schemas and dataset validation

### Build

- Pydantic `EvaluationCase`, `Question`, `ExpectedAnswer`, and `RunConfiguration`.
- JSONL loader with line-level errors.
- Cross-record validation for unique IDs and family relationships.
- Dataset counts, digest, and preview endpoint.
- Small bundled fixture dataset covering all primitives and variants.

### Tests

- Valid cases for every primitive.
- Wrong expected label.
- Duplicate ID.
- Missing base family.
- Invalid score order.
- Malformed JSONL.
- Sealed-preview restrictions.

### Exit criteria

- Invalid datasets cannot start.
- React displays useful validation messages rather than raw exceptions.

## Milestone 2 — Provider adapters

### Build

- Common `DecisionAdapter` protocol.
- Jev adapter.
- Laya adapter.
- Canonical prediction normalizer.
- Sanitized raw-response storage.
- Readiness and warm-up checks.

### Tests

- Stored response fixtures for Choice, Noul, and Score.
- Probability alignment and sum tolerance.
- Provider confidence versus selected probability.
- Timeout, context-limit, authentication, and normalization failures.
- Laya route/checkpoint metadata.

### Live smoke test

- One case per primitive against each real provider.
- Compare manually with provider-native output.

### Exit criteria

- Both systems produce the same canonical prediction schema.
- A provider failure becomes data, not a crashed run.

## Milestone 3 — Orchestrator and persistence

### Build

- Run creation and state machine.
- Seeded case ordering.
- Warm-up exclusion.
- Append-only prediction, error, and event artifacts.
- Cancellation.
- Partial-run recovery.
- In-memory event bus backed by event JSONL.

### Tests

- Complete run with fake adapters.
- One adapter failing on selected cases.
- Cancellation during execution.
- Restart and run-snapshot reconstruction.
- No duplicate case/system records after recovery.

### Exit criteria

- Completed work survives backend or browser interruption.
- Run totals reconcile.

## Milestone 4 — Metrics engine

### Build

- Choice, Noul, and Score correctness metrics.
- Brier, log loss, ECE, and reliability bins.
- Risk–coverage data.
- Robustness family comparisons.
- Repeatability metrics.
- Latency, throughput, failure, cost, and resource summaries.
- Paired family bootstrap intervals.

### Tests

- Tiny hand-calculated fixtures for every formula.
- Perfect, random, overconfident-wrong, and all-failed systems.
- Invariance families with known flip rates.
- Deterministic rescoring from stored artifacts.
- Missing values remain unavailable rather than becoming zero.

### Exit criteria

- Every summary value has a traceable numerator, denominator, and metric version.

## Milestone 5 — API and live updates

### Build

- Dataset, run, result, chart, case, and export endpoints.
- SSE progress stream with event IDs.
- Reconnect and snapshot refresh.
- OpenAPI contract checks.

### Tests

- Endpoint success and failure paths.
- Pagination and filtering.
- Last-Event-ID replay.
- Sanitization.
- Type generation/compatibility with the React client.

### Exit criteria

- A run can be created, monitored, inspected, and exported through public APIs only.

## Milestone 6 — React workflow

### Build in this order

1. Application shell and design tokens.
2. Overview and readiness.
3. New Evaluation four-step setup.
4. Live Run with SSE.
5. Results overview.
6. Case explorer and evidence drawer.
7. Reliability charts.
8. Robustness view.
9. Methodology and export.

### Animation implementation

- Define shared Framer Motion variants and duration tokens.
- Implement reduced-motion behavior at the same time as each feature.
- Animate progress from actual SSE values.
- Use layout animations for filter and evidence transitions.
- Test chart animation with realistic record counts.

### Tests

- Component states: loading, ready, empty, error, partial, completed.
- Keyboard navigation.
- Filter synchronization across URL, charts, and table.
- SSE reconnect after refresh.
- Reduced motion.
- Screenshot regression for major pages.

### Exit criteria

- The full evaluation process is understandable without logs or documentation.

## Milestone 7 — Evaluation content

### Demonstration set

- 24 reviewed base families.
- Six presentations per family.
- Balanced primitives and representative domains.

### Publishable set

- Expand to 60 base families.
- Independent second review.
- Resolve disagreements.
- Freeze 25% sealed families.
- Record dataset and split digests.
- Lock primary metrics before the final run.

### Exit criteria

- Every case has an explicit evidence or policy path to its expected answer.
- No provider output was used as final ground truth.

## Milestone 8 — Final validation and demo

### Run sequence

1. Offline unit and integration tests.
2. Fake-adapter end-to-end run.
3. Six-case live smoke run.
4. Demonstration run.
5. Freeze versions/configuration.
6. Final publishable run.
7. Verify totals and spot-check disagreements.
8. Export report and reproducibility bundle.

### Demo flow

1. Open readiness dashboard.
2. Select bundled dataset.
3. Review model versions and suites.
4. Start evaluation.
5. Watch Jev and Laya lanes update.
6. Open final summary.
7. Adjust acceptable risk on the risk–coverage chart.
8. Select an option-order failure from the robustness heatmap.
9. Compare both probability distributions in the case explorer.
10. Export the report.

## 3. Same-day prototype plan

A one-day build should use fake adapters for most UI development and a small live dataset.

| Time | Outcome |
|---|---|
| Hour 1 | Repository, schemas, fixture dataset |
| Hours 2–3 | Jev/Laya adapters and canonical result |
| Hours 4–5 | Runner, persistence, core metrics |
| Hour 6 | FastAPI endpoints and SSE |
| Hours 7–9 | React setup, live run, overview, case explorer |
| Hour 10 | Reliability/robustness charts and motion polish |
| Hour 11 | Tests, smoke run, bug fixes |
| Hour 12 | Demo data, screenshots, report, recording |

The 60-family publishable dataset is follow-up evaluation work; it should not be rushed merely to fit the implementation day.

## 4. Test matrix

| Layer | Offline CI | Optional live |
|---|---:|---:|
| Schemas and loader | Yes | No |
| Adapter normalization fixtures | Yes | No |
| Jev connectivity | No | Yes |
| Laya real checkpoint | No | Yes |
| Orchestrator with fake adapters | Yes | No |
| Metric formulas | Yes | No |
| FastAPI endpoints | Yes | No |
| React components | Yes | No |
| Playwright fake run | Yes | No |
| Full real comparison | No | Yes |

## 5. Quality gates

### Code gate

- Format, lint, type-check, and tests pass.
- No secret patterns in tracked files.
- No unpinned provider alias in final-run configuration.

### Data gate

- Dataset validation has zero blocking errors.
- Family/variant counts reconcile.
- Sealed split digest is recorded.

### Evaluation gate

- Comparison integrity checklist passes.
- Default and tuned configurations are distinct.
- Warm-up excluded from warm latency.
- Failure records included in end-to-end metrics.
- Cost assumptions visible.

### UI gate

- Core workflow works at desktop and tablet widths.
- Keyboard smoke test passes.
- Reduced-motion mode works.
- Charts include denominators and textual interpretations.
- Loading, empty, error, partial, and completed states are implemented.

## 6. Risks and mitigations

| Risk | Mitigation |
|---|---|
| No Jev credential | Develop with fixture adapter; block only live Jev run |
| Laya weight download/startup is slow | Readiness check, persistent cache, explicit preload/warm-up phase |
| Local hardware changes results | Record complete environment and never generalize speed beyond it |
| Small dataset creates noisy conclusions | Show counts/CIs, label demo results illustrative, expand before publishing |
| Fine-tuned Laya contaminates comparison | Separate track and system ID; freeze split digests |
| Confidence fields are misinterpreted | Store provider confidence and selected probability separately |
| Provider outage skews failures | Record category/time; use preregistered operational rerun rule |
| UI appears polished but metrics are wrong | Hand-calculated metric fixtures before chart implementation |
| Animation hurts usability | Central motion tokens, reduced-motion mode, performance budget |
| Raw response leaks a key | Header exclusion, recursive redaction, export secret tests |

## 7. Definition of done

### Product

- User can configure, run, understand, inspect, and export a paired evaluation.
- Every evaluation phase is represented in the React UI.
- Conditional conclusions link to supporting evidence.

### Evaluation

- Both systems see equivalent canonical cases.
- All three primitives work.
- Correctness, calibration, automation, robustness, repeatability, performance, cost, and failure metrics are available.
- Raw evidence and reproducibility metadata are retained.

### Engineering

- Offline test suite requires no API key or model download.
- Live smoke tests work when dependencies are available.
- Partial runs are recoverable.
- Reports can be regenerated from artifacts.

### Design

- Interface is professional and responsive.
- Motion is smooth, meaningful, and accessible.
- Case-level evidence is never more than one interaction away from a summary visualization.

