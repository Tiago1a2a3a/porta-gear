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

    def test_gestor_modo_alternancia_e_bloqueio(self):
        import os
        from pathlib import Path
        import signal
        import tempfile
        from src.modulo_central.gestor_modo import (
            ErroModoBloqueado,
            GestorModo,
            MODO_CADASTRO,
            MODO_PRODUCAO,
        )

        sinais_recebidos = []
        antigo_usr1 = None
        antigo_usr2 = None
        if hasattr(signal, "SIGUSR1"):
            antigo_usr1 = signal.signal(signal.SIGUSR1, lambda s, f: sinais_recebidos.append(s))
        if hasattr(signal, "SIGUSR2"):
            antigo_usr2 = signal.signal(signal.SIGUSR2, lambda s, f: sinais_recebidos.append(s))

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                caminho_pid = Path(tmpdir) / "teste.pid"
                caminho_estado = Path(tmpdir) / "teste.state"
                gestor = GestorModo(caminho_pid=caminho_pid, caminho_estado=caminho_estado)

                # Modo inicial padrão
                self.assertEqual(gestor.obter_modo_atual(), MODO_PRODUCAO)
                self.assertIsNone(gestor.obter_pid_servico())

                # Sem serviço ativo, não deve bloquear
                gestor.validar_permissao_leitor("novo-usuario")

                # Simula serviço ativo gravando PID atual
                gestor.gravar_pid_servico(os.getpid())
                self.assertEqual(gestor.obter_pid_servico(), os.getpid())

                # Em PRODUCAO com serviço ativo -> deve bloquear comando com leitor
                with self.assertRaises(ErroModoBloqueado):
                    gestor.validar_permissao_leitor("novo-usuario")

                # Alterna para CADASTRO
                gestor.alternar_para_modo_cadastro()
                self.assertEqual(gestor.obter_modo_atual(), MODO_CADASTRO)
                if hasattr(signal, "SIGUSR1"):
                    self.assertIn(signal.SIGUSR1, sinais_recebidos)

                # Em CADASTRO -> comando com leitor deve ser liberado mesmo com serviço ativo
                gestor.validar_permissao_leitor("novo-usuario")

                # Retorna para PRODUCAO
                gestor.alternar_para_modo_producao()
                self.assertEqual(gestor.obter_modo_atual(), MODO_PRODUCAO)
                if hasattr(signal, "SIGUSR2"):
                    self.assertIn(signal.SIGUSR2, sinais_recebidos)

                # Limpa PID
                gestor.limpar_pid()
                self.assertIsNone(gestor.obter_pid_servico())
        finally:
            if hasattr(signal, "SIGUSR1") and antigo_usr1 is not None:
                signal.signal(signal.SIGUSR1, antigo_usr1)
            if hasattr(signal, "SIGUSR2") and antigo_usr2 is not None:
                signal.signal(signal.SIGUSR2, antigo_usr2)

    def test_comandos_modo_terminal(self):
        from src.modulo_central.main import main

        # Testar execução dos comandos status, modo-cadastro e modo-producao
        self.assertEqual(main(["status"]), 0)
        self.assertEqual(main(["modo-cadastro"]), 0)
        self.assertEqual(main(["modo-producao"]), 0)


if __name__ == "__main__":
    unittest.main()
