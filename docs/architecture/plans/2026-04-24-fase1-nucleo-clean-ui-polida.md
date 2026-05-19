# Fase 1 — Núcleo Clean + UI Polida — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refatorar o projeto atual (`src/main.py` monolítico) em Clean Architecture de 4 camadas, substituindo dlib por MediaPipe Face Mesh e adicionando renderização polida, mantendo comportamento funcional equivalente ao atual.

**Architecture:** Domain (puro) → Application (use cases + ports) → Infrastructure (adapters MediaPipe/OpenCV/pygame) → Interfaces (CLI + config YAML). Composition root em `bootstrap.py`.

**Tech Stack:** Python 3.11+, MediaPipe, OpenCV (opencv-python), numpy, pygame, pydantic-settings, PyYAML, pytest, pytest-cov.

**Spec:** `docs/superpowers/specs/2026-04-24-driver-fatigue-ubiquitous-design.md`

---

## Estrutura de arquivos ao final da Fase 1

```
pyproject.toml                                  # [novo]
src/driver_fatigue/
  __init__.py                                   # [novo]
  domain/
    __init__.py
    entities.py                                 # Frame, Point, FaceLandmarks, FatigueState, FatigueEvent
    value_objects.py                            # FatigueThresholds
    metrics.py                                  # eye_aspect_ratio, mouth_aspect_ratio
    evaluator.py                                # evaluate_fatigue
    rendering_theme.py                          # RenderingTheme
  application/
    __init__.py
    ports.py                                    # VideoSourcePort, FaceDetectorPort, AlertSinkPort, FramePresenterPort
    use_cases/
      __init__.py
      detect_fatigue.py                         # DetectFatigueUseCase
      monitor_driver.py                         # MonitorDriverUseCase
  infrastructure/
    __init__.py
    video_sources/
      __init__.py
      webcam.py                                 # WebcamVideoSource
    detectors/
      __init__.py
      mediapipe_detector.py                     # MediapipeFaceDetector + índices
    alert_sinks/
      __init__.py
      sound.py                                  # SoundSink (pygame)
      log.py                                    # LogSink
    presenters/
      __init__.py
      opencv_window.py                          # OpenCvWindowPresenter
    rendering/
      __init__.py
      curves.py                                 # catmull_rom_spline
      overlay.py                                # draw_filled_overlay
      glow.py                                   # apply_glow
      hud.py                                    # draw_hud
  interfaces/
    __init__.py
    cli/
      __init__.py
      main.py                                   # CLI argparse
    config/
      __init__.py
      settings.py                               # pydantic-settings
  bootstrap.py                                  # composition root
tests/
  __init__.py
  conftest.py
  unit/
    __init__.py
    domain/
      __init__.py
      test_metrics.py
      test_evaluator.py
      test_entities.py
    application/
      __init__.py
      test_detect_fatigue.py
      test_monitor_driver.py
  integration/
    __init__.py
    test_mediapipe_detector.py                  # smoke test contra test_sonolency.mp4
    test_opencv_presenter.py                    # renderização contra buffer
    test_log_sink.py
    test_sound_sink.py
  e2e/
    __init__.py
    test_bootstrap_pipeline.py                  # pipeline completa com FakeVideoSource

config/
  default.yaml                                  # [novo]
  example.env                                   # [novo]

# removidos ao final:
src/main.py                                     # substituído por src/driver_fatigue/
requeriments/requirements.txt                   # substituído por pyproject.toml
```

---

## Task 1: Scaffolding do projeto e pyproject.toml

**Files:**
- Create: `pyproject.toml`
- Create: `src/driver_fatigue/__init__.py` (vazio)
- Create: `tests/__init__.py` (vazio)
- Create: `tests/conftest.py`
- Create: `.gitignore` (adicionar se não existir)
- Create: estrutura de pastas de módulos com `__init__.py` vazios

- [ ] **Step 1: Criar pyproject.toml**

```toml
[build-system]
requires = ["setuptools>=68", "wheel"]
build-backend = "setuptools.build_meta"

[project]
name = "driver-fatigue-detector"
version = "0.2.0"
description = "Driver fatigue detector — Clean Architecture"
requires-python = ">=3.11"
dependencies = [
    "opencv-python>=4.9",
    "mediapipe>=0.10.9",
    "numpy>=1.26",
    "pygame>=2.5",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "pyyaml>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "ruff>=0.3",
]

[project.scripts]
driver-fatigue = "driver_fatigue.interfaces.cli.main:main"

[tool.setuptools.packages.find]
where = ["src"]

[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "-ra --strict-markers"

[tool.coverage.run]
source = ["src/driver_fatigue/domain", "src/driver_fatigue/application"]
branch = true

[tool.coverage.report]
fail_under = 95
show_missing = true
```

- [ ] **Step 2: Criar árvore de pastas e __init__.py vazios**

Criar arquivos vazios (apenas `__init__.py` com conteúdo `""`):

```
src/driver_fatigue/__init__.py
src/driver_fatigue/domain/__init__.py
src/driver_fatigue/application/__init__.py
src/driver_fatigue/application/use_cases/__init__.py
src/driver_fatigue/infrastructure/__init__.py
src/driver_fatigue/infrastructure/video_sources/__init__.py
src/driver_fatigue/infrastructure/detectors/__init__.py
src/driver_fatigue/infrastructure/alert_sinks/__init__.py
src/driver_fatigue/infrastructure/presenters/__init__.py
src/driver_fatigue/infrastructure/rendering/__init__.py
src/driver_fatigue/interfaces/__init__.py
src/driver_fatigue/interfaces/cli/__init__.py
src/driver_fatigue/interfaces/config/__init__.py
tests/__init__.py
tests/unit/__init__.py
tests/unit/domain/__init__.py
tests/unit/application/__init__.py
tests/integration/__init__.py
tests/e2e/__init__.py
```

- [ ] **Step 3: Criar tests/conftest.py**

```python
"""Fixtures compartilhados de pytest."""
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ASSETS_DIR = PROJECT_ROOT / "assets"


@pytest.fixture(scope="session")
def test_video_path() -> Path:
    path = ASSETS_DIR / "test_sonolency.mp4"
    if not path.exists():
        pytest.skip(f"Vídeo de teste não encontrado: {path}")
    return path
```

- [ ] **Step 4: Instalar em modo editable e validar**

Run: `pip install -e ".[dev]"`
Expected: instalação sem erros.

Run: `pytest --collect-only`
Expected: `collected 0 items` (nenhum teste ainda, mas pytest carrega).

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml src/driver_fatigue tests/
git commit -m "chore: scaffolding Clean Architecture + pyproject.toml"
```

---

## Task 2: Domain — Point e Frame

**Files:**
- Create: `src/driver_fatigue/domain/entities.py`
- Create: `tests/unit/domain/test_entities.py`

- [ ] **Step 1: Escrever os testes**

`tests/unit/domain/test_entities.py`:

```python
import numpy as np
import pytest

from driver_fatigue.domain.entities import Frame, Point


class TestPoint:
    def test_point_has_x_and_y(self):
        p = Point(x=1.5, y=2.5)
        assert p.x == 1.5
        assert p.y == 2.5

    def test_point_is_frozen(self):
        p = Point(x=1.0, y=2.0)
        with pytest.raises((AttributeError, Exception)):
            p.x = 99.0


class TestFrame:
    def test_frame_stores_image_timestamp_and_index(self):
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        f = Frame(image=img, timestamp=1.5, index=42)
        assert f.image is img
        assert f.timestamp == 1.5
        assert f.index == 42

    def test_frame_is_frozen(self):
        img = np.zeros((10, 10, 3), dtype=np.uint8)
        f = Frame(image=img, timestamp=0.0, index=0)
        with pytest.raises((AttributeError, Exception)):
            f.index = 99
```

- [ ] **Step 2: Rodar teste para confirmar falha**

Run: `pytest tests/unit/domain/test_entities.py -v`
Expected: ERROR ao importar (`ModuleNotFoundError` ou `ImportError`) — módulo ainda não existe.

- [ ] **Step 3: Implementar entities.py**

`src/driver_fatigue/domain/entities.py`:

```python
from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True, slots=True)
class Point:
    x: float
    y: float


@dataclass(frozen=True)
class Frame:
    image: np.ndarray
    timestamp: float
    index: int
```

Nota: `Frame` não usa `slots=True` porque `np.ndarray` + frozen + slots têm pegadinhas; `frozen=True` basta.

- [ ] **Step 4: Rodar teste para confirmar sucesso**

Run: `pytest tests/unit/domain/test_entities.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/domain/entities.py tests/unit/domain/test_entities.py
git commit -m "feat(domain): Point e Frame com testes"
```

---

## Task 3: Domain — FaceLandmarks, FatigueState, FatigueEvent

**Files:**
- Modify: `src/driver_fatigue/domain/entities.py`
- Modify: `tests/unit/domain/test_entities.py`

- [ ] **Step 1: Adicionar testes**

Adicionar ao final de `tests/unit/domain/test_entities.py`:

```python
from driver_fatigue.domain.entities import (
    FaceLandmarks,
    FatigueEvent,
    FatigueState,
    Severity,
)


def _pts(n: int) -> tuple:
    return tuple(Point(x=float(i), y=float(i)) for i in range(n))


class TestFaceLandmarks:
    def test_all_required_regions_present(self):
        lm = FaceLandmarks(
            left_eye_contour=_pts(6),
            right_eye_contour=_pts(6),
            left_iris=_pts(5),
            right_iris=_pts(5),
            mouth_outer=_pts(12),
            mouth_inner=_pts(8),
            face_oval=_pts(36),
        )
        assert len(lm.left_eye_contour) == 6
        assert lm.left_iris is not None

    def test_iris_can_be_none(self):
        lm = FaceLandmarks(
            left_eye_contour=_pts(6),
            right_eye_contour=_pts(6),
            left_iris=None,
            right_iris=None,
            mouth_outer=_pts(12),
            mouth_inner=_pts(8),
            face_oval=_pts(36),
        )
        assert lm.left_iris is None
        assert lm.right_iris is None


class TestFatigueState:
    def test_initial_state_is_normal(self):
        s = FatigueState.initial()
        assert s.ear == 0.0
        assert s.mar == 0.0
        assert s.consecutive_frames == 0
        assert s.is_fatigued is False
        assert s.is_yawning is False
        assert s.severity == "normal"

    def test_state_is_frozen(self):
        s = FatigueState.initial()
        with pytest.raises((AttributeError, Exception)):
            s.ear = 0.9


class TestFatigueEvent:
    def test_event_has_timestamp_state_and_frame_index(self):
        s = FatigueState.initial()
        e = FatigueEvent(timestamp=1.5, state=s, frame_index=10)
        assert e.timestamp == 1.5
        assert e.state is s
        assert e.frame_index == 10
```

- [ ] **Step 2: Rodar teste para confirmar falha**

Run: `pytest tests/unit/domain/test_entities.py -v`
Expected: ImportError em `FaceLandmarks`, `FatigueState`, `FatigueEvent`, `Severity`.

- [ ] **Step 3: Estender entities.py**

Adicionar ao `src/driver_fatigue/domain/entities.py`:

```python
from typing import Literal

Severity = Literal["normal", "warning", "alert"]


