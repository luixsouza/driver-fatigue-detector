import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FatigueGauge } from "../components/gauge/FatigueGauge";

describe("FatigueGauge", () => {
  it("renders the index value rounded", () => {
    render(<FatigueGauge state={{ fatigue_index: 67.4, index_severity: "alert", explain: "BPM baixo + tempo alto" }} />);
    expect(screen.getByText("67")).toBeInTheDocument();
    expect(screen.getByText(/BPM baixo/)).toBeInTheDocument();
  });

  it("falls back to 0 when no state", () => {
    render(<FatigueGauge state={null} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("shows critico suffix when critical=true", () => {
    render(<FatigueGauge state={{ fatigue_index: 90, index_severity: "alert", critical: true, explain: "x" }} />);
    expect(screen.getByText(/Crítico/)).toBeInTheDocument();
  });
});
