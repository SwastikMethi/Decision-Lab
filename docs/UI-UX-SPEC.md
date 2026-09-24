# React UI and UX Specification

## 1. Experience goal

The interface should make a technically serious evaluation feel clear, calm, and inspectable.

The visual impression is **professional analysis workspace**, not gaming dashboard or marketing landing page. Motion should help users follow execution, compare changing values, and understand relationships between a summary and its evidence.

## 2. Frontend stack

- React 18+
- TypeScript
- Vite
- React Router
- Tailwind CSS
- shadcn/ui primitives
- Framer Motion
- TanStack Query
- TanStack Table
- Recharts
- Lucide icons
- Vitest, React Testing Library, and Playwright

## 3. Information architecture

### Main navigation

1. **Overview** — recent evaluations and system readiness.
2. **New Evaluation** — dataset, track, suites, and final review.
3. **Live Run** — real-time execution and failures.
4. **Results** — executive comparison and conditional findings.
5. **Reliability** — calibration and safe automation.
6. **Robustness** — variant sensitivity and failure patterns.
7. **Cases** — searchable case-level evidence.
8. **Methodology** — dataset, versions, scoring, and limitations.

The selected run is persistent across result pages. Run ID and important filters should be represented in the URL.

## 4. Application shell

### Desktop

- Collapsible left navigation: 248 px expanded, 72 px collapsed.
- Top bar with run selector, track badge, run status, and export button.
- Main content maximum width around 1600 px with responsive gutters.
- Optional right-side evidence drawer for case details without leaving a chart.

### Tablet and mobile

- Navigation becomes a sheet.
- Charts stack vertically.
- Comparison tables switch to paired cards when horizontal space is insufficient.
- The case explorer retains filtering and evidence access; no core feature is desktop-only.

## 5. Visual language

### Tone

- Clean, analytical, restrained.
- Strong typography and spacing.
- Soft depth rather than glossy effects.
- Data is visually dominant.

### Color system

| Role | Suggested color |
|---|---|
| Jev | Indigo `#6366F1` |
| Laya | Teal `#14B8A6` |
| Correct | Emerald `#22C55E` |
| Warning | Amber `#F59E0B` |
| Incorrect/error | Rose `#F43F5E` |
| Neutral information | Slate scale |
| Selection/focus | Sky `#0EA5E9` |

Model colors remain consistent across every chart. Correctness is also represented by icon, text, or pattern so color does not carry meaning alone.

### Surfaces

- Light mode: near-white canvas with white elevated cards and slate borders.
- Dark mode: deep slate canvas, not pure black.
- Border radius: 12–16 px for panels; 8–10 px for controls.
- Shadows are subtle and reserved for floating layers or focused comparison cards.

### Typography

- Interface: Inter or Geist Sans.
- Numbers: tabular numerals.
- Raw JSON/code: Geist Mono or JetBrains Mono.
- Page title: 28–32 px.
- Section title: 18–22 px.
- Body: 14–16 px.

## 6. Motion system

### Principles

1. Motion explains origin, destination, progress, or change.
2. Evaluation data never bounces or moves continuously after settling.
3. Live progress reflects real backend events; no fake completion animation.
4. Motion is short enough to keep analysis fast.
5. `prefers-reduced-motion` disables non-essential movement.

### Timing tokens

| Motion | Duration | Easing |
|---|---:|---|
| Hover/focus response | 120–160 ms | ease-out |
| Tooltip/popover | 140–180 ms | ease-out |
| Panel expand/collapse | 200–240 ms | ease-in-out |
| Page transition | 220–280 ms | ease-out |
| Chart/value update | 300–450 ms | gentle ease-out |
| First dashboard reveal | 450–600 ms total stagger | ease-out |

### Required animations

#### Page transitions

- New page fades from 0 to 1 and moves upward 8 px.
- Previous page does not slide dramatically off-screen.

#### Setup stepper

- Active step underline smoothly moves between steps.
- Completed step changes to a check with a short scale transition.
- Validation errors shake only the affected field by 2–3 px once; never loop.