@dataclass(frozen=True)
class FaceLandmarks:
    left_eye_contour: tuple[Point, ...]
    right_eye_contour: tuple[Point, ...]
    left_iris: tuple[Point, ...] | None
    right_iris: tuple[Point, ...] | None
    mouth_outer: tuple[Point, ...]
    mouth_inner: tuple[Point, ...]
    face_oval: tuple[Point, ...]


@dataclass(frozen=True)
class FatigueState:
    ear: float
    mar: float
    consecutive_frames: int
    is_fatigued: bool
    is_yawning: bool
    severity: Severity

    @classmethod
    def initial(cls) -> "FatigueState":
        return cls(
            ear=0.0,
            mar=0.0,
            consecutive_frames=0,
            is_fatigued=False,
            is_yawning=False,
            severity="normal",
        )


@dataclass(frozen=True)
class FatigueEvent:
    timestamp: float
    state: FatigueState
    frame_index: int
```

- [ ] **Step 4: Rodar teste para confirmar sucesso**

Run: `pytest tests/unit/domain/test_entities.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/domain/entities.py tests/unit/domain/test_entities.py
git commit -m "feat(domain): FaceLandmarks, FatigueState, FatigueEvent"
```

---

## Task 4: Domain — FatigueThresholds

**Files:**
- Create: `src/driver_fatigue/domain/value_objects.py`
- Create: `tests/unit/domain/test_value_objects.py`

- [ ] **Step 1: Escrever os testes**

`tests/unit/domain/test_value_objects.py`:

```python
import pytest

from driver_fatigue.domain.value_objects import FatigueThresholds


class TestFatigueThresholds:
    def test_defaults_match_original_code(self):
        t = FatigueThresholds()
        assert t.ear_threshold == 0.25
        assert t.mar_threshold == 0.60
        assert t.consecutive_frames == 20

    def test_warning_ratio_default(self):
        t = FatigueThresholds()
        assert t.warning_ratio == 0.85

    def test_is_frozen(self):
        t = FatigueThresholds()
        with pytest.raises((AttributeError, Exception)):
            t.ear_threshold = 0.9

    def test_rejects_invalid_warning_ratio(self):
        with pytest.raises(ValueError):
            FatigueThresholds(warning_ratio=1.5)

    def test_rejects_negative_consecutive_frames(self):
        with pytest.raises(ValueError):
            FatigueThresholds(consecutive_frames=-1)
```

- [ ] **Step 2: Rodar teste para confirmar falha**

Run: `pytest tests/unit/domain/test_value_objects.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar value_objects.py**

`src/driver_fatigue/domain/value_objects.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FatigueThresholds:
    ear_threshold: float = 0.25
    mar_threshold: float = 0.60
    consecutive_frames: int = 20
    warning_ratio: float = 0.85

    def __post_init__(self) -> None:
        if not 0.0 < self.warning_ratio <= 1.0:
            raise ValueError("warning_ratio deve estar em (0, 1]")
        if self.consecutive_frames < 0:
            raise ValueError("consecutive_frames não pode ser negativo")
        if self.ear_threshold <= 0:
            raise ValueError("ear_threshold deve ser positivo")
        if self.mar_threshold <= 0:
            raise ValueError("mar_threshold deve ser positivo")
```

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/unit/domain/test_value_objects.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/domain/value_objects.py tests/unit/domain/test_value_objects.py
git commit -m "feat(domain): FatigueThresholds com validação"
```

---

## Task 5: Domain — eye_aspect_ratio

**Files:**
- Create: `src/driver_fatigue/domain/metrics.py`
- Create: `tests/unit/domain/test_metrics.py`

**Nota sobre EAR genérico:** a métrica EAR original (dlib 6 pontos) é `(|p1-p5| + |p2-p4|) / (2 * |p0-p3|)`. Para contornos maiores (MediaPipe), generalizamos: razão entre "altura média vertical do olho" e "largura horizontal". A implementação usa os 6 pontos-chave semânticos (externo, superior-esquerdo, superior-direito, interno, inferior-direito, inferior-esquerdo) — o adapter MediaPipe é responsável por escolher esses 6 pontos ao construir o `left_eye_contour`/`right_eye_contour` com exatamente 6 pontos nessa ordem.

- [ ] **Step 1: Escrever os testes**

`tests/unit/domain/test_metrics.py`:

```python
import math

import pytest

from driver_fatigue.domain.entities import Point
from driver_fatigue.domain.metrics import eye_aspect_ratio, mouth_aspect_ratio


def _eye(open_ratio: float) -> tuple[Point, ...]:
    """Olho sintético: p0 e p3 são cantos (largura=1.0),
    p1,p2 em cima e p5,p4 embaixo separados por open_ratio."""
    h = open_ratio / 2
    return (
        Point(x=0.0, y=0.0),    # p0 canto esquerdo
        Point(x=0.3, y=-h),     # p1 topo-esq
        Point(x=0.7, y=-h),     # p2 topo-dir
        Point(x=1.0, y=0.0),    # p3 canto direito
        Point(x=0.7, y=h),      # p4 base-dir
        Point(x=0.3, y=h),      # p5 base-esq
    )


class TestEyeAspectRatio:
    def test_fully_open_eye(self):
        eye = _eye(open_ratio=0.4)
        # altura média = 0.4, largura = 1.0 → EAR = (0.4+0.4)/(2*1.0) = 0.4
        assert eye_aspect_ratio(eye) == pytest.approx(0.4, abs=1e-6)

    def test_closed_eye(self):
        eye = _eye(open_ratio=0.0)
        assert eye_aspect_ratio(eye) == pytest.approx(0.0, abs=1e-6)

    def test_standard_threshold_boundary(self):
        # EAR = 0.25 (threshold padrão) → open_ratio = 0.25
        eye = _eye(open_ratio=0.25)
        assert eye_aspect_ratio(eye) == pytest.approx(0.25, abs=1e-6)

    def test_raises_on_wrong_number_of_points(self):
        pts = tuple(Point(x=float(i), y=0.0) for i in range(5))
        with pytest.raises(ValueError):
            eye_aspect_ratio(pts)

    def test_raises_on_zero_width(self):
        pts = (
            Point(0.0, 0.0), Point(0.0, 0.0), Point(0.0, 0.0),
            Point(0.0, 0.0), Point(0.0, 0.0), Point(0.0, 0.0),
        )
        with pytest.raises(ValueError):
            eye_aspect_ratio(pts)
```

- [ ] **Step 2: Rodar teste para confirmar falha**

Run: `pytest tests/unit/domain/test_metrics.py::TestEyeAspectRatio -v`
Expected: ImportError.

- [ ] **Step 3: Implementar eye_aspect_ratio**

`src/driver_fatigue/domain/metrics.py`:

```python
"""Métricas geométricas puras sobre landmarks faciais."""
from __future__ import annotations

import math
from typing import Sequence

from driver_fatigue.domain.entities import Point


def _dist(a: Point, b: Point) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)


def eye_aspect_ratio(eye: Sequence[Point]) -> float:
    """Razão altura/largura do olho.

    Espera 6 pontos na ordem semântica:
    p0=canto externo, p1=topo-ext, p2=topo-int, p3=canto interno,
    p4=base-int, p5=base-ext.

    Formula: (|p1-p5| + |p2-p4|) / (2 * |p0-p3|)
    """
    if len(eye) != 6:
        raise ValueError(f"eye_aspect_ratio requer 6 pontos, recebeu {len(eye)}")
    width = _dist(eye[0], eye[3])
    if width == 0.0:
        raise ValueError("largura do olho é zero — pontos coincidentes")
    a = _dist(eye[1], eye[5])
    b = _dist(eye[2], eye[4])
    return (a + b) / (2.0 * width)
```

- [ ] **Step 4: Rodar teste para confirmar sucesso**

Run: `pytest tests/unit/domain/test_metrics.py::TestEyeAspectRatio -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/domain/metrics.py tests/unit/domain/test_metrics.py
git commit -m "feat(domain): eye_aspect_ratio"
```

---

## Task 6: Domain — mouth_aspect_ratio

**Files:**
- Modify: `src/driver_fatigue/domain/metrics.py`
- Modify: `tests/unit/domain/test_metrics.py`

**Nota:** MAR usa 12 pontos do contorno externo da boca (análogo aos 20 do dlib, mas abstraído). Adapter MediaPipe entrega `mouth_outer` com exatamente 12 pontos ordenados começando pelo canto esquerdo, percorrendo o lábio superior, canto direito, lábio inferior e voltando — índices de pares verticais (3,9), (2,10), (4,8), e par horizontal (0,6).

- [ ] **Step 1: Adicionar testes**

Adicionar ao `tests/unit/domain/test_metrics.py`:

```python
def _mouth(open_ratio: float) -> tuple[Point, ...]:
    """Boca sintética com 12 pontos. Largura=1.0, abertura=open_ratio."""
    h = open_ratio / 2
    # p0..p6 = lábio superior (esq → dir)
    # p6..p11,p0 = lábio inferior (dir → esq → esq)
    return (
        Point(0.0, 0.0),    # p0 canto esq
        Point(0.15, -h),    # p1 topo
        Point(0.35, -h),    # p2 topo
        Point(0.5, -h),     # p3 topo centro
        Point(0.65, -h),    # p4 topo
        Point(0.85, -h),    # p5 topo
        Point(1.0, 0.0),    # p6 canto dir
        Point(0.85, h),     # p7 base
        Point(0.65, h),     # p8 base
        Point(0.5, h),      # p9 base centro
        Point(0.35, h),     # p10 base
        Point(0.15, h),     # p11 base
    )


class TestMouthAspectRatio:
    def test_closed_mouth(self):
        m = _mouth(open_ratio=0.0)
        assert mouth_aspect_ratio(m) == pytest.approx(0.0, abs=1e-6)

    def test_open_mouth(self):
        m = _mouth(open_ratio=0.6)
        # alturas (p3-p9)=0.6, (p2-p10)=0.6, (p4-p8)=0.6 → média=0.6
        # largura (p0-p6)=1.0 → MAR=0.6
        assert mouth_aspect_ratio(m) == pytest.approx(0.6, abs=1e-6)

    def test_raises_on_wrong_number_of_points(self):
        pts = tuple(Point(x=float(i), y=0.0) for i in range(11))
        with pytest.raises(ValueError):
            mouth_aspect_ratio(pts)

    def test_raises_on_zero_width(self):
        pts = tuple(Point(0.0, 0.0) for _ in range(12))
        with pytest.raises(ValueError):
            mouth_aspect_ratio(pts)
```

- [ ] **Step 2: Rodar teste para confirmar falha**

Run: `pytest tests/unit/domain/test_metrics.py::TestMouthAspectRatio -v`
Expected: AttributeError (`mouth_aspect_ratio` não existe).

- [ ] **Step 3: Adicionar mouth_aspect_ratio**

Adicionar ao `src/driver_fatigue/domain/metrics.py`:

```python
def mouth_aspect_ratio(mouth: Sequence[Point]) -> float:
    """Razão altura/largura da boca.

    Espera 12 pontos do contorno externo. Largura = |p0 - p6|.
    Altura = média de |p3-p9|, |p2-p10|, |p4-p8|.
    """
    if len(mouth) != 12:
        raise ValueError(f"mouth_aspect_ratio requer 12 pontos, recebeu {len(mouth)}")
    width = _dist(mouth[0], mouth[6])
    if width == 0.0:
        raise ValueError("largura da boca é zero — pontos coincidentes")
    a = _dist(mouth[3], mouth[9])
    b = _dist(mouth[2], mouth[10])
    c = _dist(mouth[4], mouth[8])
    return (a + b + c) / (3.0 * width)
