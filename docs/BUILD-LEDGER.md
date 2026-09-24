# DecisionLab implementation ledger

Plan: approved end-to-end implementation from the 24 September 2026 conversation.

## Accepted requirements

- Full local product and publishable benchmark workflow; human review gates publication.
- Separate 24-family development and 60-family evaluation sets; six presentations each.
- Fifteen evaluation families sealed; both tracks frozen before evaluation.
- Noul/Score replace Choice-only transformations with second paraphrase and state-key order.
- Immutable predictions; pure scoring; no provider calls during rescoring.
- Real Jev and pinned local Laya, plus explicitly labeled offline simulation.

## Sequence and status

1. Foundation and contracts: complete; Python 3.12, Node 24 target, dependency locks, CI, generated API request types.
2. Dataset lifecycle and benchmark content: complete; 144 development / 360 evaluation presentations, draft review status.
3. Provider adapters: complete; pinned Laya smoke passed on CPU and MPS for all three primitives. Jev live verification awaits a credential.
4. Durable runner and SSE: complete; paired execution, retries, cancellation, single-writer ownership, replay and crash recovery.
5. Metrics, calibration, protocols and reports: complete; pure scoring, frozen development thresholds, artifact signatures, review gate and sealed release.
6. API and React workspace: complete; setup/live/results/reliability/robustness/cases/methodology, evidence drawer and exports.
7. Verification and final review: complete; fresh independent code review, one corrective pass, and green offline/browser checks. Live Jev validation and independently reviewed publication data remain external prerequisites.

## Decisions

- Ruling: use the newly initialized feature branch in the user's empty workspace; there is no existing application branch to isolate. No unrelated work is present. Cost if wrong: branch isolation must be added before unrelated work begins.
- Runtime target is Python 3.12 / Node 24; the machine's global Python 3.14 is not used.
- Publication requires imported independent human reviews; generated policy labels remain provisional.
- Core numeric processing uses NumPy/SciPy/scikit-learn; no pandas dependency is needed for JSONL and grouped metrics.
- Performance batches are explicitly shared-state question batches, supported by both providers, rather than silently comparing independent-state batches with shared-state requests.

## Verification

