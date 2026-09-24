# Research Baseline and Existing Evidence

**Research date:** 24 September 2026

This document records the evidence used to design DecisionLab. It is not a substitute for running the project’s own pinned comparison.

## 1. Systems being compared

### Jev

Jev is TypeSafe AI’s hosted System One decision model. It accepts shared state and typed `choice`, `score`, and `noul` questions, then returns bounded values and probabilities rather than generated prose.

Verified current reference information:

- versioned model: `jev-1.13.0`;
- hosted API;
- text/JSON state;
- 64k tokens per request, with the documented state/longest-question constraint;
- priced per input token;
- English is the primary training language;
- customer-specific fine-tuning is not exposed; behavior is shaped through state, instructions, criteria, and application logic.

Sources:

- [TypeSafe primitives](https://docs.typesafe.ai/primitives)
- [TypeSafe model reference](https://docs.typesafe.ai/models)
- [Jev 1.13 documented limitations](https://docs.typesafe.ai/model-jaggedness/jev-1.13)
- [TypeSafe confidence](https://docs.typesafe.ai/confidence)

### Laya

Laya is an open-weight, locally runnable System One decision engine implementing compatible `choice`, `score`, and `noul` workflows.

Verified current reference information:

- Apache 2.0 model/repository licensing as published;
- Python package and local execution;
- English, multilingual, and typed-decisions checkpoints;
- built-in Router;
- ModernBERT/mmBERT encoder-based architecture with a decision head;
- configurable local deployment, HTTP server, and optional MCP integration;
- strongest published typed-decisions result belongs to a checkpoint fine-tuned on that benchmark’s training split;
- documented limitations include high-cardinality option budgets, weaker ordinal Score behavior, label sensitivity, and calibration requirements.

Sources:

- [Laya repository](https://github.com/NandhaKishorM/laya)
- [Laya model card](https://huggingface.co/convaiinnovations/laya)
- [Laya benchmark report](https://github.com/NandhaKishorM/laya/blob/main/BENCHMARKS.md)

## 2. Why the shared API matters

Both systems accept nearly the same conceptual contract:

```text
state + typed question + bounded criteria
                    ↓
selected value + probability distribution
```

This makes a paired comparison more defensible than comparing a classifier with a generative chatbot. DecisionLab can preserve one canonical case and limit adapter differences to required serialization.

## 3. Existing Laya-published comparison

Laya’s documentation contains a Jev comparison, but it explicitly states that Jev values were taken from third-party published results rather than measured in the same run, and that prompts/sample sizes differ.

It also reports a strong `laya-typed-decisions` result after fine-tuning on that benchmark’s training split. That result is useful for a domain-adaptation track, but it is not an out-of-the-box generic comparison.

DecisionLab response:

- do not reuse this table as final evidence;
- maintain separate Default and Production-tuned tracks;
- evaluate both systems in the same paired harness.

## 4. Independent JevBench evidence

[JevBench](https://github.com/fstandhartinger/jevbench) independently evaluates Jev-class decision systems.

One published frozen-set result reports:

| System | Composite | Intelligence | Calibration | Speed | Cost |
|---|---:|---:|---:|---:|---:|
| Jev 1.13.0 | 74.4 | 85.7 | 82.7 | 83.3 | 52.0 |
| Laya 421M | 54.4 | 45.8 | 62.5 | 71.1 | 86.2 |

Source: [JevBench results](https://github.com/fstandhartinger/jevbench/blob/main/RESULTS-v1.2.md)

Important caveats:

- the Laya row used the English root checkpoint and package version documented by that run;
- it ran locally on CPU while Jev used a production API;
- Laya’s 512-token budget truncated longer hard cases;
- self-hosted latency received an explicit benchmark adjustment;
- the composite depends on benchmark-specific weights and transformations.

DecisionLab response:

- reuse the idea of frozen and sealed decisions;
- preserve raw and adjusted timing separately;
- avoid a mandatory weighted composite;
- test current pinned configurations and report context/cardinality curves.

## 5. Direct public classification benchmark

A separate reproducible project compared Jev and Laya on 500 examples from each of three public text-classification datasets using shared label descriptions.

Published results included:

| Dataset | Jev accuracy | Laya accuracy | Main observation |
|---|---:|---:|---|
| AG News, 4 labels | 84.3%; 85.8% with revised descriptions | 90.6% | Laya led on this run |
| SST-2, 2 labels | 95.4% | 92.0% | Both were strong |
| Banking77, 77 labels | 76.4% | 38.2% | Jev led substantially as option count increased |

Source: [JEV classifier benchmark](https://github.com/dhruvmehra/jevbench/blob/main/docs/results/2026-09-22-n500-summary.md)

Important caveats:

- only Choice-style public classification was tested;
- old public datasets may occur in pretraining data;
- Jev latency included an API hop while Laya was local;
- a label-description change affected Jev’s AG News result;
- the benchmark does not cover robustness, repeatability, Noul, Score, or risk–coverage.

DecisionLab response:

- treat option-cardinality and instruction wording as first-class diagnostics;
- add all three primitives;
- add controlled behavioral variants;
- build original reviewed cases and retain a sealed split.

## 6. Documented system limitations worth testing

### Jev hypotheses

Official documentation identifies sensitivity to:

- literal wording;
- arithmetic and numeric precision;
- dates and temporal comparison;
- multiple levels of indirection;
- irrelevant large state;
- adversarial content;
- contradictory instructions/criteria;
- assumed structural consistency between differently phrased primitives.

DecisionLab should include relevant diagnostic cases but should not turn code-computable arithmetic into the primary comparison target.

### Laya hypotheses

Published documentation identifies sensitivity to:

- large option sets under the default option-token budget;
- boolean-looking labels;
- Noul label wording;
- weak ordinal Score performance in published diagnostics;
- raw overconfidence and the need for domain calibration;
- language/checkpoint routing;
- context settings and checkpoint specialization.

These are hypotheses to test, not outcomes to assume.

## 7. Evaluation research foundations

DecisionLab uses established ideas rather than accuracy alone:

- Calibration measures whether predicted confidence corresponds to empirical correctness. Temperature scaling is a common post-hoc method, but it must be fitted on separate development data. [On Calibration of Modern Neural Networks](https://proceedings.mlr.press/v70/guo17a.html)
- Behavioral testing uses controlled transformations and invariance expectations to reveal failures hidden by ordinary aggregate datasets. [Beyond Accuracy: Behavioral Testing of NLP Models with CheckList](https://aclanthology.org/2020.acl-main.442/)
- Selective prediction evaluates error as the system abstains on uncertain examples, motivating risk–coverage reporting. [SelectiveNet](https://proceedings.mlr.press/v97/geifman19a.html)

## 8. Research conclusions informing the product

1. There is no credible basis for one unconditional winner.
2. Jev and Laya can be compared through one canonical typed-decision contract.
3. Option count, context, wording, primitive, and calibration can materially change the result.
4. Default and fine-tuned configurations answer different questions and must be separate.
5. Local versus API latency and cost require transparent deployment labels.
6. Risk at useful automation coverage is more actionable than accuracy alone.
7. The unique contribution should be behavioral reliability and evidence exploration, not another static score table.

## 9. Remaining pre-run verification

Immediately before a final evaluation:

- confirm the Jev API path and credential;
- resolve and record the exact Jev version returned;
- pin the Laya package and checkpoint revisions;
- verify all three primitive mappings with smoke cases;
- record hardware and effective context/option settings;
- freeze dataset, scoring code, thresholds, and random seeds;
- ensure no sealed case was used for calibration or model selection.

