import { useEffect, useRef, useState } from "react";

/**
 * Consome /api/stream (SSE) com reconnect exponencial.
 * Retorna { status, lastState, events } onde:
 * - status: "connecting" | "live" | "reconnecting"
 * - lastState: ultimo payload com event === "state" (ou null)
 * - events: lista (max 60) de payloads com event !== "state", mais recente primeiro
 */
export function useEventStream() {
  const [status, setStatus] = useState("connecting");
  const [lastState, setLastState] = useState(null);
  const [events, setEvents] = useState([]);
  const cancelledRef = useRef(false);
  const esRef = useRef(null);

  useEffect(() => {
    cancelledRef.current = false;
    let backoff = 1000;
    let timer = null;

    function connect() {
      const es = new EventSource("/api/stream");
      esRef.current = es;
      es.onopen = () => {
        setStatus("live");
        backoff = 1000;
      };
      es.onmessage = (msg) => {
        try {
          const p = JSON.parse(msg.data);
          if (p.event === "state") {
            setLastState(p);
          } else {
            setEvents((prev) => [p, ...prev].slice(0, 60));
          }
        } catch {
          /* ignore malformed */
        }
      };
      es.onerror = () => {
        setStatus("reconnecting");
        es.close();
        if (!cancelledRef.current) {
          timer = setTimeout(() => {
            backoff = Math.min(backoff * 1.5, 10000);
            connect();
          }, backoff);
        }
      };
    }
    connect();
    return () => {
      cancelledRef.current = true;
      if (timer) clearTimeout(timer);
      esRef.current?.close();
    };
  }, []);

  return { status, lastState, events };
}
