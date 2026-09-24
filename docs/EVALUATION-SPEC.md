# Evaluation Methodology Specification

## 1. Purpose

This document defines how DecisionLab produces a fair, reproducible, and useful Jev-versus-Laya comparison.

It is the scoring authority for the project. UI labels and reports must follow these definitions.

## 2. What “generic comparison” means

No finite benchmark proves that one system is universally better. In this project, **generic** means:

- multiple realistic domains;
- all three shared decision primitives;
- small and large answer spaces;
- short and long state;
- clear, ambiguous, and unsupported cases;
- ordinary and adversarial variants;
- quality, confidence, speed, cost, and operational measurements;
- conclusions stated by workload rather than as one universal winner.

## 3. Comparison tracks

### Track A: Default

Purpose: measure what a developer receives with minimal setup.

| System | Configuration |
|---|---|
| Jev | Pinned versioned model, standard request path, no evaluation-derived prompt changes |
| Laya | Pinned package and checkpoint revisions, recommended Router, shipped calibration, no evaluation-derived fine-tuning |

### Track B: Production-tuned

Purpose: measure legitimate improvements selected only from a development split.

Allowed:

- clearer instructions that remain semantically equivalent for both systems;
- confidence thresholds fitted on development data;
- declared temperature calibration;
- a Laya domain-tuned checkpoint trained without sealed cases;
- context or option-budget settings selected before sealed evaluation.

Not allowed:

- inspecting sealed labels while tuning;
- using different task meaning for each system;
- selecting the better result per case;
- replacing failures after results are known;
- presenting Track B as the default model comparison.

Every tuned configuration is treated as a separate system row, for example `laya-router-default` and `laya-domain-tuned`.

## 4. Dataset composition

### 4.1 Prototype dataset

For product development and demos:

- 24 base families;
- 8 `choice`, 8 `noul`, and 8 `score`;
- six presentations per family;
- 144 case presentations.

These results are illustrative and must not be presented as a definitive model comparison.

### 4.2 Publishable evaluation target

- 60 base families;
- 20 per primitive;
- six presentations per family;
- 360 primary case presentations;
- 25% of base families held sealed until final execution.

Domains are balanced as closely as practical:

| Domain | Example decisions |
|---|---|
| Customer support | Intent, department, urgency, refund request |
| Safety and moderation | Violation category, severity, human review |
| Operations | Incident class, impact, escalation |
| Agent guardrails | Tool safety, approval requirement, action route |

The platform must display actual counts rather than assuming perfect balance.

## 5. Case-family design

Each family represents one semantic decision and contains:

1. **Base:** concise canonical case.
2. **Paraphrase:** same facts and intent, different wording.
3. **Option order:** criteria inserted in a different order.
4. **Opaque labels:** semantic keys replaced by `A`, `B`, `C`, while descriptions preserve meaning.
5. **Distractor:** irrelevant but realistic fields or text added.
6. **Adversarial state:** state includes text attempting to influence the evaluator, while the requested judgment remains unchanged.

Additional diagnostic suites may vary context length and option count, but their altered difficulty must be reported separately rather than treated as invariance.

Every variant records:

- `family_id`;
- transformation type;
- expected invariant or expected change;
- source/reviewer;
- validation status.

## 6. Ground truth

### 6.1 Preferred construction

Use explicit policies or constructed facts that deterministically imply the answer. Example: a routing policy states that duplicate charges go to Billing, and the case contains a duplicate charge.

### 6.2 Review process

- Author creates the case and expected answer.
- A second reviewer independently answers from the supplied policy.
- Disagreement is adjudicated before evaluation.
- Cases whose answer depends on unstated knowledge are rewritten or marked ambiguous.

### 6.3 Ambiguity

Ambiguous cases are valuable but must be intentional. They should include an `other`, `unknown`, `insufficient_information`, or review option when that is the desired action.

If soft human distributions are collected, they are reported separately from hard-label accuracy.

