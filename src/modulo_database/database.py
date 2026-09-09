"""Operações do banco SQLite local.

Este arquivo contém somente regras de dados. A criação e a preparação da
instância usada pelo sistema ficam em ``setup_database.py``.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
import hashlib
import hmac
from pathlib import Path
import secrets
import sqlite3


class ErroDatabase(Exception):
    """Erro de validação ou persistência do banco local."""


@dataclass(frozen=True)
class Usuario:
    id_usuario: str
    nome: str
    uid_cartao: str
    ativo: bool


@dataclass(frozen=True)
class DecisaoAcesso:
    uid_cartao: str
    autorizado: bool
    motivo: str
    usuario: Usuario | None


def normalizar_uid(valor: str) -> str:
    """Converte o UID para hexadecimal maiúsculo sem separadores."""
    uid = "".join(
        caractere
        for caractere in valor.upper()
        if caractere not in " :-\t\r\n"
    )

    if len(uid) < 8 or len(uid) % 2 != 0:
        raise ErroDatabase(
            "UID inválido. Informe bytes hexadecimais, por exemplo 04A1B2C3."
        )
    if any(caractere not in "0123456789ABCDEF" for caractere in uid):
        raise ErroDatabase("UID inválido. Use somente caracteres hexadecimais.")

    return uid


class BancoAcesso:
    """Cadastro, consulta e registro de acessos no SQLite."""

    def __init__(self, caminho: str | Path):
        self.caminho = Path(caminho)

    def _conectar(self) -> sqlite3.Connection:
        self.caminho.parent.mkdir(parents=True, exist_ok=True)
        conexao = sqlite3.connect(self.caminho)
        conexao.row_factory = sqlite3.Row
        conexao.execute("PRAGMA foreign_keys = ON")
        conexao.execute("PRAGMA busy_timeout = 5000")
        return conexao

    @contextmanager
    def _sessao(self):
        conexao = self._conectar()
        try:
            yield conexao
            conexao.commit()
        except Exception:
            conexao.rollback()
            raise
        finally:
            conexao.close()

    def inicializar(self) -> None:
        """Cria as tabelas necessárias quando ainda não existem."""
        with self._sessao() as conexao:
            conexao.executescript(
                """
                CREATE TABLE IF NOT EXISTS users (
                    user_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    card_uid TEXT NOT NULL UNIQUE,
                    is_active INTEGER NOT NULL DEFAULT 1
                        CHECK (is_active IN (0, 1)),
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS access_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT,
                    card_uid TEXT NOT NULL,
                    granted INTEGER NOT NULL CHECK (granted IN (0, 1)),
                    reason TEXT NOT NULL,
                    occurred_at TEXT NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_access_log_occurred_at
                    ON access_log (occurred_at DESC);

                CREATE TABLE IF NOT EXISTS system_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                """
            )
        self.inicializar_senha_admin()

    def obter_config(self, chave: str, padrao: str | None = None) -> str | None:
        """Obtém um valor de configuração do sistema."""
        with self._sessao() as conexao:
            linha = conexao.execute(
                "SELECT value FROM system_config WHERE key = ?",
                (chave,),
            ).fetchone()
            if linha is None:
                return padrao
            return linha["value"]

    def gravar_config(self, chave: str, valor: str) -> None:
        """Salva ou atualiza uma configuração do sistema."""
        agora = _timestamp()
        with self._sessao() as conexao:
            conexao.execute(
                """
                INSERT INTO system_config (key, value, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    value = excluded.value,
                    updated_at = excluded.updated_at
                """,
                (chave, valor, agora),
            )

    def _gerar_hash_senha(self, senha: str, salt: bytes) -> str:
        """Gera hash PBKDF2-HMAC-SHA256 (100.000 iterações)."""
        return hashlib.pbkdf2_hmac(
            "sha256",
            senha.encode("utf-8"),
            salt,
            100_000,
        ).hex()

    def inicializar_senha_admin(self, senha_padrao: str = "123456789") -> None:
        """Garante que haja uma senha de administrador cadastrada no banco."""
        salt_hex = self.obter_config("admin_password_salt")
        hash_armazenado = self.obter_config("admin_password_hash")
        if not salt_hex or not hash_armazenado:
            self.definir_senha_admin(senha_padrao)

    def definir_senha_admin(self, nova_senha: str) -> None:
        """Define uma nova senha de administrador calculando novo salt e hash."""
        nova_senha = (nova_senha or "").strip()
        if len(nova_senha) < 4:
            raise ErroDatabase("A senha de administrador deve ter no mínimo 4 caracteres.")

        salt = secrets.token_bytes(16)
        hash_hex = self._gerar_hash_senha(nova_senha, salt)
        self.gravar_config("admin_password_salt", salt.hex())
        self.gravar_config("admin_password_hash", hash_hex)

    def verificar_senha_admin(self, senha: str) -> bool:
        """Verifica se a senha fornecida confere com a gravada no banco."""
        salt_hex = self.obter_config("admin_password_salt")
        hash_armazenado = self.obter_config("admin_password_hash")

        if not salt_hex or not hash_armazenado:
            self.inicializar_senha_admin()
            salt_hex = self.obter_config("admin_password_salt")
            hash_armazenado = self.obter_config("admin_password_hash")

        try:
            salt = bytes.fromhex(salt_hex)
            hash_calculado = self._gerar_hash_senha(senha, salt)
            return hmac.compare_digest(hash_calculado, hash_armazenado)
        except Exception:
            return False

    def alterar_senha_admin(self, senha_atual: str, nova_senha: str) -> bool:
        """Altera a senha de administrador validando a senha atual."""
        if not self.verificar_senha_admin(senha_atual):
            raise ErroDatabase("A senha atual informada está incorreta.")
        self.definir_senha_admin(nova_senha)
        return True

    def adicionar_usuario(
        self,
        id_usuario: str,
        nome: str,
        uid_cartao: str,
        ativo: bool = True,
    ) -> Usuario:
        """Adiciona um usuário e impede IDs ou cartões duplicados."""
        id_usuario = id_usuario.strip()
        nome = nome.strip()
        uid_cartao = normalizar_uid(uid_cartao)

        if not id_usuario:
            raise ErroDatabase("O ID do usuário é obrigatório.")
        if not nome:
            raise ErroDatabase("O nome do usuário é obrigatório.")

        agora = _timestamp()
        try:
            with self._sessao() as conexao:
                conexao.execute(
                    """
                    INSERT INTO users
                        (user_id, name, card_uid, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (id_usuario, nome, uid_cartao, int(ativo), agora, agora),
                )
        except sqlite3.IntegrityError as erro:
            raise ErroDatabase(
                "ID de usuário ou UID do cartão já cadastrado."
            ) from erro

        return Usuario(id_usuario, nome, uid_cartao, ativo)

    def listar_usuarios(self) -> list[Usuario]:
        """Retorna todos os usuários em ordem alfabética."""
        with self._sessao() as conexao:
            linhas = conexao.execute(
                """
                SELECT user_id, name, card_uid, is_active
                FROM users
                ORDER BY name, user_id
                """
            ).fetchall()
        return [_usuario_da_linha(linha) for linha in linhas]

    def buscar_usuario_por_uid(self, uid_cartao: str) -> Usuario | None:
        """Procura um cadastro pelo UID do cartão."""
        uid_cartao = normalizar_uid(uid_cartao)
        with self._sessao() as conexao:
            linha = conexao.execute(
                """
                SELECT user_id, name, card_uid, is_active
                FROM users
                WHERE card_uid = ?
                """,
                (uid_cartao,),
            ).fetchone()
        return _usuario_da_linha(linha) if linha is not None else None

    def alterar_usuario(
        self,
        id_usuario: str,
        *,
        nome: str | None = None,
        uid_cartao: str | None = None,
        ativo: bool | None = None,
    ) -> Usuario:
        """Altera somente os campos informados de um cadastro existente."""
        if nome is None and uid_cartao is None and ativo is None:
            raise ErroDatabase("Informe pelo menos um campo para alterar.")

        campos: list[str] = []
        valores: list[str | int] = []

        if nome is not None:
            nome = nome.strip()
            if not nome:
                raise ErroDatabase("O nome do usuário não pode ficar vazio.")
            campos.append("name = ?")
            valores.append(nome)

        if uid_cartao is not None:
            campos.append("card_uid = ?")
            valores.append(normalizar_uid(uid_cartao))

        if ativo is not None:
            campos.append("is_active = ?")
            valores.append(int(ativo))

        campos.append("updated_at = ?")
        valores.append(_timestamp())
        valores.append(id_usuario)

        try:
            with self._sessao() as conexao:
                cursor = conexao.execute(
                    f"UPDATE users SET {', '.join(campos)} WHERE user_id = ?",
                    valores,
                )
        except sqlite3.IntegrityError as erro:
            raise ErroDatabase("O novo UID já pertence a outro usuário.") from erro

        if cursor.rowcount != 1:
            raise ErroDatabase("Usuário não encontrado.")

        usuario = self.buscar_usuario_por_id(id_usuario)
        if usuario is None:
            raise ErroDatabase("Usuário não encontrado após a alteração.")
        return usuario

    def proximo_id_disponivel(self) -> str:
        """Calcula o próximo ID sequencial formatado com 3 dígitos (ex: 001, 002...)."""
        with self._sessao() as conexao:
            linhas = conexao.execute("SELECT user_id FROM users").fetchall()

        ids_numericos: list[int] = []
        for linha in linhas:
            uid_str = str(linha["user_id"]).strip()
            try:
                ids_numericos.append(int(uid_str))
            except ValueError:
                pass

        proximo = max(ids_numericos, default=0) + 1
        return f"{proximo:03d}"

    def buscar_usuario_por_id(self, id_usuario: str) -> Usuario | None:
        """Procura um cadastro pelo ID do usuário."""
        with self._sessao() as conexao:
            linha = conexao.execute(
                """
                SELECT user_id, name, card_uid, is_active
                FROM users
                WHERE user_id = ?
                """,
                (id_usuario,),
            ).fetchone()
        return _usuario_da_linha(linha) if linha is not None else None

    def buscar_usuarios_por_nome(self, nome: str) -> list[Usuario]:
        """Busca usuários ativos ou inativos pelo nome aproximado."""
        termo = nome.strip()
        if not termo:
            return []
        with self._sessao() as conexao:
            linhas = conexao.execute(
                """
                SELECT user_id, name, card_uid, is_active
                FROM users
                WHERE name LIKE ? AND name NOT LIKE '%-exl'
                ORDER BY user_id ASC
                """,
                (f"%{termo}%",),
            ).fetchall()
        return [_usuario_da_linha(linha) for linha in linhas]

    def definir_usuario_ativo(self, id_usuario: str, ativo: bool) -> bool:
        """Ativa ou desativa um cadastro."""
        with self._sessao() as conexao:
            cursor = conexao.execute(
                """
                UPDATE users
                SET is_active = ?, updated_at = ?
                WHERE user_id = ?
                """,
                (int(ativo), _timestamp(), id_usuario),
            )
        return cursor.rowcount == 1

    def remover_usuario(self, id_usuario: str) -> bool:
        """Marca o usuário como removido no banco, mantendo seu histórico com o sufixo -exl."""
        usuario = self.buscar_usuario_por_id(id_usuario)
        if usuario is None or usuario.nome.endswith("-exl"):
            return False

        novo_nome = f"{usuario.nome}-exl"
        novo_uid = f"{usuario.uid_cartao}-EXL-{id_usuario}"
        with self._sessao() as conexao:
            cursor = conexao.execute(
                """
                UPDATE users
                SET name = ?, card_uid = ?, is_active = 0, updated_at = ?
                WHERE user_id = ?
                """,
                (novo_nome, novo_uid, _timestamp(), id_usuario),
            )
        return cursor.rowcount == 1

    def verificar_acesso(self, uid_cartao: str) -> DecisaoAcesso:
        """Verifica cadastro e estado ativo e registra o resultado."""
        uid_cartao = normalizar_uid(uid_cartao)
        usuario = self.buscar_usuario_por_uid(uid_cartao)

        if usuario is None:
            decisao = DecisaoAcesso(
                uid_cartao,
                False,
                "cartao_nao_cadastrado",
                None,
            )
        elif not usuario.ativo:
            decisao = DecisaoAcesso(
                uid_cartao,
                False,
                "usuario_inativo",
                usuario,
            )
        else:
            decisao = DecisaoAcesso(
                uid_cartao,
                True,
                "acesso_autorizado",
                usuario,
            )

        self.registrar_acesso(decisao)
        return decisao

    def registrar_acesso(self, decisao: DecisaoAcesso) -> None:
        """Grava uma decisão de acesso no histórico local."""
        with self._sessao() as conexao:
            conexao.execute(
                """
                INSERT INTO access_log
                    (user_id, card_uid, granted, reason, occurred_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    decisao.usuario.id_usuario if decisao.usuario else None,
                    decisao.uid_cartao,
                    int(decisao.autorizado),
                    decisao.motivo,
                    _timestamp(),
                ),
            )

    def acessos_recentes(self, limite: int = 20) -> list[sqlite3.Row]:
        """Retorna os registros mais recentes com nome do usuário quando cadastrado."""
        if limite < 1:
            raise ErroDatabase("O limite de registros deve ser maior que zero.")

        with self._sessao() as conexao:
            return conexao.execute(
                """
                SELECT
                    a.id,
                    a.user_id,
                    u.name AS user_name,
                    a.card_uid,
                    a.granted,
                    a.reason,
                    a.occurred_at
                FROM access_log a
                LEFT JOIN users u ON a.user_id = u.user_id
                ORDER BY a.id DESC
                LIMIT ?
                """,
                (limite,),
            ).fetchall()


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _usuario_da_linha(linha: sqlite3.Row) -> Usuario:
    return Usuario(
        id_usuario=linha["user_id"],
        nome=linha["name"],
        uid_cartao=linha["card_uid"],
        ativo=bool(linha["is_active"]),
    )

