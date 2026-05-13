import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSimulatedInputs } from "../hooks/useSimulatedInputs";

beforeEach(() => {
  vi.useFakeTimers();
  global.fetch = vi.fn(() => Promise.resolve({ status: 202, ok: true, json: async () => ({}) }));
});

afterEach(() => vi.useRealTimers());

describe("useSimulatedInputs", () => {
  it("debounces POST /api/inputs", async () => {
    const { result } = renderHook(() => useSimulatedInputs());
    act(() => { result.current.setInputs({ bpm: 60 }); });
    act(() => { result.current.setInputs({ bpm: 55 }); });
    act(() => { result.current.setInputs({ bpm: 50 }); });

    expect(global.fetch).not.toHaveBeenCalledWith("/api/inputs", expect.anything());
    act(() => { vi.advanceTimersByTime(150); });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("startDemo sets demoState to running on 202", async () => {
    const { result } = renderHook(() => useSimulatedInputs());
    await act(async () => { await result.current.startDemo(); });
    expect(result.current.demoState).toBe("running");
  });
});
