# Detector de Fadiga

Detector de sonolência em motoristas em tempo real, com dashboard web para
monitoramento ubíquo. Usa **MediaPipe FaceLandmarker** para extrair landmarks
faciais e regras de domínio para discriminar piscadas, falas e cabeceios de
sinais reais de fadiga. Arquitetura limpa em 4 camadas (domínio puro →
aplicação → infraestrutura → interfaces).

## Demonstração em GIF

![Demonstração](https://github.com/luixsouza/SonolencyDetector/blob/main/assets/sonolency.gif?raw=true)

## Funcionalidades

- Detecção de olhos fechados (**EAR**), bocejo (**MAR**) e cabeceio (pitch) em
  tempo real, com landmarks faciais do MediaPipe.
- **Calibração por usuário**: aprende o EAR/MAR/pitch de repouso nos primeiros
  ~2s de operação, depois compara contra esse baseline em vez de um threshold
  global — corrige sensibilidade ao formato do olho, óculos e iluminação.
- **Discriminadores temporais**: histerese, cooldown de alarme, janela de
  estabilidade de MAR (separa bocejo de fala).
- **Guarda de qualidade de frame**: descarta detecções com rosto torto, longe
  do quadro ou em baixa confiança — preserva calibração e evita falso positivo.
- Dashboard web ao vivo com vídeo + overlay + timeline de eventos (SSE+MJPEG).
- Saídas plugáveis: alarme sonoro, log, webhook HTTP, MQTT, JSONL para
  auditoria.
- Fontes plugáveis: webcam, arquivo de vídeo, RTSP.

## Instalação

```bash
pip install -e ".[dev]"
```

## Uso

```bash
# detecção na webcam (padrão)
driver-fatigue run

# webcam específica
driver-fatigue run --source webcam:1

# arquivo de vídeo
driver-fatigue run --source file:assets/test_sonolency.mp4

# stream RTSP
driver-fatigue run --source rtsp://user:pass@camera.local/live

# modo headless (sem GUI), só alertas de rede
driver-fatigue run --headless --sinks log,mqtt --config config/default.yaml

# grava vídeo com overlay (ideal pra demonstração)
driver-fatigue run --source file:assets/test_sonolency.mp4 --record docs/demo.mp4

# múltiplos sinks simultâneos
driver-fatigue run --sinks sound,log,http --config config/default.yaml

# equivalente via módulo
python -m driver_fatigue run --source webcam:0
```

## Dashboard web em tempo real (ubiquidade)

Dashboard mostra **vídeo da câmera com overlay** + **alertas em tempo real**.
Detector e dashboard sobem juntos com **um comando único**:

```bash
# tudo num so comando — webcam por default
driver-fatigue web --port 8000

# com video em vez de webcam
driver-fatigue web --port 8000 --source file:assets/test_sonolency.mp4

# RTSP
driver-fatigue web --port 8000 --source rtsp://user:pass@cam.local/live
```

Abra `http://localhost:8000/` — vídeo aparece no painel central com overlay
do detector (curvas de olho/boca, glow, HUD) e a coluna lateral mostra
severidade, EAR/MAR, contadores e timeline de alertas.

Para rodar detector e dashboard em **máquinas diferentes** (cenário ubíquo):

```bash
# máquina A — dashboard só
driver-fatigue web --port 8000 --no-detector

# máquina B — detector apontando pra A
driver-fatigue run --dashboard http://maquina-a:8000 --headless
```

## Configuração

Suporta YAML e variáveis de ambiente (prefixo `DRIVER_FATIGUE_`).

```bash
# exemplo YAML
driver-fatigue run --config config/default.yaml

# exemplo via env
export DRIVER_FATIGUE_SOURCE__KIND=rtsp
export DRIVER_FATIGUE_SOURCE__URL=rtsp://cam.local/stream
export DRIVER_FATIGUE_SINKS='["log","mqtt"]'
driver-fatigue run
```

Consulte `config/default.yaml` e `config/example.env` para todas as opções.

## Arquitetura

O projeto segue Clean Architecture em 4 camadas. Veja o design completo em
[`docs/superpowers/specs/2026-04-24-driver-fatigue-ubiquitous-design.md`](superpowers/specs/2026-04-24-driver-fatigue-ubiquitous-design.md)
e a expansão da Fase 2 em
[`docs/superpowers/specs/2026-04-24-fase2-fontes-saidas-gravacao-design.md`](superpowers/specs/2026-04-24-fase2-fontes-saidas-gravacao-design.md).

## Como funciona

Pipeline a cada frame:

1. **Captura** — webcam/arquivo/RTSP (`VideoSource`). Webcam no Windows usa
   DirectShow + MJPG quando suportado, pra destravar 30fps em HD.
2. **Detecção** — MediaPipe `FaceLandmarker` em `RunningMode.VIDEO` (reusa o
   tracker entre frames). A imagem é reduzida pra ~640px antes da detecção pra
   economizar CPU; landmarks vêm normalizados (0..1) e são remapeados pro
   tamanho original na hora de renderizar.
3. **Métricas de domínio** — `EAR` (razão altura/largura dos olhos) e `MAR`
   (razão altura/largura da boca). Funções puras, sem dependência de framework.
4. **Qualidade do frame** — `FrameQualityPolicy` estima yaw/pitch da cabeça e
   área do rosto. Frames ruins (rosto torto, longe, baixa confiança) NÃO
   alimentam o evaluator — só o caso especial de cabeceio é mantido (pitch alto
   é evidência, não ruído).
5. **Calibração contínua** — `PersonalBaseline` aprende EAR/MAR/pitch de
   repouso por usuário via Welford online. Threshold de olho fechado vira
   `ear_rest * ear_close_ratio`; threshold de bocejo vira
   `mar_rest + z * mar_std`; cabeceio vira `abs(pitch - pitch_rest) >= delta`.
6. **Decisão** — `evaluate_fatigue` aplica histerese (entrada por
   `warning_ratio` * `consecutive_frames`, saída por `recovery_frames`),
   cooldown de alarme e discriminação bocejo vs fala via estabilidade do MAR
   numa janela deslizante.
7. **Notificação** — `MonitorDriverUseCase` notifica os sinks na transição
   `normal/warning → alert`. Sinks são compostos: som, log, webhook HTTP, MQTT,
   JSONL podem rodar em paralelo.

O dashboard web (`driver-fatigue web`) embute o detector como **thread no
mesmo processo** — vídeo e eventos vão pela memória (sem subprocess, sem HTTP
loopback). O modo distribuído (detector e dashboard em máquinas diferentes)
ainda funciona via `driver-fatigue run --dashboard http://host:porta`.

## Fase 3 — Fusão Multimodal

O dashboard agora calcula um **Índice de Fadiga 0–100%** combinando sinais reais (EAR/MAR/cabeceio do MediaPipe) com sinais simulados via sliders (BPM, ruído de volante, tempo dirigindo, hora do dia).

**Stack:** scikit-fuzzy (BSD) + React + Vite + Tailwind. Tudo local, sem internet.

### Como rodar a demo

```bash
pip install -e ".[fuzzy]"
cd web && npm install && npm run build && cd ..
python -m driver_fatigue.interfaces.web --port 8000
# abra http://localhost:8000
```

### Modo demo automático

Clica no botão "Modo demo automático" no painel — cenário scriptado de 30s anima os sliders (motorista entrando em sonolência: BPM cai, volante oscila, salto pra madrugada). Os sliders ficam read-only durante o demo; clique "Parar" pra retomar controle.

### Endpoints novos

- `GET /api/inputs` — snapshot atual dos sliders.
- `POST /api/inputs` — atualiza sliders. Body: `{"bpm": 60, "steering_noise": 0.5, ...}`. Faixas inválidas são clampadas.
- `POST /api/demo/start` — inicia cenário de 30s.
- `POST /api/demo/stop` — aborta cenário.
