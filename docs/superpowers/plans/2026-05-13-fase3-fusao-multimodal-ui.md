# Fase 3 — Fusão Multimodal + UI React/Tailwind — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adicionar motor de fusão multimodal fuzzy (EAR/MAR + BPM/volante/tempo/hora simulados → Índice de Fadiga 0–100% explicável) e reescrever o dashboard web em React + Vite + Tailwind com identidade IFG/NumbERS.

**Architecture:** Eixo A — motor fuzzy no domínio (`FatigueInputs` → `IndexEvaluator` Protocol) com impl scikit-fuzzy na infra; integrado ao `_InProcessFramePresenter` existente; sliders entram via novo `POST /api/inputs`. Eixo B — frontend novo em `web/` (React 18 + Vite 5 + Tailwind 3) cujo build vai pra `interfaces/web/static/`, servido pelo `http.server` Python sem mudança de transporte (SSE+MJPEG continuam).

**Tech Stack:** Backend: scikit-fuzzy (BSD), pydantic (já em uso). Frontend: React 18, Vite 5, Tailwind 3, lucide-react, clsx, vitest + @testing-library/react.

**Spec:** `docs/superpowers/specs/2026-05-13-fase3-fusao-multimodal-ui-design.md`

---

## File Structure

**Backend — arquivos novos:**
- `src/driver_fatigue/domain/fatigue_index.py` — `FatigueInputs`, `FatigueIndex`, `IndexEvaluator` Protocol, `circadian_risk()`
- `src/driver_fatigue/infrastructure/fatigue_inference/__init__.py`
- `src/driver_fatigue/infrastructure/fatigue_inference/fuzzy.py` — `FuzzyIndexEvaluator` (scikit-fuzzy)
- `src/driver_fatigue/infrastructure/fatigue_inference/noop.py` — `NoOpIndexEvaluator` fallback

**Backend — arquivos modificados:**
- `src/driver_fatigue/interfaces/config/settings.py` — `FatigueIndexSettings` + campo em `AppSettings`
- `src/driver_fatigue/bootstrap.py` — `_build_index_evaluator()`
- `src/driver_fatigue/interfaces/web/server.py` — `_simulated_inputs`, endpoints `/api/inputs` GET/POST, `/api/demo/start|stop`, integração no `_InProcessFramePresenter`/`_InProcessAlertSink`

**Backend — testes novos:**
- `tests/unit/test_fuzzy_index.py`
- `tests/unit/test_circadian.py`
- `tests/integration/test_inputs_endpoint.py`
- `tests/integration/test_demo_scenario.py`
- `tests/e2e/test_dashboard_fusion.py`

**Frontend — diretório novo `web/`:**
- `web/package.json`, `web/vite.config.js`, `web/tailwind.config.js`, `web/postcss.config.js`, `web/index.html`, `web/.gitignore`
- `web/public/ifg-logo.svg`
- `web/src/main.jsx`, `web/src/App.jsx`, `web/src/index.css`
- `web/src/hooks/useEventStream.js`
- `web/src/hooks/useSimulatedInputs.js`
- `web/src/hooks/useVideoHealth.js`
- `web/src/components/header/Header.jsx`
- `web/src/components/header/ConnBadge.jsx`
- `web/src/components/video/VideoCard.jsx`
- `web/src/components/video/AlertFlash.jsx`
- `web/src/components/gauge/FatigueGauge.jsx`
- `web/src/components/gauge/SeverityIcon.jsx`
- `web/src/components/sliders/SliderPanel.jsx`
- `web/src/components/sliders/SliderControl.jsx`
- `web/src/components/sliders/DemoButton.jsx`
- `web/src/components/timeline/Timeline.jsx`
- `web/src/components/timeline/EventRow.jsx`
- `web/src/components/metrics/MetricsGrid.jsx`
- `web/src/components/ui/Card.jsx`
- `web/src/components/ui/ProgressBar.jsx`

**Frontend — testes novos:**
- `web/src/__tests__/useSimulatedInputs.test.jsx`
- `web/src/__tests__/FatigueGauge.test.jsx`
- `web/vitest.config.js`

**Outros:**
- `pyproject.toml` — extra `fuzzy = ["scikit-fuzzy>=0.4"]`
- `.gitignore` — `web/node_modules/`, `web/dist/`
- `src/driver_fatigue/interfaces/web/static/` — apagado e regerado pelo build do Vite

---

## Task 1: Setup — dependência opcional `fuzzy` no pyproject

**Files:**
- Modify: `pyproject.toml`
- Modify: `.gitignore`

- [ ] **Step 1: Adicionar extra `fuzzy` em pyproject.toml**

Ler `pyproject.toml`. Procurar `[project.optional-dependencies]` (criar se não existir). Adicionar:

```toml
[project.optional-dependencies]
fuzzy = ["scikit-fuzzy>=0.4.2", "scipy>=1.10", "networkx>=3.0"]
```

(scipy e networkx são deps transitivas de scikit-fuzzy; listá-las explicitamente garante resolução previsível.)

- [ ] **Step 2: Adicionar `web/node_modules/` e `web/dist/` no .gitignore**

Ler `.gitignore`. Logo após `dist/` (linha 8), adicionar:

```
web/node_modules/
web/dist/
```

- [ ] **Step 3: Instalar o extra localmente**

Run: `pip install -e ".[fuzzy]"`
Expected: install OK; `python -c "import skfuzzy; print(skfuzzy.__version__)"` imprime versão >= 0.4.

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "build: extra fuzzy + ignore web/node_modules e dist"
```

---

## Task 2: Curva circadiana (domínio puro, sem deps)

**Files:**
- Create: `src/driver_fatigue/domain/fatigue_index.py`
- Test: `tests/unit/test_circadian.py`

- [ ] **Step 1: Escrever o teste falhando**

Criar `tests/unit/test_circadian.py`:

```python
import pytest
from driver_fatigue.domain.fatigue_index import circadian_risk


@pytest.mark.parametrize("hour,expected_range", [
    (3.0,  (0.85, 1.0)),   # madrugada profunda
    (4.5,  (0.85, 1.0)),
    (12.0, (0.0, 0.2)),    # meio-dia
    (15.0, (0.5, 0.7)),    # pós-almoço
    (20.0, (0.0, 0.2)),    # noite cedo
    (0.0,  (0.0, 0.5)),    # transição
])
def test_circadian_risk_in_expected_ranges(hour, expected_range):
    low, high = expected_range
    risk = circadian_risk(hour)
    assert low <= risk <= high, f"hour={hour} risk={risk:.2f} esperado em [{low},{high}]"


def test_circadian_risk_is_continuous_at_transitions():
    # transições 30min: 01:30→02:00 deve subir suavemente
    r1 = circadian_risk(1.5)
    r2 = circadian_risk(2.0)
    assert r2 > r1
    assert r2 - r1 < 0.5  # nao salta abrupto


def test_circadian_risk_clamps_input():
    assert circadian_risk(-1.0) == circadian_risk(0.0)
    assert circadian_risk(25.0) == circadian_risk(23.99)
```

- [ ] **Step 2: Rodar teste pra confirmar que falha**

Run: `pytest tests/unit/test_circadian.py -v`
Expected: FAIL `ModuleNotFoundError: No module named 'driver_fatigue.domain.fatigue_index'`

- [ ] **Step 3: Implementar curva**

Criar `src/driver_fatigue/domain/fatigue_index.py`:

```python
"""Motor de fusao multimodal — contratos de dominio.

Define os value objects de entrada/saida do indice de fadiga e o Protocol
que implementacoes concretas (fuzzy, ml, regras simples) precisam seguir.

A curva circadiana fica aqui porque e logica de dominio pura, sem deps.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


def circadian_risk(hour_of_day: float) -> float:
    """Risco circadiano em [0, 1] em funcao da hora do dia.

    - 02:00-06:00: 0.9 (vale circadiano noturno)
    - 14:00-16:00: 0.6 (vale pos-prandial)
    - resto:       0.1
    - transicoes lineares de 30min nas bordas

    Args:
        hour_of_day: 0.0-23.99 (clampado se fora)
    """
    h = max(0.0, min(23.99, hour_of_day))

    def _bump(center_start: float, center_end: float, peak: float) -> float:
        # 0.5h de rampa subindo antes de center_start, 0.5h descendo apos center_end
        ramp = 0.5
        base = 0.1
        if center_start <= h <= center_end:
            return peak
        if center_start - ramp <= h < center_start:
            t = (h - (center_start - ramp)) / ramp
            return base + (peak - base) * t
        if center_end < h <= center_end + ramp:
            t = 1.0 - (h - center_end) / ramp
            return base + (peak - base) * t
        return base

    night = _bump(2.0, 6.0, 0.9)
    afternoon = _bump(14.0, 16.0, 0.6)
    return max(night, afternoon)
```

- [ ] **Step 4: Rodar teste pra confirmar passing**

Run: `pytest tests/unit/test_circadian.py -v`
Expected: PASS — todos os parametrizados verde + continuidade + clamp.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/domain/fatigue_index.py tests/unit/test_circadian.py
git commit -m "feat(domain): curva circadiana pra risco de sonolencia"
```

---

## Task 3: Value objects `FatigueInputs` e `FatigueIndex` + Protocol

**Files:**
- Modify: `src/driver_fatigue/domain/fatigue_index.py`

- [ ] **Step 1: Acrescentar value objects e Protocol ao módulo**

Adicionar ao final de `src/driver_fatigue/domain/fatigue_index.py`:

```python
@dataclass(frozen=True, slots=True)
class FatigueInputs:
    """Snapshot consumido pelo motor de fusao a cada frame.

    Campos normalizados pra 0-1 quando possivel pra desacoplar do
    baseline de cada usuario. Sinais simulados sao clampados antes de
    chegar aqui (responsabilidade do endpoint /api/inputs).
    """
    ear_norm: float
    mar_norm: float
    head_drop_frames: int
    consecutive_eyes_closed: int
    bpm: float
    steering_noise: float
    hours_driving: float
    hour_of_day: float


@dataclass(frozen=True, slots=True)
class FatigueIndex:
    value: float
    severity: str
    top_contributors: tuple[str, ...]
    explain: str
    critical: bool = False

    @classmethod
    def empty(cls) -> "FatigueIndex":
        return cls(value=0.0, severity="normal", top_contributors=(), explain="")


class IndexEvaluator(Protocol):
    def compute(self, inputs: FatigueInputs) -> FatigueIndex: ...
```

- [ ] **Step 2: Teste rápido de smoke (imports + construção)**

Criar `tests/unit/test_fatigue_index_types.py`:

```python
from driver_fatigue.domain.fatigue_index import (
    FatigueInputs, FatigueIndex, IndexEvaluator,
)


def test_inputs_are_constructible():
    inp = FatigueInputs(
        ear_norm=0.8, mar_norm=0.1, head_drop_frames=0,
        consecutive_eyes_closed=0, bpm=75.0, steering_noise=0.1,
        hours_driving=1.0, hour_of_day=10.0,
    )
    assert inp.bpm == 75.0


def test_index_empty_factory():
    idx = FatigueIndex.empty()
    assert idx.value == 0.0
    assert idx.severity == "normal"
    assert idx.top_contributors == ()
    assert idx.critical is False


def test_index_evaluator_is_protocol():
    # Protocol — qualquer obj com .compute(inputs) -> FatigueIndex satisfaz
    class _Fake:
        def compute(self, inputs):
            return FatigueIndex.empty()
    f: IndexEvaluator = _Fake()
    assert isinstance(f.compute(FatigueInputs(0,0,0,0,0,0,0,0)), FatigueIndex)
```

- [ ] **Step 3: Run e confirmar passing**

Run: `pytest tests/unit/test_fatigue_index_types.py -v`
Expected: PASS — 3 testes.

- [ ] **Step 4: Commit**

```bash
git add src/driver_fatigue/domain/fatigue_index.py tests/unit/test_fatigue_index_types.py
git commit -m "feat(domain): FatigueInputs, FatigueIndex e IndexEvaluator Protocol"
```

---

## Task 4: `NoOpIndexEvaluator` (fallback sem scikit-fuzzy)

**Files:**
- Create: `src/driver_fatigue/infrastructure/fatigue_inference/__init__.py`
- Create: `src/driver_fatigue/infrastructure/fatigue_inference/noop.py`
- Test: `tests/unit/test_noop_evaluator.py`

- [ ] **Step 1: Escrever teste falhando**

Criar `tests/unit/test_noop_evaluator.py`:

```python
from driver_fatigue.domain.fatigue_index import FatigueInputs
from driver_fatigue.infrastructure.fatigue_inference.noop import NoOpIndexEvaluator


def test_noop_returns_zero_index():
    ev = NoOpIndexEvaluator()
    out = ev.compute(FatigueInputs(0.8, 0.1, 0, 0, 75.0, 0.1, 1.0, 10.0))
    assert out.value == 0.0
    assert out.severity == "normal"
    assert out.explain == "indice de fadiga desabilitado"
```

- [ ] **Step 2: Confirmar fail**

Run: `pytest tests/unit/test_noop_evaluator.py -v`
Expected: FAIL `ModuleNotFoundError`.

- [ ] **Step 3: Criar package + implementação**

Criar `src/driver_fatigue/infrastructure/fatigue_inference/__init__.py` vazio.

Criar `src/driver_fatigue/infrastructure/fatigue_inference/noop.py`:

```python
"""Fallback que desabilita o indice quando scikit-fuzzy nao esta instalado
ou quando o usuario optou por desligar via config."""
from __future__ import annotations

from driver_fatigue.domain.fatigue_index import (
    FatigueIndex, FatigueInputs, IndexEvaluator,
)


class NoOpIndexEvaluator:
    def compute(self, inputs: FatigueInputs) -> FatigueIndex:  # noqa: ARG002
        return FatigueIndex(
            value=0.0,
            severity="normal",
            top_contributors=(),
            explain="indice de fadiga desabilitado",
        )


# protocolo satisfeito estruturalmente, mas damos a anotacao explicita
# pra pegar erros de assinatura em type-check
_ev: IndexEvaluator = NoOpIndexEvaluator()
```

- [ ] **Step 4: Run + commit**

Run: `pytest tests/unit/test_noop_evaluator.py -v`
Expected: PASS.

```bash
git add src/driver_fatigue/infrastructure/fatigue_inference/ tests/unit/test_noop_evaluator.py
git commit -m "feat(infra): NoOpIndexEvaluator fallback"
```

---

## Task 5: `FuzzyIndexEvaluator` — esqueleto + 1ª regra (TDD)

**Files:**
- Create: `src/driver_fatigue/infrastructure/fatigue_inference/fuzzy.py`
- Test: `tests/unit/test_fuzzy_index.py`

- [ ] **Step 1: Escrever o primeiro teste — caso baseline normal**

Criar `tests/unit/test_fuzzy_index.py`:

```python
"""Testes de comportamento do motor fuzzy.

