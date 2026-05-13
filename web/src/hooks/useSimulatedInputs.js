import { useCallback, useEffect, useRef, useState } from "react";

const INITIAL = {
  bpm: 75,
  steering_noise: 0.1,
  hours_driving: 0,
  hour_of_day: new Date().getHours(),
};

const DEBOUNCE_MS = 100;
const DEMO_POLL_MS = 500;

/**
 * Gerencia o estado dos sliders e sincroniza com /api/inputs (POST debounced).
 * Quando demoState === "running", faz polling GET /api/inputs e atualiza inputs
 * com o que o servidor diz (script do servidor sobrescreve).
 */
export function useSimulatedInputs() {
  const [inputs, setInputs] = useState(INITIAL);
  const [demoState, setDemoState] = useState("idle"); // idle | running

  const debounceRef = useRef(null);
  const pollRef = useRef(null);

  const setInputsLocal = useCallback((updater) => {
    setInputs((prev) => {
      const next = typeof updater === "function" ? updater(prev) : { ...prev, ...updater };
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        fetch("/api/inputs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(next),
        }).catch(() => {});
      }, DEBOUNCE_MS);
      return next;
    });
  }, []);

  const startDemo = useCallback(async () => {
    try {
      const r = await fetch("/api/demo/start", { method: "POST" });
      if (r.status === 202) {
        setDemoState("running");
      }
    } catch {}
  }, []);

  const stopDemo = useCallback(async () => {
    try {
      await fetch("/api/demo/stop", { method: "POST" });
    } catch {}
    setDemoState("idle");
  }, []);

  useEffect(() => {
    if (demoState !== "running") {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch("/api/inputs");
        if (r.ok) {
          const data = await r.json();
          setInputs(data);
        }
      } catch {}
    }, DEMO_POLL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [demoState]);

  return { inputs, setInputs: setInputsLocal, demoState, startDemo, stopDemo };
}
