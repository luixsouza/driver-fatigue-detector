# Arquitetura — Driver Fatigue Detector

**Versão:** 1.0 — 2026-04-28
**Branch de referência:** `feat/fase2-5-falsos-positivos`

> Este documento descreve a arquitetura do sistema sob a ótica do
> paradigma de **computação ubíqua** e de **sistemas distribuídos**:
> quais são as camadas, onde está o sensor, onde está o atuador, como
> os componentes se comunicam, onde está o processamento, e como o
> sistema lida com falhas, mobilidade e heterogeneidade.

---

## 1. Visão geral

O sistema é composto por **três processos distribuídos** rodando, no
caso típico, na mesma máquina embarcada (notebook ou SBC dentro do
veículo) — mas desacoplados o suficiente para serem distribuídos em
máquinas diferentes se necessário (a comunicação é HTTP/MQTT padrão).

```
                           ╭──────────────────────────────╮
                           │       AMBIENTE FÍSICO        │
                           │   (cabine, motorista, voz)   │
                           ╰──────────────┬───────────────╯
                                          │ luz, gestos
                                          ▼
                              ┌───────────────────────┐
                              │   Webcam embarcada    │  ← SENSOR
                              │   (webcam:0 / RTSP /  │
                              │    arquivo de vídeo)  │
                              └───────────┬───────────┘
                                          │ frames RGB
                                          ▼
   ┌──────────────────────────────────────────────────────────────────┐
   │  PROCESSO 1 — Detector  (`driver-fatigue run`)                    │
   │  ─────────────────────────────────────────────                    │
   │   VideoSourcePort  ──►  MediapipeFaceDetector                     │
   │                            │                                      │
   │                            ▼                                      │
   │   FrameQualityPolicy  ─►  FatigueEvaluator (heurística + base-    │
   │                           line + histerese + cooldown)            │
   │                            │                                      │
   │                            ▼                                      │
   │                       ContextValidator (PERCLOS + ONNX local)     │
   │                            │                                      │
   │   ┌────────────┬───────────┼───────────┬────────────┬─────────┐  │
   │   ▼            ▼           ▼           ▼            ▼         ▼  │
   │ SoundSink  LogSink  HttpWebhookSink  MqttSink  JsonlSink  Mjpeg  │
   │  (atuador) (audit)   (atuador rede)  (atuador) (audit)  (stream) │
   └─────┬──────────┬───────────┬───────────┬────────────┬─────────┬──┘
         │          │           │           │            │         │
         ▼          ▼           ▼           ▼            ▼         ▼
    Alto-falante  arq de    HTTP POST   MQTT broker  events.jsonl  HTTP
    da cabine     log local externo     externo      em disco      MJPEG
    (ATUADOR)              (frota,      (frota,      (auditoria)   ↓
                            telemetria)  telemetria)               PROCESSO 2
                                                                    Web Server
                                                                   (`driver-
                                                                    fatigue
                                                                    web`)
                                                                    │
                                                                    ▼
                                                              Browser do
                                                              gestor / motorista
                                                              (SSE + MJPEG)
```

**Quem é o quê no vocabulário do checklist:**

- **Sensor:** webcam (ou RTSP/arquivo).
- **Borda (edge):** PROCESSO 1 — onde a inferência acontece.
- **Atuadores:** alto-falante (`SoundSink`), webhook HTTP, broker MQTT,
  dashboard web.
- **Persistência local:** `JsonlEventSink` (`events.jsonl`) e logs.
- **Middleware/integração:** `CompositeSink` (fan-out com isolamento
  de falhas), servidor web local (broker SSE), MQTT (broker
  externo).

---

## 2. Camadas (Clean Architecture, 4 camadas)

```
src/driver_fatigue/
├── domain/                  ← regras puras de fadiga
│   ├── entities.py          (Frame, FatigueState, FatigueEvent)
│   ├── value_objects.py     (PersonalBaseline, FrameQuality, ContextVerdict)
│   ├── evaluator.py         (heurística + histerese + cooldown)
│   └── rendering_theme.py
│
├── application/             ← casos de uso (orquestração)
│   ├── ports.py             (VideoSource, FaceDetector, AlertSink,
│   │                         ContextValidator, FramePresenter)
│   └── use_cases/
│       ├── detect_fatigue.py   (1 frame → FatigueState)
│       └── monitor_driver.py   (loop completo)
│
├── infrastructure/          ← adapters concretos
│   ├── video_sources/       (webcam, file, rtsp)
│   ├── detectors/           (MediaPipe)
│   ├── context_validators/  (noop, eye_state ONNX, PERCLOS)
│   ├── alert_sinks/         (sound, log, http_webhook, mqtt, jsonl, composite)
│   ├── presenters/          (opencv_window, headless, file_recorder, mjpeg_push)
│   └── rendering/
│
└── interfaces/              ← entrypoints e config
    ├── cli/                 (driver-fatigue run)
    ├── web/                 (driver-fatigue web — SSE + MJPEG)
    └── config/              (settings via pydantic + YAML + env)
```