```

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/unit/domain/test_metrics.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/domain/metrics.py tests/unit/domain/test_metrics.py
git commit -m "feat(domain): mouth_aspect_ratio"
```

---

## Task 7: Domain — evaluate_fatigue

**Files:**
- Create: `src/driver_fatigue/domain/evaluator.py`
- Create: `tests/unit/domain/test_evaluator.py`

- [ ] **Step 1: Escrever testes para as transições**

`tests/unit/domain/test_evaluator.py`:

```python
import pytest

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Point
from driver_fatigue.domain.evaluator import evaluate_fatigue
from driver_fatigue.domain.value_objects import FatigueThresholds


def _eye(open_ratio: float) -> tuple[Point, ...]:
    h = open_ratio / 2
    return (
        Point(0.0, 0.0), Point(0.3, -h), Point(0.7, -h),
        Point(1.0, 0.0), Point(0.7, h),  Point(0.3, h),
    )


def _mouth(open_ratio: float) -> tuple[Point, ...]:
    h = open_ratio / 2
    return (
        Point(0.0, 0.0), Point(0.15, -h), Point(0.35, -h), Point(0.5, -h),
        Point(0.65, -h), Point(0.85, -h), Point(1.0, 0.0), Point(0.85, h),
        Point(0.65, h), Point(0.5, h), Point(0.35, h), Point(0.15, h),
    )


def _landmarks(eye_open: float, mouth_open: float) -> FaceLandmarks:
    return FaceLandmarks(
        left_eye_contour=_eye(eye_open),
        right_eye_contour=_eye(eye_open),
        left_iris=None, right_iris=None,
        mouth_outer=_mouth(mouth_open),
        mouth_inner=_mouth(mouth_open * 0.5),
        face_oval=tuple(Point(float(i), 0.0) for i in range(36)),
    )


THRESH = FatigueThresholds(
    ear_threshold=0.25, mar_threshold=0.60,
    consecutive_frames=5, warning_ratio=0.8,
)


class TestEvaluateFatigue:
    def test_open_eyes_no_yawn_is_normal(self):
        lm = _landmarks(eye_open=0.4, mouth_open=0.1)
        result = evaluate_fatigue(lm, THRESH, FatigueState.initial())
        assert result.severity == "normal"
        assert result.is_fatigued is False
        assert result.consecutive_frames == 0

    def test_closed_eyes_increment_counter(self):
        lm = _landmarks(eye_open=0.1, mouth_open=0.1)  # EAR=0.1 < 0.25
        result = evaluate_fatigue(lm, THRESH, FatigueState.initial())
        assert result.consecutive_frames == 1
        assert result.severity == "warning"

    def test_counter_reaches_threshold_triggers_alert(self):
        lm = _landmarks(eye_open=0.1, mouth_open=0.1)
        state = FatigueState.initial()
        for _ in range(5):  # consecutive_frames threshold = 5
            state = evaluate_fatigue(lm, THRESH, state)
        assert state.consecutive_frames == 5
        assert state.severity == "alert"
        assert state.is_fatigued is True

    def test_yawn_also_increments_counter(self):
        lm = _landmarks(eye_open=0.4, mouth_open=0.8)  # MAR>0.60
        result = evaluate_fatigue(lm, THRESH, FatigueState.initial())
        assert result.consecutive_frames == 1
        assert result.is_yawning is True

    def test_open_eyes_reset_counter_back_to_normal(self):
        lm_closed = _landmarks(eye_open=0.1, mouth_open=0.1)
        lm_open = _landmarks(eye_open=0.4, mouth_open=0.1)
        state = FatigueState.initial()
        for _ in range(5):
            state = evaluate_fatigue(lm_closed, THRESH, state)
        assert state.severity == "alert"
        state = evaluate_fatigue(lm_open, THRESH, state)
        assert state.severity == "normal"
        assert state.consecutive_frames == 0
        assert state.is_fatigued is False

    def test_warning_fires_before_alert(self):
        # warning_ratio=0.8 * 5 = 4 → frames 1..3 = warning, frame 4 já é alert
        lm = _landmarks(eye_open=0.1, mouth_open=0.1)
        state = FatigueState.initial()
        state = evaluate_fatigue(lm, THRESH, state)  # 1
        assert state.severity == "warning"
        state = evaluate_fatigue(lm, THRESH, state)  # 2
        state = evaluate_fatigue(lm, THRESH, state)  # 3
        state = evaluate_fatigue(lm, THRESH, state)  # 4
        assert state.severity == "alert"  # 4 >= 0.8 * 5
```

- [ ] **Step 2: Rodar teste para confirmar falha**

Run: `pytest tests/unit/domain/test_evaluator.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar evaluator.py**

`src/driver_fatigue/domain/evaluator.py`:

```python
"""Regra central de decisão sobre fadiga, a partir de landmarks."""
from __future__ import annotations

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState
from driver_fatigue.domain.metrics import eye_aspect_ratio, mouth_aspect_ratio
from driver_fatigue.domain.value_objects import FatigueThresholds


def evaluate_fatigue(
    landmarks: FaceLandmarks,
    thresholds: FatigueThresholds,
    previous: FatigueState,
) -> FatigueState:
    left_ear = eye_aspect_ratio(landmarks.left_eye_contour)
    right_ear = eye_aspect_ratio(landmarks.right_eye_contour)
    ear = (left_ear + right_ear) / 2.0
    mar = mouth_aspect_ratio(landmarks.mouth_outer)

    eyes_closed = ear < thresholds.ear_threshold
    yawning = mar > thresholds.mar_threshold
    triggered = eyes_closed or yawning

    if triggered:
        consecutive = previous.consecutive_frames + 1
    else:
        consecutive = 0

    warning_cutoff = int(thresholds.consecutive_frames * thresholds.warning_ratio)
    if consecutive >= warning_cutoff and consecutive > 0:
        severity = "alert"
    elif consecutive > 0:
        severity = "warning"
    else:
        severity = "normal"

    return FatigueState(
        ear=ear,
        mar=mar,
        consecutive_frames=consecutive,
        is_fatigued=(severity == "alert"),
        is_yawning=(yawning and consecutive > 0),
        severity=severity,
    )
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/unit/domain/test_evaluator.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/domain/evaluator.py tests/unit/domain/test_evaluator.py
git commit -m "feat(domain): evaluate_fatigue com transicoes normal/warning/alert"
```

---

## Task 8: Domain — RenderingTheme

**Files:**
- Create: `src/driver_fatigue/domain/rendering_theme.py`
- Create: `tests/unit/domain/test_rendering_theme.py`

- [ ] **Step 1: Escrever testes**

`tests/unit/domain/test_rendering_theme.py`:

```python
import pytest

from driver_fatigue.domain.rendering_theme import RenderingTheme


class TestRenderingTheme:
    def test_defaults(self):
        t = RenderingTheme()
        assert t.color_normal == (255, 255, 0)   # ciano BGR
        assert t.color_warning == (0, 200, 255)  # âmbar BGR
        assert t.color_alert == (50, 50, 255)    # vermelho BGR
        assert t.overlay_alpha == 0.35
        assert t.glow_enabled is True
        assert t.show_hud is True
        assert t.smoothing_steps == 20

    def test_is_frozen(self):
        t = RenderingTheme()
        with pytest.raises((AttributeError, Exception)):
            t.show_hud = False

    def test_rejects_alpha_out_of_range(self):
        with pytest.raises(ValueError):
            RenderingTheme(overlay_alpha=1.5)

    def test_rejects_negative_smoothing(self):
        with pytest.raises(ValueError):
            RenderingTheme(smoothing_steps=-1)
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/unit/domain/test_rendering_theme.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar**

`src/driver_fatigue/domain/rendering_theme.py`:

```python
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RenderingTheme:
    color_normal: tuple[int, int, int] = (255, 255, 0)    # ciano BGR
    color_warning: tuple[int, int, int] = (0, 200, 255)   # âmbar BGR
    color_alert: tuple[int, int, int] = (50, 50, 255)     # vermelho BGR
    overlay_alpha: float = 0.35
    glow_enabled: bool = True
    glow_sigma: int = 15
    show_hud: bool = True
    show_face_oval: bool = True
    smoothing_steps: int = 20

    def __post_init__(self) -> None:
        if not 0.0 <= self.overlay_alpha <= 1.0:
            raise ValueError("overlay_alpha deve estar em [0, 1]")
        if self.smoothing_steps < 0:
            raise ValueError("smoothing_steps não pode ser negativo")
        if self.glow_sigma < 0:
            raise ValueError("glow_sigma não pode ser negativo")
```

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/unit/domain/test_rendering_theme.py -v`
Expected: 4 passed.

- [ ] **Step 5: Verificar cobertura do domain**

Run: `pytest tests/unit/domain/ --cov=src/driver_fatigue/domain --cov-report=term-missing`
Expected: coverage >= 95% em todos os módulos do domain.

- [ ] **Step 6: Commit**

```bash
git add src/driver_fatigue/domain/rendering_theme.py tests/unit/domain/test_rendering_theme.py
git commit -m "feat(domain): RenderingTheme value object"
```

---

## Task 9: Application — Ports (protocols)

**Files:**
- Create: `src/driver_fatigue/application/ports.py`

Protocols não precisam de teste próprio — são cobertos pelos testes dos use cases que os consomem.

- [ ] **Step 1: Implementar ports.py**

`src/driver_fatigue/application/ports.py`:

```python
"""Interfaces (ports) que a Application exige da Infrastructure."""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from driver_fatigue.domain.entities import (
    FaceLandmarks,
    FatigueEvent,
    FatigueState,
    Frame,
)


@runtime_checkable
class VideoSourcePort(Protocol):
    def read(self) -> Frame | None:
        """Retorna o próximo Frame ou None quando terminou."""
        ...

    def release(self) -> None:
        """Libera recursos (câmera, arquivo, conexão)."""
        ...


@runtime_checkable
class FaceDetectorPort(Protocol):
    def detect(self, frame: Frame) -> list[FaceLandmarks]:
        """Lista de rostos detectados no frame; vazia se nenhum."""
        ...


@runtime_checkable
class AlertSinkPort(Protocol):
    def notify(self, event: FatigueEvent) -> None:
        """Chamado quando severity vira 'alert'."""
        ...

    def on_recovery(self, frame_index: int) -> None:
        """Chamado quando severity volta a 'normal' após 'alert'."""
        ...


