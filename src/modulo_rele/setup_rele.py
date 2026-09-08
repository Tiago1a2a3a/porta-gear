"""Inicialização do relé da fechadura."""

from __future__ import annotations

from pathlib import Path
from typing import Callable
import time

from .rele import ConfiguracaoRele, ReleLuckfox


def setup_rele(
    *,
    numero_gpio: int = 52,
    chip_gpio: str | None = None,
    linha_offset: int | None = None,
    raiz_sysfs: Path = Path("/sys/class/gpio"),
    configuracao: ConfiguracaoRele = ConfiguracaoRele(),
    esperar: Callable[[float], None] = time.sleep,
    modo_assincrono: bool = True,
) -> ReleLuckfox:
    """Cria, configura e devolve o relé pronto para uso."""
    rele = ReleLuckfox(
        numero_gpio=numero_gpio,
        chip_gpio=chip_gpio,
        linha_offset=linha_offset,
        raiz_sysfs=raiz_sysfs,
        configuracao=configuracao,
        esperar=esperar,
        modo_assincrono=modo_assincrono,
    )
    rele.configurar()
    return rele

