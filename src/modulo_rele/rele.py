"""Operações do relé conectado ao GPIO do Luckfox usando libgpiod."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading
import time
from typing import Callable


NIVEL_ATIVO = 0
NIVEL_INATIVO = 1


class ErroRele(Exception):
    """Erro de configuração ou acionamento do relé."""


@dataclass(frozen=True)
class ConfiguracaoRele:
    quantidade_pulsos: int = 1
    tempo_ligado: float = 1.0
    tempo_desligado: float = 0.0

    def validar(self) -> None:
        if self.quantidade_pulsos < 1:
            raise ErroRele("A quantidade de pulsos deve ser maior que zero.")
        if self.tempo_ligado < 0 or self.tempo_desligado < 0:
            raise ErroRele("Os tempos do relé não podem ser negativos.")


class ReleLuckfox:
    """Controla o relé ativo em nível baixo usando libgpiod (quando disponível) ou sysfs.
    
    Permite acionamento assíncrono via Thread para não bloquear o loop principal
    quando em operação real (esperar == time.sleep).
    """

    def __init__(
        self,
        numero_gpio: int = 52,
        chip_gpio: str | None = None,
        linha_offset: int | None = None,
        raiz_sysfs: Path = Path("/sys/class/gpio"),
        configuracao: ConfiguracaoRele = ConfiguracaoRele(),
        esperar: Callable[[float], None] = time.sleep,
        modo_assincrono: bool = True,
    ):
        self.numero_gpio = numero_gpio
        self.chip_gpio = chip_gpio if chip_gpio is not None else f"gpiochip{numero_gpio // 32}"
        self.linha_offset = linha_offset if linha_offset is not None else (numero_gpio % 32)
        self.raiz_sysfs = raiz_sysfs
        self.caminho_gpio = raiz_sysfs / f"gpio{numero_gpio}"
        self.configuracao = configuracao
        self._esperar = esperar
        self.modo_assincrono = modo_assincrono
        self._configurado = False
        self._linha = None
        self._usando_sysfs = False
        self._thread_rele: threading.Thread | None = None
        self._lock = threading.Lock()

    def configurar(self) -> None:
        """Configura a linha GPIO via libgpiod ou sysfs e deixa o relé desligado."""
        self.configuracao.validar()

        # Prioriza sysfs se a raiz_sysfs foi personalizada (ex: em testes) ou se gpiod não existir
        usar_sysfs = self.raiz_sysfs != Path("/sys/class/gpio")
        if not usar_sysfs:
            try:
                import gpiod
                chip = gpiod.Chip(self.chip_gpio)
                self._linha = chip.get_line(self.linha_offset)
                self._linha.request(
                    consumer="porta_gear",
                    type=gpiod.LINE_REQ_DIR_OUT,
                    default_vals=[NIVEL_INATIVO]
                )
                self._configurado = True
                self._usando_sysfs = False
                return
            except (ImportError, Exception):
                usar_sysfs = True

        if usar_sysfs:
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
                self._usando_sysfs = True
                self._escrever(NIVEL_INATIVO)
            except OSError as erro:
                raise ErroRele(
                    f"Não foi possível configurar GPIO{self.numero_gpio}: {erro}"
                ) from erro

            self._configurado = True

    def abrir_porta(self) -> None:
        """Executa os pulsos para abrir a porta (assíncrono em operação real)."""
        if not self._configurado and self._linha is None:
            raise ErroRele("O relé precisa passar por setup_rele() antes do uso.")

        # Em testes (esperar customizado) ou modo síncrono, executa diretamente
        if not self.modo_assincrono or self._esperar is not time.sleep:
            self._executar_pulsos()
            return

        with self._lock:
            if self._thread_rele is not None and not self._thread_rele.is_alive():
                self._thread_rele = None

            if self._thread_rele is None:
                self._thread_rele = threading.Thread(
                    target=self._executar_pulsos,
                    name="rele-pulsos",
                    daemon=True,
                )
                self._thread_rele.start()

    def _executar_pulsos(self) -> None:
        try:
            self._escrever(NIVEL_INATIVO)
            for _ in range(self.configuracao.quantidade_pulsos):
                self._escrever(NIVEL_ATIVO)
                self._esperar(self.configuracao.tempo_ligado)
                self._escrever(NIVEL_INATIVO)
                self._esperar(self.configuracao.tempo_desligado)
        except Exception as e:
            print(f"[Erro na Thread do Relé]: {e}")

    def desligar(self) -> None:
        """Retorna imediatamente o relé ao nível seguro e libera recursos."""
        self._escrever(NIVEL_INATIVO)
        if self._linha is not None:
            try:
                self._linha.release()
            except Exception:
                pass
            self._linha = None

    def _escrever(self, nivel: int) -> None:
        if nivel not in {NIVEL_ATIVO, NIVEL_INATIVO}:
            raise ErroRele(f"Nível inválido para o relé: {nivel}")
        try:
            if self._linha is not None:
                self._linha.set_value(nivel)
            else:
                (self.caminho_gpio / "value").write_text(str(nivel))
        except Exception as erro:
            raise ErroRele(f"Não foi possível escrever no relé: {erro}") from erro