@runtime_checkable
class FramePresenterPort(Protocol):
    def present(
        self,
        frame: Frame,
        landmarks: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        """Renderiza/armazena o frame com overlays."""
        ...

    def should_stop(self) -> bool:
        """True se o usuário solicitou encerramento (ex.: tecla 'q')."""
        ...

    def close(self) -> None:
        """Libera recursos (janelas, arquivos)."""
        ...
```

- [ ] **Step 2: Validar que importa sem erro**

Run: `python -c "from driver_fatigue.application.ports import VideoSourcePort, FaceDetectorPort, AlertSinkPort, FramePresenterPort; print('ok')"`
Expected: `ok`.

- [ ] **Step 3: Commit**

```bash
git add src/driver_fatigue/application/ports.py
git commit -m "feat(application): ports VideoSource/Detector/AlertSink/Presenter"
```

---

## Task 10: Application — DetectFatigueUseCase

**Files:**
- Create: `src/driver_fatigue/application/use_cases/detect_fatigue.py`
- Create: `tests/unit/application/test_detect_fatigue.py`

- [ ] **Step 1: Escrever testes com fakes**

`tests/unit/application/test_detect_fatigue.py`:

```python
import numpy as np
import pytest

from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.domain.value_objects import FatigueThresholds


def _landmarks(eye_open: float, mouth_open: float) -> FaceLandmarks:
    h_eye = eye_open / 2
    h_m = mouth_open / 2
    eye = (
        Point(0.0, 0.0), Point(0.3, -h_eye), Point(0.7, -h_eye),
        Point(1.0, 0.0), Point(0.7, h_eye), Point(0.3, h_eye),
    )
    mouth = (
        Point(0.0, 0.0), Point(0.15, -h_m), Point(0.35, -h_m), Point(0.5, -h_m),
        Point(0.65, -h_m), Point(0.85, -h_m), Point(1.0, 0.0), Point(0.85, h_m),
        Point(0.65, h_m), Point(0.5, h_m), Point(0.35, h_m), Point(0.15, h_m),
    )
    return FaceLandmarks(
        left_eye_contour=eye, right_eye_contour=eye,
        left_iris=None, right_iris=None,
        mouth_outer=mouth, mouth_inner=mouth,
        face_oval=tuple(Point(float(i), 0.0) for i in range(36)),
    )


class FakeDetector:
    def __init__(self, landmarks_list: list[FaceLandmarks]):
        self._ret = landmarks_list

    def detect(self, frame):
        return self._ret


def _frame() -> Frame:
    return Frame(image=np.zeros((2, 2, 3), dtype=np.uint8), timestamp=0.0, index=0)


class TestDetectFatigueUseCase:
    def test_returns_previous_state_when_no_face(self):
        uc = DetectFatigueUseCase(FakeDetector([]), FatigueThresholds())
        prev = FatigueState.initial()
        state, faces = uc.execute(_frame(), prev)
        assert state == prev
        assert faces == []

    def test_uses_first_face_when_multiple(self):
        lm1 = _landmarks(eye_open=0.1, mouth_open=0.1)
        lm2 = _landmarks(eye_open=0.5, mouth_open=0.1)
        uc = DetectFatigueUseCase(
            FakeDetector([lm1, lm2]),
            FatigueThresholds(ear_threshold=0.25, mar_threshold=0.6,
                              consecutive_frames=5, warning_ratio=0.8),
        )
        state, faces = uc.execute(_frame(), FatigueState.initial())
        assert state.severity == "warning"  # baseado em lm1 (EAR=0.1)
        assert len(faces) == 2

    def test_open_eyes_stay_normal(self):
        lm = _landmarks(eye_open=0.5, mouth_open=0.1)
        uc = DetectFatigueUseCase(FakeDetector([lm]), FatigueThresholds())
        state, _ = uc.execute(_frame(), FatigueState.initial())
        assert state.severity == "normal"
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/unit/application/test_detect_fatigue.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar use case**

`src/driver_fatigue/application/use_cases/detect_fatigue.py`:

```python
from __future__ import annotations

from driver_fatigue.application.ports import FaceDetectorPort
from driver_fatigue.domain.entities import (
    FaceLandmarks,
    FatigueState,
    Frame,
)
from driver_fatigue.domain.evaluator import evaluate_fatigue
from driver_fatigue.domain.value_objects import FatigueThresholds


class DetectFatigueUseCase:
    def __init__(
        self,
        detector: FaceDetectorPort,
        thresholds: FatigueThresholds,
    ) -> None:
        self._detector = detector
        self._thresholds = thresholds

    def execute(
        self,
        frame: Frame,
        previous: FatigueState,
    ) -> tuple[FatigueState, list[FaceLandmarks]]:
        faces = self._detector.detect(frame)
        if not faces:
            return previous, faces
        new_state = evaluate_fatigue(faces[0], self._thresholds, previous)
        return new_state, faces
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/unit/application/test_detect_fatigue.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/application/use_cases/detect_fatigue.py tests/unit/application/test_detect_fatigue.py
git commit -m "feat(application): DetectFatigueUseCase"
```

---

## Task 11: Application — MonitorDriverUseCase

**Files:**
- Create: `src/driver_fatigue/application/use_cases/monitor_driver.py`
- Create: `tests/unit/application/test_monitor_driver.py`

- [ ] **Step 1: Escrever testes**

`tests/unit/application/test_monitor_driver.py`:

```python
import numpy as np

from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.application.use_cases.monitor_driver import MonitorDriverUseCase
from driver_fatigue.domain.entities import (
    FaceLandmarks,
    FatigueState,
    Frame,
    Point,
)
from driver_fatigue.domain.value_objects import FatigueThresholds


def _eye(open_ratio):
    h = open_ratio / 2
    return (Point(0,0), Point(0.3,-h), Point(0.7,-h),
            Point(1,0), Point(0.7,h), Point(0.3,h))


def _mouth(open_ratio):
    h = open_ratio / 2
    return (Point(0,0), Point(0.15,-h), Point(0.35,-h), Point(0.5,-h),
            Point(0.65,-h), Point(0.85,-h), Point(1,0), Point(0.85,h),
            Point(0.65,h), Point(0.5,h), Point(0.35,h), Point(0.15,h))


def _landmarks(eye_open, mouth_open):
    return FaceLandmarks(
        left_eye_contour=_eye(eye_open), right_eye_contour=_eye(eye_open),
        left_iris=None, right_iris=None,
        mouth_outer=_mouth(mouth_open), mouth_inner=_mouth(mouth_open),
        face_oval=tuple(Point(float(i), 0) for i in range(36)),
    )


class FakeSource:
    def __init__(self, n: int):
        self._remaining = n
        self._i = 0
        self.released = False

    def read(self):
        if self._remaining <= 0:
            return None
        self._remaining -= 1
        self._i += 1
        img = np.zeros((2, 2, 3), dtype=np.uint8)
        return Frame(image=img, timestamp=float(self._i), index=self._i - 1)

    def release(self):
        self.released = True


class FakeDetector:
    def __init__(self, lm):
        self._lm = lm

    def detect(self, frame):
        return [self._lm] if self._lm else []


class SpySink:
    def __init__(self):
        self.notifications = []
        self.recoveries = []

    def notify(self, event):
        self.notifications.append(event)

    def on_recovery(self, frame_index):
        self.recoveries.append(frame_index)


class FakePresenter:
    def __init__(self, stop_after: int = 1_000_000):
        self.presented = 0
        self._stop_after = stop_after
        self.closed = False

    def present(self, frame, landmarks, state):
        self.presented += 1

    def should_stop(self):
        return self.presented >= self._stop_after

    def close(self):
        self.closed = True


class TestMonitorDriverUseCase:
    def _build(self, n_frames, lm, stop_after=10_000):
        source = FakeSource(n_frames)
        sink = SpySink()
        presenter = FakePresenter(stop_after=stop_after)
        detect = DetectFatigueUseCase(
            FakeDetector(lm),
            FatigueThresholds(
                ear_threshold=0.25, mar_threshold=0.6,
                consecutive_frames=3, warning_ratio=0.8,
            ),
        )
        uc = MonitorDriverUseCase(
            source=source, detect=detect, sink=sink, presenter=presenter,
        )
        return uc, source, sink, presenter

    def test_stops_when_source_exhausts(self):
        uc, source, sink, presenter = self._build(n_frames=3, lm=_landmarks(0.5, 0.1))
        uc.run()
        assert presenter.presented == 3
        assert source.released is True
        assert presenter.closed is True

    def test_stops_when_presenter_requests(self):
        uc, source, sink, presenter = self._build(
            n_frames=100, lm=_landmarks(0.5, 0.1), stop_after=2,
        )
        uc.run()
        assert presenter.presented == 2

    def test_notifies_sink_on_alert(self):
        # 3 frames com olhos fechados → atinge alert ao 3º (threshold=3)
        uc, source, sink, presenter = self._build(n_frames=3, lm=_landmarks(0.1, 0.1))
        uc.run()
        # notify chamado uma única vez: transição normal/warning → alert
        assert len(sink.notifications) == 1
        assert sink.notifications[0].state.severity == "alert"

    def test_notifies_recovery_after_alert(self):
        # Simula: 3 frames alert → 2 frames normal → deve chamar on_recovery
        source = FakeSource(5)
        sink = SpySink()
        presenter = FakePresenter()

        class TwoPhaseDetector:
            def __init__(self):
                self.calls = 0
            def detect(self, frame):
                self.calls += 1
                if self.calls <= 3:
                    return [_landmarks(0.1, 0.1)]  # fechado
                return [_landmarks(0.5, 0.1)]      # aberto

        detect = DetectFatigueUseCase(
            TwoPhaseDetector(),
            FatigueThresholds(ear_threshold=0.25, mar_threshold=0.6,
                              consecutive_frames=3, warning_ratio=0.8),
        )
        MonitorDriverUseCase(
            source=source, detect=detect, sink=sink, presenter=presenter,
        ).run()
        assert len(sink.notifications) == 1
        assert len(sink.recoveries) == 1
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/unit/application/test_monitor_driver.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar**

`src/driver_fatigue/application/use_cases/monitor_driver.py`:

```python
from __future__ import annotations

from driver_fatigue.application.ports import (
    AlertSinkPort,
    FramePresenterPort,
    VideoSourcePort,
)
from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.domain.entities import FatigueEvent, FatigueState


class MonitorDriverUseCase:
    def __init__(
        self,
        source: VideoSourcePort,
        detect: DetectFatigueUseCase,
        sink: AlertSinkPort,
        presenter: FramePresenterPort,
    ) -> None:
        self._source = source
        self._detect = detect
        self._sink = sink
        self._presenter = presenter

    def run(self) -> None:
        state = FatigueState.initial()
        try:
            while not self._presenter.should_stop():
                frame = self._source.read()
                if frame is None:
                    break
                new_state, faces = self._detect.execute(frame, state)

                self._maybe_notify(previous=state, current=new_state, frame_index=frame.index)

                self._presenter.present(frame, faces, new_state)
                state = new_state
        finally:
            self._source.release()
            self._presenter.close()

    def _maybe_notify(
        self,
        previous: FatigueState,
        current: FatigueState,
        frame_index: int,
    ) -> None:
        entered_alert = previous.severity != "alert" and current.severity == "alert"
        left_alert = previous.severity == "alert" and current.severity == "normal"
        if entered_alert:
            self._sink.notify(FatigueEvent(
                timestamp=float(frame_index),  # substituído por timestamp real no bootstrap
                state=current,
                frame_index=frame_index,
            ))
        elif left_alert:
            self._sink.on_recovery(frame_index)
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/unit/application/test_monitor_driver.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/application/use_cases/monitor_driver.py tests/unit/application/test_monitor_driver.py
git commit -m "feat(application): MonitorDriverUseCase com notificacao edge-triggered"
```

---

## Task 12: Infrastructure — WebcamVideoSource

**Files:**
- Create: `src/driver_fatigue/infrastructure/video_sources/webcam.py`
- Create: `tests/integration/test_webcam_source.py`

**Nota:** teste "real" requer webcam presente — skip se indisponível. Testamos o comportamento estrutural (release).

- [ ] **Step 1: Escrever testes**

`tests/integration/test_webcam_source.py`:

```python
import cv2
import pytest

from driver_fatigue.infrastructure.video_sources.webcam import WebcamVideoSource


def _webcam_available() -> bool:
    cap = cv2.VideoCapture(0)
    ok = cap.isOpened()
    cap.release()
    return ok


pytestmark = pytest.mark.skipif(
    not _webcam_available(),
    reason="webcam 0 indisponível",
)


class TestWebcamVideoSource:
    def test_reads_a_frame(self):
        src = WebcamVideoSource(device_index=0)
        try:
            frame = src.read()
            assert frame is not None
            assert frame.image.shape[2] == 3
            assert frame.index == 0
            next_frame = src.read()
            assert next_frame.index == 1
        finally:
            src.release()

    def test_release_is_idempotent(self):
        src = WebcamVideoSource(device_index=0)
        src.release()
        src.release()  # não deve falhar
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_webcam_source.py -v`
Expected: ModuleNotFoundError (ou skip se sem webcam).

- [ ] **Step 3: Implementar webcam.py**

`src/driver_fatigue/infrastructure/video_sources/webcam.py`:

```python
from __future__ import annotations

import time

import cv2

from driver_fatigue.domain.entities import Frame


class WebcamVideoSource:
    def __init__(self, device_index: int = 0) -> None:
        self._cap = cv2.VideoCapture(device_index)
        if not self._cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir webcam {device_index}")
        self._index = 0
        self._released = False

    def read(self) -> Frame | None:
        ok, img = self._cap.read()
        if not ok:
            return None
        frame = Frame(image=img, timestamp=time.monotonic(), index=self._index)
        self._index += 1
        return frame

    def release(self) -> None:
        if not self._released:
            self._cap.release()
            self._released = True
```

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/integration/test_webcam_source.py -v`
Expected: 2 passed (ou 2 skipped).

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/video_sources/webcam.py tests/integration/test_webcam_source.py
git commit -m "feat(infra): WebcamVideoSource adapter"
```

---

## Task 13: Infrastructure — MediapipeFaceDetector (adapter)

**Files:**
- Create: `src/driver_fatigue/infrastructure/detectors/mediapipe_detector.py`
- Create: `tests/integration/test_mediapipe_detector.py`

**Nota sobre índices MediaPipe Face Mesh:**
Os índices abaixo foram extraídos da documentação oficial do MediaPipe (constantes `FACEMESH_LEFT_EYE`, `FACEMESH_LIPS`, `FACEMESH_FACE_OVAL`) e ordenados semanticamente. Para EAR/MAR usamos um subconjunto semântico (6 olhos / 12 boca) equivalente ao esquema do dlib, escolhidos nas posições cardinais.

```python
# 6 pontos por olho (canto ext, topo-ext, topo-int, canto int, base-int, base-ext)
LEFT_EYE_EAR_INDICES  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_EAR_INDICES = [362, 385, 387, 263, 373, 380]

# Íris (refine_landmarks=True habilita índices 468-477)
LEFT_IRIS_INDICES  = [468, 469, 470, 471, 472]
RIGHT_IRIS_INDICES = [473, 474, 475, 476, 477]

# 12 pontos do contorno externo da boca (ordem horária começando no canto esquerdo)
MOUTH_OUTER_MAR_INDICES = [61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91]
# 8 pontos do contorno interno
MOUTH_INNER_INDICES = [78, 81, 13, 311, 308, 402, 14, 178]

# 36 pontos do face oval (subamostrado da FACEMESH_FACE_OVAL)
FACE_OVAL_INDICES = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]
```

- [ ] **Step 1: Escrever smoke test**

`tests/integration/test_mediapipe_detector.py`:

```python
import cv2
import pytest

