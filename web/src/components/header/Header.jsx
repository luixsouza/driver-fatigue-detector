import { ConnBadge } from "./ConnBadge.jsx";

export function Header({ status, fps = 0 }) {
  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-surface-0/70 px-7 py-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <img src="/ifg-logo.svg" alt="IFG" className="h-9 w-9 rounded-lg shadow-[0_6px_16px_rgba(35,164,85,0.25)]" />
        <div>
          <h1 className="m-0 text-[15px] font-semibold tracking-tight text-text-0">
            Driver Fatigue · Live Monitor
          </h1>
          <p className="m-0 mt-0.5 text-[11px] tracking-[0.04em] text-text-2">
            Sistemas Ubíquos · NumbERS · IFG
          </p>
        </div>
      </div>
      <div className="flex items-center gap-3">
        {fps > 0 && (
          <span className="inline-flex items-center gap-1.5 rounded-full border border-line bg-surface-1 px-3 py-1 font-mono text-xs tabular-nums text-text-1">
            <span className="text-text-2">FPS</span>
            <b className="text-text-0">{fps}</b>
          </span>
        )}
        <ConnBadge status={status} />
      </div>
    </header>
  );
}
