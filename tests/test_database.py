from pathlib import Path
import tempfile
import unittest

from src.modulo_database.database import BancoAcesso, ErroDatabase
from src.modulo_database.setup_database import setup_database


class TestesDatabase(unittest.TestCase):
    def setUp(self):
        self.pasta = tempfile.TemporaryDirectory()
        self.caminho = Path(self.pasta.name) / "teste.sqlite3"
        self.banco = setup_database(self.caminho)

    def tearDown(self):
        self.pasta.cleanup()

    def test_autoriza_somente_usuario_ativo(self):
        self.banco.adicionar_usuario("001", "Ana", "04:A1:B2:C3")

        autorizado = self.banco.verificar_acesso("04A1B2C3")
        self.assertTrue(autorizado.autorizado)
        self.assertEqual(autorizado.usuario.nome, "Ana")

        self.banco.definir_usuario_ativo("001", False)
        negado = self.banco.verificar_acesso("04A1B2C3")
        self.assertFalse(negado.autorizado)
        self.assertEqual(negado.motivo, "usuario_inativo")

    def test_impede_uid_duplicado(self):
        self.banco.adicionar_usuario("001", "Ana", "04A1B2C3")
        with self.assertRaises(ErroDatabase):
            self.banco.adicionar_usuario("002", "Bruno", "04-A1-B2-C3")

    def test_altera_cadastro(self):
        self.banco.adicionar_usuario("001", "Ana", "04A1B2C3")
        alterado = self.banco.alterar_usuario(
            "001",
            nome="Ana Silva",
            uid_cartao="11223344",
            ativo=False,
        )

        self.assertEqual(alterado.nome, "Ana Silva")
        self.assertEqual(alterado.uid_cartao, "11223344")
        self.assertFalse(alterado.ativo)

    def test_registra_acessos_permitidos_e_negados(self):
        self.banco.adicionar_usuario("001", "Ana", "04A1B2C3")
        self.banco.verificar_acesso("04A1B2C3")
        self.banco.verificar_acesso("AABBCCDD")

        registros = self.banco.acessos_recentes(2)
        self.assertEqual(len(registros), 2)
        self.assertEqual(registros[0]["reason"], "cartao_nao_cadastrado")
        self.assertEqual(registros[1]["reason"], "acesso_autorizado")


if __name__ == "__main__":
    unittest.main()

