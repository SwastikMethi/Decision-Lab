# Customer support benchmark results

This is an exploratory live run of the `full` DecisionLab profile against Jev and Laya. Jev led both comparisons on this dataset. The paired accuracy difference was 41.7 percentage points, with a family-bootstrap 95% confidence interval of 16.7 to 66.7 points.

## Dataset and method

- 24 synthetic customer-support cases across 12 semantic families.
- 12 development cases were used for calibration; 12 sealed evaluation cases were used for comparison.
- Choice, Noul, and Score each contributed four development and four evaluation cases. Every family has a base and paraphrase case.
- The evaluation answers were reviewed by `Codex AI reviewer — not an independent human`. This run is marked `publication: false` and is not an independently reviewed benchmark.
- The live run completed 1,008 scheduled requests and 9,936 logical questions, plus 18 warm-up requests. It exercised quality, calibration, paraphrase robustness, five-call repeatability, load, context-length, and option-cardinality suites.

## Primary KPIs

| Track | System | Accuracy | Macro F1 | Brier | ECE | Primary failures | p50 latency | p95 latency |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Default | Jev | 100.0% | 1.000 | 0.0013 | 0.0175 | 0/12 | 314 ms | 985 ms |
| Default | Laya | 58.3% | 0.833 | 0.2171 | 0.1612 | 2/12 | 44 ms | 57 ms |
| Production tuned | Jev | 100.0% | 1.000 | <0.0001 | <0.0001 | 0/12 | 329 ms | 377 ms |
| Production tuned | Laya | 58.3% | 0.833 | 0.3000 | 0.3000 | 2/12 | 45 ms | 55 ms |

Macro F1 is the mean across compatible Choice label spaces; accuracy covers all 12 primary evaluation cases.

Both tracks selected Jev. Tuning left accuracy unchanged. It improved Jev's calibration on this split, while Laya's Brier score and ECE became worse.

## What the diagnostic suites found

- Jev scored 100% in every context-length and option-cardinality bucket, with no failures across either 246-request evaluation run.
- Laya scored 83.3% at the 1,024-token context bucket and 66.7% at 4,096 and 16,384 tokens. Its 10-, 50-, and 75-option buckets scored 0% and contained normalization failures.
- Jev had no answer flips across base/paraphrase pairs. Laya flipped one Noul answer in both tracks; some Choice and Score pairs were not comparable because one side failed.
- All valid repeatability samples had complete modal agreement. Two Laya cases produced no valid outputs across their five repeats.
- Jev's highest observed load throughput was 691.2 logical questions/s on default and 766.4 on production tuned, with no failures. Laya peaked at 75.7 and 80.1 logical questions/s and still produced failures. These measurements describe this machine and configuration only.

## Frozen policy

The tuned Jev policy accepted 10 of 12 evaluation cases with no accepted errors: 83.3% coverage and 0% observed risk. The tuned Laya policy accepted 5 of 12 with one accepted error: 41.7% coverage and 20% observed risk. Both policies are flagged unstable because calibration used only two development families per primitive.

## Cost evidence

Recorded Jev usage implies an estimated API cost of **$0.02568048** for development, both evaluation tracks, and their warm-ups. This is an estimate from recorded tokens and the configured rate, not provider-reported billing. Laya cost is unavailable because no local hourly cost was configured. Failed attempts without usage records may add cost.

## Reproducibility

- Workflow: `01a0edc3-58bd-71d4-9a4d-3ea0ee4c1d51`
- Protocol: `01a0edd1-2189-7270-8a9a-a575cb8663f1`
- Calibration: `01a0edc3-58bd-71d4-9a4d-3ea0ee4c1d51-calibration`
- Evaluation digest: `sha256:6590eee0f179d59c27467583c2ce07d7b77b5d9c5fb96015a90fbd4be9bdd974`
- Jev model: `jev-1.13.0`
- Laya package: `0.3.20`; checkpoint revision: `55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851`

The machine-readable output in `result.json` contains every KPI, diagnostic bucket, repeatability sample, load point, cost field, and frozen-policy result. These findings apply only to this small synthetic dataset and frozen configuration; they do not establish a universal model ranking.
