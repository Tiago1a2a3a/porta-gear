"""Camada de serviços da aplicação - Porta GEAR.

Provê uma API de serviços limpa e desacoplada contendo todas as regras de negócio
e orquestração do sistema (banco de dados, relé, leitor e gestor de modo).
Esta camada é a única fonte da verdade, sendo consumida tanto pelo Terminal CLI
quanto pela Interface Web HTTP/REST.
"""

from __future__ import annotations

import hmac
import os
from pathlib import Path
import secrets
import sys
import threading
import time
from typing import Any

# Senha mestre única e fixa definida diretamente em código (imutável pela interface web)
SENHA_MESTRE_GEAR: str = "123456789"

from src.modulo_central.gestor_modo import (
    ErroModoBloqueado,
    GestorModo,
    MODO_CADASTRO,
    MODO_PRODUCAO,
)
from src.modulo_database.database import (
    BancoAcesso,
    DecisaoAcesso,
    ErroDatabase,
    Usuario,
    normalizar_uid,
)
from src.modulo_database.setup_database import (
    CAMINHO_DATABASE_PADRAO,
    setup_database,
)
from src.modulo_leitor.setup_leitor import (
    EXECUTAVEL_PADRAO as EXECUTAVEL_LEITOR_PADRAO,
    setup_leitor,
)
from src.modulo_rele.rele import (
    ConfiguracaoRele,
    ErroRele,
    ReleLuckfox,
)
from src.modulo_rele.setup_rele import setup_rele


