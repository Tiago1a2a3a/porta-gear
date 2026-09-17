"""Módulo para controle do LED de status via sysfs em background."""

from __future__ import annotations

import os
import threading
import time
from pathlib import Path


class LedStatus:
    """Controla um LED conectado a um pino GPIO no Linux usando sysfs."""

    def __init__(self, numero_gpio: int = 59, raiz_sysfs: Path = Path("/sys/class/gpio")):
        self.numero_gpio = numero_gpio
        self.raiz_sysfs = raiz_sysfs
        self.caminho_gpio = self.raiz_sysfs / f"gpio{numero_gpio}"
        self._inicializado = False
        self._inicializar_hardware()

    def _inicializar_hardware(self) -> None:
        """Exporta e configura o GPIO como saída."""
        if not self.raiz_sysfs.exists():
            print(f"[Aviso] {self.raiz_sysfs} não encontrado. LED ignorado (modo dev/mock).")
            return

        try:
            if not self.caminho_gpio.exists():
                (self.raiz_sysfs / "export").write_text(str(self.numero_gpio))
                time.sleep(0.1)  # Aguarda o udev/kernel criar o diretório

            (self.caminho_gpio / "direction").write_text("out")
            (self.caminho_gpio / "value").write_text("0")
            self._inicializado = True
        except Exception as e:
            print(f"[Erro] Falha ao inicializar LED GPIO{self.numero_gpio}: {e}")

    def _escrever_valor(self, valor: str) -> None:
        if not self._inicializado:
            return
        try:
            (self.caminho_gpio / "value").write_text(valor)
        except Exception as e:
            print(f"Erro LED: {e}") durante o uso normal

    def piscar_sucesso(self) -> None:
        """Pisca o LED verde por 1.075s em background."""
        def _rotina():
            self._escrever_valor("1")
            time.sleep(1.075)
            self._escrever_valor("0")
            
        thread = threading.Thread(target=_rotina, daemon=True)
        thread.start()

# Instância global para uso em todo o backend
led_sistema = LedStatus(numero_gpio=59)
