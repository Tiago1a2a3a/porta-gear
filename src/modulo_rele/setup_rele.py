"""Inicialização do relé da fechadura."""

from __future__ import annotations

from pathlib import Path
from typing import Callable
import time

from .rele import ConfiguracaoRele, ReleLuckfox


def setup_rele(
    *,
    numero_gpio: int = 52,
    raiz_sysfs: Path = Path("/sys/class/gpio"),
    configuracao: ConfiguracaoRele = ConfiguracaoRele(),
    esperar: Callable[[float], None] = time.sleep,
) -> ReleLuckfox:
    """Cria, configura e devolve o relé pronto para uso."""
    rele = ReleLuckfox(
        numero_gpio=numero_gpio,
        raiz_sysfs=raiz_sysfs,
        configuracao=configuracao,
        esperar=esperar,
    )
    rele.configurar()
    return rele

