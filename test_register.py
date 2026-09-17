from src.modulo_central.servicos_porta import ServicosPorta
import time

serv = ServicosPorta(caminho_database="data/portagear.db")
try:
    print(serv.cadastrar_usuario(nome="teste2", uid_cartao="AAAA4321", grupo="Turma XYZ"))
except Exception as e:
    import traceback
    traceback.print_exc()
