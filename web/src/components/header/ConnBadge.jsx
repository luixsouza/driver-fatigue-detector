import clsx from "clsx";

const STYLE = {
  live:         { dot: "bg-severity-normal animate-pulse-green", label: "ao vivo" },
  connecting:   { dot: "bg-severity-warning",                    label: "conectando" },
  reconnecting: { dot: "bg-severity-alert",                      label: "reconectando" },
};

export function ConnBadge({ status }) {
  const s = STYLE[status] || STYLE.connecting;
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface-1 px-3 py-1 text-xs text-text-1">
      <span className={clsx("h-1.5 w-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
  );
}