from driver_fatigue.domain.entities import Frame
from driver_fatigue.infrastructure.detectors.mediapipe_detector import (
    MediapipeFaceDetector,
)


@pytest.fixture
def frames_from_test_video(test_video_path):
    cap = cv2.VideoCapture(str(test_video_path))
    assert cap.isOpened()
    frames = []
    for i in range(10):
        ok, img = cap.read()
        if not ok:
            break
        frames.append(Frame(image=img, timestamp=float(i), index=i))
    cap.release()
    return frames


class TestMediapipeFaceDetector:
    def test_detects_at_least_one_face_in_sample(self, frames_from_test_video):
        det = MediapipeFaceDetector()
        try:
            detections = [det.detect(f) for f in frames_from_test_video]
        finally:
            det.close()
        # Ao menos metade dos frames devem retornar ≥1 face
        hits = sum(1 for d in detections if d)
        assert hits >= len(frames_from_test_video) // 2

    def test_returned_landmarks_have_expected_arities(self, frames_from_test_video):
        det = MediapipeFaceDetector()
        try:
            for f in frames_from_test_video:
                for lm in det.detect(f):
                    assert len(lm.left_eye_contour) == 6
                    assert len(lm.right_eye_contour) == 6
                    assert len(lm.mouth_outer) == 12
                    assert len(lm.mouth_inner) == 8
                    assert len(lm.face_oval) == 36
                    if lm.left_iris is not None:
                        assert len(lm.left_iris) == 5
                        assert len(lm.right_iris) == 5
                    return  # basta verificar o primeiro rosto encontrado
        finally:
            det.close()
        pytest.fail("nenhum rosto detectado — teste inconclusivo")
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_mediapipe_detector.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar mediapipe_detector.py**

`src/driver_fatigue/infrastructure/detectors/mediapipe_detector.py`:

```python
from __future__ import annotations

import cv2
import mediapipe as mp

from driver_fatigue.domain.entities import FaceLandmarks, Frame, Point

LEFT_EYE_EAR_INDICES  = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_EAR_INDICES = [362, 385, 387, 263, 373, 380]
LEFT_IRIS_INDICES  = [468, 469, 470, 471, 472]
RIGHT_IRIS_INDICES = [473, 474, 475, 476, 477]
MOUTH_OUTER_MAR_INDICES = [61, 40, 37, 0, 267, 270, 291, 321, 314, 17, 84, 91]
MOUTH_INNER_INDICES = [78, 81, 13, 311, 308, 402, 14, 178]
FACE_OVAL_INDICES = [
    10, 338, 297, 332, 284, 251, 389, 356, 454, 323, 361, 288,
    397, 365, 379, 378, 400, 377, 152, 148, 176, 149, 150, 136,
    172, 58, 132, 93, 234, 127, 162, 21, 54, 103, 67, 109,
]


class MediapipeFaceDetector:
    def __init__(
        self,
        max_faces: int = 1,
        min_detection_confidence: float = 0.5,
        min_tracking_confidence: float = 0.5,
    ) -> None:
        self._face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=max_faces,
            refine_landmarks=True,  # habilita íris
            min_detection_confidence=min_detection_confidence,
            min_tracking_confidence=min_tracking_confidence,
        )

    def detect(self, frame: Frame) -> list[FaceLandmarks]:
        rgb = cv2.cvtColor(frame.image, cv2.COLOR_BGR2RGB)
        rgb.flags.writeable = False
        results = self._face_mesh.process(rgb)
        if not results.multi_face_landmarks:
            return []

        h, w = frame.image.shape[:2]
        out: list[FaceLandmarks] = []
        for face in results.multi_face_landmarks:
            pts = [Point(x=lm.x * w, y=lm.y * h) for lm in face.landmark]
            out.append(FaceLandmarks(
                left_eye_contour=tuple(pts[i] for i in LEFT_EYE_EAR_INDICES),
                right_eye_contour=tuple(pts[i] for i in RIGHT_EYE_EAR_INDICES),
                left_iris=tuple(pts[i] for i in LEFT_IRIS_INDICES) if len(pts) > 472 else None,
                right_iris=tuple(pts[i] for i in RIGHT_IRIS_INDICES) if len(pts) > 477 else None,
                mouth_outer=tuple(pts[i] for i in MOUTH_OUTER_MAR_INDICES),
                mouth_inner=tuple(pts[i] for i in MOUTH_INNER_INDICES),
                face_oval=tuple(pts[i] for i in FACE_OVAL_INDICES),
            ))
        return out

    def close(self) -> None:
        self._face_mesh.close()
```

- [ ] **Step 4: Rodar teste**

Run: `pytest tests/integration/test_mediapipe_detector.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/detectors/mediapipe_detector.py tests/integration/test_mediapipe_detector.py
git commit -m "feat(infra): MediapipeFaceDetector com smoke test"
```

---

## Task 14: Infrastructure — rendering/curves (Catmull-Rom)

**Files:**
- Create: `src/driver_fatigue/infrastructure/rendering/curves.py`
- Create: `tests/integration/test_rendering_curves.py`

- [ ] **Step 1: Escrever testes**

`tests/integration/test_rendering_curves.py`:

```python
import numpy as np
import pytest

from driver_fatigue.domain.entities import Point
from driver_fatigue.infrastructure.rendering.curves import catmull_rom_closed


class TestCatmullRomClosed:
    def test_interpolates_more_points_than_input(self):
        pts = [Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)]
        out = catmull_rom_closed(pts, steps_per_segment=10)
        assert len(out) > len(pts)
        assert len(out) == len(pts) * 10

    def test_returns_float32_array_shape_N_2(self):
        pts = [Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)]
        out = catmull_rom_closed(pts, steps_per_segment=5)
        assert out.dtype == np.float32
        assert out.shape[1] == 2

    def test_passes_through_input_points(self):
        pts = [Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)]
        out = catmull_rom_closed(pts, steps_per_segment=10)
        for p in pts:
            # cada ponto de entrada deve estar muito próximo de algum ponto de saída
            d = np.min(np.linalg.norm(out - np.array([p.x, p.y]), axis=1))
            assert d < 1e-4

    def test_steps_per_segment_zero_returns_just_input(self):
        pts = [Point(0, 0), Point(1, 0), Point(1, 1), Point(0, 1)]
        out = catmull_rom_closed(pts, steps_per_segment=0)
        assert len(out) == len(pts)

    def test_requires_at_least_four_points(self):
        with pytest.raises(ValueError):
            catmull_rom_closed([Point(0, 0), Point(1, 1), Point(2, 0)], steps_per_segment=5)
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_rendering_curves.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar curves.py**

`src/driver_fatigue/infrastructure/rendering/curves.py`:

```python
from __future__ import annotations

from typing import Sequence

import numpy as np

from driver_fatigue.domain.entities import Point


