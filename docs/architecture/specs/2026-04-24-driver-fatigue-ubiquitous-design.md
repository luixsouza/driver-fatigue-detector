# Driver Fatigue Detector — Arquitetura Ubíqua (Clean Architecture)

**Data:** 2026-04-24
**Status:** Proposto (aguardando revisão)

## 1. Contexto e motivação

O projeto atual (`src/main.py`, ~110 linhas) detecta sonolência via EAR/MAR com dlib, exibe janela OpenCV e toca alarme pygame. Tudo em um único arquivo, com webcam hardcoded e sem separação de responsabilidades.

**Objetivo:** tornar o projeto ubíquo — o mesmo núcleo de detecção rodando em PC, servidor, edge e contêiner, com múltiplas entradas (webcam, RTSP, arquivo), múltiplas saídas (som local, webhook HTTP, MQTT, log), com ou sem GUI, configurável por arquivo/env, empacotado em Docker e integrável via API REST.

A refatoração também moderniza a visualização: troca dlib (68 landmarks) por MediaPipe Face Mesh (468 landmarks + íris) e adiciona renderização polida com overlays translúcidos, curvas suaves, HUD e estados reativos.

## 2. Princípios arquiteturais

Clean Architecture em 4 camadas com regra de dependência apontando sempre para dentro:

```
Interfaces (CLI, API, Config)
        ↓
Infrastructure (adapters concretos)
        ↓
Application (use cases + ports)
        ↓
Domain (entidades + regras puras)
```

- **Domain** não conhece nada externo — nem OpenCV, nem MediaPipe, nem pygame.
- **Application** define interfaces (ports) e orquestra. Não instancia adapters.
- **Infrastructure** implementa ports usando bibliotecas concretas.
- **Interfaces** são os entry points (CLI, REST) que acionam a Application.
- **Composition root** (`bootstrap.py`) lê a config e monta o grafo de dependências — é o único lugar que "costura" tudo.

## 3. Camadas em detalhe

### 3.1 Domain

Python puro, sem dependências externas além de `numpy` (para operações vetoriais com pontos).

**Entidades e value objects:**

```python
# domain/entities.py
@dataclass(frozen=True)
class Frame:
    image: np.ndarray   # BGR
    timestamp: float    # segundos (monotonic)
    index: int          # contador sequencial

@dataclass(frozen=True)
class Point:
    x: float
    y: float

@dataclass(frozen=True)
class FaceLandmarks:
    """Representação semântica, independente do detector usado."""
    left_eye_contour:  tuple[Point, ...]
    right_eye_contour: tuple[Point, ...]
    left_iris:   tuple[Point, ...] | None
    right_iris:  tuple[Point, ...] | None
    mouth_outer: tuple[Point, ...]
    mouth_inner: tuple[Point, ...]
    face_oval:   tuple[Point, ...]

@dataclass(frozen=True)
class FatigueState:
    ear: float
    mar: float
    consecutive_frames: int
    is_fatigued: bool
    is_yawning: bool
    severity: Literal["normal", "warning", "alert"]

@dataclass(frozen=True)
class FatigueEvent:
    timestamp: float
    state: FatigueState
    frame_index: int
```

**Value object de configuração de domínio:**

```python
# domain/value_objects.py
@dataclass(frozen=True)
class FatigueThresholds:
    ear_threshold: float = 0.25
    mar_threshold: float = 0.60
    consecutive_frames: int = 20
    warning_ratio: float = 0.85  # fração do threshold que dispara "warning"
```

**Funções puras:**

```python
# domain/metrics.py
def eye_aspect_ratio(eye: Sequence[Point]) -> float: ...
def mouth_aspect_ratio(mouth: Sequence[Point]) -> float: ...

# domain/evaluator.py
def evaluate_fatigue(
    landmarks: FaceLandmarks,
    thresholds: FatigueThresholds,
    previous: FatigueState,
) -> FatigueState: ...
```

O `evaluate_fatigue` é puro: dado o mesmo input, mesmo output. Facilita teste.

### 3.2 Application

Define ports (interfaces) e use cases.

**Ports:**

