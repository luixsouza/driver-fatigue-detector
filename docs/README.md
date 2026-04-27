# Detector de Fadiga

Este projeto implementa um sistema de detecção de fadiga e bocejo utilizando visão computacional. Ele usa as bibliotecas OpenCV, dlib, numpy, pygame e threading para detectar fadiga e emitir um alerta sonoro quando sinais de cansaço são detectados.

## Demonstração em GIF

![Demonstração](https://github.com/luixsouza/SonolencyDetector/blob/main/assets/sonolency.gif?raw=true)

## Funcionalidades

- Detecta o fechamento dos olhos e bocejos em tempo real.
- Emite um alarme sonoro ao detectar sinais de fadiga.
- Utiliza landmarks faciais para detectar e monitorar os olhos e a boca.

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

Sobe um dashboard que recebe eventos do detector via webhook HTTP e os mostra
ao vivo via Server-Sent Events. O detector pode rodar em uma máquina e o
dashboard ser aberto em qualquer browser na rede — mesma arquitetura, sem
acoplamento extra.

```bash
# terminal 1 — dashboard (sem deps adicionais, só stdlib)
driver-fatigue web --port 8000

# terminal 2 — detector apontando o webhook pra esse servidor
DRIVER_FATIGUE_HTTP_WEBHOOK__URL=http://localhost:8000/api/events \
  driver-fatigue run --sinks log,http --config config/default.yaml
```

Abra `http://localhost:8000/` no browser — alertas e recuperações chegam em
tempo real, sem reload.

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

- O sistema utiliza a razão entre a altura e a largura dos olhos (`Eye Aspect Ratio - EAR`) para detectar se a pessoa está com os olhos fechados.
- Para detectar bocejos, ele utiliza a razão entre a altura e a largura da boca (`Mouth Aspect Ratio - MAR`).
- Se um fechamento dos olhos ou bocejo persistir por um número consecutivo de frames, um alarme sonoro será ativado.
