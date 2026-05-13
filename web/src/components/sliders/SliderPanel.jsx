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
    <Card title="Sinais simulados">
      <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
        <SliderControl
          label="BPM"
          value={inputs.bpm} min={40} max={120} step={1} unit="bpm"
          onChange={(v) => setInputs({ bpm: v })}
          disabled={disabled}
        />
        <SliderControl
          label="Volante (ruído)"
          value={inputs.steering_noise} min={0} max={1} step={0.01}
          onChange={(v) => setInputs({ steering_noise: v })}
          disabled={disabled}
        />
        <SliderControl
          label="Tempo dirigindo"
          value={inputs.hours_driving} min={0} max={10} step={0.1} unit="h"
          onChange={(v) => setInputs({ hours_driving: v })}
          disabled={disabled}
        />
        <SliderControl
          label="Hora do dia"
          value={inputs.hour_of_day} min={0} max={23.99} step={0.25}
          format={HOUR_FORMAT}
          onChange={(v) => setInputs({ hour_of_day: v })}
          disabled={disabled}
        />
      </div>
      <DemoButton demoState={demoState} onStart={startDemo} onStop={stopDemo} />
    </Card>
  );
}