#### Live run

- Overall progress bar uses a smooth spring toward actual completion.
- Current phase has a restrained animated indicator.
- Completed cases enter the activity list with a short fade/height transition.
- Jev and Laya lanes advance independently.
- A failure produces a one-time color and icon transition, not a flashing alert.

#### Metric cards

- Values interpolate only when changing from provisional to final or when filters change.
- The previous value remains accessible to screen readers through descriptive text.
- Positive or negative deltas briefly reveal beside the value, then remain static.

#### Probability comparison

- Bars grow horizontally from zero on first reveal.
- Changing the selected case morphs bar widths and crossfades labels.
- Expected-answer marker remains anchored and does not animate ambiguously.

#### Charts

- Series reveal in a consistent Jev-then-Laya order.
- Filters morph existing marks when possible instead of destroying/recreating the chart.
- Hovering one system dims, but does not hide, the other.
- Selection in a chart animates the evidence drawer from the right.

#### Reduced motion

- Replace transforms with short opacity changes.
- Disable number interpolation and chart drawing animations.
- Keep real progress updates and state changes visible.

### Avoid

- Confetti.
- Neon glows.
- Infinite pulsing after a run completes.
- Animated gradients behind data.
- Three-dimensional charts.
- Motion that implies one model is winning before final scoring.

## 7. Screen specifications

## 7.1 Overview

### Purpose

Orient the user and make readiness obvious.

### Sections

- Header: “DecisionLab” and one-sentence product purpose.
- Readiness strip: Jev credential, Laya checkpoint, local device, dataset availability.
- Primary action: **New Evaluation**.
- Recent-run table: status, track, systems, dataset, date, completion, and key result.
- Small methodology note: no universal winner; results are configuration-specific.

### Empty state

Show a compact explanation and a button to run the bundled demonstration dataset.

## 7.2 New Evaluation

Use a four-step flow.

### Step 1: Dataset

- Bundled dataset cards.
- Drag-and-drop JSONL import.
- Validation summary with counts by primitive, domain, split, and variant.
- Expandable line-level errors.

### Step 2: Systems

- Track selection: Default or Production-tuned.
- Jev model/version and readiness.
- Laya mode, checkpoint, device, and readiness.
- Visible “comparison integrity” warnings.

### Step 3: Suites

- Quality.
- Calibration.
- Robustness.
- Repeatability.
- Performance.
- Estimated calls, approximate runtime, and cost basis.

### Step 4: Review

- Immutable summary of dataset digest, versions, track, suites, seed, and output location.
- Disclosure that Jev-bound state leaves the local machine.
- Start button.

## 7.3 Live Run

### Header

- Run name and ID.
- Track and dataset.
- Elapsed time.
- Cancel action.

### Phase timeline

`Validating → Warming → Running → Scoring → Completed`

### Paired lanes

Two equally weighted cards:

- completed/total;
- current suite;
- recent latency;
- retries/failures;
- active checkpoint/model;
- provisional accuracy clearly labeled.

### Activity timeline

Shows structured events with filters for system, phase, and error.

### Failure behavior

Errors appear inline and in a summary card. The screen does not automatically navigate away.

## 7.4 Results overview

### Executive summary

Start with conditional findings rather than a winner banner. Example:

- “Jev led on high-cardinality Choice cases.”
- “Laya produced lower warm local latency on this machine.”
- “At ≤2% observed risk, Jev automated X% and Laya Y%.”

Every statement links to supporting filters.

### KPI cards

- End-to-end correctness.
- Brier score.
- Coverage at selected risk.
- Warm p50 latency.
- Cost per 1,000 decisions.
- Failure rate.

Cards show both systems, denominator, difference, and confidence interval where applicable.

### Main visualizations

- Accuracy by primitive: grouped horizontal bars.
- Quality versus latency: scatter plot.
- Domain comparison: heatmap.
- Operational comparison: concise table.

### Track banner

Default and Production-tuned results use an always-visible badge. Fine-tuned checkpoint results include a prominent label.

## 7.5 Reliability

### Calibration chart

