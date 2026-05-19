import { useEffect, useRef, useState } from "react";

/**
 * Calcula FPS efetivo da stream de eventos (lastState). Janela deslizante
 * dos ultimos N timestamps. Retorna numero arredondado.
 */
export function useFpsTracker(lastState, windowSize = 30) {
  const tsRef = useRef([]);
  const [fps, setFps] = useState(0);

  useEffect(() => {
    if (!lastState?.timestamp) return;
    const now = lastState.timestamp;
    const buf = tsRef.current;
    buf.push(now);
    if (buf.length > windowSize) buf.shift();
    if (buf.length >= 2) {
      const dt = buf[buf.length - 1] - buf[0];
      if (dt > 0) {
        setFps(Math.round((buf.length - 1) / dt));
      }
    }
  }, [lastState, windowSize]);

  return fps;
}
