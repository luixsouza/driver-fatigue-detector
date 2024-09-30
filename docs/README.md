# Detector de Fadiga

Este projeto implementa um sistema de detecção de fadiga e bocejo utilizando visão computacional. Ele usa as bibliotecas OpenCV, dlib, numpy, pygame e threading para detectar fadiga e emitir um alerta sonoro quando sinais de cansaço são detectados.

## Demonstração em GIF

![Demonstração](assets/sonolency.gif)

## Funcionalidades

- Detecta o fechamento dos olhos e bocejos em tempo real.
- Emite um alarme sonoro ao detectar sinais de fadiga.
- Utiliza landmarks faciais para detectar e monitorar os olhos e a boca.

## Instalação

### Pré-requisitos

- Python 3.8 ou superior
- Webcam para a captura de vídeo

### Dependências

As dependências do projeto estão listadas no arquivo `requirements.txt`. Para instalar as dependências, execute:

```bash
pip install -r requirements.txt
```

### Arquivo `requirements.txt`

```txt
opencv-python
dlib
numpy
pygame
```

### Instalação do dlib

Como o `dlib` pode ser complicado de instalar, dependendo do seu sistema operacional, recomenda-se seguir as instruções específicas do [repositório oficial do dlib](https://github.com/davisking/dlib).

No Ubuntu, por exemplo, você pode instalar o `dlib` com os seguintes comandos:

```bash
sudo apt-get install cmake
pip install dlib
```

No Windows, pode ser necessário instalar Visual Studio para obter as ferramentas de build.

### Pygame

Instale o `pygame` com:

```bash
pip install pygame
```

## Uso

1. Certifique-se de que o arquivo `shape_predictor_68_face_landmarks.dat` está na mesma pasta que o script Python. Esse arquivo pode ser baixado [aqui](http://dlib.net/files/shape_predictor_68_face_landmarks.dat.bz2).
2. Conecte a webcam ao seu computador.
3. Execute o script:

```bash
python detector_fadiga.py
```

4. A detecção será feita em tempo real e um alerta sonoro será disparado se a fadiga for detectada.

## Como funciona

- O sistema utiliza a razão entre a altura e a largura dos olhos (`Eye Aspect Ratio - EAR`) para detectar se a pessoa está com os olhos fechados.
- Para detectar bocejos, ele utiliza a razão entre a altura e a largura da boca (`Mouth Aspect Ratio - MAR`).
- Se um fechamento dos olhos ou bocejo persistir por um número consecutivo de frames, um alarme sonoro será ativado.

## Teclas de controle

- Pressione `q` para encerrar a execução do programa.
