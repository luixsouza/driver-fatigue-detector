import { Card } from "../ui/Card.jsx";
import { SliderControl } from "./SliderControl.jsx";
import { DemoButton } from "./DemoButton.jsx";

const HOUR_FORMAT = (v) => {
  const h = Math.floor(v);
  const m = Math.round((v - h) * 60);
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`;
};

export function SliderPanel({ inputs, setInputs, demoState, startDemo, stopDemo }) {
  const disabled = demoState === "running";

  return (
    <div className="space-y-4">
      {/* Thresholds reais — afetam o alarme principal */}
      <Card title="Thresholds de detecção (afetam o alarme)">
        <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
          <SliderControl
            label="EAR threshold"
            value={inputs.ear_threshold ?? 0.19}
            min={0.10} max={0.35} step={0.01}
            onChange={(v) => setInputs({ ear_threshold: v })}
          />
          <SliderControl
            label="MAR threshold"
            value={inputs.mar_threshold ?? 0.65}
            min={0.30} max={0.90} step={0.01}
            onChange={(v) => setInputs({ mar_threshold: v })}
          />
          <SliderControl
            label="Frames consecutivos"
            value={inputs.consecutive_frames ?? 22}
            min={5} max={60} step={1}
            onChange={(v) => setInputs({ consecutive_frames: v })}
          />
          <SliderControl
            label="Cabeceio (graus)"
            value={inputs.head_drop_pitch_deg ?? 22}
            min={10} max={45} step={1} unit="°"
            onChange={(v) => setInputs({ head_drop_pitch_deg: v })}
          />
        </div>
        <p className="mt-3 text-xs text-text-2">
          Olho fechado abaixo de <strong>EAR</strong> por <strong>{Math.round(inputs.consecutive_frames ?? 22)} frames</strong>{" "}
          (~{((inputs.consecutive_frames ?? 22) / 30).toFixed(1)}s @ 30fps) dispara alarme.
        </p>
      </Card>

      {/* Sinais simulados — alimentam só o fatigue_index secundário */}
      <Card title="Sinais contextuais simulados (índice secundário)">
        <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
          <SliderControl
            label="BPM"
            value={inputs.bpm ?? 75} min={40} max={120} step={1} unit="bpm"
            onChange={(v) => setInputs({ bpm: v })}
            disabled={disabled}
          />
          <SliderControl
            label="Volante (ruído)"
            value={inputs.steering_noise ?? 0.1} min={0} max={1} step={0.01}
            onChange={(v) => setInputs({ steering_noise: v })}
            disabled={disabled}
          />
          <SliderControl
            label="Tempo dirigindo"
            value={inputs.hours_driving ?? 0} min={0} max={10} step={0.1} unit="h"
            onChange={(v) => setInputs({ hours_driving: v })}
            disabled={disabled}
          />
          <SliderControl
            label="Hora do dia"
            value={inputs.hour_of_day ?? 12} min={0} max={23.99} step={0.25}
            format={HOUR_FORMAT}
            onChange={(v) => setInputs({ hour_of_day: v })}
            disabled={disabled}
          />
        </div>
        <DemoButton demoState={demoState} onStart={startDemo} onStop={stopDemo} />
      </Card>
    </div>
  );
}
