import { useEffect, useState } from "react";

/**
 * Poll /api/health a 3s. Retorna { videoOnline, videoAge }.
 * videoOnline = video_age_seconds < 30 && !== null.
 */
export function useVideoHealth(intervalMs = 3000) {
  const [state, setState] = useState({ videoOnline: false, videoAge: null });

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const r = await fetch("/api/health");
        const h = await r.json();
        if (cancelled) return;
        const age = h.video_age_seconds;
        setState({
          videoOnline: age !== null && age < 30,
          videoAge: age,
        });
      } catch {
        if (!cancelled) setState({ videoOnline: false, videoAge: null });
      }
    }
    tick();
    const id = setInterval(tick, intervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [intervalMs]);

  return state;
}
