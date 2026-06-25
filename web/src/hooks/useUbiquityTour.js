import { useCallback, useMemo, useState } from "react";

export const TOUR_STEPS = [
  {
    id: "fault",
    label: "Tolerância a falhas",
    what: "Derrubamos o detector de propósito.",
    why: "Num veículo, o sistema não pode morrer — ele se recupera sozinho.",
  },
  {
    id: "heterogeneity",
    label: "Heterogeneidade",
    what: "Um alerta vai para 5 destinos diferentes ao mesmo tempo.",
    why: "Som, log, nuvem, broker… se um falha, os outros seguem (isolamento).",
  },
  {
    id: "privacy",
    label: "Privacidade",
    what: "Lemos o registro que foi gravado em disco.",
    why: "Só números saem do dispositivo — a imagem do motorista nunca.",
  },
  {
    id: "security",
    label: "Segurança",
    what: "Publicamos sem credencial e depois com credencial.",
    why: "Só quem tem a chave consegue falar com o sistema.",
  },
  {
    id: "distribution",
    label: "Distribuição",
    what: "Publicamos um evento pela rede (HTTP) e ele volta no painel.",
    why: "Cada veículo de uma frota se comunica exatamente assim.",
  },
];

/**
 * Reduz a lista crua de eventos `tour` (vinda do SSE) em um estado
 * estruturado por passo, e expõe start()/stop().
 *
 * Retorna { running, finished, aborted, steps, start, stop, requested } onde
 * steps é um mapa { [stepId]: { status, title, narration, data } }.
 */
export function useUbiquityTour(tourEvents) {
  const [requested, setRequested] = useState(false);

  const { running, finished, aborted, steps } = useMemo(() => {
    let run = false;
    let fin = false;
    let abort = false;
    const map = {};
    for (const ev of tourEvents) {
      if (ev.kind === "lifecycle") {
        if (ev.status === "started") { run = true; fin = false; abort = false; }
        else if (ev.status === "finished") { run = false; fin = true; }
        else if (ev.status === "aborted") { run = false; abort = true; }
      } else if (ev.kind === "step" && ev.step) {
        map[ev.step] = {
          status: ev.status,        // running | done | failed
          title: ev.title ?? map[ev.step]?.title,
          narration: ev.narration,
          data: ev.data ?? {},
        };
      }
    }
    return { running: run, finished: fin, aborted: abort, steps: map };
  }, [tourEvents]);

  const start = useCallback(async () => {
    setRequested(true);
    try {
      await fetch("/api/demo/tour/start", { method: "POST" });
    } catch {
      setRequested(false);
    }
  }, []);

  const stop = useCallback(async () => {
    try {
      await fetch("/api/demo/tour/stop", { method: "POST" });
    } catch {}
    setRequested(false);
  }, []);

  return { running: running || (requested && !finished && !aborted), finished, aborted, steps, start, stop, requested };
}
