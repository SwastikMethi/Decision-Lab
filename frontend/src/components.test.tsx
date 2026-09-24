import { render, screen, fireEvent } from "@testing-library/react";
import { describe, it, expect } from "vitest";
import { RiskControl, Status } from "./components";

describe("risk operating points", () => {
  it("selects complete tied groups and exposes small samples", () => {
    render(
      <RiskControl
        systems={{
          "jev-default": [
            {
              threshold: 0.9,
              accepted: 20,
              errors: 0,
              denominator: 100,
              coverage: 0.2,
              risk: 0,
              unstable: true,
            },
            {
              threshold: 0.8,
              accepted: 50,
              errors: 2,
              denominator: 100,
              coverage: 0.5,
              risk: 0.04,
              unstable: false,
            },
          ],
        }}
      />,
    );
    expect(screen.getByText("20.0% coverage")).toBeInTheDocument();
    expect(screen.getByText(/Small sample/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Acceptable observed risk (%)"), {
      target: { value: "5" },
    });
    expect(screen.getByText("50.0% coverage")).toBeInTheDocument();
  });
  it("does not describe an interrupted run as completed", () => {
    render(<Status value="partial" />);
    expect(screen.getByText("Partial")).toBeInTheDocument();
    expect(screen.queryByText("Completed")).not.toBeInTheDocument();
  });
});
