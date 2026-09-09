"""Loop permanente e processamento dos cartões com alternância de modos."""

from __future__ import annotations

from pathlib import Path
import signal
import sys
import time

from src.modulo_central.gestor_modo import (
    GestorModo,
    InterrupcaoModo,
    MODO_CADASTRO,
    MODO_PRODUCAO,
)
from src.modulo_central.setup_sistema import Sistema
from src.modulo_database.database import DecisaoAcesso
from src.modulo_leitor.leitor import ErroLeitor
from src.modulo_leitor.setup_leitor import EXECUTAVEL_PADRAO, setup_leitor


def executar_loop(
    sistema: Sistema,
    gestor: GestorModo | None = None,
) -> None:
    """Aguarda continuamente os UIDs ou alterna para cadastro quando solicitado."""
    if gestor is None:
        gestor = GestorModo()

    gestor.gravar_pid_servico()
    gestor.gravar_modo(MODO_PRODUCAO)

    def _tratar_sigusr1(signum: int, frame: object) -> None:
        raise InterrupcaoModo(MODO_CADASTRO)

    def _tratar_sigusr2(signum: int, frame: object) -> None:
        raise InterrupcaoModo(MODO_PRODUCAO)

    def _tratar_sigterm(signum: int, frame: object) -> None:
        sys.exit(0)

    if sys.platform != "win32":
        if hasattr(signal, "SIGUSR1"):
            signal.signal(signal.SIGUSR1, _tratar_sigusr1)
        if hasattr(signal, "SIGUSR2"):
            signal.signal(signal.SIGUSR2, _tratar_sigusr2)
        if hasattr(signal, "SIGTERM"):
            signal.signal(signal.SIGTERM, _tratar_sigterm)

    print(f"Sistema iniciado em MODO PRODUÇÃO. Leitor pronto: {sistema.leitor.nome_dispositivo}")

    leitor_aberto = True
    try:
        while True:
            modo_atual = gestor.obter_modo_atual()

            if modo_atual == MODO_CADASTRO:
                if leitor_aberto:
                    sistema.leitor.encerrar()
                    leitor_aberto = False
                    print("[MODO CADASTRO] Leitor PN532 liberado da porta. Pronto para novos cadastros ou troca de cartões.")

                try:
                    time.sleep(0.5)
                except InterrupcaoModo as mudanca:
                    if mudanca.novo_modo == MODO_PRODUCAO:
                        gestor.gravar_modo(MODO_PRODUCAO)
                continue

            # MODO_PRODUCAO
            if not leitor_aberto:
                print("[MODO PRODUÇÃO] Reativando leitor PN532 para controle de acesso...")
                executavel = (
                    sistema.configuracao.executavel_leitor
                    if sistema.configuracao is not None
                    else getattr(sistema.leitor, "executavel", EXECUTAVEL_PADRAO)
                )
                timeout_setup = (
                    sistema.configuracao.timeout_setup_leitor
                    if sistema.configuracao is not None
                    else 10.0
                )
                try:
                    sistema.leitor = setup_leitor(
                        executavel=executavel,
                        timeout_setup=timeout_setup,
                    )
                    leitor_aberto = True
                    print(f"Leitor pronto: {sistema.leitor.nome_dispositivo}")
                except ErroLeitor as erro:
                    print(f"Aviso: falha temporária ao inicializar leitor: {erro}. Nova tentativa em 1s...")
                    time.sleep(1.0)
                    continue

            try:
                uid = sistema.leitor.ler()
                if uid is not None:
                    processar_uid(sistema, uid)
            except InterrupcaoModo as mudanca:
                if mudanca.novo_modo == MODO_CADASTRO:
                    gestor.gravar_modo(MODO_CADASTRO)
                    if leitor_aberto:
                        sistema.leitor.encerrar()
                        leitor_aberto = False
                        print("[MODO CADASTRO] Leitor PN532 liberado da porta. Pronto para novos cadastros ou troca de cartões.")
            except ErroLeitor as erro:
                print(f"Aviso: falha de leitura no leitor PN532: {erro}. Reiniciando...")
                if leitor_aberto:
                    sistema.leitor.encerrar()
                    leitor_aberto = False
                time.sleep(0.5)
    finally:
        if leitor_aberto:
            sistema.leitor.encerrar()
        sistema.rele.desligar()
        gestor.limpar_pid()
        gestor.gravar_modo(MODO_PRODUCAO)


def processar_uid(sistema: Sistema, uid: str) -> DecisaoAcesso:
    """Consulta um UID e abre a porta quando o acesso é autorizado."""
    decisao = sistema.database.verificar_acesso(uid)

    if decisao.autorizado:
        usuario = decisao.usuario
        print(f"ACESSO AUTORIZADO: {usuario.nome} ({usuario.id_usuario})")
        sistema.rele.abrir_porta()
    else:
        print(f"ACESSO NEGADO: {decisao.motivo}")

    return decisao