### 6.4 Prohibited labeling

Do not use Jev, Laya, or another single model as the authoritative gold label.

## 7. Primitive-specific interpretation

### Choice

- Expected value is one key from the supplied criteria.
- All criteria are mutually exclusive unless the case explicitly tests ambiguity.
- Probability distribution must cover exactly the evaluated options after normalization.

### Noul

- Expected value is `true` or `false`.
- Canonical distribution is `{false: 1-p, true: p}`.
- Default classification threshold is `0.5`; operational threshold analysis is separate.

### Score

- Criteria are ordered from lowest to highest.
- Expected value is an ordinal level index.
- If the provider returns a continuous expected score, exact-level accuracy uses the highest-probability level while ordinal error uses the expected score where valid.

## 8. Evaluation suites

### 8.1 Correctness

Runs every primary case once per system and reports by primitive, domain, and difficulty bucket.

### 8.2 Calibration

Uses the probability assigned to the correct outcome. Calibration is computed globally and by major subgroup when sample size is sufficient.

Post-hoc calibration may be shown only in Track B and must be fitted on development data.

### 8.3 Robustness

Compares each transformed variant with its base family. The suite measures whether answer and probability change without a semantic reason.

### 8.4 Repeatability

- Stratified sample of 30 presentations when available.
- Five fresh calls per system by default.
- Measures answer flips and probability variation.
- Repeated calls are excluded from ordinary accuracy totals to prevent weighting those cases more heavily.

### 8.5 Context-length diagnostic

Adds controlled irrelevant content at configured size buckets. This is a degradation curve, not an invariance score once truncation occurs.

### 8.6 Option-cardinality diagnostic

Uses comparable tasks with 2, 4, 10, 20, 50, and 75 options where feasible. Reports effective context/option settings and failures.

### 8.7 Performance

Measured separately from quality:

- cold start;
- warm single-case p50/p95/p99;
- batches of 1, 5, 10, and 50 questions when supported;
- concurrency 1, 4, and 8 for an explicit load test;
- sustained throughput;
- failure/rate-limit rate.

Local and remote times are labeled differently. Jev is end-to-end API latency. Laya reports local end-to-end latency and, where obtainable, model inference time.

## 9. Metrics

### 9.1 Correctness

| Primitive | Primary metrics |
|---|---|
| Choice | Accuracy, macro-F1, negative log loss, multiclass Brier score |
| Noul | Accuracy at 0.5, Brier score, log loss, AUROC when both classes are sufficiently represented |
| Score | Exact-level accuracy, ordinal mean absolute error, ranked probability score |

Invalid, failed, or missing outputs count as incorrect in end-to-end correctness. A second “answered-only” view may be shown but cannot replace end-to-end results.

### 9.2 Calibration

Report:

- expected calibration error with configured bins;
- Brier score;
- log loss;
- reliability diagram;
- sample count per bin;
- pre- and post-calibration results separately.

ECE is descriptive and depends on binning. It is never the only calibration result.

### 9.3 Selective automation

For threshold `t`:

- **coverage:** share of predictions accepted automatically;
- **selective risk:** error rate among accepted predictions;
- **escalation rate:** `1 - coverage`;
- **automation accuracy:** accuracy among accepted predictions.

Report the complete risk–coverage curve and these practical operating points:

- maximum coverage at or below 1% observed risk;
- maximum coverage at or below 2% observed risk;
- results at confidence thresholds 0.60, 0.70, 0.80, and 0.90.

An operating point with too few samples is visibly marked unstable.

### 9.4 Robustness

- **answer-flip rate:** transformed cases whose selected outcome differs from the base;
- **harmful-flip rate:** correct base becomes incorrect variant;
- **beneficial-flip rate:** incorrect base becomes correct variant;
- **probability drift:** Jensen–Shannon divergence between aligned probability distributions;
- **accuracy delta:** transformed accuracy minus base accuracy;
- **option-order sensitivity:** metrics limited to option-order variants;
- **label sensitivity:** metrics limited to opaque-label variants.

