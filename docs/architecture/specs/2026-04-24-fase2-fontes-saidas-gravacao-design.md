# Fase 2 — Múltiplas Fontes, Múltiplas Saídas, Gravação (Clean Architecture)

**Data:** 2026-04-24
**Status:** Proposto (aguardando revisão)
**Base:** Fase 1 concluída (branch `feat/fase1-nucleo-clean`, 27 commits, 67 testes)
**Spec Fase 1:** `docs/superpowers/specs/2026-04-24-driver-fatigue-ubiquitous-design.md`

## 1. Objetivo

Expandir a ubiquidade do projeto além do par `webcam → som local`:

- **Entradas adicionais:** vídeo de arquivo (MP4/MOV) e stream RTSP.
- **Saídas adicionais:** webhook HTTP (POST JSON), MQTT (JSON publish), e composição arbitrária.
- **Gravação MP4 com overlay:** o mesmo quadro renderizado que aparece na tela é gravável em arquivo, ideal para demonstração e material de artigo.
- **Refatoração coerente:** extrair o `FrameRenderer` do `OpenCvWindowPresenter` para que display e gravação compartilhem exatamente a mesma lógica de desenho, evitando divergência visual.

Nenhuma mudança no domínio. Toda a expansão é em `infrastructure/`, `interfaces/` e `bootstrap.py`.

## 2. Componentes novos

### 2.1 Fontes de vídeo (Infrastructure)

```
infrastructure/video_sources/
├── webcam.py          # [existente]
├── rtsp.py            # [novo] RtspVideoSource
└── file.py            # [novo] FileVideoSource
```

**`RtspVideoSource`**

```python
class RtspVideoSource:
    def __init__(
        self,
        url: str,
        reconnect_attempts: int = 3,
        initial_backoff_seconds: float = 1.0,
    ) -> None: ...
    def read(self) -> Frame | None: ...
    def release(self) -> None: ...
```

Usa `cv2.VideoCapture(url, cv2.CAP_FFMPEG)`. Em caso de `read()` falho (`ok == False`), tenta reconectar com backoff exponencial `initial_backoff * 2^i` (1s, 2s, 4s) até `reconnect_attempts` vezes. Se esgotar, retorna `None` definitivamente e a pipeline encerra pela mesma rota do `VideoSourcePort`.

**`FileVideoSource`**

```python
class FileVideoSource:
    def __init__(self, path: Path, loop: bool = False) -> None: ...
```

`cv2.VideoCapture(str(path))`. Ao fim do arquivo, retorna `None` (ou reinicia se `loop=True`). Timestamps são `monotonic()` no momento da leitura (não os do arquivo).

### 2.2 Renderização — refactor para compartilhamento

**Problema atual:** `OpenCvWindowPresenter.present()` concentra desenho + exibição. Gravação precisaria duplicar a lógica ou depender da janela.

**Solução:** extrair a lógica pura de renderização em uma classe sem efeitos colaterais.

```
infrastructure/rendering/
├── curves.py                # [existente]
├── overlay.py               # [existente]
├── glow.py                  # [existente]
├── hud.py                   # [existente]
└── renderer.py              # [novo] FrameRenderer
```

**`FrameRenderer`** (em `rendering/renderer.py`)

```python
class FrameRenderer:
    """Produz o frame renderizado (overlay completo) a partir de landmarks e estado.

    Sem efeitos colaterais — não desenha em janela, não grava em arquivo.
    Mantém estado interno de FPS (EMA) para alimentar o HUD.
    """
    def __init__(self, theme: RenderingTheme) -> None: ...
    def render(
        self,
        frame: Frame,
        landmarks: list[FaceLandmarks],
        state: FatigueState,
    ) -> np.ndarray: ...
```

**`OpenCvWindowPresenter` (refactor)** — passa a delegar para `FrameRenderer` e só acrescenta `cv2.imshow + waitKey + destroyWindow`. Modo `headless` é removido dessa classe (veja 2.3 para o novo `HeadlessPresenter`). Assinatura pública da classe permanece a mesma exceto `headless` removido.

### 2.3 Presenters novos

```
infrastructure/presenters/
├── opencv_window.py         # [refactor]
├── headless.py              # [novo] HeadlessPresenter
├── file_recorder.py         # [novo] FileRecorderPresenter
└── composite.py             # [novo] CompositePresenter
```

**`HeadlessPresenter`** — não desenha nada, não guarda estado. Serve para modo "só sinks" (ex.: servidor MQTT, onde ninguém olha a tela nem grava).

