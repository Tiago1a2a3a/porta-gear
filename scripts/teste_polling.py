import subprocess
import time

print("Iniciando leitor_pn532 para teste de polling...")
p = subprocess.Popen(
    ["/root/Projeto_tiago/src/modulo_leitor/nativo/leitor_pn532"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
print("PID:", p.pid)
pronto = p.stdout.readline()
print("Header:", repr(pronto))

# Aguarda 3 segundos observando o processo
for i in range(10):
    poll = p.poll()
    print(f"[{i*0.5:.1f}s] Poll: {poll}")
    if poll is not None:
        print("Processo encerrou prematuramente!")
        print("Stderr:", p.stderr.read())
        break
    time.sleep(0.5)

if p.poll() is None:
    print("Processo ainda está vivo e rodando o polling normalmente!")
    p.terminate()
