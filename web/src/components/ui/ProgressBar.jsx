import clsx from "clsx";

const SEVERITY_BG = {
  normal:  "bg-severity-normal",
  warning: "bg-severity-warning",
  alert:   "bg-severity-alert",
};

export function ProgressBar({ value, max = 100, severity = "normal" }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="h-1.5 w-full rounded-full bg-line overflow-hidden">
      <div
        className={clsx("h-full rounded-full transition-[width,background] duration-300", SEVERITY_BG[severity])}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
