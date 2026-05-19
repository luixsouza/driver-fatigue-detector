"""Fallback que desabilita o indice quando scikit-fuzzy nao esta instalado
ou quando o usuario optou por desligar via config."""
from __future__ import annotations

from driver_fatigue.domain.fatigue_index import (
    FatigueIndex,
    FatigueInputs,
    IndexEvaluator,
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
