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
    FatigueIndex,
    FatigueInputs,
    circadian_risk,
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
        # eyes_closed = 1 - ear_norm: 0.0 = olhos abertos, 1.0 = olhos fechados
        eyes = ctrl.Antecedent(np.linspace(0, 1, 100), "eyes_closed")
        eyes["aberto"]  = fuzz.trapmf(eyes.universe, [0.0, 0.0, 0.15, 0.30])
        eyes["parcial"] = fuzz.trimf(eyes.universe, [0.25, 0.45, 0.65])
        eyes["fechado"] = fuzz.trapmf(eyes.universe, [0.55, 0.72, 1.0, 1.0])

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
        idx["normal"]  = fuzz.trapmf(idx.universe, [0,   0,  2,  5])
        idx["atencao"] = fuzz.trimf(idx.universe, [35, 52, 70])
        idx["alerta"]  = fuzz.trimf(idx.universe, [55, 70, 85])
        idx["critico"] = fuzz.trapmf(idx.universe, [45, 60, 100, 100])

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

        if value < 35:
            severity = "normal"
        elif value < 60:
            severity = "warning"
        else:
            severity = "alert"
        critical = value >= 80

        top, explain = self._top_contributors(sim, inp, value)
        return FatigueIndex(
            value=value, severity=severity,
            top_contributors=top, explain=explain, critical=critical,
        )

    def _top_contributors(self, sim, inp: FatigueInputs, value: float) -> tuple[tuple[str, ...], str]:
        """Top regras ativadas. scikit-fuzzy 0.5.0 nao expoe _aggregate_firing
        consistentemente, entao caimos numa heuristica baseada nos inputs:
        qual antecedente esta mais 'ruim' (longe do baseline saudavel)."""
        if value < 35:
            return (), ""

        # Heuristica: ranking de inputs por "gravidade" pra essa pessoa
        scores: list[tuple[str, float]] = []
        # eyes_closed: quanto menor ear_norm, pior
        eyes_bad = max(0.0, 1.0 - inp.ear_norm)
        if eyes_bad > 0.4:
            scores.append(("R1" if inp.head_drop_frames > 10 else "R4", eyes_bad))
        # mouth: quanto maior mar_norm (>0.5), mais perto de bocejo
        if inp.mar_norm > 0.5:
            scores.append(("R2" if eyes_bad > 0.5 else "R3", inp.mar_norm))
        # head_drop: pesado domina
        if inp.head_drop_frames >= 35:
            scores.append(("R10", inp.head_drop_frames / 60.0))
        elif inp.head_drop_frames >= 8:
            scores.append(("R1", inp.head_drop_frames / 60.0))
        # bpm: baixo
        if inp.bpm < 60:
            scores.append(("R4" if eyes_bad > 0.3 else "R5", (60 - inp.bpm) / 20))
        # tempo: longo
        if inp.hours_driving > 5:
            scores.append(("R8" if circadian_risk(inp.hour_of_day) > 0.5 else "R3", inp.hours_driving / 10))
        # steering
        if inp.steering_noise > 0.5:
            scores.append(("R6", inp.steering_noise))

        # dedup mantendo a maior pontuacao por label
        by_label: dict[str, float] = {}
        for label, s in scores:
            by_label[label] = max(by_label.get(label, 0.0), s)
        ordered = sorted(by_label.items(), key=lambda x: x[1], reverse=True)
        top_labels = tuple(lbl for lbl, _ in ordered[:2])
        if not top_labels:
            # Index alto mas nada cruzou os thresholds — fallback generico
            return ("R11",), "padrao multivariado"
        human = [_RULE_LABELS.get(lbl, lbl) for lbl in top_labels]
        return top_labels, " + ".join(human)
