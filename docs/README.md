# DecisionLab

For installation, the implemented workflow, and review/publication gates, see the [project README](../README.md). The documents below retain the original design rationale; [BUILD-LEDGER.md](BUILD-LEDGER.md) records implementation decisions.

DecisionLab is a professional evaluation platform for comparing **Jev** and **Laya** as typed decision systems.

The platform sends the same `choice`, `noul`, and `score` decisions to both systems, stores their complete probability distributions, and explains where each system is accurate, calibrated, stable, fast, and practical to operate.

The product is intentionally not a one-number leaderboard. Its central question is:

> Under which conditions should a developer choose Jev or Laya?

## Core workflow

1. Select an evaluation dataset.
2. Validate its schemas and expected answers.
3. Choose the comparison track and model versions.
4. Warm the systems and run identical decisions.
5. Monitor progress and failures in real time.
6. Calculate correctness, calibration, robustness, automation, latency, cost, and resource metrics.
7. Inspect individual disagreements.
8. Export a reproducible report.

## Comparison tracks

| Track | Jev | Laya | Question answered |
|---|---|---|---|
| Default | Pinned Jev model with standard request configuration | Pinned Laya package using its recommended router and shipped defaults | What does a new developer get out of the box? |
| Production-tuned | Frozen prompts and confidence thresholds selected on a development set | Frozen thresholds, calibration, and optionally a separately identified domain-tuned checkpoint | What is the best deployable configuration after legitimate tuning? |

Results from these tracks must never be merged into one score.

## MVP technology

- Python 3.12 and Node 24
- FastAPI evaluation API
- Jev/TypeSafe Python SDK
- Laya running locally
- Pydantic schemas
- NumPy, SciPy, and scikit-learn metrics
- React + TypeScript + Vite
- Tailwind CSS and Radix accessible components
- Framer Motion
- Recharts, with custom SVG only where required
- JSONL/JSON run artifacts; no database required for the prototype

## Documentation

- [PRD.md](PRD.md) — product requirements, scope, users, flows, and acceptance criteria.
- [TRD.md](TRD.md) — architecture, components, execution model, security, and operations.
- [EVALUATION-SPEC.md](EVALUATION-SPEC.md) — fairness protocol, dataset construction, metrics, and statistical reporting.
- [UI-UX-SPEC.md](UI-UX-SPEC.md) — React information architecture, visual system, charts, interactions, and animations.
- [API-DATA-SPEC.md](API-DATA-SPEC.md) — canonical schemas, REST/SSE endpoints, statuses, and artifact layout.
- [IMPLEMENTATION-PLAN.md](IMPLEMENTATION-PLAN.md) — build order, testing strategy, risks, and definition of done.
- [RESEARCH-BASELINE.md](RESEARCH-BASELINE.md) — verified existing evidence, known limitations, and research sources.

## Prototype boundary

The first version is local and single-user. It does not include authentication, team workspaces, a production database, cloud deployment, or automatic fine-tuning. It must nevertheless preserve raw outputs, versions, configuration, hardware metadata, and scoring rules so every result is auditable.

## Definition of done

The prototype is complete when a user can start one comparison, follow its progress in the React UI, inspect every prediction and metric, understand the tradeoffs between Jev and Laya, and export a reproducible report without reading raw logs.