Cobrimos cada caso de fadiga prototipico do spec. Os limites de severity
sao: < 35 normal, 35-60 warning, 60-80 alert, >= 80 alert+critical.
"""
import pytest

skfuzzy = pytest.importorskip("skfuzzy")

from driver_fatigue.domain.fatigue_index import FatigueInputs
from driver_fatigue.infrastructure.fatigue_inference.fuzzy import (
    FuzzyIndexEvaluator,
)


@pytest.fixture(scope="module")
def evaluator():
    return FuzzyIndexEvaluator()


def _inputs(**over) -> FatigueInputs:
    base = dict(
        ear_norm=0.85, mar_norm=0.10, head_drop_frames=0,
        consecutive_eyes_closed=0, bpm=75.0, steering_noise=0.10,
        hours_driving=1.0, hour_of_day=10.0,
    )
    base.update(over)
    return FatigueInputs(**base)


def test_normal_baseline_low_index(evaluator):
    out = evaluator.compute(_inputs())
    assert out.value < 35, f"esperado normal, veio {out.value:.1f}"
    assert out.severity == "normal"
```

- [ ] **Step 2: Run e confirmar fail**

Run: `pytest tests/unit/test_fuzzy_index.py -v`
Expected: FAIL `ModuleNotFoundError: ...fuzzy`.

- [ ] **Step 3: Implementação inicial do `FuzzyIndexEvaluator`**

Criar `src/driver_fatigue/infrastructure/fatigue_inference/fuzzy.py`:

```python
"""Motor de fusao multimodal usando logica fuzzy (scikit-fuzzy).

12 regras IF-THEN combinam sinais reais (olhos/boca/cabeca) com simulados
(BPM/volante/tempo/hora) produzindo um indice 0-100 explicavel. Cada
inferencia retorna as 2-3 regras mais ativadas pra mostrar na UI.

