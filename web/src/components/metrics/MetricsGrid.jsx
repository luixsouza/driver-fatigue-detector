import clsx from "clsx";
import { Card } from "../ui/Card.jsx";

function Metric({ label, value, hint, accent }) {
  const valColor =
    accent === "alert"   ? "text-severity-alert"   :
    accent === "warning" ? "text-severity-warning" :
    accent === "normal"  ? "text-severity-normal"  :
    "text-text-0";
  return (
    <div className="rounded-lg border border-line bg-surface-1 p-3">
      <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.14em] text-text-2">{label}</div>
      <div className={clsx("font-mono text-xl font-semibold tabular-nums tracking-tight", valColor)}>
        {value}
        {hint && <small className="ml-1.5 text-[11px] font-normal text-text-2">{hint}</small>}
      </div>
    </div>
  );
}

export function MetricsGrid({ state, events }) {
  const alerts = events.filter((e) => e.event === "fatigue_alert").length;
  const recoveries = events.filter((e) => e.event === "fatigue_recovery").length;
  const consec = state?.consecutive_frames ?? 0;
  const severity = state?.severity ?? "normal";
  return (
    <Card title="Métricas">
      <div className="grid grid-cols-2 gap-2">
        <Metric label="EAR" value={state?.ear?.toFixed(3) ?? "—"} />
        <Metric label="MAR" value={state?.mar?.toFixed(3) ?? "—"} />
        <Metric
          label="Frames consec."
          value={consec}
          hint="olho fechado"
          accent={severity === "alert" ? "alert" : severity === "warning" ? "warning" : null}
        />
        <Metric label="Alertas" value={alerts} accent={alerts > 0 ? "alert" : null} />
        <Metric label="Recoveries" value={recoveries} accent={recoveries > 0 ? "normal" : null} />
        <Metric
          label="Calibração"
          value={state?.calibrating ? `${Math.round((state.calibration_progress ?? 0) * 100)}%` : "ok"}
          accent={state?.calibrating ? "warning" : "normal"}
        />
      </div>
    </Card>
  );
}
