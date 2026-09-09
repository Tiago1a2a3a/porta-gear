"""Gestão dos modos de operação (Produção vs Cadastro) e controle de concorrência do leitor."""

from __future__ import annotations

import os
from pathlib import Path
import signal
import sys
import tempfile
import time

MODO_PRODUCAO = "PRODUCAO"
MODO_CADASTRO = "CADASTRO"


class ErroModoBloqueado(Exception):
    """Comando bloqueado devido ao modo de operação atual."""


def _diretorio_temporario() -> Path:
    padrao_linux = Path("/tmp")
    if padrao_linux.is_dir():
        return padrao_linux
    return Path(tempfile.gettempdir())


CAMINHO_PID_PADRAO = _diretorio_temporario() / "porta_gear.pid"
CAMINHO_ESTADO_PADRAO = _diretorio_temporario() / "porta_gear.state"


class InterrupcaoModo(Exception):
    """Sinal para notificar a mudança de modo no loop bloqueante."""

    def __init__(self, novo_modo: str):
        super().__init__(f"Mudança para modo: {novo_modo}")
        self.novo_modo = novo_modo


def processo_ativo(pid: int) -> bool:
    """Verifica se um processo com o PID fornecido ainda está em execução."""
    if pid <= 0:
        return False
    try:
        if sys.platform == "win32":
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            handle = kernel32.OpenProcess(0x1000, False, pid)
            if handle:
                kernel32.CloseHandle(handle)
                return True
            return False
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError, PermissionError):
        return False


class GestorModo:
    """Controla o estado de execução (Produção/Cadastro) e comunicação com o serviço."""

    def __init__(
        self,
        caminho_pid: Path = CAMINHO_PID_PADRAO,
        caminho_estado: Path = CAMINHO_ESTADO_PADRAO,
    ) -> None:
        self.caminho_pid = caminho_pid
        self.caminho_estado = caminho_estado

    def obter_pid_servico(self) -> int | None:
        """Retorna o PID do serviço principal se estiver ativo."""
        if not self.caminho_pid.is_file():
            return None
        try:
            conteudo = self.caminho_pid.read_text(encoding="utf-8").strip()
            if not conteudo:
                return None
            pid = int(conteudo)
            if processo_ativo(pid):
                return pid
            # Arquivo stale (processo morreu)
            self.limpar_pid()
            return None
        except (ValueError, OSError):
            return None

    def gravar_pid_servico(self, pid: int | None = None) -> None:
        """Registra o PID do serviço principal."""
        pid_atual = pid if pid is not None else os.getpid()
        self.caminho_pid.parent.mkdir(parents=True, exist_ok=True)
        self.caminho_pid.write_text(str(pid_atual), encoding="utf-8")

    def limpar_pid(self) -> None:
        """Remove o arquivo de PID se existir."""
        try:
            if self.caminho_pid.is_file():
                self.caminho_pid.unlink()
        except OSError:
            pass

    def obter_modo_atual(self) -> str:
        """Consulta o modo atual do sistema (padrão: PRODUCAO)."""
        if not self.caminho_estado.is_file():
            return MODO_PRODUCAO
        try:
            conteudo = self.caminho_estado.read_text(encoding="utf-8").strip().upper()
            if conteudo == MODO_CADASTRO:
                return MODO_CADASTRO
            return MODO_PRODUCAO
        except OSError:
            return MODO_PRODUCAO

    def gravar_modo(self, modo: str) -> None:
        """Grava o modo de operação no arquivo de estado."""
        self.caminho_estado.parent.mkdir(parents=True, exist_ok=True)
        self.caminho_estado.write_text(modo.upper(), encoding="utf-8")

    def alternar_para_modo_cadastro(self) -> bool:
        """Alterna para o modo de cadastro e notifica o serviço ativo para liberar o leitor."""
        self.gravar_modo(MODO_CADASTRO)
        pid = self.obter_pid_servico()
        if pid is not None:
            self._enviar_sinal(pid, "CADASTRO")
            for _ in range(10):
                time.sleep(0.1)
                if self.obter_modo_atual() == MODO_CADASTRO:
                    break
        return True

    def alternar_para_modo_producao(self) -> bool:
        """Alterna para o modo de produção e notifica o serviço para reabrir o leitor."""
        self.gravar_modo(MODO_PRODUCAO)
        pid = self.obter_pid_servico()
        if pid is not None:
            self._enviar_sinal(pid, "PRODUCAO")
        return True

    def validar_permissao_leitor(self, comando: str) -> None:
        """Garante que comandos com leitor não rodem concorrentemente no modo produção."""
        pid = self.obter_pid_servico()
        modo = self.obter_modo_atual()

        if pid is not None and modo == MODO_PRODUCAO:
            raise ErroModoBloqueado(
                f"O comando '{comando}' requer acesso exclusivo ao leitor PN532, "
                f"mas o sistema está em MODO DE PRODUÇÃO com o serviço ativo (PID {pid}).\n"
                f"Para liberar o leitor, execute primeiro:\n"
                f"  python3 main.py modo-cadastro\n"
                f"Após concluir o cadastro, retorne para o modo normal com:\n"
                f"  python3 main.py modo-producao"
            )

    def _enviar_sinal(self, pid: int, destino: str) -> None:
        if sys.platform != "win32":
            if destino == "CADASTRO" and hasattr(signal, "SIGUSR1"):
                try:
                    os.kill(pid, signal.SIGUSR1)
                except OSError:
                    pass
            elif destino == "PRODUCAO" and hasattr(signal, "SIGUSR2"):
                try:
                    os.kill(pid, signal.SIGUSR2)
                except OSError:
                    pass
