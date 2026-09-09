"""Comunicação com o processo persistente que mantém o PN532 aberto de forma bloqueante."""

from __future__ import annotations

from pathlib import Path
import select
import subprocess
import sys
import time

from src.modulo_database.database import ErroDatabase, normalizar_uid


class ErroLeitor(Exception):
    """Erro de instalação, comunicação ou resposta do leitor."""


class LeitorPN532:
    """Representa uma única conexão persistente e bloqueante com o PN532."""

    def __init__(self, processo: subprocess.Popen[str], executavel: Path):
        self._processo = processo
        self.executavel = executavel
        self.nome_dispositivo: str | None = None

    def aguardar_pronto(self, timeout_segundos: float = 10.0) -> None:
        """Espera a confirmação de que libnfc e PN532 foram inicializados."""
        linha = self._ler_linha()
        if not linha.startswith("READY "):
            detalhe = self._detalhe_erro(linha)
            self.encerrar()
            raise ErroLeitor(f"Resposta inesperada durante o setup: {detalhe}")

        self.nome_dispositivo = linha.removeprefix("READY ").strip()

    def ler(self, timeout_segundos: float | None = None) -> str | None:
        """Aguarda o próximo cartão sem reinicializar o PN532 (chamada bloqueante)."""
        tempo_limite = time.time() + timeout_segundos if timeout_segundos is not None else None

        while True:
            if timeout_segundos is not None:
                restante = tempo_limite - time.time()
                if restante <= 0:
                    return None
                if sys.platform != "win32" and self._processo.stdout is not None:
                    prontos, _, _ = select.select([self._processo.stdout], [], [], max(0.0, restante))
                    if not prontos:
                        return None

            linha = self._ler_linha()
            if not linha:
                return None
            if linha.startswith("UID "):
                try:
                    return normalizar_uid(linha.removeprefix("UID "))
                except ErroDatabase as erro:
                    raise ErroLeitor(f"UID inválido recebido do leitor: {erro}") from erro
            if linha.startswith("READY "):
                continue

            raise ErroLeitor(f"Resposta desconhecida do leitor: {linha}")

    def encerrar(self) -> None:
        """Encerra o processo e libera a conexão nativa com a libnfc."""
        if self._processo.poll() is not None:
            return

        self._processo.terminate()
        try:
            self._processo.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            self._processo.kill()
            self._processo.wait(timeout=1.0)

    def _ler_linha(self) -> str:
        if self._processo.stdout is None:
            raise ErroLeitor("O processo do leitor não possui stdout disponível.")

        linha = self._processo.stdout.readline()
        if not linha:
            codigo = self._processo.poll()
            detalhe = self._detalhe_erro("")
            raise ErroLeitor(
                f"O leitor persistente foi encerrado"
                f"{f' com código {codigo}' if codigo is not None else ''}. {detalhe}"
            )
        return linha.strip()

    def _detalhe_erro(self, alternativa: str) -> str:
        stderr = self._processo.stderr
        if stderr is not None and self._processo.poll() is not None:
            detalhe = stderr.read().strip()
            if detalhe:
                return detalhe
        return alternativa or "Nenhum detalhe foi informado."
