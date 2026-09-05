# Arquitetura do Projeto Tiago

## Regra de organização

Cada componente possui dois arquivos:

1. `setup_*.py`: prepara o componente uma vez durante a inicialização;
2. arquivo de operação: contém as funções usadas durante o funcionamento.

Os módulos de leitor, relé e database não dependem do módulo central. O módulo
central pode importar os três e coordenar o fluxo.

## Módulo do relé

- `setup_rele.py`: cria o objeto, exporta o GPIO52, configura como saída e deixa
  o relé desligado em nível `HIGH`.
- `rele.py`: contém a configuração dos pulsos e `ReleLuckfox.abrir_porta()`.

## Módulo do leitor

- `setup_leitor.py`: inicia uma única instância do leitor nativo e aguarda a
  confirmação de que o PN532 está pronto.
- `leitor.py`: mantém a referência ao processo aberto e aguarda os UIDs.
- `nativo/leitor_pn532.c`: abre a libnfc e o PN532 uma vez, executa o polling
  ISO14443A continuamente e publica cada UID pela saída local do processo.

O Device Tree, o SPI0 e a configuração da libnfc continuam sendo tarefas do
sistema Linux. O Python usa o dispositivo já disponibilizado pela libnfc.

## Módulo do database

- `setup_database.py`: abre/cria o arquivo e garante que as tabelas existam.
- `database.py`: adiciona, procura, altera, ativa, desativa e remove usuários;
  verifica acessos e grava o histórico.

O esquema permanece compatível com o banco da versão anterior:

```text
users
  user_id
  name
  card_uid
  is_active
  created_at
  updated_at

access_log
  id
  user_id
  card_uid
  granted
  reason
  occurred_at
```

## Módulo central

- `setup_sistema.py`: chama os três setups e devolve os componentes prontos.
- `loop_sistema.py`: executa o loop permanente e processa os UIDs.
- `comandos_terminal.py`: define e executa os comandos administrativos.
- `funcoes_auxiliares.py`: formata resultados e monta configurações.
- `main.py`: apenas escolhe entre o loop e um comando administrativo.

O loop Python fica bloqueado em `leitor.ler()` sem reinicializar o equipamento.
O leitor nativo usa `nfc_initiator_target_is_present()` para aguardar a retirada
do cartão, impedindo aberturas repetidas.

## Estado da validação

A lógica pode ser testada em qualquer computador. Ainda precisam ser validados
no Luckfox:

- PN532 Funduino V3 pela libnfc em SPI;
- disponibilidade de `/dev/spidev0.0`;
- GPIO52 e nível ativo baixo do KY-019;
- duração real dos pulsos da fechadura.
