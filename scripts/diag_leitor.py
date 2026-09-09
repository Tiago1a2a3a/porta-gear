import subprocess
import time

print("Iniciando leitor_pn532...")
p = subprocess.Popen(
    ["/root/Projeto_tiago/src/modulo_leitor/nativo/leitor_pn532"],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
)
print("PID:", p.pid)
time.sleep(1)
print("Poll:", p.poll())
linha = p.stdout.readline()
print("Linha lida:", repr(linha))
if p.poll() is not None:
    print("Stderr:", p.stderr.read())
p.terminate()
print("Fim do teste.")
