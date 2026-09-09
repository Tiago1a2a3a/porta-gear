import traceback
from src.modulo_central.setup_sistema import setup_sistema
from src.modulo_central.loop_sistema import executar_loop
from src.modulo_central.funcoes_auxiliares import ConfiguracaoSistema

print("Iniciando setup_sistema...")
try:
    sistema = setup_sistema(ConfiguracaoSistema())
    print("Setup OK! Leitor:", sistema.leitor.nome_dispositivo)
    print("Executando loop_sistema (teste por 5 segundos)...")
    # Tenta ler 1 vez com timeout de 5 segundos
    uid = sistema.leitor.ler(timeout_segundos=5.0)
    print("Leitura retornou:", uid)
except Exception:
    traceback.print_exc()
finally:
    print("Fim do teste.")
