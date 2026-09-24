import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  ArrowRight,
  Check,
  CheckCircle2,
  Database,
  FileUp,
  Info,
  LockKeyhole,
  Play,
  ShieldCheck,
} from "lucide-react";
import { post, request, useDatasets, useReadiness, label } from "../api";
import {
  BusyButton,
  ErrorBox,
  JsonBlock,
  Loading,
  PageTitle,
  Panel,
  cn,
} from "../components";
import type { Calibration, Dataset, Protocol, RunConfig } from "../types";

export default function Setup() {
  const navigate = useNavigate();
  const client = useQueryClient();
  const datasets = useDatasets(),
    readiness = useReadiness();
  const calibrations = useQuery({
    queryKey: ["calibrations"],
    queryFn: () => request<{ items: Calibration[] }>("/calibrations"),
  });
  const protocols = useQuery({
    queryKey: ["protocols"],
    queryFn: () => request<{ items: Protocol[] }>("/protocols"),
  });
  const [step, setStep] = useState(0);
  const [dataset, setDataset] = useState("demo");
  const [mode, setMode] = useState<"fake" | "live">("fake");
  const [track, setTrack] = useState<"default" | "production-tuned">("default");
  const [name, setName] = useState("Default comparison");
  const [model, setModel] = useState("jev-1.13.0");
  const [device, setDevice] = useState<"auto" | "cpu" | "mps" | "cuda">("auto");
  const [checkpoint, setCheckpoint] = useState<
    "router" | "english" | "multilingual" | "typed-decisions"
  >("router");
  const [seed, setSeed] = useState(20260924);
  const [repetitions, setRepetitions] = useState(5);
  const [sampleSize, setSampleSize] = useState(30);
  const [calibration, setCalibration] = useState("");
  const [protocol, setProtocol] = useState("");
  const [acknowledged, setAcknowledged] = useState(false);
  const [suites, setSuites] = useState({
    repeatability: false,
    performance: false,
    context_length: false,
    option_cardinality: false,
  });
  const [importResult, setImportResult] = useState<Dataset | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [hourly, setHourly] = useState("");
  const [basis, setBasis] = useState("");
  const [overrides, setOverrides] = useState("{}");
  const selected = datasets.data?.items.find((d) => d.dataset_id === dataset);
  const sealed = !!selected?.counts.split.sealed;
  const config = useMemo(() => {
    const frozen = protocols.data?.items.find((p) => p.protocol_id === protocol)
      ?.tracks[track]?.configuration;
    if (frozen)
      return {
        ...frozen,
        protocol_id: protocol,
        publication: true,
        acknowledge_remote: acknowledged,
      };
    return {
      name,
      track,
      dataset_ref: dataset,
      dataset_digest: selected?.digest,
      mode,
      seed,
      acknowledge_remote: acknowledged,
      systems: {
        jev: { enabled: true, model, timeout_seconds: 30, max_retries: 2 },
        laya: {
          enabled: true,
          mode: "router",
          device,
          preload: true,
          timeout_seconds: 120,
          checkpoint: track === "default" ? "router" : checkpoint,
          checkpoint_revision:
            mode === "live" ? readiness.data?.laya.revision : null,
        },
      },
      suites: {
        quality: true,
        calibration: true,
        robustness: true,
        repeatability: {
          enabled: suites.repeatability,
          repetitions,
          sample_size: sampleSize,
        },
        performance: {
          enabled: suites.performance,
          concurrency: [1, 4, 8],
          batch_sizes: [1, 5, 10, 50],
          sample_size: sampleSize,
        },
        context_length: suites.context_length,
        option_cardinality: suites.option_cardinality,
      },
      metrics: {
        ece_bins: 10,
        confidence_thresholds: [0.6, 0.7, 0.8, 0.9],
        bootstrap_samples: 2000,
        bootstrap_seed: seed,
        local_hourly_cost_usd: hourly ? Number(hourly) : null,
        local_cost_basis: basis || null,
        jev_usd_per_million_input_tokens: 0.042,
      },
      calibration_id:
        track === "production-tuned" && calibration ? calibration : null,
      instruction_overrides:
        track === "production-tuned" ? JSON.parse(overrides || "{}") : {},
      publication: false,
      protocol_id: null,
    };
  }, [
    name,
    track,
    dataset,
    selected,
    mode,
    seed,
    acknowledged,
    model,
    device,
    checkpoint,
    suites,
    repetitions,
    sampleSize,
    calibration,
    protocol,
    protocols.data,
    readiness.data,
    hourly,
    basis,
    overrides,
  ]);
  const estimate = useQuery({
    queryKey: ["estimate", config],
    queryFn: () =>
      post<{
        requests: number;
        questions: number;
        warmup_requests: number;
        maximum_jev_retries: number;
        note: string;
      }>("/runs/estimate", { ...config, acknowledge_remote: true }),
    enabled: step === 3 && !!selected,
  });
  const start = useMutation({
    mutationFn: () => post<{ run_id: string }>("/runs", config),
    onSuccess: (r) => {
      client.invalidateQueries({ queryKey: ["runs"] });
      navigate("/runs/" + r.run_id + "/live");
    },
  });
  async function upload(file?: File) {
    if (!file) return;
    setError(null);
    try {
      const body = new FormData();
      body.append("file", file);
      const result = await request<Dataset>("/datasets/validate", {
        method: "POST",
        body,
      });
      setImportResult(result);
      if (result.valid) {
        await client.invalidateQueries({ queryKey: ["datasets"] });
        setDataset(result.dataset_id);
      }
    } catch (error) {
      setError(error);
    }
  }
  function next() {
    setError(null);
    if (step === 0 && !selected) {
      setError(new Error("Select a valid dataset first."));
      return;
    }
    if (step === 1 && sealed && !protocol) {
      setError(
        new Error(
          "This dataset contains sealed cases. Complete independent review and freeze both tracks in Methodology before running it.",
        ),
      );
      return;
    }
    setStep(step + 1);
  }
  return (
    <div className="page setup-page">
      <PageTitle
        title="New evaluation"
        description="One dataset. Two decision systems. A comparison you can inspect."
      />
      <ol className="stepper">
        {["Dataset", "Systems", "Suites", "Review"].map((title, index) => (
          <li
            className={cn(index === step && "current", index < step && "done")}
            key={title}
          >
            <button disabled={index > step} onClick={() => setStep(index)}>
              <span>{index < step ? <Check size={15} /> : index + 1}</span>
              {title}
            </button>
          </li>
        ))}
      </ol>
      <ErrorBox error={error || start.error} />
      {datasets.isLoading ? (
        <Loading />
      ) : (
        <>
          {step === 0 && (
            <>
              <Panel
                title="Choose your evidence"
                description="Start with the development set, or bring a dataset that matches your workload."
              >
                <div className="dataset-options">
                  {datasets.data?.items.map((d) => (
                    <button
                      className={cn(
                        "dataset-option",
                        d.dataset_id === dataset && "selected",
                      )}
                      key={d.dataset_id}
                      onClick={() => {
                        setDataset(d.dataset_id);
                        setProtocol("");
                      }}
                    >
                      <div className="dataset-icon">
                        <Database size={23} />
                      </div>
                      <div>
                        <h3>
                          {d.dataset_id === "demo"
                            ? "Development collection"
                            : d.dataset_id === "benchmark"
                              ? "Evaluation collection"
                              : d.name}
                        </h3>
                        <p>
                          {d.counts.families} families · {d.counts.cases}{" "}
                          presentations
                        </p>
                        <div className="tags">
                          <span>Choice</span>
                          <span>Noul</span>
                          <span>Score</span>
                          {!!d.counts.split.sealed && (
                            <span>
                              <LockKeyhole size={12} />
                              {d.counts.split.sealed} sealed
                            </span>
                          )}
                        </div>
                      </div>
                      {d.dataset_id === dataset ? (
                        <CheckCircle2 className="selected-check" size={22} />
                      ) : (
                        <span className="radio-circle" />
                      )}
                    </button>
                  ))}
                </div>
                <label
                  className="upload"
                  onDragOver={(e) => e.preventDefault()}
                  onDrop={(e) => {
                    e.preventDefault();
                    upload(e.dataTransfer.files[0]);
                  }}
                >
                  <FileUp size={24} />
                  <strong>Import your own JSONL</strong>
                  <span>
                    Drop a file here or choose a file. Maximum 25 MiB.
                  </span>
                  <input
                    type="file"
                    accept=".jsonl,.json"
                    aria-label="Import JSONL dataset"
                    onChange={(e) => upload(e.target.files?.[0])}
                  />
                </label>
                {importResult && !importResult.valid && (
                  <div className="validation-errors" role="alert">
                    <h3>Resolve these issues before starting</h3>
                    {importResult.issues.map((issue, i) => (
                      <p key={i}>
                        Line {issue.line} · {issue.field}: {issue.message}
                      </p>
                    ))}
                  </div>
                )}
              </Panel>
              {selected && (
                <div className="dataset-summary">
                  <ShieldCheck size={18} />
                  <div>
                    <strong>Schema validation passed</strong>
                    <p>
                      {Object.entries(selected.counts.primitive)
                        .map(([p, n]) => n + " " + label(p))
                        .join(" · ")}
                      . Gold labels remain provisional until independently
                      reviewed.
                    </p>
                  </div>
                </div>
              )}
            </>
          )}
          {step === 1 && (
            <Panel
              title="Choose the comparison"
              description="Default and Production-tuned results stay separate in every view."
            >
              <div className="form-grid">
                <label>
                  Comparison track
                  <select
                    value={track}
                    onChange={(e) => setTrack(e.target.value as typeof track)}
                  >
                    <option value="default">Default</option>
                    <option value="production-tuned">Production-tuned</option>
                  </select>
                </label>
                <label>
                  Execution mode
                  <select
                    aria-label="Execution mode"
                    value={mode}
                    onChange={(e) => setMode(e.target.value as typeof mode)}
                  >
                    <option value="fake">
                      Simulation — offline demonstration
                    </option>
                    <option value="live">Live — real Jev and local Laya</option>
                  </select>
                </label>
              </div>
              <div className="notice">
                <Info size={18} />
                <p>
                  {mode === "fake"
                    ? "Simulation generates synthetic outcomes to demonstrate the workspace. It cannot support conclusions about either model."
                    : "Jev sends case state to the TypeSafe API. Laya inference stays on this machine. Credentials remain backend-only."}
                </p>
              </div>
              <div className="paired system-config">
                <div>
                  <span className="model-name">
                    <i className="jev" />
                    Jev
                  </span>
                  <p>Hosted typed decisions</p>
                  <label>
                    Versioned model
                    <input
                      value={model}
                      onChange={(e) => setModel(e.target.value)}
                    />
                  </label>
                  <span
                    className={
                      readiness.data?.jev.configured
                        ? "success-text"
                        : "warning-text"
                    }
                  >
                    {readiness.data?.jev.configured
                      ? "Credential configured"
                      : "Live credential not configured"}
                  </span>
                </div>
                <div>
                  <span className="model-name">
                    <i className="laya" />
                    Laya
                  </span>
                  <p>Local Router and pinned checkpoints</p>
                  <label>
                    Device
                    <select
                      value={device}
                      onChange={(e) =>
                        setDevice(e.target.value as typeof device)
                      }
                    >
                      {["auto", "mps", "cpu", "cuda"].map((d) => (
                        <option key={d} value={d}>
                          {d === "auto" ? "Auto-detect" : d.toUpperCase()}
                        </option>
                      ))}
                    </select>
                  </label>
                  <span
                    className={
                      readiness.data?.laya.ready
                        ? "success-text"
                        : "warning-text"
                    }
                  >
                    {readiness.data?.laya.ready
                      ? "Checkpoints ready"
                      : readiness.data?.laya.reason || "Checking local runtime"}
                  </span>
                </div>
              </div>
              {track === "production-tuned" && (
                <div className="advanced-fields">
                  <h3>Frozen tuning inputs</h3>
                  <div className="form-grid">
                    <label>
                      Calibration artifact
                      <select
                        value={calibration}
                        onChange={(e) => setCalibration(e.target.value)}
                      >
                        <option value="">No post-hoc calibration</option>
                        {calibrations.data?.items
                          .filter((c) => c.source_mode === mode)
                          .map((c) => (
                            <option
                              key={c.calibration_id}
                              value={c.calibration_id}
                            >
                              {c.calibration_id.slice(0, 18)}
                            </option>
                          ))}
                      </select>
                    </label>
                    <label>
                      Checkpoint route
                      <select
                        value={checkpoint}
                        onChange={(e) =>
                          setCheckpoint(e.target.value as typeof checkpoint)
                        }
                      >
                        {[
                          "router",
                          "english",
                          "multilingual",
                          "typed-decisions",
                        ].map((v) => (
                          <option key={v} value={v}>
                            {label(v)}
                          </option>
                        ))}
                      </select>
                    </label>
                  </div>
                  <label>
                    Matched instruction overrides (JSON by label-space ID)
                    <textarea
                      defaultValue="{}"
                      onBlur={(e) => {
                        try {
                          const parsed = JSON.parse(e.target.value);
                          if (
                            !parsed ||
                            Array.isArray(parsed) ||
                            typeof parsed !== "object" ||
                            Object.values(parsed).some(
                              (v) => typeof v !== "string",
                            )
                          )
                            throw new Error();
                          setOverrides(e.target.value);
                          setError(null);
                        } catch {
                          setError(
                            new Error(
                              "Overrides must be a JSON object mapping label-space IDs to instructions.",
                            ),
                          );
                        }
                      }}
                    />
                  </label>
                </div>
              )}
              {sealed && (
                <label>
                  Frozen evaluation protocol
                  <select
                    value={protocol}
                    onChange={(e) => {
                      setProtocol(e.target.value);
                      setMode("live");
                    }}
                  >
                    <option value="">Select a reviewed, frozen protocol</option>
                    {protocols.data?.items
                      .filter((p) => p.dataset_id === dataset)
                      .map((p) => (
                        <option key={p.protocol_id} value={p.protocol_id}>
                          {p.protocol_id}
                        </option>
                      ))}
                  </select>
                </label>
              )}
            </Panel>
          )}
          {step === 2 && (
            <Panel
              title="What do you want to measure?"
              description="Primary correctness, calibration, robustness, and warm latency are always included."
            >
              <div className="suite-list">
                {[
                  [
                    "quality",
                    "Correctness & calibration",
                    "All primary decisions, complete probabilities, reliability and risk–coverage.",
                  ],
                  [
                    "robustness",
                    "Behavioral robustness",
                    "Controlled family variants reveal sensitivity to wording and presentation.",
                  ],
                ].map(([id, title, description]) => (
                  <div className="suite-row" key={id}>
                    <CheckCircle2 size={21} />
                    <div>
                      <h3>{title}</h3>
                      <p>{description}</p>
                    </div>
                    <span className="badge">Included</span>
                  </div>
                ))}
                {(
                  [
                    [
                      "repeatability",
                      "Repeatability",
                      "Fresh calls measure answer flips and probability variation.",
                    ],
                    [
                      "performance",
                      "Load & batching",
                      "Separate runs at concurrency 1/4/8 and 1/5/10/50 questions per shared-state request.",
                    ],
                    [
                      "context_length",
                      "Context-length diagnostic",
                      "Adds irrelevant content at 1,024 / 4,096 / 16,384 character buckets.",
                    ],
                    [
                      "option_cardinality",
                      "Option-cardinality diagnostic",
                      "Choice answer spaces with 2 / 4 / 10 / 20 / 50 / 75 options.",
                    ],
                  ] as const
                ).map(([key, title, description]) => (
                  <label className="suite-row" key={key}>
                    <input
                      type="checkbox"
                      checked={suites[key]}
                      onChange={(e) =>
                        setSuites({ ...suites, [key]: e.target.checked })
                      }
                    />
                    <div>
                      <h3>{title}</h3>
                      <p>{description}</p>
                    </div>
                  </label>
                ))}
              </div>
              {(suites.repeatability || suites.performance) && (
                <div className="form-grid">
                  <label>
                    Sample size
                    <input
                      type="number"
                      min="1"
                      max="500"
                      value={sampleSize}
                      onChange={(e) => setSampleSize(Number(e.target.value))}
                    />
                  </label>
                  <label>
                    Repeatability calls per case
                    <input
                      type="number"
                      min="2"
                      max="20"
                      value={repetitions}
                      onChange={(e) => setRepetitions(Number(e.target.value))}
                    />
                  </label>
                </div>
              )}
              <details>
                <summary>Cost assumptions and reproducibility</summary>
                <div className="form-grid">
                  <label>
                    Random seed
                    <input
                      type="number"
                      value={seed}
                      onChange={(e) => setSeed(Number(e.target.value))}
                    />
                  </label>
                  <label>
                    Local compute cost (USD / hour, optional)
                    <input
                      type="number"
                      min="0"
                      step=".01"
                      value={hourly}
                      onChange={(e) => setHourly(e.target.value)}
                    />
                  </label>
                </div>
                <label>
                  Hardware, utilization, and price basis
                  <input
                    value={basis}
                    onChange={(e) => setBasis(e.target.value)}
                    placeholder="Describe the assumptions behind the hourly estimate"
                  />
                </label>
                <p className="caption">
                  Unset local cost is reported as unavailable. Jev API cost
                  estimates use $0.042 per million input tokens, separately from
                  reported billing.
                </p>
              </details>
            </Panel>
          )}
          {step === 3 && (
            <Panel
              title="Review your evaluation"
              description="This configuration will be saved alongside every prediction."
            >
              <label>
                Evaluation name
                <input
                  maxLength={160}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              <dl className="review-grid">
                <div>
                  <dt>Dataset</dt>
                  <dd>{selected?.name}</dd>
                </div>
                <div>
                  <dt>Track</dt>
                  <dd>{label(track)}</dd>
                </div>
                <div>
                  <dt>Execution</dt>
                  <dd>
                    {mode === "fake" ? "Simulated outcomes" : "Live providers"}
                  </dd>
                </div>
                <div>
                  <dt>Requests</dt>
                  <dd>
                    {estimate.data?.requests.toLocaleString() ?? "Calculating…"}{" "}
                    <small>
                      + {estimate.data?.warmup_requests ?? 0} warm-up
                    </small>
                  </dd>
                </div>
                <div>
                  <dt>Logical questions</dt>
                  <dd>{estimate.data?.questions.toLocaleString() ?? "—"}</dd>
                </div>
                <div>
                  <dt>Retry budget</dt>
                  <dd>
                    Up to {estimate.data?.maximum_jev_retries ?? 0} additional
                    Jev calls
                  </dd>
                </div>
              </dl>
              <p className="caption">
                Actual runtime and cost are measured during execution. Load
                tests and repeats are excluded from primary quality totals.
              </p>
              <div className="digest">
                <LockKeyhole size={15} />
                {selected?.digest}
              </div>
              {mode === "live" && (
                <label className="consent">
                  <input
                    type="checkbox"
                    checked={acknowledged}
                    onChange={(e) => setAcknowledged(e.target.checked)}
                  />
                  <span>
                    I understand that case state will be sent to Jev’s hosted
                    API.
                  </span>
                </label>
              )}
              {mode === "fake" && (
                <div className="notice">
                  <Info size={18} />
                  <p>
                    This is an offline product demonstration. All screens and
                    exports will identify the outcomes as simulated.
                  </p>
                </div>
              )}
              <details>
                <summary>View effective configuration</summary>
                <JsonBlock value={config} />
              </details>
              <ErrorBox error={estimate.error} />
            </Panel>
          )}
          <div className="wizard-actions">
            <button
              className="button secondary"
              disabled={step === 0}
              onClick={() => setStep(step - 1)}
            >
              <ArrowLeft size={16} />
              Back
            </button>
            <span>Step {step + 1} of 4</span>
            {step < 3 ? (
              <button className="button primary" onClick={next}>
                Continue
                <ArrowRight size={16} />
              </button>
            ) : (
              <BusyButton
                className="button primary"
                busy={start.isPending}
                disabled={
                  !name.trim() ||
                  (mode === "live" && !acknowledged) ||
                  !estimate.data ||
                  !!estimate.error
                }
                onClick={() => start.mutate()}
              >
                <Play size={16} />
                Start evaluation
              </BusyButton>
            )}
          </div>
        </>
      )}
    </div>
  );
}
