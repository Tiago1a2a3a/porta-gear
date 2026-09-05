from pathlib import Path
import tempfile
import unittest

from src.modulo_rele.rele import ConfiguracaoRele, ReleLuckfox
from src.modulo_rele.setup_rele import setup_rele


class TestesRele(unittest.TestCase):
    def test_setup_configura_gpio52_em_estado_seguro(self):
        with tempfile.TemporaryDirectory() as pasta:
            raiz = Path(pasta)
            gpio = raiz / "gpio52"
            gpio.mkdir()
            (gpio / "direction").write_text("")
            (gpio / "value").write_text("")

            setup_rele(numero_gpio=52, raiz_sysfs=raiz)

            self.assertEqual((gpio / "direction").read_text(), "out")
            self.assertEqual((gpio / "value").read_text(), "1")

    def test_abrir_porta_preserva_sequencia_ativa_baixa(self):
        esperas = []
        configuracao = ConfiguracaoRele(
            quantidade_pulsos=2,
            tempo_ligado=1.0,
            tempo_desligado=0.5,
        )
        rele = ReleLuckfox(configuracao=configuracao, esperar=esperas.append)
        rele._configurado = True
        niveis = []
        rele._escrever = niveis.append

        rele.abrir_porta()

        self.assertEqual(niveis, [1, 0, 1, 0, 1])
        self.assertEqual(esperas, [1.0, 0.5, 1.0, 0.5])


if __name__ == "__main__":
    unittest.main()