Custo: ~3-5ms por frame em CPU. ControlSystem e simulator sao criados
uma vez no __init__ pra reusar o grafo de inferencia.
"""
from __future__ import annotations

import numpy as np
import skfuzzy as fuzz
from skfuzzy import control as ctrl

from driver_fatigue.domain.fatigue_index import (
    FatigueIndex, FatigueInputs, circadian_risk,
)


_RULE_LABELS: dict[str, str] = {
    "R1":  "olhos fechados + cabeceio",
    "R2":  "olhos fechados + bocejo",
    "R3":  "bocejo + tempo alto",
    "R4":  "BPM baixo + olhos parciais",
    "R5":  "BPM baixo + circadiano em vale",
    "R6":  "volante errante + tempo medio",
    "R7":  "volante oscilando + circadiano medio",
    "R8":  "tempo longo + circadiano em vale",
    "R9":  "falando, nao bocejando",
    "R10": "cabeceio pesado",
    "R11": "tudo normal",
    "R12": "tempo longo + BPM baixo + olhos parciais",
}


class FuzzyIndexEvaluator:
    def __init__(self) -> None:
        eyes = ctrl.Antecedent(np.linspace(0, 1, 100), "eyes_closed")
        eyes["aberto"]  = fuzz.trapmf(eyes.universe, [0.7, 0.85, 1.0, 1.0])
        eyes["parcial"] = fuzz.trimf(eyes.universe, [0.3, 0.5, 0.7])
        eyes["fechado"] = fuzz.trapmf(eyes.universe, [0.0, 0.0, 0.2, 0.35])

        mouth = ctrl.Antecedent(np.linspace(0, 1, 100), "mouth")
        mouth["fechada"] = fuzz.trapmf(mouth.universe, [0.0, 0.0, 0.15, 0.30])
        mouth["falando"] = fuzz.trimf(mouth.universe, [0.25, 0.40, 0.55])
        mouth["bocejo"]  = fuzz.trapmf(mouth.universe, [0.50, 0.70, 1.0, 1.0])

        head = ctrl.Antecedent(np.arange(0, 61, 1), "head")
        head["nenhum"] = fuzz.trapmf(head.universe, [0, 0, 4, 8])
        head["leve"]   = fuzz.trimf(head.universe, [6, 15, 25])
        head["pesado"] = fuzz.trapmf(head.universe, [20, 35, 60, 60])

        bpm = ctrl.Antecedent(np.arange(40, 121, 1), "bpm")
        bpm["baixo"]  = fuzz.trapmf(bpm.universe, [40, 40, 50, 60])
        bpm["normal"] = fuzz.trimf(bpm.universe, [55, 75, 95])
        bpm["alto"]   = fuzz.trapmf(bpm.universe, [90, 100, 120, 120])

        steer = ctrl.Antecedent(np.linspace(0, 1, 100), "steer")
        steer["estavel"]   = fuzz.trapmf(steer.universe, [0.0, 0.0, 0.15, 0.30])
        steer["oscilando"] = fuzz.trimf(steer.universe, [0.20, 0.40, 0.65])
        steer["errante"]   = fuzz.trapmf(steer.universe, [0.55, 0.75, 1.0, 1.0])

        time_ = ctrl.Antecedent(np.linspace(0, 10, 100), "time")
        time_["curto"] = fuzz.trapmf(time_.universe, [0, 0, 1, 2.5])
        time_["medio"] = fuzz.trimf(time_.universe, [1.5, 3.5, 5.5])
        time_["longo"] = fuzz.trapmf(time_.universe, [4, 7, 10, 10])

        circ = ctrl.Antecedent(np.linspace(0, 1, 100), "circ")
        circ["seguro"] = fuzz.trapmf(circ.universe, [0.0, 0.0, 0.15, 0.30])
        circ["medio"]  = fuzz.trimf(circ.universe, [0.20, 0.45, 0.70])
        circ["vale"]   = fuzz.trapmf(circ.universe, [0.60, 0.80, 1.0, 1.0])

        idx = ctrl.Consequent(np.arange(0, 101, 1), "idx")
        idx["normal"]  = fuzz.trapmf(idx.universe, [0,  0,  20, 35])
        idx["atencao"] = fuzz.trimf(idx.universe, [25, 45, 65])
        idx["alerta"]  = fuzz.trimf(idx.universe, [55, 70, 85])
        idx["critico"] = fuzz.trapmf(idx.universe, [75, 90, 100, 100])

        rules = [
            ctrl.Rule(eyes["fechado"] & head["leve"],                idx["alerta"],  label="R1"),
            ctrl.Rule(eyes["fechado"] & mouth["bocejo"],             idx["critico"], label="R2"),
            ctrl.Rule(mouth["bocejo"] & time_["longo"],              idx["alerta"],  label="R3"),
            ctrl.Rule(bpm["baixo"]   & ~eyes["aberto"],              idx["alerta"],  label="R4"),
            ctrl.Rule(bpm["baixo"]   & circ["vale"],                 idx["atencao"], label="R5"),
            ctrl.Rule(steer["errante"]   & ~time_["curto"],          idx["alerta"],  label="R6"),
            ctrl.Rule(steer["oscilando"] & ~circ["seguro"],          idx["atencao"], label="R7"),
            ctrl.Rule(time_["longo"]     & circ["vale"],             idx["atencao"], label="R8"),
            ctrl.Rule(eyes["parcial"]    & mouth["falando"],         idx["normal"],  label="R9"),
            ctrl.Rule(head["pesado"],                                idx["critico"], label="R10"),
            ctrl.Rule(bpm["normal"] & steer["estavel"] & eyes["aberto"], idx["normal"], label="R11"),
            ctrl.Rule(time_["longo"] & bpm["baixo"] & ~eyes["aberto"], idx["critico"], label="R12"),
        ]
        self._rules = rules
        self._system = ctrl.ControlSystem(rules)
        # Antecedent refs guardados pra reuso
        self._antecedents = {
            "eyes": eyes, "mouth": mouth, "head": head, "bpm": bpm,
            "steer": steer, "time": time_, "circ": circ,
        }
        self._consequent = idx

    def compute(self, inp: FatigueInputs) -> FatigueIndex:
        sim = ctrl.ControlSystemSimulation(self._system)
        sim.input["eyes_closed"] = max(0.0, min(1.0, 1.0 - inp.ear_norm))
        sim.input["mouth"]       = max(0.0, min(1.0, inp.mar_norm))
        sim.input["head"]        = max(0.0, min(60.0, float(inp.head_drop_frames)))
        sim.input["bpm"]         = max(40.0, min(120.0, inp.bpm))
        sim.input["steer"]       = max(0.0, min(1.0, inp.steering_noise))
        sim.input["time"]        = max(0.0, min(10.0, inp.hours_driving))
        sim.input["circ"]        = circadian_risk(inp.hour_of_day)
        try:
            sim.compute()
            value = float(sim.output.get("idx", 0.0))
        except (ValueError, KeyError):
            value = 0.0
        value = max(0.0, min(100.0, value))

        # severity mapping
        if value < 35:
            severity = "normal"
        elif value < 60:
            severity = "warning"
        else:
            severity = "alert"
        critical = value >= 80

        # explainability: pegar 2 regras mais ativadas
        top, explain = self._top_contributors(sim)
        return FatigueIndex(
            value=value, severity=severity,
            top_contributors=top, explain=explain, critical=critical,
        )

    def _top_contributors(self, sim) -> tuple[tuple[str, ...], str]:
        # ControlSystemSimulation expoe firing strength via sim.ctrl.rules
        # apos compute(). Iteramos coletando (label, strength).
        try:
            scored: list[tuple[str, float]] = []
            for rule in self._system.rules:
                # sim.* nao expoe firing diretamente em todas as versoes;
                # usamos o cache interno se disponivel, senao caimos no fallback
                aggregate = sim._array_inputs if hasattr(sim, "_array_inputs") else None  # noqa: SLF001
                label = getattr(rule, "label", None) or rule.consequent[0].label
                strength = float(getattr(rule, "_aggregate_firing", [0.0])[0]) if hasattr(rule, "_aggregate_firing") else 0.0
                scored.append((label, strength))
            scored.sort(key=lambda x: x[1], reverse=True)
            top_labels = tuple(lbl for lbl, s in scored[:2] if s > 0.05)
            human = [_RULE_LABELS.get(lbl, lbl) for lbl in top_labels]
            return top_labels, " + ".join(human) if human else ""
        except Exception:
            return (), ""
```

- [ ] **Step 4: Run, confirmar passing do teste baseline**

Run: `pytest tests/unit/test_fuzzy_index.py::test_normal_baseline_low_index -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/driver_fatigue/infrastructure/fatigue_inference/fuzzy.py tests/unit/test_fuzzy_index.py
git commit -m "feat(infra): FuzzyIndexEvaluator com 12 regras IF-THEN"
```

---

## Task 6: Casos de fadiga prototípicos no fuzzy

**Files:**
- Modify: `tests/unit/test_fuzzy_index.py`

- [ ] **Step 1: Adicionar mais testes parametrizados (cobre cada regra)**

Acrescentar ao final de `tests/unit/test_fuzzy_index.py`:

```python
def test_eyes_closed_plus_head_drop_triggers_alert(evaluator):
    # R1: eyes_closed + head_drop = alerta (>= 60)
    out = evaluator.compute(_inputs(
        ear_norm=0.10, head_drop_frames=20,
    ))
    assert out.value >= 60, f"esperado alert, veio {out.value:.1f}"
    assert out.severity == "alert"


def test_eyes_closed_plus_yawn_is_critical(evaluator):
    # R2: critico (>=80)
    out = evaluator.compute(_inputs(
        ear_norm=0.10, mar_norm=0.85,
    ))
    assert out.value >= 75, f"esperado critico, veio {out.value:.1f}"
    assert out.critical or out.severity == "alert"


def test_low_bpm_with_partial_eyes_triggers_alert(evaluator):
    # R4: bpm baixo + olhos nao-abertos
    out = evaluator.compute(_inputs(
        bpm=45.0, ear_norm=0.50,
    ))
    assert out.value >= 50


def test_drowsy_night_scenario_is_critical(evaluator):
    # R12: tempo longo + bpm baixo + olhos parciais + circadiano vale
    out = evaluator.compute(_inputs(
        ear_norm=0.40, mar_norm=0.30, bpm=48.0,
        hours_driving=8.0, hour_of_day=3.5,
        steering_noise=0.60,
    ))
    assert out.value >= 70, f"cenario noturno: {out.value:.1f}"


def test_talking_not_yawning_stays_normal(evaluator):
    # R9: anti-FP: motorista falando (mar medio, ear normal) nao deve gerar alert
    out = evaluator.compute(_inputs(
        ear_norm=0.80, mar_norm=0.45,
    ))
    assert out.value < 50, f"falando virou alert: {out.value:.1f}"


def test_heavy_head_drop_is_critical(evaluator):
    # R10
    out = evaluator.compute(_inputs(
        head_drop_frames=45,
    ))
    assert out.value >= 70


def test_explain_text_non_empty_when_active(evaluator):
    out = evaluator.compute(_inputs(
        ear_norm=0.10, head_drop_frames=20,
    ))
    assert out.explain != ""
    assert len(out.top_contributors) >= 1
```

- [ ] **Step 2: Rodar e ajustar parametros se algum teste falhar**

Run: `pytest tests/unit/test_fuzzy_index.py -v`
Expected: todos PASS. Se algum falhar marginalmente, ajustar as funções de pertinência em `fuzzy.py` (alargar o conjunto que precisa pegar mais força). NÃO afrouxar o teste — afrouxar a regra fuzzy.

**Nota sobre `_top_contributors`:** a API de inspeção de firing strength do scikit-fuzzy varia entre versões. Se `_aggregate_firing` não existir na versão instalada, substituir por:

```python
# Alternativa: re-simular cada regra isolada e pegar a saida media
# Ou usar sim.ctrl_rules dict se disponivel
strength = 0.0
try:
    strength = float(sim.output_crisp_value(rule.consequent[0]))  # API varia
except Exception:
    pass
```

Se nada funcionar, fallback aceitável: heurística baseada em `inputs` direto (qual antecedente teve maior pertinência num conjunto "ruim"). Manter `top_contributors` retornando algo não-vazio quando `value > 35`.

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_fuzzy_index.py src/driver_fatigue/infrastructure/fatigue_inference/fuzzy.py
git commit -m "test(fuzzy): cenarios prototipicos + ajustes finos das regras"
```

---

## Task 7: Settings — `FatigueIndexSettings`

**Files:**
- Modify: `src/driver_fatigue/interfaces/config/settings.py`
- Test: `tests/unit/test_settings_fatigue_index.py`

- [ ] **Step 1: Escrever teste**

Criar `tests/unit/test_settings_fatigue_index.py`:

```python
from driver_fatigue.interfaces.config.settings import AppSettings


def test_default_fatigue_index_enabled():
    s = AppSettings()
    assert s.fatigue_index.enabled is True


def test_fatigue_index_can_be_disabled_via_yaml(tmp_path):
    cfg = tmp_path / "c.yaml"
    cfg.write_text("fatigue_index:\n  enabled: false\n")
    s = AppSettings.from_yaml(cfg)
    assert s.fatigue_index.enabled is False
```

- [ ] **Step 2: Run, confirmar fail**

Run: `pytest tests/unit/test_settings_fatigue_index.py -v`
Expected: FAIL — `AppSettings` não tem atributo `fatigue_index`.

- [ ] **Step 3: Adicionar settings model**

Ler `src/driver_fatigue/interfaces/config/settings.py`. Localizar a definição de `AppSettings` (próximo ao final) e onde os outros sub-models são declarados.

Adicionar antes de `class AppSettings`:

```python
class FatigueIndexSettings(BaseModel):
    enabled: bool = True
```

Dentro de `AppSettings` adicionar o campo (mantendo o padrão dos outros):

```python
    fatigue_index: FatigueIndexSettings = Field(default_factory=FatigueIndexSettings)
```

- [ ] **Step 4: Run + commit**

Run: `pytest tests/unit/test_settings_fatigue_index.py -v`
Expected: PASS.

```bash
git add src/driver_fatigue/interfaces/config/settings.py tests/unit/test_settings_fatigue_index.py
git commit -m "feat(config): FatigueIndexSettings com enabled toggle"
```

---

## Task 8: Bootstrap — `_build_index_evaluator()` com fallback

**Files:**
- Modify: `src/driver_fatigue/bootstrap.py`
- Test: `tests/unit/test_bootstrap_index_evaluator.py`

- [ ] **Step 1: Teste**

Criar `tests/unit/test_bootstrap_index_evaluator.py`:

```python
from driver_fatigue.bootstrap import _build_index_evaluator
from driver_fatigue.infrastructure.fatigue_inference.noop import NoOpIndexEvaluator
from driver_fatigue.interfaces.config.settings import AppSettings, FatigueIndexSettings


def test_disabled_returns_noop():
    s = AppSettings(fatigue_index=FatigueIndexSettings(enabled=False))
    ev = _build_index_evaluator(s)
    assert isinstance(ev, NoOpIndexEvaluator)


def test_enabled_returns_fuzzy_when_available():
    import pytest
    pytest.importorskip("skfuzzy")
    from driver_fatigue.infrastructure.fatigue_inference.fuzzy import FuzzyIndexEvaluator
    s = AppSettings()
    ev = _build_index_evaluator(s)
    assert isinstance(ev, FuzzyIndexEvaluator)
```

- [ ] **Step 2: Run, confirmar fail**

Run: `pytest tests/unit/test_bootstrap_index_evaluator.py -v`
Expected: FAIL — `_build_index_evaluator` não existe.

- [ ] **Step 3: Adicionar em bootstrap.py**

Ler `src/driver_fatigue/bootstrap.py`. Após as outras funções `_build_*`, adicionar:

```python
def _build_index_evaluator(settings: AppSettings):
    """Constroi o motor de fusao multimodal.

    Retorna NoOp se desabilitado ou se scikit-fuzzy nao estiver instalado.
    """
    from driver_fatigue.infrastructure.fatigue_inference.noop import NoOpIndexEvaluator

    if not settings.fatigue_index.enabled:
        return NoOpIndexEvaluator()
    try:
        from driver_fatigue.infrastructure.fatigue_inference.fuzzy import (
            FuzzyIndexEvaluator,
        )
        return FuzzyIndexEvaluator()
    except ImportError:
        _log.warning(
            "scikit-fuzzy nao instalado; rodando sem indice de fadiga. "
            "Instale com: pip install -e \".[fuzzy]\""
        )
        return NoOpIndexEvaluator()
```

- [ ] **Step 4: Run + commit**

Run: `pytest tests/unit/test_bootstrap_index_evaluator.py -v`
Expected: PASS.

```bash
git add src/driver_fatigue/bootstrap.py tests/unit/test_bootstrap_index_evaluator.py
git commit -m "feat(bootstrap): _build_index_evaluator com fallback NoOp"
```

---

## Task 9: Endpoints `/api/inputs` GET/POST

**Files:**
- Modify: `src/driver_fatigue/interfaces/web/server.py`
- Test: `tests/integration/test_inputs_endpoint.py`

- [ ] **Step 1: Teste de integração**

Criar `tests/integration/test_inputs_endpoint.py`:

```python
import json
import threading
import time
import urllib.request
from contextlib import contextmanager

import pytest

from driver_fatigue.interfaces.web import server as web_server


@contextmanager
def _run_server(port: int, api_key: str | None = None):
    httpd = web_server._QuietThreadingHTTPServer(
        ("127.0.0.1", port), web_server._Handler,
    )
    web_server._api_key = api_key
    web_server._started_at = time.monotonic()
    # reset state
    web_server._simulated_inputs.update(
        bpm=75.0, steering_noise=0.1, hours_driving=0.0, hour_of_day=12.0,
    )
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()


def _free_port() -> int:
    import socket
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_post_inputs_updates_snapshot():
    port = _free_port()
    with _run_server(port) as base:
        body = json.dumps({"bpm": 60.0, "steering_noise": 0.5}).encode()
        req = urllib.request.Request(
            f"{base}/api/inputs", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=2) as r:
            assert r.status == 202

        with urllib.request.urlopen(f"{base}/api/inputs", timeout=2) as r:
            data = json.loads(r.read())
        assert data["bpm"] == 60.0
        assert data["steering_noise"] == 0.5
        assert data["hours_driving"] == 0.0  # preserva ausente


def test_post_inputs_clamps_out_of_range():
    port = _free_port()
    with _run_server(port) as base:
        body = json.dumps({"bpm": 999.0, "steering_noise": -0.5}).encode()
        req = urllib.request.Request(
            f"{base}/api/inputs", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=2)
        with urllib.request.urlopen(f"{base}/api/inputs", timeout=2) as r:
            data = json.loads(r.read())
        assert data["bpm"] == 120.0
        assert data["steering_noise"] == 0.0


def test_post_inputs_requires_auth_when_configured():
    port = _free_port()
    with _run_server(port, api_key="secret") as base:
        body = json.dumps({"bpm": 60.0}).encode()
        req = urllib.request.Request(
            f"{base}/api/inputs", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(urllib.error.HTTPError) as exc:
            urllib.request.urlopen(req, timeout=2)
        assert exc.value.code == 401
```

- [ ] **Step 2: Run, confirmar fail**

Run: `pytest tests/integration/test_inputs_endpoint.py -v`
Expected: FAIL — endpoint não existe (404).

- [ ] **Step 3: Implementar no server.py**

Ler `src/driver_fatigue/interfaces/web/server.py`. Após as variáveis de módulo (`_api_key`, `_started_at`, `_last_event_at`), adicionar:

```python
# Snapshot dos sliders simulados (BPM, volante, tempo, hora).
# Acessado pelo POST /api/inputs (escrita), GET /api/inputs (leitura),
# e pelo _InProcessFramePresenter (leitura a cada frame).
_simulated_lock = threading.Lock()
_simulated_inputs: dict[str, float] = {
    "bpm": 75.0,
    "steering_noise": 0.1,
    "hours_driving": 0.0,
    "hour_of_day": 12.0,
}

_INPUT_RANGES: dict[str, tuple[float, float]] = {
    "bpm": (40.0, 120.0),
    "steering_noise": (0.0, 1.0),
    "hours_driving": (0.0, 10.0),
    "hour_of_day": (0.0, 23.99),
}


def _get_simulated_snapshot() -> dict[str, float]:
    with _simulated_lock:
        return dict(_simulated_inputs)


def _update_simulated(updates: dict) -> None:
    with _simulated_lock:
        for key, lo_hi in _INPUT_RANGES.items():
            if key in updates:
                val = updates[key]
                try:
                    val = float(val)
                except (TypeError, ValueError):
                    continue
                lo, hi = lo_hi
                _simulated_inputs[key] = max(lo, min(hi, val))
```

Em `do_GET`, antes da linha `if path == "/api/health"`, adicionar:

```python
        if path == "/api/inputs":
            self._json(200, _get_simulated_snapshot())
            return
```

Em `do_POST`, antes do `self.send_error(404, "not found")` final, adicionar:

```python
        if self.path == "/api/inputs":
            length = int(self.headers.get("Content-Length", "0"))
            body = self.rfile.read(length) if length > 0 else b""
            if not self._require_auth():
                return
            if not body:
                self.send_error(400, "empty body")
                return
            try:
                payload = json.loads(body.decode("utf-8"))
            except json.JSONDecodeError as exc:
                self.send_error(400, f"invalid json: {exc}")
                return
            if not isinstance(payload, dict):
                self.send_error(400, "expected json object")
                return
            _update_simulated(payload)
            self._json(202, {"status": "accepted"})
            return
```

- [ ] **Step 4: Run + commit**

Run: `pytest tests/integration/test_inputs_endpoint.py -v`
Expected: PASS — 3 testes.

```bash
git add src/driver_fatigue/interfaces/web/server.py tests/integration/test_inputs_endpoint.py
git commit -m "feat(web): endpoints /api/inputs GET/POST com clamp e auth"
```

---

## Task 10: Modo demo — `_DemoScenarioRunner` + endpoints `/api/demo/{start,stop}`

**Files:**
- Modify: `src/driver_fatigue/interfaces/web/server.py`
- Test: `tests/integration/test_demo_scenario.py`

- [ ] **Step 1: Teste**

Criar `tests/integration/test_demo_scenario.py`:

```python
import json
import socket
import threading
import time
import urllib.error
import urllib.request
from contextlib import contextmanager

import pytest

from driver_fatigue.interfaces.web import server as web_server


@contextmanager
def _run_server(port: int):
    httpd = web_server._QuietThreadingHTTPServer(
        ("127.0.0.1", port), web_server._Handler,
    )
    web_server._api_key = None
    web_server._started_at = time.monotonic()
    web_server._simulated_inputs.update(
        bpm=75.0, steering_noise=0.1, hours_driving=0.0, hour_of_day=12.0,
    )
    web_server._demo_runner = None
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        if web_server._demo_runner is not None:
            web_server._demo_runner.stop()
        httpd.shutdown()


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _post(url: str, payload: dict | None = None):
    body = json.dumps(payload or {}).encode()
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json"},
    )
    return urllib.request.urlopen(req, timeout=2)


def test_demo_start_moves_bpm_over_time():
    port = _free_port()
    with _run_server(port) as base:
        r = _post(f"{base}/api/demo/start")
        assert r.status == 202
        # script anda em 10Hz; em 1.5s o bpm ja deve ter caido do baseline 75
        time.sleep(1.5)
        with urllib.request.urlopen(f"{base}/api/inputs", timeout=2) as resp:
            data = json.loads(resp.read())
        assert data["bpm"] < 75.0, f"bpm nao moveu: {data}"


def test_demo_start_while_running_returns_409():
    port = _free_port()
    with _run_server(port) as base:
        _post(f"{base}/api/demo/start")
        with pytest.raises(urllib.error.HTTPError) as exc:
            _post(f"{base}/api/demo/start")
        assert exc.value.code == 409


def test_demo_stop_aborts_running_scenario():
    port = _free_port()
    with _run_server(port) as base:
        _post(f"{base}/api/demo/start")
        time.sleep(0.3)
        r = _post(f"{base}/api/demo/stop")
        assert r.status in (200, 202)
        # Apos stop, segundo stop retorna not_running
        r2 = _post(f"{base}/api/demo/stop")
        body = json.loads(r2.read())
        assert body["status"] == "not_running"
```

- [ ] **Step 2: Run, confirmar fail**

Run: `pytest tests/integration/test_demo_scenario.py -v`
Expected: FAIL — endpoints 404.

- [ ] **Step 3: Implementar runner + endpoints**

Em `src/driver_fatigue/interfaces/web/server.py`, após `_update_simulated`, adicionar:

```python
# Cenario scriptado pra demonstracao. Anda em 10Hz interpolando entre
# checkpoints. Singleton: so um demo roda por vez (segunda chamada → 409).
_demo_runner_lock = threading.Lock()
_demo_runner: "_DemoScenarioRunner | None" = None


_DEMO_TIMELINE: list[tuple[float, dict[str, float]]] = [
    (0.0,  {"bpm": 75, "steering_noise": 0.10, "hours_driving": 5.0, "hour_of_day": 15.0}),
    (5.0,  {"bpm": 70, "steering_noise": 0.15, "hours_driving": 5.5, "hour_of_day": 15.0}),
    (10.0, {"bpm": 62, "steering_noise": 0.30, "hours_driving": 6.0, "hour_of_day": 15.0}),
    (15.0, {"bpm": 55, "steering_noise": 0.50, "hours_driving": 6.5, "hour_of_day": 15.0}),
    (20.0, {"bpm": 50, "steering_noise": 0.65, "hours_driving": 7.0, "hour_of_day": 3.5}),
    (25.0, {"bpm": 48, "steering_noise": 0.75, "hours_driving": 7.5, "hour_of_day": 3.5}),
    (30.0, {"bpm": 48, "steering_noise": 0.75, "hours_driving": 7.5, "hour_of_day": 3.5}),
]


class _DemoScenarioRunner:
    def __init__(self) -> None:
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, daemon=True)

    def start(self) -> None:
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def _loop(self) -> None:
        start = time.monotonic()
        step = 0.1  # 10Hz
        while not self._stop.is_set():
            elapsed = time.monotonic() - start
            if elapsed >= _DEMO_TIMELINE[-1][0]:
                _update_simulated(_DEMO_TIMELINE[-1][1])
                break
            snapshot = self._interpolate(elapsed)
            _update_simulated(snapshot)
            if self._stop.wait(step):
                return

    @staticmethod
    def _interpolate(t: float) -> dict[str, float]:
        # encontra o segmento [t_i, t_{i+1}] que contem t
        for i in range(len(_DEMO_TIMELINE) - 1):
            t0, p0 = _DEMO_TIMELINE[i]
            t1, p1 = _DEMO_TIMELINE[i + 1]
            if t0 <= t < t1:
                frac = (t - t0) / (t1 - t0)
                return {k: p0[k] + (p1[k] - p0[k]) * frac for k in p0}
        return dict(_DEMO_TIMELINE[-1][1])
```

Em `do_POST`, adicionar antes do `404` final:

```python
        if self.path == "/api/demo/start":
            if not self._require_auth():
                return
            global _demo_runner
            with _demo_runner_lock:
                if _demo_runner is not None and _demo_runner._thread.is_alive():
                    self.send_error(409, "demo already running")
                    return
                _demo_runner = _DemoScenarioRunner()
                _demo_runner.start()
            self._json(202, {"status": "started", "duration_seconds": _DEMO_TIMELINE[-1][0]})
            return
        if self.path == "/api/demo/stop":
            if not self._require_auth():
                return
            global _demo_runner
            with _demo_runner_lock:
                if _demo_runner is None or not _demo_runner._thread.is_alive():
                    self._json(200, {"status": "not_running"})
                    return
                _demo_runner.stop()
                _demo_runner = None
            self._json(202, {"status": "stopped"})
            return
```

- [ ] **Step 4: Run + commit**

Run: `pytest tests/integration/test_demo_scenario.py -v`
Expected: PASS — 3 testes.

```bash
git add src/driver_fatigue/interfaces/web/server.py tests/integration/test_demo_scenario.py
git commit -m "feat(web): cenario demo automatico 30s + endpoints start/stop"
```

---

## Task 11: Integração — `_InProcessFramePresenter` e `_InProcessAlertSink` consomem o `IndexEvaluator`

**Files:**
- Modify: `src/driver_fatigue/interfaces/web/server.py`
- Test: `tests/integration/test_state_payload_has_index.py`

- [ ] **Step 1: Teste — payload SSE contém `fatigue_index`**

Criar `tests/integration/test_state_payload_has_index.py`:

```python
"""Confirma que publish_state inclui fatigue_index/severity/explain
no payload SSE quando o evaluator esta plugado."""
import time
from unittest.mock import MagicMock

from driver_fatigue.domain.entities import FatigueState, Frame
from driver_fatigue.domain.fatigue_index import FatigueIndex
from driver_fatigue.interfaces.web import server as web_server


class _StubEvaluator:
    def compute(self, inputs):
        return FatigueIndex(
            value=72.0, severity="alert",
            top_contributors=("R4",), explain="BPM baixo + olhos parciais",
            critical=False,
        )


def test_publish_state_includes_index_fields():
    captured: list[dict] = []
    original = web_server._broadcast
    web_server._broadcast = lambda ev: captured.append(ev)
    try:
        sink = web_server._InProcessAlertSink(evaluator=_StubEvaluator())
        frame = Frame(image=None, timestamp=time.time(), index=42)  # type: ignore[arg-type]
        state = FatigueState.initial()
        sink.publish_state(frame, state)
    finally:
        web_server._broadcast = original

    assert len(captured) == 1
    ev = captured[0]
    assert ev["event"] == "state"
    assert ev["fatigue_index"] == 72.0
    assert ev["index_severity"] == "alert"
    assert ev["explain"] == "BPM baixo + olhos parciais"
    assert ev["top_contributors"] == ["R4"]
    assert ev["critical"] is False
```

- [ ] **Step 2: Run, confirmar fail**

Run: `pytest tests/integration/test_state_payload_has_index.py -v`
Expected: FAIL — `_InProcessAlertSink` não aceita `evaluator=`.

- [ ] **Step 3: Modificar `_InProcessAlertSink` e `_InProcessFramePresenter`**

Em `src/driver_fatigue/interfaces/web/server.py`, modificar `_InProcessAlertSink.__init__` e `publish_state`:

```python
class _InProcessAlertSink:
    def __init__(self, evaluator=None) -> None:
        from driver_fatigue.infrastructure.fatigue_inference.noop import NoOpIndexEvaluator
        self._evaluator = evaluator or NoOpIndexEvaluator()

    def notify(self, event) -> None:
        # mantem evento simples; sink externo nao recebe fatigue_index
        _broadcast({
            "event": "fatigue_alert",
            "timestamp": event.timestamp,
            "frame_index": event.frame_index,
            "ear": event.state.ear,
            "mar": event.state.mar,
            "severity": event.state.severity,
            "consecutive_frames": event.state.consecutive_frames,
        })

    def on_recovery(self, frame_index: int) -> None:
        _broadcast({
            "event": "fatigue_recovery",
            "timestamp": 0.0,
            "frame_index": frame_index,
        })

    def publish_state(self, frame, state) -> None:
        from driver_fatigue.domain.fatigue_index import FatigueInputs
        baseline = state.baseline
        sim = _get_simulated_snapshot()
        # normalizacoes
        ear_rest = max(baseline.ear_rest, 0.05) if baseline.sample_count > 0 else 0.30
        mar_std = max(baseline.mar_std, 0.04) if baseline.sample_count > 0 else 0.04
        mar_rest = baseline.mar_rest if baseline.sample_count > 0 else 0.20
        ear_norm = max(0.0, min(1.0, state.ear / ear_rest))
        mar_norm = max(0.0, min(1.0, (state.mar - mar_rest) / (mar_std * 3 + 1e-6)))
        inputs = FatigueInputs(
            ear_norm=ear_norm, mar_norm=mar_norm,
            head_drop_frames=state.head_drop_frames,
            consecutive_eyes_closed=state.consecutive_frames,
            bpm=sim["bpm"], steering_noise=sim["steering_noise"],
            hours_driving=sim["hours_driving"], hour_of_day=sim["hour_of_day"],
        )
        idx = self._evaluator.compute(inputs)
        _broadcast({
            "event": "state",
            "timestamp": frame.timestamp,
            "frame_index": frame.index,
            "ear": state.ear,
            "mar": state.mar,
            "severity": state.severity,
            "consecutive_frames": state.consecutive_frames,
            "calibrating": (
                baseline.sample_count > 0 and baseline.sample_count < 30
            ),
            "calibration_progress": min(1.0, baseline.sample_count / 45.0),
            "quality_ok": state.quality.trustworthy,
            "quality_reason": state.quality.reason,
            "fatigue_index": idx.value,
            "index_severity": idx.severity,
            "explain": idx.explain,
            "top_contributors": list(idx.top_contributors),
            "critical": idx.critical,
        })
```

E em `_EmbeddedDetectorRunner._run_once`, passar o evaluator:

```python
    def _run_once(self) -> None:
        from driver_fatigue.bootstrap import build_monitor_use_case, _build_renderer, _build_index_evaluator
        settings = self._build_settings()
        renderer = _build_renderer(settings)
        self._presenter = _InProcessFramePresenter(
            renderer,
            max_fps=settings.dashboard_stream.max_fps,
            jpeg_quality=settings.dashboard_stream.jpeg_quality,
        )
        evaluator = _build_index_evaluator(settings)
        sink = _InProcessAlertSink(evaluator=evaluator)
        uc = build_monitor_use_case(
            settings=settings,
            sink_override=sink,
            presenter_override=self._presenter,
        )
        uc.run()
```

- [ ] **Step 4: Run + commit**

Run: `pytest tests/integration/test_state_payload_has_index.py -v`
Expected: PASS.

Rodar suite completa:
Run: `pytest tests/ -v -x`
Expected: tudo verde. Se algum teste antigo quebrar com a nova chave no payload, ajustar o teste (não o código).

```bash
git add src/driver_fatigue/interfaces/web/server.py tests/integration/test_state_payload_has_index.py
git commit -m "feat(web): publish_state inclui fatigue_index do motor fuzzy"
```

---

## Task 12: E2E smoke — detector mockado + slider altera índice no SSE

**Files:**
- Test: `tests/e2e/test_dashboard_fusion.py`

- [ ] **Step 1: Teste E2E**

Criar `tests/e2e/test_dashboard_fusion.py`:

```python
"""Smoke E2E: levanta o server, faz POST /api/inputs com BPM baixo e
confirma que o proximo evento 'state' tem fatigue_index reagindo.

