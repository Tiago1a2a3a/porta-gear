"""Configuração e operação do relé da fechadura."""

from .rele import ConfiguracaoRele, ErroRele, ReleLuckfox
from .setup_rele import setup_rele

__all__ = ["ConfiguracaoRele", "ErroRele", "ReleLuckfox", "setup_rele"]

