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
# detecção padrão (webcam 0, janela OpenCV)
driver-fatigue run

# webcam específica
driver-fatigue run --source webcam:1

# modo headless (sem janela, só alarme sonoro e log)
driver-fatigue run --headless

# config customizada
driver-fatigue run --config config/default.yaml

# equivalente via módulo
python -m driver_fatigue run --source webcam:0
```

## Arquitetura

O projeto segue Clean Architecture em 4 camadas. Veja o design completo em
[`docs/superpowers/specs/2026-04-24-driver-fatigue-ubiquitous-design.md`](superpowers/specs/2026-04-24-driver-fatigue-ubiquitous-design.md).

## Como funciona

- O sistema utiliza a razão entre a altura e a largura dos olhos (`Eye Aspect Ratio - EAR`) para detectar se a pessoa está com os olhos fechados.
- Para detectar bocejos, ele utiliza a razão entre a altura e a largura da boca (`Mouth Aspect Ratio - MAR`).
- Se um fechamento dos olhos ou bocejo persistir por um número consecutivo de frames, um alarme sonoro será ativado.