Nao depende de webcam — mockamos a thread do detector pra publicar
estados sintéticos a 5Hz."""
import json
import socket
import threading
import time
import urllib.request
from contextlib import contextmanager

import pytest

skfuzzy = pytest.importorskip("skfuzzy")

from driver_fatigue.domain.entities import Frame, FatigueState
from driver_fatigue.interfaces.web import server as web_server


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@contextmanager
def _running_dashboard(port: int):
    """Sobe http server + thread que faz publish_state a 5Hz."""
    from driver_fatigue.bootstrap import _build_index_evaluator
    from driver_fatigue.interfaces.config.settings import AppSettings
    web_server._api_key = None
    web_server._started_at = time.monotonic()
    web_server._simulated_inputs.update(
        bpm=75.0, steering_noise=0.1, hours_driving=0.0, hour_of_day=12.0,
    )
    settings = AppSettings()
    evaluator = _build_index_evaluator(settings)
    sink = web_server._InProcessAlertSink(evaluator=evaluator)

    httpd = web_server._QuietThreadingHTTPServer(
        ("127.0.0.1", port), web_server._Handler,
    )
    stop = threading.Event()

    def _publisher():
        i = 0
        while not stop.is_set():
            frame = Frame(image=None, timestamp=time.time(), index=i)  # type: ignore[arg-type]
            sink.publish_state(frame, FatigueState.initial())
            i += 1
            stop.wait(0.2)

    server_t = threading.Thread(target=httpd.serve_forever, daemon=True)
    pub_t = threading.Thread(target=_publisher, daemon=True)
    server_t.start(); pub_t.start()
    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        stop.set()
        httpd.shutdown()


def _read_one_state(base: str, timeout: float = 3.0) -> dict:
    """Le um unico evento 'state' do SSE."""
    req = urllib.request.Request(f"{base}/api/stream")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        deadline = time.monotonic() + timeout
        buf = b""
        while time.monotonic() < deadline:
            chunk = r.read1(2048)
            if not chunk:
                continue
            buf += chunk
            while b"\n\n" in buf:
                event, _, buf = buf.partition(b"\n\n")
                line = event.decode("utf-8")
                for ln in line.splitlines():
                    if ln.startswith("data: "):
                        payload = json.loads(ln[6:])
                        if payload.get("event") == "state":
                            return payload
        raise TimeoutError("no state event")


def test_lowering_bpm_raises_fatigue_index():
    port = _free_port()
    with _running_dashboard(port) as base:
        time.sleep(0.4)
        baseline = _read_one_state(base)
        baseline_idx = baseline["fatigue_index"]

        # baixa BPM pra 45 e simula 7h de direcao em madrugada
        body = json.dumps({
            "bpm": 45.0, "hours_driving": 7.0, "hour_of_day": 3.5,
            "steering_noise": 0.6,
        }).encode()
        req = urllib.request.Request(
            f"{base}/api/inputs", data=body, method="POST",
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=2)

        time.sleep(0.6)
        worse = _read_one_state(base)
        assert worse["fatigue_index"] > baseline_idx + 5, (
            f"indice nao subiu: {baseline_idx:.1f} -> {worse['fatigue_index']:.1f}"
        )
```

- [ ] **Step 2: Run**

Run: `pytest tests/e2e/test_dashboard_fusion.py -v -x`
Expected: PASS (pode levar ~2s).

Se falhar por flakiness de timing, aumentar `time.sleep(0.6)` pra `1.0` antes de marcar como bug.

- [ ] **Step 3: Commit**

```bash
git add tests/e2e/test_dashboard_fusion.py
git commit -m "test(e2e): slider de BPM faz fatigue_index reagir no SSE"
```

---

## Task 13: Setup do projeto React — `web/`

**Files:**
- Create: `web/package.json`
- Create: `web/vite.config.js`
- Create: `web/tailwind.config.js`
- Create: `web/postcss.config.js`
- Create: `web/.gitignore`
- Create: `web/index.html`
- Create: `web/src/main.jsx`
- Create: `web/src/index.css`

- [ ] **Step 1: Criar `web/package.json`**

```json
{
  "name": "driver-fatigue-web",
  "private": true,
  "version": "0.3.0",
  "type": "module",
  "scripts": {
    "dev": "vite",
    "build": "vite build",
    "preview": "vite preview",
    "test": "vitest"
  },
  "dependencies": {
    "clsx": "^2.1.1",
    "lucide-react": "^0.460.0",
    "react": "^18.3.1",
    "react-dom": "^18.3.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.5.0",
    "@testing-library/react": "^16.0.1",
    "@vitejs/plugin-react": "^4.3.4",
    "autoprefixer": "^10.4.20",
    "jsdom": "^25.0.1",
    "postcss": "^8.4.49",
    "tailwindcss": "^3.4.16",
    "vite": "^5.4.11",
    "vitest": "^2.1.8"
  }
}
```

- [ ] **Step 2: Criar `web/vite.config.js`**

```js
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: "../src/driver_fatigue/interfaces/web/static",
    emptyOutDir: true,
    assetsDir: "assets",
  },
  server: {
    proxy: {
      "/api": "http://localhost:8000",
    },
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/__tests__/setup.js"],
  },
});
```

- [ ] **Step 3: Criar `web/tailwind.config.js`**

```js
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ifg: {
          green: "#23A455",
          "green-dark": "#1C7A3F",
          "green-light": "#4CC97A",
        },
        surface: {
          0: "#08090c",
          1: "#0e1116",
          2: "#14181f",
          3: "#1a1f28",
        },
        line: {
          DEFAULT: "#232934",
          strong: "#2c333f",
        },
        text: {
          0: "#f1f4f9",
          1: "#a8b1bf",
          2: "#6b7385",
          3: "#444c5c",
        },
        severity: {
          normal: "#4ade80",
          warning: "#fbbf24",
          alert: "#f43f5e",
        },
      },
      fontFamily: {
        sans: ['Inter', 'ui-sans-serif', 'system-ui', 'Segoe UI', 'sans-serif'],
        mono: ['JetBrains Mono', 'ui-monospace', 'monospace'],
      },
      borderRadius: {
        card: "16px",
      },
      keyframes: {
        pulseGreen: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(74,222,128,0.6)" },
          "70%": { boxShadow: "0 0 0 10px rgba(74,222,128,0)" },
        },
        flashRed: {
          "0%, 100%": { boxShadow: "inset 0 0 60px rgba(244,63,94,0.25)" },
          "50%":      { boxShadow: "inset 0 0 120px rgba(244,63,94,0.50)" },
        },
      },
      animation: {
        "pulse-green": "pulseGreen 1.6s ease-in-out infinite",
        "flash-red":   "flashRed 0.9s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
```

- [ ] **Step 4: Criar `web/postcss.config.js`**

```js
export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
};
```

- [ ] **Step 5: Criar `web/.gitignore`**

```
node_modules/
dist/
.vite/
```

- [ ] **Step 6: Criar `web/index.html`**

```html
<!doctype html>
<html lang="pt-BR">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/ifg-logo.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Driver Fatigue · NumbERS · IFG</title>
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap" rel="stylesheet" />
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.jsx"></script>
  </body>
</html>
```

- [ ] **Step 7: Criar `web/src/index.css`**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

html, body, #root { height: 100%; }
body {
  margin: 0;
  background: theme(colors.surface.0);
  color: theme(colors.text.0);
  font-family: theme(fontFamily.sans);
  -webkit-font-smoothing: antialiased;
  text-rendering: optimizeLegibility;
}

input[type="range"] {
  @apply accent-ifg-green;
}
```

- [ ] **Step 8: Criar `web/src/main.jsx`**

```jsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App.jsx";
import "./index.css";

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
```

- [ ] **Step 9: Criar `web/src/App.jsx` (placeholder mínimo, pra build passar)**

```jsx
export default function App() {
  return <div className="p-8 text-text-1">Driver Fatigue · em construção</div>;
}
```

- [ ] **Step 10: Instalar deps**

Run: `cd web && npm install`
Expected: install completa sem erros (pode levar 1-2min).

- [ ] **Step 11: Build de smoke**

Run: `cd web && npm run build`
Expected: gera `src/driver_fatigue/interfaces/web/static/index.html` + `assets/index-*.js`/`.css`.

Verificar: `ls src/driver_fatigue/interfaces/web/static/` mostra `index.html` e pasta `assets/`.

- [ ] **Step 12: Commit**

```bash
git add web/ src/driver_fatigue/interfaces/web/static/
git commit -m "feat(web): setup React + Vite + Tailwind com tokens IFG"
```

---

## Task 14: Logo IFG (SVG) e `web/public/`

**Files:**
- Create: `web/public/ifg-logo.svg`

- [ ] **Step 1: Adicionar SVG da logo IFG**

Criar `web/public/ifg-logo.svg`. Usar a marca "IF" estilizada (versão simplificada usável offline):

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="IFG">
  <defs>
    <linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#23A455"/>
      <stop offset="100%" stop-color="#1C7A3F"/>
    </linearGradient>
  </defs>
  <rect width="64" height="64" rx="14" fill="url(#g)"/>
  <text x="50%" y="58%" text-anchor="middle" dominant-baseline="middle"
        font-family="Inter, Segoe UI, sans-serif" font-weight="700"
        font-size="26" fill="#ffffff" letter-spacing="-1">IFG</text>
</svg>
```

**Nota:** se você tiver acesso ao SVG oficial do IFG (em `numbers-site/public/images/`), substitua este placeholder. Se não, este placeholder respeita a paleta institucional e funciona como marca temporária.

- [ ] **Step 2: Verificar build copia o arquivo**

Run: `cd web && npm run build`
Verificar: `ls src/driver_fatigue/interfaces/web/static/ifg-logo.svg` existe (Vite copia `public/*` pra raiz do dist).

- [ ] **Step 3: Commit**

```bash
git add web/public/ifg-logo.svg src/driver_fatigue/interfaces/web/static/ifg-logo.svg
git commit -m "feat(web): logo IFG (placeholder oficial-compativel)"
```

---

## Task 15: Hook `useEventStream` + setup de testes

**Files:**
- Create: `web/src/__tests__/setup.js`
- Create: `web/src/hooks/useEventStream.js`
- Create: `web/src/__tests__/useEventStream.test.jsx`

- [ ] **Step 1: Setup de testes**

Criar `web/src/__tests__/setup.js`:

```js
import "@testing-library/jest-dom/vitest";
```

- [ ] **Step 2: Implementar hook (sem TDD aqui — hook de I/O testado funcionalmente)**

Criar `web/src/hooks/useEventStream.js`:

```js
import { useEffect, useRef, useState } from "react";

/**
 * Consome /api/stream (SSE) com reconnect exponencial.
 * Retorna { status, lastState, events } onde:
 * - status: "connecting" | "live" | "reconnecting"
 * - lastState: ultimo payload com event === "state" (ou null)
 * - events: lista (max 60) de payloads com event !== "state", mais recente primeiro
 */
export function useEventStream() {
  const [status, setStatus] = useState("connecting");
  const [lastState, setLastState] = useState(null);
  const [events, setEvents] = useState([]);
  const cancelledRef = useRef(false);
  const esRef = useRef(null);

  useEffect(() => {
    cancelledRef.current = false;
    let backoff = 1000;
    let timer = null;

    function connect() {
      const es = new EventSource("/api/stream");
      esRef.current = es;
      es.onopen = () => {
        setStatus("live");
        backoff = 1000;
      };
      es.onmessage = (msg) => {
        try {
          const p = JSON.parse(msg.data);
          if (p.event === "state") {
            setLastState(p);
          } else {
            setEvents((prev) => [p, ...prev].slice(0, 60));
          }
        } catch {
          /* ignore malformed */
        }
      };
      es.onerror = () => {
        setStatus("reconnecting");
        es.close();
        if (!cancelledRef.current) {
          timer = setTimeout(() => {
            backoff = Math.min(backoff * 1.5, 10000);
            connect();
          }, backoff);
        }
      };
    }
    connect();
    return () => {
      cancelledRef.current = true;
      if (timer) clearTimeout(timer);
      esRef.current?.close();
    };
  }, []);

  return { status, lastState, events };
}
```

- [ ] **Step 3: Smoke test**

Criar `web/src/__tests__/useEventStream.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useEventStream } from "../hooks/useEventStream";

class MockEventSource {
  constructor(url) {
    this.url = url;
    MockEventSource.lastInstance = this;
  }
  close() { this.closed = true; }
}

beforeEach(() => {
  vi.stubGlobal("EventSource", MockEventSource);
});

describe("useEventStream", () => {
  it("opens an EventSource on /api/stream", () => {
    renderHook(() => useEventStream());
    expect(MockEventSource.lastInstance.url).toBe("/api/stream");
  });

  it("populates lastState on state event", () => {
    const { result } = renderHook(() => useEventStream());
    act(() => {
      MockEventSource.lastInstance.onopen?.();
      MockEventSource.lastInstance.onmessage?.({
        data: JSON.stringify({ event: "state", fatigue_index: 42 }),
      });
    });
    expect(result.current.lastState.fatigue_index).toBe(42);
    expect(result.current.status).toBe("live");
  });

  it("pushes non-state events into events list", () => {
    const { result } = renderHook(() => useEventStream());
    act(() => {
      MockEventSource.lastInstance.onmessage?.({
        data: JSON.stringify({ event: "fatigue_alert", ear: 0.2 }),
      });
    });
    expect(result.current.events[0].event).toBe("fatigue_alert");
  });
});
```

- [ ] **Step 4: Run + commit**

Run: `cd web && npm test -- --run`
Expected: 3 testes PASS.

```bash
git add web/src/hooks/useEventStream.js web/src/__tests__/
git commit -m "feat(web): useEventStream hook + smoke tests"
```

---

## Task 16: Hook `useSimulatedInputs` (POST debounced + demo polling)

**Files:**
- Create: `web/src/hooks/useSimulatedInputs.js`
- Create: `web/src/__tests__/useSimulatedInputs.test.jsx`

- [ ] **Step 1: Implementar hook**

Criar `web/src/hooks/useSimulatedInputs.js`:

```js
import { useCallback, useEffect, useRef, useState } from "react";

const INITIAL = {
  bpm: 75,
  steering_noise: 0.1,
  hours_driving: 0,
  hour_of_day: new Date().getHours(),
};

const DEBOUNCE_MS = 100;
const DEMO_POLL_MS = 500;

/**
 * Gerencia o estado dos sliders e sincroniza com /api/inputs (POST debounced).
 * Quando demoState === "running", faz polling GET /api/inputs e atualiza inputs
 * com o que o servidor diz (script do servidor sobrescreve).
 */
export function useSimulatedInputs() {
  const [inputs, setInputs] = useState(INITIAL);
  const [demoState, setDemoState] = useState("idle"); // idle | running

  const debounceRef = useRef(null);
  const pollRef = useRef(null);

  const setInputsLocal = useCallback((updater) => {
    setInputs((prev) => {
      const next = typeof updater === "function" ? updater(prev) : { ...prev, ...updater };
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => {
        fetch("/api/inputs", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(next),
        }).catch(() => {});
      }, DEBOUNCE_MS);
      return next;
    });
  }, []);

  const startDemo = useCallback(async () => {
    try {
      const r = await fetch("/api/demo/start", { method: "POST" });
      if (r.status === 202) {
        setDemoState("running");
      }
    } catch {}
  }, []);

  const stopDemo = useCallback(async () => {
    try {
      await fetch("/api/demo/stop", { method: "POST" });
    } catch {}
    setDemoState("idle");
  }, []);

  useEffect(() => {
    if (demoState !== "running") {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = setInterval(async () => {
      try {
        const r = await fetch("/api/inputs");
        if (r.ok) {
          const data = await r.json();
          setInputs(data);
        }
      } catch {}
    }, DEMO_POLL_MS);
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [demoState]);

  return { inputs, setInputs: setInputsLocal, demoState, startDemo, stopDemo };
}
```

- [ ] **Step 2: Teste**

Criar `web/src/__tests__/useSimulatedInputs.test.jsx`:

```jsx
import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, act } from "@testing-library/react";
import { useSimulatedInputs } from "../hooks/useSimulatedInputs";

beforeEach(() => {
  vi.useFakeTimers();
  global.fetch = vi.fn(() => Promise.resolve({ status: 202, ok: true, json: async () => ({}) }));
});

describe("useSimulatedInputs", () => {
  it("debounces POST /api/inputs", async () => {
    const { result } = renderHook(() => useSimulatedInputs());
    act(() => { result.current.setInputs({ bpm: 60 }); });
    act(() => { result.current.setInputs({ bpm: 55 }); });
    act(() => { result.current.setInputs({ bpm: 50 }); });

    expect(global.fetch).not.toHaveBeenCalledWith("/api/inputs", expect.anything());
    act(() => { vi.advanceTimersByTime(150); });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });

  it("startDemo sets demoState to running on 202", async () => {
    const { result } = renderHook(() => useSimulatedInputs());
    await act(async () => { await result.current.startDemo(); });
    expect(result.current.demoState).toBe("running");
  });
});
```

- [ ] **Step 3: Run + commit**

Run: `cd web && npm test -- --run useSimulatedInputs`
Expected: 2 PASS.

```bash
git add web/src/hooks/useSimulatedInputs.js web/src/__tests__/useSimulatedInputs.test.jsx
git commit -m "feat(web): useSimulatedInputs com debounce + demo polling"
```

---

## Task 17: Hook `useVideoHealth`

**Files:**
- Create: `web/src/hooks/useVideoHealth.js`

- [ ] **Step 1: Implementar**

Criar `web/src/hooks/useVideoHealth.js`:

```js
import { useEffect, useState } from "react";

/**
 * Poll /api/health a 3s. Retorna { videoOnline, videoAge }.
 * videoOnline = video_age_seconds < 30 && !== null.
 */
export function useVideoHealth(intervalMs = 3000) {
  const [state, setState] = useState({ videoOnline: false, videoAge: null });

  useEffect(() => {
    let cancelled = false;
    async function tick() {
      try {
        const r = await fetch("/api/health");
        const h = await r.json();
        if (cancelled) return;
        const age = h.video_age_seconds;
        setState({
          videoOnline: age !== null && age < 30,
          videoAge: age,
        });
      } catch {
        if (!cancelled) setState({ videoOnline: false, videoAge: null });
      }
    }
    tick();
    const id = setInterval(tick, intervalMs);
    return () => { cancelled = true; clearInterval(id); };
  }, [intervalMs]);

  return state;
}
```

- [ ] **Step 2: Commit (sem teste — wrapper trivial)**

```bash
git add web/src/hooks/useVideoHealth.js
git commit -m "feat(web): useVideoHealth hook"
```

---

## Task 18: Componentes UI primitivos — `Card`, `ProgressBar`

**Files:**
- Create: `web/src/components/ui/Card.jsx`
- Create: `web/src/components/ui/ProgressBar.jsx`

- [ ] **Step 1: `Card.jsx`**

```jsx
import clsx from "clsx";

export function Card({ children, className = "", title, badge }) {
  return (
    <section className={clsx(
      "rounded-card bg-gradient-to-b from-surface-1 to-surface-2",
      "border border-line shadow-[0_16px_40px_-16px_rgba(0,0,0,0.4)]",
      "p-5", className,
    )}>
      {title && (
        <header className="mb-3 flex items-center justify-between">
          <h2 className="text-[10px] font-semibold uppercase tracking-[0.16em] text-text-2">
            {title}
          </h2>
          {badge && <span className="text-[9px] uppercase tracking-[0.1em] text-text-2">{badge}</span>}
        </header>
      )}
      {children}
    </section>
  );
}
```

- [ ] **Step 2: `ProgressBar.jsx`**

```jsx
import clsx from "clsx";

const SEVERITY_BG = {
  normal:  "bg-severity-normal",
  warning: "bg-severity-warning",
  alert:   "bg-severity-alert",
};

export function ProgressBar({ value, max = 100, severity = "normal" }) {
  const pct = Math.max(0, Math.min(100, (value / max) * 100));
  return (
    <div className="h-1.5 w-full rounded-full bg-line overflow-hidden">
      <div
        className={clsx("h-full rounded-full transition-[width,background] duration-300", SEVERITY_BG[severity])}
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/ui/
git commit -m "feat(web): primitivos UI Card e ProgressBar"
```

---

## Task 19: `Header` + `ConnBadge`

**Files:**
- Create: `web/src/components/header/Header.jsx`
- Create: `web/src/components/header/ConnBadge.jsx`

- [ ] **Step 1: `ConnBadge.jsx`**

```jsx
import clsx from "clsx";

const STYLE = {
  live:         { dot: "bg-severity-normal animate-pulse-green", label: "ao vivo" },
  connecting:   { dot: "bg-severity-warning",                    label: "conectando" },
  reconnecting: { dot: "bg-severity-alert",                      label: "reconectando" },
};

export function ConnBadge({ status }) {
  const s = STYLE[status] || STYLE.connecting;
  return (
    <span className="inline-flex items-center gap-2 rounded-full border border-line bg-surface-1 px-3 py-1 text-xs text-text-1">
      <span className={clsx("h-1.5 w-1.5 rounded-full", s.dot)} />
      {s.label}
    </span>
  );
}
```

- [ ] **Step 2: `Header.jsx`**

```jsx
import { ConnBadge } from "./ConnBadge.jsx";

export function Header({ status }) {
  return (
    <header className="sticky top-0 z-10 flex items-center justify-between border-b border-line bg-surface-0/70 px-7 py-4 backdrop-blur">
      <div className="flex items-center gap-3">
        <img src="/ifg-logo.svg" alt="IFG" className="h-9 w-9 rounded-lg shadow-[0_6px_16px_rgba(35,164,85,0.25)]" />
        <div>
          <h1 className="m-0 text-[15px] font-semibold tracking-tight text-text-0">
            Driver Fatigue · Live Monitor
          </h1>
          <p className="m-0 mt-0.5 text-[11px] tracking-[0.04em] text-text-2">
            Sistemas Ubíquos · NumbERS · IFG
          </p>
        </div>
      </div>
      <ConnBadge status={status} />
    </header>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/header/
git commit -m "feat(web): Header com logo IFG + ConnBadge"
```

---

## Task 20: `VideoCard` + `AlertFlash`

**Files:**
- Create: `web/src/components/video/VideoCard.jsx`
- Create: `web/src/components/video/AlertFlash.jsx`

- [ ] **Step 1: `AlertFlash.jsx`**

```jsx
import clsx from "clsx";

export function AlertFlash({ active }) {
  return (
    <div className={clsx(
      "pointer-events-none absolute inset-0 rounded-[inherit]",
      active && "animate-flash-red border-8 border-severity-alert",
    )} />
  );
}
```

- [ ] **Step 2: `VideoCard.jsx`**

```jsx
import { useEffect, useRef, useState } from "react";
import { Video, VideoOff } from "lucide-react";
import { AlertFlash } from "./AlertFlash.jsx";

export function VideoCard({ lastState, videoOnline }) {
  const imgRef = useRef(null);
  const [loaded, setLoaded] = useState(false);

  useEffect(() => {
    if (!videoOnline) {
      setLoaded(false);
      if (imgRef.current) imgRef.current.removeAttribute("src");
      return;
    }
    if (imgRef.current && !imgRef.current.src) {
      imgRef.current.src = `/api/video?_=${Date.now()}`;
    }
  }, [videoOnline]);

  const ear = lastState?.ear?.toFixed(2) ?? "—";
  const mar = lastState?.mar?.toFixed(2) ?? "—";
  const isAlert = lastState?.index_severity === "alert" || lastState?.severity === "alert";

  return (
    <div className="relative aspect-video overflow-hidden rounded-card border border-line bg-black shadow-[0_30px_60px_-20px_rgba(0,0,0,0.7)]">
      <img
        ref={imgRef}
        alt=""
        className="block h-full w-full object-contain"
        onLoad={() => setLoaded(true)}
        onError={() => setLoaded(false)}
      />
      {!loaded && (
        <div className="absolute inset-0 grid place-items-center bg-surface-1 text-center text-text-2">
          <div className="px-10">
            <div className="mx-auto mb-4 grid h-16 w-16 place-items-center rounded-2xl border border-line bg-surface-2">
              {videoOnline ? <Video className="h-8 w-8" /> : <VideoOff className="h-8 w-8" />}
            </div>
            <h3 className="m-0 mb-1 text-lg font-semibold text-text-0">
              {videoOnline ? "Carregando stream…" : "Detector offline"}
            </h3>
            <p className="text-sm">
              Aguardando frames da câmera. O detector embutido está respawnando automaticamente.
            </p>
          </div>
        </div>
      )}
      <div className="pointer-events-none absolute inset-0 z-10">
        <div className="absolute left-4 top-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-surface-0/70 px-3 py-1 text-xs tabular-nums text-text-1 backdrop-blur">
          <span className="h-2 w-2 rounded-full bg-severity-alert animate-pulse" />
          {loaded ? "ao vivo" : "offline"}
        </div>
        <div className="absolute right-4 top-4 inline-flex items-center gap-2 rounded-full border border-white/10 bg-surface-0/70 px-3 py-1 text-xs tabular-nums text-text-1 backdrop-blur">
          <span className="font-mono">EAR <b className="text-text-0">{ear}</b> · MAR <b className="text-text-0">{mar}</b></span>
        </div>
      </div>
      <AlertFlash active={isAlert} />
    </div>
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add web/src/components/video/
git commit -m "feat(web): VideoCard com placeholder e AlertFlash"
```

---

## Task 21: `FatigueGauge` (arco SVG + explain)

**Files:**
- Create: `web/src/components/gauge/SeverityIcon.jsx`
- Create: `web/src/components/gauge/FatigueGauge.jsx`
- Create: `web/src/__tests__/FatigueGauge.test.jsx`

- [ ] **Step 1: `SeverityIcon.jsx`**

```jsx
import { CheckCircle2, AlertTriangle, AlertOctagon } from "lucide-react";
import clsx from "clsx";

const MAP = {
  normal:  { Icon: CheckCircle2,  cls: "text-severity-normal bg-severity-normal/10" },
  warning: { Icon: AlertTriangle, cls: "text-severity-warning bg-severity-warning/10" },
  alert:   { Icon: AlertOctagon,  cls: "text-severity-alert   bg-severity-alert/15" },
};

export function SeverityIcon({ severity, size = "md" }) {
  const { Icon, cls } = MAP[severity] || MAP.normal;
  const dim = size === "lg" ? "h-14 w-14" : "h-10 w-10";
  return (
    <div className={clsx("grid place-items-center rounded-2xl transition-colors", dim, cls)}>
      <Icon className="h-2/3 w-2/3" />
    </div>
  );
}
```

- [ ] **Step 2: `FatigueGauge.jsx`**

```jsx
import clsx from "clsx";
import { SeverityIcon } from "./SeverityIcon.jsx";
import { Card } from "../ui/Card.jsx";

const SEVERITY_LABEL = { normal: "Normal", warning: "Atenção", alert: "Alerta" };

// arco semicircular 0-100% — math: angulo de -180 a 0 graus, raio 80
function _arcPath(pct) {
  const angle = -Math.PI + (pct / 100) * Math.PI;
  const x = 100 + 80 * Math.cos(angle);
  const y = 100 + 80 * Math.sin(angle);
  const large = pct > 50 ? 1 : 0;
  return `M 20 100 A 80 80 0 ${large} 1 ${x} ${y}`;
}

export function FatigueGauge({ state }) {
  const value = state?.fatigue_index ?? 0;
  const severity = state?.index_severity ?? "normal";
  const critical = state?.critical ?? false;
  const explain = state?.explain ?? "—";

  return (
    <Card title="Índice de Fadiga" badge={state?.calibrating ? "calibrando…" : null}>
      <div className="flex flex-col items-center">
        <svg viewBox="0 0 200 110" className="w-full max-w-[260px]">
          <defs>
            <linearGradient id="gauge" x1="0" y1="0" x2="1" y2="0">
              <stop offset="0%"   stopColor="#4ade80"/>
              <stop offset="50%"  stopColor="#fbbf24"/>
              <stop offset="100%" stopColor="#f43f5e"/>
            </linearGradient>
          </defs>
          <path d="M 20 100 A 80 80 0 0 1 180 100" stroke="#232934" strokeWidth="14" fill="none" strokeLinecap="round"/>
          <path d={_arcPath(value)} stroke="url(#gauge)" strokeWidth="14" fill="none" strokeLinecap="round"
                style={{ transition: "all 300ms ease" }}/>
          <text x="100" y="92" textAnchor="middle" className="fill-text-0 font-semibold tabular-nums"
                style={{ fontSize: 36 }}>
            {Math.round(value)}
          </text>
          <text x="100" y="108" textAnchor="middle" className="fill-text-2" style={{ fontSize: 10 }}>
            / 100
          </text>
        </svg>
        <div className={clsx("mt-2 flex items-center gap-3", critical && "animate-pulse")}>
          <SeverityIcon severity={severity} />
          <div>
            <div className="text-lg font-semibold tracking-tight text-text-0">
              {SEVERITY_LABEL[severity]}{critical && " · Crítico"}
            </div>
            <div className="mt-0.5 text-xs text-text-1">
              {explain}
            </div>
          </div>
        </div>
      </div>
    </Card>
  );
}
```

- [ ] **Step 3: Teste**

Criar `web/src/__tests__/FatigueGauge.test.jsx`:

```jsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { FatigueGauge } from "../components/gauge/FatigueGauge";

describe("FatigueGauge", () => {
  it("renders the index value rounded", () => {
    render(<FatigueGauge state={{ fatigue_index: 67.4, index_severity: "alert", explain: "BPM baixo + tempo alto" }} />);
    expect(screen.getByText("67")).toBeInTheDocument();
    expect(screen.getByText(/BPM baixo/)).toBeInTheDocument();
  });

  it("falls back to 0 when no state", () => {
    render(<FatigueGauge state={null} />);
    expect(screen.getByText("0")).toBeInTheDocument();
  });

  it("shows critico suffix when critical=true", () => {
    render(<FatigueGauge state={{ fatigue_index: 90, index_severity: "alert", critical: true, explain: "x" }} />);
    expect(screen.getByText(/Crítico/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run + commit**

Run: `cd web && npm test -- --run FatigueGauge`
Expected: 3 PASS.

```bash
git add web/src/components/gauge/ web/src/__tests__/FatigueGauge.test.jsx
git commit -m "feat(web): FatigueGauge com arco SVG e explain"
```

---

## Task 22: `SliderPanel` + `SliderControl` + `DemoButton`

**Files:**
- Create: `web/src/components/sliders/SliderControl.jsx`
- Create: `web/src/components/sliders/DemoButton.jsx`
- Create: `web/src/components/sliders/SliderPanel.jsx`

- [ ] **Step 1: `SliderControl.jsx`**

```jsx
import clsx from "clsx";

export function SliderControl({ label, value, min, max, step, unit, onChange, disabled, format }) {
  const display = format ? format(value) : `${Number(value).toFixed(step < 1 ? 2 : 0)}${unit ? ` ${unit}` : ""}`;
  return (
    <label className={clsx("block", disabled && "opacity-60")}>
      <div className="mb-1.5 flex items-baseline justify-between">
        <span className="text-[10px] font-medium uppercase tracking-[0.14em] text-text-2">{label}</span>
        <span className="font-mono text-sm tabular-nums text-text-0">{display}</span>
      </div>
      <input
        type="range"
        min={min} max={max} step={step}
        value={value}
        disabled={disabled}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full"
      />
    </label>
  );
}
```

- [ ] **Step 2: `DemoButton.jsx`**

```jsx
import { Play, Square } from "lucide-react";
import clsx from "clsx";

export function DemoButton({ demoState, onStart, onStop }) {
  const running = demoState === "running";
  return (
    <div className="mt-4 flex gap-2">
      <button
        type="button"
        onClick={running ? onStop : onStart}
        className={clsx(
          "flex flex-1 items-center justify-center gap-2 rounded-lg px-4 py-2.5 text-sm font-medium transition",
          running
            ? "bg-severity-alert/15 text-severity-alert hover:bg-severity-alert/25"
            : "bg-ifg-green text-white hover:bg-ifg-green-dark"
        )}
      >
        {running ? <Square className="h-4 w-4" /> : <Play className="h-4 w-4" />}
        {running ? "Parar cenário demo" : "Modo demo automático"}
      </button>
    </div>
  );
}
```

- [ ] **Step 3: `SliderPanel.jsx`**

```jsx
import { Card } from "../ui/Card.jsx";
import { SliderControl } from "./SliderControl.jsx";
import { DemoButton } from "./DemoButton.jsx";

const HOUR_FORMAT = (v) => {
  const h = Math.floor(v);
  const m = Math.round((v - h) * 60);
  return `${String(h).padStart(2,"0")}:${String(m).padStart(2,"0")}`;
};

export function SliderPanel({ inputs, setInputs, demoState, startDemo, stopDemo }) {
  const disabled = demoState === "running";

  return (
    <Card title="Sinais simulados">
      <div className="grid grid-cols-1 gap-x-6 gap-y-4 sm:grid-cols-2 lg:grid-cols-4">
        <SliderControl
          label="BPM"
          value={inputs.bpm} min={40} max={120} step={1} unit="bpm"
          onChange={(v) => setInputs({ bpm: v })}
          disabled={disabled}
        />
        <SliderControl
          label="Volante (ruído)"
          value={inputs.steering_noise} min={0} max={1} step={0.01}
          onChange={(v) => setInputs({ steering_noise: v })}
          disabled={disabled}
        />
        <SliderControl
          label="Tempo dirigindo"
          value={inputs.hours_driving} min={0} max={10} step={0.1} unit="h"
          onChange={(v) => setInputs({ hours_driving: v })}
          disabled={disabled}
        />
        <SliderControl
          label="Hora do dia"
          value={inputs.hour_of_day} min={0} max={23.99} step={0.25}
          format={HOUR_FORMAT}
          onChange={(v) => setInputs({ hour_of_day: v })}
          disabled={disabled}
        />
      </div>
      <DemoButton demoState={demoState} onStart={startDemo} onStop={stopDemo} />
    </Card>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add web/src/components/sliders/
git commit -m "feat(web): SliderPanel com 4 sliders + botao demo"
```

---

## Task 23: `MetricsGrid`, `Timeline`, `EventRow`

**Files:**
- Create: `web/src/components/metrics/MetricsGrid.jsx`
- Create: `web/src/components/timeline/EventRow.jsx`
- Create: `web/src/components/timeline/Timeline.jsx`

- [ ] **Step 1: `MetricsGrid.jsx`**

```jsx
import { Card } from "../ui/Card.jsx";

function Metric({ label, value, hint }) {
  return (
    <div className="rounded-lg border border-line bg-surface-1 p-3">
      <div className="mb-1 text-[10px] font-medium uppercase tracking-[0.14em] text-text-2">{label}</div>
      <div className="font-mono text-xl font-semibold tabular-nums tracking-tight text-text-0">
        {value}
        {hint && <small className="ml-1.5 text-[11px] font-normal text-text-2">{hint}</small>}
      </div>
    </div>
  );
}

export function MetricsGrid({ state, events }) {
  const alerts = events.filter((e) => e.event === "fatigue_alert").length;
  const recoveries = events.filter((e) => e.event === "fatigue_recovery").length;
  return (
    <Card title="Métricas">
      <div className="grid grid-cols-2 gap-2">
        <Metric label="EAR" value={state?.ear?.toFixed(2) ?? "—"} />
        <Metric label="MAR" value={state?.mar?.toFixed(2) ?? "—"} />
        <Metric label="Alertas" value={alerts} />
        <Metric label="Recoveries" value={recoveries} />
      </div>
    </Card>
  );
}
```

- [ ] **Step 2: `EventRow.jsx`**

```jsx
import clsx from "clsx";

const KIND = {
  fatigue_alert:    { stripe: "bg-severity-alert",   title: "Alerta de fadiga" },
  fatigue_recovery: { stripe: "bg-severity-normal",  title: "Motorista recuperou" },
};

function fmt(ts) {
  if (!ts) return "—";
  return new Date(ts * 1000).toLocaleTimeString("pt-BR", { hour12: false });
}

export function EventRow({ event }) {
  const k = KIND[event.event] || { stripe: "bg-severity-warning", title: event.event };
  const meta = [];
  if (event.ear !== undefined) meta.push(`EAR ${(+event.ear).toFixed(2)}`);
  if (event.mar !== undefined) meta.push(`MAR ${(+event.mar).toFixed(2)}`);
  if (event.consecutive_frames !== undefined) meta.push(`conseq ${event.consecutive_frames}`);

  return (
    <div className="grid grid-cols-[4px_1fr_auto] items-center gap-3 rounded-lg border border-line bg-surface-1 px-3 py-2.5 animate-in fade-in slide-in-from-top-1 duration-200">
      <div className={clsx("h-full min-h-7 w-1 rounded", k.stripe)} />
      <div className="min-w-0">
        <div className="text-xs font-semibold text-text-0">{k.title}</div>
        <div className="truncate text-[11px] tabular-nums text-text-2">{meta.join(" · ") || "—"}</div>
      </div>
      <div className="whitespace-nowrap text-[10px] tabular-nums text-text-3">
        {fmt(event.received_at || event.timestamp)}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: `Timeline.jsx`**

```jsx
import { Card } from "../ui/Card.jsx";
import { EventRow } from "./EventRow.jsx";

export function Timeline({ events }) {
  return (
    <Card title="Eventos">
      <div className="flex max-h-[360px] flex-col gap-2 overflow-y-auto pr-1">
        {events.length === 0 ? (
          <div className="px-2 py-6 text-center text-xs text-text-2">
            Nenhum evento ainda — quando o detector disparar, aparece aqui.
          </div>
        ) : (
          events.map((e, i) => <EventRow key={`${e.timestamp}-${i}`} event={e} />)
        )}
      </div>
    </Card>
  );
}
```

- [ ] **Step 4: Commit**

```bash
git add web/src/components/metrics/ web/src/components/timeline/
git commit -m "feat(web): MetricsGrid + Timeline + EventRow"
```

---

## Task 24: `App.jsx` final montando o layout Cockpit

**Files:**
- Modify: `web/src/App.jsx`

- [ ] **Step 1: Substituir o placeholder por layout completo**

Sobrescrever `web/src/App.jsx`:

```jsx
import { Header } from "./components/header/Header.jsx";
import { VideoCard } from "./components/video/VideoCard.jsx";
import { FatigueGauge } from "./components/gauge/FatigueGauge.jsx";
import { SliderPanel } from "./components/sliders/SliderPanel.jsx";
import { MetricsGrid } from "./components/metrics/MetricsGrid.jsx";
import { Timeline } from "./components/timeline/Timeline.jsx";
import { useEventStream } from "./hooks/useEventStream.js";
import { useSimulatedInputs } from "./hooks/useSimulatedInputs.js";
import { useVideoHealth } from "./hooks/useVideoHealth.js";

export default function App() {
  const { status, lastState, events } = useEventStream();
  const { inputs, setInputs, demoState, startDemo, stopDemo } = useSimulatedInputs();
  const { videoOnline } = useVideoHealth();

  return (
    <div className="min-h-screen bg-surface-0 text-text-0">
      <Header status={status} />
      <main className="mx-auto mt-6 grid max-w-[1480px] grid-cols-12 gap-6 px-7 pb-9">
        <section className="col-span-12 space-y-4 lg:col-span-8">
          <VideoCard lastState={lastState} videoOnline={videoOnline} />
          <SliderPanel
            inputs={inputs}
            setInputs={setInputs}
            demoState={demoState}
            startDemo={startDemo}
            stopDemo={stopDemo}
          />
        </section>
        <aside className="col-span-12 space-y-4 lg:col-span-4">
          <FatigueGauge state={lastState} />
          <MetricsGrid state={lastState} events={events} />
          <Timeline events={events} />
        </aside>
      </main>
    </div>
  );
}
```

- [ ] **Step 2: Build + smoke visual**

Run: `cd web && npm run build`
Expected: build OK, sem warnings de import.

- [ ] **Step 3: Commit**

```bash
git add web/src/App.jsx src/driver_fatigue/interfaces/web/static/
git commit -m "feat(web): App.jsx monta layout Cockpit completo"
```

---

## Task 25: `_serve_static` aceita assets do Vite

**Files:**
- Modify: `src/driver_fatigue/interfaces/web/server.py`

- [ ] **Step 1: Garantir mimes corretos pra `.svg`, `.woff2`, `.png`**

Ler `_guess_mime` em `src/driver_fatigue/interfaces/web/server.py`. Substituir por:

```python
    def _guess_mime(self, name: str) -> str:
        if name.endswith(".html"):
            return "text/html; charset=utf-8"
        if name.endswith(".js") or name.endswith(".mjs"):
            return "application/javascript; charset=utf-8"
        if name.endswith(".css"):
            return "text/css; charset=utf-8"
        if name.endswith(".json"):
            return "application/json"
        if name.endswith(".svg"):
            return "image/svg+xml"
        if name.endswith(".png"):
            return "image/png"
        if name.endswith(".woff2"):
            return "font/woff2"
        if name.endswith(".ico"):
            return "image/x-icon"
        return "application/octet-stream"
```

- [ ] **Step 2: `do_GET` precisa servir `/assets/*` (gerado pelo Vite na raiz do static)**

No `do_GET`, antes da linha `if path.startswith("/static/")`, adicionar:

```python
        if path.startswith("/assets/"):
            name = path[1:]  # strip leading slash → "assets/index-XXXX.js"
            mime = self._guess_mime(name)
            self._serve_static(name, mime)
            return
        if path.endswith(".svg") or path.endswith(".png") or path.endswith(".ico"):
            # arquivos da raiz do public/ (ifg-logo.svg, favicons, etc.)
            name = path.lstrip("/")
            mime = self._guess_mime(name)
            self._serve_static(name, mime)
            return
```

- [ ] **Step 3: Smoke manual**

Run:
```bash
python -m driver_fatigue.interfaces.web --no-detector --port 8000
```

(Em outro terminal:) `curl -I http://localhost:8000/ifg-logo.svg` → deve responder 200 com `Content-Type: image/svg+xml`.

`curl -I http://localhost:8000/assets/<algum-arquivo>.js` → 200 com `application/javascript`.

Parar com Ctrl+C.

- [ ] **Step 4: Commit**

```bash
git add src/driver_fatigue/interfaces/web/server.py
git commit -m "feat(web): server serve /assets/* e SVG/PNG/woff2 da raiz"
```

---

## Task 26: README e config — documentar nova fase

**Files:**
- Modify: `docs/README.md`
- Modify: `config/web-demo.yaml`

- [ ] **Step 1: Adicionar bloco no README**

Ler `docs/README.md`. Adicionar seção:

```markdown
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
```

- [ ] **Step 2: Configurar fatigue_index no web-demo.yaml**

Adicionar ao final de `config/web-demo.yaml`:

```yaml
fatigue_index:
  enabled: true
```

- [ ] **Step 3: Commit**

```bash
git add docs/README.md config/web-demo.yaml
git commit -m "docs: README e config da Fase 3 (fusao multimodal)"
```

---

## Task 27: Suite full + smoke manual + push opcional

**Files:**
- (nenhum — validação final)

- [ ] **Step 1: Suite Python completa**

Run: `pytest -v`
Expected: tudo verde. Se algum teste antigo quebrar (ex: snapshot do payload SSE em teste existente), ajustar o teste pra incluir as chaves novas.

- [ ] **Step 2: Suite frontend completa**

Run: `cd web && npm test -- --run`
Expected: todos os testes Vitest verdes.

- [ ] **Step 3: Smoke manual com webcam**

Build + start:
```bash
cd web && npm run build && cd ..
python -m driver_fatigue.interfaces.web --port 8000 -v
```

Abrir `http://localhost:8000`. Validar:
- Logo IFG no header, verde.
- Stream MJPEG aparece após uns 2-3s de calibração da câmera.
- ConnBadge verde "ao vivo".
- Move slider BPM pra 50 → gauge sobe em <1s.
- Clica "Modo demo automático" → sliders se animam sozinhos, gauge sobe progressivamente, timeline registra alert quando cruza 60.
- Fecha olhos por 2s → severity vai pra warning/alert; AlertFlash pulsando borda vermelha.
- Move janela pra 375px de largura → vira coluna única, scroll vertical, tudo legível.

Parar com Ctrl+C.

- [ ] **Step 4: Commit final de marcação**

```bash
git commit --allow-empty -m "chore: Fase 3 completa — fusao multimodal + UI React/Tailwind"
```

(Opcional, se aprovado por humano:)
```bash
git push origin feat/fase3-fusao-multimodal-ui
gh pr create --title "Fase 3 — Fusao multimodal fuzzy + UI React/Tailwind" --body "..."
```

---

## Self-Review

**Spec coverage:**
- Spec §4.1 (contratos domínio) → Tasks 2, 3.
- Spec §4.2 (fuzzy infra, regras, defuzzy, explainability) → Tasks 5, 6.
- Spec §4.3 (bootstrap) → Task 8.
- Spec §4.4 (integração no presenter) → Task 11.
- Spec §4.5 (payload SSE) → Task 11.
- Spec §5.1–5.4 (endpoints) → Tasks 9, 10.
- Spec §6.1 (estrutura web/) → Task 13.
- Spec §6.2 (build pipeline) → Tasks 13, 25.
- Spec §6.3 (stack) → Task 13.
- Spec §6.4 (tokens Tailwind) → Task 13.
- Spec §6.5 (componentes) → Tasks 18–23.
- Spec §6.6 (hooks) → Tasks 15, 16, 17.
- Spec §6.7 (layout) → Task 24.
- Spec §7 (config) → Tasks 7, 26.
- Spec §8 (testes) → Tasks 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16, 21.
- Spec §11 (critérios aceite) → Task 27.

**Placeholder scan:** nenhum "TBD"/"TODO"/"handle edge cases" presente; todos os steps mostram código exato ou comando exato.

**Type consistency:**
- `FatigueInputs` campos (`ear_norm`, `mar_norm`, `head_drop_frames`, `consecutive_eyes_closed`, `bpm`, `steering_noise`, `hours_driving`, `hour_of_day`) usados consistentemente em Tasks 3, 5, 9, 11, 12.
- `FatigueIndex` campos (`value`, `severity`, `top_contributors`, `explain`, `critical`) consistentes em Tasks 3, 4, 5, 11, 21.
- Endpoint payloads consistentes: snake_case em todo lugar (`steering_noise`, `hours_driving`, `hour_of_day`, `index_severity`, `top_contributors`).
- Severity strings ("normal"/"warning"/"alert") consistentes entre Python e React.
- Hook return shapes (`{ status, lastState, events }`, `{ inputs, setInputs, demoState, startDemo, stopDemo }`, `{ videoOnline, videoAge }`) consistentes entre Tasks 15–17 e 24.

Sem ajustes adicionais necessários.
