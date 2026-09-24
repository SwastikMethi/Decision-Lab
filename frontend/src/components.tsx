import { useState, type ReactNode } from "react";
import {
  AlertCircle,
  Check,
  ChevronRight,
  X,
  LoaderCircle,
  ArrowUpRight,
  CircleDot,
} from "lucide-react";
import * as Dialog from "@radix-ui/react-dialog";
import * as Tabs from "@radix-ui/react-tabs";
import { motion, useReducedMotion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { clsx } from "clsx";
import { twMerge } from "tailwind-merge";
import { request, label, systemName, color, pct, number } from "./api";
import type { CaseDetail, RiskPoint } from "./types";

export function cn(...inputs: Parameters<typeof clsx>) {
  return twMerge(clsx(inputs));
}
export function Status({ value }: { value: string }) {
  const done = value === "completed";
  const active = [
    "warming",
    "running",
    "validating",
    "scoring",
    "cancelling",
  ].includes(value);
  return (
    <span
      className={cn(
        "badge status",
        done ? "success" : active ? "active" : "neutral",
      )}
    >
      {done ? (
        <Check size={12} />
      ) : active ? (
        <CircleDot size={12} />
      ) : (
        <AlertCircle size={12} />
      )}{" "}
      {label(value)}
    </span>
  );
}
export function PageTitle({
  title,
  description,
  action,
}: {
  title: string;
  description?: string;
  action?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <h1>{title}</h1>
        {description && <p>{description}</p>}
      </div>
      {action}
    </div>
  );
}
export function Panel({
  title,
  description,
  children,
  action,
  className,
}: {
  title?: string;
  description?: string;
  children: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("panel", className)}>
      {title && (
        <div className="panel-heading">
          <div>
            <h2>{title}</h2>
            {description && <p>{description}</p>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}
export function ErrorBox({ error }: { error: unknown }) {
  if (!error) return null;
  return (
    <div role="alert" className="notice error">
      <AlertCircle size={18} />
      <div>
        <strong>We couldn’t complete that step</strong>
        <p>{error instanceof Error ? error.message : String(error)}</p>
        <small>Previously saved results remain available.</small>
      </div>
    </div>
  );
}
export function Loading() {
  return (
    <div
      aria-busy="true"
      aria-label="Loading evaluation data"
      className="skeletons"
      role="status"
    >
      <div />
      <div />
      <div />
    </div>
  );
}
export function Empty({
  title,
  children,
}: {
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="empty">
      <CircleDot size={32} />
      <h2>{title}</h2>
      <p>{children}</p>
    </div>
  );
}
export function JsonBlock({ value }: { value: unknown }) {
  return <pre className="json">{JSON.stringify(value, null, 2)}</pre>;
}
export function RiskControl({
  systems,
}: {
  systems: Record<string, RiskPoint[]>;
}) {
  const [target, setTarget] = useState(2);
  return (
    <div className="risk-control">
      <label>
        Acceptable observed risk (%)
        <input
          aria-label="Acceptable observed risk (%)"
          type="number"
          min="0"
          max="100"
          step=".5"
          value={target}
          onChange={(e) =>
            setTarget(Math.min(100, Math.max(0, Number(e.target.value))))
          }
        />
      </label>
      <div className="paired">
        {Object.entries(systems).map(([system, curve]) => {
          const point = curve
            .filter((p) => p.risk !== null && p.risk <= target / 100)
            .sort((a, b) => b.coverage - a.coverage)[0];
          return (
            <div key={system} className="operating-point">
              <span className="model-name">
                <i style={{ background: color(system) }} />
                {systemName(system)}
              </span>
              <strong>
                {point
                  ? pct(point.coverage) + " coverage"
                  : "No eligible threshold"}
              </strong>
              <small>
                {point
                  ? point.accepted +
                    " / " +
                    point.denominator +
                    " accepted · " +
                    pct(point.risk) +
                    " observed risk"
                  : "All cases require review at this target."}
              </small>
              {point?.unstable && (
                <span className="warning-text">
                  Small sample — fewer than 30 accepted decisions
                </span>
              )}
            </div>
          );
        })}
      </div>
      <p className="caption">
        Thresholds accept complete confidence ties. Observed risk describes this
        dataset; it is not a future error guarantee.
      </p>
    </div>
  );
}
export function Filters({
  domains = false,
  domainOptions = [],
}: {
  domains?: boolean;
  domainOptions?: string[];
}) {
  const [params, setParams] = useSearchParams();
  const update = (key: string, value: string) => {
    const next = new URLSearchParams(params);
    value ? next.set(key, value) : next.delete(key);
    next.delete("page");
    next.delete("case");
    setParams(next);
  };
  return (
    <div className="filters">
      <label className="sr-only" htmlFor="primitive-filter">
        Primitive
      </label>
      <select
        id="primitive-filter"
        value={params.get("primitive") || ""}
        onChange={(e) => update("primitive", e.target.value)}
      >
        <option value="">All primitives</option>
        {["choice", "noul", "score"].map((v) => (
          <option key={v} value={v}>
            {label(v)}
          </option>
        ))}
      </select>
      <label className="sr-only" htmlFor="domain-filter">
        Domain
      </label>
      <select
        id="domain-filter"
        value={params.get("domain") || ""}
        onChange={(e) => update("domain", e.target.value)}
      >
        <option value="">All domains</option>
        {domainOptions.map((v) => (
          <option key={v} value={v}>
            {label(v)}
          </option>
        ))}
      </select>
      {domains && (
        <>
          <label className="sr-only" htmlFor="variant-filter">
            Transformation
          </label>
          <select
            id="variant-filter"
            value={params.get("variant") || ""}
            onChange={(e) => update("variant", e.target.value)}
          >
            <option value="">All transformations</option>
            {[
              "base",
              "paraphrase",
              "paraphrase_2",
              "option_order",
              "opaque_labels",
              "state_key_order",
              "distractor",
              "adversarial_state",
              "context_length",
              "option_cardinality",
            ].map((v) => (
              <option key={v} value={v}>
                {label(v)}
              </option>
            ))}
          </select>
        </>
      )}
      <button
        className={cn(
          "filter-toggle",
          params.get("disagreement") === "true" && "selected",
        )}
        aria-pressed={params.get("disagreement") === "true"}
        onClick={() =>
          update("disagreement", params.get("disagreement") ? "" : "true")
        }
      >
        Disagreements only
      </button>
      {params.size > 0 && (
        <button className="text-button" onClick={() => setParams({})}>
          Clear filters
        </button>
      )}
    </div>
  );
}
export function EvidenceDrawer({ runId }: { runId: string }) {
  const [params, setParams] = useSearchParams();
  const caseId = params.get("case");
  const jevEvaluation = params.get("jev_evaluation"),
    layaEvaluation = params.get("laya_evaluation");
  const reduced = useReducedMotion();
  const query = useQuery({
    queryKey: ["case", runId, caseId, jevEvaluation, layaEvaluation],
    queryFn: () => request<CaseDetail>("/runs/" + runId + "/cases/" + caseId),
    enabled: !!caseId,
  });
  const close = () => {
    const next = new URLSearchParams(params);
    next.delete("case");
    next.delete("jev_evaluation");
    next.delete("laya_evaluation");
    setParams(next);
  };
  const select = (id: string) => {
    const next = new URLSearchParams(params);
    next.set("case", id);
    next.delete("jev_evaluation");
    next.delete("laya_evaluation");
    setParams(next);
  };
  let data = query.data;
  if (data && (jevEvaluation || layaEvaluation)) {
    const predictions = Object.fromEntries(
      [
        ["jev", jevEvaluation],
        ["laya", layaEvaluation],
      ].flatMap(([system, id]) => {
        const prediction = data?.all_predictions.find(
          (p) => p.evaluation_id === id,
        );
        return prediction ? [[system, prediction]] : [];
      }),
    );
    data = {
      ...data,
      predictions,
      correctness: Object.fromEntries(
        ["jev", "laya"].map((system) => [
          system,
          predictions[system]?.status === "success" &&
            predictions[system]?.answer?.selected ===
              String(data?.case.expected.value),
        ]),
      ),
    };
  }
  const outcomes = data
    ? Object.keys(
        data.predictions.jev?.answer?.probabilities ||
          data.predictions.laya?.answer?.probabilities ||
          {},
      )
    : [];
  return (
    <Dialog.Root
      open={!!caseId}
      onOpenChange={(open) => {
        if (!open) close();
      }}
    >
      <Dialog.Portal>
        <Dialog.Overlay className="drawer-overlay" />
        <Dialog.Content
          className="drawer"
          aria-describedby="evidence-description"
        >
          <motion.div
            initial={{ x: reduced ? 0 : 24, opacity: 0 }}
            animate={{ x: 0, opacity: 1 }}
            transition={{ duration: 0.2 }}
          >
            <div className="drawer-header">
              <div>
                <span className="muted">Case evidence</span>
                <Dialog.Title>{caseId}</Dialog.Title>
              </div>
              <Dialog.Close className="icon-button" aria-label="Close evidence">
                <X size={20} />
              </Dialog.Close>
            </div>
            <Dialog.Description id="evidence-description">
              Inspect the input, paired outcomes, and the exact evidence behind
              this decision.
            </Dialog.Description>
            {query.isLoading ? (
              <Loading />
            ) : query.error ? (
              <ErrorBox error={query.error} />
            ) : (
              data && (
                <Tabs.Root defaultValue="decision" key={caseId}>
                  <Tabs.List className="tabs" aria-label="Evidence sections">
                    {[
                      "decision",
                      "probabilities",
                      "raw",
                      "family",
                      "metadata",
                    ].map((t) => (
                      <Tabs.Trigger key={t} value={t}>
                        {label(t)}
                      </Tabs.Trigger>
                    ))}
                  </Tabs.List>
                  <Tabs.Content value="decision">
                    <div className="evidence-meta">
                      {(jevEvaluation || layaEvaluation) && (
                        <span className="badge">Selected playback request</span>
                      )}
                      <span className="badge">
                        {label(data.case.primitive)}
                      </span>
                      <span className="badge">{label(data.case.variant)}</span>
                      <span className="badge">{label(data.case.domain)}</span>
                    </div>
                    <h3>Question</h3>
                    <p>{data.case.question.instructions}</p>
                    <h3>Expected outcome</h3>
                    <strong className="expected">
                      {String(data.case.expected.value)}
                    </strong>
                    <h3>Input state</h3>
                    <JsonBlock value={data.case.state} />
                    <h3>Criteria</h3>
                    <JsonBlock value={data.case.question.criteria} />
                    <div className="paired">
                      {["jev", "laya"].map((key) => (
                        <div className="answer-card" key={key}>
                          <span className="model-name">
                            <i style={{ background: color(key) }} />
                            {systemName(key)}
                          </span>
                          <strong>
                            {data.predictions[key]?.answer?.selected ??
                              "No valid answer"}
                          </strong>
                          <span
                            className={
                              data.correctness[key]
                                ? "success-text"
                                : "error-text"
                            }
                          >
                            {data.correctness[key]
                              ? "Correct"
                              : "Incorrect or failed"}
                          </span>
                          {data.predictions[key]?.error && (
                            <p>{data.predictions[key].error?.message}</p>
                          )}
                        </div>
                      ))}
                    </div>
                  </Tabs.Content>
                  <Tabs.Content value="probabilities">
                    <h3>Complete outcome distributions</h3>
                    <p className="caption">
                      Aligned by outcome, not by displayed position. Expected
                      outcome: {String(data.case.expected.value)}.
                    </p>
                    {outcomes.map((outcome) => (
                      <div key={outcome} className="probability-row">
                        <strong>
                          {outcome}{" "}
                          {outcome === String(data.case.expected.value) && (
                            <Check size={14} />
                          )}
                        </strong>
                        {["jev", "laya"].map((key) => {
                          const probability =
                            data.predictions[key]?.answer?.probabilities[
                              outcome
                            ];
                          return (
                            <div key={key} className="probability">
                              <span>{systemName(key)}</span>
                              <div className="bar-track">
                                <motion.div
                                  initial={false}
                                  animate={{
                                    width: (probability ?? 0) * 100 + "%",
                                  }}
                                  transition={{ duration: reduced ? 0 : 0.3 }}
                                  style={{ background: color(key) }}
                                />
                              </div>
                              <b>{pct(probability)}</b>
                            </div>
                          );
                        })}
                      </div>
                    ))}
                    {outcomes.length === 0 && (
                      <p>Neither system returned a valid distribution.</p>
                    )}
                    <h3>Confidence signals</h3>
                    {["jev", "laya"].map((key) => (
                      <p key={key}>
                        {systemName(key)}: selected probability{" "}
                        {pct(
                          data.predictions[key]?.answer?.decision_probability,
                        )}
                        ; provider confidence{" "}
                        {pct(
                          data.predictions[key]?.answer?.provider_confidence,
                        )}
                        .
                      </p>
                    ))}
                  </Tabs.Content>
                  <Tabs.Content value="raw">
                    {["jev", "laya"].map((key) => (
                      <div key={key}>
                        <h3>{systemName(key)} sanitized response</h3>
                        <JsonBlock
                          value={data.predictions[key]?.raw_response ?? null}
                        />
                      </div>
                    ))}
                  </Tabs.Content>
                  <Tabs.Content value="family">
                    <h3>One decision, multiple presentations</h3>
                    {data.family.map((row) => (
                      <button
                        className={cn(
                          "family-row",
                          row.case.id === caseId && "selected",
                        )}
                        onClick={() => select(row.case.id)}
                        key={row.case.id}
                      >
                        <div>
                          <strong>{label(row.case.variant)}</strong>
                          <small>{row.case.id}</small>
                        </div>
                        <span>
                          {
                            Object.values(row.correctness).filter(Boolean)
                              .length
                          }
                          /2 correct
                        </span>
                        <ChevronRight size={16} />
                      </button>
                    ))}
                  </Tabs.Content>
                  <Tabs.Content value="metadata">
                    <JsonBlock
                      value={{
                        case: data.case.metadata,
                        predictions: data.all_predictions.map((p) => ({
                          evaluation: p.evaluation_id,
                          suite: p.suite,
                          model: p.model,
                          timing: p.timing,
                          usage: p.usage,
                          retries: p.retry_count,
                        })),
                      }}
                    />
                  </Tabs.Content>
                </Tabs.Root>
              )
            )}
          </motion.div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
export function InspectButton({ onClick }: { onClick: () => void }) {
  return (
    <button className="text-button" onClick={onClick}>
      Inspect evidence <ArrowUpRight size={14} />
    </button>
  );
}
export function BusyButton({
  busy,
  children,
  ...props
}: React.ButtonHTMLAttributes<HTMLButtonElement> & { busy?: boolean }) {
  return (
    <button {...props} disabled={props.disabled || busy}>
      {busy && <LoaderCircle size={16} className="spin" />}
      {children}
    </button>
  );
}
