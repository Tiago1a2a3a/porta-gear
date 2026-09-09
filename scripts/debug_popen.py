import sys
sys.path.insert(0, "/root/Projeto_tiago")

import os
from pathlib import Path
import subprocess
import time

caminho = Path("/root/Projeto_tiago/src/modulo_leitor/nativo/leitor_pn532")
print("Iniciando processo:", caminho)
proc = subprocess.Popen(
    [str(caminho)],
    stdin=subprocess.DEVNULL,
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True,
    bufsize=1,
)

print("Aguardando 0.5s...")
time.sleep(0.5)
print("Poll:", proc.poll())
print("Tentando ler linha do stdout...")
linha = proc.stdout.readline()
print("Linha:", repr(linha))
print("Poll apos readline:", proc.poll())
print("Stderr:", repr(proc.stderr.read()))
proc.terminate()
