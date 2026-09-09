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
from src.modulo_central.gestor_modo import (
    ErroModoBloqueado,
    GestorModo,
    MODO_CADASTRO,
    MODO_PRODUCAO,
)
from src.modulo_database.database import ErroDatabase
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
    parser.add_argument("--pulsos", type=int, default=3)
    parser.add_argument("--tempo-ligado", type=float, default=0.8)
    parser.add_argument("--tempo-desligado", type=float, default=0.4)
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

    novo = comandos.add_parser(
        "novo-usuario",
        help="assistente interativo: gera próximo ID e lê a tag no PN532",
    )
    novo.add_argument("--nome", help="nome do usuário (opcional, pode digitar interativamente)")
    novo.add_argument("--id", dest="id_usuario", help="ID manual (opcional, gerado automaticamente)")
    novo.add_argument("--timeout", type=float, default=30.0, help="tempo máximo para aproximar a tag")

    trocar = comandos.add_parser(
        "trocar-cartao",
        aliases=["novo-cartao"],
        help="atualiza o cartão de um usuário existente lendo direto no leitor",
    )
    trocar.add_argument("--id", dest="id_usuario", help="ID do usuário")
    trocar.add_argument("--nome", help="nome ou parte do nome do usuário")
    trocar.add_argument("--timeout", type=float, default=30.0, help="tempo máximo para aproximar a nova tag")

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

    comandos.add_parser(
        "modo-cadastro",
        help="alterna o sistema para modo de cadastro e libera o leitor PN532",
    )

    comandos.add_parser(
        "modo-producao",
        help="alterna o sistema para modo de produção e reativa o leitor na porta",
    )

    comandos.add_parser(
        "status",
        help="exibe o modo de operação e estado atual do leitor e do serviço",
    )

    return parser


