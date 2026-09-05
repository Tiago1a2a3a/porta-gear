# Leitor persistente do PN532

Este pequeno executável mantém a libnfc e o PN532 abertos durante toda a
execução. Ele não é um servidor e não usa rede. A comunicação com o Python é
local, pelas saídas do próprio processo.

Compile no Luckfox depois de instalar os cabeçalhos da libnfc:

```bash
cd src/modulo_leitor/nativo
make
```

Protocolo de saída:

```text
READY nome_do_dispositivo
UID 04A1B2C3
UID 11223344
```

O leitor procura somente cartões ISO14443A a 106 kbps, modalidade usada pelos
cartões MIFARE do projeto.

