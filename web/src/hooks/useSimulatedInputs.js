import { useCallback, useEffect, useRef, useState } from "react";

// Inputs simulados (alimentam fatigue_index secundário).
const INITIAL_SIM = {
  bpm: 75,
  steering_noise: 0.1,
  hours_driving: 0,
  hour_of_day: new Date().getHours(),
};

// Thresholds reais (afetam o severity/alarme principal).
// Valores iniciais são placeholders — o servidor manda os reais via GET /api/inputs.
const INITIAL_THRESHOLDS = {
  ear_threshold: 0.19,
  mar_threshold: 0.65,
  consecutive_frames: 22,
  head_drop_pitch_deg: 22,
};

const DEBOUNCE_MS = 100;
const DEMO_POLL_MS = 500;

/**
 * Gerencia sim inputs + thresholds reais, sincroniza com /api/inputs.
 * Bootstrap: na montagem faz GET pra pegar valores reais do detector.
 * Durante demo: faz polling 2Hz e sobrescreve sim inputs com o que o servidor diz.
 */
export function useSimulatedInputs() {
  const [inputs, setInputs] = useState({ ...INITIAL_SIM, ...INITIAL_THRESHOLDS });
  const [demoState, setDemoState] = useState("idle"); // idle | running

  const debounceRef = useRef(null);
  const pollRef = useRef(null);

  // Bootstrap: na primeira render busca o estado atual do servidor
  // (thresholds vêm do YAML, sim inputs vêm do servidor).
  useEffect(() => {
    let cancelled = false;
    fetch("/api/inputs")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (!cancelled && data) {
          setInputs((prev) => ({ ...prev, ...data }));
        }
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, []);

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
          setInputs((prev) => ({ ...prev, ...data }));
        }
      } catch {}
    }, DEMO_POLL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [demoState]);

  return { inputs, setInputs: setInputsLocal, demoState, startDemo, stopDemo };
}
