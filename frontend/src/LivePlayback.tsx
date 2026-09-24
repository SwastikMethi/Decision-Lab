import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useReducedMotion } from "framer-motion";
import {
  ArrowRight,
  Check,
  ChevronLeft,
  ChevronRight,
  ChevronsRight,
  Cloud,
  Cpu,
  FileText,
  LockKeyhole,
  Pause,
  Play,
  RotateCcw,
  TriangleAlert,
  X,
} from "lucide-react";
import { isTerminal, label, number, pct, request, systemName } from "./api";
import { ErrorBox, EvidenceDrawer } from "./components";
import type { PlaybackFrame, PlaybackOutcome, PlaybackPage } from "./types";

const INPUT_MS = 1100;
const OUTPUT_MS = 900;
const HOLD_MS = 1000;
const SYSTEMS = ["jev", "laya"] as const;
type Clock = { input: number; jev: number; laya: number };

export function PairedFrame({
  frame,
  playing,
  speed,
  reducedMotion,
  onFinished,
}: {
  frame: PlaybackFrame;
  playing: boolean;
  speed: number;
  reducedMotion: boolean;
  onFinished: () => void;
}) {
  const ready = (system: string) => frame.systems[system]?.state !== "pending";
  const [clock, setClock] = useState<Clock>(() => ({
    input: reducedMotion ? INPUT_MS : 0,
    jev: reducedMotion && ready("jev") ? OUTPUT_MS : 0,
    laya: reducedMotion && ready("laya") ? OUTPUT_MS : 0,
  }));
  const finished = useRef(false);
  const finishAt = reducedMotion ? OUTPUT_MS + 3000 : OUTPUT_MS + HOLD_MS;
  const jevReady = ready("jev"),
    layaReady = ready("laya");
  useEffect(() => {
    if (!playing) return;
    let previousTime = performance.now();
    let animation: number;
    const tick = (now: number) => {
      const delta = (now - previousTime) * speed;
      previousTime = now;
      setClock((previous) => {
        const next = {
          input: Math.min(INPUT_MS, previous.input + delta),
          jev:
            previous.input >= INPUT_MS && jevReady
              ? Math.min(
                  finishAt,
                  Math.max(previous.jev, reducedMotion ? OUTPUT_MS : 0) + delta,
                )
              : previous.jev,
          laya:
            previous.input >= INPUT_MS && layaReady
              ? Math.min(
                  finishAt,
                  Math.max(previous.laya, reducedMotion ? OUTPUT_MS : 0) +
                    delta,
                )
              : previous.laya,
        };
        return next.input === previous.input &&
          next.jev === previous.jev &&
          next.laya === previous.laya
          ? previous
          : next;
      });
      animation = requestAnimationFrame(tick);
    };
    animation = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(animation);
  }, [playing, speed, reducedMotion, jevReady, layaReady, finishAt]);
  useEffect(() => {
    if (!playing) finished.current = false;
    if (
      playing &&
      clock.jev >= finishAt &&
      clock.laya >= finishAt &&
      !finished.current
    ) {
      finished.current = true;
      onFinished();
    }
  }, [clock, finishAt, playing, onFinished]);
  return (
    <div className="decision-lanes">
      {SYSTEMS.map((system) => (
        <DecisionLane
          key={system}
          system={system}
          frame={frame}
          outcome={frame.systems[system]}
          inputProgress={clock.input / INPUT_MS}
          outputProgress={Math.min(1, clock[system] / OUTPUT_MS)}
          playing={playing}
          reducedMotion={reducedMotion}
        />
      ))}
    </div>
  );
}