```python
# application/ports.py
class VideoSourcePort(Protocol):
    def read(self) -> Frame | None: ...   # None quando acabou/desconectou
    def release(self) -> None: ...

class FaceDetectorPort(Protocol):
    def detect(self, frame: Frame) -> list[FaceLandmarks]: ...

class AlertSinkPort(Protocol):
    def notify(self, event: FatigueEvent) -> None: ...
    def on_recovery(self, frame_index: int) -> None: ...
    # notify: chamado quando severity vira "alert"
    # on_recovery: chamado quando sai de "alert" de volta para "normal"
    #              (permite ao SoundSink parar o alarme, ao MQTT publicar "ok", etc.)

class FramePresenterPort(Protocol):
    def present(self, frame: Frame, landmarks: list[FaceLandmarks], state: FatigueState) -> None: ...
    def close(self) -> None: ...
    def should_stop(self) -> bool: ...  # ex: usuário apertou 'q'
```

**Use cases:**

```python
# application/use_cases/detect_fatigue.py
class DetectFatigueUseCase:
    def __init__(self, detector: FaceDetectorPort, thresholds: FatigueThresholds): ...
    def execute(self, frame: Frame, previous: FatigueState) -> tuple[FatigueState, list[FaceLandmarks]]: ...

# application/use_cases/monitor_driver.py
class MonitorDriverUseCase:
    def __init__(
        self,
        source: VideoSourcePort,
        detect: DetectFatigueUseCase,
        sinks: AlertSinkPort,
        presenter: FramePresenterPort,
    ): ...
    def run(self) -> None:
        """Loop principal: frame → detect → notify sinks → present."""
```

### 3.3 Infrastructure

Adapters concretos, agrupados por port:

```
infrastructure/
├── video_sources/
│   ├── webcam.py         # cv2.VideoCapture(int)
│   ├── rtsp.py           # cv2.VideoCapture(rtsp_url)
│   └── file.py           # cv2.VideoCapture(path)
├── detectors/
│   └── mediapipe_detector.py   # MediaPipe FaceMesh → FaceLandmarks semântico
├── alert_sinks/
│   ├── sound.py          # pygame
│   ├── http_webhook.py   # httpx POST
│   ├── mqtt.py           # paho-mqtt
│   ├── log.py            # logging estruturado (JSON)
│   └── composite.py      # fan-out para vários sinks
├── presenters/
│   ├── opencv_window.py  # janela com RenderingTheme
│   ├── file_recorder.py  # grava MP4 via cv2.VideoWriter
│   ├── composite.py      # combina window + recorder
│   └── headless.py       # no-op (retorna should_stop via SIGINT)
└── rendering/
    ├── theme.py          # RenderingTheme (value object)
    ├── curves.py         # Catmull-Rom / B-spline smoothing
    ├── overlay.py        # fillPoly + addWeighted helpers
    ├── glow.py           # GaussianBlur + blend aditivo
    └── hud.py            # painel com EAR/MAR/FPS/estado
```

**Detalhe do MediaPipe adapter:** mapeia índices fixos do FaceMesh para o contrato semântico de `FaceLandmarks`. Tabelas de índices (`LEFT_EYE_INDICES`, `RIGHT_IRIS_INDICES`, etc.) ficam como constantes no módulo.

### 3.4 Rendering (qualidade visual)

O `OpenCvWindowPresenter` recebe um `RenderingTheme` e aplica em ordem:

1. **Face oval** — linha translúcida fina (alpha 0.25) em toda a face
2. **Overlay translúcido** nos olhos e boca — `fillPoly` em layer separado, combinado com `cv2.addWeighted(alpha=0.35)`
3. **Curvas suaves** — contornos interpolados com Catmull-Rom (20 pontos entre cada par) e desenhados com `cv2.LINE_AA`
4. **Glow neon** — cópia dos contornos borrada com `cv2.GaussianBlur(k=15)` e somada com blend aditivo (`cv2.add`)
5. **Íris** — círculos concêntricos (externo + pupila) se o detector fornecer
6. **HUD** — painel inferior translúcido com EAR, MAR, frames consecutivos, FPS, estado e barrinha de progresso até o threshold
7. **Estados reativos:**
   - `normal` → ciano `(0, 255, 255)` suave
   - `warning` → âmbar `(0, 200, 255)` pulsante (seno do tempo modula alpha)
   - `alert` → vermelho `(50, 50, 255)` + borda pulsando + vignette vermelho na tela toda

```python
# domain/rendering_theme.py  (domain porque é config semântica, não implementação)
@dataclass(frozen=True)
class RenderingTheme:
    color_normal:  tuple[int, int, int] = (255, 255, 0)    # ciano BGR
    color_warning: tuple[int, int, int] = (0, 200, 255)    # âmbar
    color_alert:   tuple[int, int, int] = (50, 50, 255)    # vermelho
    overlay_alpha: float = 0.35
    glow_enabled:  bool = True
    glow_sigma:    int = 15
    show_hud:      bool = True
    show_face_oval: bool = True
    smoothing_steps: int = 20  # interpolação Catmull-Rom
```

