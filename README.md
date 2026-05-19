# Driver Fatigue Detector

Sistema de detecção de fadiga em motoristas em tempo real, baseado em visão computacional e fusão multimodal (EAR/MAR + head pose + inferência fuzzy), construído sobre **Clean Architecture**.

![demo](docs/img/sonolency.gif)

## Visão geral

| Aspecto | Detalhe |
|---------|---------|
| **Linguagem** | Python 3.11+ |
| **Frontend** | React + Vite + Tailwind (em `web/`) |
| **Vision** | MediaPipe FaceLandmarker (em VIDEO mode, com downscale) |
| **Inferência** | Motor fuzzy de 12 regras IF–THEN, com fallback NoOp via feature flag |
| **Atuação** | 5 sinks plugáveis: log, JSONL, MQTT, HTTP webhook, som |
| **Fontes** | Webcam local, arquivo MP4, RTSP, ou push via REST autenticado |

## Arquitetura

Quatro camadas Clean Architecture:

```
┌─────────────────────────────────────────────────────┐
│  interfaces/        cli/ , web/ (REST + cockpit)    │
├─────────────────────────────────────────────────────┤
│  application/       ports.py (5 Protocols) +        │
│                     use_cases/                      │
├─────────────────────────────────────────────────────┤
│  domain/            entities, evaluator,            │
│                     fatigue_index, metrics, quality │
├─────────────────────────────────────────────────────┤
│  infrastructure/    adapters por porta:             │
│                     alert_sinks/, context_validators/,│
│                     detectors/, index_evaluators/,  │
│                     presenters/, rendering/,        │
│                     video_sources/                  │
└─────────────────────────────────────────────────────┘
                       ▲
              config/ (settings.py)
              resources/ (audio, models)
```

Cinco portas expostas pela camada de aplicação:

- `FaceLandmarkDetector` — extrai landmarks faciais (atualmente MediaPipe)
- `VideoSource` — fornece frames (webcam, arquivo, RTSP)
- `ContextValidator` — valida qualidade do contexto (luz, head pose, oclusão)
- `IndexEvaluator` — calcula índice de fadiga (Fuzzy ou NoOp)
- `AlertSink` — publica eventos (log, JSONL, MQTT, HTTP, som; agregado por Composite)

Cada porta é um `Protocol` em `application/ports.py`; bootstrap injeta a implementação concreta via config.

Análise arquitetural completa em `docs/architecture/specs/` e `docs/architecture/plans/`. Artigo SOLID em `docs/article-solid/`.

## Como rodar

### Backend (CLI)

```bash
pip install -e ".[dev,fuzzy]"
driver-fatigue --config config/default.yaml
```

Variáveis de ambiente (override do YAML) — ver `config/example.env`:

```bash
DRIVER_FATIGUE_SOURCE__KIND=webcam
DRIVER_FATIGUE_THRESHOLDS__EAR_THRESHOLD=0.25
```

### Web Cockpit

```bash
# backend (porta 8000 por padrão)
python -m driver_fatigue.interfaces.web --config config/web-demo.yaml

# frontend (porta 5173 dev)
cd web && npm install && npm run dev
```

O backend serve os artefatos buildados em `src/driver_fatigue/interfaces/web/static/`. O `web/` top-level contém o código-fonte React + Vite.

### Testes

```bash
pytest                                              # tudo
pytest tests/unit                                   # só unitários (rápido)
pytest --ignore=tests/integration/test_webcam_source.py \
       --ignore=tests/integration/test_rtsp_video_source.py    # CI-friendly
```

Cobertura: `pytest --cov` (alvo: 95% em `domain/` e `application/`).

## Estrutura

```
.
├── .github/workflows/        CI (pytest + ruff + frontend build)
├── config/                   YAMLs de runtime + example.env
├── docs/
│   ├── architecture/         specs/ e plans/ (artefatos arquiteturais)
│   ├── article-solid/        artigo SBC sobre SOLID aplicado a este projeto
│   └── img/                  imagens de documentação (demo gif)
├── src/driver_fatigue/
│   ├── application/          ports.py + use_cases/
│   ├── config/               settings.py (Pydantic + YAML)
│   ├── domain/               entities, evaluator, métricas — sem deps externas
│   ├── infrastructure/       adapters por porta (Strategy plural)
│   ├── interfaces/           cli/ + web/ (REST + cockpit React buildado)
│   └── resources/            audio/ + models/ — empacotados via package-data
├── tests/
│   ├── e2e/                  pipeline fim-a-fim
│   ├── fixtures/             test_sonolency.mp4
│   ├── integration/          adapters reais
│   └── unit/                 domínio + aplicação
├── web/                      fonte React + Vite + Tailwind
├── LICENSE                   MIT
├── pyproject.toml            setuptools + ruff + pytest + coverage
└── README.md                 este arquivo
```

## Status

- **Fase 1** ✅ — núcleo Clean Architecture + UI polida
- **Fase 2** ✅ — fontes (webcam/file/RTSP) + sinks (log/JSONL/MQTT/HTTP/som) + gravação
- **Fase 2.5** ✅ — redução de falsos positivos (PERCLOS, baseline pessoal de pitch, validadores de contexto)
- **Fase 3** ✅ — fusão multimodal (EAR + MAR + head pose + ONNX) + Cockpit React/Tailwind
- **Artigo SOLID** ✅ — entregue (`docs/article-solid/`)

## Licença

MIT — ver `LICENSE`.
