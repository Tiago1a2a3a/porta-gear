"""Inicialização única do leitor PN532 persistente."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess

from .leitor import ErroLeitor, LeitorPN532


EXECUTAVEL_PADRAO = Path(__file__).resolve().parent / "nativo" / "leitor_pn532"


def setup_leitor(
    *,
    executavel: str | Path = EXECUTAVEL_PADRAO,
    timeout_setup: float = 10.0,
) -> LeitorPN532:
    """Inicia o processo nativo e aguarda o PN532 ficar pronto."""
    if os.name != "posix":
        raise ErroLeitor("O leitor PN532 persistente deve ser executado no Linux do Luckfox.")

    caminho = Path(executavel).expanduser().resolve()
    if not caminho.is_file():
        raise ErroLeitor(
            f"Leitor nativo não encontrado em {caminho}. "
            "Compile-o com: make -C src/modulo_leitor/nativo"
        )
    if not os.access(caminho, os.X_OK):
        raise ErroLeitor(f"O leitor nativo não possui permissão de execução: {caminho}")

    try:
        processo = subprocess.Popen(
            [str(caminho)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
    except OSError as erro:
        raise ErroLeitor(f"Não foi possível iniciar o leitor nativo: {erro}") from erro

    leitor = LeitorPN532(processo, caminho)
    leitor.aguardar_pronto(timeout_setup)
    return leitor