### 9.5 Repeatability

- modal-answer agreement;
- any-flip rate;
- mean and maximum probability standard deviation;
- mean Jensen–Shannon divergence across repetitions.

### 9.6 System metrics

- warm p50/p95/p99 latency;
- cold-start duration;
- questions per second;
- timeout, retry, and failure rates;
- provider-reported API cost per 1,000 decisions;
- estimated local compute cost per 1,000 decisions;
- peak process RAM and, where available, VRAM;
- model download/storage size.

Local cost assumptions—hardware, hourly price, power, and utilization—must be displayed beside the estimate.

## 10. Confidence normalization

Store two fields where applicable:

- `provider_confidence`: the provider’s returned confidence statistic;
- `decision_probability`: probability of the selected outcome.

Do not assume these quantities are identical. Risk–coverage defaults to selected-outcome probability unless the report explicitly selects and names another signal.

Noul uses distance from uncertainty only for optional diagnostics; action thresholds should operate on `P(true)` or `P(false)` according to the intended action.

## 11. Statistical reporting

- Report numerator and denominator beside every percentage.
- Use paired bootstrap 95% confidence intervals over base families, not independent case rows, so variants from one family stay together.
- Use a fixed recorded bootstrap seed.
- For paired hard-label differences, McNemar’s test may be included as a secondary diagnostic.
- Do not claim superiority when intervals are wide or the difference is practically trivial.
- Clearly separate exploratory slices from preregistered primary metrics.

## 12. Fairness controls

Before a final run, freeze:

- dataset and split digests;
- case transformations;
- provider versions;
- prompts/instructions/criteria;
- adapter versions;
- effective context and option budgets;
- thresholds and calibration files;
- random seeds;
- scoring code version;
- hardware/deployment configuration.

The platform should generate a “comparison integrity” checklist before enabling the final run.

## 13. Exclusions and failure handling

- No case is silently dropped.
- Context-limit failures count as failures for the configured system.
- Retries are recorded and measured.
- Manual reruns after inspecting correctness create a new run; they do not overwrite results.
- Provider outages are reported separately and may justify an operational rerun only when the rule is declared before labels are inspected.
- Cancelled runs are clearly marked partial and are not included in final conclusions by default.

## 14. Reporting format

Every report contains:

1. executive summary;
2. exact systems and tracks;
3. dataset and ground-truth method;
4. correctness by primitive and domain;
5. calibration and selective automation;
6. robustness and repeatability;
7. performance, cost, and resources;
8. representative wins, losses, and disagreements;
9. operational comparison;
10. limitations and threats to validity;
11. reproducibility manifest;
12. conditional recommendations.

Recommended conclusion style:

> Jev was stronger for high-cardinality choices in this evaluation, while Laya provided lower warm local latency and offline operation. At the selected 2% risk target, Jev automated X% and Laya automated Y%. These findings apply to the pinned configurations and dataset described above.

## 15. Threats to validity

- Small or synthetic datasets may not represent production traffic.
- Public examples may appear in training data.
- Human-authored criteria can favor one model’s learned phrasing.
- API and local latency are different deployment products.
- Model aliases can move unless version IDs are pinned.
- Laya performance depends on hardware and effective token budgets.
- Post-hoc calibration can overfit small development sets.
- A fine-tuned checkpoint answers a different question from zero-shot comparison.
- Aggregate metrics can hide severe subgroup failures.

These limitations must appear in the UI and exported report, not only in developer documentation.

## 16. Evaluation definition of done

- All 60 publishable base families pass independent review.
- Sealed families remain unseen during tuning.
- Both systems complete the same primary presentations or record explicit failures.
- All metric denominators reconcile with case and failure counts.
- Robustness is computed by family rather than unrelated rows.
- Confidence, probability, and calibration are not conflated.
- Default and tuned results remain separate.
- The final report includes raw artifacts, uncertainty, and limitations.

