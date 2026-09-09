"""Pequenas funções compartilhadas pelo módulo central."""

from __future__ import annotations

import argparse

from src.modulo_central.setup_sistema import ConfiguracaoSistema
from src.modulo_database.database import DecisaoAcesso, Usuario
from src.modulo_rele.rele import ConfiguracaoRele
from src.modulo_rele.setup_rele import setup_rele


def configuracao_sistema_pelos_argumentos(
    args: argparse.Namespace,
) -> ConfiguracaoSistema:
    """Converte argumentos do terminal na configuração geral."""
    return ConfiguracaoSistema(
        caminho_database=args.database,
        numero_gpio_rele=args.gpio_rele,
        quantidade_pulsos=args.pulsos,
        tempo_rele_ligado=args.tempo_ligado,
        tempo_rele_desligado=args.tempo_desligado,
        executavel_leitor=args.executavel_leitor,
        timeout_setup_leitor=args.timeout_setup_leitor,
    )


def setup_rele_pelos_argumentos(args: argparse.Namespace):
    """Prepara o relé usando os parâmetros informados no terminal."""
    configuracao = ConfiguracaoRele(
        quantidade_pulsos=args.pulsos,
        tempo_ligado=args.tempo_ligado,
        tempo_desligado=args.tempo_desligado,
    )
    return setup_rele(
        numero_gpio=args.gpio_rele,
        configuracao=configuracao,
    )


def finalizar_decisao(
    decisao: DecisaoAcesso,
    args: argparse.Namespace,
    abrir_porta: bool,
) -> int:
    """Mostra a decisão e opcionalmente aciona o relé."""
    if not decisao.autorizado:
        print(f"ACESSO NEGADO: {decisao.motivo}")
        return 1

    usuario = decisao.usuario
    print(f"ACESSO AUTORIZADO: {usuario.nome} ({usuario.id_usuario})")
    if abrir_porta:
        rele = setup_rele_pelos_argumentos(args)
        rele.abrir_porta()
        print("Porta acionada.")
    return 0


def mostrar_usuario(usuario: Usuario) -> None:
    """Exibe um cadastro em uma linha."""
    estado = "ativo" if usuario.ativo else "inativo"
    print(
        f"{usuario.id_usuario} | {usuario.nome} | "
        f"{usuario.uid_cartao} | {estado}"
    )


def mostrar_registros(registros) -> None:
    """Exibe os registros de acesso no terminal."""
    if not registros:
        print("Nenhum acesso registrado.")
        return

    for registro in registros:
        estado = "AUTORIZADO" if registro["granted"] else "NEGADO"
        id_usuario = registro["user_id"] or "-"
        nome_usuario = registro["user_name"] if "user_name" in registro.keys() and registro["user_name"] else "-"
        print(
            f"{registro['occurred_at']} | {estado} | {id_usuario} | {nome_usuario} | "
            f"{registro['card_uid']} | {registro['reason']}"
        )
