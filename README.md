# DecisionLab

Run the same typed decisions through hosted Jev and local Laya, inspect their evidence, and export a reproducible comparison. Use the web workspace or drive the full guarded evaluation from Codex or Claude Code through the included MCP server. DecisionLab covers Choice, Noul, Score, calibration, selective automation, robustness, repeatability, latency, cost, and failures.

## Start locally

Requires macOS or Linux, [uv](https://docs.astral.sh/uv/), and Node 24 (see `.nvmrc`). Run commands from the repository root.

```sh
uv sync --locked
npm ci
npm run build
.venv/bin/decisionlab serve
```

Open **http://127.0.0.1:8768**. Choose **New evaluation → Development collection → Simulation** to exercise the whole workflow without credentials or model downloads. Simulation is visibly labeled throughout, including exports; its numbers say nothing about either provider.

For frontend development, run `.venv/bin/decisionlab serve --reload` in one terminal and `npm run dev` in another. Vite serves http://127.0.0.1:5173 and proxies the API. The backend defaults to port 8768; set `DECISIONLAB_API_TARGET` to use another address.

## Live providers

Copy `.env.example` to `.env` and set `TYPESAFE_API_KEY` locally. Then install and prepare the pinned local runtime:

```sh
uv sync --locked --extra laya
.venv/bin/decisionlab models prepare --revision 55cf4c4ebb4ebe31b2550e8bdf3bd21b99753851
.venv/bin/python scripts/smoke_laya.py --device mps
.venv/bin/decisionlab serve
```

Use `--device cpu` for the smoke script on a machine without Apple GPU support. Preparation downloads approximately 2.37 GB into the Hugging Face cache and records all three checkpoint routes in `models/lock.json`. Runtime inference uses that local snapshot. The app records actual device, checkpoint, dtype, applied temperatures, SDK warnings, package versions, and source digest. A GPU unavailable to the process can fall back to CPU; the actual runtime is recorded.

Jev-bound state leaves the machine only for an explicitly selected, acknowledged live run. No credential is accepted through the browser. Jev is pinned to `jev-1.13.0` by default, and a different returned version fails the decision. At build verification, real Laya passed all three primitives on CPU and MPS; a real Jev call still requires your credential.

## Dataset and publication workflow

The bundled policy-derived labels are **drafts**, not independently verified ground truth.

| Collection | Families | Presentations | Purpose |
|---|---:|---:|---|
| `demo` | 24 | 144 | Development and calibration |
| `benchmark` | 60 | 360 | Evaluation; 15 families / 90 presentations sealed |

The two collections have disjoint family IDs. Every family has six presentations. Choice tests paraphrase, option order, opaque labels, distractor state, and adversarial state; Noul and Score substitute a second paraphrase and state-key order for the Choice-only transformations. Score criteria remain ordered.

1. Run the development collection. Use the Production-tuned track for any prompt or checkpoint experiments; leave calibration unset while collecting the predictions used to fit a new calibration.
2. In **Methodology**, fit calibration from an uncalibrated development run. The resulting temperatures and thresholds can only be reused with matching prompts, models, checkpoint revision, device setting, and live/simulation mode. Development and evaluation families must be disjoint.
3. Download the evaluation collection's blind review packet. Have an independent human label every presentation, then import their JSON reviews. The reviewer must provide `case_id`, `reviewer`, `answer`, and `rationale`. Use native JSON booleans for Noul and integer level indices for Score.
4. Disagreements require a separate named adjudicator, `adjudicated_answer`, and `adjudication_rationale`. To correct a gold label, import and review a new dataset. Software records the attestation; it cannot verify the reviewer's identity or independence.
5. Prepare and freeze both live track configurations together in **Methodology**. Put the chosen `calibration_id` and tuning settings in Production-tuned. Freeze the exact Jev version, 40-character Laya revision, seeds, suite settings, and cost assumptions. The protocol binds the dataset, reviews, calibration content, scoring implementation, and installed inference packages.
6. Select that protocol in **New evaluation** and execute each track once. Sealed evidence and exports unlock only after both finish. Interrupted records remain intact; a failed frozen track cannot be replaced with a cherry-picked rerun. Operational follow-ups require a new explicitly exploratory protocol and report: set `publication` to `false` in both configurations. A new protocol cannot restore publication eligibility for a dataset already used in a different live evaluation protocol.

Sealing is a workflow boundary in a local single-user application. A person with filesystem access or the reviewer packet can read source cases; it is not a tamper-proof examination system.

You can import UTF-8 JSONL up to 25 MiB. The validator checks native labels, duplicates, family relationships, transformations, and probability outcome mappings. See [the schema](backend/decisionlab/schemas.py) and [the API contract](docs/openapi.json) for the executable format.

## Evidence and recovery

**Live run** plays each saved question through side-by-side Jev and Laya diagrams: input → model → selected option → correct/incorrect. Bars show the saved probabilities. Pause, step, change speed, or jump to the latest comparison; **Inspect** opens the exact request shown, including repeats and batches. Playback never makes provider calls or slows evaluation, and Results open as soon as the evaluation finishes. Position and speed survive refresh in the same browser tab. Reduced motion shows outcomes without traveling packets.

Data lives under `data/` by default; set `DECISIONLAB_DATA_ROOT` to change it. A run includes immutable case/configuration snapshots, a seeded schedule, append-only predictions/events/errors, warm-up evidence, environment information, and versioned metrics. Frozen runs additionally snapshot reviews, protocols, and calibration artifacts. Reports and ZIP bundles include checksums.

Refresh or reopen the browser to reconnect to the run. Cancellation stops new work and allows up to five seconds for an in-flight request before cancellation. Restarting after a crash marks interrupted runs partial and retains complete JSONL records, ignoring a torn final record. It does not silently retry them. One backend process may own a data root at a time; use the UI to rescore while it is running, or stop it before using:

```sh
.venv/bin/decisionlab rescore RUN_ID
```

Rescoring makes no provider calls. Accuracy and coverage include missing/failed primary decisions in their denominators. Calibration excludes invalid probability distributions and reports the exclusion count. Repeats, shared-state performance batches, and context/cardinality diagnostics do not reweight primary quality. Confidence uses the selected-outcome probability, independently of provider confidence. Family bootstrap intervals preserve dependence among transformations. Small-sample risk estimates are descriptive.

Cost estimates distinguish recorded provider usage, warm-up, retries with unavailable usage, and user-supplied local hardware costs. Local RAM is measured for the app and worker together; no remote RAM estimate is invented. Local throughput includes queueing, while inference and queue timings remain separate.

## Checks

```sh
.venv/bin/ruff check backend scripts
.venv/bin/ruff format --check backend scripts
.venv/bin/mypy backend/decisionlab
.venv/bin/python -m pytest -q
npm run format:check
npm test
npm run build
npx playwright install chromium
npm run test:e2e
```

Offline tests need neither a provider key nor Laya weights. Browser tests use isolated ports 5183 and 8778 with `test-results/data`, covering playback, refresh, evidence, export, accessibility, and mobile reduced motion. CI runs the same checks using locked dependencies; it does not make paid provider calls.

Regenerate the TypeScript request contract after API changes:

```sh
.venv/bin/decisionlab openapi
npm run types:api
```

## MCP benchmark runner

The local MCP server lets Codex or Claude Code run the complete DecisionLab methodology from a dataset folder. It uses the same backend, review gates, frozen configurations, metrics, and reports as the web workspace. The backend owns durable progress, so closing the MCP client does not lose workflow state.

### Quick start with the bundled dataset

From the repository root, run:

```sh
./install-mcp.sh sample-datasets customer-support-full
source .cache/decisionlab-mcp/env.sh
codex
```

Then ask Codex:

```text
Use the decisionlab-mcp tools to run a standard comparison on the
customer-support-full dataset. Show me the request estimates before asking
for approval, guide me through the review step, and summarize the final KPIs.
```

The installer installs dependencies, runs the offline backend, MCP, and frontend checks, starts an isolated DecisionLab backend on port 8879, verifies all six MCP tools, and prepares the dataset without making provider calls. Live Jev or Laya execution begins only after the MCP client sends both explicit confirmation flags. Stop the installer-managed backend with `./install-mcp.sh --stop`.

To use your own data, place `dataset.jsonl` in a named child folder and pass both names to the installer:

```text
/absolute/path/to/evaluation-datasets/
└── support-routing/
    └── dataset.jsonl
```

```sh
./install-mcp.sh /absolute/path/to/evaluation-datasets support-routing
source .cache/decisionlab-mcp/env.sh
codex
```

Use [`sample-datasets/customer-support-full/dataset.jsonl`](sample-datasets/customer-support-full/dataset.jsonl) as a working format example. Inputs must be UTF-8 JSONL, no larger than 25 MiB, and must pass DecisionLab's label, family, transformation, and probability-mapping validation.

### Available MCP tools

| Tool | Purpose |
|---|---|
| `prepare_benchmark` | Validate and partition a dataset, estimate requests, and create the blind-review packet. |
| `list_benchmarks` | List durable benchmark workflows. |
| `get_benchmark_status` | Return progress, estimates, blockers, review state, and the next action. |
| `advance_benchmark` | Advance one step and start at most one provider run; the first live advance requires both consent flags. |
| `cancel_benchmark` | Stop active work while retaining completed evidence. |
| `get_benchmark_report` | Return verdicts, paired confidence intervals, calibration, failures, latency, cost, robustness, and Markdown. |

### Manual configuration

Start DecisionLab first. Keep `TYPESAFE_API_KEY` and all provider configuration only in that backend process:

```sh
.venv/bin/decisionlab serve
```

Set the one filesystem boundary the MCP process needs. The value must be an absolute path, and each child folder you select must contain `dataset.jsonl`:

```sh
export DECISIONLAB_DATASET_ROOT=/absolute/path/to/evaluation-datasets
export TARGET_API_BASE_URL=http://127.0.0.1:8768
```

Project registrations are in `.mcp.json` for Claude Code and `.codex/config.toml` for Codex. Approve the project server in Claude Code, or trust the project in Codex, then use the tools in this order:

1. `prepare_benchmark(dataset_folder="support-routing")` validates and partitions the file, returns estimates, and writes a blind review packet.
2. Read the estimates with `get_benchmark_status`. When ready, call `advance_benchmark` once with `confirm_live_calls=true` and `confirm_remote_data=true`.
3. Poll status and advance after development completes. Calibration is fitted only from development predictions.
4. At `waiting_for_review`, have an independent person label the blind packet and save the JSON array at the returned `review.submission_path`.
5. Advance to validate the reviews and freeze paired default and production-tuned configurations. Continue polling and advancing; a call starts at most one provider run.
6. When both tracks complete, call `get_benchmark_report` for the accuracy verdict, paired confidence interval, calibration, failure, latency, cost, robustness, and optional full-profile KPIs.

Use `profile="standard"` for the default quality/calibration/robustness evaluation or `profile="full"` to add repeats, load tests, context length, and option-cardinality diagnostics. The report declares `no_clear_winner` whenever the paired 95% accuracy interval includes zero. It never converts secondary KPIs into a winner or claims a universal model ranking.

The MCP verifier uses mock HTTP only. It never starts a real provider run.

## Layout

- `backend/decisionlab/`: contracts, dataset policies, adapters, local worker, runner, metrics, calibration, review gates, API, reports.
- `frontend/src/`: React workspace and evidence views.
- `backend/tests/`, `frontend/e2e/`: offline integrity and browser checks.
- `docs/`: original product/design specifications and [implementation ledger](docs/BUILD-LEDGER.md).

This version is local and single-user. It has no authentication, hosted deployment, database, or training orchestrator. Keep it bound to loopback. Original planning documents describe the broader rationale; this README, the implementation ledger, and generated OpenAPI contract describe the delivered behavior.
