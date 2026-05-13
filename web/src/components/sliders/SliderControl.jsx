import clsx from "clsx";

export function SliderControl({ label, value, min, max, step, unit, onChange, disabled, format }) {
  const display = format ? format(value) : `${Number(value).toFixed(step < 1 ? 2 : 0)}${unit ? ` ${unit}` : ""}`;
  return (
    <label className={clsx("block", disabled && "opacity-60")}>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-text-2">{label}</span>
        <span className="font-mono text-sm tabular-nums text-text-0">{display}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full"
      />
    </label>
  );
}
