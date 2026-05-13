import { Play, Square } from "lucide-react";
import clsx from "clsx";

export function DemoButton({ demoState, onStart, onStop }) {
  const running = demoState === "running";
  return (
    <div className="mt-4 flex gap-2">
      <button
        type="button"
        onClick={running ? onStop : onStart}
        className={clsx(
          "flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition",
          running
            ? "bg-severity-alert/15 text-severity-alert hover:bg-severity-alert/25"
            : "bg-ifg-green text-white hover:bg-ifg-green-dark"
        )}
      >
        {running ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        {running ? "Parar cenário demo" : "Modo demo automático"}
      </button>
    </div>
  );
}