class ServicosPorta:
    """Orquestrador de serviços desacoplado da Porta GEAR."""

    def __init__(
        self,
        caminho_database: Path | str | None = None,
        database: BancoAcesso | None = None,
        gestor_modo: GestorModo | None = None,
        rele: ReleLuckfox | None = None,
        configuracao_rele: ConfiguracaoRele | None = None,
        numero_gpio_rele: int = 52,
        executavel_leitor: Path | str | None = None,
        senha_mestre: str = SENHA_MESTRE_GEAR,
    ) -> None:
        if database is not None:
            self.database = database
        else:
            db_path = caminho_database or CAMINHO_DATABASE_PADRAO
            self.database = setup_database(db_path)

        self.gestor_modo = gestor_modo or GestorModo()
        self.configuracao_rele = configuracao_rele or ConfiguracaoRele()
        self.numero_gpio_rele = numero_gpio_rele
        self.executavel_leitor = Path(executavel_leitor or EXECUTAVEL_LEITOR_PADRAO)
        self.senha_mestre = str(senha_mestre)

        # Estado da fechadura em memória para atualização síncrona/reativa da UI
        self._estado_porta = {
            "aberta": False,
            "tempo_restante": 0.0,
            "ultimo_acionamento": None,
        }
        self._lock_porta = threading.Lock()

        # Sessões ativas de autenticação web (token -> timestamp de expiração)
        self._sessoes_ativas: dict[str, float] = {}
        self._lock_auth = threading.Lock()

        # Inicializa relé se disponível no ambiente
        self.rele = rele
        self.rele_disponivel = False
        self._inicializar_rele_hardware()

    def _inicializar_rele_hardware(self) -> None:
        """Tenta inicializar o relé físico via sysfs se presente no ambiente."""
        if self.rele is not None:
            self.rele_disponivel = True
            return

        try:
            self.rele = setup_rele(
                numero_gpio=self.numero_gpio_rele,
                configuracao=self.configuracao_rele,
            )
            self.rele_disponivel = True
        except (ErroRele, OSError, Exception):
            # Em computadores de desenvolvimento (Windows/macOS/Linux sem sysfs gpio),
            # opera em modo emulado com aviso sem travar a aplicação.
            self.rele = None
            self.rele_disponivel = False

    def _temporizador_fechar_porta(self, duracao: float = 3.5) -> None:
        """Mantém a porta aberta e atualiza a contagem regressiva para a UI."""
        def _rotina():
            inicio = time.time()
            with self._lock_porta:
                self._estado_porta["aberta"] = True
                self._estado_porta["ultimo_acionamento"] = time.strftime("%H:%M:%S")

            while True:
                passado = time.time() - inicio
                restante = max(0.0, duracao - passado)
                with self._lock_porta:
                    self._estado_porta["tempo_restante"] = round(restante, 1)
                    if restante <= 0:
                        self._estado_porta["aberta"] = False
                        self._estado_porta["tempo_restante"] = 0.0
                        break
                time.sleep(0.2)

        t = threading.Thread(target=_rotina, daemon=True)
        t.start()

    # -------------------------------------------------------------------------
    # 1. STATUS E OPERAÇÃO DO SISTEMA
    # -------------------------------------------------------------------------

    def obter_status(self) -> dict[str, Any]:
        """Consolida o status completo do sistema."""
        modo = self.gestor_modo.obter_modo_atual()
        pid = self.gestor_modo.obter_pid_servico()
        usuarios = self.database.listar_usuarios()

        ativos = sum(1 for u in usuarios if u.ativo and not u.nome.endswith("-exl"))
        total = sum(1 for u in usuarios if not u.nome.endswith("-exl"))

        with self._lock_porta:
            porta_info = dict(self._estado_porta)

        return {
            "sucesso": True,
            "modo": modo,
            "servico": {
                "ativo": pid is not None,
                "pid": pid,
            },
            "porta": porta_info,
            "estatisticas": {
                "total_usuarios": total,
                "usuarios_ativos": ativos,
                "usuarios_inativos": total - ativos,
            },
            "hardware": {
                "rele_ativo": self.rele_disponivel,
                "leitor_nativo_instalado": self.executavel_leitor.is_file(),
            },
        }

    def alternar_modo(self, novo_modo: str) -> dict[str, Any]:
        """Alterna entre MODO_PRODUCAO e MODO_CADASTRO."""
        modo_normalizado = str(novo_modo).strip().upper()
        if modo_normalizado == MODO_CADASTRO:
            self.gestor_modo.alternar_para_modo_cadastro()
            msg = "Sistema alternado para MODO CADASTRO. Leitor liberado para gestão de credenciais."
        elif modo_normalizado == MODO_PRODUCAO:
            self.gestor_modo.alternar_para_modo_producao()
            msg = "Sistema alternado para MODO PRODUÇÃO. Controle de acesso da porta ativo."
        else:
            raise ValueError(f"Modo inválido: '{novo_modo}'. Escolha 'PRODUCAO' ou 'CADASTRO'.")

        return {
            "sucesso": True,
            "modo": modo_normalizado,
            "mensagem": msg,
        }

    # -------------------------------------------------------------------------
    # 2. CONTROLE DA PORTA E FECHADURA
    # -------------------------------------------------------------------------

    def abrir_porta(
        self,
        origem: str = "WEB",
        duracao: float = 3.5,
        acionar_hardware: bool = True,
    ) -> dict[str, Any]:
        """Executa a abertura da porta, aciona o relé físico e registra log."""
        # Atualiza timer do estado visual da porta
        self._temporizador_fechar_porta(duracao)

        # Se disponível e solicitado, aciona o relé físico em thread separada
        if acionar_hardware and self.rele is not None:
            def _acionar_rele():
                try:
                    self.rele.abrir_porta()
                except Exception as e:
                    sys.stderr.write(f"[*] Erro ao pulsar rele fisico: {e}\n")

            threading.Thread(target=_acionar_rele, daemon=True).start()

        # Registra acesso no banco de dados SQLite
        try:
            self.database.registrar_acesso(
                DecisaoAcesso(
                    uid_cartao=origem,
                    autorizado=True,
                    motivo=f"liberacao_remota_{origem.lower()}",
                    usuario=None,
                )
            )
        except Exception:
            pass

        return {
            "sucesso": True,
            "mensagem": "Comando de abertura enviado: fechadura destrancada!",
            "duracao": duracao,
            "hardware_acionado": self.rele is not None,
        }

    # -------------------------------------------------------------------------
    # 3. GESTÃO DE MEMBROS E CREDENCIAIS
    # -------------------------------------------------------------------------

    def cadastrar_usuario(
        self,
        nome: str,
        uid_cartao: str,
        id_usuario: str | None = None,
        ativo: bool = True,
    ) -> dict[str, Any]:
        """Cadastra um novo membro no sistema com validações completas."""
        nome = (nome or "").strip()
        if not nome:
            raise ValueError("O nome do membro é obrigatório.")

        uid_cartao = (uid_cartao or "").strip()
        if not uid_cartao:
            raise ValueError("O UID do cartão RFID é obrigatório.")

        uid_norm = normalizar_uid(uid_cartao)

        if not id_usuario or not str(id_usuario).strip():
            id_usuario = self.database.proximo_id_disponivel()
        else:
            id_usuario = str(id_usuario).strip()

        # Valida se o UID já está em uso por outro usuário ativo/válido
        existente = self.database.buscar_usuario_por_uid(uid_norm)
        if existente is not None:
            raise ErroDatabase(
                f"Cartão '{uid_norm}' já está cadastrado para o membro {existente.nome} ({existente.id_usuario})."
            )

        usuario = self.database.adicionar_usuario(
            id_usuario=id_usuario,
            nome=nome,
            uid_cartao=uid_norm,
            ativo=bool(ativo),
        )

        return {
            "sucesso": True,
            "mensagem": f"Membro '{usuario.nome}' (ID {usuario.id_usuario}) cadastrado com sucesso!",
            "usuario": {
                "id": usuario.id_usuario,
                "nome": usuario.nome,
                "uid_cartao": usuario.uid_cartao,
                "ativo": usuario.ativo,
            },
        }

    def trocar_cartao(self, id_usuario: str, novo_uid: str) -> dict[str, Any]:
        """Substitui o cartão RFID associado a um membro existente."""
        id_usuario = (id_usuario or "").strip()
        if not id_usuario:
            raise ValueError("O ID do membro é obrigatório.")

        novo_uid = (novo_uid or "").strip()
        if not novo_uid:
            raise ValueError("O novo UID do cartão é obrigatório.")

        novo_uid_norm = normalizar_uid(novo_uid)

        usuario = self.database.buscar_usuario_por_id(id_usuario)
        if usuario is None:
            raise ErroDatabase(f"Membro com ID '{id_usuario}' não encontrado.")

        if usuario.uid_cartao == novo_uid_norm:
            return {
                "sucesso": True,
                "mensagem": f"O cartão informado já é o cartão cadastrado para {usuario.nome}.",
                "usuario": {
                    "id": usuario.id_usuario,
                    "nome": usuario.nome,
                    "uid_cartao": usuario.uid_cartao,
                    "ativo": usuario.ativo,
                },
            }

        # Verifica se o novo UID já pertence a outra pessoa
        dono_cartao = self.database.buscar_usuario_por_uid(novo_uid_norm)
        if dono_cartao is not None and dono_cartao.id_usuario != id_usuario:
            raise ErroDatabase(
                f"Este cartão já está cadastrado para {dono_cartao.nome} ({dono_cartao.id_usuario})."
            )

        usuario_atualizado = self.database.alterar_usuario(
            id_usuario=id_usuario,
            uid_cartao=novo_uid_norm,
        )

        return {
            "sucesso": True,
            "mensagem": f"Cartão de '{usuario_atualizado.nome}' atualizado com sucesso para {usuario_atualizado.uid_cartao}!",
            "usuario": {
                "id": usuario_atualizado.id_usuario,
                "nome": usuario_atualizado.nome,
                "uid_cartao": usuario_atualizado.uid_cartao,
                "ativo": usuario_atualizado.ativo,
            },
        }

    def alterar_nome(self, id_usuario: str, novo_nome: str) -> dict[str, Any]:
        """Atualiza o nome de um membro cadastrado."""
        id_usuario = (id_usuario or "").strip()
        if not id_usuario:
            raise ValueError("O ID do membro é obrigatório.")

        novo_nome = (novo_nome or "").strip()
        if not novo_nome:
            raise ValueError("O novo nome não pode ser vazio.")

        usuario = self.database.buscar_usuario_por_id(id_usuario)
        if usuario is None:
            raise ErroDatabase(f"Membro com ID '{id_usuario}' não encontrado.")

        usuario_atualizado = self.database.alterar_usuario(
            id_usuario=id_usuario,
            nome=novo_nome,
        )

        return {
            "sucesso": True,
            "mensagem": f"Nome do membro atualizado para '{usuario_atualizado.nome}'!",
            "usuario": {
                "id": usuario_atualizado.id_usuario,
                "nome": usuario_atualizado.nome,
                "uid_cartao": usuario_atualizado.uid_cartao,
                "ativo": usuario_atualizado.ativo,
            },
        }

    def definir_status_usuario(self, id_usuario: str, ativo: bool) -> dict[str, Any]:
        """Altera o status de bloqueio/liberação (ativo/inativo) do membro."""
        id_usuario = (id_usuario or "").strip()
        if not id_usuario:
            raise ValueError("O ID do membro é obrigatório.")

        sucesso = self.database.definir_usuario_ativo(id_usuario, bool(ativo))
        if not sucesso:
            raise ErroDatabase(f"Membro com ID '{id_usuario}' não encontrado.")

        return {
            "sucesso": True,
            "id": id_usuario,
            "ativo": bool(ativo),
            "mensagem": f"Acesso do membro {'liberado (ATIVO)' if ativo else 'bloqueado (INATIVO)'}.",
        }

    def remover_usuario(self, id_usuario: str) -> dict[str, Any]:
        """Remove o membro das credenciais ativas preservando integridade de auditoria."""
        id_usuario = (id_usuario or "").strip()
        if not id_usuario:
            raise ValueError("O ID do membro é obrigatório.")

        sucesso = self.database.remover_usuario(id_usuario)
        if not sucesso:
            raise ErroDatabase(f"Membro '{id_usuario}' não encontrado ou já removido.")

        return {
            "sucesso": True,
            "id": id_usuario,
            "mensagem": f"Membro '{id_usuario}' removido do controle ativo (histórico preservado).",
        }

    def listar_usuarios(self, busca: str | None = None) -> dict[str, Any]:
        """Lista os membros cadastrados com opção de busca por nome."""
        if busca and busca.strip():
            usuarios = self.database.buscar_usuarios_por_nome(busca.strip())
        else:
            usuarios = self.database.listar_usuarios()

        lista = [
            {
                "id": u.id_usuario,
                "nome": u.nome,
                "uid_cartao": u.uid_cartao,
                "ativo": u.ativo,
                "excluido": u.nome.endswith("-exl"),
            }
            for u in usuarios
        ]

        proximo_id = self.database.proximo_id_disponivel()
        return {
            "sucesso": True,
            "usuarios": lista,
            "proximo_id": proximo_id,
        }

    def obter_usuario(self, id_usuario: str) -> dict[str, Any]:
        """Obtém detalhes de um membro específico."""
        usuario = self.database.buscar_usuario_por_id(id_usuario)
        if usuario is None:
            raise ErroDatabase(f"Membro com ID '{id_usuario}' não encontrado.")

        return {
            "sucesso": True,
            "usuario": {
                "id": usuario.id_usuario,
                "nome": usuario.nome,
                "uid_cartao": usuario.uid_cartao,
                "ativo": usuario.ativo,
                "excluido": usuario.nome.endswith("-exl"),
            },
        }

    def obter_registros(self, limite: int = 30) -> list[dict[str, Any]]:
        """Retorna os registros de acesso mais recentes."""
        registros = self.database.acessos_recentes(limite=limite)
        return [
            {
                "id": r["id"],
                "usuario_id": r["user_id"],
                "usuario_nome": r["user_name"],
                "uid_cartao": r["card_uid"],
                "autorizado": bool(r["granted"]),
                "motivo": r["reason"],
                "data_hora": r["occurred_at"],
            }
            for r in registros
        ]

    # -------------------------------------------------------------------------
    # 4. OPERAÇÕES DE LEITURA E IDENTIFICAÇÃO DE TAG RFID
    # -------------------------------------------------------------------------

    def processar_tag(self, uid: str) -> dict[str, Any]:
        """Processa a leitura de uma tag RFID respeitando o modo atual do sistema."""
        uid_norm = normalizar_uid(uid)
        modo = self.gestor_modo.obter_modo_atual()

        if modo == MODO_CADASTRO:
            # Em modo cadastro: captura a tag sem abrir a porta
            existente = self.database.buscar_usuario_por_uid(uid_norm)
            return {
                "sucesso": True,
                "modo": MODO_CADASTRO,
                "uid": uid_norm,
                "ja_cadastrado": existente is not None,
                "usuario": {
                    "id": existente.id_usuario,
                    "nome": existente.nome,
                    "ativo": existente.ativo,
                } if existente else None,
                "mensagem": f"Tag {uid_norm} capturada no Modo Cadastro.",
            }

        # Em modo produção: valida credencial e autoriza abertura se válido
        decisao = self.database.verificar_acesso(uid_norm)
        if decisao.autorizado:
            self.abrir_porta(origem=f"TAG_{uid_norm}", acionar_hardware=True)

        return {
            "sucesso": True,
            "modo": MODO_PRODUCAO,
            "autorizado": decisao.autorizado,
            "motivo": decisao.motivo,
            "uid": decisao.uid_cartao,
            "usuario": {
                "id": decisao.usuario.id_usuario,
                "nome": decisao.usuario.nome,
            } if decisao.usuario else None,
        }

    def capturar_tag_leitor_hardware(self, timeout: float = 30.0) -> str:
        """Realiza a leitura direta de uma tag no leitor PN532 físico.

        Requer que o sistema esteja em MODO_CADASTRO para não colidir com o serviço
        da porta, e que esteja em ambiente Linux com o binário nativo.
        """
        self.gestor_modo.validar_permissao_leitor("capturar_tag")

        leitor = setup_leitor(executavel=self.executavel_leitor)
        try:
            uid = leitor.ler(timeout)
        finally:
            leitor.encerrar()

        if not uid:
            raise TimeoutError("Tempo limite esgotado: nenhum cartão foi aproximado do leitor.")

        return uid

    # -------------------------------------------------------------------------
    # 5. AUTENTICAÇÃO E SEGURANÇA WEB
    # -------------------------------------------------------------------------

    def autenticar_admin(self, senha: str, duracao_sessao: float = 86400.0) -> dict[str, Any]:
        """Valida a senha fixa de administrador definida em código e gera token de sessão."""
        senha_limpa = (senha or "").strip()
        if not hmac.compare_digest(senha_limpa, self.senha_mestre):
            raise PermissionError("Senha de administrador incorreta.")

        token = secrets.token_hex(32)
        expiracao = time.time() + duracao_sessao

        with self._lock_auth:
            self._sessoes_ativas[token] = expiracao

        return {
            "sucesso": True,
            "token": token,
            "mensagem": "Autenticado com sucesso no sistema.",
            "expira_em": expiracao,
        }

    def validar_token(self, token: str | None) -> bool:
        """Verifica se o token de sessão fornecido é válido e não expirou."""
        if not token or not isinstance(token, str):
            return False

        token_limpo = token.strip()
        agora = time.time()

        with self._lock_auth:
            expiracao = self._sessoes_ativas.get(token_limpo)
            if expiracao is None:
                return False
            if agora > expiracao:
                del self._sessoes_ativas[token_limpo]
                return False
            # Renova por mais 24h na atividade contínua
            self._sessoes_ativas[token_limpo] = agora + 86400.0
            return True

    def encerrar_sessao(self, token: str | None) -> bool:
        """Invalida a sessão ativa (logout)."""
        if not token or not isinstance(token, str):
            return False

        with self._lock_auth:
            return self._sessoes_ativas.pop(token.strip(), None) is not None
