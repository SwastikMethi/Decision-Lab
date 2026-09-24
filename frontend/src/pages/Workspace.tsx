import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Activity,
  ArrowRight,
  CheckCircle2,
  Clock3,
  Database,
  Download,
  FileCheck2,
  FlaskConical,
  Info,
  LockKeyhole,
  Play,
  Plus,
  ShieldCheck,
  Upload,
} from "lucide-react";
import { motion } from "framer-motion";
import {
  color,
  isTerminal,
  label,
  number,
  post,
  request,
  systemName,
  useDatasets,
  useReadiness,
  useRun,
  useRuns,
  useSummary,
} from "../api";
import {
  BusyButton,
  Empty,
  ErrorBox,
  JsonBlock,
  Loading,
  PageTitle,
  Panel,
  Status,
} from "../components";
import type { Calibration, Dataset, Protocol, RunConfig } from "../types";

export function Overview() {
  const runs = useRuns(),
    readiness = useReadiness(),
    datasets = useDatasets();
  const items = runs.data?.items || [];
  const completed = items.filter((r) => r.status === "completed").length;
  return (
    <div className="page">
      <PageTitle
        title="Your evaluation workspace"
        description="Understand where each decision system earns your trust."
        action={
          <Link className="button primary" to="/new">
            <Plus size={17} />
            New evaluation
          </Link>
        }
      />
      <ErrorBox error={runs.error || readiness.error} />
      <div className="readiness-strip">
        <div>
          <span className="model-name">
            <i className="jev" />
            Jev API
          </span>
          <strong
            className={
              readiness.data?.jev.configured ? "success-text" : "muted"
            }
          >
            {readiness.data?.jev.configured
              ? "Credential ready"
              : "Credential needed"}
          </strong>
          <small>Versioned hosted inference</small>
        </div>
        <div>
          <span className="model-name">
            <i className="laya" />
            Laya local
          </span>
          <strong
            className={readiness.data?.laya.ready ? "success-text" : "muted"}
          >
            {readiness.data?.laya.ready ? "Checkpoints ready" : "Setup needed"}
          </strong>
          <small>
            {readiness.data?.laya.package_version
              ? "Package " + readiness.data.laya.package_version
              : "CPU, MPS, or CUDA"}
          </small>
        </div>
        <div>
          <span className="model-name">
            <Database size={14} />
            Datasets
          </span>
          <strong>{datasets.data?.items.length ?? "—"} collections</strong>
          <small>Validated before every run</small>
        </div>
        <div>
          <span className="model-name">
            <ShieldCheck size={14} />
            Storage
          </span>
          <strong>
            {readiness.data?.storage.writable
              ? "Local & writable"
              : "Checking…"}
          </strong>
          <small>Raw evidence stays available</small>
        </div>
      </div>
      <div className="overview-intro">
        <div>
          <div className="intro-symbol">
            <FlaskConical size={28} />
          </div>
          <h2>
            A comparison is only as useful
            <br />
            as the evidence behind it.
          </h2>
          <p>
            Run the same typed decisions through Jev and Laya. Explore
            correctness, confidence, robustness, and the cost of putting each
            system to work.
          </p>
          <Link to="/new" className="text-button">
            Build your next comparison <ArrowRight size={16} />
          </Link>
        </div>
        <div
          className="comparison-illustration"
          aria-label="The same case is evaluated independently by Jev and Laya"
        >
          <div className="illustration-input">
            <Database size={18} />
            <span>
              One canonical case<small>State + question + criteria</small>
            </span>
            <CheckCircle2 size={16} />
          </div>
          <div className="branch-lines" />
          <div className="paired">
            <div className="illustration-model">
              <i className="model-dot jev" />
              <strong>Jev</strong>
              <small>Hosted API</small>
            </div>
            <div className="illustration-model">
              <i className="model-dot laya" />
              <strong>Laya</strong>
              <small>Local inference</small>
            </div>
          </div>
          <div className="illustration-output">
            <ShieldCheck size={16} /> Paired, inspectable evidence
          </div>
        </div>
      </div>
      <Panel
        title="Recent evaluations"
        description={
          items.length
            ? completed + " completed evaluations in this workspace."
            : "Your runs and their evidence will appear here."
        }
        action={<span className="badge">{items.length} runs</span>}
      >
        {runs.isLoading ? (
          <Loading />
        ) : !items.length ? (
          <Empty title="Start with the development collection">
            144 presentations across Choice, Noul, and Score.{" "}
            <Link to="/new">Create your first evaluation.</Link>
          </Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Evaluation</th>
                  <th>Track</th>
                  <th>Status</th>
                  <th>Progress</th>
                  <th>Created</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {items.map((run) => (
                  <tr key={run.run_id}>
                    <td>
                      <Link
                        className="strong-link"
                        to={
                          "/runs/" +
                          run.run_id +
                          "/" +
                          (isTerminal(run.status) ? "results" : "live")
                        }
                      >
                        {run.name}
                      </Link>
                      <small className="cell-note">
                        {run.mode === "fake" ? "Simulation" : "Live providers"}{" "}
                        · {run.effective_config.dataset_ref}
                      </small>
                    </td>
                    <td>
                      <span className="badge">{label(run.track)}</span>
                    </td>
                    <td>
                      <Status value={run.status} />
                    </td>
                    <td>
                      {run.progress.completed}/{run.progress.total}
                    </td>
                    <td>{new Date(run.created_at).toLocaleDateString()}</td>
                    <td>
                      <Link
                        className="icon-button"
                        aria-label={"Open " + run.name}
                        to={
                          "/runs/" +
                          run.run_id +
                          "/" +
                          (isTerminal(run.status) ? "results" : "live")
                        }
                      >
                        <ArrowRight size={17} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
      <div className="methodology-footnote">
        <Info size={17} />
        <p>
          Results are specific to the dataset, versions, and hardware.
          Simulation is always labeled; publication requires independent case
          review.
        </p>
      </div>
    </div>
  );
}

export function Live() {
  const { runId = "" } = useParams();
  const query = useRun(runId),
    client = useQueryClient();
  const [events, setEvents] = useState<
    {
      id: string;
      type: string;
      case_id?: string;
      system_id?: string;
      suite?: string;
      error?: { message: string };
    }[]
  >([]);
  const [filter, setFilter] = useState("all");
  const [clock, setClock] = useState(Date.now());
  const cancel = useMutation({
    mutationFn: () => post("/runs/" + runId + "/cancel"),
    onSuccess: () => client.invalidateQueries({ queryKey: ["run", runId] }),
  });
  useEffect(() => {
    const timer = setInterval(() => setClock(Date.now()), 1000);
    return () => clearInterval(timer);
  }, []);
  useEffect(() => {
    const seen = new Set<string>();
    const source = new EventSource("/api/v1/runs/" + runId + "/events");
    const kinds = [
      "run.created",
      "validation.completed",
      "warmup.started",
      "warmup.completed",
      "suite.started",
      "case.started",
      "case.completed",
      "case.failed",
      "scoring.started",
      "scoring.completed",
      "run.completed",
      "run.cancelling",
      "run.cancelled",
      "run.failed",
    ];
    kinds.forEach((type) =>
      source.addEventListener(type, (event) => {
        const message = event as MessageEvent;
        if (seen.has(message.lastEventId)) return;
        seen.add(message.lastEventId);
        const data = JSON.parse(message.data);
        setEvents((previous) =>
          [{ id: message.lastEventId, type, ...data }, ...previous].slice(
            0,
            80,
          ),
        );
        if (type.startsWith("run.") || type.includes("scoring"))
          client.invalidateQueries({ queryKey: ["run", runId] });
        if (["run.completed", "run.cancelled", "run.failed"].includes(type)) {
          source.close();
          client.invalidateQueries({ queryKey: ["runs"] });
        }
      }),
    );
    return () => source.close();
  }, [runId, client]);
  const run = query.data;
  if (query.isLoading) return <Loading />;
  if (!run) return <ErrorBox error={query.error} />;
  const elapsed = Math.max(
    0,
    ((run.ended_at ? new Date(run.ended_at).getTime() : clock) -
      new Date(run.started_at).getTime()) /
      1000,
  );
  const done = isTerminal(run.status);
  const progress = run.progress.total
    ? run.progress.completed / run.progress.total
    : 0;
  const phases = ["validating", "warming", "running", "scoring", "completed"];
  return (
    <div className="page">
      <PageTitle
        title={run.name}
        description="Follow both systems from the same input to persisted evidence."
        action={
          done ? (
            <Link className="button primary" to={"/runs/" + runId + "/results"}>
              Explore results
              <ArrowRight size={17} />
            </Link>
          ) : (
            <BusyButton
              className="button secondary"
              busy={cancel.isPending}
              disabled={run.status === "cancelling"}
              onClick={() => cancel.mutate()}
            >
              Cancel evaluation
            </BusyButton>
          )
        }
      />
      {run.mode === "fake" && (
        <div className="notice">
          <FlaskConical size={18} />
          <p>
            Simulated outcomes — this run demonstrates the product, not either
            model’s performance.
          </p>
        </div>
      )}
      <ErrorBox error={query.error || cancel.error} />
      {run.warnings.map((w) => (
        <div className="notice" key={w}>
          <Info size={17} />
          <p>{w}</p>
        </div>
      ))}
      <Panel className="live-progress">
        <div className="live-topline">
          <Status value={run.status} />
          <span>
            <Clock3 size={15} /> {Math.floor(elapsed / 60)}m{" "}
            {Math.floor(elapsed % 60)}s elapsed
          </span>
        </div>
        <div className="progress-title">
          <h2>
            {done
              ? run.status === "completed"
                ? "Your evaluation is ready"
                : "Execution stopped; evidence preserved"
              : "Building your comparison"}
          </h2>
          <strong>
            {Math.round(progress * 100)}
            <span>%</span>
          </strong>
        </div>
        <div
          className="progress-track"
          role="progressbar"
          aria-label="Evaluation progress"
          aria-valuemin={0}
          aria-valuemax={run.progress.total || 1}
          aria-valuenow={run.progress.completed}
        >
          <motion.div
            animate={{ width: progress * 100 + "%" }}
            transition={{ duration: 0.3 }}
          />
        </div>
        <div className="progress-caption">
          <span>
            {run.progress.completed.toLocaleString()} /{" "}
            {run.progress.total.toLocaleString()} measured requests saved
          </span>
          <span>Warm-up excluded</span>
        </div>
        <ol className="phase-timeline">
          {phases.map((phase, index) => (
            <li
              className={index <= phases.indexOf(run.status) ? "reached" : ""}
              key={phase}
            >
              <span>
                {index < phases.indexOf(run.status) ? (
                  <CheckCircle2 size={16} />
                ) : (
                  index + 1
                )}
              </span>
              {label(phase)}
            </li>
          ))}
        </ol>
      </Panel>
      <div className="paired">
        {["jev", "laya"].map((key) => {
          const lane = run.progress.systems[key + "-" + run.track];
          return (
            <Panel
              key={key}
              title={systemName(key)}
              description={
                key === "jev"
                  ? "End-to-end API requests"
                  : "Local inference on the selected device"
              }
            >
              <div className="lane-total" style={{ color: color(key) }}>
                {lane?.completed ?? 0}
                <span> outcomes saved</span>
              </div>
              <div className="lane-stats">
                <div>
                  <span>Failures</span>
                  <strong>{lane?.failures ?? 0}</strong>
                </div>
                <div>
                  <span>Retries</span>
                  <strong>{lane?.retries ?? 0}</strong>
                </div>
                <div>
                  <span>Latest latency</span>
                  <strong>
                    {number(lane?.latency_ms, 0)}
                    <small> ms</small>
                  </strong>
                </div>
              </div>
              <p className="caption">
                {done
                  ? "Final metrics are calculated from saved evidence."
                  : "Counts are provisional until execution and scoring finish."}
              </p>
            </Panel>
          );
        })}
      </div>
      <Panel
        title="Activity"
        description="Events are saved with the run and replayed after reconnection."
        action={
          <select
            aria-label="Activity filter"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="all">All events</option>
            <option value="jev">Jev</option>
            <option value="laya">Laya</option>
            <option value="failed">Failures</option>
          </select>
        }
      >
        <div className="activity-list" aria-live="polite">
          {events
            .filter(
              (e) =>
                filter === "all" ||
                (filter === "failed"
                  ? e.type.includes("failed")
                  : e.system_id?.startsWith(filter)),
            )
            .slice(0, 25)
            .map((event) => (
              <div className="activity-event" key={event.id}>
                <span
                  className={
                    event.type.includes("failed") ? "error-text" : "muted"
                  }
                >
                  <Activity size={14} />
                </span>
                <div>
                  <strong>{label(event.type.replace(".", " "))}</strong>
                  <small>
                    {event.case_id || event.suite || "Run lifecycle"}{" "}
                    {event.error?.message}
                  </small>
                </div>
                {event.system_id && (
                  <span className="badge">{systemName(event.system_id)}</span>
                )}
                <span className="event-id">#{event.id}</span>
              </div>
            ))}
          {events.length === 0 && (
            <p className="muted">Connecting to the saved event stream…</p>
          )}
        </div>
      </Panel>
    </div>
  );
}

export function Methodology() {
  const { runId = "" } = useParams();
  const run = useRun(runId),
    summary = useSummary(runId, ""),
    datasets = useDatasets(),
    readiness = useReadiness();
  const client = useQueryClient();
  const [dataset, setDataset] = useState("benchmark");
  const [configuration, setConfiguration] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState<unknown>(null);
  const detail = useQuery({
    queryKey: ["dataset", dataset],
    queryFn: () => request<Dataset>("/datasets/" + dataset),
  });
  const calibrate = useMutation({
    mutationFn: () => post<Calibration>("/calibrations", { run_id: runId }),
    onSuccess: (r) => {
      setMessage("Calibration saved: " + r.calibration_id);
      client.invalidateQueries({ queryKey: ["calibrations"] });
    },
  });
  const rescore = useMutation({
    mutationFn: () =>
      post("/runs/" + runId + "/rescore", { scoring_version: "1.0.0" }),
    onSuccess: () => {
      setMessage("Metrics regenerated from immutable predictions.");
      client.invalidateQueries({ queryKey: ["summary", runId] });
    },
  });
  const freeze = useMutation({
    mutationFn: () =>
      post<Protocol>("/protocols", {
        dataset_id: dataset,
        configurations: JSON.parse(configuration),
      }),
    onSuccess: (r) => {
      setMessage("Both tracks frozen: " + r.protocol_id);
      client.invalidateQueries({ queryKey: ["protocols"] });
    },
  });
  async function importReview(file?: File) {
    if (!file) return;
    try {
      const value = JSON.parse(await file.text());
      const result = await post<{ approved: number; total: number }>(
        "/datasets/" + dataset + "/reviews",
        { reviews: Array.isArray(value) ? value : value.reviews },
      );
      setMessage(
        result.approved + " / " + result.total + " presentations approved.",
      );
      client.invalidateQueries({ queryKey: ["dataset", dataset] });
      setError(null);
    } catch (error) {
      setError(error);
    }
  }
  function prepareProtocol() {
    if (!run.data || !detail.data) return;
    const base = {
      ...run.data.effective_config,
      dataset_ref: dataset,
      dataset_digest: detail.data.digest,
      mode: "live",
      publication: true,
      acknowledge_remote: true,
      systems: {
        ...run.data.effective_config.systems,
        laya: {
          ...run.data.effective_config.systems?.laya,
          checkpoint_revision: readiness.data?.laya.revision,
        },
      },
      calibration_id: null,
      protocol_id: null,
    };
    setConfiguration(
      JSON.stringify(
        {
          default: { ...base, track: "default", instruction_overrides: {} },
          "production-tuned": { ...base, track: "production-tuned" },
        },
        null,
        2,
      ),
    );
  }
  if (run.isLoading || summary.isLoading) return <Loading />;
  return (
    <div className="page">
      <PageTitle
        title="Methodology & reproducibility"
        description="The conditions behind the numbers are part of the result."
      />
      <ErrorBox
        error={
          error ||
          run.error ||
          summary.error ||
          calibrate.error ||
          rescore.error ||
          freeze.error
        }
      />
      {message && (
        <div className="notice success" role="status">
          <CheckCircle2 size={18} />
          <p>{message}</p>
        </div>
      )}
      <div className="paired">
        <Panel title="Evaluation record">
          <dl className="record-list">
            <dt>Run</dt>
            <dd>{run.data?.run_id}</dd>
            <dt>Track</dt>
            <dd>{run.data?.track}</dd>
            <dt>Mode</dt>
            <dd>
              {run.data?.mode === "fake"
                ? "Simulation — illustrative"
                : "Live providers"}
            </dd>
            <dt>Dataset</dt>
            <dd>{run.data?.effective_config.dataset_ref}</dd>
            <dt>Scoring version</dt>
            <dd>{summary.data?.scoring_version}</dd>
            <dt>Publication</dt>
            <dd>
              {run.data?.publication
                ? "Review and protocol requirements satisfied"
                : "Not publication-qualified"}
            </dd>
          </dl>
          <p className="digest">{run.data?.dataset_digest}</p>
        </Panel>
        <Panel
          title="Export evidence"
          description="Reports include methodology, limitations, and the effective configuration."
        >
          <div className="export-list">
            {[
              ["markdown", "Markdown report"],
              ["html", "Standalone HTML report"],
              ["summary-json", "Summary JSON"],
              ["predictions-jsonl", "Prediction JSONL"],
              ["bundle", "Complete reproducibility bundle"],
            ].map(([format, title]) => (
              <a
                key={format}
                href={"/api/v1/runs/" + runId + "/exports/" + format}
              >
                <Download size={16} />
                {title}
                <ArrowRight size={14} />
              </a>
            ))}
          </div>
        </Panel>
      </div>
      <Panel title="Scoring definitions">
        <div className="definitions">
          {Object.entries(summary.data?.definitions || {}).map(
            ([key, value]) => (
              <div key={key}>
                <h3>{label(key)}</h3>
                <p>{value}</p>
              </div>
            ),
          )}
        </div>
        <BusyButton
          className="button secondary"
          busy={rescore.isPending}
          onClick={() => rescore.mutate()}
        >
          Rebuild metrics from artifacts
        </BusyButton>
      </Panel>
      <Panel
        title="Development calibration"
        description="Fit temperature scaling and an observed-risk threshold from an uncalibrated development run. Keep its prompts and model configuration for evaluation."
      >
        <BusyButton
          className="button secondary"
          busy={calibrate.isPending}
          onClick={() => calibrate.mutate()}
        >
          <Activity size={16} />
          Fit calibration from this run
        </BusyButton>
        <p className="caption">
          The artifact retains its source mode and dataset digest.
          Simulation-derived calibration cannot be used for live evaluation.
        </p>
      </Panel>
      <Panel
        title="Independent review & publication"
        description="Publication is a data milestone. Every presentation needs an independent review before either track is frozen."
      >
        <label>
          Collection to review
          <select value={dataset} onChange={(e) => setDataset(e.target.value)}>
            {datasets.data?.items.map((d) => (
              <option key={d.dataset_id} value={d.dataset_id}>
                {d.name}
              </option>
            ))}
          </select>
        </label>
        <div className="review-progress">
          <FileCheck2 size={20} />
          <strong>
            {detail.data?.review?.approved ?? 0} /{" "}
            {detail.data?.review?.total ?? 0} presentations reviewed
          </strong>
          <span className="badge">
            {detail.data?.review?.complete
              ? "Ready to freeze"
              : "Review required"}
          </span>
        </div>
        <div className="action-row">
          <a
            className="button secondary"
            href={"/api/v1/datasets/" + dataset + "/review-packet"}
            download="blind-review-packet.json"
          >
            <Download size={16} />
            Download blind review packet
          </a>
          <label className="button secondary">
            <Upload size={16} />
            Import independent reviews
            <input
              className="file-control"
              type="file"
              accept=".json"
              aria-label="Import independent reviews"
              onChange={(e) => importReview(e.target.files?.[0])}
            />
          </label>
        </div>
        <details>
          <summary>Review format and disagreement handling</summary>
          <p>
            Return a JSON array with case_id, reviewer, answer, and rationale.
            Reviewer answers retain their native primitive type. Disagreements
            require a distinct adjudicator, adjudicated_answer, and
            adjudication_rationale. Correcting gold labels requires importing
            and reviewing a new dataset.
          </p>
          <JsonBlock
            value={[
              {
                case_id: "example-choice-base",
                reviewer: "Independent reviewer name",
                answer: "billing",
                rationale: "The policy routes duplicate payments to Billing.",
              },
            ]}
          />
        </details>
        <div className="freeze-panel">
          <h3>
            <LockKeyhole size={17} />
            Freeze both tracks together
          </h3>
          <p>
            Pin the Default and Production-tuned configurations before exposing
            sealed outcomes. Once executed, a frozen track cannot be replaced.
          </p>
          <button className="button secondary" onClick={prepareProtocol}>
            Prepare configuration pair
          </button>
          {configuration && (
            <>
              <label>
                Frozen configurations
                <textarea
                  className="config-editor"
                  aria-label="Frozen configurations"
                  value={configuration}
                  onChange={(e) => setConfiguration(e.target.value)}
                />
              </label>
              <BusyButton
                className="button primary"
                busy={freeze.isPending}
                onClick={() => freeze.mutate()}
              >
                Freeze reviewed protocol
              </BusyButton>
            </>
          )}
        </div>
      </Panel>
      <Panel title="Limitations">
        {summary.data?.limitations.map((text) => (
          <p className="limitation" key={text}>
            <Info size={16} />
            {text}
          </p>
        ))}
      </Panel>
      <details className="panel">
        <summary>Full configuration and hardware</summary>
        <JsonBlock
          value={{
            configuration: run.data?.effective_config,
            environment: Object.values(summary.data?.systems || {})[0]
              ?.resources,
          }}
        />
      </details>
    </div>
  );
}