```python
class HeadlessPresenter:
    def present(self, frame, landmarks, state) -> None: pass  # no-op
    def should_stop(self) -> bool: ...  # SIGINT-aware via signal handler instalado no __init__
    def close(self) -> None: pass
```

**`FileRecorderPresenter`**

```python
class FileRecorderPresenter:
    def __init__(
        self,
        renderer: FrameRenderer,
        output_path: Path,
        fps: int = 30,
        codec: str = "mp4v",
    ) -> None: ...
```

Renderiza com o `FrameRenderer` compartilhado e escreve via `cv2.VideoWriter`. Inicializa o `VideoWriter` no primeiro `present()` (quando já sabemos `frame.image.shape`). Se `VideoWriter.isOpened()` retornar False, loga warning e passa a ser no-op (não derruba pipeline). `close()` chama `writer.release()`.

**`CompositePresenter`**

```python
class CompositePresenter:
    def __init__(self, *presenters: FramePresenterPort) -> None: ...
    def present(self, frame, landmarks, state) -> None:
        for p in self._presenters:
            p.present(frame, landmarks, state)
    def should_stop(self) -> bool:
        return any(p.should_stop() for p in self._presenters)
    def close(self) -> None:
        for p in self._presenters:
            p.close()
```

### 2.4 Sinks novos

```
infrastructure/alert_sinks/
├── sound.py                 # [existente]
├── log.py                   # [existente]
├── composite.py             # [novo] CompositeSink (promove _CompositeSink de bootstrap.py)
├── http_webhook.py          # [novo] HttpWebhookSink
└── mqtt.py                  # [novo] MqttSink
```

**Payload unificado** (usado por HTTP e MQTT):

```json
{
  "event": "fatigue_alert",
  "timestamp": 1234.56,
  "frame_index": 742,
  "ear": 0.182,
  "mar": 0.521,
  "severity": "alert",
  "consecutive_frames": 20
}
```

Para `on_recovery`, `event = "fatigue_recovery"` e `ear/mar/severity/consecutive_frames` omitidos (só `timestamp` e `frame_index`).

**`HttpWebhookSink`**

```python
class HttpWebhookSink:
    def __init__(
        self,
        url: str,
        bearer_token: str | None = None,
        timeout_seconds: float = 3.0,
    ) -> None: ...
    def notify(self, event: FatigueEvent) -> None: ...
    def on_recovery(self, frame_index: int) -> None: ...
```

Usa `httpx.Client` (síncrono) mantido na instância. Em falha (timeout, 5xx, rede), loga warning e continua. Auth via `Authorization: Bearer <token>` quando `bearer_token` presente.

**`MqttSink`**

```python
class MqttSink:
    def __init__(
        self,
        broker: str,
        port: int = 1883,
        topic: str = "driver_fatigue/events",
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
        connect_timeout_seconds: float = 3.0,
    ) -> None: ...
```

Usa `paho.mqtt.client.Client` com loop assíncrono (`client.loop_start()`). Se `connect()` falhar no `__init__`, loga e o sink fica em modo "offline"; cada `notify` tenta reconectar best-effort antes de publicar. `publish()` com QoS 1. Encerramento via `__del__` → `loop_stop() + disconnect()`.

**`CompositeSink`** (promovido para módulo público a partir do `_CompositeSink` interno em `bootstrap.py`): mantém mesma semântica — fan-out com tratamento de exceção por sink.

### 2.5 AppSettings expandido

```python
class SourceSettings(BaseModel):
    kind: Literal["webcam", "rtsp", "file"] = "webcam"
    index: int = 0              # webcam
    url: str | None = None      # rtsp
    path: Path | None = None    # file
    loop: bool = False          # file

class HttpWebhookSettings(BaseModel):
    url: str
    bearer_token: str | None = None
    timeout_seconds: float = 3.0

class MqttSettings(BaseModel):
    broker: str
    port: int = 1883
    topic: str = "driver_fatigue/events"
    username: str | None = None
    password: str | None = None

class RecordingSettings(BaseModel):
    path: Path | None = None    # None = não grava
    fps: int = 30
    codec: str = "mp4v"

class AppSettings(BaseSettings):
    # ... existentes ...
    sinks: list[Literal["sound", "log", "http", "mqtt"]] = Field(
        default_factory=lambda: ["sound", "log"],
    )
    http_webhook: HttpWebhookSettings | None = None
    mqtt: MqttSettings | None = None
    recording: RecordingSettings = Field(default_factory=RecordingSettings)
```

