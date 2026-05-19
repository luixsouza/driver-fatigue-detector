import clsx from "clsx";

/**
 * Banner full-width que mostra o estado global do sistema. Cores e tokens
 * alinhados com o tema (severity-*, surface-*) em vez de tailwind defaults.
 */
export function StatusBanner({ lastState }) {
  const s = lastState;

  if (!s) {
    return (
      <Wrap accent="line">
        <Title text="Aguardando detecção facial…" muted />
      </Wrap>
    );
  }

  if (s.calibrating) {
    const progress = Math.round((s.calibration_progress ?? 0) * 100);
    const frames = Math.round((s.calibration_progress ?? 0) * 45);
    return (
      <Wrap accent="warning">
        <div className="flex items-center justify-between gap-4">
          <Title text="Calibrando perfil pessoal — fique relaxado olhando pra câmera" accent="warning" />
          <span className="font-mono text-xs text-severity-warning/80">
            {frames}/45 frames · {progress}%
          </span>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-severity-warning/15">
          <div
            className="h-full bg-severity-warning transition-all duration-200"
            style={{ width: `${progress}%` }}
          />
        </div>
      </Wrap>
    );
  }

  if (s.quality_ok === false) {
    return (
      <Wrap accent="line">
        <div className="flex items-center justify-between gap-4">
          <Title text="Qualidade do frame insuficiente" muted />
          {s.quality_reason && (
            <span className="font-mono text-xs text-text-2">{s.quality_reason}</span>
          )}
        </div>
      </Wrap>
    );
  }

  const severity = s.severity ?? "normal";
  if (severity === "alert") {
    return (
      <Wrap accent="alert" pulsing>
        <div className="flex items-center justify-between gap-4">
          <Title text="⚠ ALERTA — FADIGA DETECTADA" accent="alert" bold />
          <span className="font-mono text-xs text-severity-alert">
            {s.consecutive_frames ?? 0} frames consecutivos
          </span>
        </div>
      </Wrap>
    );
  }

  if (severity === "warning") {
    return (
      <Wrap accent="warning">
        <Title text="Atenção — sinais iniciais de fadiga" accent="warning" />
      </Wrap>
    );
  }

  return (
    <Wrap accent="normal">
      <div className="flex items-center justify-between gap-4">
        <Title text="Operando normalmente" accent="normal" />
        <span className="font-mono text-xs text-severity-normal/70">
          EAR {s.ear?.toFixed(3) ?? "—"} · MAR {s.mar?.toFixed(3) ?? "—"}
        </span>
      </div>
    </Wrap>
  );
}

// --- Subcomponents ---

const ACCENT = {
  normal:  "border-severity-normal/60  bg-severity-normal/5",
  warning: "border-severity-warning/60 bg-severity-warning/10",
  alert:   "border-severity-alert      bg-severity-alert/15",
  line:    "border-line                bg-surface-1",
};

function Wrap({ accent, pulsing, children }) {
  return (
    <div
      className={clsx(
        "rounded-card border-l-4 px-4 py-3",
        ACCENT[accent] || ACCENT.line,
        pulsing && "animate-pulse",
      )}
    >
      {children}
    </div>
  );
}

function Title({ text, accent, bold, muted }) {
  const color =
    accent === "alert"   ? "text-severity-alert"   :
    accent === "warning" ? "text-severity-warning" :
    accent === "normal"  ? "text-severity-normal"  :
    muted ? "text-text-2" : "text-text-0";
  return (
    <span className={clsx(bold ? "text-base font-bold uppercase tracking-wide" : "text-sm font-semibold", color)}>
      {text}
    </span>
  );
}
