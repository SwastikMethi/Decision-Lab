import { act, cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { PairedFrame } from "./LivePlayback";
import type { PlaybackFrame } from "./types";

const frame: PlaybackFrame = {
  key: "run:0",
  ordinal: 0,
  sealed: false,
  suite: "quality",
  repetition: 0,
  concurrency: 1,
  batch_size: 1,
  case: {
    id: "example",
    primitive: "choice",
    variant: "base",
    instructions: "Which team?",
    input_preview: "I paid twice",
    expected_key: "billing",
    options: [
      { id: "billing", label: "Billing" },
      { id: "technical", label: "Technical" },
    ],
  },
  systems: {
    jev: {
      evaluation_id: "jev:quality:example:0:1:1",
      state: "success",
      selected: "billing",
      probabilities: { billing: 0.8, technical: 0.2 },
      correctness: true,
      latency_ms: 42,
      retry_count: 0,
      error: null,
    },
    laya: {
      evaluation_id: "laya:quality:example:0:1:1",
      state: "success",
      selected: "technical",
      probabilities: { billing: 0.3, technical: 0.7 },
      correctness: false,
      latency_ms: 25,
      retry_count: 0,
      error: null,
    },
  },
};

afterEach(() => {
  cleanup();
  vi.useRealTimers();
});

describe("paired answer animation", () => {
  it("reveals probabilities and correctness only when the output packet arrives, then advances", () => {
    vi.useFakeTimers();
    const finished = vi.fn();
    render(
      <PairedFrame
        frame={frame}
        playing
        speed={1}
        reducedMotion={false}
        onFinished={finished}
      />,
    );
    expect(screen.queryByText("Correct")).not.toBeInTheDocument();
    expect(screen.queryByText("80.0%")).not.toBeInTheDocument();
    expect(screen.queryByText("Selected: Billing")).not.toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1500));
    expect(screen.queryByText("Correct")).not.toBeInTheDocument();
    expect(finished).not.toHaveBeenCalled();
    act(() => vi.advanceTimersByTime(650));
    expect(screen.getByText("Correct")).toBeInTheDocument();
    expect(screen.getByText("Incorrect")).toBeInTheDocument();
    expect(screen.getByText("80.0%")).toBeInTheDocument();
    expect(screen.getByText("Recorded 42 ms")).toBeInTheDocument();
    expect(screen.getByText("Selected: Billing")).toBeInTheDocument();
    expect(screen.getByText("Selected: Technical")).toBeInTheDocument();
    act(() => vi.advanceTimersByTime(1100));
    expect(finished).toHaveBeenCalledTimes(1);
  });

  it("pause freezes the animation and speed changes resume the same frame", () => {
    vi.useFakeTimers();
    const finished = vi.fn();
    const view = render(
      <PairedFrame
        frame={frame}
        playing
        speed={1}
        reducedMotion={false}
        onFinished={finished}
      />,
    );
    act(() => vi.advanceTimersByTime(600));
    view.rerender(
      <PairedFrame
        frame={frame}
        playing={false}
        speed={1}
        reducedMotion={false}
        onFinished={finished}
      />,
    );
    act(() => vi.advanceTimersByTime(10000));
    expect(screen.queryByText("Correct")).not.toBeInTheDocument();
    expect(finished).not.toHaveBeenCalled();
    view.rerender(
      <PairedFrame
        frame={frame}
        playing
        speed={4}
        reducedMotion={false}
        onFinished={finished}
      />,
    );
    act(() => vi.advanceTimersByTime(750));
    expect(screen.getByText("Correct")).toBeInTheDocument();
    expect(finished).toHaveBeenCalledTimes(1);
  });

  it("waits for the second saved result without inventing an answer", () => {
    vi.useFakeTimers();
    const pending = structuredClone(frame);
    pending.systems.laya = {
      evaluation_id: "laya-id",
      state: "pending",
      selected: null,
      probabilities: {},
      correctness: null,
      latency_ms: null,
      retry_count: 0,
      error: null,
    };
    const finished = vi.fn();
    const view = render(
      <PairedFrame
        frame={pending}
        playing
        speed={1}
        reducedMotion={false}
        onFinished={finished}
      />,
    );
    act(() => vi.advanceTimersByTime(5000));
    expect(screen.getByText("Awaiting result")).toBeInTheDocument();
    expect(screen.queryByText("Incorrect")).not.toBeInTheDocument();
    expect(finished).not.toHaveBeenCalled();
    view.rerender(
      <PairedFrame
        frame={frame}
        playing
        speed={1}
        reducedMotion={false}
        onFinished={finished}
      />,
    );
    act(() => vi.advanceTimersByTime(2100));
    expect(screen.getByText("Incorrect")).toBeInTheDocument();
    expect(finished).toHaveBeenCalledTimes(1);
  });

  it("reduced motion reveals real outcomes immediately and keeps failures distinct", () => {
    const failed = structuredClone(frame);
    failed.systems.laya = {
      evaluation_id: "laya-id",
      state: "failed",
      selected: null,
      probabilities: {},
      correctness: null,
      latency_ms: 20,
      retry_count: 2,
      error: "Provider unavailable",
    };
    render(
      <PairedFrame
        frame={failed}
        playing={false}
        speed={1}
        reducedMotion
        onFinished={() => {}}
      />,
    );
    expect(screen.getByText("Correct")).toBeInTheDocument();
    expect(screen.getByText("No valid response")).toBeInTheDocument();
    expect(screen.getByText("Provider unavailable")).toBeInTheDocument();
    expect(screen.queryByText("Incorrect")).not.toBeInTheDocument();
    expect(
      screen.getByLabelText("Laya diagram").querySelector(".correct-option"),
    ).toBeNull();
  });
});
