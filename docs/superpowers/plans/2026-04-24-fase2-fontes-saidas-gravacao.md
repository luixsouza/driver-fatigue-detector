# Fase 2 — Múltiplas Fontes, Saídas e Gravação — Plano de Implementação

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Estender a ubiquidade do detector adicionando fontes (RTSP, arquivo), sinks de rede (HTTP webhook, MQTT), gravação MP4 com overlay e extraindo `FrameRenderer` compartilhado entre janela e gravador.

**Architecture:** Infrastructure-only (nenhuma mudança em Domain/Application). O `FrameRenderer` vira a única fonte de verdade para renderização; `OpenCvWindowPresenter` e `FileRecorderPresenter` delegam para ele. Sinks compostos via `CompositeSink` público. CLI e `AppSettings` ganham novos enums e validação cruzada.

**Tech Stack:** OpenCV (VideoCapture/VideoWriter), httpx (HTTP), paho-mqtt (MQTT), pydantic-settings, pytest + respx (mock httpx).

**Spec:** `docs/superpowers/specs/2026-04-24-fase2-fontes-saidas-gravacao-design.md`

---

## Arquivos ao final da Fase 2

**Novos:**
```
src/driver_fatigue/infrastructure/
├── rendering/
│   └── renderer.py                       # [novo] FrameRenderer
├── presenters/
│   ├── headless.py                       # [novo] HeadlessPresenter
│   ├── file_recorder.py                  # [novo] FileRecorderPresenter
│   └── composite.py                      # [novo] CompositePresenter
├── video_sources/
│   ├── file.py                           # [novo] FileVideoSource
│   └── rtsp.py                           # [novo] RtspVideoSource
└── alert_sinks/
    ├── composite.py                      # [novo] CompositeSink
    ├── http_webhook.py                   # [novo] HttpWebhookSink
    └── mqtt.py                           # [novo] MqttSink

tests/integration/
├── test_frame_renderer.py                # [novo]
├── test_headless_presenter.py            # [novo]
├── test_file_recorder.py                 # [novo]
├── test_composite_presenter.py           # [novo]
├── test_file_video_source.py             # [novo]
├── test_rtsp_video_source.py             # [novo]
├── test_http_webhook_sink.py             # [novo]
├── test_mqtt_sink.py                     # [novo]
└── test_composite_sink.py                # [novo]
```

**Modificados:**
```
pyproject.toml                            # add httpx, paho-mqtt, respx
src/driver_fatigue/
├── infrastructure/presenters/opencv_window.py  # delega a FrameRenderer; remove headless arg
├── interfaces/config/settings.py               # novos blocos/campos + model_validator
├── interfaces/cli/main.py                      # aceita file:/rtsp:, --sinks, --record
└── bootstrap.py                                # novo wiring; remove _CompositeSink privado

tests/integration/test_opencv_presenter.py      # ajusta para novo construtor
tests/unit/interfaces/test_settings.py          # novos testes de validação cruzada
tests/integration/test_cli.py                   # testa novos formatos de --source
tests/e2e/test_bootstrap_pipeline.py            # extensão com --record
docs/README.md                                  # exemplos de uso Fase 2
config/default.yaml                             # exemplos de http/mqtt/recording
config/example.env                              # novas env vars
```

---

## Task 1: Adicionar dependências

**Files:**
- Modify: `pyproject.toml`

- [ ] **Step 1: Atualizar pyproject.toml**

Localize o bloco `dependencies` e adicione `httpx>=0.27` e `paho-mqtt>=2.0`. No bloco `[project.optional-dependencies].dev`, adicione `respx>=0.21`.

Resultado esperado:

```toml
dependencies = [
    "opencv-python>=4.9",
    "mediapipe>=0.10.9",
    "numpy>=1.26",
    "pygame>=2.5",
    "pydantic>=2.6",
    "pydantic-settings>=2.2",
    "pyyaml>=6.0",
    "httpx>=0.27",
    "paho-mqtt>=2.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0",
    "pytest-cov>=4.1",
    "pytest-timeout>=2.2",
    "respx>=0.21",
    "ruff>=0.3",
]
```

- [ ] **Step 2: Instalar**

Run: `pip install -e ".[dev]"`
Expected: httpx, paho-mqtt, respx instalados sem erros.

- [ ] **Step 3: Commit**

```bash
git add pyproject.toml
git commit -m "chore: adiciona httpx, paho-mqtt, respx para Fase 2"
```

---

## Task 2: Extrair FrameRenderer de OpenCvWindowPresenter

**Files:**
- Create: `src/driver_fatigue/infrastructure/rendering/renderer.py`
- Create: `tests/integration/test_frame_renderer.py`

Motivo: o renderer precisa ser reusado pelo `FileRecorderPresenter` sem depender de janela. Extraímos a lógica pura `(frame, landmarks, state) -> np.ndarray`.

- [ ] **Step 1: Escrever teste**

`tests/integration/test_frame_renderer.py`:

```python
import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.domain.rendering_theme import RenderingTheme
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer


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


class TestFrameRenderer:
    def test_render_returns_numpy_array(self):
        r = FrameRenderer(theme=RenderingTheme())
        out = r.render(_frame(), [_landmarks()], FatigueState.initial())
        assert isinstance(out, np.ndarray)
        assert out.shape == (240, 320, 3)
        assert out.dtype == np.uint8

    def test_render_produces_non_black_output_with_landmarks(self):
        r = FrameRenderer(theme=RenderingTheme())
        state = FatigueState(
            ear=0.22, mar=0.35, consecutive_frames=3,
            is_fatigued=False, is_yawning=False, severity="warning",
        )
        out = r.render(_frame(), [_landmarks()], state)
        assert out.sum() > 0

    def test_render_no_faces_still_renders_hud(self):
        r = FrameRenderer(theme=RenderingTheme())
        out = r.render(_frame(), [], FatigueState.initial())
        assert out.sum() > 0  # HUD pinta alguns pixels

    def test_render_alert_adds_vignette(self):
        r_normal = FrameRenderer(theme=RenderingTheme())
        state_normal = FatigueState.initial()
        r_alert = FrameRenderer(theme=RenderingTheme())
        state_alert = FatigueState(
            ear=0.1, mar=0.1, consecutive_frames=30,
            is_fatigued=True, is_yawning=False, severity="alert",
        )
        out_normal = r_normal.render(_frame(), [_landmarks()], state_normal)
        out_alert = r_alert.render(_frame(), [_landmarks()], state_alert)
        # vignette vermelho adiciona canal R no topo-esq (pixel pouco tocado pelo resto)
        assert out_alert[5, 5, 2] > out_normal[5, 5, 2]

    def test_render_does_not_mutate_input_frame(self):
        r = FrameRenderer(theme=RenderingTheme())
        frame = _frame()
        original = frame.image.copy()
        _ = r.render(frame, [_landmarks()], FatigueState.initial())
        assert np.array_equal(frame.image, original)
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_frame_renderer.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar**

`src/driver_fatigue/infrastructure/rendering/renderer.py`:

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


class FrameRenderer:
    """Produz o frame com overlay completo. Sem efeitos colaterais externos."""

    def __init__(self, theme: RenderingTheme) -> None:
        self._theme = theme
        self._last_ts: float | None = None
        self._fps_ema: float = 0.0

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

    def render(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> np.ndarray:
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

        return img
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_frame_renderer.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/rendering/renderer.py tests/integration/test_frame_renderer.py
git commit -m "feat(rendering): extrai FrameRenderer para reuso entre janela e gravador"
```

---

## Task 3: Refatorar OpenCvWindowPresenter para usar FrameRenderer

**Files:**
- Modify: `src/driver_fatigue/infrastructure/presenters/opencv_window.py`
- Modify: `tests/integration/test_opencv_presenter.py`

Objetivo: presenter fica minúsculo, só aplica display. O modo `headless` sai daqui e vira `HeadlessPresenter` separado (Task 4).