function DecisionLane({
  system,
  frame,
  outcome,
  inputProgress,
  outputProgress,
  playing,
  reducedMotion,
}: {
  system: "jev" | "laya";
  frame: PlaybackFrame;
  outcome: PlaybackOutcome;
  inputProgress: number;
  outputProgress: number;
  playing: boolean;
  reducedMotion: boolean;
}) {
  const body = useRef<HTMLDivElement>(null),
    node = useRef<HTMLDivElement>(null),
    input = useRef<HTMLDivElement>(null);
  const options = useRef<HTMLDivElement>(null),
    target = useRef<HTMLDivElement>(null);
  const [line, setLine] = useState({
    x1: 90,
    y1: 155,
    x2: 175,
    y2: 155,
    ix: 55,
    iy: 48,
    my: 120,
  });
  const arrived = outputProgress >= 1;
  const success = outcome.state === "success";
  const outputStarted = outputProgress > 0;
  const status = !arrived
    ? inputProgress < 1
      ? "Receiving input"
      : outputStarted
        ? "Delivering answer"
        : "Awaiting result"
    : success
      ? outcome.correctness
        ? "Correct"
        : "Incorrect"
      : outcome.state === "failed"
        ? "No valid response"
        : "Not completed";
  useLayoutEffect(() => {
    if (inputProgress < 1 || !success || !options.current || !target.current)
      return;
    const list = options.current,
      item = target.current;
    list.scrollTop = Math.max(
      0,
      item.offsetTop -
        list.offsetTop -
        list.clientHeight / 2 +
        item.clientHeight / 2,
    );
  }, [inputProgress >= 1, success, outcome.selected]);
  useLayoutEffect(() => {
    const measure = () => {
      if (!body.current || !node.current || !input.current || !options.current)
        return;
      const b = body.current.getBoundingClientRect(),
        n = node.current.getBoundingClientRect();
      const i = input.current.getBoundingClientRect(),
        list = options.current.getBoundingClientRect();
      const t = target.current?.getBoundingClientRect() || list;
      setLine({
        x1: n.right - b.left,
        y1: n.top + n.height / 2 - b.top,
        x2: list.left - b.left,
        y2:
          Math.max(
            list.top + 12,
            Math.min(list.bottom - 12, t.top + t.height / 2),
          ) - b.top,
        ix: i.left + i.width / 2 - b.left,
        iy: i.bottom - b.top,
        my: n.top - b.top,
      });
    };
    measure();
    const observer =
      typeof ResizeObserver === "undefined"
        ? null
        : new ResizeObserver(measure);
    [body.current, node.current, options.current, target.current].forEach(
      (element) => element && observer?.observe(element),
    );
    options.current?.addEventListener("scroll", measure);
    const list = options.current;
    return () => {
      observer?.disconnect();
      list?.removeEventListener("scroll", measure);
    };
  }, [outcome.selected, frame.key, inputProgress >= 1]);
  const mid = (line.x1 + line.x2) / 2,
    t = outputProgress,
    u = 1 - t;
  const dotX =
    u ** 3 * line.x1 +
    3 * u ** 2 * t * mid +
    3 * u * t ** 2 * mid +
    t ** 3 * line.x2;
  const dotY =
    u ** 3 * line.y1 +
    3 * u ** 2 * t * line.y1 +
    3 * u * t ** 2 * line.y2 +
    t ** 3 * line.y2;
  const inputT = Math.min(1, inputProgress * 2);
  const expected = frame.case?.options.find(
    (o) => o.id === frame.case?.expected_key,
  );
  const nodeClass = arrived
    ? success
      ? outcome.correctness
        ? "is-correct"
        : "is-incorrect"
      : "is-error"
    : "";
  return (
    <section
      className={`decision-lane ${system} ${nodeClass}`}
      aria-label={`${systemName(system)} diagram`}
    >
      <header className="diagram-heading">
        <span className="diagram-brand">
          <i />
          {systemName(system)}
        </span>
        <span>
          {system === "jev" ? <Cloud size={14} /> : <Cpu size={14} />}
          {system === "jev" ? "Hosted API" : "On this machine"}
        </span>
      </header>
      <div ref={body} className="diagram-body">
        <svg className="diagram-wires" aria-hidden="true">
          <path
            d={`M ${line.ix} ${line.iy} L ${line.ix} ${line.my}`}
            className="diagram-wire"
          />
          <path
            d={`M ${line.x1} ${line.y1} C ${mid} ${line.y1}, ${mid} ${line.y2}, ${line.x2} ${line.y2}`}
            className={`diagram-wire ${outputStarted && success ? "active" : ""}`}
          />
          {!reducedMotion && inputProgress > 0 && inputT < 1 && (
            <circle
              className="answer-packet"
              r="5"
              cx={line.ix}
              cy={line.iy + (line.my - line.iy) * inputT}
            />
          )}
          {!reducedMotion && success && outputStarted && !arrived && (
            <g>
              <circle className="packet-halo" r="11" cx={dotX} cy={dotY} />
              <circle className="answer-packet" r="5" cx={dotX} cy={dotY} />
            </g>
          )}
        </svg>
        <div className="diagram-source">
          <div ref={input} className="input-node">
            <FileText size={16} />
            <span>Input</span>
          </div>
          <div
            ref={node}
            className={`model-node ${inputProgress >= 0.5 && !outputStarted ? "is-waiting" : ""}`}
            style={{ animationPlayState: playing ? "running" : "paused" }}
          >
            <span className="model-orbit" />
            {system === "jev" ? (
              <Cloud size={31} strokeWidth={1.5} />
            ) : (
              <Cpu size={31} strokeWidth={1.5} />
            )}
          </div>
          <span className="model-node-label">{systemName(system)}</span>
          {frame.batch_size > 1 && (
            <span className="batch-packet">×{frame.batch_size} questions</span>
          )}
        </div>
        <div className="diagram-options-column">
          <span className="options-label">
            {frame.case?.primitive === "score"
              ? "Ordered levels"
              : "Answer options"}
            <small>{frame.case?.options.length}</small>
          </span>
          <div
            className="diagram-options"
            ref={options}
            tabIndex={0}
            role="group"
            aria-label={`${systemName(system)} answer options`}
          >
            {frame.case?.options.map((option) => {
              const selected = option.id === outcome.selected;
              const correct =
                arrived && success && option.id === frame.case?.expected_key;
              const wrong =
                arrived && selected && outcome.correctness === false;
              const probability = outcome.probabilities?.[option.id];
              return (
                <div
                  ref={selected ? target : undefined}
                  key={option.id}
                  className={`diagram-option ${arrived && selected ? "is-selected" : ""} ${correct ? "correct-option" : ""} ${wrong ? "wrong-option" : ""}`}
                >
                  <div className="option-text">
                    <span className="option-key">
                      {frame.case?.primitive === "noul" ? (
                        option.id === "true" ? (
                          <Check size={13} />
                        ) : (
                          <X size={13} />
                        )
                      ) : (
                        option.id
                      )}
                    </span>
                    <span title={option.label}>{option.label}</span>
                    {arrived && selected && (
                      <span className="option-verdict">
                        {outcome.correctness ? (
                          <Check size={14} />
                        ) : (
                          <X size={14} />
                        )}
                      </span>
                    )}
                  </div>
                  <div className="option-probability">
                    <div className="option-track">
                      <div
                        style={{
                          width: `${(probability ?? 0) * outputProgress * 100}%`,
                        }}
                      />
                    </div>
                    <span>
                      {arrived && probability != null ? pct(probability) : "—"}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <footer className="diagram-verdict" aria-live="polite" aria-atomic="true">
        <div className="verdict-main">
          {arrived ? (
            success ? (
              outcome.correctness ? (
                <Check size={19} />
              ) : (
                <X size={19} />
              )
            ) : (
              <TriangleAlert size={18} />
            )
          ) : (
            <span className={`waiting-dot ${playing ? "moving" : ""}`} />
          )}
          <strong>{status}</strong>
          {arrived && outcome.latency_ms != null && (
            <small>Recorded {number(outcome.latency_ms, 0)} ms</small>
          )}
        </div>
        {arrived && success && !outcome.correctness && (
          <p>Expected: {expected?.label}</p>
        )}
        {arrived && outcome.error && <p>{outcome.error}</p>}
        {arrived && (outcome.retry_count ?? 0) > 0 && (
          <p>
            {outcome.retry_count}{" "}
            {outcome.retry_count === 1 ? "retry" : "retries"}
          </p>
        )}
      </footer>
    </section>
  );
}

function savedPreferences(runId: string) {
  try {
    const value = JSON.parse(
      sessionStorage.getItem(`decisionlab-playback:${runId}`) || "{}",
    );
    return {
      position:
        Number.isSafeInteger(value.position) && value.position >= 0
          ? value.position
          : 0,
      speed: [1, 2, 4].includes(value.speed) ? value.speed : 1,
      playing: typeof value.playing === "boolean" ? value.playing : true,
    };
  } catch {
    return { position: 0, speed: 1, playing: true };
  }
}

export default function LivePlayback({ runId }: { runId: string }) {
  const [preferences] = useState(() => savedPreferences(runId));
  const [position, setPosition] = useState<number>(preferences.position);
  const [speed, setSpeed] = useState<number>(preferences.speed);
  const [playing, setPlaying] = useState<boolean>(preferences.playing);
  const [replay, setReplay] = useState(0);
  const [stepping, setStepping] = useState(false);
  const completedFrame = useRef(false);
  const [params, setParams] = useSearchParams();
  const reduced = !!useReducedMotion();
  const pageStart = Math.floor(position / 20) * 20;
  const query = useQuery({
    queryKey: ["playback", runId, pageStart],
    queryFn: () =>
      request<PlaybackPage>(
        `/runs/${runId}/playback?after=${pageStart - 1}&limit=20`,
      ),
    gcTime: 0,
    refetchInterval: (q) =>
      q.state.data?.withheld_frames && q.state.data?.run_status === "completed"
        ? 5000
        : false,
  });
  const page = query.data;
  const frame = page?.items.find((item) => item.ordinal === position);
  const maxPosition = Math.max(0, (page?.total_frames ?? 1) - 1);
  useEffect(() => {
    try {
      sessionStorage.setItem(
        `decisionlab-playback:${runId}`,
        JSON.stringify({ position, speed, playing }),
      );
    } catch {
      /* Storage can be disabled without preventing playback. */
    }
  }, [runId, position, speed, playing]);
  useEffect(() => {
    if (page && position > maxPosition) setPosition(maxPosition);
    if (frame?.sealed && page && playing) {
      const next = page.items.find(
        (item) => item.ordinal > position && !item.sealed,
      );
      if (next) setPosition(next.ordinal);
      else if (page.next_cursor !== null) setPosition(page.next_cursor + 1);
      else setPlaying(false);
    }
  }, [frame?.sealed, page, position, maxPosition, playing]);
  const move = (next: number) => {
    completedFrame.current = false;
    setPlaying(true);
    setStepping(true);
    setPosition(Math.max(0, Math.min(maxPosition, next)));
    setReplay((n) => n + 1);
  };
  const inspect = () => {
    if (!frame?.case) return;
    setPlaying(false);
    const next = new URLSearchParams(params);
    next.set("case", frame.case.id);
    SYSTEMS.forEach((system) =>
      next.set(`${system}_evaluation`, frame.systems[system].evaluation_id),
    );
    setParams(next);
  };
  const finish = () => {
    completedFrame.current = stepping || position === maxPosition;
    if (!completedFrame.current) setPosition(position + 1);
    else setPlaying(false);
  };
  return (
    <section
      className="playback-workspace"
      aria-label="Paired decision playback"
    >
      <div className="playback-toolbar">
        <div className="playback-title">
          <span className="playback-icon">
            <Play size={15} />
          </span>
          <div>
            <h2>Decision playback</h2>
            <p>
              {page && isTerminal(page.run_status)
                ? "Evaluation finished. Explore every saved response."
                : "Watch the decisions. Evaluation continues at full speed."}
            </p>
          </div>
        </div>
        <div className="playback-controls">
          <button
            className="icon-button"
            aria-label="Previous comparison"
            disabled={!page || position === 0}
            onClick={() => move(position - 1)}
          >
            <ChevronLeft size={18} />
          </button>
          <button
            className="playback-toggle"
            aria-label={playing ? "Pause playback" : "Play playback"}
            disabled={!frame || frame.sealed}
            onClick={() => {
              if (
                !playing &&
                position === maxPosition &&
                completedFrame.current
              ) {
                completedFrame.current = false;
                setReplay((n) => n + 1);
              }
              setStepping(false);
              setPlaying(!playing);
            }}
          >
            {playing ? <Pause size={17} /> : <Play size={17} />}
          </button>
          <button
            className="icon-button"
            aria-label="Next comparison"
            disabled={!page || position >= maxPosition}
            onClick={() => move(position + 1)}
          >
            <ChevronRight size={18} />
          </button>
          <select
            aria-label="Playback speed"
            value={speed}
            onChange={(e) => setSpeed(Number(e.target.value))}
          >
            {[1, 2, 4].map((value) => (
              <option key={value} value={value}>
                {value}×
              </option>
            ))}
          </select>
          <button
            className="text-button playback-latest"
            disabled={page?.latest_available == null}
            onClick={() => move(page?.latest_available ?? 0)}
          >
            Jump to latest
            <ChevronsRight size={15} />
          </button>
        </div>
      </div>
      <ErrorBox error={query.error} />
      {page && page.withheld_frames > 0 && (
        <div className="playback-sealed">
          <LockKeyhole size={14} />
          {page.withheld_frames} sealed comparisons hidden until both tracks
          complete
        </div>
      )}
      {!frame ? (
        <div className="playback-empty" role="status">
          {query.isLoading
            ? "Loading saved decisions…"
            : "No scheduled decisions are available."}
        </div>
      ) : frame.sealed ? (
        <div className="playback-empty">
          <LockKeyhole size={28} />
          <h3>These results are still sealed</h3>
          <p>They unlock after both frozen tracks complete.</p>
          <button className="text-button" onClick={() => move(0)}>
            <RotateCcw size={15} />
            Back to first comparison
          </button>
        </div>
      ) : (
        <>
          <div className="playback-case">
            <div className="playback-case-top">
              <span className="case-position">
                Comparison {position + 1} <span>/ {page?.total_frames}</span>
              </span>
              <div className="playback-tags">
                <span>{label(frame.case?.primitive || "")}</span>
                <span>{label(frame.suite)}</span>
                {frame.suite === "repeatability" && (
                  <span>Repeat {frame.repetition + 1}</span>
                )}
                {frame.suite === "performance" && (
                  <span>
                    {frame.concurrency} concurrent · ×{frame.batch_size}{" "}
                    questions
                  </span>
                )}
              </div>
              <button
                className="text-button"
                onClick={inspect}
                title="View the full question, input, and saved response"
              >
                Inspect
                <ArrowRight size={14} />
              </button>
            </div>
            <h3>{frame.case?.instructions}</h3>
            <p className="playback-input">
              <FileText size={17} />
              <span>{frame.case?.input_preview}</span>
            </p>
            {frame.batch_size > 1 && (
              <p className="batch-explanation">
                Batch example: the saved representative answer from{" "}
                {frame.batch_size} questions sharing this input.
              </p>
            )}
          </div>
          <PairedFrame
            key={`${frame.key}:${replay}`}
            frame={frame}
            playing={playing}
            speed={speed}
            reducedMotion={reduced}
            onFinished={finish}
          />
          <div className="playback-footnote">
            <span>
              Input <ArrowRight size={12} /> Model <ArrowRight size={12} />{" "}
              Options <ArrowRight size={12} /> Outcome
            </span>
            <span>Playback speed does not represent model latency</span>
          </div>
        </>
      )}
      <EvidenceDrawer runId={runId} />
    </section>
  );
}