def executar_comando_terminal(args: argparse.Namespace) -> int:
    """Executa um comando administrativo que não seja o loop permanente."""
    gestor = GestorModo()

    if args.comando == "modo-cadastro":
        gestor.alternar_para_modo_cadastro()
        pid = gestor.obter_pid_servico()
        if pid is not None:
            print(f"Sistema alternado para MODO DE CADASTRO. O serviço principal (PID {pid}) liberou o leitor PN532.")
        else:
            print("Sistema alternado para MODO DE CADASTRO (o serviço principal não está em execução).")
        return 0

    if args.comando == "modo-producao":
        gestor.alternar_para_modo_producao()
        pid = gestor.obter_pid_servico()
        if pid is not None:
            print(f"Sistema retornado para MODO DE PRODUÇÃO. O serviço principal (PID {pid}) reativou o leitor na porta.")
        else:
            print("Sistema alternado para MODO DE PRODUÇÃO (o serviço principal não está em execução).")
        return 0

    database = setup_database(args.database)

    if args.comando == "status":
        modo = gestor.obter_modo_atual()
        pid = gestor.obter_pid_servico()
        usuarios = database.listar_usuarios()
        print("=" * 44)
        print("        STATUS DO SISTEMA - PORTA GEAR      ")
        print("=" * 44)
        print(f"Modo de operação  : {modo}")
        if pid is not None:
            estado_servico = f"ATIVO (PID {pid})"
            if modo == MODO_CADASTRO:
                estado_leitor = "LIBERADO (Disponível para cadastros)"
            else:
                estado_leitor = "OCUPADO (Monitorando porta)"
        else:
            estado_servico = "PARADO"
            estado_leitor = "LIVRE (Serviço não iniciado)"
        print(f"Serviço da porta  : {estado_servico}")
        print(f"Leitor PN532      : {estado_leitor}")
        print(f"Banco de dados    : {args.database}")
        print(f"Total de usuários : {len(usuarios)}")
        print("=" * 44)
        return 0

    if args.comando in {"novo-usuario", "trocar-cartao", "novo-cartao", "ler-cartao"}:
        gestor.validar_permissao_leitor(args.comando)

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

    if args.comando == "novo-usuario":
        nome = args.nome
        if not nome:
            try:
                nome = input("Digite o nome do usuário: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nOperação cancelada.")
                return 1
            if not nome:
                print("Erro: O nome do usuário não pode ser vazio.")
                return 1

        id_usuario = args.id_usuario or database.proximo_id_disponivel()
        print(f"ID atribuído: {id_usuario}")
        print("Aproxime o cartão/tag do leitor PN532...")

        leitor = setup_leitor(
            executavel=args.executavel_leitor,
            timeout_setup=args.timeout_setup_leitor,
        )
        try:
            uid_cartao = leitor.ler(args.timeout)
        finally:
            leitor.encerrar()

        if uid_cartao is None:
            print("Tempo esgotado. Nenhum cartão detectado.")
            return 1

        print(f"Cartão detectado: {uid_cartao}")
        existente = database.buscar_usuario_por_uid(uid_cartao)
        if existente is not None:
            print(f"Erro: Cartão já cadastrado para {existente.nome} ({existente.id_usuario}).")
            return 1

        try:
            usuario = database.adicionar_usuario(
                id_usuario=id_usuario,
                nome=nome,
                uid_cartao=uid_cartao,
                ativo=True,
            )
            print("\nUsuário cadastrado com sucesso:")
            mostrar_usuario(usuario)
            return 0
        except ErroDatabase as erro:
            print(f"Erro ao cadastrar: {erro}")
            return 1

    if args.comando in {"trocar-cartao", "novo-cartao"}:
        usuario = None
        id_usuario = args.id_usuario
        nome = args.nome

        if not id_usuario and not nome:
            try:
                entrada = input("Digite o ID ou Nome do usuário: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\nOperação cancelada.")
                return 1
            if not entrada:
                print("Erro: Nenhum dado informado.")
                return 1
            usuario = database.buscar_usuario_por_id(entrada)
            if usuario is None:
                nome = entrada

        if usuario is None and id_usuario:
            usuario = database.buscar_usuario_por_id(id_usuario)
            if usuario is None:
                print(f"Erro: Usuário com ID '{id_usuario}' não encontrado.")
                return 1

        if usuario is None and nome:
            candidatos = database.buscar_usuarios_por_nome(nome)
            if not candidatos:
                print(f"Erro: Nenhum usuário encontrado com o nome '{nome}'.")
                return 1
            if len(candidatos) == 1:
                usuario = candidatos[0]
            else:
                print("Mais de um usuário encontrado:")
                for c in candidatos:
                    mostrar_usuario(c)
                try:
                    id_escolhido = input("Digite o ID exato desejado: ").strip()
                except (EOFError, KeyboardInterrupt):
                    print("\nOperação cancelada.")
                    return 1
                usuario = database.buscar_usuario_por_id(id_escolhido)
                if usuario is None:
                    print("ID inválido.")
                    return 1

        if usuario is None:
            print("Erro: Usuário não localizado.")
            return 1

        print(f"Usuário selecionado: {usuario.nome} ({usuario.id_usuario})")
        print(f"Cartão atual: {usuario.uid_cartao}")
        print("Aproxime o NOVO cartão/tag do leitor PN532...")

        leitor = setup_leitor(
            executavel=args.executavel_leitor,
            timeout_setup=args.timeout_setup_leitor,
        )
        try:
            novo_uid = leitor.ler(args.timeout)
        finally:
            leitor.encerrar()

        if novo_uid is None:
            print("Tempo esgotado. Nenhum cartão detectado.")
            return 1

        print(f"Novo cartão detectado: {novo_uid}")

        if novo_uid == usuario.uid_cartao:
            print("Aviso: Esse já é o cartão cadastrado para este usuário.")
            return 0

        existente = database.buscar_usuario_por_uid(novo_uid)
        if existente is not None:
            print(f"Erro: Este cartão já está cadastrado para {existente.nome} ({existente.id_usuario}).")
            return 1

        try:
            usuario_atualizado = database.alterar_usuario(usuario.id_usuario, uid_cartao=novo_uid)
            print("\nCartão atualizado com sucesso:")
            mostrar_usuario(usuario_atualizado)
            return 0
        except ErroDatabase as erro:
            print(f"Erro ao atualizar cartão: {erro}")
            return 1

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
