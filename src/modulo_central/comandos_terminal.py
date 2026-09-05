"""Definição e execução dos comandos administrativos do terminal."""

from __future__ import annotations

import argparse
from pathlib import Path

from src.modulo_central.funcoes_auxiliares import (
    finalizar_decisao,
    mostrar_registros,
    mostrar_usuario,
    setup_rele_pelos_argumentos,
)
from src.modulo_database.setup_database import CAMINHO_DATABASE_PADRAO, setup_database
from src.modulo_leitor.setup_leitor import EXECUTAVEL_PADRAO, setup_leitor


def criar_parser() -> argparse.ArgumentParser:
    """Cria os argumentos aceitos pelo programa."""
    parser = argparse.ArgumentParser(
        description="Controle de acesso local do Luckfox Pico Ultra."
    )
    parser.add_argument(
        "--database",
        type=Path,
        default=CAMINHO_DATABASE_PADRAO,
        help="arquivo SQLite local",
    )
    parser.add_argument("--gpio-rele", type=int, default=52)
    parser.add_argument("--pulsos", type=int, default=1)
    parser.add_argument("--tempo-ligado", type=float, default=1.0)
    parser.add_argument("--tempo-desligado", type=float, default=0.0)
    parser.add_argument(
        "--executavel-leitor",
        type=Path,
        default=EXECUTAVEL_PADRAO,
        help="caminho do leitor PN532 persistente",
    )
    parser.add_argument("--timeout-setup-leitor", type=float, default=10.0)

    comandos = parser.add_subparsers(dest="comando", required=True)

    comandos.add_parser(
        "executar",
        help="inicializa o sistema e começa o loop permanente",
    )

    comandos.add_parser("inicializar-banco", help="cria as tabelas locais")

    cadastrar = comandos.add_parser("cadastrar-usuario")
    cadastrar.add_argument("--id", required=True, dest="id_usuario")
    cadastrar.add_argument("--nome", required=True)
    cadastrar.add_argument("--uid", required=True, dest="uid_cartao")
    cadastrar.add_argument("--inativo", action="store_true")

    comandos.add_parser("listar-usuarios")

    alterar = comandos.add_parser("alterar-usuario")
    alterar.add_argument("--id", required=True, dest="id_usuario")
    alterar.add_argument("--nome")
    alterar.add_argument("--uid", dest="uid_cartao")
    estado = alterar.add_mutually_exclusive_group()
    estado.add_argument("--ativo", action="store_true", dest="ativo")
    estado.add_argument("--inativo", action="store_false", dest="ativo")
    alterar.set_defaults(ativo=None)

    for nome, ativo in (
        ("ativar-usuario", True),
        ("desativar-usuario", False),
    ):
        comando = comandos.add_parser(nome)
        comando.add_argument("--id", required=True, dest="id_usuario")
        comando.set_defaults(ativo=ativo)

    remover = comandos.add_parser("remover-usuario")
    remover.add_argument("--id", required=True, dest="id_usuario")

    autorizar = comandos.add_parser("autorizar")
    autorizar.add_argument("--uid", required=True, dest="uid_cartao")
    autorizar.add_argument("--abrir-porta", action="store_true")

    ler = comandos.add_parser("ler-cartao")
    ler.add_argument("--abrir-porta", action="store_true")
    ler.add_argument("--timeout", type=float, default=30.0)

    comandos.add_parser("abrir-porta")

    registros = comandos.add_parser("registros")
    registros.add_argument("--limite", type=int, default=20)

    return parser


def executar_comando_terminal(args: argparse.Namespace) -> int:
    """Executa um comando administrativo que não seja o loop permanente."""
    database = setup_database(args.database)

    if args.comando == "inicializar-banco":
        print(f"Banco local pronto: {args.database}")
        return 0

    if args.comando == "cadastrar-usuario":
        usuario = database.adicionar_usuario(
            args.id_usuario,
            args.nome,
            args.uid_cartao,
            ativo=not args.inativo,
        )
        mostrar_usuario(usuario)
        return 0

    if args.comando == "listar-usuarios":
        usuarios = database.listar_usuarios()
        if not usuarios:
            print("Nenhum usuário cadastrado.")
        for usuario in usuarios:
            mostrar_usuario(usuario)
        return 0

    if args.comando == "alterar-usuario":
        usuario = database.alterar_usuario(
            args.id_usuario,
            nome=args.nome,
            uid_cartao=args.uid_cartao,
            ativo=args.ativo,
        )
        print("Usuário alterado:")
        mostrar_usuario(usuario)
        return 0

    if args.comando in {"ativar-usuario", "desativar-usuario"}:
        if not database.definir_usuario_ativo(args.id_usuario, args.ativo):
            print("Usuário não encontrado.")
            return 1
        estado = "ativado" if args.ativo else "desativado"
        print(f"Usuário {args.id_usuario} {estado}.")
        return 0

    if args.comando == "remover-usuario":
        if not database.remover_usuario(args.id_usuario):
            print("Usuário não encontrado.")
            return 1
        print(f"Usuário {args.id_usuario} removido.")
        return 0

    if args.comando == "autorizar":
        decisao = database.verificar_acesso(args.uid_cartao)
        return finalizar_decisao(decisao, args, args.abrir_porta)

    if args.comando == "ler-cartao":
        leitor = setup_leitor(
            executavel=args.executavel_leitor,
            timeout_setup=args.timeout_setup_leitor,
        )
        try:
            uid = leitor.ler(args.timeout)
        finally:
            leitor.encerrar()
        if uid is None:
            print("Nenhum cartão detectado.")
            return 1
        print(f"UID lido: {uid}")
        decisao = database.verificar_acesso(uid)
        return finalizar_decisao(decisao, args, args.abrir_porta)

    if args.comando == "abrir-porta":
        rele = setup_rele_pelos_argumentos(args)
        rele.abrir_porta()
        print("Porta acionada.")
        return 0

    if args.comando == "registros":
        mostrar_registros(database.acessos_recentes(args.limite))
        return 0

    raise AssertionError(f"Comando administrativo não tratado: {args.comando}")
