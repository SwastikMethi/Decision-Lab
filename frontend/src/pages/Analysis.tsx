import { useMemo, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type ColumnDef,
  type SortingState,
} from "@tanstack/react-table";
import {
  ArrowDownUp,
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  CircleHelp,
  FlaskConical,
  Info,
  Search,
  X,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import {
  color,
  filterQuery,
  label,
  number,
  pct,
  request,
  systemName,
  useRun,
  useRuns,
  useSummary,
} from "../api";
import {
  Empty,
  ErrorBox,
  EvidenceDrawer,
  Filters,
  InspectButton,
  Loading,
  PageTitle,
  Panel,
  RiskControl,
} from "../components";
import type { CaseRow, Summary, SystemMetrics } from "../types";

const percentTick = (value: number) => Math.round(value * 100) + "%";
function LegendNames() {
  return (
    <div className="chart-legend">
      {["jev", "laya"].map((key) => (
        <span key={key}>
          <i style={{ background: color(key) }} />
          {systemName(key)}
        </span>
      ))}
    </div>
  );
}

export default function Analysis() {
  const { runId = "", view = "results" } = useParams();
  const [params, setParams] = useSearchParams();
  const filters = filterQuery(params),
    query = useSummary(runId, filters),
    manifest = useRun(runId);
  const [evidenceError, setEvidenceError] = useState<unknown>(null);
  async function inspect(extra: Record<string, string> = {}) {
    const next = new URLSearchParams(filters);
    Object.entries(extra).forEach(([key, value]) => next.set(key, value));
    try {
      const response = await request<{ items: CaseRow[] }>(
        "/runs/" + runId + "/cases?" + next.toString() + "&page_size=1",
      );
      if (response.items[0]) {
        next.set("case", response.items[0].case.id);
        setParams(next);
      } else {
        setEvidenceError(
          new Error(
            "No cases match that chart selection. Clear a filter and try again.",
          ),
        );
      }
    } catch (error) {
      setEvidenceError(error);
    }
  }
  const titles: Record<string, [string, string]> = {
    results: ["Results overview", "Read the tradeoffs. Follow the evidence."],
    reliability: [
      "Reliability & automation",
      "Confidence is useful only when it corresponds to correctness.",
    ],
    robustness: [
      "Behavioral robustness",
      "The same decision should survive a different presentation.",
    ],
    cases: [
      "Case explorer",
      "Every input, outcome, and failure — side by side.",
    ],
  };
  const [title, description] = titles[view] || titles.results;
  const summary = query.data;
  return (
    <div className="page analysis-page">
      <PageTitle
        title={title}
        description={description}
        action={<LegendNames />}
      />
      {manifest.data?.mode === "fake" && (
        <div className="notice">
          <FlaskConical size={18} />
          <p>
            <strong>Simulated outcomes.</strong> These measurements demonstrate
            the interface and are not evidence about either provider.
          </p>
        </div>
      )}
      {summary?.partial && (
        <div className="notice">
          <Info size={18} />
          <p>
            This is a partial run. Missing primary outcomes count as incorrect;
            conclusions are provisional.
          </p>
        </div>
      )}
      {summary?.sealed_results_withheld && (
        <div className="notice">
          <Info size={18} />
          <p>Sealed outcomes are withheld until both frozen tracks complete.</p>
        </div>
      )}
      <Filters
        domains={view === "cases" || view === "robustness"}
        domainOptions={summary?.filter_options.domains || []}
      />
      <ErrorBox error={query.error || evidenceError} />
      {query.isLoading ? (
        <Loading />
      ) : (
        summary && (
          <>
            <div className="analysis-context">
              <span>
                {summary.counts.cases.toLocaleString()} presentations ·{" "}
                {summary.counts.families.toLocaleString()} base families
              </span>
              <span>
                {summary.provisional
                  ? "Provisional measurements"
                  : "Scored from stored artifacts"}{" "}
                · v{summary.scoring_version}
              </span>
            </div>
            {view === "results" && (
              <Results summary={summary} runId={runId} inspect={inspect} />
            )}
            {view === "reliability" && (
              <Reliability summary={summary} inspect={inspect} />
            )}
            {view === "robustness" && (
              <Robustness summary={summary} inspect={inspect} />
            )}
            {view === "cases" && <Cases runId={runId} />}
          </>
        )
      )}
      <EvidenceDrawer runId={runId} />
    </div>
  );
}

function Results({
  summary,
  runId,
  inspect,
}: {
  summary: Summary;
  runId: string;
  inspect: (filters?: Record<string, string>) => void;
}) {
  const systems = Object.entries(summary.systems);
  const allRuns = useRuns(),
    [compare, setCompare] = useState("");
  const comparison = useQuery({
    queryKey: ["comparison", runId, compare],
    queryFn: () =>
      request<{ left: Summary; right: Summary }>(
        "/runs/" + runId + "/comparison/" + compare,
      ),
    enabled: !!compare,
  });
  const kpis: {
    title: string;
    description: string;
    read: (m: SystemMetrics) => number | null;
    format: (n: number | null) => string;
  }[] = [
    {
      title: "End-to-end correctness",
      description: "All scheduled primary decisions",
      read: (m) => m.correctness.accuracy.value,
      format: pct,
    },
    {
      title: "Brier score",
      description: "Probability error · lower is better",
      read: (m) => m.calibration.brier.value,
      format: (v) => number(v, 3),
    },
    {
      title: "Coverage at ≤2% risk",
      description: "Observed operating point",
      read: (m) =>
        m.selective_automation.operating_points[1]?.point?.coverage ?? null,
      format: pct,
    },
    {
      title: "Warm p50 latency",
      description: "End-to-end milliseconds",
      read: (m) => m.performance.warm_p50_ms,
      format: (v) => number(v, 1),
    },
    {
      title: "Cost / 1,000 decisions",
      description: "USD · reported or estimated API cost",
      read: (m) => m.cost.per_1000_decisions_usd,
      format: (v) => (v === null ? "Unavailable" : "$" + number(v, 4)),
    },
    {
      title: "Failure rate",
      description: "Missing and invalid outputs included",
      read: (m) => m.failures.rate,
      format: pct,
    },
  ];
  const primitives = ["choice", "noul", "score"].filter((primitive) =>
    summary.slices.some(
      (s) => s.dimension === "primitive" && s.value === primitive,
    ),
  );
  const primitiveData = primitives.map((primitive) => {
    const row: Record<string, string | number | null> = {
      primitive: label(primitive),
    };
    systems.forEach(([id]) => {
      const slice = summary.slices.find(
        (s) =>
          s.system_id === id &&
          s.dimension === "primitive" &&
          s.value === primitive,
      );
      row[systemName(id)] = slice?.metrics.correctness.accuracy.value ?? null;
    });
    return row;
  });
  const domains = [
    ...new Set(
      summary.slices
        .filter((s) => s.dimension === "domain")
        .map((s) => s.value),
    ),
  ];
  return (
    <>
      <div className="kpi-grid">
        {kpis.map((kpi) => (
          <div className="kpi" key={kpi.title}>
            <h2>
              {kpi.title}
              <CircleHelp size={13} />
            </h2>
            <div className="kpi-values">
              {systems.map(([id, metrics]) => (
                <div key={id}>
                  <span>{systemName(id)}</span>
                  <strong
                    className={
                      kpi.read(metrics) === null ? "unavailable" : undefined
                    }
                  >
                    {kpi.format(kpi.read(metrics))}
                  </strong>
                </div>
              ))}
            </div>
            <p>{kpi.description}</p>
          </div>
        ))}
      </div>
      <div className="findings-strip">
        <span className="findings-icon">
          <Info size={19} />
        </span>
        <div>
          <h2>What this run tells you</h2>
          {summary.findings.length ? (
            summary.findings.map((f) => (
              <button key={f.text} onClick={() => inspect(f.filters)}>
                {f.text}
                <ArrowRight size={14} />
              </button>
            ))
          ) : (
            <p>Add more eligible cases to compare workload slices.</p>
          )}
          <small>
            Exploratory descriptions, not claims of statistical superiority.
          </small>
        </div>
      </div>
      <div className="chart-grid">
        <Panel
          title="Correctness by primitive"
          description="Same presentations, compared within each decision type."
          action={<InspectButton onClick={() => inspect()} />}
        >
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart
                data={primitiveData}
                margin={{ top: 8, right: 12, left: -10, bottom: 0 }}
              >
                <CartesianGrid strokeDasharray="3 3" vertical={false} />
                <XAxis dataKey="primitive" axisLine={false} tickLine={false} />
                <YAxis
                  domain={[0, 1]}
                  tickFormatter={percentTick}
                  axisLine={false}
                  tickLine={false}
                />
                <Tooltip formatter={(value) => pct(Number(value))} />
                <Bar
                  dataKey="Jev"
                  fill={color("jev")}
                  radius={[4, 4, 0, 0]}
                  barSize={30}
                  isAnimationActive={false}
                  onClick={(_, index) =>
                    inspect({ primitive: primitives[index] })
                  }
                />
                <Bar
                  dataKey="Laya"
                  fill={color("laya")}
                  radius={[4, 4, 0, 0]}
                  barSize={30}
                  isAnimationActive={false}
                  onClick={(_, index) =>
                    inspect({ primitive: primitives[index] })
                  }
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
          <p className="caption">
            Each bar includes provider failures in its denominator. Select a bar
            to inspect its cases.
          </p>
        </Panel>
        <Panel
          title="Quality and latency"
          description="A deployment tradeoff, not a single leaderboard."
          action={<InspectButton onClick={() => inspect()} />}
        >
          <div className="chart">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ left: 4, right: 20, bottom: 8 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="latency"
                  name="Warm p50"
                  unit=" ms"
                  tickLine={false}
                />
                <YAxis
                  type="number"
                  dataKey="accuracy"
                  name="Correctness"
                  domain={[0, 1]}
                  tickFormatter={percentTick}
                  tickLine={false}
                />
                <Tooltip
                  formatter={(v, name) =>
                    name === "Correctness"
                      ? pct(Number(v))
                      : number(Number(v), 2) + " ms"
                  }
                />
                {systems
                  .filter(([, m]) => m.performance.warm_p50_ms !== null)
                  .map(([id, m]) => (
                    <Scatter
                      key={id}
                      name={systemName(id)}
                      data={[
                        {
                          latency: m.performance.warm_p50_ms,
                          accuracy: m.correctness.accuracy.value,
                        },
                      ]}
                      fill={color(id)}
                      isAnimationActive={false}
                      onClick={() => inspect()}
                    />
                  ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <p className="caption">
            Jev includes a network round trip. Laya reflects this machine’s
            local runtime.
          </p>
        </Panel>
      </div>
      <Panel
        title="Performance by domain"
        description="Select a workload to explore the decisions behind its aggregate."
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Domain</th>
                {systems.map(([id]) => (
                  <th key={id}>{systemName(id)} correctness</th>
                ))}
                <th>Cases</th>
              </tr>
            </thead>
            <tbody>
              {domains.map((domain) => (
                <tr key={domain}>
                  <td>
                    <button
                      className="text-button"
                      onClick={() => inspect({ domain })}
                    >
                      {label(domain)}
                      <ArrowRight size={14} />
                    </button>
                  </td>
                  {systems.map(([id]) => {
                    const value = summary.slices.find(
                      (s) =>
                        s.system_id === id &&
                        s.dimension === "domain" &&
                        s.value === domain,
                    )?.metrics.correctness.accuracy;
                    return (
                      <td key={id}>
                        <div className="inline-metric">
                          <div className="inline-track">
                            <i
                              style={{
                                width: (value?.value ?? 0) * 100 + "%",
                                background: color(id),
                              }}
                            />
                          </div>
                          <strong>{pct(value?.value)}</strong>
                        </div>
                        <small className="cell-note">
                          {value?.numerator}/{value?.denominator} correct
                        </small>
                      </td>
                    );
                  })}
                  <td>
                    {
                      summary.slices.find(
                        (s) => s.dimension === "domain" && s.value === domain,
                      )?.count
                    }
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel
        title="Paired uncertainty"
        description="95% bootstrap intervals resample whole families, retaining their variants."
      >
        {summary.comparisons.map((c) => (
          <div className="comparison-row" key={c.metric}>
            <span>
              {systemName(c.left)} minus {systemName(c.right)} accuracy
            </span>
            <strong>
              {c.difference === null
                ? "Unavailable"
                : (c.difference * 100).toFixed(1) + " percentage points"}
            </strong>
            <span>
              95% interval:{" "}
              {c.ci95
                ? c.ci95.map((v) => (v * 100).toFixed(1)).join(" to ") + " pp"
                : "Unavailable"}
            </span>
            <span>{c.families} families</span>
          </div>
        ))}
      </Panel>
      <Performance summary={summary} />
      <Panel
        title="Compare compatible runs"
        description="Only the same dataset, track, scoring version, and execution mode can be compared."
      >
        <label>
          Earlier evaluation
          <select value={compare} onChange={(e) => setCompare(e.target.value)}>
            <option value="">Choose a run</option>
            {allRuns.data?.items
              .filter((r) => r.run_id !== runId)
              .map((r) => (
                <option value={r.run_id} key={r.run_id}>
                  {r.name} — {r.track}
                </option>
              ))}
          </select>
        </label>
        <ErrorBox error={comparison.error} />
        {comparison.data && (
          <div className="paired">
            {Object.entries(comparison.data).map(([side, data]) => (
              <div key={side}>
                <h3>
                  {side === "left"
                    ? "Current evaluation"
                    : "Selected evaluation"}
                </h3>
                {Object.entries(data.systems).map(([id, m]) => (
                  <p key={id}>
                    {systemName(id)}: {pct(m.correctness.accuracy.value)} (
                    {m.correctness.accuracy.numerator}/
                    {m.correctness.accuracy.denominator})
                  </p>
                ))}
              </div>
            ))}
          </div>
        )}
      </Panel>
    </>
  );
}

function Reliability({
  summary,
  inspect,
}: {
  summary: Summary;
  inspect: () => void;
}) {
  const systems = Object.entries(summary.systems);
  return (
    <>
      <div className="chart-grid">
        <Panel
          title="Calibration"
          description="Well-calibrated predictions track the diagonal."
          action={<InspectButton onClick={inspect} />}
        >
          <div className="chart tall">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ left: 0, right: 15, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  type="number"
                  dataKey="confidence"
                  name="Mean confidence"
                  domain={[0, 1]}
                  tickFormatter={percentTick}
                />
                <YAxis
                  type="number"
                  dataKey="accuracy"
                  name="Observed accuracy"
                  domain={[0, 1]}
                  tickFormatter={percentTick}
                />
                <ReferenceLine
                  segment={[
                    { x: 0, y: 0 },
                    { x: 1, y: 1 },
                  ]}
                  stroke="#94a3b8"
                  strokeDasharray="5 5"
                />
                <Tooltip formatter={(value) => pct(Number(value))} />
                {systems.map(([id, m]) => (
                  <Scatter
                    key={id}
                    name={systemName(id)}
                    data={m.calibration.bins.filter((b) => b.count > 0)}
                    fill={color(id)}
                    line
                    isAnimationActive={false}
                  />
                ))}
              </ScatterChart>
            </ResponsiveContainer>
          </div>
          <p className="caption">
            Top-label confidence is compared with actual correctness. Empty bins
            are omitted, not treated as zero.
          </p>
          <div className="paired">
            {systems.map(([id, m]) => (
              <div key={id}>
                <span className="model-name">
                  <i style={{ background: color(id) }} />
                  {systemName(id)}
                </span>
                <p>
                  ECE <strong>{number(m.calibration.ece.value, 3)}</strong> ·
                  Brier <strong>{number(m.calibration.brier.value, 3)}</strong>
                </p>
                <small>
                  {m.calibration.ece.denominator} valid;{" "}
                  {m.calibration.excluded} excluded failures
                </small>
              </div>
            ))}
          </div>
        </Panel>
        <Panel
          title="Risk–coverage"
          description="How much work can be accepted at each observed error level?"
          action={<InspectButton onClick={inspect} />}
        >
          <div className="chart tall">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart margin={{ left: 0, right: 15, bottom: 10 }}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="coverage"
                  type="number"
                  domain={[0, 1]}
                  tickFormatter={percentTick}
                />
                <YAxis
                  dataKey="risk"
                  type="number"
                  domain={[0, 1]}
                  tickFormatter={percentTick}
                />
                <Tooltip
                  formatter={(value) => pct(Number(value))}
                  labelFormatter={(v) => "Coverage " + pct(Number(v))}
                />
                {systems.map(([id, m]) => (
                  <Line
                    key={id}
                    name={systemName(id)}
                    data={m.selective_automation.curve}
                    dataKey="risk"
                    type="stepAfter"
                    stroke={color(id)}
                    strokeWidth={2}
                    dot={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
          <p className="caption">
            Coverage denominator includes failures. Lower risk at higher
            coverage is preferable for this dataset.
          </p>
        </Panel>
      </div>
      <Panel title="Choose an operating point">
        <RiskControl
          systems={Object.fromEntries(
            systems.map(([id, m]) => [id, m.selective_automation.curve]),
          )}
        />
      </Panel>
      <div className="chart-grid">
        {systems.map(([id, m]) => (
          <Panel
            key={id}
            title={`${systemName(id)} confidence distribution`}
            description={`${m.calibration.ece.denominator} valid decisions, grouped by selected-outcome probability.`}
            action={<InspectButton onClick={inspect} />}
          >
            <div className="chart">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={m.calibration.confidence_histogram.map((b) => ({
                    ...b,
                    band: `${Math.round(b.lower * 100)}–${Math.round(b.upper * 100)}%`,
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" vertical={false} />
                  <XAxis dataKey="band" tick={{ fontSize: 10 }} interval={1} />
                  <YAxis allowDecimals={false} width={35} />
                  <Tooltip />
                  <Legend />
                  <Bar
                    dataKey="correct"
                    name="Correct"
                    stackId="outcome"
                    fill={color(id)}
                    isAnimationActive={false}
                  />
                  <Bar
                    dataKey="incorrect"
                    name="Incorrect"
                    stackId="outcome"
                    fill="#e66c70"
                    isAnimationActive={false}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
            {m.selective_automation.frozen_policy && (
              <p className="caption">
                Frozen development policy:{" "}
                {m.selective_automation.frozen_policy.accepted}/
                {m.selective_automation.frozen_policy.denominator} accepted;{" "}
                {pct(m.selective_automation.frozen_policy.risk)} observed risk.
                This threshold was fixed before evaluation.
              </p>
            )}
          </Panel>
        ))}
      </div>
      <Panel title="Thresholds and escalations">
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>System</th>
                <th>Threshold</th>
                <th>Accepted / total</th>
                <th>Coverage</th>
                <th>Observed risk</th>
                <th>Escalations</th>
                <th>Stability</th>
              </tr>
            </thead>
            <tbody>
              {systems.flatMap(([id, m]) =>
                m.selective_automation.thresholds.map((p) => (
                  <tr key={id + p.threshold}>
                    <td>
                      <span className="model-name">
                        <i style={{ background: color(id) }} />
                        {systemName(id)}
                      </span>
                    </td>
                    <td>{p.threshold.toFixed(2)}</td>
                    <td>
                      {p.accepted}/{p.denominator}
                    </td>
                    <td>{pct(p.coverage)}</td>
                    <td>{pct(p.risk)}</td>
                    <td>{p.escalations}</td>
                    <td>
                      {p.unstable ? (
                        <span className="warning-text">Small sample</span>
                      ) : (
                        "30+ accepted"
                      )}
                    </td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel
        title="Calibration bins"
        description="Every plotted calibration point retains its denominator."
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>System</th>
                <th>Confidence interval</th>
                <th>Count</th>
                <th>Mean confidence</th>
                <th>Observed accuracy</th>
              </tr>
            </thead>
            <tbody>
              {systems.flatMap(([id, m]) =>
                m.calibration.bins.map((b) => (
                  <tr key={id + b.lower}>
                    <td>{systemName(id)}</td>
                    <td>
                      {pct(b.lower)}–{pct(b.upper)}
                    </td>
                    <td>{b.count}</td>
                    <td>{pct(b.confidence)}</td>
                    <td>{pct(b.accuracy)}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </Panel>
    </>
  );
}

function Robustness({
  summary,
  inspect,
}: {
  summary: Summary;
  inspect: (filters?: Record<string, string>) => void;
}) {
  const systems = Object.entries(summary.systems);
  const transformations = [
    ...new Set(systems.flatMap(([, m]) => m.robustness.map((r) => r.variant))),
  ];
  return (
    <>
      <Panel
        title="Transformation sensitivity"
        description="Harmful flips: a correct base outcome becomes incorrect after a meaning-preserving change."
      >
        <div className="table-wrap">
          <table className="heatmap">
            <thead>
              <tr>
                <th>Transformation</th>
                {systems.map(([id]) => (
                  <th key={id}>{systemName(id)}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {transformations.map((variant) => (
                <tr key={variant}>
                  <td>{label(variant)}</td>
                  {systems.map(([id, m]) => (
                    <td key={id}>
                      <div className="heatmap-cells">
                        {m.robustness
                          .filter((r) => r.variant === variant)
                          .map((row) => (
                            <button
                              key={row.primitive}
                              onClick={() =>
                                inspect({ variant, primitive: row.primitive })
                              }
                              style={{
                                background:
                                  "rgba(244,63,94," +
                                  (0.035 + row.harmful_flip_rate * 0.28) +
                                  ")",
                              }}
                            >
                              <span>{label(row.primitive)}</span>
                              <strong>{pct(row.harmful_flip_rate)}</strong>
                              <small>
                                {row.comparable_count}/{row.count} pairs
                              </small>
                            </button>
                          ))}
                      </div>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="caption">
          Choice-only transformations are not imposed on Noul or ordered Score
          levels. Missing pairs stay visible.
        </p>
      </Panel>
      <Panel
        title="Aligned probability drift"
        description="Semantic outcome mappings prevent opaque labels or option order from creating artificial differences."
      >
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>System</th>
                <th>Transformation</th>
                <th>Primitive</th>
                <th>Answer flips</th>
                <th>Beneficial flips</th>
                <th>Accuracy delta</th>
                <th>Mean JS divergence</th>
                <th>Missing pairs</th>
              </tr>
            </thead>
            <tbody>
              {systems.flatMap(([id, m]) =>
                m.robustness.map((row) => (
                  <tr key={id + row.variant + row.primitive}>
                    <td>{systemName(id)}</td>
                    <td>
                      <button
                        className="text-button"
                        onClick={() =>
                          inspect({
                            variant: row.variant,
                            primitive: row.primitive,
                          })
                        }
                      >
                        {label(row.variant)}
                      </button>
                    </td>
                    <td>{label(row.primitive)}</td>
                    <td>{pct(row.answer_flip_rate)}</td>
                    <td>{pct(row.beneficial_flip_rate)}</td>
                    <td>{pct(row.accuracy_delta)}</td>
                    <td>{number(row.probability_drift.value, 4)}</td>
                    <td>{row.missing_pairs}</td>
                  </tr>
                )),
              )}
            </tbody>
          </table>
        </div>
      </Panel>
      <div className="paired">
        {["context_length", "option_cardinality"].map((variant) => (
          <Panel
            key={variant}
            title={label(variant) + " diagnostic"}
            description="Reported separately from invariance and primary accuracy."
          >
            {systems.every(
              ([, m]) => !m.diagnostics.some((d) => d.variant === variant),
            ) ? (
              <Empty title="This diagnostic was not selected">
                Enable it in the Suites step of a new evaluation.
              </Empty>
            ) : (
              <>
                <div className="chart">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart margin={{ right: 20 }}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis
                        dataKey="bucket"
                        type="number"
                        domain={["dataMin", "dataMax"]}
                      />
                      <YAxis
                        domain={[0, 1]}
                        tickFormatter={percentTick}
                        width={42}
                      />
                      <Tooltip formatter={(value) => pct(Number(value))} />
                      <Legend />
                      {systems.map(([id, m]) => (
                        <Line
                          key={id}
                          data={m.diagnostics.filter(
                            (d) => d.variant === variant,
                          )}
                          dataKey="accuracy"
                          name={systemName(id)}
                          stroke={color(id)}
                          strokeWidth={2}
                          isAnimationActive={false}
                        />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                </div>
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>System</th>
                        <th>Bucket</th>
                        <th>Correctness</th>
                        <th>Failures / total</th>
                      </tr>
                    </thead>
                    <tbody>
                      {systems.flatMap(([id, m]) =>
                        m.diagnostics
                          .filter((d) => d.variant === variant)
                          .map((d) => (
                            <tr key={id + d.bucket}>
                              <td>{systemName(id)}</td>
                              <td>{d.bucket}</td>
                              <td>{pct(d.accuracy)}</td>
                              <td>
                                {d.failures}/{d.count}
                              </td>
                            </tr>
                          )),
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </Panel>
        ))}
      </div>
      <Panel
        title="Repeatability"
        description="Repeated calls never reweight the primary accuracy denominator."
      >
        {systems.every(([, m]) => !m.repeatability.length) ? (
          <Empty title="No repeatability calls in this run">
            Enable Repeatability to measure fresh-call label flips and
            probability variation.
          </Empty>
        ) : (
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>System</th>
                  <th>Case</th>
                  <th>Valid / calls</th>
                  <th>Modal agreement</th>
                  <th>Any flip</th>
                  <th>Mean probability σ</th>
                  <th>Mean JS</th>
                </tr>
              </thead>
              <tbody>
                {systems.flatMap(([id, m]) =>
                  m.repeatability.map((r) => (
                    <tr key={id + r.case_id}>
                      <td>{systemName(id)}</td>
                      <td>{r.case_id}</td>
                      <td>
                        {r.valid}/{r.calls}
                      </td>
                      <td>{pct(r.modal_agreement)}</td>
                      <td>
                        {r.any_flip === null
                          ? "Unavailable"
                          : r.any_flip
                            ? "Yes"
                            : "No"}
                      </td>
                      <td>{number(r.mean_probability_std, 4)}</td>
                      <td>{number(r.mean_js_divergence, 4)}</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}

function Performance({ summary }: { summary: Summary }) {
  const systems = Object.entries(summary.systems);
  return (
    <Panel
      title="Operations & performance"
      description="Warm latency, observed failures, and deployment resources."
    >
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Measure</th>
              {systems.map(([id]) => (
                <th key={id}>{systemName(id)}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[
              [
                "Cold start & warm-up",
                (m: SystemMetrics) =>
                  number(m.performance.warmup?.cold_start_ms) + " ms",
              ],
              [
                "Warm p50",
                (m: SystemMetrics) => number(m.performance.warm_p50_ms) + " ms",
              ],
              [
                "Warm p95",
                (m: SystemMetrics) => number(m.performance.warm_p95_ms) + " ms",
              ],
              [
                "Warm p99",
                (m: SystemMetrics) => number(m.performance.warm_p99_ms) + " ms",
              ],
              [
                "Failed primary decisions",
                (m: SystemMetrics) =>
                  m.failures.count + " / " + m.failures.denominator,
              ],
              ["Retries", (m: SystemMetrics) => String(m.failures.retries)],
              [
                "Observed peak process RAM",
                (m: SystemMetrics) =>
                  m.resources?.peak_process_ram_bytes
                    ? number(
                        Number(m.resources.peak_process_ram_bytes) / 1024 ** 3,
                      ) + " GiB"
                    : "Unavailable",
              ],
            ].map(([title, read]) => (
              <tr key={title as string}>
                <td>{title as string}</td>
                {systems.map(([id, m]) => (
                  <td key={id}>{(read as (m: SystemMetrics) => string)(m)}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <p className="caption">
        Process RAM is observed for the application and its local worker
        together, not attributed to the remote provider.
      </p>
      {systems.some(([, m]) => m.performance.load_tests.length > 0) && (
        <>
          <h3>Separate load tests</h3>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>System</th>
                  <th>Client concurrency</th>
                  <th>Questions / request</th>
                  <th>Requests</th>
                  <th>Throughput</th>
                  <th>Failures</th>
                  <th>Queue p50</th>
                </tr>
              </thead>
              <tbody>
                {systems.flatMap(([id, m]) =>
                  m.performance.load_tests.map((t) => (
                    <tr key={id + t.concurrency + "-" + t.batch_size}>
                      <td>{systemName(id)}</td>
                      <td>{t.concurrency}</td>
                      <td>{t.batch_size}</td>
                      <td>{t.count}</td>
                      <td>{number(t.questions_per_second)} questions/s</td>
                      <td>{t.failures}</td>
                      <td>{number(t.queue_p50_ms)} ms</td>
                    </tr>
                  )),
                )}
              </tbody>
            </table>
          </div>
          <p className="caption">
            Batches contain questions sharing one state. Laya serializes model
            access; client concurrency can increase queueing.
          </p>
        </>
      )}
    </Panel>
  );
}

function Cases({ runId }: { runId: string }) {
  const [params, setParams] = useSearchParams();
  const [sorting, setSorting] = useState<SortingState>([]);
  const page = Math.max(1, Number(params.get("page") || 1));
  const filters = filterQuery(params);
  const query = useQuery({
    queryKey: ["cases", runId, filters, page],
    queryFn: () =>
      request<{ items: CaseRow[]; total: number }>(
        "/runs/" + runId + "/cases?" + filters + "&page=" + page,
      ),
  });
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    if (key !== "page") next.delete("page");
    setParams(next);
  };
  const columns = useMemo<ColumnDef<CaseRow>[]>(
    () => [
      {
        id: "case",
        accessorFn: (row) => row.case.id,
        header: "Case / family",
        cell: ({ row }) => (
          <div>
            <button
              className="case-link"
              aria-label={"Inspect case " + row.original.case.id}
              onClick={() => update("case", row.original.case.id)}
            >
              {row.original.case.id}
              <ArrowRight size={13} />
            </button>
            <small className="cell-note">
              {label(row.original.case.domain)}
            </small>
          </div>
        ),
      },
      {
        id: "primitive",
        accessorFn: (row) => row.case.primitive,
        header: "Primitive",
        cell: ({ getValue }) => (
          <span className="badge">{label(String(getValue()))}</span>
        ),
      },
      {
        id: "variant",
        accessorFn: (row) => row.case.variant,
        header: "Presentation",
        cell: ({ getValue }) => label(String(getValue())),
      },
      {
        id: "expected",
        accessorFn: (row) => String(row.case.expected.value),
        header: "Expected",
      },
      ...["jev", "laya"].map((key) => ({
        id: key,
        accessorFn: (row: CaseRow) =>
          row.predictions[key]?.answer?.selected ?? "",
        header: systemName(key),
        cell: ({ row }: { row: { original: CaseRow } }) => {
          const p = row.original.predictions[key];
          return (
            <div className="outcome">
              <span
                className={
                  row.original.correctness[key]
                    ? "success-text"
                    : p
                      ? "error-text"
                      : "muted"
                }
              >
                {p ? (
                  row.original.correctness[key] ? (
                    <Check size={13} />
                  ) : (
                    <X size={13} />
                  )
                ) : null}
                {p?.answer?.selected ?? (p ? "Failed" : "Pending")}
              </span>
              <small>
                {p?.answer
                  ? pct(p.answer.decision_probability) +
                    " · " +
                    number(p.timing.latency_ms, 0) +
                    " ms"
                  : p?.error?.category}
              </small>
            </div>
          );
        },
      })),
      {
        id: "disagreement",
        accessorFn: (row) => row.disagreement,
        header: "Comparison",
        cell: ({ getValue }) =>
          getValue() ? (
            <span className="badge warning">Disagreed</span>
          ) : (
            <span className="muted">Aligned</span>
          ),
      },
    ],
    [params.toString()],
  );
  const table = useReactTable({
    data: query.data?.items || [],
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });
  return (
    <Panel>
      <div className="case-toolbar">
        <label className="search-input">
          <Search size={17} />
          <input
            aria-label="Search cases"
            placeholder="Search state, policy, or case ID…"
            value={params.get("q") || ""}
            onChange={(e) => update("q", e.target.value)}
          />
        </label>
        <label>
          Jev outcome
          <select
            value={params.get("jev_correct") || ""}
            onChange={(e) => update("jev_correct", e.target.value)}
          >
            <option value="">All</option>
            <option value="true">Correct</option>
            <option value="false">Incorrect or failed</option>
          </select>
        </label>
        <label>
          Laya outcome
          <select
            value={params.get("laya_correct") || ""}
            onChange={(e) => update("laya_correct", e.target.value)}
          >
            <option value="">All</option>
            <option value="true">Correct</option>
            <option value="false">Incorrect or failed</option>
          </select>
        </label>
      </div>
      <details>
        <summary>Confidence and failure filters</summary>
        <div className="form-grid">
          <label>
            Minimum confidence
            <input
              type="number"
              min="0"
              max="1"
              step=".05"
              value={params.get("confidence_min") || "0"}
              onChange={(e) => update("confidence_min", e.target.value)}
            />
          </label>
          <label>
            Failure category
            <select
              value={params.get("error_category") || ""}
              onChange={(e) => update("error_category", e.target.value)}
            >
              <option value="">All outcomes</option>
              {[
                "authentication",
                "rate_limit",
                "timeout",
                "network",
                "invalid_request",
                "context_limit",
                "runtime",
                "normalization",
              ].map((v) => (
                <option key={v} value={v}>
                  {label(v)}
                </option>
              ))}
            </select>
          </label>
        </div>
      </details>
      <ErrorBox error={query.error} />
      {query.isLoading ? (
        <Loading />
      ) : query.data?.total === 0 ? (
        <Empty title="No cases match these filters">
          Try removing a filter or changing the search text.
        </Empty>
      ) : (
        <div className="table-wrap">
          <table className="case-table">
            <thead>
              {table.getHeaderGroups().map((group) => (
                <tr key={group.id}>
                  {group.headers.map((header) => (
                    <th key={header.id}>
                      <button
                        onClick={header.column.getToggleSortingHandler()}
                        title="Sort this page"
                      >
                        {flexRender(
                          header.column.columnDef.header,
                          header.getContext(),
                        )}
                        <ArrowDownUp size={11} />
                      </button>
                    </th>
                  ))}
                </tr>
              ))}
            </thead>
            <tbody>
              {table.getRowModel().rows.map((row) => (
                <tr key={row.id}>
                  {row.getVisibleCells().map((cell) => (
                    <td key={cell.id}>
                      {flexRender(
                        cell.column.columnDef.cell,
                        cell.getContext(),
                      )}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
      <div className="pagination">
        <span>
          {query.data?.total.toLocaleString() ?? 0} matching presentations ·
          sorted within page
        </span>
        <div>
          <button
            className="icon-button"
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => update("page", String(page - 1))}
          >
            <ChevronLeft size={17} />
          </button>
          <span>
            Page {page} of{" "}
            {Math.max(1, Math.ceil((query.data?.total ?? 0) / 50))}
          </span>
          <button
            className="icon-button"
            aria-label="Next page"
            disabled={page * 50 >= (query.data?.total ?? 0)}
            onClick={() => update("page", String(page + 1))}
          >
            <ChevronRight size={17} />
          </button>
        </div>
      </div>
    </Panel>
  );
}