def catmull_rom_closed(
    points: Sequence[Point],
    steps_per_segment: int = 20,
) -> np.ndarray:
    """Catmull-Rom spline fechado passando por todos os pontos.

    Retorna array shape (N*steps_per_segment, 2) em float32.
    Se steps_per_segment==0, retorna apenas os pontos originais.
    """
    if len(points) < 4:
        raise ValueError("Catmull-Rom requer ao menos 4 pontos")

    arr = np.array([[p.x, p.y] for p in points], dtype=np.float32)
    if steps_per_segment == 0:
        return arr

    n = len(arr)
    out_segments = []
    for i in range(n):
        p0 = arr[(i - 1) % n]
        p1 = arr[i]
        p2 = arr[(i + 1) % n]
        p3 = arr[(i + 2) % n]
        # t em [0, 1): steps_per_segment pontos por segmento p1→p2
        t = np.linspace(0.0, 1.0, steps_per_segment, endpoint=False, dtype=np.float32)
        t2 = t * t
        t3 = t2 * t
        seg = 0.5 * (
            (2 * p1)
            + (-p0 + p2) * t[:, None]
            + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2[:, None]
            + (-p0 + 3 * p1 - 3 * p2 + p3) * t3[:, None]
        )
        out_segments.append(seg.astype(np.float32))
    return np.concatenate(out_segments, axis=0)
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_rendering_curves.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/rendering/curves.py tests/integration/test_rendering_curves.py
git commit -m "feat(rendering): Catmull-Rom spline fechado"
```

---

## Task 15: Infrastructure — rendering/overlay, glow, hud

**Files:**
- Create: `src/driver_fatigue/infrastructure/rendering/overlay.py`
- Create: `src/driver_fatigue/infrastructure/rendering/glow.py`
- Create: `src/driver_fatigue/infrastructure/rendering/hud.py`
- Create: `tests/integration/test_rendering_helpers.py`

Esses helpers recebem `np.ndarray` (imagem BGR) e o modificam/retornam modificado. Testes verificam mudança de pixels, não aparência.

- [ ] **Step 1: Escrever testes**

`tests/integration/test_rendering_helpers.py`:

```python
import numpy as np

from driver_fatigue.infrastructure.rendering.glow import apply_glow
from driver_fatigue.infrastructure.rendering.hud import draw_hud
from driver_fatigue.infrastructure.rendering.overlay import draw_filled_overlay


def _blank(h=100, w=200):
    return np.zeros((h, w, 3), dtype=np.uint8)


class TestDrawFilledOverlay:
    def test_paints_region(self):
        img = _blank()
        polygon = np.array([[50, 30], [100, 30], [100, 60], [50, 60]], dtype=np.int32)
        out = draw_filled_overlay(img, polygon, color=(0, 255, 0), alpha=0.5)
        # pelo menos um pixel verde (G>0) dentro do polígono
        assert out[45, 75, 1] > 0

    def test_does_not_modify_input(self):
        img = _blank()
        original = img.copy()
        polygon = np.array([[10, 10], [20, 10], [20, 20], [10, 20]], dtype=np.int32)
        _ = draw_filled_overlay(img, polygon, color=(255, 0, 0), alpha=0.5)
        assert np.array_equal(img, original)


class TestApplyGlow:
    def test_glow_increases_brightness_around_line(self):
        img = _blank()
        img[50, 100:110] = (255, 255, 255)
        out = apply_glow(img, sigma=5)
        assert out[52, 105, 0] > 0  # borrado para baixo


class TestDrawHud:
    def test_hud_writes_pixels_in_bottom_region(self):
        img = _blank(h=300, w=400)
        out = draw_hud(
            img,
            ear=0.22, mar=0.35, consecutive=8, fps=29.5, severity="warning",
            max_consecutive=20,
        )
        # HUD fica nos últimos ~60px — alguns pixels não-pretos lá
        assert out[250:, :, :].sum() > 0
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_rendering_helpers.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar overlay.py**

`src/driver_fatigue/infrastructure/rendering/overlay.py`:

```python
from __future__ import annotations

import cv2
import numpy as np


def draw_filled_overlay(
    image: np.ndarray,
    polygon: np.ndarray,
    color: tuple[int, int, int],
    alpha: float,
) -> np.ndarray:
    """Desenha polígono preenchido sobre uma cópia de `image` com transparência alpha."""
    layer = image.copy()
    cv2.fillPoly(layer, [polygon.astype(np.int32)], color, lineType=cv2.LINE_AA)
    return cv2.addWeighted(layer, alpha, image, 1.0 - alpha, 0)
```

- [ ] **Step 4: Implementar glow.py**

`src/driver_fatigue/infrastructure/rendering/glow.py`:

```python
from __future__ import annotations

import cv2
import numpy as np


def apply_glow(image: np.ndarray, sigma: int) -> np.ndarray:
    """Retorna `image` com efeito glow aditivo sobre pixels brilhantes."""
    if sigma <= 0:
        return image
    k = sigma * 2 + 1
    blurred = cv2.GaussianBlur(image, (k, k), sigma)
    return cv2.add(image, blurred)
```

- [ ] **Step 5: Implementar hud.py**

`src/driver_fatigue/infrastructure/rendering/hud.py`:

```python
from __future__ import annotations

import cv2
import numpy as np

_COLOR_BY_SEVERITY = {
    "normal": (200, 200, 200),
    "warning": (0, 200, 255),
    "alert": (50, 50, 255),
}


def draw_hud(
    image: np.ndarray,
    ear: float,
    mar: float,
    consecutive: int,
    fps: float,
    severity: str,
    max_consecutive: int,
) -> np.ndarray:
    """Desenha painel inferior translúcido com métricas."""
    out = image.copy()
    h, w = out.shape[:2]
    panel_h = 60
    panel = np.zeros_like(out)
    cv2.rectangle(panel, (0, h - panel_h), (w, h), (40, 40, 40), -1)
    blended = cv2.addWeighted(panel, 0.6, out, 1.0, 0)

    color = _COLOR_BY_SEVERITY.get(severity, (200, 200, 200))
    font = cv2.FONT_HERSHEY_DUPLEX
    cv2.putText(blended, f"EAR {ear:.2f}", (10, h - 35), font, 0.55, color, 1, cv2.LINE_AA)
    cv2.putText(blended, f"MAR {mar:.2f}", (110, h - 35), font, 0.55, color, 1, cv2.LINE_AA)
    cv2.putText(blended, f"FPS {fps:.1f}", (210, h - 35), font, 0.55, (200, 200, 200), 1, cv2.LINE_AA)
    cv2.putText(blended, severity.upper(), (w - 120, h - 35), font, 0.6, color, 1, cv2.LINE_AA)

    # barra de progresso
    bar_x0, bar_x1 = 10, w - 10
    bar_y = h - 12
    cv2.rectangle(blended, (bar_x0, bar_y), (bar_x1, bar_y + 4), (80, 80, 80), -1)
    ratio = min(1.0, consecutive / max(1, max_consecutive))
    fill_x = int(bar_x0 + (bar_x1 - bar_x0) * ratio)
    cv2.rectangle(blended, (bar_x0, bar_y), (fill_x, bar_y + 4), color, -1)
    return blended
```

- [ ] **Step 6: Rodar testes**

Run: `pytest tests/integration/test_rendering_helpers.py -v`
Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add src/driver_fatigue/infrastructure/rendering tests/integration/test_rendering_helpers.py
git commit -m "feat(rendering): overlay, glow, hud helpers"
```

---

## Task 16: Infrastructure — OpenCvWindowPresenter

**Files:**
- Create: `src/driver_fatigue/infrastructure/presenters/opencv_window.py`
- Create: `tests/integration/test_opencv_presenter.py`

O presenter é difícil de testar em janela real. Criamos **modo headless** opcional (pula `cv2.imshow`) que ainda executa toda a pipeline de desenho — assim validamos resultado em buffer.

- [ ] **Step 1: Escrever testes**

`tests/integration/test_opencv_presenter.py`:

```python
import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.domain.rendering_theme import RenderingTheme
from driver_fatigue.infrastructure.presenters.opencv_window import OpenCvWindowPresenter


def _pts(n, scale=50):
    return tuple(Point(x=float(i * scale / n + 10), y=float(i * scale / n + 10)) for i in range(n))


def _landmarks():
    return FaceLandmarks(
        left_eye_contour=_pts(6), right_eye_contour=_pts(6),
        left_iris=_pts(5), right_iris=_pts(5),
        mouth_outer=_pts(12), mouth_inner=_pts(8),
        face_oval=_pts(36, scale=200),
    )


def _frame():
    return Frame(image=np.zeros((240, 320, 3), dtype=np.uint8), timestamp=0.0, index=0)


class TestOpenCvWindowPresenterHeadless:
    def test_render_produces_non_black_output(self):
        p = OpenCvWindowPresenter(theme=RenderingTheme(), headless=True)
        state = FatigueState(
            ear=0.22, mar=0.35, consecutive_frames=3,
            is_fatigued=False, is_yawning=False, severity="warning",
        )
        p.present(_frame(), [_landmarks()], state)
        assert p.last_rendered is not None
        assert p.last_rendered.sum() > 0

    def test_no_faces_still_renders_hud(self):
        p = OpenCvWindowPresenter(theme=RenderingTheme(), headless=True)
        p.present(_frame(), [], FatigueState.initial())
        assert p.last_rendered is not None
        assert p.last_rendered.sum() > 0

    def test_should_stop_defaults_false_in_headless(self):
        p = OpenCvWindowPresenter(theme=RenderingTheme(), headless=True)
        assert p.should_stop() is False

    def test_close_is_idempotent(self):
        p = OpenCvWindowPresenter(theme=RenderingTheme(), headless=True)
        p.close()
        p.close()
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_opencv_presenter.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar opencv_window.py**

`src/driver_fatigue/infrastructure/presenters/opencv_window.py`:

```python
from __future__ import annotations

import time

import cv2
import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame
from driver_fatigue.domain.rendering_theme import RenderingTheme
from driver_fatigue.infrastructure.rendering.curves import catmull_rom_closed
from driver_fatigue.infrastructure.rendering.glow import apply_glow
from driver_fatigue.infrastructure.rendering.hud import draw_hud
from driver_fatigue.infrastructure.rendering.overlay import draw_filled_overlay

_WINDOW_NAME = "Detector de Fadiga"


class OpenCvWindowPresenter:
    def __init__(
        self,
        theme: RenderingTheme,
        headless: bool = False,
        window_name: str = _WINDOW_NAME,
    ) -> None:
        self._theme = theme
        self._headless = headless
        self._window = window_name
        self._closed = False
        self._stop_requested = False
        self._last_ts: float | None = None
        self._fps_ema: float = 0.0
        self.last_rendered: np.ndarray | None = None

    def _color_for(self, severity: str) -> tuple[int, int, int]:
        if severity == "alert":
            return self._theme.color_alert
        if severity == "warning":
            return self._theme.color_warning
        return self._theme.color_normal

    def _smooth(self, pts) -> np.ndarray:
        return catmull_rom_closed(pts, self._theme.smoothing_steps)

    def _update_fps(self, ts: float) -> float:
        if self._last_ts is not None:
            dt = max(1e-6, ts - self._last_ts)
            inst = 1.0 / dt
            self._fps_ema = 0.9 * self._fps_ema + 0.1 * inst if self._fps_ema else inst
        self._last_ts = ts
        return self._fps_ema

    def present(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        img = frame.image.copy()
        color = self._color_for(state.severity)

        for lm in landmarks_list:
            if self._theme.show_face_oval:
                face_curve = self._smooth(lm.face_oval)
                cv2.polylines(
                    img, [face_curve.astype(np.int32)],
                    isClosed=True, color=color, thickness=1, lineType=cv2.LINE_AA,
                )

            for region in (lm.left_eye_contour, lm.right_eye_contour):
                curve = self._smooth(region)
                img = draw_filled_overlay(img, curve, color, self._theme.overlay_alpha)
                cv2.polylines(
                    img, [curve.astype(np.int32)],
                    isClosed=True, color=color, thickness=2, lineType=cv2.LINE_AA,
                )

            for region in (lm.mouth_outer,):
                curve = self._smooth(region)
                img = draw_filled_overlay(img, curve, color, self._theme.overlay_alpha)
                cv2.polylines(
                    img, [curve.astype(np.int32)],
                    isClosed=True, color=color, thickness=2, lineType=cv2.LINE_AA,
                )

            for iris in (lm.left_iris, lm.right_iris):
                if iris is None:
                    continue
                cx = int(sum(p.x for p in iris) / len(iris))
                cy = int(sum(p.y for p in iris) / len(iris))
                cv2.circle(img, (cx, cy), 4, color, 1, cv2.LINE_AA)
                cv2.circle(img, (cx, cy), 2, color, -1, cv2.LINE_AA)

        if self._theme.glow_enabled:
            img = apply_glow(img, self._theme.glow_sigma)

        if state.severity == "alert":
            # vignette vermelho
            h, w = img.shape[:2]
            vignette = np.zeros_like(img)
            cv2.rectangle(vignette, (0, 0), (w, h), self._theme.color_alert, -1)
            img = cv2.addWeighted(vignette, 0.15, img, 1.0, 0)
            cv2.putText(
                img, "FADIGA DETECTADA",
                (20, 40), cv2.FONT_HERSHEY_DUPLEX, 1.0,
                self._theme.color_alert, 2, cv2.LINE_AA,
            )

        if self._theme.show_hud:
            fps = self._update_fps(frame.timestamp or time.monotonic())
            img = draw_hud(
                img,
                ear=state.ear, mar=state.mar,
                consecutive=state.consecutive_frames,
                fps=fps, severity=state.severity,
                max_consecutive=max(1, state.consecutive_frames + 1),
            )

        self.last_rendered = img

        if not self._headless:
            cv2.imshow(self._window, img)
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                self._stop_requested = True

    def should_stop(self) -> bool:
        return self._stop_requested

    def close(self) -> None:
        if self._closed:
            return
        if not self._headless:
            try:
                cv2.destroyWindow(self._window)
            except cv2.error:
                pass
        self._closed = True
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_opencv_presenter.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/presenters/opencv_window.py tests/integration/test_opencv_presenter.py
git commit -m "feat(infra): OpenCvWindowPresenter com rendering polido e modo headless"
```

---

## Task 17: Infrastructure — LogSink

**Files:**
- Create: `src/driver_fatigue/infrastructure/alert_sinks/log.py`
- Create: `tests/integration/test_log_sink.py`

- [ ] **Step 1: Escrever testes**

`tests/integration/test_log_sink.py`:

```python
import logging

from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.infrastructure.alert_sinks.log import LogSink


class TestLogSink:
    def test_notify_emits_warning_record(self, caplog):
        sink = LogSink()
        event = FatigueEvent(
            timestamp=1.5,
            state=FatigueState(
                ear=0.18, mar=0.2, consecutive_frames=20,
                is_fatigued=True, is_yawning=False, severity="alert",
            ),
            frame_index=100,
        )
        with caplog.at_level(logging.WARNING):
            sink.notify(event)
        assert any("FADIGA" in r.message.upper() for r in caplog.records)

    def test_on_recovery_emits_info(self, caplog):
        sink = LogSink()
        with caplog.at_level(logging.INFO):
            sink.on_recovery(frame_index=200)
        assert any("recup" in r.message.lower() or "recovery" in r.message.lower()
                   for r in caplog.records)
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_log_sink.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar log.py**

`src/driver_fatigue/infrastructure/alert_sinks/log.py`:

```python
from __future__ import annotations

import logging

from driver_fatigue.domain.entities import FatigueEvent

_log = logging.getLogger("driver_fatigue.alerts")


class LogSink:
    def notify(self, event: FatigueEvent) -> None:
        _log.warning(
            "FADIGA detectada | frame=%d ear=%.3f mar=%.3f",
            event.frame_index, event.state.ear, event.state.mar,
        )

    def on_recovery(self, frame_index: int) -> None:
        _log.info("Motorista recuperado | frame=%d", frame_index)
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_log_sink.py -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/alert_sinks/log.py tests/integration/test_log_sink.py
git commit -m "feat(infra): LogSink"
```

---

## Task 18: Infrastructure — SoundSink

**Files:**
- Create: `src/driver_fatigue/infrastructure/alert_sinks/sound.py`
- Create: `tests/integration/test_sound_sink.py`

Teste usa mocks em `pygame.mixer` para não exigir áudio real.

- [ ] **Step 1: Escrever testes**

`tests/integration/test_sound_sink.py`:

```python
from pathlib import Path
from unittest.mock import MagicMock, patch

from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.infrastructure.alert_sinks.sound import SoundSink


def _event():
    return FatigueEvent(
        timestamp=0.0,
        state=FatigueState.initial(),
        frame_index=0,
    )


class TestSoundSink:
    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_notify_starts_playback(self, pygame_mock):
        pygame_mock.mixer.Sound.return_value = MagicMock()
        sink = SoundSink(sound_path=Path("audio/alarm.wav"))
        sink.notify(_event())
        assert pygame_mock.mixer.Sound.return_value.play.called

    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_on_recovery_stops_playback(self, pygame_mock):
        pygame_mock.mixer.Sound.return_value = MagicMock()
        sink = SoundSink(sound_path=Path("audio/alarm.wav"))
        sink.notify(_event())
        sink.on_recovery(frame_index=10)
        assert pygame_mock.mixer.Sound.return_value.stop.called

    @patch("driver_fatigue.infrastructure.alert_sinks.sound.pygame")
    def test_repeated_notify_does_not_restart(self, pygame_mock):
        pygame_mock.mixer.Sound.return_value = MagicMock()
        sink = SoundSink(sound_path=Path("audio/alarm.wav"))
        sink.notify(_event())
        sink.notify(_event())
        assert pygame_mock.mixer.Sound.return_value.play.call_count == 1
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_sound_sink.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar sound.py**

`src/driver_fatigue/infrastructure/alert_sinks/sound.py`:

```python
from __future__ import annotations

from pathlib import Path

import pygame

from driver_fatigue.domain.entities import FatigueEvent


class SoundSink:
    def __init__(self, sound_path: Path, loops: int = -1) -> None:
        if not pygame.mixer.get_init():
            pygame.mixer.init()
        self._sound = pygame.mixer.Sound(str(sound_path))
        self._loops = loops
        self._playing = False

    def notify(self, event: FatigueEvent) -> None:
        if self._playing:
            return
        self._sound.play(loops=self._loops)
        self._playing = True

    def on_recovery(self, frame_index: int) -> None:
        if self._playing:
            self._sound.stop()
            self._playing = False
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_sound_sink.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/alert_sinks/sound.py tests/integration/test_sound_sink.py
git commit -m "feat(infra): SoundSink com prevencao de play duplicado"
```

---

## Task 19: Interfaces — Settings (pydantic-settings)

**Files:**
- Create: `src/driver_fatigue/interfaces/config/settings.py`
- Create: `config/default.yaml`
- Create: `config/example.env`
- Create: `tests/unit/interfaces/__init__.py`
- Create: `tests/unit/interfaces/test_settings.py`

- [ ] **Step 1: Escrever testes**

`tests/unit/interfaces/test_settings.py`:

```python
from pathlib import Path

from driver_fatigue.interfaces.config.settings import AppSettings


class TestAppSettings:
    def test_defaults(self):
        s = AppSettings()
        assert s.source.kind == "webcam"
        assert s.source.index == 0
        assert s.thresholds.ear_threshold == 0.25
        assert s.alarm_sound_path.name == "alarm.wav"

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("DRIVER_FATIGUE_SOURCE__INDEX", "2")
        monkeypatch.setenv("DRIVER_FATIGUE_THRESHOLDS__EAR_THRESHOLD", "0.30")
        s = AppSettings()
        assert s.source.index == 2
        assert s.thresholds.ear_threshold == 0.30

    def test_load_from_yaml(self, tmp_path):
        yaml = tmp_path / "conf.yaml"
        yaml.write_text(
            "thresholds:\n  ear_threshold: 0.22\n  mar_threshold: 0.55\n"
            "source:\n  kind: webcam\n  index: 1\n"
        )
        s = AppSettings.from_yaml(yaml)
        assert s.thresholds.ear_threshold == 0.22
        assert s.source.index == 1
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/unit/interfaces/test_settings.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar settings.py**

`src/driver_fatigue/interfaces/config/settings.py`:

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class SourceSettings(BaseModel):
    kind: Literal["webcam"] = "webcam"
    index: int = 0


class ThresholdsSettings(BaseModel):
    ear_threshold: float = 0.25
    mar_threshold: float = 0.60
    consecutive_frames: int = 20
    warning_ratio: float = 0.85


class ThemeSettings(BaseModel):
    glow_enabled: bool = True
    show_hud: bool = True
    show_face_oval: bool = True
    smoothing_steps: int = 20
    overlay_alpha: float = 0.35


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="DRIVER_FATIGUE_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    source: SourceSettings = Field(default_factory=SourceSettings)
    thresholds: ThresholdsSettings = Field(default_factory=ThresholdsSettings)
    theme: ThemeSettings = Field(default_factory=ThemeSettings)
    alarm_sound_path: Path = Path("audio/alarm.wav")
    headless: bool = False

    @classmethod
    def from_yaml(cls, path: Path) -> "AppSettings":
        data = yaml.safe_load(path.read_text())
        return cls(**(data or {}))
```

- [ ] **Step 4: Criar config/default.yaml e config/example.env**

`config/default.yaml`:

```yaml
source:
  kind: webcam
  index: 0
thresholds:
  ear_threshold: 0.25
  mar_threshold: 0.60
  consecutive_frames: 20
  warning_ratio: 0.85
theme:
  glow_enabled: true
  show_hud: true
  show_face_oval: true
  smoothing_steps: 20
  overlay_alpha: 0.35
alarm_sound_path: audio/alarm.wav
headless: false
```

`config/example.env`:

```
DRIVER_FATIGUE_SOURCE__INDEX=0
DRIVER_FATIGUE_THRESHOLDS__EAR_THRESHOLD=0.25
DRIVER_FATIGUE_THRESHOLDS__MAR_THRESHOLD=0.60
DRIVER_FATIGUE_HEADLESS=false
```

- [ ] **Step 5: Rodar testes**

