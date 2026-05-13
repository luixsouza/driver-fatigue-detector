import clsx from "clsx";

export function Card({ children, className = "", title, badge }) {
  return (
    <section className={clsx(
      "rounded-card bg-gradient-to-b from-surface-1 to-surface-2",
      "border border-line shadow-[0_16px_40px_-16px_rgba(0,0,0,0.4)]",
      "p-5", className,
    )}>
      {title && (
        <header className="mb-3 flex items-center justify-between">
          <h2 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-2">
            {title}
          </h2>
          {badge && <span className="text-[9px] uppercase tracking-[0.1em] text-text-2">{badge}</span>}
        </header>
      )}
      {children}
    </section>
  );
}