**Regra de dependência:** seta sempre aponta para dentro
(`interfaces` → `infrastructure` → `application` → `domain`).
O `domain` não importa nada do projeto fora dele e nada externo
exceto numpy.

---

## 3. Componentes distribuídos e seus protocolos

| Componente | Protocolo | Direção | Porta padrão |
|---|---|---|---|
| Detector → Web Server (eventos) | HTTP POST `/api/events` (JSON) | uni | 8000 |
| Detector → Web Server (vídeo) | HTTP POST `/api/video/push` (JPEG) | uni | 8000 |
| Browser → Web Server (eventos) | HTTP SSE `/api/stream` | uni | 8000 |
| Browser → Web Server (vídeo) | HTTP MJPEG `/api/video` | uni | 8000 |
| Detector → Webhook externo | HTTP POST (JSON) | uni | configurável |
| Detector → Broker MQTT | MQTT publish | uni | 1883 |
| Detector → Disco (auditoria) | append-only file (JSONL) | uni | filesystem |

Todos os protocolos são **padrão de mercado**, permitindo integração
com sistemas heterogêneos (qualquer broker MQTT, qualquer endpoint
HTTP, qualquer leitor de JSONL).

---

## 4. Fluxo de um frame (caminho crítico)

```
1. WebcamVideoSource.read()                        ── ~33ms (30 fps)
       └─► Frame(image, timestamp, index)
2. MediapipeFaceDetector.detect(frame)             ── ~10–20ms CPU
       └─► [FaceLandmarks(...)]
3. FrameQualityPolicy.evaluate(landmarks, frame)   ── <1ms
       ├─► trustworthy? sim → segue
       └─► não → estado inalterado, HUD anota motivo
4. FatigueEvaluator.evaluate(landmarks, state, t)  ── <1ms
       ├─► calibra baseline (warmup)
       ├─► aplica thresholds relativos
       ├─► histerese / cooldown / discriminador fala-bocejo
       └─► nova FatigueState
5. ContextValidator.confirm_drowsy(...) [só se virar alert]
       └─► PERCLOS + CNN ONNX (eyes-open/closed)   ── <5ms CPU
6. CompositeSink.notify(event) [se confirmado]
       ├─► SoundSink (rampa de volume)
       ├─► LogSink
       ├─► JsonlEventSink (append)
       ├─► HttpWebhookSink (se configurado)
       └─► MqttSink (se configurado)
7. FramePresenter.present(frame, landmarks, state)
       ├─► OpenCvWindowPresenter (modo desktop)
       ├─► HeadlessPresenter (modo embarcado)
       ├─► FileRecorderPresenter (se gravando)
       └─► MjpegStreamPresenter (se dashboard ligado)
```

Tempo total típico em CPU comum: **20–35 ms/frame** → ~30 fps com folga.

---

## 5. Adaptação automática (sensibilidade ao contexto)

| Mecanismo | Onde | O que adapta |
|---|---|---|
| `PersonalBaseline` (calibração warmup) | `domain/evaluator.py` | `ear_threshold` e `mar_threshold` viram relativos ao motorista da sessão |
| `FrameQualityPolicy` | `domain/value_objects.py` | Descarta frames com yaw/pitch fora do envelope ou face fora do quadro |
| Histerese (`recovery_frames`, `min_alert_duration_frames`) | `domain/evaluator.py` | Evita oscilação rápida entre normal/alert |
| Cooldown (`alarm_cooldown_seconds`) | `domain/evaluator.py` | Evita disparos seguidos do mesmo evento |
| Discriminador fala vs bocejo | `domain/evaluator.py` | Desconsidera MAR alto com alta variância (fala) |
| `ContextValidator` (CNN local + PERCLOS) | `infrastructure/context_validators/` | Confirma suspeita antes de notificar sinks |
| Rampa de volume (`SoundSink`) | `infrastructure/alert_sinks/sound.py` | Volume sobe gradualmente para acordar sem assustar |

---

## 6. Tolerância a falhas

| Falha | Mitigação | Onde |
|---|---|---|
| Detector trava ou processo morre | `_DetectorSupervisor` respawn com backoff | `interfaces/web/server.py` |
| Vídeo de arquivo termina | `--loop` ou supervisor reinicia | `infrastructure/video_sources/file.py`, supervisor |
| Sink individual lança exceção | `CompositeSink` isola por sink (try/except) | `infrastructure/alert_sinks/composite.py` |
| Modelo ONNX ausente / `onnxruntime` indisponível | Fallback automático para `NoopContextValidator`, com warning | `bootstrap._build_validator` |
| Webhook HTTP fora do ar | `HttpWebhookSink` loga e segue (não bloqueia o loop) | `infrastructure/alert_sinks/http_webhook.py` |
| Frame de baixa qualidade (cabeça virada, rosto fora) | `FrameQualityPolicy` descarta sem alterar estado; HUD anota motivo | `domain/value_objects.py` |
| Erro durante validação contextual | `fail_safe_on_error: alarm` (default) → dispara alarme em vez de suprimir | `MonitorDriverUseCase` |
| Áudio indisponível (sem `pygame`) | `SoundSink` logado como indisponível, sistema continua | `bootstrap._build_single_sink` |

