# Agentes ESP32 — Tunneus v4.0

Firmware para subagentes passivos ESP32.

## Requisitos

- Board: ESP32 DevKit v1/v2 ou compatível
- Arduino IDE 2.x
- Bibliotecas:
  - `ArduinoWebsockets` by gilmaimon
  - `ArduinoJson` by Benoit Blanchon

## Configuração

Edite as constantes no topo do arquivo `.ino`:

```cpp
const char* WIFI_SSID     = "SUA_REDE_WIFI";
const char* WIFI_PASSWORD = "SUA_SENHA_WIFI";
const char* GATEWAY_HOST  = "IP_DO_GATEWAY";  // ex: 192.168.1.10
const char* AGENT_ID      = "esp32-01";        // mude para cada protótipo: 01, 02, 03
```

## Agente 03 — Bancada de sensores e motor de passo

Sketch: `agente03/agente03.ino` (firmware v4.4, protocolo v4.1). Abra a pasta `agente03` no Arduino IDE (o nome da pasta deve ser igual ao do `.ino`).

Bibliotecas adicionais: `Adafruit BMP085 Library` (BMP180), além de `ArduinoWebsockets` e `ArduinoJson` 6.x.

Edite no topo: `WIFI_SSID`, `WIFI_PASSWORD`, `GATEWAY_HOST`. `AGENT_ID` e `SECRET_HEX` deve corresponder ao `esp32-03` do `registry.json` local.

| Capability | Argumentos | Resposta (stdout) |
|:---|:---|:---|
| `LER_SENSORES` | — | `TEMPERATURA=23.45 C \| PRESSAO=101325 Pa \| ALTITUDE=28.10 m \| CORRENTE=0.123 A \| DISTANCIA=35.2 cm` (`DISTANCIA=NA` sem eco) |
| `TEMPERATURA`, `PRESSAO`, `ALTITUDE`, `CORRENTE`, `DISTANCIA` | — | `valor unidade` (ex.: `23.45 C`) |
| `START` | — | gira continuamente (400 us, direita) até `PARE` ou 60 s |
| `PARE` | — | para o motor |
| `MOVER` | `dir`, `steps`, `speed` | inicia o movimento programado (ver `PROTOCOLO.md` 3.4.1) |

Calibração na bancada: se `direita` girar para o lado errado, inverta `DIR_DIREITA_NIVEL_ALTO`. Se `rapida` (200 us) perder passos com carga, aumente `PULSO_US_RAPIDA` e atualize a tabela em `PROTOCOLO.md` e `MOTOR.speeds` no dashboard.
