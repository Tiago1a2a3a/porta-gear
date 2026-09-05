from io import StringIO
from pathlib import Path
import unittest

from src.modulo_leitor.leitor import LeitorPN532


class ProcessoTeste:
    def __init__(self, saida: str):
        self.stdout = StringIO(saida)
        self.stderr = StringIO("")
        self.codigo = None
        self.terminado = False

    def poll(self):
        return self.codigo

    def terminate(self):
        self.terminado = True
        self.codigo = 0

    def wait(self, timeout=None):
        return self.codigo

    def kill(self):
        self.codigo = -9


class TestesLeitor(unittest.TestCase):
    def test_ler_recebe_uid_do_processo_persistente(self):
        processo = ProcessoTeste("UID 04A1B2C3\n")
        leitor = LeitorPN532(processo, Path("leitor_pn532"))

        self.assertEqual(leitor.ler(), "04A1B2C3")

    def test_ler_ignora_ready_e_aguarda_uid(self):
        processo = ProcessoTeste("READY PN532 SPI\nUID 11 22 33 44\n")
        leitor = LeitorPN532(processo, Path("leitor_pn532"))

        self.assertEqual(leitor.ler(), "11223344")

    def test_encerrar_finaliza_o_mesmo_processo(self):
        processo = ProcessoTeste("")
        leitor = LeitorPN532(processo, Path("leitor_pn532"))

        leitor.encerrar()

        self.assertTrue(processo.terminado)


if __name__ == "__main__":
    unittest.main()

