import clsx from "clsx";

const KIND = {
  fatigue_alert:    { stripe: "bg-severity-alert",   title: "Alerta de fadiga" },
  fatigue_recovery: { stripe: "bg-severity-normal",  title: "Motorista recuperou" },
};

function fmt(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleTimeString("pt-BR", { hour12: false });
}

export function EventRow({ event }) {
  const k = KIND[event.event] || { stripe: "bg-severity-warning", title: event.event };
  const meta = [];
  if (event.ear !== undefined) meta.push(`EAR ${(+event.ear).toFixed(2)}`);
  if (event.mar !== undefined) meta.push(`MAR ${(+event.mar).toFixed(2)}`);
  if (event.consecutive_frames !== undefined) meta.push(`conseq ${event.consecutive_frames}`);

  return (
    <div className="grid grid-cols-[4px_1fr_auto] items-center gap-3 rounded-lg border border-line bg-surface-1 px-3 py-2.5 animate-in fade-in slide-in-from-top-1 duration-200">
      <div className={clsx("h-full min-h-7 w-1 rounded", k.stripe)} />
      <div className="min-w-0">
        <div className="text-xs font-semibold text-text-0">{k.title}</div>
        <div className="truncate text-[11px] tabular-nums text-text-2">{meta.join(" · ") || "—"}</div>
      </div>
      <div className="whitespace-nowrap text-[10px] tabular-nums text-text-3">
        {fmt(event.received_at || event.timestamp)}
      </div>
    </div>
  );
}
