import { Header } from "./components/header/Header.jsx";
import { StatusBanner } from "./components/status/StatusBanner.jsx";
import { AlertOverlay } from "./components/status/AlertOverlay.jsx";
import { VideoCard } from "./components/video/VideoCard.jsx";
import { FatigueGauge } from "./components/gauge/FatigueGauge.jsx";
import { SliderPanel } from "./components/sliders/SliderPanel.jsx";
import { MetricsGrid } from "./components/metrics/MetricsGrid.jsx";
import { Timeline } from "./components/timeline/Timeline.jsx";
import { TourPanel } from "./components/tour/TourPanel.jsx";
import { useEventStream } from "./hooks/useEventStream.js";
import { useSimulatedInputs } from "./hooks/useSimulatedInputs.js";
import { useUbiquityTour } from "./hooks/useUbiquityTour.js";
import { useVideoHealth } from "./hooks/useVideoHealth.js";
import { useFpsTracker } from "./hooks/useFpsTracker.js";
import { useTheme } from "./hooks/useTheme.js";

export default function App() {
  const { status, lastState, events, tourEvents } = useEventStream();
  const { inputs, setInputs, demoState, startDemo, stopDemo } = useSimulatedInputs();
  const tour = useUbiquityTour(tourEvents);
  const { videoOnline } = useVideoHealth();
  const fps = useFpsTracker(lastState);
  const { theme, toggle } = useTheme();

  const alerting = lastState?.severity === "alert";

  return (
    <div className="min-h-screen bg-surface-0 text-text-0">
      <Header status={status} fps={fps} theme={theme} onToggleTheme={toggle} />
      <AlertOverlay active={alerting} />

      <main className="mx-auto max-w-[1280px] space-y-6 px-6 pb-12 pt-6">
        <StatusBanner lastState={lastState} />

        {/* Monitor ao vivo */}
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <VideoCard lastState={lastState} videoOnline={videoOnline} />
          </div>
          <aside className="space-y-6">
            <FatigueGauge state={lastState} />
            <MetricsGrid state={lastState} events={events} />
          </aside>
        </section>

        {/* Tour Ubíquo — destaque, largura total */}
        <TourPanel tour={tour} />

        {/* Controles e histórico */}
        <section className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <SliderPanel
            inputs={inputs}
            setInputs={setInputs}
            demoState={demoState}
            startDemo={startDemo}
            stopDemo={stopDemo}
          />
          <Timeline events={events} />
        </section>
      </main>
    </div>
  );
}