### 3.5 Interfaces

**CLI (`interfaces/cli/main.py`):**

```bash
driver-fatigue run \
    --source webcam:1 \
    --sinks sound,mqtt,http \
    --presenter window+record:out.mp4 \
    --config config/default.yaml
```

**API (`interfaces/api/server.py`)** (FastAPI, Fase 3):

- `POST /sessions` — inicia sessão com config
- `GET  /sessions/{id}` — estado atual
- `DELETE /sessions/{id}` — encerra
- `WS   /sessions/{id}/events` — stream de `FatigueEvent`
- `GET  /health`

**Config (`interfaces/config/settings.py`)** — pydantic-settings lendo env + YAML com precedência clara (env sobrescreve YAML sobrescreve defaults).

## 4. Estrutura de pastas

```
src/driver_fatigue/
├── domain/
│   ├── entities.py
│   ├── value_objects.py
│   ├── metrics.py
│   ├── evaluator.py
│   └── rendering_theme.py
├── application/
│   ├── ports.py
│   └── use_cases/
│       ├── detect_fatigue.py
│       └── monitor_driver.py
├── infrastructure/
│   ├── video_sources/{webcam,rtsp,file}.py
│   ├── detectors/mediapipe_detector.py
│   ├── alert_sinks/{sound,http_webhook,mqtt,log,composite}.py
│   ├── presenters/{opencv_window,file_recorder,composite,headless}.py
│   └── rendering/{curves,overlay,glow,hud}.py
├── interfaces/
│   ├── cli/main.py
│   ├── api/{server,schemas}.py
│   └── config/settings.py
└── bootstrap.py

tests/
├── unit/            # domain + use cases (puros, sem hardware)
├── integration/     # adapters com fixtures de vídeo
└── e2e/             # fluxo completo usando assets/test_sonolency.mp4

config/
├── default.yaml
└── example.env

docker/
├── Dockerfile.headless
└── Dockerfile.api

docker-compose.yml
pyproject.toml   # substitui requirements/requirements.txt
```

## 5. Fluxo de dados

```
Webcam/RTSP/File (VideoSourcePort)
        │ Frame
        ▼
MediaPipe Detector (FaceDetectorPort)
        │ List[FaceLandmarks]
        ▼
DetectFatigueUseCase
        │ FatigueState (ear, mar, severity)
        ▼
MonitorDriverUseCase
        ├── FatigueEvent ──► CompositeSink ──► {Sound, Webhook, MQTT, Log}
        └── Frame+State+Landmarks ──► CompositePresenter ──► {Window, FileRecorder}
```

## 6. Tratamento de erros

- **VideoSource falha** (desconexão RTSP, webcam removida): `read()` retorna `None`; o use case tenta `reconnect()` com backoff exponencial (3 tentativas, 2^n segundos) e, se falhar, emite `SourceFailureEvent` para os sinks e encerra com código 1.
- **Detector sem face detectada**: retorna lista vazia; use case mantém `FatigueState` anterior com `consecutive_frames` zerado.
- **Sink falha** (rede indisponível para webhook/MQTT): cada sink captura sua própria exceção e loga; `CompositeSink` nunca propaga erro de um sink para os outros. Garantia: um MQTT offline não derruba o som local.
- **Config inválida**: pydantic-settings falha no boot com mensagem acionável; `bootstrap.py` sai com código 2.

**Regra de severity** (no `evaluate_fatigue`):

- `normal` — `ear >= ear_threshold` e `mar <= mar_threshold`
- `warning` — um dos dois cruzou o limiar pela primeira vez, mas `consecutive_frames < consecutive_frames_threshold * warning_ratio`
- `alert` — `consecutive_frames >= consecutive_frames_threshold` (estado confirmado de fadiga)

Transição `alert → normal` dispara `on_recovery` nos sinks.

## 7. Estratégia de testes

| Camada | Tipo | Exemplos |
|---|---|---|
| Domain | Unit puro | EAR/MAR para formas conhecidas, `evaluate_fatigue` em todos os estados |
| Application | Unit com fakes | `MonitorDriverUseCase` com `FakeVideoSource`, `FakeDetector`, spy sinks |
| Infrastructure | Integration | `MediapipeFaceDetector` contra frames de `assets/test_sonolency.mp4`; `HttpWebhookSink` contra `respx` |
| End-to-end | E2E | CLI processando `test_sonolency.mp4` em modo headless → verifica eventos gerados |

