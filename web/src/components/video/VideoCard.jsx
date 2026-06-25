import { useEffect, useRef, useState } from "react";
import { Video, VideoOff } from "lucide-react";
import { AlertFlash } from "./AlertFlash.jsx";

export function VideoCard({ lastState, videoOnline }) {
  const imgRef = useRef(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!videoOnline) {
      setLoaded(false);
      if (imgRef.current) imgRef.current.removeAttribute("src");
      return;
    }
    if (imgRef.current && !imgRef.current.src) {
      imgRef.current.src = `/api/video?_=${Date.now()}`;
    }
  }, [videoOnline]);

  const ear = lastState?.ear?.toFixed(2) ?? "—";
  const mar = lastState?.mar?.toFixed(2) ?? "—";
  const isAlert = lastState?.index_severity === "alert" || lastState?.severity === "alert";

  return (
    <div className="shadow-card relative aspect-video overflow-hidden rounded-card border border-line bg-surface-2">
      <img
        ref={imgRef}
        alt=""
        className="block h-full w-full object-contain"
        onLoad={() => setLoaded(true)}
        onError={() => setLoaded(false)}
      />
      {!loaded && (
        <div className="absolute inset-0 grid place-items-center bg-surface-2 text-center text-text-2">
          <div className="max-w-sm px-8">
            <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-2xl border border-line bg-surface-1">
              {videoOnline ? <Video className="h-7 w-7" /> : <VideoOff className="h-7 w-7" />}
            </div>
            <h3 className="m-0 mb-1.5 text-base font-semibold text-text-0">
              {videoOnline ? "Carregando stream…" : "Sem vídeo ao vivo"}
            </h3>
            <p className="text-sm leading-relaxed">
              {videoOnline
                ? "Aguardando os primeiros frames da câmera."
                : "O detector de visão (câmera + mesh facial) não está ativo neste ambiente. O Tour Ubíquo abaixo funciona normalmente."}
            </p>
          </div>
        </div>
      )}
      <div className="pointer-events-none absolute inset-0 z-10">
        <div className="absolute left-4 top-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-surface-0/70 px-3 py-1 text-xs tabular-nums text-text-1 backdrop-blur">
          <span className="h-2 w-2 rounded-full bg-severity-alert animate-pulse" />
          {loaded ? "ao vivo" : "offline"}
        </div>
        <div className="absolute right-4 top-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-surface-0/70 px-3 py-1 text-xs tabular-nums text-text-1 backdrop-blur">
          <span className="font-mono">EAR <b className="text-text-0">{ear}</b> · MAR <b className="text-text-0">{mar}</b></span>
        </div>
      </div>
      <AlertFlash active={isAlert} />
    </div>
  );
}