---

## 7. Segurança

- **API key local:** endpoints sensíveis do dashboard (`POST /api/events`,
  `POST /api/video/push`) exigem header `X-API-Key` quando
  `web.api_key` está configurado. Detector é injetado com a mesma chave.
- **Webhook externo:** suporta `bearer_token` (configurável via env
  `DRIVER_FATIGUE_HTTP_WEBHOOK__BEARER_TOKEN`).
- **MQTT:** suporta `username`/`password`.
- **Path traversal no static:** `_serve_static` valida com
  `Path.relative_to(STATIC_DIR)` (defesa em profundidade contra `..`).
- **Tamanho máximo de upload de JPEG:** 5 MB (`/api/video/push`).

Para ambientes de produção em rede pública, recomenda-se colocar o
servidor web atrás de um proxy reverso com TLS (nginx, Caddy).

---

## 8. Privacidade

Documento dedicado: `docs/PRIVACY.md`. Resumo:

- Vídeo nunca sai do dispositivo (mesmo dashboard local serve do
  localhost por padrão).
- Baseline é por sessão (não persiste entre execuções).
- `events.jsonl` contém só métricas numéricas, sem imagem.
- Sem identificação biométrica do motorista.

---

## 9. Mobilidade

O sistema foi projetado para rodar **dentro do veículo em movimento**:

- **Sem dependência de internet em runtime** (modelos baixados uma vez,
  validador local). Conectividade variável não interrompe operação.
- **Hardware leve:** caminha em laptop modesto e em SBC tipo
  Raspberry Pi 4 (modelo ONNX ~50 KB, MediaPipe roda em CPU).
- **Sinks de rede são opcionais:** webhook/MQTT só publicam quando
  há conexão; falha não para o detector.
- **Dashboard local:** acessível via Wi-Fi do veículo (hotspot do
  notebook ou rede local 4G/5G), sem depender de servidor remoto.

Detalhes operacionais em `docs/DEPLOYMENT.md`.

---

## 10. Heterogeneidade e escalabilidade

**Heterogeneidade.** O sistema integra dispositivos e protocolos
heterogêneos via ports (Clean Architecture):

- Fontes de vídeo trocáveis: webcam local, câmera IP RTSP, arquivo
  de vídeo.
- Sinks intercambiáveis: alto-falante local, log, HTTP (qualquer
  endpoint), MQTT (qualquer broker), JSONL (qualquer leitor).
- Validador contextual plugável: `noop`, `eye_state` (ONNX), futuro
  `drowsiness_cnn`.

**Escalabilidade horizontal (frota).** Para uma frota de N veículos:

```
veículo 1  ──► detector  ──┐
veículo 2  ──► detector  ──┤
   ...                     ├─► broker MQTT central  ──► dashboard de frota
veículo N  ──► detector  ──┘                       └─► armazenamento histórico
```

Cada veículo é uma instância independente publicando métricas
numéricas no broker central. **Não há ponto único de falha no detector**:
um veículo desconectado continua alarmando localmente. O backend
central de frota está fora do escopo desta entrega, mas o
`MqttSink` já fornece o ponto de integração.

---

## 11. Decisões arquiteturais (mini-ADRs)

1. **Clean Architecture com 4 camadas.** Permite testar o domínio
   sem MediaPipe/OpenCV/pygame e trocar adapters sem tocar regras.
   Spec original: `docs/superpowers/specs/2026-04-24-driver-fatigue-ubiquitous-design.md`.
2. **Validador contextual como port plugável.** Permite começar com
   `noop` (zero dependência), evoluir para `eye_state` (ONNX local) e
   adicionar `drowsiness_cnn` no futuro sem refatoração.
3. **Servidor web em stdlib pura.** Sem Flask/FastAPI: zero dep
   adicional. SSE + MJPEG cobrem o caso de uso simples sem
   sobre-engenharia.
4. **CompositeSink com isolamento por sink.** Falha de um adapter
   (ex.: webhook fora do ar) não derruba os outros nem o loop.
5. **Calibração por sessão (não persistente).** Privacidade sobre
   conveniência: prefere recalibrar a cada execução do que armazenar
   perfil biométrico.
6. **Modelos ONNX versionados no repo (com hash).** Reprodutibilidade
   sobre limpeza de repo: o avaliador pode rodar a POC e obter
   exatamente o mesmo resultado.
