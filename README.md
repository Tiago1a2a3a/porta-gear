# Porta GEAR — Controle de Acesso Local e Autônomo

Sistema local de controle de acesso desenvolvido para a **Porta GEAR** (Grupo de Estudos Avançados em Robótica — UFMG) em parceria com o **VeRLab** (Laboratório de Visão e Robótica).

O projeto é 100% autônomo, operando localmente no **Luckfox Pico Ultra** com leitor **PN532** (SPI) e relé **KY-019** (GPIO52), sem depender de LDAP, servidores externos ou acesso à Internet.

---

## 🏛️ Estrutura do Projeto

```text
Projeto_tiago/
├── src/
│   ├── modulo_rele/
│   │   ├── setup_rele.py           # Configuração do GPIO52 via sysfs
│   │   └── rele.py                 # Acionamento pulsado da fechadura
│   ├── modulo_leitor/
│   │   ├── setup_leitor.py         # Inicialização do executável PN532
│   │   ├── leitor.py               # Interface Python para libnfc
│   │   └── nativo/
│   │       ├── leitor_pn532.c      # Leitura nativa contínua em C (libnfc)
│   │       └── Makefile
│   ├── modulo_database/
│   │   ├── setup_database.py       # Inicialização do banco SQLite local
│   │   └── database.py             # CRUD de usuários, logs e credenciais
│   └── modulo_central/
│       ├── servicos_porta.py       # Camada de serviços desacoplada (Fonte da Verdade)
│       ├── gestor_modo.py          # Controle de concorrência (PRODUÇÃO vs CADASTRO)
│       ├── setup_sistema.py        # Inicialização dos componentes
│       ├── loop_sistema.py         # Polling contínuo de acesso da porta
│       ├── comandos_terminal.py    # Interface CLI administrativa
│       └── main.py                 # Ponto de entrada CLI
├── web/
│   ├── server.py                   # Servidor HTTP/REST nativo (sem dependências externas)
│   ├── templates/index.html        # Interface de comando SPA (Dark Theme GEAR)
│   ├── static/
│   │   ├── css/style.css           # Estilização moderna com Glassmorphism e Blur
│   │   ├── js/app.js               # Lógica reativa, polling e anti-bypass
│   │   └── img/                    # Identidade visual e logos oficiais
│   ├── iniciar_web.bat             # Inicializador rápido para Windows
│   └── iniciar_web.sh              # Inicializador para Linux / Luckfox
├── data/                           # Banco de dados SQLite local
├── docs/                           # Documentação de Arquitetura e Hardware
├── tests/                          # Testes unitários automatizados
└── main.py                         # Ponto de entrada CLI na raiz
```

---

## 🌐 Painel Web de Comando & Monitoramento

O sistema conta com uma interface web de alto padrão visual, desenvolvida especificamente com a identidade visual do GEAR e VeRLab, com foco em leveza, responsividade e total independência de bibliotecas externas (zero dependência de npm/pip).

### 🔒 Segurança e Autenticação Anti-Bypass
- **Bloqueio com Vidro Fosco (*Frosted Glass Blur*)**: Tela de login minimalista flutuando sobre o painel desfocado em tempo real.
- **Validação Anti-Bypass no Servidor**: Nenhuma rota da API (status, acionamento do relé, alternância de modo ou cadastro) pode ser consumida sem um token criptográfico emitido após o login.
- **Senha Fixa em Código**: Definida diretamente como constante imutável em [`src/modulo_central/servicos_porta.py`](src/modulo_central/servicos_porta.py):
  > **Senha de acesso de administrador (neste commit):** `123456789`

### 🚀 Como Executar o Servidor Web

#### No Windows:
Execute o atalho:
```cmd
iniciar_web.bat
```
Ou via linha de comando:
```cmd
python web\server.py --porta 8088
```

#### No Linux / Luckfox:
```bash
python3 web/server.py --porta 8088
```

Acesse no navegador:
👉 **http://localhost:8088**

---

## 💻 Comandos via Terminal (CLI)

Além do painel web, o gerenciamento administrativo completo pode ser realizado diretamente via linha de comando:

```bash
# Inicialização e estado
python3 main.py inicializar-banco
python3 main.py listar-usuarios
python3 main.py registros

# Gestão de membros
python3 main.py cadastrar-usuario --id 001 --nome "Ana" --uid 04A1B2C3
python3 main.py alterar-usuario --id 001 --nome "Ana Silva"
python3 main.py desativar-usuario --id 001
python3 main.py ativar-usuario --id 001
python3 main.py remover-usuario --id 001
```

### Execução no Hardware Real (Luckfox Pico Ultra):
Compila o leitor nativo em C e inicia o serviço permanente da porta:
```bash
make -C src/modulo_leitor/nativo
python3 main.py executar
```

---

## 🧪 Testes Automatizados

A suíte de testes cobre a integridade de banco de dados, regras de negócio, serviços orquestradores e validação de tokens:

```bash
python -m unittest discover -s tests -v
```

---

## 📚 Documentação Adicional
- [docs/ARQUITETURA.md](docs/ARQUITETURA.md) — Arquitetura de software e fluxo contínuo.
- [docs/HARDWARE.md](docs/HARDWARE.md) — Pinout e conexões SPI / GPIO no Luckfox Pico Ultra.
