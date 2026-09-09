"""Operações do relé conectado ao GPIO do Luckfox via sysfs."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time
from typing import Callable


NIVEL_ATIVO = 1
NIVEL_INATIVO = 0


class ErroRele(Exception):
    """Erro de configuração ou acionamento do relé."""


@dataclass(frozen=True)
class ConfiguracaoRele:
    quantidade_pulsos: int = 3
    tempo_ligado: float = 0.8
    tempo_desligado: float = 0.4

    def validar(self) -> None:
        if self.quantidade_pulsos < 1:
            raise ErroRele("A quantidade de pulsos deve ser maior que zero.")
        if self.tempo_ligado < 0 or self.tempo_desligado < 0:
            raise ErroRele("Os tempos do relé não podem ser negativos.")


class ReleLuckfox:
    """Controla o relé de forma totalmente bloqueante e síncrona via sysfs."""

    def __init__(
        self,
        numero_gpio: int = 52,
        raiz_sysfs: Path = Path("/sys/class/gpio"),
        configuracao: ConfiguracaoRele = ConfiguracaoRele(),
        esperar: Callable[[float], None] = time.sleep,
    ):
        self.numero_gpio = numero_gpio
        self.raiz_sysfs = raiz_sysfs
        self.caminho_gpio = raiz_sysfs / f"gpio{numero_gpio}"
        self.configuracao = configuracao
        self._esperar = esperar
        self._configurado = False

    def configurar(self) -> None:
        """Exporta o GPIO e deixa o relé desligado em estado seguro (nível 0)."""
        self.configuracao.validar()

        if not self.caminho_gpio.exists():
            try:
                (self.raiz_sysfs / "export").write_text(str(self.numero_gpio))
            except OSError as erro:
                if not self.caminho_gpio.exists():
                    raise ErroRele(
                        f"Não foi possível exportar GPIO{self.numero_gpio}: {erro}"
                    ) from erro

            for _ in range(10):
                if self.caminho_gpio.exists():
                    break
                time.sleep(0.05)
            else:
                raise ErroRele(
                    f"GPIO{self.numero_gpio} não apareceu após a exportação."
                )

        try:
            (self.caminho_gpio / "direction").write_text("out")
            self._escrever(NIVEL_INATIVO)
        except OSError as erro:
            raise ErroRele(
                f"Não foi possível configurar GPIO{self.numero_gpio}: {erro}"
            ) from erro

        self._configurado = True

    def abrir_porta(self) -> None:
        """Executa os pulsos de abertura de forma totalmente bloqueante e sequencial."""
        if not self._configurado:
            raise ErroRele("O relé precisa passar por setup_rele() antes do uso.")

        self._escrever(NIVEL_INATIVO)
        for _ in range(self.configuracao.quantidade_pulsos):
            self._escrever(NIVEL_ATIVO)
            self._esperar(self.configuracao.tempo_ligado)
            self._escrever(NIVEL_INATIVO)
            if self.configuracao.tempo_desligado > 0:
                self._esperar(self.configuracao.tempo_desligado)

    def desligar(self) -> None:
        """Retorna imediatamente o relé ao nível seguro."""
        self._escrever(NIVEL_INATIVO)

    def _escrever(self, nivel: int) -> None:
        if nivel not in {NIVEL_ATIVO, NIVEL_INATIVO}:
            raise ErroRele(f"Nível inválido para o relé: {nivel}")
        try:
            (self.caminho_gpio / "value").write_text(str(nivel))
        except Exception as erro:
            raise ErroRele(f"Não foi possível escrever no relé: {erro}") from erro