- Reliability line against perfect-calibration diagonal.
- Sample count visible per bin.
- Toggle between primitive and system.

### Risk–coverage chart

- Shared axes and two model lines.
- User enters acceptable observed risk, such as 2%.
- Intersection values update in a summary card.
- Small-sample regions are shaded or marked uncertain.

### Confidence distribution

- Correct and incorrect distributions displayed separately.
- Tooltip includes count, mean confidence, and error rate.

### Threshold table

Rows for 0.60, 0.70, 0.80, and 0.90 showing coverage, risk, accepted count, and escalations.

## 7.6 Robustness

### Transformation heatmap

Rows are transformation types; columns are systems and primitives. Cells show harmful-flip rate or accuracy delta.

### Family explorer

- Base case at the top.
- Variants shown as connected cards below.
- Each card displays answer, correctness, and probability shift.
- Selecting a card opens full evidence.

### Sensitivity cards

- Option-order sensitivity.
- Opaque-label sensitivity.
- Distractor degradation.
- Adversarial-state degradation.
- Context-length curve.
- Option-cardinality curve.

## 7.7 Case explorer

### Table columns

- case/family ID;
- domain;
- primitive;
- variant;
- expected answer;
- Jev answer and correctness;
- Laya answer and correctness;
- confidence/probability;
- latency;
- disagreement indicator.

### Filters

- correctness combination;
- disagreement;
- domain;
- primitive;
- variant;
- confidence range;
- failure type;
- text search.

### Evidence drawer

Tabs:

1. **Decision:** state, question, criteria, expected answer.
2. **Probabilities:** aligned comparison bars.
3. **Raw:** sanitized provider responses.
4. **Family:** base and sibling variants.
5. **Metadata:** model version, checkpoint, route, latency, retry, and cost.

Provide next/previous disagreement controls for rapid review.

## 7.8 Methodology

Display:

- comparison track;
- systems and versions;
- dataset composition and digest;
- ground-truth process;
- suites and transformations;
- metric definitions;
- hardware/environment;
- cost assumptions;
- warnings, exclusions, and limitations;
- scoring code version.

This page is included in exports.

## 8. Chart standards

- All axes start from a defensible baseline; accuracy bars normally start at zero.
- Tooltips show raw counts and denominators.
- Differences include direction and unit.
- Lower-is-better metrics are labeled explicitly.
- Missing values are shown as “Unavailable,” not zero.
- Failure counts remain visible beside answered-only metrics.
- Comparison filters apply consistently across cards, charts, and cases.
- Every chart has an adjacent concise text interpretation.

## 9. Loading, empty, and error states

### Loading

- Use skeletons matching final layout.
- Do not use full-page spinners after the application shell loads.
- Long chart calculations show a local progress state without blocking navigation.

### Empty

Explain why no data exists and provide the next action, such as removing a filter.

### Error

Show:

- what failed;
- whether stored data is safe;
- whether retry is appropriate;
- a compact technical detail expander;
- recovery action.

## 10. Accessibility

- Visible focus rings.
- Full keyboard operation of dialogs, tabs, tables, and drawers.
- Skip-to-content link.
- Semantic headings and landmarks.
- Chart summaries exposed as text.
- Patterns/icons accompany color states.
- Minimum 44 px touch targets on compact layouts.
- Reduced-motion implementation tested in Playwright.

## 11. Responsive breakpoints

- `<640 px`: single-column compact layout.
- `640–1024 px`: stacked analysis panels, compact navigation.
- `>1024 px`: full navigation and paired layouts.
- `>1440 px`: wider multi-chart grids and optional evidence drawer.

## 12. Frontend acceptance criteria

- A user can complete the full workflow without opening developer tools.
- Every summary can be traced to cases or methodology.
- Live progress survives a browser refresh.
- Model identity and comparison track remain visible on all result screens.
- Animations remain smooth on a typical laptop and never delay interaction.
- Reduced-motion mode retains all information.
- No secret or raw authorization data appears in browser network responses.
- Core pages pass automated accessibility checks and keyboard smoke tests.