Validações cruzadas (via `model_validator`):
- `source.kind == "rtsp"` exige `source.url`
- `source.kind == "file"` exige `source.path`
- `"http" in sinks` exige `http_webhook` não-nulo
- `"mqtt" in sinks` exige `mqtt` não-nulo

## 3. CLI

Extensão do comando `run`:

```bash
driver-fatigue run \
    --source <spec> \
    [--sinks <comma-list>] \
    [--record <path>] \
    [--headless] \
    [--config <yaml>]
```

**`--source <spec>`** — um dos formatos:
- `webcam:<index>` — ex.: `webcam:0`
- `file:<path>` — ex.: `file:assets/test_sonolency.mp4`
- `rtsp://<url>` — ex.: `rtsp://user:pass@192.168.1.10/stream`

**`--sinks`** — lista separada por vírgula dos sinks ativos. Default: `sound,log`. Valores aceitos: `sound`, `log`, `http`, `mqtt`. `http`/`mqtt` exigem os blocos correspondentes no config YAML.

**`--record <path>`** — atalho para gravar MP4 no caminho dado. Se ausente, não grava. Quando presente, o presenter final vira `CompositePresenter(window_or_headless, recorder)`.

**`--headless`** — usa `HeadlessPresenter` no lugar de `OpenCvWindowPresenter`. Compatível com `--record` (o recorder renderiza independente da janela).

Exemplos que devem funcionar pós-Fase 2:

```bash
# Servidor edge: RTSP de câmera veicular, sem GUI, manda alertas por MQTT
driver-fatigue run --source "rtsp://cam.local/live" --headless --sinks log,mqtt --config config/edge.yaml

# Demonstração pro artigo: processa vídeo de teste, grava output com overlay
driver-fatigue run --source file:assets/test_sonolency.mp4 --record docs/demo.mp4

# Setup local clássico
driver-fatigue run --source webcam:0  # equivalente a antes, sem regressão
```

## 4. Bootstrap atualizado

`bootstrap.py::build_monitor_use_case` ganha novos ramos:

```python
def _build_source(settings):
    kind = settings.source.kind
    if kind == "webcam":
        return WebcamVideoSource(settings.source.index)
    if kind == "rtsp":
        return RtspVideoSource(settings.source.url)
    if kind == "file":
        return FileVideoSource(settings.source.path, loop=settings.source.loop)
    raise ValueError(f"source.kind {kind!r} não suportado")

def _build_sinks(settings) -> AlertSinkPort:
    sinks: list[AlertSinkPort] = []
    for name in settings.sinks:
        if name == "log":   sinks.append(LogSink())
        elif name == "sound": sinks.append(SoundSink(settings.alarm_sound_path))
        elif name == "http":  sinks.append(HttpWebhookSink(settings.http_webhook.url, ...))
        elif name == "mqtt":  sinks.append(MqttSink(settings.mqtt.broker, ...))
    return CompositeSink(*sinks)

def _build_presenter(settings, renderer) -> FramePresenterPort:
    main = HeadlessPresenter() if settings.headless else OpenCvWindowPresenter(renderer)
    if settings.recording.path is None:
        return main
    recorder = FileRecorderPresenter(
        renderer, settings.recording.path,
        fps=settings.recording.fps, codec=settings.recording.codec,
    )
    return CompositePresenter(main, recorder)
```

O `FrameRenderer` é construído uma vez no bootstrap e compartilhado entre `OpenCvWindowPresenter` e `FileRecorderPresenter` — garante consistência visual entre tela e arquivo.

## 5. Testes

| Componente | Tipo de teste | Observações |
|---|---|---|
| `FrameRenderer` | Integration (pixels) | Verifica que render produz pixels não-pretos, que severity muda cor dominante, que íris vira círculos quando fornecida |
| `OpenCvWindowPresenter` (refatorado) | Mantém testes existentes | `last_rendered` some; em vez disso, testa que delega para `FrameRenderer` e chama `cv2.imshow`/`destroyWindow` com mocks |
| `HeadlessPresenter` | Unit | `present` é no-op; `should_stop` vira True após SIGINT (teste com `os.kill(os.getpid(), SIGINT)` ou mockando o handler) |
| `FileRecorderPresenter` | Integration | Escreve 5 frames em `tmp_path`, lê o MP4 de volta com `cv2.VideoCapture`, confirma ≥ 5 frames |
| `CompositePresenter` | Unit | `present` chama todos; `should_stop` é OR; `close` propaga mesmo se um falhar |
| `RtspVideoSource` | Unit com mock | Não conecta RTSP real; `cv2.VideoCapture` é patched; valida lógica de reconexão e backoff |
| `FileVideoSource` | Integration | Lê `assets/test_sonolency.mp4`, confirma frames sequenciais, `loop=True` rebobina |
| `HttpWebhookSink` | Integration com `respx` | Mocka httpx, valida payload JSON e Bearer header |
| `MqttSink` | Unit com mock | `paho.mqtt.client.Client` é patched; valida publish com topic + payload; reconexão best-effort |
| `CompositeSink` | Unit | Um sink que levanta exceção não derruba os outros |
| CLI atualizada | Integration | `--source file:...` e `--source rtsp://...` aceitos; `--record out.mp4` adiciona recorder; `--sinks http,log` valida combinação |
| E2E | Extensão do existente | Reusa `test_pipeline_processes_test_video_headless` com `--record` habilitado, confirma que o MP4 existe e tem ≥ N frames |

