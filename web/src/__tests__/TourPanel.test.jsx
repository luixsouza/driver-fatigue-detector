import { describe, it, expect, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TourPanel } from "../components/tour/TourPanel.jsx";

const baseTour = {
  running: false, finished: false, steps: {},
  start: vi.fn(), stop: vi.fn(),
};

describe("TourPanel", () => {
  it("renderiza os 5 passos e o botão de iniciar", () => {
    render(<TourPanel tour={baseTour} />);
    expect(screen.getByText("Tolerância a falhas")).toBeTruthy();
    expect(screen.getByText("Heterogeneidade")).toBeTruthy();
    expect(screen.getByText("Privacidade")).toBeTruthy();
    expect(screen.getByText("Segurança")).toBeTruthy();
    expect(screen.getByText("Distribuição")).toBeTruthy();
    expect(screen.getByText("Iniciar Tour Ubíquo")).toBeTruthy();
  });

  it("mostra os detalhes reais de um passo concluído (heterogeneidade)", () => {
    const tour = {
      ...baseTour,
      steps: {
        heterogeneity: {
          status: "done",
          narration: "4/5 sinks entregaram",
          data: {
            delivered: 4, isolated: 1,
            sinks: [
              { name: "Log", kind: "stdout", delivered: true, latency_ms: 16, isolated: false },
              { name: "MQTT", kind: "rede", delivered: false, latency_ms: 15, isolated: true, error: "broker offline" },
            ],
          },
        },
      },
    };
    render(<TourPanel tour={tour} />);
    expect(screen.getByText("Log")).toBeTruthy();
    expect(screen.getByText("MQTT")).toBeTruthy();
    expect(screen.getByText("isolado")).toBeTruthy();
  });

  it("troca o rótulo do botão para 'Parar tour' quando rodando", () => {
    render(<TourPanel tour={{ ...baseTour, running: true }} />);
    expect(screen.getByText("Parar tour")).toBeTruthy();
  });
});
