import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useUbiquityTour, TOUR_STEPS } from "../hooks/useUbiquityTour";

beforeEach(() => {
  vi.stubGlobal("fetch", vi.fn(() => Promise.resolve({ status: 202, ok: true })));
});

describe("useUbiquityTour", () => {
  it("expõe os 5 passos na ordem", () => {
    expect(TOUR_STEPS.map((s) => s.id)).toEqual([
      "fault", "heterogeneity", "privacy", "security", "distribution",
    ]);
  });

  it("marca running quando recebe lifecycle started", () => {
    const events = [{ event: "tour", kind: "lifecycle", status: "started" }];
    const { result } = renderHook(() => useUbiquityTour(events));
    expect(result.current.running).toBe(true);
    expect(result.current.finished).toBe(false);
  });

  it("reduz eventos de passo no mapa steps", () => {
    const events = [
      { event: "tour", kind: "lifecycle", status: "started" },
      { event: "tour", kind: "step", step: "security", title: "Segurança",
        status: "done", narration: "ok", data: { passed: true } },
    ];
    const { result } = renderHook(() => useUbiquityTour(events));
    expect(result.current.steps.security.status).toBe("done");
    expect(result.current.steps.security.data.passed).toBe(true);
  });

  it("marca finished e zera running no lifecycle finished", () => {
    const events = [
      { event: "tour", kind: "lifecycle", status: "started" },
      { event: "tour", kind: "lifecycle", status: "finished" },
    ];
    const { result } = renderHook(() => useUbiquityTour(events));
    expect(result.current.finished).toBe(true);
    expect(result.current.running).toBe(false);
  });

  it("start() faz POST em /api/demo/tour/start", async () => {
    const { result } = renderHook(() => useUbiquityTour([]));
    await act(async () => { await result.current.start(); });
    expect(fetch).toHaveBeenCalledWith("/api/demo/tour/start", { method: "POST" });
  });
});
