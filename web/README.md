# Interface Web de Comando - Porta GEAR (Tema GEAR / VerLab)

Painel de controle local desenvolvido para gerenciamento de acesso e comando da fechadura da **Porta GEAR** (UFMG).

---

## 🎨 Características e Identidade Visual

- **Identidade GEAR / VerLab**: Cores institucionais Verde VerLab (`#2e7d32`, `#4caf50`) e Azul Robótica/GEAR (`#1e3a8a`, `#2563eb`), com Dark Theme moderno de alto contraste.
- **100% Autocontido e Offline**: Sem dependência de CDNs, fontes externas ou pacotes externos do pip. Roda diretamente com o Python nativo.
- **Baixo Consumo de Recursos**: Ocupa menos de 15 MB de RAM, ideal tanto para PCs quanto para placas embarcadas como o Luckfox Pico Ultra.

---

## 🚀 Funcionalidades

1. **Painel de Comando da Porta**:
   - Botão de abertura com acionamento do relé simulado e temporizador regressivo de segurança.
   - Animação visual em tempo real do estado da fechadura (Trancada / Aberta).
   - Feedback sonoro sintetizado em HTML5 Web Audio API.

2. **Simulador de Leitura RFID / NFC**:
   - Permite testar tags aproximadas (ex: `04A1B2C3`), verificando permissão no banco e disparando a abertura quando autorizado.
   - Chips rápidos com tags de exemplo para testes ágeis.

3. **Gerenciamento de Usuários (CRUD)**:
   - **Cadastro**: com auto-sugestão do próximo ID sequencial (`001`, `002`...).
   - **Edição**: alteração de nome, UID do cartão ou estado.
   - **Ativação/Desativação com 1 clique**: bloqueio ou liberação imediata sem excluir o cadastro.
   - **Exclusão segura**: preserva rastreabilidade no histórico aplicando o padrão `-exl`.
   - **Busca em tempo real**: filtro instantâneo por nome.

4. **Histórico de Acessos**:
   - Visualização em tempo real das tentativas de acesso, horários e motivos.

---

## 🖥️ Como Executar

### No Windows:
Basta dar dois cliques no arquivo:
```cmd
iniciar_web.bat
```
Ou executar no terminal:
```cmd
python server.py --porta 8088
```

### No Linux / Luckfox:
```bash
bash iniciar_web.sh
```

Acesse no navegador:
👉 **http://localhost:8088**

> **Senha padrão deste commit:** `123456789` (definida diretamente em `src/modulo_central/servicos_porta.py`).
