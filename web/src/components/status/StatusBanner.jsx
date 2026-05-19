/**
 * Banner full-width que mostra o estado global do sistema:
 *  - "Aguardando rosto" → sem deteccao
 *  - "Calibrando NN/60" → durante warmup
 *  - "Qualidade ruim: {reason}" → quality.trustworthy === false
 *  - "Normal" → operando
 *  - "ATENÇÃO" → warning
 *  - "ALERTA — FADIGA DETECTADA" → severity === alert
 */
export function StatusBanner({ lastState }) {
  const s = lastState;

  // Sem estado ainda
  if (!s) {
    return (
      <div className="rounded-lg border border-border-1 bg-surface-1 px-4 py-3 text-sm text-text-2">
        Aguardando deteção facial...
      </div>
    );
  }

  // Calibrando
  if (s.calibrating) {
    const progress = Math.round((s.calibration_progress ?? 0) * 100);
    const frames = Math.round((s.calibration_progress ?? 0) * 60);
    return (
      <div className="rounded-lg border-l-4 border-amber-400 bg-amber-500/10 px-4 py-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold text-amber-300">
            Calibrando perfil pessoal — fique relaxado olhando pra câmera
          </span>
          <span className="font-mono text-xs text-amber-200">{frames}/60 frames ({progress}%)</span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-amber-900/40">
          <div
            className="h-full bg-amber-400 transition-all duration-200"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>
    );
  }

  // Qualidade ruim
  if (s.quality_ok === false) {
    return (
      <div className="rounded-lg border-l-4 border-slate-500 bg-slate-500/10 px-4 py-3 text-sm text-slate-300">
        <strong>Qualidade do frame insuficiente</strong>
        {s.quality_reason && <span className="ml-2 text-slate-400">— {s.quality_reason}</span>}
      </div>
    );
  }

  // Severity-based
  const severity = s.severity ?? "normal";
  if (severity === "alert") {
    return (
      <div className="animate-pulse rounded-lg border-l-4 border-red-500 bg-red-500/15 px-4 py-3">
        <div className="flex items-center justify-between">
          <span className="text-base font-bold uppercase tracking-wide text-red-300">
            ⚠ Alerta — Fadiga detectada
          </span>
          <span className="font-mono text-xs text-red-200">
            {s.consecutive_frames ?? 0} frames consecutivos
          </span>
        </div>
      </div>
    );
  }

  if (severity === "warning") {
    return (
      <div className="rounded-lg border-l-4 border-yellow-500 bg-yellow-500/10 px-4 py-3">
        <span className="text-sm font-semibold text-yellow-300">
          Atenção — sinais iniciais de fadiga
        </span>
      </div>
    );
  }

  // Normal
  return (
    <div className="rounded-lg border-l-4 border-emerald-500/70 bg-emerald-500/5 px-4 py-3">
      <div className="flex items-center justify-between">
        <span className="text-sm font-medium text-emerald-300">
          Operando normalmente
        </span>
        <span className="font-mono text-xs text-emerald-200/70">
          EAR {s.ear?.toFixed(3) ?? "—"} · MAR {s.mar?.toFixed(3) ?? "—"}
        </span>
      </div>
    </div>
  );
}
