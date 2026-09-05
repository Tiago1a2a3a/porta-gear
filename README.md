# Projeto Tiago — controle de acesso local

Versão reorganizada do controle de acesso para Luckfox Pico Ultra. O projeto
original foi mantido separado como cópia de segurança.

## Estrutura

```text
src/
├── modulo_rele/
│   ├── setup_rele.py       inicializa o GPIO52
│   └── rele.py             abre a porta
├── modulo_leitor/
│   ├── setup_leitor.py     inicializa o PN532/libnfc uma vez
│   ├── leitor.py           aguarda os UIDs da conexão aberta
│   └── nativo/
│       └── leitor_pn532.c  polling persistente usando a API da libnfc
├── modulo_database/
│   ├── setup_database.py   abre/cria o SQLite
│   └── database.py         gerencia usuários e acessos
└── modulo_central/
    ├── setup_sistema.py        executa todos os setups uma vez
    ├── loop_sistema.py         mantém a leitura contínua dos cartões
    ├── comandos_terminal.py    comandos administrativos
    ├── funcoes_auxiliares.py   formatação e montagem de configurações
    └── main.py                 apenas escolhe e inicia o fluxo
```

O arquivo `main.py` da raiz é somente o ponto de entrada.

## Fluxo principal

```text
setup_sistema()
    ├── setup_rele()
    ├── setup_database()
    └── setup_leitor()

loop permanente
    ├── aguarda um UID do PN532
    ├── consulta o UID no SQLite
    ├── abre a porta se o usuário estiver ativo
    ├── registra a decisão
    └── o leitor nativo aguarda a retirada antes de publicar outro UID
```

## Comandos

```bash
python3 main.py inicializar-banco
python3 main.py cadastrar-usuario --id 001 --nome "Ana" --uid 04A1B2C3
python3 main.py listar-usuarios
python3 main.py alterar-usuario --id 001 --nome "Ana Silva"
python3 main.py desativar-usuario --id 001
python3 main.py ativar-usuario --id 001
python3 main.py remover-usuario --id 001
python3 main.py registros
```

No Luckfox, com PN532 e relé configurados:

```bash
make -C src/modulo_leitor/nativo
python3 main.py executar
```

O modo `executar` usa o hardware real. Não existe modo de simulação no código
de produção. A libnfc e o PN532 são abertos uma única vez pelo executável
`leitor_pn532`; o loop Python apenas aguarda os UIDs publicados por ele.

## Testes

```bash
python -m unittest discover -s tests -v
```

Consulte [docs/ARQUITETURA.md](docs/ARQUITETURA.md) e
[docs/HARDWARE.md](docs/HARDWARE.md).
