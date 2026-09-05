import unittest

from src.modulo_central.loop_sistema import processar_uid
from src.modulo_database.database import DecisaoAcesso, Usuario


class DatabaseTeste:
    def __init__(self, decisao):
        self.decisao = decisao

    def verificar_acesso(self, uid):
        return self.decisao


class ReleTeste:
    def __init__(self):
        self.aberturas = 0

    def abrir_porta(self):
        self.aberturas += 1


class SistemaTeste:
    def __init__(self, decisao):
        self.database = DatabaseTeste(decisao)
        self.rele = ReleTeste()


class TestesCentral(unittest.TestCase):
    def test_cartao_autorizado_abre_porta(self):
        usuario = Usuario("001", "Ana", "04A1B2C3", True)
        decisao = DecisaoAcesso("04A1B2C3", True, "acesso_autorizado", usuario)
        sistema = SistemaTeste(decisao)

        processar_uid(sistema, "04A1B2C3")

        self.assertEqual(sistema.rele.aberturas, 1)

    def test_cartao_negado_nao_abre_porta(self):
        decisao = DecisaoAcesso("AABBCCDD", False, "cartao_nao_cadastrado", None)
        sistema = SistemaTeste(decisao)

        processar_uid(sistema, "AABBCCDD")

        self.assertEqual(sistema.rele.aberturas, 0)


if __name__ == "__main__":
    unittest.main()
