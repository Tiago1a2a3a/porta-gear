"""Inicialização do banco SQLite."""

from __future__ import annotations

from pathlib import Path

from .database import BancoAcesso


CAMINHO_DATABASE_PADRAO = Path("data/access_control.sqlite3")


def setup_database(
    caminho: str | Path = CAMINHO_DATABASE_PADRAO,
) -> BancoAcesso:
    """Abre o banco e cria as tabelas ausentes uma única vez."""
    banco = BancoAcesso(caminho)
    banco.inicializar()
    return banco

