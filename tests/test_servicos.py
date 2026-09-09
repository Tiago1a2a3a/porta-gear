"""Testes unitários da camada de serviços da aplicação (ServicosPorta)."""

from pathlib import Path
import tempfile
import time
import unittest

from src.modulo_central.gestor_modo import (
    GestorModo,
    MODO_CADASTRO,
    MODO_PRODUCAO,
)
from src.modulo_central.servicos_porta import ServicosPorta
from src.modulo_database.database import ErroDatabase, normalizar_uid
from src.modulo_database.setup_database import setup_database


class TestesServicosPorta(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.caminho_db = self.temp_path / "teste_servicos.sqlite3"
        self.caminho_pid = self.temp_path / "teste.pid"
        self.caminho_estado = self.temp_path / "teste.state"

        self.gestor = GestorModo(
            caminho_pid=self.caminho_pid,
            caminho_estado=self.caminho_estado,
        )
        self.database = setup_database(self.caminho_db)
        self.servicos = ServicosPorta(
            database=self.database,
            gestor_modo=self.gestor,
        )

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_obter_status_inicial(self):
        status = self.servicos.obter_status()
        self.assertTrue(status["sucesso"])
        self.assertEqual(status["modo"], MODO_PRODUCAO)
        self.assertFalse(status["servico"]["ativo"])
        self.assertEqual(status["estatisticas"]["total_usuarios"], 0)
        self.assertFalse(status["porta"]["aberta"])

    def test_alternar_modo(self):
        resp_cad = self.servicos.alternar_modo("CADASTRO")
        self.assertTrue(resp_cad["sucesso"])
        self.assertEqual(resp_cad["modo"], MODO_CADASTRO)
        self.assertEqual(self.servicos.obter_status()["modo"], MODO_CADASTRO)

        resp_prod = self.servicos.alternar_modo("PRODUCAO")
        self.assertTrue(resp_prod["sucesso"])
        self.assertEqual(resp_prod["modo"], MODO_PRODUCAO)
        self.assertEqual(self.servicos.obter_status()["modo"], MODO_PRODUCAO)

        with self.assertRaises(ValueError):
            self.servicos.alternar_modo("MODO_INEXISTENTE")

    def test_cadastrar_usuario_sucesso(self):
        resp = self.servicos.cadastrar_usuario(
            nome="Carlos Silva",
            uid_cartao="04A1B2C3",
            id_usuario="001",
        )
        self.assertTrue(resp["sucesso"])
        self.assertEqual(resp["usuario"]["id"], "001")
        self.assertEqual(resp["usuario"]["nome"], "Carlos Silva")
        self.assertEqual(resp["usuario"]["uid_cartao"], "04A1B2C3")

        # Verifica persistência no banco
        usuario = self.database.buscar_usuario_por_id("001")
        self.assertIsNotNone(usuario)
        self.assertEqual(usuario.nome, "Carlos Silva")

    def test_cadastrar_usuario_validacoes(self):
        with self.assertRaises(ValueError):
            self.servicos.cadastrar_usuario(nome="", uid_cartao="11223344")

        with self.assertRaises(ValueError):
            self.servicos.cadastrar_usuario(nome="Carlos", uid_cartao="")

        # Cadastra primeiro usuário
        self.servicos.cadastrar_usuario(nome="Carlos", uid_cartao="11223344", id_usuario="001")

        # Tentar cadastrar outro com mesma tag deve falhar
        with self.assertRaises(ErroDatabase):
            self.servicos.cadastrar_usuario(nome="Ana", uid_cartao="11223344", id_usuario="002")

    def test_trocar_cartao(self):
        self.servicos.cadastrar_usuario(nome="Julia", uid_cartao="A1B2C3D4", id_usuario="005")

        resp = self.servicos.trocar_cartao("005", "D4C3B2A1")
        self.assertTrue(resp["sucesso"])
        self.assertEqual(resp["usuario"]["uid_cartao"], "D4C3B2A1")

        # Se tentar trocar para o mesmo cartão, deve avisar com sucesso
        resp_mesmo = self.servicos.trocar_cartao("005", "D4C3B2A1")
        self.assertTrue(resp_mesmo["sucesso"])

        # Usuário inexistente
        with self.assertRaises(ErroDatabase):
            self.servicos.trocar_cartao("999", "AABBCCDD")

    def test_alterar_nome(self):
        self.servicos.cadastrar_usuario(nome="Roberto", uid_cartao="55667788", id_usuario="010")

        resp = self.servicos.alterar_nome("010", "Roberto Santos")
        self.assertTrue(resp["sucesso"])
        self.assertEqual(resp["usuario"]["nome"], "Roberto Santos")

        with self.assertRaises(ValueError):
            self.servicos.alterar_nome("010", "   ")

        with self.assertRaises(ErroDatabase):
            self.servicos.alterar_nome("999", "Nome Qualquer")

    def test_definir_status_e_remover(self):
        self.servicos.cadastrar_usuario(nome="Lucas", uid_cartao="12345678", id_usuario="020")

        # Bloquear usuário
        resp_bloq = self.servicos.definir_status_usuario("020", False)
        self.assertTrue(resp_bloq["sucesso"])
        self.assertFalse(resp_bloq["ativo"])
        self.assertFalse(self.database.buscar_usuario_por_id("020").ativo)

        # Liberar usuário
        resp_lib = self.servicos.definir_status_usuario("020", True)
        self.assertTrue(resp_lib["sucesso"])
        self.assertTrue(resp_lib["ativo"])

        # Remover usuário
        resp_rem = self.servicos.remover_usuario("020")
        self.assertTrue(resp_rem["sucesso"])

    def test_abrir_porta_e_registros(self):
        resp = self.servicos.abrir_porta(origem="TESTE_UNITARIO", duracao=0.5)
        self.assertTrue(resp["sucesso"])

        registros = self.servicos.obter_registros(limite=5)
        self.assertGreater(len(registros), 0)
        self.assertEqual(registros[0]["uid_cartao"], "TESTE_UNITARIO")
        self.assertTrue(registros[0]["autorizado"])

    def test_processar_tag_modos(self):
        self.servicos.cadastrar_usuario(nome="Mariana", uid_cartao="CAFE1234", id_usuario="030")

        # Modo PRODUÇÃO: Deve conceder acesso
        self.servicos.alternar_modo("PRODUCAO")
        resp_prod = self.servicos.processar_tag("CAFE1234")
        self.assertTrue(resp_prod["autorizado"])
        self.assertEqual(resp_prod["usuario"]["nome"], "Mariana")

        # Modo CADASTRO: Deve apenas inspecionar a tag sem acionar abertura
        self.servicos.alternar_modo("CADASTRO")
        resp_cad = self.servicos.processar_tag("CAFE1234")
        self.assertEqual(resp_cad["modo"], MODO_CADASTRO)
        self.assertTrue(resp_cad["ja_cadastrado"])
        self.assertEqual(resp_cad["usuario"]["id"], "030")

    def test_autenticacao_tokens_e_sessoes(self):
        # Autenticação com senha correta
        resp_auth = self.servicos.autenticar_admin("123456789")
        self.assertTrue(resp_auth["sucesso"])
        token = resp_auth["token"]
        self.assertIsInstance(token, str)
        self.assertTrue(len(token) >= 32)

        # Validação do token emitido
        self.assertTrue(self.servicos.validar_token(token))
        self.assertFalse(self.servicos.validar_token("token_falso_bypass"))
        self.assertFalse(self.servicos.validar_token(None))
        self.assertFalse(self.servicos.validar_token(""))

        # Senha incorreta
        with self.assertRaises(PermissionError):
            self.servicos.autenticar_admin("senha_errada")

        # Logout / Encerramento de sessão
        self.assertTrue(self.servicos.encerrar_sessao(token))
        self.assertFalse(self.servicos.validar_token(token))


if __name__ == "__main__":
    unittest.main()