## 6. Tratamento de erros

- **RTSP falha permanente:** 3 reconexões exponenciais → `read()` retorna `None` → pipeline encerra via `finally` normal
- **Arquivo terminou:** `read()` retorna `None` na primeira leitura pós-EOF; `loop=True` rebobina via `cap.set(POS_FRAMES, 0)`
- **HTTP webhook timeout:** loga e continua; não afeta outros sinks
- **MQTT desconectado:** tenta reconectar no próximo `notify`; se falhar, loga e descarta (best-effort)
- **MP4 writer falhou ao abrir:** loga warning, presenter vira no-op
- **Config inválida** (ex.: `sinks: [http]` sem `http_webhook`): pydantic levanta `ValidationError` no boot, CLI sai com código 2

## 7. Dependências adicionadas

```toml
# pyproject.toml
dependencies = [
    # ... existentes ...
    "httpx>=0.27",
    "paho-mqtt>=2.0",
]

[project.optional-dependencies]
dev = [
    # ... existentes ...
    "respx>=0.21",   # mock httpx
]
```

## 8. Decomposição em sub-fases (para o plano)

| Sub-fase | Entrega | Depende de |
|---|---|---|
| 2.1 Fontes | `FileVideoSource`, `RtspVideoSource`, CLI aceita `file:`/`rtsp:`, settings parser | — |
| 2.2 Renderer refactor | Extrai `FrameRenderer`; `OpenCvWindowPresenter` passa a delegar (testes antigos adaptados) | — |
| 2.3 Presenters de gravação | `HeadlessPresenter`, `FileRecorderPresenter`, `CompositePresenter`, flag `--record` | 2.2 |
| 2.4 Sinks HTTP/MQTT | `HttpWebhookSink`, `MqttSink`, `CompositeSink` público, flag `--sinks`, settings | — |
| 2.5 Integração final | Bootstrap atualizado costura tudo; E2E estendido; README com exemplos | 2.1–2.4 |

Ordem sugerida no plano: 2.2 primeiro (renderer refactor, zero-impact em comportamento), depois 2.1 e 2.4 em paralelo lógico, depois 2.3 (depende do renderer), depois 2.5.

## 9. Fora de escopo

- Autenticação HTTP avançada (OAuth, mTLS) — só Bearer token estático
- MQTT sobre TLS — porta 8883 com certificados é Fase futura
- Stream de vídeo saindo (ex.: re-publicar frames processados como HLS/RTSP) — não é requisito
- Gravação com codec H.264 nativo (exige ffmpeg) — `mp4v` do OpenCV basta para Fase 2
- UI web de monitoramento (isso é parte da Fase 3 — API REST)
- Persistência de eventos em banco — sinks são efêmeros por design nesta fase

## 10. Compatibilidade com Fase 1

- Configurações existentes da Fase 1 continuam válidas (novos campos têm defaults)
- `driver-fatigue run --source webcam:0` (sem novos flags) produz comportamento idêntico à Fase 1
- Nenhuma API pública da Application/Domain muda
- Único ponto de refactor visível: `OpenCvWindowPresenter.__init__` remove `headless` — callers internos (bootstrap) são ajustados; ninguém externo consumia

**Testes existentes que mudam** (sub-fase 2.2):
- `tests/integration/test_opencv_presenter.py` — substitui verificações de `last_rendered` por verificações usando um `FrameRenderer` instanciável diretamente; remove `headless=True` do construtor. Novos testes do `FrameRenderer` em `tests/integration/test_frame_renderer.py` cobrem a lógica de renderização.

**Mudança no `bootstrap._CompositeSink`** (sub-fase 2.4): promovido para `infrastructure.alert_sinks.composite.CompositeSink` (módulo público). O código antigo em `bootstrap.py` é removido e substituído por import.
