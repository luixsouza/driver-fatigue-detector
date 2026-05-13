import clsx from "clsx";

export function AlertFlash({ active }) {
  return (
    <div className={clsx(
      "pointer-events-none absolute inset-0 rounded-[inherit]",
      active && "animate-flash-red border-8 border-severity-alert",
    )} />
  );
}
