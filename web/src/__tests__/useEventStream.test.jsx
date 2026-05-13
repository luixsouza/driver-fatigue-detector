import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useEventStream } from "../hooks/useEventStream";

class MockEventSource {
  constructor(url) {
    this.url = url;
    MockEventSource.lastInstance = this;
  }
  close() { this.closed = true; }
}

beforeEach(() => {
  vi.stubGlobal("EventSource", MockEventSource);
});

describe("useEventStream", () => {
  it("opens an EventSource on /api/stream", () => {
    renderHook(() => useEventStream());
    expect(MockEventSource.lastInstance.url).toBe("/api/stream");
  });

  it("populates lastState on state event", () => {
    const { result } = renderHook(() => useEventStream());
    act(() => {
      MockEventSource.lastInstance.onopen?.();
      MockEventSource.lastInstance.onmessage?.({
        data: JSON.stringify({ event: "state", fatigue_index: 42 }),
      });
    });
    expect(result.current.lastState.fatigue_index).toBe(42);
    expect(result.current.status).toBe("live");
  });

  it("pushes non-state events into events list", () => {
    const { result } = renderHook(() => useEventStream());
    act(() => {
      MockEventSource.lastInstance.onmessage?.({
        data: JSON.stringify({ event: "fatigue_alert", ear: 0.2 }),
      });
    });
    expect(result.current.events[0].event).toBe("fatigue_alert");
  });
});
