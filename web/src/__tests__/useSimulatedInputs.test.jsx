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
    // Hook faz um GET bootstrap inicial; conta apenas POSTs daqui em diante.
    const postCount = () => global.fetch.mock.calls.filter(
      ([, opts]) => opts && opts.method === "POST",
    ).length;

    act(() => { result.current.setInputs({ bpm: 60 }); });
    act(() => { result.current.setInputs({ bpm: 55 }); });
    act(() => { result.current.setInputs({ bpm: 50 }); });

    expect(postCount()).toBe(0);
    act(() => { vi.advanceTimersByTime(150); });
    expect(postCount()).toBe(1);
  });

  it("startDemo sets demoState to running on 202", async () => {
    const { result } = renderHook(() => useSimulatedInputs());
    await act(async () => { await result.current.startDemo(); });
    expect(result.current.demoState).toBe("running");
  });
});
