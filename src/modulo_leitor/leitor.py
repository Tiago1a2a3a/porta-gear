"""Comunicação com o processo persistente que mantém o PN532 aberto."""

from __future__ import annotations

from pathlib import Path
from queue import Empty, Queue
import subprocess
from threading import Thread
import time

from src.modulo_database.database import ErroDatabase, normalizar_uid


class ErroLeitor(Exception):
    """Erro de instalação, comunicação ou resposta do leitor."""


_FIM_DA_SAIDA = object()


class LeitorPN532:
    """Representa uma única conexão persistente com o PN532."""

    def __init__(self, processo: subprocess.Popen[str], executavel: Path):
        self._processo = processo
        self.executavel = executavel
        self.nome_dispositivo: str | None = None
        self._linhas: Queue[str | object] = Queue()
        self._thread_saida = Thread(
            target=self._receber_saida,
            name="saida-leitor-pn532",
            daemon=True,
        )
        self._thread_saida.start()

    def aguardar_pronto(self, timeout_segundos: float = 10.0) -> None:
        """Espera a confirmação de que libnfc e PN532 foram inicializados."""
        linha = self._ler_linha(timeout_segundos)
        if linha is None:
            self.encerrar()
            raise ErroLeitor(
                "O leitor não confirmou a inicialização dentro do tempo esperado."
            )
        if not linha.startswith("READY "):
            detalhe = self._detalhe_erro(linha)
            self.encerrar()
            raise ErroLeitor(f"Resposta inesperada durante o setup: {detalhe}")

        self.nome_dispositivo = linha.removeprefix("READY ").strip()

    def ler(self, timeout_segundos: float | None = None) -> str | None:
        """Aguarda o próximo cartão sem reinicializar o PN532.

        Sem timeout, a chamada fica bloqueada até um cartão ser aproximado. Com
        timeout, retorna ``None`` quando nenhum UID chegar no período informado.
        """
        prazo = (
            None
            if timeout_segundos is None
            else time.monotonic() + timeout_segundos
        )

        while True:
            restante = None if prazo is None else max(0.0, prazo - time.monotonic())
            linha = self._ler_linha(restante)

            if linha is None:
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
            self._processo.wait(timeout=3.0)
        except subprocess.TimeoutExpired:
            self._processo.kill()
            self._processo.wait(timeout=1.0)
        self._thread_saida.join(timeout=1.0)

    def _ler_linha(self, timeout_segundos: float | None) -> str | None:
        if timeout_segundos is not None and timeout_segundos < 0:
            raise ValueError("O timeout de leitura não pode ser negativo.")

        try:
            item = self._linhas.get(timeout=timeout_segundos)
        except Empty:
            return None

        if item is not _FIM_DA_SAIDA:
            return str(item)

        codigo = self._processo.poll()
        detalhe = self._detalhe_erro("")
        raise ErroLeitor(
            f"O leitor persistente foi encerrado"
            f"{f' com código {codigo}' if codigo is not None else ''}. {detalhe}"
        )

    def _receber_saida(self) -> None:
        stdout = self._processo.stdout
        if stdout is None:
            self._linhas.put(_FIM_DA_SAIDA)
            return

        for linha in stdout:
            linha = linha.strip()
            if linha:
                self._linhas.put(linha)
        self._linhas.put(_FIM_DA_SAIDA)

    def _detalhe_erro(self, alternativa: str) -> str:
        stderr = self._processo.stderr
        if stderr is not None and self._processo.poll() is not None:
            detalhe = stderr.read().strip()
            if detalhe:
                return detalhe
        return alternativa or "Nenhum detalhe foi informado."
