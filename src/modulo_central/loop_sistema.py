"""Loop permanente e processamento dos cartões."""

from __future__ import annotations

from src.modulo_central.setup_sistema import Sistema
from src.modulo_database.database import DecisaoAcesso


def executar_loop(sistema: Sistema) -> None:
    """Aguarda continuamente os UIDs publicados pelo leitor persistente."""
    print(f"Sistema iniciado. Leitor pronto: {sistema.leitor.nome_dispositivo}")

    try:
        while True:
            uid = sistema.leitor.ler()
            if uid is not None:
                processar_uid(sistema, uid)
    finally:
        sistema.leitor.encerrar()
        sistema.rele.desligar()


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
