import { Header } from "./components/header/Header.jsx";
import { StatusBanner } from "./components/status/StatusBanner.jsx";
import { VideoCard } from "./components/video/VideoCard.jsx";
import { FatigueGauge } from "./components/gauge/FatigueGauge.jsx";
import { SliderPanel } from "./components/sliders/SliderPanel.jsx";
import { MetricsGrid } from "./components/metrics/MetricsGrid.jsx";
import { Timeline } from "./components/timeline/Timeline.jsx";
import { useEventStream } from "./hooks/useEventStream.js";
import { useSimulatedInputs } from "./hooks/useSimulatedInputs.js";
import { useVideoHealth } from "./hooks/useVideoHealth.js";

export default function App() {
  const { status, lastState, events } = useEventStream();
  const { inputs, setInputs, demoState, startDemo, stopDemo } = useSimulatedInputs();
  const { videoOnline } = useVideoHealth();

  return (
    <div className="min-h-screen bg-surface-0 text-text-0">
      <Header status={status} />
      <main className="mx-auto mt-6 grid max-w-[1480px] grid-cols-12 gap-6 px-7 pb-9">
        <div className="col-span-12">
          <StatusBanner lastState={lastState} />
        </div>
        <section className="col-span-12 space-y-4 lg:col-span-8">
          <VideoCard lastState={lastState} videoOnline={videoOnline} />
          <SliderPanel
            inputs={inputs}
            setInputs={setInputs}
            demoState={demoState}
            startDemo={startDemo}
            stopDemo={stopDemo}
          />
        </section>
        <aside className="col-span-12 space-y-4 lg:col-span-4">
          <FatigueGauge state={lastState} />
          <MetricsGrid state={lastState} events={events} />
          <Timeline events={events} />
        </aside>
      </main>
    </div>
  );
}
