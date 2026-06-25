import clsx from "clsx";

export function Card({ children, className = "", title, badge }) {
  return (
    <section className={clsx(
      "shadow-card rounded-card border border-line bg-surface-1 p-5",
      className,
    )}>
      {title && (
        <header className="mb-3 flex items-center justify-between">
          <h2 className="text-[11px] font-semibold uppercase tracking-[0.12em] text-text-2">
            {title}
          </h2>
          {badge && (
            <span className="rounded-full border border-line px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-text-2">
              {badge}
            </span>
          )}
        </header>
      )}
      {children}
    </section>
  );
}