Cobertura alvo: **100% domain**, **>90% application**, infrastructure cobre caminhos principais.

## 8. Decomposição em fases

Cada fase é um spec → plano → implementação independente.

### Fase 1 — Núcleo Clean + UI polida (FOCO AGORA)

**Entrega:**
- Todas as camadas do Domain e Application
- Adapters: `WebcamVideoSource`, `MediapipeFaceDetector`, `SoundSink`, `LogSink`, `OpenCvWindowPresenter` com `RenderingTheme` completo (curvas suaves, overlays, glow, HUD, estados reativos)
- `bootstrap.py` + CLI básica com argparse
- `pyproject.toml` (substitui requirements.txt)
- Config via YAML + pydantic-settings
- Testes unitários do domain

**Paridade:** comportamento funcional idêntico ao `main.py` atual, mas com visualização muito mais polida e precisa (MediaPipe).

**Critério de aceitação:**
- `python -m driver_fatigue run --source webcam:0` reproduz o comportamento atual
- Detecção visivelmente mais precisa nos olhos e boca (MediaPipe)
- Testes unitários do domain passando com 100% de cobertura
- Smoke test do `MediapipeFaceDetector` usando `assets/test_sonolency.mp4` (verifica que detecta landmarks em N frames conhecidos)

### Fase 2 — Múltiplas fontes & saídas

**Entrega:**
- `RtspVideoSource`, `FileVideoSource`
- `HttpWebhookSink`, `MqttSink`, `CompositeSink`
- `HeadlessPresenter`, `FileRecorderPresenter`, `CompositePresenter`
- CLI com flags `--sinks`, `--presenter`, `--record`, `--headless`

**Critério de aceitação:**
- `--source rtsp://...` funciona
- `--presenter window+record:out.mp4` gera MP4 com overlay
- `--headless --sinks mqtt,log` roda sem GUI

### Fase 3 — API REST

**Entrega:**
- FastAPI com endpoints de sessões e WebSocket de eventos
- Schemas pydantic
- Testes E2E com `httpx.AsyncClient` e `TestClient`

**Critério de aceitação:**
- `POST /sessions` inicia monitoramento assíncrono
- WS emite eventos em tempo real
- OpenAPI disponível em `/docs`

### Fase 4 — Docker & Deploy

**Entrega:**
- `Dockerfile.headless` (multi-stage, MediaPipe runtime)
- `Dockerfile.api` (FastAPI + uvicorn)
- `docker-compose.yml` com perfis `headless`, `api`, `with-mqtt`
- README atualizado

**Critério de aceitação:**
- `docker compose --profile api up` sobe API funcional
- Imagem `headless` < 500MB
- Build reprodutível em Linux e Windows (WSL)

## 9. Decisões e tradeoffs

| Decisão | Alternativa descartada | Razão |
|---|---|---|
| Clean Architecture 4 camadas | Hexagonal 3 camadas | Mais explícita e didática, adequada ao contexto acadêmico |
| MediaPipe Face Mesh | dlib 68 landmarks | Maior precisão, iris nativa, build mais leve, Apache 2.0 |
| pydantic-settings | configparser / dotenv puro | Validação automática, type-safe, padrão moderno |
| pyproject.toml | requirements.txt | Padrão PEP 621, instalação como pacote (`pip install -e .`) |
| `AlertSinkPort` distinto de `FramePresenterPort` | Uma única `OutputPort` | Saídas de evento (som/rede) têm semântica diferente de saídas visuais (janela/vídeo) |
| `CompositePort` implementado como adapter | `List[Port]` no use case | Mantém use case simples; fan-out fica isolado e testável |
| Fase 1 já inclui MediaPipe e UI polida | Deixar UI pra depois | UI polida é o que torna o projeto "bonito" e o usuário pediu isso já |

## 10. Fora de escopo

- Detecção de distração (olhar para o lado, celular): escopo futuro
- Reconhecimento do motorista (identidade): não faz parte de detecção de fadiga
- Modelo ML próprio para sonolência: o escopo é baseado em EAR/MAR como indicadores geométricos
- Mobile app nativo (iOS/Android): a API permite isso como projeto separado depois
- Persistência histórica de eventos (banco de dados): pode ser adicionada como sink futuramente