Run: `pytest tests/unit/interfaces/test_settings.py -v`
Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add src/driver_fatigue/interfaces/config config/default.yaml config/example.env tests/unit/interfaces
git commit -m "feat(interfaces): AppSettings com pydantic-settings e YAML"
```

---

## Task 20: Composition root — bootstrap.py

**Files:**
- Create: `src/driver_fatigue/bootstrap.py`
- Create: `tests/e2e/test_bootstrap_pipeline.py`

- [ ] **Step 1: Escrever teste E2E com FakeVideoSource**

`tests/e2e/test_bootstrap_pipeline.py`:

```python
from pathlib import Path

import cv2
import numpy as np
import pytest

from driver_fatigue.application.ports import VideoSourcePort
from driver_fatigue.application.use_cases.monitor_driver import MonitorDriverUseCase
from driver_fatigue.bootstrap import build_monitor_use_case
from driver_fatigue.domain.entities import Frame
from driver_fatigue.interfaces.config.settings import AppSettings


class FramesFromFile(VideoSourcePort):
    def __init__(self, path: Path, max_frames: int):
        self._cap = cv2.VideoCapture(str(path))
        self._max = max_frames
        self._i = 0
        self._released = False

    def read(self) -> Frame | None:
        if self._i >= self._max:
            return None
        ok, img = self._cap.read()
        if not ok:
            return None
        frame = Frame(image=img, timestamp=float(self._i), index=self._i)
        self._i += 1
        return frame

    def release(self) -> None:
        if not self._released:
            self._cap.release()
            self._released = True


@pytest.mark.timeout(30)
def test_pipeline_processes_test_video_headless(test_video_path):
    settings = AppSettings(headless=True)
    uc: MonitorDriverUseCase = build_monitor_use_case(
        settings=settings,
        source_override=FramesFromFile(test_video_path, max_frames=20),
        sound_override="disabled",  # evita tocar áudio durante teste
    )
    uc.run()  # não deve lançar
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/e2e/test_bootstrap_pipeline.py -v`
Expected: ImportError (bootstrap inexistente).

- [ ] **Step 3: Implementar bootstrap.py**

`src/driver_fatigue/bootstrap.py`:

```python
from __future__ import annotations

from typing import Literal

from driver_fatigue.application.ports import (
    AlertSinkPort,
    FramePresenterPort,
    VideoSourcePort,
)
from driver_fatigue.application.use_cases.detect_fatigue import DetectFatigueUseCase
from driver_fatigue.application.use_cases.monitor_driver import MonitorDriverUseCase
from driver_fatigue.domain.rendering_theme import RenderingTheme
from driver_fatigue.domain.value_objects import FatigueThresholds
from driver_fatigue.infrastructure.alert_sinks.log import LogSink
from driver_fatigue.infrastructure.alert_sinks.sound import SoundSink
from driver_fatigue.infrastructure.detectors.mediapipe_detector import MediapipeFaceDetector
from driver_fatigue.infrastructure.presenters.opencv_window import OpenCvWindowPresenter
from driver_fatigue.infrastructure.video_sources.webcam import WebcamVideoSource
from driver_fatigue.interfaces.config.settings import AppSettings


class _CompositeSink:
    def __init__(self, *sinks: AlertSinkPort) -> None:
        self._sinks = sinks

    def notify(self, event) -> None:
        for s in self._sinks:
            try:
                s.notify(event)
            except Exception:
                import logging
                logging.getLogger("driver_fatigue").exception(
                    "sink %s falhou em notify", type(s).__name__,
                )

    def on_recovery(self, frame_index: int) -> None:
        for s in self._sinks:
            try:
                s.on_recovery(frame_index)
            except Exception:
                import logging
                logging.getLogger("driver_fatigue").exception(
                    "sink %s falhou em on_recovery", type(s).__name__,
                )


def _build_source(settings: AppSettings) -> VideoSourcePort:
    if settings.source.kind == "webcam":
        return WebcamVideoSource(device_index=settings.source.index)
    raise ValueError(f"source.kind {settings.source.kind!r} não suportado na Fase 1")


def _build_presenter(settings: AppSettings) -> FramePresenterPort:
    theme = RenderingTheme(
        glow_enabled=settings.theme.glow_enabled,
        show_hud=settings.theme.show_hud,
        show_face_oval=settings.theme.show_face_oval,
        smoothing_steps=settings.theme.smoothing_steps,
        overlay_alpha=settings.theme.overlay_alpha,
    )
    return OpenCvWindowPresenter(theme=theme, headless=settings.headless)


def _build_sink(
    settings: AppSettings,
    sound_override: Literal["disabled"] | None = None,
) -> AlertSinkPort:
    log_sink = LogSink()
    if sound_override == "disabled":
        return log_sink
    try:
        sound_sink = SoundSink(sound_path=settings.alarm_sound_path)
        return _CompositeSink(sound_sink, log_sink)
    except Exception:
        import logging
        logging.getLogger("driver_fatigue").warning(
            "SoundSink indisponível, usando somente LogSink",
        )
        return log_sink


def build_monitor_use_case(
    settings: AppSettings,
    source_override: VideoSourcePort | None = None,
    sound_override: Literal["disabled"] | None = None,
) -> MonitorDriverUseCase:
    source = source_override if source_override is not None else _build_source(settings)
    detector = MediapipeFaceDetector()
    thresholds = FatigueThresholds(
        ear_threshold=settings.thresholds.ear_threshold,
        mar_threshold=settings.thresholds.mar_threshold,
        consecutive_frames=settings.thresholds.consecutive_frames,
        warning_ratio=settings.thresholds.warning_ratio,
    )
    detect = DetectFatigueUseCase(detector=detector, thresholds=thresholds)
    sink = _build_sink(settings, sound_override=sound_override)
    presenter = _build_presenter(settings)
    return MonitorDriverUseCase(
        source=source, detect=detect, sink=sink, presenter=presenter,
    )
```

- [ ] **Step 4: Instalar pytest-timeout (para o timeout E2E)**

Run: `pip install pytest-timeout`
Alternativa: adicione `pytest-timeout>=2.2` ao `pyproject.toml` em `[project.optional-dependencies].dev`.

- [ ] **Step 5: Rodar teste E2E**

Run: `pytest tests/e2e/test_bootstrap_pipeline.py -v`
Expected: 1 passed.

- [ ] **Step 6: Commit**

```bash
git add src/driver_fatigue/bootstrap.py tests/e2e pyproject.toml
git commit -m "feat: bootstrap composition root + E2E headless com video de teste"
```

---

## Task 21: Interfaces — CLI

**Files:**
- Create: `src/driver_fatigue/interfaces/cli/main.py`
- Create: `tests/integration/test_cli.py`

- [ ] **Step 1: Escrever testes**

`tests/integration/test_cli.py`:

```python
import subprocess
import sys

import pytest


class TestCli:
    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, "-m", "driver_fatigue", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert "--source" in result.stdout
        assert "--headless" in result.stdout

    def test_invalid_source_kind_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, "-m", "driver_fatigue", "run",
             "--source", "banana:0", "--headless"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode != 0
```

- [ ] **Step 2: Criar módulo executável `__main__.py`**

`src/driver_fatigue/__main__.py`:

```python
from driver_fatigue.interfaces.cli.main import main

if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Rodar teste (deve falhar)**

Run: `pytest tests/integration/test_cli.py -v`
Expected: falha por ausência de `main.py`.

- [ ] **Step 4: Implementar CLI**

`src/driver_fatigue/interfaces/cli/main.py`:

```python
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from driver_fatigue.bootstrap import build_monitor_use_case
from driver_fatigue.interfaces.config.settings import AppSettings


def _parse_source(arg: str) -> tuple[str, int]:
    kind, _, value = arg.partition(":")
    if kind != "webcam":
        raise argparse.ArgumentTypeError(
            f"source '{kind}' não suportado na Fase 1 (use 'webcam:N')"
        )
    try:
        return kind, int(value or "0")
    except ValueError as e:
        raise argparse.ArgumentTypeError(str(e))


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driver-fatigue",
        description="Detector de fadiga em motoristas (Clean Architecture).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="inicia detecção")
    run.add_argument("--source", type=_parse_source, default=("webcam", 0),
                     help="fonte de vídeo (ex.: webcam:0)")
    run.add_argument("--config", type=Path, default=None,
                     help="caminho para YAML de configuração")
    run.add_argument("--headless", action="store_true", help="sem janela OpenCV")
    run.add_argument("--verbose", "-v", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    if args.command == "run":
        if args.config and args.config.exists():
            settings = AppSettings.from_yaml(args.config)
        else:
            settings = AppSettings()

        kind, index = args.source
        settings = settings.model_copy(update={
            "source": settings.source.model_copy(update={"kind": kind, "index": index}),
            "headless": args.headless or settings.headless,
        })
        uc = build_monitor_use_case(settings=settings)
        uc.run()
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 5: Rodar testes**

Run: `pytest tests/integration/test_cli.py -v`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
git add src/driver_fatigue/__main__.py src/driver_fatigue/interfaces/cli/main.py tests/integration/test_cli.py
git commit -m "feat(cli): comando driver-fatigue run"
```

---

## Task 22: Remover código legado e atualizar README

**Files:**
- Delete: `src/main.py`
- Delete: `requeriments/requirements.txt` (e possivelmente a pasta)
- Modify: `docs/README.md`

- [ ] **Step 1: Validar que novo ponto de entrada funciona**

Run: `python -m driver_fatigue --help`
Expected: mostra ajuda sem erros.

- [ ] **Step 2: Remover arquivos legados**

```bash
git rm src/main.py
git rm requeriments/requirements.txt
rmdir requeriments 2>/dev/null || true
```

- [ ] **Step 3: Atualizar README**

Editar `docs/README.md` substituindo as seções de instalação e uso por:

```markdown
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
```

- [ ] **Step 4: Rodar suite completa**

Run: `pytest -v`
Expected: todos os testes passam.

Run: `pytest tests/unit/domain/ --cov=src/driver_fatigue/domain --cov-report=term-missing`
Expected: coverage >= 95% no domain.

- [ ] **Step 5: Commit final da Fase 1**

```bash
git add docs/README.md
git rm src/main.py requeriments/requirements.txt 2>/dev/null
git commit -m "chore: remove codigo legado apos refactor Fase 1

Substitui src/main.py monolitico por src/driver_fatigue/ em Clean Architecture.
Substitui requirements.txt por pyproject.toml.
Ponto de entrada: 'driver-fatigue run' ou 'python -m driver_fatigue run'."
```

---

## Critérios de aceitação da Fase 1

- [ ] `python -m driver_fatigue run --source webcam:0` roda e reproduz o comportamento original
- [ ] Visualização visivelmente mais rica: curvas suaves, overlays translúcidos, glow, HUD, estados reativos (normal/warning/alert)
- [ ] Íris rastreada quando MediaPipe retorna (olhos com círculos de íris)
- [ ] `pytest -v` — todos os testes passam
- [ ] `pytest tests/unit/domain/ --cov=src/driver_fatigue/domain` — cobertura >= 95%
- [ ] Smoke test `tests/integration/test_mediapipe_detector.py` passa (MediaPipe detecta faces em `assets/test_sonolency.mp4`)
- [ ] E2E `tests/e2e/test_bootstrap_pipeline.py` processa o vídeo completo sem erros
- [ ] `src/main.py` e `requeriments/` removidos
- [ ] `pyproject.toml` no lugar de `requirements.txt`
