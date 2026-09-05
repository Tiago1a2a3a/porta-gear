"""Ponto central: escolhe o fluxo e inicia o sistema."""

from __future__ import annotations

import sys

from src.modulo_central.comandos_terminal import (
    criar_parser,
    executar_comando_terminal,
)
from src.modulo_central.funcoes_auxiliares import (
    configuracao_sistema_pelos_argumentos,
)
from src.modulo_central.loop_sistema import executar_loop
from src.modulo_central.setup_sistema import setup_sistema
from src.modulo_database.database import ErroDatabase
from src.modulo_leitor.leitor import ErroLeitor
from src.modulo_rele.rele import ErroRele


def main(argumentos: list[str] | None = None) -> int:
    args = criar_parser().parse_args(argumentos)

    try:
        if args.comando == "executar":
            configuracao = configuracao_sistema_pelos_argumentos(args)
            sistema = setup_sistema(configuracao)
            executar_loop(sistema)
            return 0

        return executar_comando_terminal(args)
    except KeyboardInterrupt:
        print("\nSistema encerrado pelo operador.")
        return 0
    except (ErroDatabase, ErroLeitor, ErroRele, ValueError) as erro:
        print(f"Erro: {erro}", file=sys.stderr)
        return 2

