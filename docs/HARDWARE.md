# Hardware e pinagem

## PN532 Funduino V3 — SPI0

| PN532 | Luckfox Pico Ultra | GPIO | Estado |
|---|---|---:|---|
| VCC | 5 V | — | conectado |
| GND | GND | — | conectado |
| SS / SSEL | SPI0_CS0_M0 / GPIO1_C0 | 48 | conectado |
| SCK | SPI0_CLK_M0 / GPIO1_C1 | 49 | conectado |
| MOSI | SPI0_MOSI_M0 / GPIO1_C2 | 50 | conectado |
| MISO | SPI0_MISO_M0 / GPIO1_C3 | 51 | conectado |
| RSTO / RSTPD_N | GPIO1_C5 | 53 | conectado |
| IRQ | GPIO2_A1 | 65 | conectado |

O dispositivo SPI esperado no Linux é `/dev/spidev0.0`. O seletor do PN532
deve estar na posição correspondente ao modo SPI.

## Relé KY-019 / Keyes SR1Y

| Relé | Luckfox | GPIO | Estado |
|---|---|---:|---|
| S / IN | GPIO1_C4 | 52 | conectado |
| + | 5 V | — | conectado |
| − | GND | — | conectado |
| COM/NO/NC | circuito da fechadura | — | ainda não conectado |

O código considera o módulo ativo em nível alto:

```text
LOW  (0) = relé desligado (repouso)
HIGH (1) = relé acionado (fechadura abre)
```

