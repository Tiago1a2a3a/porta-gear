"""Configuração e leitura persistente do PN532."""

from .leitor import ErroLeitor, LeitorPN532
from .setup_leitor import setup_leitor

__all__ = ["ErroLeitor", "LeitorPN532", "setup_leitor"]
