# Fase 3 — Fusão Multimodal + UI React/Tailwind (NumbERS / IFG)

**Data:** 2026-05-13
**Status:** Proposto (aguardando revisão)
**Branch sugerida:** `feat/fase3-fusao-multimodal-ui`
**Base:** Fase 2.5 (`feat/fase2-5-falsos-positivos`)
**Restrição dura herdada:** zero dependência paga, zero serviço remoto em runtime. Tudo local, libs livres (BSD/MIT/Apache).
**Specs anteriores:**
- `docs/superpowers/specs/2026-04-24-driver-fatigue-ubiquitous-design.md`
- `docs/superpowers/specs/2026-04-24-fase2-fontes-saidas-gravacao-design.md`
- `docs/superpowers/specs/2026-04-27-fase2-5-reducao-falsos-positivos-validacao-contexto.md`

---

## 1. Problema

A Fase 2.5 entregou um detector confiável para o sinal de visão computacional (EAR/MAR/cabeceio com calibração por usuário e histerese). Restam duas lacunas que separam o sistema de uma demo de **fusão multimodal** apresentável no artigo:

1. **Decisão de fadiga baseada em um único modal.** O motorista pode estar com olhos abertos e ainda assim sonolento (BPM baixo, dirigindo há 6h, madrugada, volante oscilando). A literatura de drowsiness detection (revisão em `docs/research/drowsiness-detection-study.md`) é clara: estado da arte é fusão de sinais.
2. **UI com aparência genérica de protótipo.** O dashboard HTML/CSS atual é funcional mas não tem identidade visual; precisa carregar a marca institucional (IFG / NumbERS) e ter polimento de produto pra apresentação acadêmica.

Estado atual do que já existe e **não** será refeito:
- Pipeline Clean Architecture (`bootstrap.py`, use case `monitor_driver`, ports & adapters).
- Detector MediaPipe + evaluator com calibração, histerese, cooldown, discriminação fala/bocejo.
- Transporte web: `http.server` + SSE (`/api/stream`) + MJPEG (`/api/video`) + POST webhook (`/api/events`) + auth `X-API-Key`.
- Sinks externos: HTTP webhook, MQTT, sound, JSONL.

## 2. Objetivo

Adicionar **fusão multimodal explicável** ao sistema e reescrever o frontend com identidade visual institucional, sem reescrever o backend nem quebrar contratos públicos.

Dois eixos:

- **Eixo A — Motor de fusão fuzzy:** combina sinais reais (EAR/MAR/cabeceio do MediaPipe) com sinais simulados (BPM, volante, tempo de direção, hora do dia) num **Índice de Fadiga 0–100%** explicável, usando lógica fuzzy (scikit-fuzzy). Cada decisão acompanha texto curto explicando quais regras foram ativadas.
- **Eixo B — Frontend React + Vite + Tailwind:** reescreve o dashboard com componentes inspirados em [`luixsouza/numbers-site`](https://github.com/luixsouza/numbers-site), logo do IFG no header, e layout "Cockpit" (vídeo grande à esquerda, gauge de índice à direita, sliders embaixo, timeline lateral).

Eixos são independentes em código, mas casam na UI: o gauge renderiza o índice do eixo A; os sliders do eixo B alimentam o motor do eixo A.

## 3. Não-objetivos

- Treinar modelo ML supervisionado para o índice (fuzzy é a escolha — explicabilidade > F1).
- Migrar transporte SSE/MJPEG/POST para WebSocket.
- Integrar OBD-II, sensores cardíacos reais ou qualquer hardware externo. Sliders são deliberadamente simulados (decisão de escopo: demo acadêmica).
- Mudar o pipeline Clean Architecture, contratos de sinks externos (HTTP/MQTT/JSONL), ou o evento `fatigue_alert` que esses sinks consomem.
- Multi-usuário simultâneo no dashboard.
- React Router / múltiplas páginas. Tudo numa SPA single-page.
- State management lib (Redux, Zustand, etc.). `useState`/`useReducer` cobrem.

---

## 4. Eixo A — Motor de Fusão Fuzzy

### 4.1 Domínio (contratos)

Arquivo novo: `src/driver_fatigue/domain/fatigue_index.py`.

```python
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class FatigueInputs:
    """Snapshot consumido pelo motor de fusão a cada frame.

    Campos normalizados pra 0-1 quando possível pra desacoplar do
    baseline de cada usuário.
    """
    # sinais reais (vêm do FatigueState atual)
    ear_norm: float            # 0.0=olho fechado, 1.0=olho totalmente aberto (relativo ao baseline)
    mar_norm: float            # 0.0=boca fechada, 1.0=bocejo aberto
    head_drop_frames: int      # contador de frames com pitch alto sustentado
    consecutive_eyes_closed: int

    # sinais simulados (vêm do POST /api/inputs)
    bpm: float                 # 40-120 (clampado)
    steering_noise: float      # 0-1 (clampado)
    hours_driving: float       # 0-10 (clampado)
    hour_of_day: float         # 0-23.99 (clampado)


@dataclass(frozen=True, slots=True)
class FatigueIndex:
    value: float               # 0-100
    severity: str              # "normal" | "warning" | "alert"
    top_contributors: tuple[str, ...]  # nomes das regras com maior força ativada (max 3)
    explain: str               # texto curto pra UI ("BPM baixo + tempo alto")


class IndexEvaluator(Protocol):
    def compute(self, inputs: FatigueInputs) -> FatigueIndex: ...
```

**Por que `Protocol` e não classe abstrata:** mantém o padrão já usado em `application/ports.py`. Permite substituir por mock nos testes sem herança.

### 4.2 Infraestrutura (implementação fuzzy)

Arquivo novo: `src/driver_fatigue/infrastructure/fatigue_inference/fuzzy.py`.

**Dependência nova:** `scikit-fuzzy` (BSD-3-Clause). Adicionada como extra: `pip install driver-fatigue[fuzzy]`. Se a dep não estiver instalada, o `bootstrap` injeta um `NoOpIndexEvaluator` que retorna `value=0, severity=state.severity` (sistema continua funcional, só sem fusão).

**Variáveis fuzzy (`skfuzzy.control`):**

| Antecedente | Universo | Conjuntos (trapezoidais/triangulares) |
|---|---|---|
| `eyes_closed_signal` | `[0, 1]` em 100 pontos | `aberto` ⊂ [0.7, 1.0], `parcial` ⊂ [0.3, 0.7], `fechado` ⊂ [0, 0.35] |
| `mouth_yawn_signal` | `[0, 1]` em 100 pontos | `fechada` ⊂ [0, 0.3], `falando` ⊂ [0.25, 0.55], `bocejo` ⊂ [0.5, 1.0] |
| `head_drop` | `[0, 60]` frames | `nenhum` ⊂ [0, 8], `leve` ⊂ [6, 25], `pesado` ⊂ [20, 60] |
| `bpm` | `[40, 120]` | `baixo` ⊂ [40, 60], `normal` ⊂ [55, 95], `alto` ⊂ [90, 120] |
| `steering` | `[0, 1]` | `estavel` ⊂ [0, 0.3], `oscilando` ⊂ [0.2, 0.65], `errante` ⊂ [0.55, 1.0] |
| `driving_time` | `[0, 10]` h | `curto` ⊂ [0, 2.5], `medio` ⊂ [1.5, 5.5], `longo` ⊂ [4, 10] |
| `circadian_risk` | `[0, 1]` | `seguro` ⊂ [0, 0.3], `medio` ⊂ [0.2, 0.7], `vale` ⊂ [0.6, 1.0] |

**Consequente (saída):**

| Saída | Universo | Conjuntos |
|---|---|---|
| `fatigue_index` | `[0, 100]` | `normal` ⊂ [0, 35], `atencao` ⊂ [25, 65], `alerta` ⊂ [55, 85], `critico` ⊂ [75, 100] |

**Pré-processamento (Python puro, antes de entrar no fuzzy):**

- `eyes_closed_signal = 1 - ear_norm` (inverte: quanto menor o EAR, maior o sinal de olho fechado).
- `mouth_yawn_signal = clamp(mar_norm, 0, 1)`.
- `circadian_risk = circadian_curve(hour_of_day)`:
  - 0.9 em janela 02:00–06:00 (vale circadiano noturno),
  - 0.6 em janela 14:00–16:00 (vale pós-prandial),
  - 0.1 fora dessas janelas,
  - transições lineares de 30min nas bordas pra evitar descontinuidade.

**Regras (12 regras núcleo):**

```
R1.  eyes_closed=fechado E head_drop>=leve              → alerta
R2.  eyes_closed=fechado E mouth_yawn=bocejo            → critico
R3.  mouth_yawn=bocejo E driving_time=longo             → alerta
R4.  bpm=baixo E eyes_closed!=aberto                    → alerta
R5.  bpm=baixo E circadian_risk=vale                    → atencao
R6.  steering=errante E driving_time>=medio             → alerta
R7.  steering=oscilando E circadian_risk>=medio         → atencao
R8.  driving_time=longo E circadian_risk=vale           → atencao
R9.  eyes_closed=parcial E mouth_yawn=falando           → normal     (anti-FP: falando ≠ bocejo)
R10. head_drop=pesado                                   → critico
R11. bpm=normal E steering=estavel E eyes_closed=aberto → normal
R12. driving_time=longo E bpm=baixo E eyes_closed!=aberto → critico
```

**Defuzzificação:** centroide (`skfuzzy.defuzz(..., 'centroid')`).

**Mapeamento `fatigue_index.value → severity`:**

| value | severity (no SSE) |
|---|---|
| `< 35` | `normal` |
| `35 ≤ v < 60` | `warning` |
| `60 ≤ v < 80` | `alert` |
| `v ≥ 80` | `alert` (com flag `critical=True` no payload) |

Compatibilidade: sinks externos continuam recebendo só `normal`/`warning`/`alert`. O `critical=True` é opcional, consumido só pelo front pra um estilo visual mais intenso.

**Explainability:** após `compute`, o `FuzzyIndexEvaluator` inspeciona `simulation.output[<rule>]` (força de ativação) de cada regra, ordena descrescente, pega as 3 maiores e mapeia pra rótulos amigáveis:

```python
_RULE_LABELS = {
    "R1": "olhos fechados + cabeceio",
    "R2": "olhos fechados + bocejo",
    "R3": "bocejo + tempo alto",
    "R4": "BPM baixo + olhos parciais",
    # ...
}
```

`explain` = junta os 2 mais fortes com " + " (ex.: `"BPM baixo + tempo alto"`).

### 4.3 Bootstrap

`src/driver_fatigue/bootstrap.py` ganha:

```python
def _build_index_evaluator(settings) -> IndexEvaluator:
    if not settings.fatigue_index.enabled:
        return _NoOpIndexEvaluator()
    try:
        from driver_fatigue.infrastructure.fatigue_inference.fuzzy import FuzzyIndexEvaluator
        return FuzzyIndexEvaluator()
    except ImportError:
        _log.warning("scikit-fuzzy nao instalado; rodando sem indice de fadiga")
        return _NoOpIndexEvaluator()
```

`AppSettings` ganha `fatigue_index: FatigueIndexSettings` com `enabled: bool = True`. Configurável via YAML.

### 4.4 Integração no ciclo do detector

`interfaces/web/server.py::_InProcessFramePresenter` (e o `_InProcessAlertSink`) recebem o `IndexEvaluator` via construtor.

A cada frame, dentro de `present()` / `publish_state()`:

1. Lê snapshot dos simulated_inputs via `_get_simulated_snapshot()`.
2. Calcula `ear_norm = state.ear / max(state.baseline.ear_rest, 0.05)` (clampado a 0–1).
3. Calcula `mar_norm = clamp((state.mar - state.baseline.mar_rest) / max(state.baseline.mar_std * 3, 0.1), 0, 1)`.
4. Monta `FatigueInputs(...)`.
5. `index = evaluator.compute(inputs)`.
6. Adiciona `fatigue_index`, `index_severity`, `top_contributors`, `explain` ao payload SSE `state`.

**Custo computacional:** scikit-fuzzy executa ~12 regras em ~3-5ms em CPU média. A 30fps temos 33ms por frame; folga confortável. Se virar gargalo, cacheamos o `ControlSystem` (já é stateful, criamos uma vez no `__init__`).

### 4.5 Tipo de evento e payload

Payload `state` (acréscimos em **negrito**):

```json
{
  "event": "state",
  "timestamp": 1715630400.123,
  "frame_index": 1842,
  "ear": 0.31, "mar": 0.42,
  "severity": "warning",
  "consecutive_frames": 8,
  "calibrating": false,
  "calibration_progress": 1.0,
  "quality_ok": true,
  "quality_reason": "",
  "fatigue_index": 64.5,
  "index_severity": "alert",
  "critical": false,
  "top_contributors": ["R4", "R5"],
  "explain": "BPM baixo + circadiano em vale"
}
```

---

## 5. Eixo A — Endpoints novos

### 5.1 `POST /api/inputs`

Atualiza snapshot dos sliders. Sujeito a `_require_auth()` (mesma regra de `/api/events`).

**Request:**
```json
{ "bpm": 62, "steering_noise": 0.45, "hours_driving": 2.5, "hour_of_day": 14.5 }
```

Todos os campos opcionais; ausentes preservam valor anterior. Faixas inválidas são clampadas (não retornam 400 — sliders mudam rápido, validação rígida atrapalha).

**Response:** `202 {"status": "accepted"}`.

### 5.2 `GET /api/inputs`

Retorna o snapshot atual. Usado pelo front durante o modo demo pra sincronizar sliders com o script do servidor.

**Response:** `200 {"bpm": 62, "steering_noise": 0.45, "hours_driving": 2.5, "hour_of_day": 14.5}`.

### 5.3 `POST /api/demo/start`

Inicia o cenário scriptado (sob auth).

**Body:** opcional `{"scenario": "drowsy_night"}` (default: `drowsy_night`).

**Comportamento:** dispara uma daemon thread `_DemoScenarioRunner` que sobrescreve `_simulated_inputs` ao longo de 30s:

| t (s) | bpm | steering | hours | hour_of_day | comentário |
|---|---|---|---|---|---|
| 0 | 75 | 0.10 | 5.0 | 15.0 | linha de base saudável |
| 5 | 70 | 0.15 | 5.5 | 15.0 | leve fadiga |
| 10 | 62 | 0.30 | 6.0 | 15.0 | tempo+volante começam |
| 15 | 55 | 0.50 | 6.5 | 15.0 | BPM cai, volante oscila |
| 20 | 50 | 0.65 | 7.0 | 03.5 | jump pra madrugada |
| 25 | 48 | 0.75 | 7.5 | 03.5 | crítico |
| 30 | fim — mantém último estado |

Interpolação linear entre pontos (10Hz de update). Apenas um demo pode rodar por vez; chamada subsequente retorna `409 {"status": "already_running"}`.

**Response:** `202 {"status": "started", "duration_seconds": 30}`.

### 5.4 `POST /api/demo/stop`

Aborta cenário em execução. Sliders ficam congelados no último valor escrito (não revertem ao estado pré-demo, propositadamente — usuário pode continuar interagindo a partir dali).

**Response:** `202 {"status": "stopped"}` ou `200 {"status": "not_running"}`.

---

## 6. Eixo B — Frontend React + Vite + Tailwind

### 6.1 Estrutura

Diretório novo `web/` na raiz:

```
web/
├── package.json
├── vite.config.js
├── tailwind.config.js
├── postcss.config.js
├── index.html
├── public/
│   └── ifg-logo.svg
└── src/
    ├── main.jsx
    ├── App.jsx
    ├── index.css
    ├── components/
    │   ├── header/
    │   │   ├── Header.jsx
    │   │   └── ConnBadge.jsx
    │   ├── video/
    │   │   ├── VideoCard.jsx
    │   │   └── AlertFlash.jsx
    │   ├── gauge/
    │   │   ├── FatigueGauge.jsx
    │   │   └── SeverityIcon.jsx
    │   ├── sliders/
    │   │   ├── SliderPanel.jsx
    │   │   ├── SliderControl.jsx
    │   │   └── DemoButton.jsx
    │   ├── timeline/
    │   │   ├── Timeline.jsx
    │   │   └── EventRow.jsx
    │   ├── metrics/
    │   │   └── MetricsGrid.jsx
    │   └── ui/
    │       ├── Card.jsx
    │       └── ProgressBar.jsx
    └── hooks/
        ├── useEventStream.js
        ├── useSimulatedInputs.js
        └── useVideoHealth.js
```

### 6.2 Build pipeline

`web/vite.config.js`:

```js
export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/driver_fatigue/interfaces/web/static",
    emptyOutDir: true,
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
});
```

- `npm run build` (em `web/`) gera arquivos diretamente na pasta servida pelo Python.
- `npm run dev` (em `web/`) sobe Vite em `:5173` com proxy para `:8000` (dev workflow).

**Servidor Python:**
- `interfaces/web/server.py::_serve_static` ganha suporte a hash-asset paths (Vite gera `assets/index-<hash>.js`).
- Aceita `.svg`, `.woff2`, `.png` no `_guess_mime` (Vite pode emitir esses).
- `GET /` continua servindo `index.html`; `GET /assets/*` é tratado como static.

**SPA fallback:** como é single-page sem router, não precisa fallback 404→index.html.

### 6.3 Stack

| Dep | Versão alvo | Por quê |
|---|---|---|
| react | 18.x | estável, hooks |
| react-dom | 18.x | — |
| vite | 5.x | build rápido |
| @vitejs/plugin-react | 4.x | — |
| tailwindcss | 3.x | mesma versão do numbers-site |
| postcss | 8.x | dep do Tailwind |
| autoprefixer | 10.x | — |
| lucide-react | latest | ícones (mesma família que numbers-site usa) |
| clsx | latest | conditional className |

Zero dependência de runtime adicional além dessas.

### 6.4 Tokens visuais (Tailwind)

`tailwind.config.js`:

```js
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ifg: {
          green: "#23A455",      // verde institucional IFG
          "green-dark": "#1C7A3F",
          "green-light": "#4CC97A",
        },
        surface: {
          0: "#08090c",
          1: "#0e1116",
          2: "#14181f",
          3: "#1a1f28",
        },
        line: {
          DEFAULT: "#232934",
          strong: "#2c333f",
        },
        text: {
          0: "#f1f4f9",
          1: "#a8b1bf",
          2: "#6b7385",
          3: "#444c5c",
        },
        severity: {
          normal: "#4ade80",
          warning: "#fbbf24",
          alert: "#f43f5e",
        },
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "Segoe UI", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      borderRadius: {
        card: "16px",
      },
    },
  },
};
```

Identidade visual: verde IFG `#23A455` no logo, accents e estados "normal". Severities mantêm semântica de cor universal (verde/amarelo/vermelho).

### 6.5 Componentes — comportamento

**`Header.jsx`:** sticky top, blur 12px, border-bottom. Logo IFG (SVG em `public/ifg-logo.svg`) à esquerda + título "Driver Fatigue · Live Monitor" + subtítulo "Sistemas Ubíquos · NumbERS · IFG". `ConnBadge` à direita, pílula com bullet animado: verde "ao vivo" / amarelo "conectando" / vermelho "reconectando".

**`VideoCard.jsx`:** `<img src="/api/video">` ocupando o card 16:9. Placeholder quando `useVideoHealth()` reporta detector offline. Overlay com pílulas nos cantos: esquerda "REC" pulsante, direita "EAR {valor} · MAR {valor}" em fonte mono. `AlertFlash` overlay com borda vermelha pulsante quando `index_severity === "alert"`.

**`FatigueGauge.jsx`:** arco SVG semicircular 0–100%. Gradiente verde→amarelo→vermelho conforme o valor sobe. No centro: número grande tabular (`text-6xl font-semibold`), abaixo: badge da severity, abaixo: linha `explain` em `text-text-1 text-sm`. Transição CSS smooth (300ms) entre valores. Quando `critical=true`, adiciona shake animation sutil.

**`SliderPanel.jsx`:** grid responsivo (4 cols desktop, 2 tablet, 1 mobile) de `SliderControl`. Cada slider tem label uppercase tracking-wider, valor à direita em fonte tabular, range nativo HTML estilizado via Tailwind (`accent-ifg-green`). Mudanças disparam `setInputs()` do `useSimulatedInputs` (debounce interno 100ms). Bot ão "▶ Modo Demo Automático" full-width abaixo, com estado `loading` durante os 30s do script — texto vira "Cenário rodando… 12s / 30s", botão fica desabilitado, e exibe botão secundário "■ Parar".

Durante demo: `useSimulatedInputs` faz polling GET `/api/inputs` a 500ms e atualiza estado local — sliders se movem sozinhos refletindo o script do servidor. Quando demo termina/para, polling cessa, controle volta pro usuário.

**`MetricsGrid.jsx`:** 2x2 de cards pequenos. Cada card: label uppercase tracking-wider em text-text-2, valor em `text-2xl font-semibold` tabular. Métricas: EAR, MAR, Alertas (contador), Recoveries (contador).

**`Timeline.jsx`:** lista vertical de `EventRow`. Max 60 itens (FIFO). Cada row: stripe colorida 4px à esquerda (verde/amarelo/vermelho) + título + meta (EAR/MAR/consecutivos) + timestamp à direita. `animate-in` 250ms fade+slide quando entra. Scroll interno com scrollbar custom.

### 6.6 Hooks

**`useEventStream()`** retorna `{ status, lastState, events }`.

```js
// pseudo
const [status, setStatus] = useState("connecting");
const [lastState, setLastState] = useState(null);
const [events, setEvents] = useState([]);

useEffect(() => {
  let es; let cancelled = false; let backoff = 1000;
  function connect() {
    es = new EventSource("/api/stream");
    es.onopen = () => { setStatus("live"); backoff = 1000; };
    es.onmessage = (m) => {
      const p = JSON.parse(m.data);
      if (p.event === "state") setLastState(p);
      else setEvents((prev) => [p, ...prev].slice(0, 60));
    };
    es.onerror = () => {
      setStatus("reconnecting");
      es.close();
      if (!cancelled) setTimeout(connect, backoff = Math.min(backoff * 1.5, 10000));
    };
  }
  connect();
  return () => { cancelled = true; es?.close(); };
}, []);
```

**`useSimulatedInputs()`** retorna `{ inputs, setInputs, demoState, startDemo, stopDemo }`. Internamente:
- `useState` pra cada slider.
- Debounce 100ms via `useRef` + `setTimeout`; ao expirar, `fetch POST /api/inputs`.
- `demoState`: `"idle" | "running" | "stopping"`. Quando `"running"`, dispara polling 500ms via `setInterval` em `GET /api/inputs` e atualiza `inputs` com a resposta.
- `startDemo()`: POST `/api/demo/start`, seta `demoState="running"`, inicia polling.
- `stopDemo()`: POST `/api/demo/stop`, para polling, seta `demoState="idle"`.

**`useVideoHealth()`** retorna `{ videoOnline, lastSeen }`. Polling `GET /api/health` a 3s; expõe `videoOnline = h.video_age_seconds !== null && h.video_age_seconds < 30`.

### 6.7 Layout (App.jsx, classes Tailwind aproximadas)

```jsx
<div className="min-h-screen bg-surface-0 text-text-0">
  <Header status={status} />
  <main className="mx-auto max-w-[1480px] px-7 pb-9 grid grid-cols-12 gap-6 mt-6">
    <section className="col-span-12 lg:col-span-8 space-y-4">
      <VideoCard lastState={lastState} videoOnline={videoOnline} />
      <SliderPanel inputs={inputs} setInputs={setInputs} demoState={demoState} ... />
    </section>
    <aside className="col-span-12 lg:col-span-4 space-y-4">
      <FatigueGauge state={lastState} />
      <MetricsGrid state={lastState} events={events} />
      <Timeline events={events} />
    </aside>
  </main>
</div>
```

Breakpoint `lg` (1024px): abaixo disso vira coluna única, mantendo ordem vídeo → sliders → gauge → métricas → timeline.

---

## 7. Configuração

`AppSettings` ganha um sub-modelo novo:

```python
class FatigueIndexSettings(BaseModel):
    enabled: bool = True
    # Override de pesos/regras pra calibrar via YAML sem mexer no código.
    # Default: tudo no fuzzy.py.
```

`config/web-demo.yaml` ganha:

```yaml
fatigue_index:
  enabled: true
```

Sem outros campos por enquanto — pesos das funções de pertinência ficam no código, refatorar pra YAML é YAGNI agora.

---

## 8. Testes

### 8.1 Unitários

`tests/unit/test_fuzzy_index.py`:
- Caso normal: motorista acordado, dirigindo há 1h, BPM 75 → `value < 30`.
- Caso bocejo+olhos parciais: → `value` em zona `warning`.
- Caso olhos fechados+cabeceio: → `value > 60`.
- Caso noite madrugada+BPM baixo+tempo alto: → `value > 75`.
- Caso anti-FP: motorista falando (mar alto, ear normal) → `value < 40`.
- Cada regra principal tem 1 teste de ativação isolada.

`tests/unit/test_circadian.py`: curva circadiana retorna valores esperados em pontos-chave (02:00 → 0.9, 12:00 → 0.1, 15:00 → 0.6, transições).

### 8.2 Contrato

`tests/integration/test_inputs_endpoint.py`:
- `POST /api/inputs` clampa valores fora de faixa.
- Auth: 401 sem header quando `api_key` configurado.
- `GET /api/inputs` retorna snapshot escrito.

`tests/integration/test_demo_scenario.py`:
- `POST /api/demo/start` retorna 202 e move BPM ao longo do tempo.
- Segundo `start` enquanto rodando retorna 409.
- `POST /api/demo/stop` aborta.

### 8.3 E2E (smoke)

`tests/e2e/test_dashboard_fusion.py`:
- Sobe `serve()` em porta livre com detector mockado.
- Conecta ao SSE.
- Faz POST `/api/inputs` com BPM=45.
- Confirma que próximos eventos `state` têm `fatigue_index` > valor de baseline.

### 8.4 Front

`web/src/__tests__/` (Vitest + React Testing Library):
- `useEventStream` reconecta após erro.
- `useSimulatedInputs` debounca POST.
- `FatigueGauge` renderiza valor + severity correto.
- `SliderPanel` chama `setInputs` no change.

---

## 9. Migração e compatibilidade

**Quebra de cliente externo?** Não:
- `fatigue_alert` continua tendo os mesmos campos (`ear`, `mar`, `severity`, `consecutive_frames`).
- `state` ganha campos novos; clientes existentes que ignoram chaves desconhecidas continuam OK.
- Sinks HTTP/MQTT/JSONL/sound: zero mudança.

**Quebra de UX local?** Sim, intencional: o dashboard HTML estático atual será substituído pelo build do Vite. Não há plano de manter o antigo (manteria dois frontends em paralelo).

**Rollback:** branch `feat/fase3-fusao-multimodal-ui`; PR único; se algo der errado, revert.

---

## 10. Riscos e mitigações

| Risco | Mitigação |
|---|---|
| `scikit-fuzzy` não instalado em ambiente de produção | `_NoOpIndexEvaluator` fallback automático com log warning; sistema continua funcional sem o índice. |
| Custo de 3-5ms por frame causa drop de FPS | `ControlSystem` é criado uma vez no `__init__`. Se ainda assim virar gargalo, throttling pra 10Hz (1/3 dos frames) — índice não precisa ser 30Hz, severity sim. |
| Sliders enviando POST a cada pixel arrastado saturam o servidor | Debounce 100ms no front + clamp+merge no servidor (ignora chaves ausentes). |
| Build do Vite gera nomes de asset com hash que o servidor Python não conhece | `_serve_static` é genérico (qualquer file dentro de `static/`); Vite emite paths absolutos em `index.html`, servidor pega sem mudança. |
| Logo IFG tem direitos restritos | Usar versão oficial pública do IFG (já em uso no `numbers-site`); arquivo em `web/public/` commitado. |
| Demo script roda enquanto usuário mexe no slider | Front desabilita sliders durante `demoState === "running"`; servidor sobrescreve por design. |

---

## 11. Critérios de aceite

- [ ] `pip install -e .[fuzzy]` instala `scikit-fuzzy`.
- [ ] `pytest` passa, incluindo novos testes (>=15 testes adicionados entre unit/integration/e2e).
- [ ] `cd web && npm install && npm run build` gera bundle em `src/driver_fatigue/interfaces/web/static/`.
- [ ] `python -m driver_fatigue.interfaces.web` sobe servidor, página carrega React app no `/`.
- [ ] Sliders enviam POST `/api/inputs`; índice no gauge reage em <500ms.
- [ ] `POST /api/demo/start` anima sliders ao longo de 30s; gauge sobe progressivamente; timeline registra alert quando índice cruza 60.
- [ ] Logo IFG visível no header; verde IFG presente como cor de marca.
- [ ] Página em mobile (375px) é usável (1 coluna, scroll vertical).
- [ ] Demo no Layout A · Cockpit conforme mockup aprovado.

---

## 12. Fora deste spec (próximas fases)

- Eixo C — Validador de contexto ONNX (Fase 2.5 Etapa B, já especificado).
- Persistência histórica do índice (gráfico temporal das últimas N minutos).
- Export do log da sessão (JSONL → CSV → PDF de relatório acadêmico).
- Multi-câmera / multi-motorista.
- Hardware real (OBD-II, wearable BPM).

---

## 13. Referências

- `docs/research/drowsiness-detection-study.md` — revisão acadêmica.
- [scikit-fuzzy docs](https://scikit-fuzzy.github.io/scikit-fuzzy/).
- [luixsouza/numbers-site](https://github.com/luixsouza/numbers-site) — base visual.
- Spec 2026-04-27 Fase 2.5 — heurísticas que rodam upstream do motor.
