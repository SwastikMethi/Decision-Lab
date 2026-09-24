# Animated live comparison

Approved in conversation on 25 September 2026. Base commit: `1e32629`.

## Design contract

- Same question above Jev (left, indigo) and Laya (right, teal).
- Input packet → model → selected option, with probability bars and correctness revealed only after arrival.
- Every scheduled pair participates, including repeats and batches. Pair by case, suite, repetition, concurrency and batch size. A batch is one representative answer marked ×N.
- Readable automatic playback, pause/play, previous/next, 1×/2×/4× and jump to latest. Evaluation proceeds independently; recorded timing remains distinct from animation timing.
- Compact run progress and model counts; activity behind Details. Preserve cancel, warnings, simulation labeling, and Results access.
- Choice labels, Noul Yes/No, ordered Score levels; large answer spaces scroll. Mobile stacks the panels. Dark mode, keyboard controls, and reduced motion retain all information.
- Persist position/preferences per run in session storage. Use saved predictions; never call a model to replay.
- Failed calls and terminal missing outcomes have explicit states. Sealed frames are opaque and skipped until released.
- Typed, cursor-paginated read-only playback endpoint. Inspect selects the exact displayed evaluation IDs.

## Implementation sequence

### Task 1: Saved-evidence playback contract

1. Write API tests for pairing, pagination, partial/missing states, Choice/Noul/Score, sealed data and read-only behavior.
2. Run `.venv/bin/python -m pytest -q backend/tests/test_playback.py`; expected: new endpoint tests fail.
3. Implement a compact projection from schedule, cases and predictions, with typed response and bounded pagination. Generate OpenAPI and frontend types.
4. Re-run API tests; expected: all pass.

### Task 2: Paired visual playback

1. Write timing/interaction tests that prove verdict follows packet arrival, pause freezes playback, late results wait, and failures/reduced motion are explicit.
2. Run frontend tests; expected: new component tests fail before implementation.
3. Implement diagrams and controls with existing React/Motion/SVG. Connect coalesced SSE updates and exact-prediction inspection. Keep current/adjacent pages only.
4. Re-run unit tests and TypeScript; expected: all pass.

### Task 3: End-to-end verification

1. Exercise live simulation, backlog after completion, refresh, every primitive, batches, errors, 100 options, mobile/dark/reduced-motion and accessibility.
2. Inspect browser screenshots. Run backend/unit/browser suites, lint, format, types/build and contract drift checks.
3. One fresh code review of the complete change; fix Important findings with reproducing tests. Record evidence below.

## Interface preflight

- Existing events carry case/system/suite but not answer bodies or unique repeat IDs. The playback endpoint derives pairs from the immutable schedule and predictions instead of changing provider execution.
- Existing case comparisons select primary predictions. The evidence drawer must explicitly select frame evaluation IDs from `all_predictions`.
- Existing correctness is false for missing predictions. Playback uses a separate nullable correctness contract so pending or missing results are not presented as wrong model answers.

## Decisions and progress

- Ruling: retain the clean `feat/decisionlab` workspace — it is the existing implementation branch and the user's local app workspace — cost if wrong: unrelated development must be isolated before it begins.
- Palette/type remain the app's Inter/slate, indigo and teal. The paired flow is the dominant visual; avoid extra decorative cards or constant background motion.
- Task 1: complete. New endpoint tests failed with 404 before implementation; 4 projection tests now pass, and the full backend suite passed 57 tests. Mypy passes for 15 modules. OpenAPI and TypeScript contracts regenerated.
- Task 2: complete. Frontend timing tests failed before the component existed; all 6 frontend tests now pass. Browser checks found and reproduced a shared CSS background collision, a failed-response answer highlight, and final-frame pause/resume issues; fixes are covered by the timing/accessibility/browser checks.
- Task 3: complete. Final suites pass: 57 backend, 6 frontend, 7 browser scenarios. These include the original evaluation workflow, desktop/dark mode, exact batch evidence, mobile 100-option lists, reduced motion, failed responses, sealed placeholders and the review regressions below. Packet-in-flight, desktop, mobile and dark screenshots inspected. Production build, Ruff, formatting, Mypy and runtime OpenAPI contract checks pass.
- Ruling: browser tests use ports 5183/8778 and one worker — the user's app and another project occupy the original ports, and the backend permits one active evaluation — cost if wrong: only the test-port configuration needs adjustment.
- The Vite proxy preserves the browser's Host header, so local origin checks work on either development or isolated test ports without loosening backend validation.
- One requestAnimationFrame clock controls packets, bars and verdict timing. A second interpolation clock was removed after a browser test showed movement after Pause.

## Final review

A fresh read-only reviewer reviewed `1e32629..987356a`. Three Important findings, no Critical or Minor findings, and no declined judgments. All three fixed in one pass:

- Final: fixed stale pending inspection — browser regression first showed missing results labeled as incorrect, then passed after the shared drawer polled pending evidence and refreshed on terminal status. Pending, failed and terminal missing outcomes now have distinct labels.
- Final: fixed backward navigation across sealed comparisons — browser regression first remained at comparison 23 instead of 19; it now crosses sealed intervals and page boundaries in both directions.
- Final: fixed selected-answer accessibility — timing regression first could not find the selected answer; the verdict now names the selected label for screen readers, only after arrival.
- Each regression was observed failing before its fix; final suite 57/57 backend, 6/6 frontend, 7/7 browser. No additional provider calls were made.
