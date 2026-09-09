import sys
sys.path.insert(0, "/root/Projeto_tiago")

from src.modulo_rele.setup_rele import setup_rele
from src.modulo_leitor.setup_leitor import setup_leitor

print("1. Testando setup_rele...")
rele = setup_rele()
print("Rele configurado OK.")

print("2. Testando setup_leitor...")
try:
    leitor = setup_leitor()
    print("Leitor pronto:", leitor.nome_dispositivo)
    leitor.encerrar()
except Exception as e:
    import traceback
    traceback.print_exc()
