import clsx from "clsx";
import { SeverityIcon } from "./SeverityIcon.jsx";
import { Card } from "../ui/Card.jsx";

const SEVERITY_LABEL = { normal: "Normal", warning: "Atenção", alert: "Alerta" };

// arco semicircular 0-100% — math: angulo de -180 a 0 graus, raio 80
function _arcPath(pct) {
  const angle = -Math.PI + (pct / 100) * Math.PI;
  const x = 100 + 80 * Math.cos(angle);
  const y = 100 + 80 * Math.sin(angle);
  const large = pct > 50 ? 1 : 0;
  return `M 20 100 A 80 80 0 ${large} 1 ${x} ${y}`;
}

export function FatigueGauge({ state }) {
  const value = state?.fatigue_index ?? 0;
  const severity = state?.index_severity ?? "normal";
  const critical = state?.critical ?? false;
  const explain = state?.explain ?? "—";

  return (
    <Card title="Índice de Fadiga" badge={state?.calibrating ? "calibrando…" : null}>
      <div className="flex flex-col items-center">
        <svg viewBox="0 0 200 110" className="w-full max-w-[260px]">
          <defs>
            <linearGradient id="gauge" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%"   stopColor="#4ade80"/>
              <stop offset="50%"  stopColor="#fbbf24"/>
              <stop offset="100%" stopColor="#f43f5e"/>
            </linearGradient>
          </defs>
          <path d="M 20 100 A 80 80 0 0 1 180 100" stroke="#232934" strokeWidth="14" fill="none" strokeLinecap="round"/>
          <path d={_arcPath(value)} stroke="url(#gauge)" strokeWidth="14" fill="none" strokeLinecap="round"
                style={{ transition: "all 300ms ease" }}/>
          <text x="100" y="92" textAnchor="middle" className="fill-text-0 font-semibold tabular-nums"
                style={{ fontSize: 36 }}>
            {Math.round(value)}
          </text>
          <text x="100" y="108" textAnchor="middle" className="fill-text-2" style={{ fontSize: 10 }}>
            / 100
          </text>
        </svg>
        <div className={clsx("mt-2 flex items-center gap-3", critical && "animate-pulse")}>
          <SeverityIcon severity={severity} />
          <div>
            <div className="text-lg font-semibold tracking-tight text-text-0">
              {SEVERITY_LABEL[severity]}{critical && " · Crítico"}
            </div>
            <div className="mt-0.5 text-xs text-text-1">
              {explain}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
