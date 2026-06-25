import { Sun, Moon } from "lucide-react";
import { ConnBadge } from "./ConnBadge.jsx";

export function Header({ status, fps = 0, theme, onToggleTheme }) {
  return (
    <header className="sticky top-0 z-20 border-b border-line bg-surface-0/80 backdrop-blur">
      <div className="mx-auto flex max-w-[1280px] items-center justify-between px-6 py-3.5">
        <div className="flex items-center gap-3">
          <img src="/ifg-logo.svg" alt="IFG" className="h-8 w-8 rounded-lg" />
          <div>
            <h1 className="m-0 text-[14px] font-semibold tracking-tight text-text-0">
              Driver Fatigue Monitor
            </h1>
            <p className="m-0 text-[11px] text-text-2">Sistemas Ubíquos · IFG</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {fps > 0 && (
            <span className="hidden items-center gap-1.5 rounded-full border border-line px-2.5 py-1 font-mono text-[11px] tabular-nums text-text-1 sm:inline-flex">
              <span className="text-text-2">FPS</span>
              <b className="text-text-0">{fps}</b>
            </span>
          )}
          <ConnBadge status={status} />
          <button
            type="button"
            onClick={onToggleTheme}
            aria-label="Alternar tema"
            title="Alternar tema claro/escuro"
            className="grid h-8 w-8 place-items-center rounded-full border border-line text-text-1 transition hover:bg-surface-2 hover:text-text-0"
          >
            {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
          </button>
        </div>
      </div>
    </header>
  );
}