- Initial schema/metric/runtime tests failed because implementation was absent.
- Backend: complete 288-prediction simulation; formula, missing/failure denominator, drift alignment, cancellation, replay, calibration isolation, sealed release, 10,000-case pagination, safe HTML and ZIP checksum checks.
- Pinned Laya 0.3.20 and checkpoint 55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851 (2.37 GB).
- Frontend risk-control and status checks written before components; OpenAPI-generated request types. Browser workflow and mobile accessibility passed with all axe rules, including contrast, enabled.
- Real MPS validation: Choice/Noul/Score returned normalized distributions from revision `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`; warm inference approximately 32–36 ms for these smoke cases only. This is not a comparative benchmark.
- CI follows the official [setup-node](https://github.com/actions/setup-node) and [setup-uv](https://github.com/astral-sh/setup-uv) action contracts, with Python/Node versions and dependency locks explicit.

Final local checks on 24 September 2026:

| Check | Result |
|---|---|
| `python -m pytest -q` | 53 passed; includes 15 review regression cases |
| Ruff lint / format | Passed; 21 Python files formatted |
| Mypy | Passed; 14 application modules |
| Prettier | Passed |
| `npm test` | 2 passed |
| TypeScript / production build | Passed |
| OpenAPI and TypeScript regeneration | Byte-identical artifacts; no contract drift |
| Playwright | 3 passed: full simulated workflow, mobile/reduced motion, custom dataset |
| Axe | No violations in tested views; all rules, including contrast, enabled |
| Visual inspection | Results, reliability, robustness, methodology, and dark results screenshots checked |
| Real local inference | CPU and MPS smoke passed for Choice, Noul, Score |

The complete simulation schedules 144 development presentations for each provider and retains all 288 predictions. Browser verification includes refresh/reconnection, evidence/raw response inspection, export download, custom domain filtering, absent primitive handling, and desktop/mobile layouts. Local checks used Python 3.12 and Node 25.2.1; Node 24 is the declared CI/runtime target. The workflow is configured but has not run on a remote CI service.

## Final review and fixes

One fresh-context reviewer inspected the whole implementation. Six Important findings were accepted. Two findings initially called Minor were regraded Important: a missing primitive displayed as 0% misstates the result, and an unavailable custom domain filter prevents a supported workflow. All eight were fixed in the same corrective pass; no deferred minor findings remain.

| Finding | Correction and evidence |
|---|---|
| Sibling lane continued after another lane failed | Runner owns, cancels, and awaits every child task. `test_lane_exception_cancels_and_awaits_siblings` RED→GREEN. |
| Credential-like outcome names were redacted | Preserve semantic dictionary keys, redact credential values and bearer tokens, and hash the retained request. `test_sensitive_looking_label_keys_survive_persistence` RED→GREEN; known credential values also checked. |
| Jev SDK exceptions were misclassified | Use installed SDK `status`, `headers`, `body`, validation exception, and HTTP transport exceptions. `test_jev_uses_actual_sdk_error_contract` RED→GREEN across six cases. |
| Malformed optional metadata could abort a run | Guard envelopes and numeric telemetry; retain raw evidence and per-decision failures. `test_malformed_envelopes_are_retained_per_decision` RED→GREEN across five cases. |
| Cardinality diagnostic always placed gold first | Seed and shuffle option order while retaining gold. `test_cardinality_diagnostic_does_not_put_every_gold_first` RED→GREEN. |
| Refreezing could make an evaluation rerun publishable | Check prior live evaluations across protocols, including previously frozen alternatives; reruns remain exploratory. `test_new_protocol_cannot_make_seen_evaluation_publishable` RED→GREEN. |
| Missing primitives plotted as zero | Chart only observed primitives and preserve unavailable values. Custom Choice-only browser regression passes. |
| Custom domains could not be selected | Derive filter choices from the complete run snapshot. Custom `legal_help` browser regression passes. |

All 15 backend review regressions failed before their fixes and passed afterward; the full backend suite passed 53/53. Browser checks also exposed invalid loading semantics, insufficient contrast, and a transient theme-switch contrast failure. Loading has a status role, text uses readable theme colors, and buttons no longer animate backgrounds across theme changes. Final browser suite: 3/3.

## Final rulings

- Final: Ruling: live Jev connectivity, billing, and returned version remain unverified — no credential is configured; keep the explicit live gate and tested SDK contract, and make no live comparative claim — cost if wrong: a credentialed development smoke may expose provider/account integration changes before evaluation.
- Final: Ruling: local Laya hardware evidence is limited to the exercised CPU/MPS smoke cases — the actual pinned runtime passed all primitives and records its device, but smoke timings do not establish comparative performance or cross-device equivalence — cost if wrong: a full workload may require different runtime settings or yield different latency.
- Final: Ruling: human label correctness and reviewer independence remain external attestations — generated policy labels stay draft and publication requires imported reviews/adjudication — cost if wrong: unreliable labels would invalidate a published benchmark; the gate prevents treating current drafts as reviewed.
- Final: Ruling: sealing is procedural within a local single-user workspace — APIs withhold sealed outcomes until both tracks complete; filesystem access and blind review packets are intentionally outside that boundary — cost if wrong: a user can manually inspect cases, so hostile-user or examination use would require a separate access-controlled service.
- Final: Ruling: visual/accessibility acceptance rests on the actual browser checks and screenshots — desktop analysis, dark mode, mobile setup and reduced motion were exercised with all axe rules — cost if wrong: untested browser/assistive-technology combinations may need follow-up adjustments.
- Final: Ruling: production deployment security is outside the accepted local scope — keep loopback binding, origin/host checks and a single writer; no cloud deployment or authentication is introduced — cost if wrong: shared hosting requires a separate authentication and deployment design before use.
- Final: Ruling: preserve `feat/decisionlab` in this new local repository — there is no base branch or remote integration target, and implementation does not require a push — cost if wrong: choose an integration target when the repository is shared.

## Review focus

Review the complete local application against the original specs and accepted requirements above. Prioritize canonical request parity, failures versus missing outcomes, cancellation/worker lifetimes, retry accounting, hidden SDK retries, snapshot/protocol integrity, leakage through sealed result endpoints, development-only calibration, family-aligned uncertainty, and misleading UI/report metrics. Check malformed provider results and custom datasets as well as bundled policy examples. Real Jev connectivity is unverified without a credential; the reviewer should inspect that adapter but should not make paid calls. The independent human review and final publishable evaluation are deliberately gated, not invented by the implementation.

## Design

Follow UI-UX-SPEC: Inter, slate text, near-white canvas, indigo Jev and teal Laya; compact left navigation and shared evidence drawer. Analysis uses wide charts and dense evidence rows rather than repeated decorative cards. Light/dark and reduced motion remain equivalent workflows.

## Interface preflight

- Dataset IDs resolve only under managed storage; runs snapshot digest-verified cases.
- Each evaluation ID identifies run/system/case/suite/repetition, independent of retries.
- Metric and case APIs share filters and derive correctness from immutable predictions.
- Protocol digest binds dataset and both tracks; calibration accepts development only.
