import { Card } from "../ui/Card.jsx";

function Metric({ label, value, hint }) {
  return (
    <div className="rounded-lg border border-line bg-surface-1 p-3">
      <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.14em] text-text-2">{label}</div>
      <div className="font-mono text-xl font-semibold tabular-nums tracking-tight text-text-0">
        {value}
        {hint && <small className="ml-1.5 text-[11px] font-normal text-text-2">{hint}</small>}
      </div>
    </div>
  );
}

export function MetricsGrid({ state, events }) {
  const alerts = events.filter((e) => e.event === "fatigue_alert").length;
  const recoveries = events.filter((e) => e.event === "fatigue_recovery").length;
  return (
    <Card title="Métricas">
      <div className="grid grid-cols-2 gap-2">
        <Metric label="EAR" value={state?.ear?.toFixed(2) ?? "—"} />
        <Metric label="MAR" value={state?.mar?.toFixed(2) ?? "—"} />
        <Metric label="Alertas" value={alerts} />
        <Metric label="Recoveries" value={recoveries} />
      </div>
    </Card>
  );
}
