import clsx from "clsx";
import {
  Play, Square, Check, X, Loader2, Circle,
  ServerCrash, Boxes, FileLock2, ShieldCheck, Share2,
} from "lucide-react";
import { TOUR_STEPS } from "../../hooks/useUbiquityTour.js";

const STEP_ICON = {
  fault: ServerCrash,
  heterogeneity: Boxes,
  privacy: FileLock2,
  security: ShieldCheck,
  distribution: Share2,
};

function StatusGlyph({ status }) {
  if (status === "done") return <Check className="h-4 w-4 text-severity-normal" />;
  if (status === "failed") return <X className="h-4 w-4 text-severity-alert" />;
  if (status === "running") return <Loader2 className="h-4 w-4 animate-spin text-severity-warning" />;
  return <Circle className="h-3 w-3 text-text-3" />;
}

function Chip({ ok, children }) {
  return (
    <span className={clsx(
      "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium",
      ok ? "bg-severity-normal/12 text-severity-normal"
         : "bg-severity-alert/12 text-severity-alert",
    )}>
      {ok ? <Check className="h-3 w-3" /> : <X className="h-3 w-3" />}
      {children}
    </span>
  );
}

function FaultDetail({ data }) {
  if (data.available === false) return <span className="text-text-2">detector não embutido</span>;
  if (data.respawn_seconds == null) return <span className="text-text-2">aguardando supervisor…</span>;
  return <Chip ok>detector caiu → respawn em {data.respawn_seconds.toFixed(1)}s</Chip>;
}

function HeterogeneityDetail({ data }) {
  return (
    <div className="flex flex-wrap gap-1">
      {(data.sinks ?? []).map((s) => (
        <span key={s.name} title={s.error || `${s.kind} · ${s.latency_ms}ms`}
          className={clsx(
            "inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] font-medium",
            s.isolated ? "bg-severity-alert/12 text-severity-alert"
                       : "bg-severity-normal/12 text-severity-normal",
          )}>
          {s.isolated ? <X className="h-3 w-3" /> : <Check className="h-3 w-3" />}
          {s.name}
          {s.isolated && <span className="opacity-70">isolado</span>}
        </span>
      ))}
    </div>
  );
}

function PrivacyDetail({ data }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Chip ok={data.no_image}>{data.no_image ? "0 imagem" : "imagem detectada!"}</Chip>
      <span className="font-mono text-[10px] text-text-2">{(data.keys ?? []).length} campos numéricos</span>
    </div>
  );
}

function SecurityDetail({ data }) {
  const wo = data.without_key ?? {}, wk = data.with_key ?? {};
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Chip ok={wo.blocked}>sem chave → {wo.status}</Chip>
      <Chip ok={wk.accepted}>com chave → {wk.status}</Chip>
    </div>
  );
}

function DistributionDetail({ data }) {
  return (
    <div className="flex flex-wrap items-center gap-1.5">
      <Chip ok={data.http_status === 202}>POST /api/events → {data.http_status}</Chip>
      {data.http_post_ms != null && (
        <span className="font-mono text-[10px] text-text-2">{data.http_post_ms}ms</span>
      )}
    </div>
  );
}

const DETAIL = {
  fault: FaultDetail,
  heterogeneity: HeterogeneityDetail,
  privacy: PrivacyDetail,
  security: SecurityDetail,
  distribution: DistributionDetail,
};

function StepCard({ meta, state }) {
  const Icon = STEP_ICON[meta.id] ?? Circle;
  const status = state?.status ?? "pending";
  const Detail = DETAIL[meta.id];
  const active = status === "running";
  return (
    <li className={clsx(
      "rounded-xl border p-3.5 transition",
      status === "pending" && "border-line bg-surface-1 opacity-55",
      active && "border-severity-warning/50 bg-severity-warning/5",
      status === "done" && "border-line bg-surface-1",
      status === "failed" && "border-severity-alert/50 bg-severity-alert/5",
    )}>
      <div className="mb-2 flex items-center gap-2">
        <Icon className="h-4 w-4 text-text-2" />
        <span className="flex-1 text-sm font-semibold text-text-0">{meta.label}</span>
        <StatusGlyph status={status} />
      </div>

      <dl className="space-y-1 text-xs leading-snug">
        <div className="flex gap-1.5">
          <dt className="shrink-0 font-semibold text-text-2">O quê:</dt>
          <dd className="m-0 text-text-1">{meta.what}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="shrink-0 font-semibold text-text-2">Por quê:</dt>
          <dd className="m-0 text-text-1">{meta.why}</dd>
        </div>
      </dl>

      {status !== "pending" && (
        <div className="mt-2.5 border-t border-line pt-2.5">
          {active ? (
            <span className="text-[11px] text-text-2">executando…</span>
          ) : (
            <div className="space-y-1">
              <div className="text-[10px] font-semibold uppercase tracking-wide text-text-3">Resultado</div>
              {Detail && <Detail data={state.data ?? {}} />}
            </div>
          )}
        </div>
      )}
    </li>
  );
}

export function TourPanel({ tour }) {
  const { running, finished, steps, start, stop } = tour;

  return (
    <Section running={running} finished={finished} onStart={start} onStop={stop}>
      <ol className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {TOUR_STEPS.map((meta) => (
          <StepCard key={meta.id} meta={meta} state={steps[meta.id]} />
        ))}
      </ol>
    </Section>
  );
}

function Section({ running, finished, onStart, onStop, children }) {
  const badge = finished ? "concluído" : running ? "em execução" : "pronto";
  return (
    <section className="shadow-card rounded-card border border-line bg-surface-1 p-5">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-text-0">Tour Ubíquo</h2>
            <span className="rounded-full border border-line px-2 py-0.5 text-[10px] uppercase tracking-[0.08em] text-text-2">
              {badge}
            </span>
          </div>
          <p className="mt-1 max-w-2xl text-xs text-text-2">
            Demonstração automática das 5 propriedades de sistemas ubíquos que não
            aparecem no uso normal. Um clique executa tudo e mostra o resultado ao vivo.
          </p>
        </div>
        <button
          type="button"
          onClick={running ? onStop : onStart}
          className={clsx(
            "inline-flex shrink-0 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition",
            running
              ? "bg-severity-alert/15 text-severity-alert hover:bg-severity-alert/25"
              : "bg-ifg-green text-white hover:bg-ifg-green-dark",
          )}
        >
          {running ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
          {running ? "Parar tour" : "Iniciar Tour Ubíquo"}
        </button>
      </div>
      {children}
    </section>
  );
}