- [ ] **Step 1: Atualizar testes**

Substitua o conteúdo completo de `tests/integration/test_opencv_presenter.py` por:

```python
from unittest.mock import MagicMock, patch

import numpy as np

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.domain.rendering_theme import RenderingTheme
from driver_fatigue.infrastructure.presenters.opencv_window import OpenCvWindowPresenter
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer


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


class TestOpenCvWindowPresenter:
    @patch("driver_fatigue.infrastructure.presenters.opencv_window.cv2")
    def test_present_calls_imshow_with_rendered_frame(self, cv2_mock):
        cv2_mock.waitKey.return_value = 0
        renderer = FrameRenderer(theme=RenderingTheme())
        p = OpenCvWindowPresenter(renderer=renderer)
        p.present(_frame(), [_landmarks()], FatigueState.initial())
        assert cv2_mock.imshow.called
        call_args = cv2_mock.imshow.call_args
        assert call_args.args[0]  # window name
        assert isinstance(call_args.args[1], np.ndarray)

    @patch("driver_fatigue.infrastructure.presenters.opencv_window.cv2")
    def test_q_key_requests_stop(self, cv2_mock):
        cv2_mock.waitKey.return_value = ord('q')
        renderer = FrameRenderer(theme=RenderingTheme())
        p = OpenCvWindowPresenter(renderer=renderer)
        p.present(_frame(), [], FatigueState.initial())
        assert p.should_stop() is True

    @patch("driver_fatigue.infrastructure.presenters.opencv_window.cv2")
    def test_close_destroys_window(self, cv2_mock):
        cv2_mock.waitKey.return_value = 0
        renderer = FrameRenderer(theme=RenderingTheme())
        p = OpenCvWindowPresenter(renderer=renderer)
        p.close()
        assert cv2_mock.destroyWindow.called

    @patch("driver_fatigue.infrastructure.presenters.opencv_window.cv2")
    def test_close_is_idempotent(self, cv2_mock):
        cv2_mock.waitKey.return_value = 0
        renderer = FrameRenderer(theme=RenderingTheme())
        p = OpenCvWindowPresenter(renderer=renderer)
        p.close()
        p.close()
        assert cv2_mock.destroyWindow.call_count == 1
```

- [ ] **Step 2: Reescrever presenter**

Substitua o conteúdo completo de `src/driver_fatigue/infrastructure/presenters/opencv_window.py` por:

```python
from __future__ import annotations

import cv2

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer

_WINDOW_NAME = "Detector de Fadiga"


class OpenCvWindowPresenter:
    """Presenter que mostra o frame renderizado em uma janela OpenCV."""

    def __init__(
        self,
        renderer: FrameRenderer,
        window_name: str = _WINDOW_NAME,
    ) -> None:
        self._renderer = renderer
        self._window = window_name
        self._closed = False
        self._stop_requested = False

    def present(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        img = self._renderer.render(frame, landmarks_list, state)
        cv2.imshow(self._window, img)
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            self._stop_requested = True

    def should_stop(self) -> bool:
        return self._stop_requested

    def close(self) -> None:
        if self._closed:
            return
        try:
            cv2.destroyWindow(self._window)
        except cv2.error:
            pass
        self._closed = True
```

- [ ] **Step 3: Rodar testes**

Run: `pytest tests/integration/test_opencv_presenter.py -v`
Expected: 4 passed.

- [ ] **Step 4: Commit**

```bash
git add src/driver_fatigue/infrastructure/presenters/opencv_window.py tests/integration/test_opencv_presenter.py
git commit -m "refactor(presenter): OpenCvWindowPresenter delega renderizacao ao FrameRenderer"
```

---

## Task 4: HeadlessPresenter

**Files:**
- Create: `src/driver_fatigue/infrastructure/presenters/headless.py`
- Create: `tests/integration/test_headless_presenter.py`

- [ ] **Step 1: Escrever teste**

`tests/integration/test_headless_presenter.py`:

```python
import numpy as np

from driver_fatigue.domain.entities import FatigueState, Frame
from driver_fatigue.infrastructure.presenters.headless import HeadlessPresenter


def _frame():
    return Frame(image=np.zeros((10, 10, 3), dtype=np.uint8), timestamp=0.0, index=0)


class TestHeadlessPresenter:
    def test_present_is_noop(self):
        p = HeadlessPresenter()
        p.present(_frame(), [], FatigueState.initial())  # não levanta

    def test_should_stop_defaults_false(self):
        p = HeadlessPresenter()
        assert p.should_stop() is False

    def test_request_stop_method(self):
        p = HeadlessPresenter()
        p.request_stop()
        assert p.should_stop() is True

    def test_close_is_idempotent(self):
        p = HeadlessPresenter()
        p.close()
        p.close()
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_headless_presenter.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar**

`src/driver_fatigue/infrastructure/presenters/headless.py`:

```python
from __future__ import annotations

import signal

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame


class HeadlessPresenter:
    """Presenter no-op para modo servidor: não desenha, apenas captura SIGINT."""

    def __init__(self, install_signal_handler: bool = True) -> None:
        self._stop_requested = False
        if install_signal_handler:
            try:
                signal.signal(signal.SIGINT, self._on_signal)
            except (ValueError, OSError):
                # signal.signal falha fora do main thread; OK em testes
                pass

    def _on_signal(self, signum, frame) -> None:
        self._stop_requested = True

    def present(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        pass

    def request_stop(self) -> None:
        self._stop_requested = True

    def should_stop(self) -> bool:
        return self._stop_requested

    def close(self) -> None:
        pass
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_headless_presenter.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/presenters/headless.py tests/integration/test_headless_presenter.py
git commit -m "feat(presenter): HeadlessPresenter para modo servidor"
```

---

## Task 5: FileRecorderPresenter

**Files:**
- Create: `src/driver_fatigue/infrastructure/presenters/file_recorder.py`
- Create: `tests/integration/test_file_recorder.py`

- [ ] **Step 1: Escrever teste**

`tests/integration/test_file_recorder.py`:

```python
from pathlib import Path

import cv2
import numpy as np
import pytest

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame, Point
from driver_fatigue.domain.rendering_theme import RenderingTheme
from driver_fatigue.infrastructure.presenters.file_recorder import FileRecorderPresenter
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer


def _pts(n, scale=30):
    return tuple(Point(x=float(i * scale / n + 5), y=float(i * scale / n + 5)) for i in range(n))


def _landmarks():
    return FaceLandmarks(
        left_eye_contour=_pts(6), right_eye_contour=_pts(6),
        left_iris=None, right_iris=None,
        mouth_outer=_pts(12), mouth_inner=_pts(8),
        face_oval=_pts(36, scale=100),
    )


class TestFileRecorderPresenter:
    def test_records_frames_to_mp4(self, tmp_path: Path):
        out = tmp_path / "rec.mp4"
        renderer = FrameRenderer(theme=RenderingTheme(glow_enabled=False))
        p = FileRecorderPresenter(renderer=renderer, output_path=out, fps=10)
        try:
            for i in range(5):
                frame = Frame(
                    image=np.zeros((120, 160, 3), dtype=np.uint8),
                    timestamp=float(i), index=i,
                )
                p.present(frame, [_landmarks()], FatigueState.initial())
        finally:
            p.close()

        assert out.exists()
        cap = cv2.VideoCapture(str(out))
        try:
            count = 0
            while True:
                ok, _ = cap.read()
                if not ok:
                    break
                count += 1
            assert count >= 5
        finally:
            cap.release()

    def test_close_before_present_does_nothing(self, tmp_path: Path):
        out = tmp_path / "empty.mp4"
        renderer = FrameRenderer(theme=RenderingTheme())
        p = FileRecorderPresenter(renderer=renderer, output_path=out, fps=10)
        p.close()  # nunca abriu — não deve falhar
        assert not out.exists()

    def test_should_stop_always_false(self, tmp_path: Path):
        renderer = FrameRenderer(theme=RenderingTheme())
        p = FileRecorderPresenter(
            renderer=renderer, output_path=tmp_path / "x.mp4", fps=10,
        )
        assert p.should_stop() is False
        p.close()
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_file_recorder.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar**

`src/driver_fatigue/infrastructure/presenters/file_recorder.py`:

```python
from __future__ import annotations

import logging
from pathlib import Path

import cv2

from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer

_log = logging.getLogger("driver_fatigue.recorder")


class FileRecorderPresenter:
    """Grava MP4 com overlay. Inicializa o writer no primeiro present() (shape conhecido)."""

    def __init__(
        self,
        renderer: FrameRenderer,
        output_path: Path,
        fps: int = 30,
        codec: str = "mp4v",
    ) -> None:
        self._renderer = renderer
        self._output_path = Path(output_path)
        self._fps = fps
        self._codec = codec
        self._writer: cv2.VideoWriter | None = None
        self._disabled = False
        self._closed = False

    def present(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        if self._disabled:
            return
        rendered = self._renderer.render(frame, landmarks_list, state)
        if self._writer is None:
            h, w = rendered.shape[:2]
            fourcc = cv2.VideoWriter_fourcc(*self._codec)
            self._output_path.parent.mkdir(parents=True, exist_ok=True)
            self._writer = cv2.VideoWriter(
                str(self._output_path), fourcc, self._fps, (w, h),
            )
            if not self._writer.isOpened():
                _log.warning(
                    "VideoWriter falhou em abrir %s com codec %s; gravacao desativada",
                    self._output_path, self._codec,
                )
                self._writer = None
                self._disabled = True
                return
        self._writer.write(rendered)

    def should_stop(self) -> bool:
        return False

    def close(self) -> None:
        if self._closed:
            return
        if self._writer is not None:
            self._writer.release()
            self._writer = None
        self._closed = True
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_file_recorder.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/presenters/file_recorder.py tests/integration/test_file_recorder.py
git commit -m "feat(presenter): FileRecorderPresenter grava MP4 com overlay"
```

---

## Task 6: CompositePresenter

**Files:**
- Create: `src/driver_fatigue/infrastructure/presenters/composite.py`
- Create: `tests/integration/test_composite_presenter.py`

- [ ] **Step 1: Escrever teste**

`tests/integration/test_composite_presenter.py`:

```python
import numpy as np

from driver_fatigue.domain.entities import FatigueState, Frame
from driver_fatigue.infrastructure.presenters.composite import CompositePresenter


def _frame():
    return Frame(image=np.zeros((10, 10, 3), dtype=np.uint8), timestamp=0.0, index=0)


class SpyPresenter:
    def __init__(self, stop: bool = False, raise_on_close: bool = False):
        self.presented = 0
        self.closed = False
        self._stop = stop
        self._raise = raise_on_close

    def present(self, frame, lm, state):
        self.presented += 1

    def should_stop(self):
        return self._stop

    def close(self):
        self.closed = True
        if self._raise:
            raise RuntimeError("boom")


class TestCompositePresenter:
    def test_present_calls_all(self):
        a, b = SpyPresenter(), SpyPresenter()
        c = CompositePresenter(a, b)
        c.present(_frame(), [], FatigueState.initial())
        assert a.presented == 1 and b.presented == 1

    def test_should_stop_is_or(self):
        a = SpyPresenter(stop=False)
        b = SpyPresenter(stop=True)
        c = CompositePresenter(a, b)
        assert c.should_stop() is True

    def test_close_propagates_even_if_one_raises(self):
        a = SpyPresenter(raise_on_close=True)
        b = SpyPresenter()
        c = CompositePresenter(a, b)
        c.close()
        assert a.closed is True and b.closed is True
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_composite_presenter.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar**

`src/driver_fatigue/infrastructure/presenters/composite.py`:

```python
from __future__ import annotations

import logging

from driver_fatigue.application.ports import FramePresenterPort
from driver_fatigue.domain.entities import FaceLandmarks, FatigueState, Frame

_log = logging.getLogger("driver_fatigue.presenters")


class CompositePresenter:
    """Fan-out para múltiplos presenters. Tolerante a falhas em close."""

    def __init__(self, *presenters: FramePresenterPort) -> None:
        self._presenters = presenters

    def present(
        self,
        frame: Frame,
        landmarks_list: list[FaceLandmarks],
        state: FatigueState,
    ) -> None:
        for p in self._presenters:
            p.present(frame, landmarks_list, state)

    def should_stop(self) -> bool:
        return any(p.should_stop() for p in self._presenters)

    def close(self) -> None:
        for p in self._presenters:
            try:
                p.close()
            except Exception:
                _log.exception("presenter %s falhou em close", type(p).__name__)
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_composite_presenter.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/presenters/composite.py tests/integration/test_composite_presenter.py
git commit -m "feat(presenter): CompositePresenter para fan-out"
```

---

## Task 7: FileVideoSource

**Files:**
- Create: `src/driver_fatigue/infrastructure/video_sources/file.py`
- Create: `tests/integration/test_file_video_source.py`

- [ ] **Step 1: Escrever teste**

`tests/integration/test_file_video_source.py`:

```python
from pathlib import Path

from driver_fatigue.infrastructure.video_sources.file import FileVideoSource


class TestFileVideoSource:
    def test_reads_sequential_frames(self, test_video_path: Path):
        src = FileVideoSource(path=test_video_path)
        try:
            f0 = src.read()
            f1 = src.read()
            assert f0 is not None and f1 is not None
            assert f0.index == 0 and f1.index == 1
            assert f0.image.shape[2] == 3
        finally:
            src.release()

    def test_returns_none_at_end(self, test_video_path: Path, monkeypatch):
        src = FileVideoSource(path=test_video_path)
        try:
            # força EOF rapidamente lendo todos os frames
            count = 0
            while True:
                f = src.read()
                if f is None:
                    break
                count += 1
                if count > 10_000:
                    break  # safety
            assert count > 0
            # uma leitura após EOF deve continuar None
            assert src.read() is None
        finally:
            src.release()

    def test_loop_mode_rebobina(self, test_video_path: Path):
        src = FileVideoSource(path=test_video_path, loop=True)
        try:
            # lê alguns frames, rebobina via loop
            first = src.read()
            assert first is not None
            # lê até EOF e um além — loop deve rebobinar
            count_before_loop = 0
            for _ in range(200):
                f = src.read()
                if f is None:
                    break
                count_before_loop += 1
            # agora o loop deve ter rebobinado; read() ainda retorna frame
            after = src.read()
            assert after is not None
        finally:
            src.release()

    def test_release_is_idempotent(self, test_video_path: Path):
        src = FileVideoSource(path=test_video_path)
        src.release()
        src.release()
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_file_video_source.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar**

`src/driver_fatigue/infrastructure/video_sources/file.py`:

```python
from __future__ import annotations

import time
from pathlib import Path

import cv2

from driver_fatigue.domain.entities import Frame


class FileVideoSource:
    """Lê frames de um arquivo de vídeo. Opcionalmente faz loop ao chegar ao fim."""

    def __init__(self, path: Path, loop: bool = False) -> None:
        self._path = Path(path)
        self._cap = cv2.VideoCapture(str(self._path))
        if not self._cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir vídeo {self._path}")
        self._loop = loop
        self._index = 0
        self._exhausted = False
        self._released = False

    def read(self) -> Frame | None:
        if self._released or self._exhausted:
            return None
        ok, img = self._cap.read()
        if not ok:
            if self._loop:
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, img = self._cap.read()
                if not ok:
                    self._exhausted = True
                    return None
            else:
                self._exhausted = True
                return None
        frame = Frame(image=img, timestamp=time.monotonic(), index=self._index)
        self._index += 1
        return frame

    def release(self) -> None:
        if not self._released:
            self._cap.release()
            self._released = True
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_file_video_source.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/video_sources/file.py tests/integration/test_file_video_source.py
git commit -m "feat(infra): FileVideoSource com modo loop"
```

---

## Task 8: RtspVideoSource

**Files:**
- Create: `src/driver_fatigue/infrastructure/video_sources/rtsp.py`
- Create: `tests/integration/test_rtsp_video_source.py`

Usa mock de `cv2.VideoCapture` — não conecta RTSP real.

- [ ] **Step 1: Escrever teste**

`tests/integration/test_rtsp_video_source.py`:

```python
from unittest.mock import MagicMock, patch

import numpy as np


def _fake_cap(frames_before_fail: int = 3, then_succeed: bool = False):
    """Retorna um VideoCapture mock que entrega N frames e depois falha."""
    cap = MagicMock()
    cap.isOpened.return_value = True
    seq = []
    for _ in range(frames_before_fail):
        seq.append((True, np.zeros((2, 2, 3), dtype=np.uint8)))
    seq.append((False, None))
    if then_succeed:
        seq.append((True, np.zeros((2, 2, 3), dtype=np.uint8)))
    cap.read.side_effect = seq + [(False, None)]
    return cap


class TestRtspVideoSource:
    @patch("driver_fatigue.infrastructure.video_sources.rtsp.cv2")
    @patch("driver_fatigue.infrastructure.video_sources.rtsp.time.sleep")
    def test_reads_frames_until_exhaustion(self, sleep_mock, cv2_mock):
        from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource

        cv2_mock.VideoCapture.return_value = _fake_cap(frames_before_fail=3)
        src = RtspVideoSource(url="rtsp://fake")
        frames = []
        while True:
            f = src.read()
            if f is None:
                break
            frames.append(f)
        assert len(frames) == 3

    @patch("driver_fatigue.infrastructure.video_sources.rtsp.cv2")
    @patch("driver_fatigue.infrastructure.video_sources.rtsp.time.sleep")
    def test_reconnects_on_failure(self, sleep_mock, cv2_mock):
        from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource

        first_cap = _fake_cap(frames_before_fail=2, then_succeed=False)
        reconnect_cap = _fake_cap(frames_before_fail=1, then_succeed=False)
        cv2_mock.VideoCapture.side_effect = [first_cap, reconnect_cap, reconnect_cap, reconnect_cap]

        src = RtspVideoSource(url="rtsp://fake", reconnect_attempts=2)
        # lê até esgotar (vai reconectar automaticamente)
        count = 0
        while True:
            f = src.read()
            if f is None:
                break
            count += 1
            if count > 100:
                break
        # primeiro stream deu 2 frames; reconexões tentam mais 1 antes de falhar
        assert count >= 2
        # reconexão foi tentada ao menos uma vez
        assert cv2_mock.VideoCapture.call_count >= 2

    @patch("driver_fatigue.infrastructure.video_sources.rtsp.cv2")
    @patch("driver_fatigue.infrastructure.video_sources.rtsp.time.sleep")
    def test_release_is_idempotent(self, sleep_mock, cv2_mock):
        from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource

        cv2_mock.VideoCapture.return_value = _fake_cap(frames_before_fail=0)
        src = RtspVideoSource(url="rtsp://fake")
        src.release()
        src.release()

    @patch("driver_fatigue.infrastructure.video_sources.rtsp.cv2")
    def test_raises_when_cant_open(self, cv2_mock):
        from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource

        bad = MagicMock()
        bad.isOpened.return_value = False
        cv2_mock.VideoCapture.return_value = bad
        import pytest
        with pytest.raises(RuntimeError):
            RtspVideoSource(url="rtsp://unreachable")
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_rtsp_video_source.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar**

`src/driver_fatigue/infrastructure/video_sources/rtsp.py`:

```python
from __future__ import annotations

import logging
import time

import cv2

from driver_fatigue.domain.entities import Frame

_log = logging.getLogger("driver_fatigue.rtsp")


class RtspVideoSource:
    """Lê frames de um stream RTSP com reconexão exponencial."""

    def __init__(
        self,
        url: str,
        reconnect_attempts: int = 3,
        initial_backoff_seconds: float = 1.0,
    ) -> None:
        self._url = url
        self._reconnect_attempts = reconnect_attempts
        self._initial_backoff = initial_backoff_seconds
        self._cap = self._open()
        self._index = 0
        self._released = False
        self._exhausted = False

    def _open(self) -> cv2.VideoCapture:
        cap = cv2.VideoCapture(self._url, cv2.CAP_FFMPEG)
        if not cap.isOpened():
            raise RuntimeError(f"Não foi possível abrir stream RTSP {self._url}")
        return cap

    def _try_reconnect(self) -> bool:
        for attempt in range(self._reconnect_attempts):
            backoff = self._initial_backoff * (2 ** attempt)
            _log.warning("RTSP desconectou; tentativa %d/%d em %.1fs",
                         attempt + 1, self._reconnect_attempts, backoff)
            time.sleep(backoff)
            try:
                self._cap.release()
            except Exception:
                pass
            try:
                self._cap = self._open()
                return True
            except Exception:
                continue
        return False

    def read(self) -> Frame | None:
        if self._released or self._exhausted:
            return None
        ok, img = self._cap.read()
        if not ok:
            if not self._try_reconnect():
                self._exhausted = True
                return None
            ok, img = self._cap.read()
            if not ok:
                self._exhausted = True
                return None
        frame = Frame(image=img, timestamp=time.monotonic(), index=self._index)
        self._index += 1
        return frame

    def release(self) -> None:
        if not self._released:
            try:
                self._cap.release()
            except Exception:
                pass
            self._released = True
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_rtsp_video_source.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/video_sources/rtsp.py tests/integration/test_rtsp_video_source.py
git commit -m "feat(infra): RtspVideoSource com reconexao exponencial"
```

---

## Task 9: CompositeSink (promoção do _CompositeSink)

**Files:**
- Create: `src/driver_fatigue/infrastructure/alert_sinks/composite.py`
- Create: `tests/integration/test_composite_sink.py`
- Modify: `src/driver_fatigue/bootstrap.py` (remove `_CompositeSink`, importa público)

- [ ] **Step 1: Escrever teste**

`tests/integration/test_composite_sink.py`:

```python
from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.infrastructure.alert_sinks.composite import CompositeSink


class SpySink:
    def __init__(self, raise_on: str | None = None):
        self.notified = 0
        self.recovered = 0
        self._raise = raise_on

    def notify(self, event):
        self.notified += 1
        if self._raise == "notify":
            raise RuntimeError("boom notify")

    def on_recovery(self, frame_index):
        self.recovered += 1
        if self._raise == "recovery":
            raise RuntimeError("boom recovery")


def _event():
    return FatigueEvent(
        timestamp=0.0, state=FatigueState.initial(), frame_index=0,
    )


class TestCompositeSink:
    def test_notify_fans_out(self):
        a, b = SpySink(), SpySink()
        c = CompositeSink(a, b)
        c.notify(_event())
        assert a.notified == 1 and b.notified == 1

    def test_on_recovery_fans_out(self):
        a, b = SpySink(), SpySink()
        c = CompositeSink(a, b)
        c.on_recovery(frame_index=10)
        assert a.recovered == 1 and b.recovered == 1

    def test_notify_exception_does_not_break_others(self):
        a = SpySink(raise_on="notify")
        b = SpySink()
        c = CompositeSink(a, b)
        c.notify(_event())  # não deve propagar
        assert a.notified == 1 and b.notified == 1

    def test_recovery_exception_does_not_break_others(self):
        a = SpySink(raise_on="recovery")
        b = SpySink()
        c = CompositeSink(a, b)
        c.on_recovery(frame_index=1)
        assert a.recovered == 1 and b.recovered == 1
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_composite_sink.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar composite.py**

`src/driver_fatigue/infrastructure/alert_sinks/composite.py`:

```python
from __future__ import annotations

import logging

from driver_fatigue.application.ports import AlertSinkPort
from driver_fatigue.domain.entities import FatigueEvent

_log = logging.getLogger("driver_fatigue.alerts")


class CompositeSink:
    """Fan-out de eventos para múltiplos sinks com isolamento de falhas."""

    def __init__(self, *sinks: AlertSinkPort) -> None:
        self._sinks = sinks

    def notify(self, event: FatigueEvent) -> None:
        for s in self._sinks:
            try:
                s.notify(event)
            except Exception:
                _log.exception("sink %s falhou em notify", type(s).__name__)

    def on_recovery(self, frame_index: int) -> None:
        for s in self._sinks:
            try:
                s.on_recovery(frame_index)
            except Exception:
                _log.exception("sink %s falhou em on_recovery", type(s).__name__)
```

- [ ] **Step 4: Remover `_CompositeSink` de bootstrap.py e usar o público**

Abra `src/driver_fatigue/bootstrap.py`. Remova a classe `_CompositeSink` inteira. Substitua pelo import:

```python
from driver_fatigue.infrastructure.alert_sinks.composite import CompositeSink
```

Na função `_build_sink`, troque `return _CompositeSink(sound_sink, log_sink)` por `return CompositeSink(sound_sink, log_sink)`.

- [ ] **Step 5: Rodar testes**

Run: `pytest tests/integration/test_composite_sink.py tests/e2e/ -v`
Expected: 4 novos passed + E2E ainda passa.

- [ ] **Step 6: Commit**

```bash
git add src/driver_fatigue/infrastructure/alert_sinks/composite.py tests/integration/test_composite_sink.py src/driver_fatigue/bootstrap.py
git commit -m "refactor: CompositeSink publico, remove duplicata privada em bootstrap"
```

---

## Task 10: HttpWebhookSink

**Files:**
- Create: `src/driver_fatigue/infrastructure/alert_sinks/http_webhook.py`
- Create: `tests/integration/test_http_webhook_sink.py`

- [ ] **Step 1: Escrever teste**

`tests/integration/test_http_webhook_sink.py`:

```python
import httpx
import pytest
import respx

from driver_fatigue.domain.entities import FatigueEvent, FatigueState
from driver_fatigue.infrastructure.alert_sinks.http_webhook import HttpWebhookSink


def _alert_event():
    return FatigueEvent(
        timestamp=1.5,
        state=FatigueState(
            ear=0.18, mar=0.52, consecutive_frames=20,
            is_fatigued=True, is_yawning=False, severity="alert",
        ),
        frame_index=100,
    )


class TestHttpWebhookSink:
    @respx.mock
    def test_notify_posts_json_payload(self):
        route = respx.post("https://hook.example/events").mock(
            return_value=httpx.Response(200),
        )
        sink = HttpWebhookSink(url="https://hook.example/events")
        sink.notify(_alert_event())
        assert route.called
        req = route.calls.last.request
        import json
        payload = json.loads(req.content)
        assert payload["event"] == "fatigue_alert"
        assert payload["frame_index"] == 100
        assert payload["severity"] == "alert"
        assert payload["ear"] == pytest.approx(0.18)
        assert payload["mar"] == pytest.approx(0.52)

    @respx.mock
    def test_on_recovery_posts_recovery_event(self):
        route = respx.post("https://hook.example/events").mock(
            return_value=httpx.Response(204),
        )
        sink = HttpWebhookSink(url="https://hook.example/events")
        sink.on_recovery(frame_index=200)
        assert route.called
        import json
        payload = json.loads(route.calls.last.request.content)
        assert payload["event"] == "fatigue_recovery"
        assert payload["frame_index"] == 200

    @respx.mock
    def test_bearer_token_sent_in_authorization_header(self):
        route = respx.post("https://hook.example/events").mock(
            return_value=httpx.Response(200),
        )
        sink = HttpWebhookSink(
            url="https://hook.example/events",
            bearer_token="secret-123",
        )
        sink.notify(_alert_event())
        assert route.called
        headers = route.calls.last.request.headers
        assert headers.get("authorization") == "Bearer secret-123"

    @respx.mock
    def test_timeout_is_swallowed(self):
        respx.post("https://hook.example/events").mock(
            side_effect=httpx.TimeoutException("boom"),
        )
        sink = HttpWebhookSink(url="https://hook.example/events", timeout_seconds=0.1)
        sink.notify(_alert_event())  # não deve levantar

    @respx.mock
    def test_5xx_is_swallowed(self):
        respx.post("https://hook.example/events").mock(
            return_value=httpx.Response(500),
        )
        sink = HttpWebhookSink(url="https://hook.example/events")
        sink.notify(_alert_event())  # loga mas não levanta
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_http_webhook_sink.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar**

`src/driver_fatigue/infrastructure/alert_sinks/http_webhook.py`:

```python
from __future__ import annotations

import logging

import httpx

from driver_fatigue.domain.entities import FatigueEvent

_log = logging.getLogger("driver_fatigue.alerts.http")


class HttpWebhookSink:
    """Posta eventos como JSON em um webhook HTTP."""

    def __init__(
        self,
        url: str,
        bearer_token: str | None = None,
        timeout_seconds: float = 3.0,
    ) -> None:
        self._url = url
        headers = {"Content-Type": "application/json"}
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"
        self._client = httpx.Client(
            headers=headers,
            timeout=timeout_seconds,
        )

    def notify(self, event: FatigueEvent) -> None:
        payload = {
            "event": "fatigue_alert",
            "timestamp": event.timestamp,
            "frame_index": event.frame_index,
            "ear": event.state.ear,
            "mar": event.state.mar,
            "severity": event.state.severity,
            "consecutive_frames": event.state.consecutive_frames,
        }
        self._post(payload)

    def on_recovery(self, frame_index: int) -> None:
        payload = {
            "event": "fatigue_recovery",
            "timestamp": 0.0,
            "frame_index": frame_index,
        }
        self._post(payload)

    def _post(self, payload: dict) -> None:
        try:
            response = self._client.post(self._url, json=payload)
            if response.status_code >= 500:
                _log.warning("webhook retornou %d", response.status_code)
        except httpx.HTTPError as e:
            _log.warning("webhook falhou: %s", e)

    def __del__(self):
        try:
            self._client.close()
        except Exception:
            pass
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_http_webhook_sink.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/alert_sinks/http_webhook.py tests/integration/test_http_webhook_sink.py
git commit -m "feat(infra): HttpWebhookSink com suporte Bearer e tolerancia a falhas"
```

---

## Task 11: MqttSink

**Files:**
- Create: `src/driver_fatigue/infrastructure/alert_sinks/mqtt.py`
- Create: `tests/integration/test_mqtt_sink.py`

- [ ] **Step 1: Escrever teste**

`tests/integration/test_mqtt_sink.py`:

```python
import json
from unittest.mock import MagicMock, patch

from driver_fatigue.domain.entities import FatigueEvent, FatigueState


def _alert_event():
    return FatigueEvent(
        timestamp=1.5,
        state=FatigueState(
            ear=0.18, mar=0.52, consecutive_frames=20,
            is_fatigued=True, is_yawning=False, severity="alert",
        ),
        frame_index=100,
    )


class TestMqttSink:
    @patch("driver_fatigue.infrastructure.alert_sinks.mqtt.mqtt")
    def test_notify_publishes_json_payload(self, paho_mock):
        from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink

        client_instance = MagicMock()
        paho_mock.Client.return_value = client_instance

        sink = MqttSink(broker="mqtt.example", topic="driver_fatigue/events")
        sink.notify(_alert_event())

        assert client_instance.publish.called
        call = client_instance.publish.call_args
        assert call.args[0] == "driver_fatigue/events"
        payload = json.loads(call.args[1])
        assert payload["event"] == "fatigue_alert"
        assert payload["frame_index"] == 100

    @patch("driver_fatigue.infrastructure.alert_sinks.mqtt.mqtt")
    def test_on_recovery_publishes_recovery_event(self, paho_mock):
        from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink

        client_instance = MagicMock()
        paho_mock.Client.return_value = client_instance

        sink = MqttSink(broker="mqtt.example", topic="driver_fatigue/events")
        sink.on_recovery(frame_index=200)

        assert client_instance.publish.called
        payload = json.loads(client_instance.publish.call_args.args[1])
        assert payload["event"] == "fatigue_recovery"
        assert payload["frame_index"] == 200

    @patch("driver_fatigue.infrastructure.alert_sinks.mqtt.mqtt")
    def test_connect_failure_does_not_raise(self, paho_mock):
        from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink

        client_instance = MagicMock()
        client_instance.connect.side_effect = OSError("broker offline")
        paho_mock.Client.return_value = client_instance

        # não deve levantar no __init__
        sink = MqttSink(broker="mqtt.example", topic="t")

        # notify ainda é chamável (silenciosamente tenta reconectar)
        sink.notify(_alert_event())

    @patch("driver_fatigue.infrastructure.alert_sinks.mqtt.mqtt")
    def test_uses_credentials_when_provided(self, paho_mock):
        from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink

        client_instance = MagicMock()
        paho_mock.Client.return_value = client_instance

        MqttSink(broker="x", topic="t", username="u", password="p")
        client_instance.username_pw_set.assert_called_once_with("u", "p")
```

- [ ] **Step 2: Rodar teste**

Run: `pytest tests/integration/test_mqtt_sink.py -v`
Expected: ModuleNotFoundError.

- [ ] **Step 3: Implementar**

`src/driver_fatigue/infrastructure/alert_sinks/mqtt.py`:

```python
from __future__ import annotations

import json
import logging

import paho.mqtt.client as mqtt

from driver_fatigue.domain.entities import FatigueEvent

_log = logging.getLogger("driver_fatigue.alerts.mqtt")


class MqttSink:
    """Publica eventos como JSON em um broker MQTT com QoS 1."""

    def __init__(
        self,
        broker: str,
        port: int = 1883,
        topic: str = "driver_fatigue/events",
        username: str | None = None,
        password: str | None = None,
        client_id: str | None = None,
        connect_timeout_seconds: float = 3.0,
    ) -> None:
        self._broker = broker
        self._port = port
        self._topic = topic
        self._connected = False

        self._client = mqtt.Client(client_id=client_id or "")
        if username is not None:
            self._client.username_pw_set(username, password)

        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect

        try:
            self._client.connect(broker, port, keepalive=int(connect_timeout_seconds * 10))
            self._client.loop_start()
            self._connected = True
        except Exception as e:
            _log.warning("falha ao conectar MQTT %s:%d — %s", broker, port, e)

    def _on_connect(self, client, userdata, flags, rc):
        self._connected = (rc == 0)

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False

    def _ensure_connected(self) -> None:
        if self._connected:
            return
        try:
            self._client.reconnect()
            self._connected = True
        except Exception as e:
            _log.warning("reconexao MQTT falhou: %s", e)

    def notify(self, event: FatigueEvent) -> None:
        payload = {
            "event": "fatigue_alert",
            "timestamp": event.timestamp,
            "frame_index": event.frame_index,
            "ear": event.state.ear,
            "mar": event.state.mar,
            "severity": event.state.severity,
            "consecutive_frames": event.state.consecutive_frames,
        }
        self._publish(payload)

    def on_recovery(self, frame_index: int) -> None:
        payload = {
            "event": "fatigue_recovery",
            "timestamp": 0.0,
            "frame_index": frame_index,
        }
        self._publish(payload)

    def _publish(self, payload: dict) -> None:
        self._ensure_connected()
        try:
            self._client.publish(self._topic, json.dumps(payload), qos=1)
        except Exception as e:
            _log.warning("publish MQTT falhou: %s", e)

    def __del__(self):
        try:
            self._client.loop_stop()
            self._client.disconnect()
        except Exception:
            pass
```

- [ ] **Step 4: Rodar testes**

Run: `pytest tests/integration/test_mqtt_sink.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/alert_sinks/mqtt.py tests/integration/test_mqtt_sink.py
git commit -m "feat(infra): MqttSink com reconexao best-effort e QoS 1"
```

---

## Task 12: AppSettings expandido

**Files:**
- Modify: `src/driver_fatigue/interfaces/config/settings.py`
- Modify: `tests/unit/interfaces/test_settings.py`
- Modify: `config/default.yaml`
- Modify: `config/example.env`

- [ ] **Step 1: Atualizar testes**

Substitua `tests/unit/interfaces/test_settings.py` por:

```python
from pathlib import Path

import pytest
from pydantic import ValidationError

from driver_fatigue.interfaces.config.settings import AppSettings


class TestAppSettings:
    def test_defaults(self):
        s = AppSettings()
        assert s.source.kind == "webcam"
        assert s.source.index == 0
        assert s.thresholds.ear_threshold == 0.25
        assert s.alarm_sound_path.name == "alarm.wav"
        assert s.sinks == ["sound", "log"]
        assert s.recording.path is None

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("DRIVER_FATIGUE_SOURCE__INDEX", "2")
        monkeypatch.setenv("DRIVER_FATIGUE_THRESHOLDS__EAR_THRESHOLD", "0.30")
        s = AppSettings()
        assert s.source.index == 2
        assert s.thresholds.ear_threshold == 0.30

    def test_rtsp_requires_url(self):
        with pytest.raises(ValidationError):
            AppSettings(source={"kind": "rtsp"})

    def test_file_requires_path(self):
        with pytest.raises(ValidationError):
            AppSettings(source={"kind": "file"})

    def test_http_sink_requires_config(self):
        with pytest.raises(ValidationError):
            AppSettings(sinks=["http"])

    def test_mqtt_sink_requires_config(self):
        with pytest.raises(ValidationError):
            AppSettings(sinks=["mqtt"])

    def test_valid_rtsp_config(self):
        s = AppSettings(source={"kind": "rtsp", "url": "rtsp://fake/stream"})
        assert s.source.kind == "rtsp"
        assert s.source.url == "rtsp://fake/stream"

    def test_valid_http_sink_config(self):
        s = AppSettings(
            sinks=["http"],
            http_webhook={"url": "https://hook.x/events"},
        )
        assert s.http_webhook.url == "https://hook.x/events"

    def test_load_from_yaml(self, tmp_path):
        yaml = tmp_path / "conf.yaml"
        yaml.write_text(
            "source:\n  kind: file\n  path: assets/test.mp4\n"
            "sinks: [log]\n"
            "recording:\n  path: out.mp4\n  fps: 24\n"
        )
        s = AppSettings.from_yaml(yaml)
        assert s.source.kind == "file"
        assert s.source.path == Path("assets/test.mp4")
        assert s.sinks == ["log"]
        assert s.recording.path == Path("out.mp4")
        assert s.recording.fps == 24
```

- [ ] **Step 2: Reescrever settings.py**

Substitua `src/driver_fatigue/interfaces/config/settings.py` por:

```python
from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class SourceSettings(BaseModel):
    kind: Literal["webcam", "rtsp", "file"] = "webcam"
    index: int = 0
    url: str | None = None
    path: Path | None = None
    loop: bool = False

    @model_validator(mode="after")
    def _check_fields_for_kind(self) -> "SourceSettings":
        if self.kind == "rtsp" and not self.url:
            raise ValueError("source.url é obrigatório quando kind='rtsp'")
        if self.kind == "file" and self.path is None:
            raise ValueError("source.path é obrigatório quando kind='file'")
        return self


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
    path: Path | None = None
    fps: int = 30
    codec: str = "mp4v"


SinkName = Literal["sound", "log", "http", "mqtt"]


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

    sinks: list[SinkName] = Field(default_factory=lambda: ["sound", "log"])
    http_webhook: HttpWebhookSettings | None = None
    mqtt: MqttSettings | None = None
    recording: RecordingSettings = Field(default_factory=RecordingSettings)

    @model_validator(mode="after")
    def _check_sink_configs(self) -> "AppSettings":
        if "http" in self.sinks and self.http_webhook is None:
            raise ValueError("sinks inclui 'http' mas http_webhook não foi definido")
        if "mqtt" in self.sinks and self.mqtt is None:
            raise ValueError("sinks inclui 'mqtt' mas mqtt não foi definido")
        return self

    @classmethod
    def from_yaml(cls, path: Path) -> "AppSettings":
        data = yaml.safe_load(path.read_text())
        return cls(**(data or {}))
```

- [ ] **Step 3: Atualizar config/default.yaml**

Substitua `config/default.yaml`:

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

sinks: [sound, log]

# Descomente para habilitar webhook HTTP:
# http_webhook:
#   url: https://seu-endpoint.example/driver-fatigue
#   bearer_token: null
#   timeout_seconds: 3.0

# Descomente para habilitar MQTT:
# mqtt:
#   broker: mqtt.example.com
#   port: 1883
#   topic: driver_fatigue/events
#   username: null
#   password: null

recording:
  path: null
  fps: 30
  codec: mp4v
```

- [ ] **Step 4: Atualizar config/example.env**

Substitua `config/example.env`:

```
# Fonte de vídeo
DRIVER_FATIGUE_SOURCE__KIND=webcam
DRIVER_FATIGUE_SOURCE__INDEX=0
# Para RTSP:
# DRIVER_FATIGUE_SOURCE__KIND=rtsp
# DRIVER_FATIGUE_SOURCE__URL=rtsp://user:pass@host/stream
# Para arquivo:
# DRIVER_FATIGUE_SOURCE__KIND=file
# DRIVER_FATIGUE_SOURCE__PATH=assets/test_sonolency.mp4

# Thresholds
DRIVER_FATIGUE_THRESHOLDS__EAR_THRESHOLD=0.25
DRIVER_FATIGUE_THRESHOLDS__MAR_THRESHOLD=0.60

# Modo e gravação
DRIVER_FATIGUE_HEADLESS=false
# DRIVER_FATIGUE_RECORDING__PATH=out.mp4

# Webhooks (opcional)
# DRIVER_FATIGUE_HTTP_WEBHOOK__URL=https://hook.example/events
# DRIVER_FATIGUE_MQTT__BROKER=mqtt.example
```

- [ ] **Step 5: Rodar testes**

Run: `pytest tests/unit/interfaces/test_settings.py -v`
Expected: 9 passed.

- [ ] **Step 6: Commit**

```bash
git add src/driver_fatigue/interfaces/config/settings.py tests/unit/interfaces/test_settings.py config/default.yaml config/example.env
git commit -m "feat(config): AppSettings suporta rtsp/file, sinks configuraveis e recording"
```

---

## Task 13: Bootstrap atualizado

**Files:**
- Modify: `src/driver_fatigue/bootstrap.py`

- [ ] **Step 1: Reescrever bootstrap**

Substitua completamente `src/driver_fatigue/bootstrap.py`:

```python
from __future__ import annotations

import logging
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
from driver_fatigue.infrastructure.alert_sinks.composite import CompositeSink
from driver_fatigue.infrastructure.alert_sinks.http_webhook import HttpWebhookSink
from driver_fatigue.infrastructure.alert_sinks.log import LogSink
from driver_fatigue.infrastructure.alert_sinks.mqtt import MqttSink
from driver_fatigue.infrastructure.alert_sinks.sound import SoundSink
from driver_fatigue.infrastructure.detectors.mediapipe_detector import MediapipeFaceDetector
from driver_fatigue.infrastructure.presenters.composite import CompositePresenter
from driver_fatigue.infrastructure.presenters.file_recorder import FileRecorderPresenter
from driver_fatigue.infrastructure.presenters.headless import HeadlessPresenter
from driver_fatigue.infrastructure.presenters.opencv_window import OpenCvWindowPresenter
from driver_fatigue.infrastructure.rendering.renderer import FrameRenderer
from driver_fatigue.infrastructure.video_sources.file import FileVideoSource
from driver_fatigue.infrastructure.video_sources.rtsp import RtspVideoSource
from driver_fatigue.infrastructure.video_sources.webcam import WebcamVideoSource
from driver_fatigue.interfaces.config.settings import AppSettings

_log = logging.getLogger("driver_fatigue.bootstrap")


def _build_source(settings: AppSettings) -> VideoSourcePort:
    kind = settings.source.kind
    if kind == "webcam":
        return WebcamVideoSource(device_index=settings.source.index)
    if kind == "rtsp":
        assert settings.source.url is not None
        return RtspVideoSource(url=settings.source.url)
    if kind == "file":
        assert settings.source.path is not None
        return FileVideoSource(path=settings.source.path, loop=settings.source.loop)
    raise ValueError(f"source.kind {kind!r} não suportado")


def _build_single_sink(
    name: str,
    settings: AppSettings,
    sound_override: Literal["disabled"] | None = None,
) -> AlertSinkPort | None:
    if name == "log":
        return LogSink()
    if name == "sound":
        if sound_override == "disabled":
            return None
        try:
            return SoundSink(sound_path=settings.alarm_sound_path)
        except Exception:
            _log.warning("SoundSink indisponivel, ignorando")
            return None
    if name == "http":
        cfg = settings.http_webhook
        assert cfg is not None
        return HttpWebhookSink(
            url=cfg.url, bearer_token=cfg.bearer_token,
            timeout_seconds=cfg.timeout_seconds,
        )
    if name == "mqtt":
        cfg = settings.mqtt
        assert cfg is not None
        return MqttSink(
            broker=cfg.broker, port=cfg.port, topic=cfg.topic,
            username=cfg.username, password=cfg.password,
        )
    raise ValueError(f"sink {name!r} desconhecido")


def _build_sinks(
    settings: AppSettings,
    sound_override: Literal["disabled"] | None = None,
) -> AlertSinkPort:
    resolved = []
    for name in settings.sinks:
        s = _build_single_sink(name, settings, sound_override)
        if s is not None:
            resolved.append(s)
    if not resolved:
        resolved.append(LogSink())  # fallback
    return CompositeSink(*resolved)


def _build_renderer(settings: AppSettings) -> FrameRenderer:
    theme = RenderingTheme(
        glow_enabled=settings.theme.glow_enabled,
        show_hud=settings.theme.show_hud,
        show_face_oval=settings.theme.show_face_oval,
        smoothing_steps=settings.theme.smoothing_steps,
        overlay_alpha=settings.theme.overlay_alpha,
    )
    return FrameRenderer(theme=theme)


def _build_presenter(
    settings: AppSettings,
    renderer: FrameRenderer,
) -> FramePresenterPort:
    main = HeadlessPresenter() if settings.headless else OpenCvWindowPresenter(renderer=renderer)
    if settings.recording.path is None:
        return main
    recorder = FileRecorderPresenter(
        renderer=renderer,
        output_path=settings.recording.path,
        fps=settings.recording.fps,
        codec=settings.recording.codec,
    )
    return CompositePresenter(main, recorder)


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
    sink = _build_sinks(settings, sound_override=sound_override)
    renderer = _build_renderer(settings)
    presenter = _build_presenter(settings, renderer)
    return MonitorDriverUseCase(
        source=source, detect=detect, sink=sink, presenter=presenter,
    )
```

- [ ] **Step 2: Verificar que E2E ainda funciona**

Run: `pytest tests/e2e/test_bootstrap_pipeline.py -v`
Expected: 1 passed.

- [ ] **Step 3: Commit**

```bash
git add src/driver_fatigue/bootstrap.py
git commit -m "feat: bootstrap monta rtsp/file sources, sinks http/mqtt, recording"
```

---

## Task 14: CLI estendida

**Files:**
- Modify: `src/driver_fatigue/interfaces/cli/main.py`
- Modify: `tests/integration/test_cli.py`

- [ ] **Step 1: Atualizar testes**

Substitua `tests/integration/test_cli.py`:

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
        assert "run" in result.stdout or "--source" in result.stdout

    def test_invalid_source_kind_exits_nonzero(self):
        result = subprocess.run(
            [sys.executable, "-m", "driver_fatigue", "run",
             "--source", "banana:0", "--headless"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode != 0

    def test_file_source_accepted_in_parser(self):
        # --help da subcomando run deve aceitar ajuda sem erro (valida argparse)
        result = subprocess.run(
            [sys.executable, "-m", "driver_fatigue", "run", "--help"],
            capture_output=True, text=True, timeout=15,
        )
        assert result.returncode == 0
        assert "--source" in result.stdout
        assert "--sinks" in result.stdout
        assert "--record" in result.stdout
```

- [ ] **Step 2: Reescrever main.py**

Substitua `src/driver_fatigue/interfaces/cli/main.py`:

```python
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from driver_fatigue.bootstrap import build_monitor_use_case
from driver_fatigue.interfaces.config.settings import (
    AppSettings,
    RecordingSettings,
    SourceSettings,
)


def _parse_source(arg: str) -> SourceSettings:
    """Converte 'webcam:0' | 'file:path' | 'rtsp://...' em SourceSettings."""
    if arg.startswith("rtsp://") or arg.startswith("rtsps://"):
        return SourceSettings(kind="rtsp", url=arg)
    kind, _, value = arg.partition(":")
    if kind == "webcam":
        try:
            return SourceSettings(kind="webcam", index=int(value or "0"))
        except ValueError as e:
            raise argparse.ArgumentTypeError(f"webcam index inválido: {e}")
    if kind == "file":
        if not value:
            raise argparse.ArgumentTypeError("file: requer um path (file:path/to.mp4)")
        return SourceSettings(kind="file", path=Path(value))
    raise argparse.ArgumentTypeError(
        f"source '{kind}' não suportado (use webcam:N, file:path, rtsp://...)"
    )


def _parse_sinks(arg: str) -> list[str]:
    valid = {"sound", "log", "http", "mqtt"}
    names = [n.strip() for n in arg.split(",") if n.strip()]
    for n in names:
        if n not in valid:
            raise argparse.ArgumentTypeError(
                f"sink '{n}' inválido; valores: {', '.join(sorted(valid))}"
            )
    return names


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="driver-fatigue",
        description="Detector de fadiga em motoristas (Clean Architecture).",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="inicia detecção")
    run.add_argument(
        "--source", type=_parse_source,
        default=SourceSettings(kind="webcam", index=0),
        help="fonte de vídeo: webcam:N | file:path | rtsp://...",
    )
    run.add_argument(
        "--sinks", type=_parse_sinks, default=None,
        help="sinks ativos (comma-separated): sound,log,http,mqtt",
    )
    run.add_argument(
        "--record", type=Path, default=None,
        help="grava MP4 com overlay no caminho dado",
    )
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

        # aplica overrides da CLI
        updates: dict = {
            "source": args.source,
            "headless": args.headless or settings.headless,
        }
        if args.sinks is not None:
            updates["sinks"] = args.sinks
        if args.record is not None:
            updates["recording"] = RecordingSettings(
                path=args.record,
                fps=settings.recording.fps,
                codec=settings.recording.codec,
            )
        settings = settings.model_copy(update=updates)

        uc = build_monitor_use_case(settings=settings)
        uc.run()
        return 0

    return 2


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 3: Rodar testes**

Run: `pytest tests/integration/test_cli.py -v`
Expected: 3 passed.

- [ ] **Step 4: Commit**

```bash
git add src/driver_fatigue/interfaces/cli/main.py tests/integration/test_cli.py
git commit -m "feat(cli): --source file/rtsp, --sinks e --record"
```

---

## Task 15: E2E estendido + README

**Files:**
- Modify: `tests/e2e/test_bootstrap_pipeline.py`
- Modify: `docs/README.md`

- [ ] **Step 1: Estender E2E**

Substitua `tests/e2e/test_bootstrap_pipeline.py`:

```python
from pathlib import Path

import cv2
import pytest

from driver_fatigue.application.ports import VideoSourcePort
from driver_fatigue.bootstrap import build_monitor_use_case
from driver_fatigue.domain.entities import Frame
from driver_fatigue.interfaces.config.settings import (
    AppSettings,
    RecordingSettings,
    SourceSettings,
)


class FramesFromFile(VideoSourcePort):
    def __init__(self, path: Path, max_frames: int):
        self._cap = cv2.VideoCapture(str(path))
        self._max = max_frames
        self._i = 0
        self._released = False

    def read(self):
        if self._i >= self._max:
            return None
        ok, img = self._cap.read()
        if not ok:
            return None
        frame = Frame(image=img, timestamp=float(self._i), index=self._i)
        self._i += 1
        return frame

    def release(self):
        if not self._released:
            self._cap.release()
            self._released = True


@pytest.mark.timeout(30)
def test_pipeline_processes_test_video_headless(test_video_path):
    settings = AppSettings(headless=True, sinks=["log"])
    uc = build_monitor_use_case(
        settings=settings,
        source_override=FramesFromFile(test_video_path, max_frames=20),
        sound_override="disabled",
    )
    uc.run()


@pytest.mark.timeout(60)
def test_pipeline_records_mp4_with_overlay(test_video_path, tmp_path):
    out = tmp_path / "recorded.mp4"
    settings = AppSettings(
        headless=True,
        sinks=["log"],
        recording=RecordingSettings(path=out, fps=10),
    )
    uc = build_monitor_use_case(
        settings=settings,
        source_override=FramesFromFile(test_video_path, max_frames=15),
        sound_override="disabled",
    )
    uc.run()
    assert out.exists() and out.stat().st_size > 0
    cap = cv2.VideoCapture(str(out))
    try:
        count = 0
        while True:
            ok, _ = cap.read()
            if not ok:
                break
            count += 1
        assert count >= 15
    finally:
        cap.release()


@pytest.mark.timeout(30)
def test_pipeline_works_with_file_source_via_settings(test_video_path):
    # testa o caminho real _build_source(settings) com kind=file
    settings = AppSettings(
        headless=True,
        sinks=["log"],
        source=SourceSettings(kind="file", path=test_video_path, loop=False),
    )
    # FileVideoSource vai esgotar naturalmente após N frames do vídeo
    uc = build_monitor_use_case(settings=settings, sound_override="disabled")
    uc.run()  # roda até esgotar o arquivo
```

- [ ] **Step 2: Atualizar README**

Em `docs/README.md`, substitua a seção `## Uso` por:

```markdown
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
```

- [ ] **Step 3: Rodar suite completa**

Run: `pytest -q`
Expected: todos os testes passam (apenas os 2 de webcam podem pular).

- [ ] **Step 4: Verificar no-coauthor**

Run: `git log origin/main..HEAD --format=%B | grep -ic "co-author" || echo 0`
Expected: 0.

- [ ] **Step 5: Commit**

```bash
git add tests/e2e/test_bootstrap_pipeline.py docs/README.md
git commit -m "test(e2e): recording + source file via settings; docs: exemplos Fase 2"
```

---

## Critérios de aceitação da Fase 2

- [ ] `driver-fatigue run --source file:assets/test_sonolency.mp4` processa o vídeo
- [ ] `driver-fatigue run --source rtsp://...` tenta conectar e reconecta em falha (mock test)
- [ ] `--sinks http --config ...` posta JSON em webhook
- [ ] `--sinks mqtt --config ...` publica no broker
- [ ] `--record out.mp4` gera MP4 com overlay idêntico ao display
- [ ] `--headless` roda sem abrir janela
- [ ] Suite completa passa (>=70 testes)
- [ ] Nenhum commit com `Co-Authored-By:`
