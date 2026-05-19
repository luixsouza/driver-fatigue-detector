/**
 * Overlay full-screen com borda pulsante e vinheta vermelha quando o
 * detector está em estado de alerta. Não intercepta cliques.
 */
export function AlertOverlay({ active }) {
  if (!active) return null;
  return (
    <div
      aria-hidden
      className="pointer-events-none fixed inset-0 z-50 animate-flash-red"
      style={{
        // gradiente radial: bordas vermelhas, centro transparente — mantém leitura da UI
        background:
          "radial-gradient(ellipse at center, transparent 50%, rgba(244,63,94,0.15) 100%)",
      }}
    >
      <div className="absolute inset-x-0 top-0 h-1 bg-severity-alert" />
      <div className="absolute inset-x-0 bottom-0 h-1 bg-severity-alert" />
      <div className="absolute inset-y-0 left-0 w-1 bg-severity-alert" />
      <div className="absolute inset-y-0 right-0 w-1 bg-severity-alert" />
    </div>
  );
}
