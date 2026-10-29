## PROTOCOLO.md

## Tunneus Protocol v4.1

Especificação do protocolo de comunicação entre Gateway e Subagentes

## 1. Visão Geral

O protocolo Tunneus v4.0 opera sobre duas camadas de transporte:

| Camada | Protocolo | Uso |
| --- | --- | --- |
| Sinalização | UDP (porta 18081) | Convocação do subagente (Wake |
|   |   | Packet) |
| Dados | WebSocket (porta 18080) | Autenticação, comandos e |
|   |   | resultados |

## Princípio: Subagente Passivo

O subagente (ESP32) nunca inicia conexões. Ele permanece em STANDBY ouvindo UDP e só abre WebSocket quando convocado pelo Gateway.

## 2. Fluxo Completo

## 3. Mensagens

## 3.1 Wake Packet (UDP)

Direção: Gateway → ESP

Transporte: UDP unicast, porta 18081


```
{
"type": "wake",
"agent_id": "esp32-01",
"session_id": "550e8400-e29b-41d4-a716-446655440000",
"challenge": "a1b2c3d4e5f6...",
"auth_mac": "hmac-sha256(challenge + agent_id, secret)"
}
```

| Campo | Tipo | Descrição |
| --- | --- | --- |
| type | string | Sempre "wake" |
| agent_id | string | Identificador do subagente |
| session_id | string | UUID v4 único da sessão |
| challenge | string | Hex 64 caracteres (32 bytes) |
| auth_mac | string | HMAC-SHA256(challenge || |
|   |   | agent_id, secret) em hex |

## Validação no ESP:

- 1. Verificar type == "wake"

- 2. Verificar agent_id corresponde ao próprio

- 3. Calcular expected = HMAC-SHA256(challenge + agent_id, secret)

- 4. Comparar expected com auth_mac (case-insensitive)

- 5. Se válido → transicionar para CONNECTING

## 3.2 Hello (WebSocket)

Direção: ESP → Gateway

Transporte: WebSocket (primeira mensagem após upgrade)

```
{
"type": "hello",
"agent_id": "esp32-01",
"session_id": "550e8400-e29b-41d4-a716-446655440000",
"challenge_response": "hmac-sha256(challenge, secret)",
"agent": "esp32-agent",
"version": "4.2"
}
```

| Campo | Tipo | Descrição |
| --- | --- | --- |
| type | string | Sempre "hello" |
| agent_id | string | Identificador do subagente |
| session_id | string | Mesmo UUID do Wake Packet |
| challenge_response | string | HMAC-SHA256(challenge, secret) |
|   |   | em hex |


*Table 3 – continued*

| Campo | Tipo | Descrição |
| --- | --- | --- |
| agent | string | Nome do agente (opcional) |
| version | string | Versão do firmware (opcional) |

## Validação no Gateway:

- 1. Buscar sessão efêmera por session_id

- 2. Se não encontrada → rejeitar (ESP conectou sem convocação)

- 3. Buscar agente no Registry por agent_id

- 4. Calcular expected = HMAC-SHA256(challenge, secret)

- 5. Comparar com challenge_response

- 6. Se válido → enviar Welcome, notificar Controller

## 3.3 Welcome (WebSocket)

Direção: Gateway → ESP

```
{
"type": "welcome",
"session": "550e8400-e29b-41d4-a716-446655440000",
"authenticated": true
}
```

| Campo | Tipo | Descrição |
| --- | --- | --- |
| type | string | Sempre "welcome" |
| session | string | SessionID confirmado |
| authenticated | bool | true se autenticado |

## 3.4 Command (WebSocket)

## Direção: Gateway → ESP

```
{
"type": "command",
"command_id": "op-123-uuid",
"cmd": "LED_ON"
}
```

| Campo | Tipo | Descrição |
| --- | --- | --- |
| type | string | Sempre "command" |
| command_id | string | ID da operação |


*Table 5 – continued*

| Campo | Tipo | Descrição |
| --- | --- | --- |
| cmd | string | Comando a executar |
| args | object | Opcional (v4.1). Parâmetros do |
|   |   | comando; ausente quando não há. |

## 3.4.1 Command com argumentos (v4.1)

O campo args é opcional. Sem ele a mensagem é idêntica à da v4.0, portanto agentes e comandos existentes (LED_ON, LIGAR, START, LER_SENSORES...) não mudam.

O Gateway não interpreta args: apenas valida a forma (ver abaixo) e repassa. O significado de cada campo é contrato da capability e é validado pelo firmware, que recusa argumento inválido via stderr sem tocar no hardware.

Limites verificados pelo Gateway (HTTP 400 se excedidos):

| Regra | Valor |
| --- | --- |
| Campos em args | no máximo 8 |
| Nome do campo | 1 a 24 caracteres |
| Valores | texto, número ou booleano (sem objetos nem listas) |
| Texto | no máximo 32 caracteres |
| args serializado | no máximo 256 bytes |

O limite existe porque o ESP32 interpreta a mensagem em um documento JSON de tamanho fixo.

Requisição REST correspondente: POST /api/agents/{id}/command com {"cmd":"MOVER","args":{...}}. O campo args é repassado sem alteração e também aparece no evento SSE command_created.

### Capability MOVER (Agente 03, firmware v4.4)

Executa um número fixo de passos do motor de passo.

```
{
"type": "command",
"command_id": "op-123-uuid",
"cmd": "MOVER",
"args": { "dir": "direita", "steps": 200, "speed": "normal" }
}
```

| Campo | Tipo | Valores válidos |
| --- | --- | --- |
| dir | string | "direita" ou "esquerda" |
| steps | inteiro | 1 a 30000 |
| speed | string | "lenta", "normal" ou "rapida" |

Velocidade = meio-período do pulso no pino PUL (um passo = nível alto + nível baixo = 2 × valor):

| speed | Meio-período | Passos/s aprox. |
| --- | --- | --- |
| lenta | 800 us | 625 |
| normal | 400 us | 1250 (padrão do exemplo e do START) |
| rapida | 200 us | 2500 |

Semântica:

- "direita" corresponde ao nível alto de DIR (sentido do primeiro giro do exemplo da bancada). O mapeamento para o sentido físico real é uma constante do firmware (DIR_DIREITA_NIVEL_ALTO).
- Resultado de sucesso (stdout): "Movimento INICIADO: ...". Significa que o movimento foi iniciado, NÃO que terminou: a sessão fecha antes e o firmware não informa posição nem fim.
- Argumento inválido: stdout vazio, stderr com o motivo, motor não se move.
- O movimento continua após o Bye. PARE o interrompe; um novo START ou MOVER substitui o movimento em curso.
- O limite de segurança de 60 s do firmware vale também para MOVER.
- O Gateway nunca reenvia MOVER depois que o comando foi entregue (ver seção 5.1).

## 3.5 Result (WebSocket)

Direção: ESP → Gateway

```
{
"type": "result",
"command_id": "op-123-uuid",
"stdout": "LED ligado",
"stderr": ""
}
```

| Campo | Tipo | Descrição |
| --- | --- | --- |
| type | string | Sempre "result" |
| command_id | string | ID da operação |
| stdout | string | Saída padrão |
| stderr | string | Saída de erro (opcional) |

## 3.6 Bye (WebSocket)

Direção: ESP → Gateway

```
{
"type": "bye",
"session_id": "550e8400-e29b-41d4-a716-446655440000",
"reason": "completed"
}
```

| Campo | Tipo | Descrição |
| --- | --- | --- |
| type | string | Sempre "bye" |
| session_id | string | SessionID |
| reason | string | Motivo: "completed", |
|   |   | "ack_timeout", "error" |

## 4. Timeouts

| Etapa | Timeout | Ação em caso de timeout |
| --- | --- | --- |
| WS Connection | 10s | ESP volta para STANDBY |


*Table 8 – continued*

| Etapa | Timeout | Ação em caso de timeout |
| --- | --- | --- |
| Auth (Hello → Welcome) | 8s (ESP) / 10s (Gateway) | Controller retry com novo |
|   |   | sessionID |
| Command (Welcome → | 10s | ESP volta para STANDBY |
| Command) |   |   |
| Result (Command → Result) | 15s (Gateway) | Controller retry (exceto comandos não idempotentes, ver 5.1) |
| ACK (Result → Bye) | 5s | ESP envia Bye e desconecta |
| Session TTL | 60s | Gateway remove sessão |
|   |   | fantasma |

## 5. Retry e Backoff

O Gateway implementa backoff exponencial para Wake:

| Tentativa | Delay antes do Wake |
| --- | --- |
| 1 | 0s (imediato) |
| 2 | 1s |
| 3 | 2s |
| 4 | 4s |
| 5 | 8s |

Após 5 tentativas → operação marcada como failed. (Valores conforme `internal/controller/controller.go`; a v4.0 do documento listava 4 tentativas com 0, 2, 4 e 8 s, o que não correspondia ao código.)

Importante: Cada tentativa gera um sessionID e challenge novos, eliminando a necessidade de cache anti-replay no ESP.

## 5.1 Comandos não idempotentes (v4.1)

Falhas de Wake e de autenticação acontecem antes de o comando ser entregue e continuam sendo repetidas.

Se o comando já foi entregue (evento command_sent) e o resultado não chega no prazo, o agente pode ter executado e só a resposta se perdeu. Para capabilities cujo efeito físico não pode ser repetido (hoje: MOVER), o Gateway NÃO reenvia: emite result_timeout seguido de operation_failed com reason result_unconfirmed_no_retry. Capabilities idempotentes (LED_ON, START, PARE, leituras) mantêm o comportamento de retry.

A lista está em nonIdempotentCmds, em internal/controller/controller.go.

## 6. Segurança

## 6.1 HMAC-SHA256

Todas as autenticações usam HMAC-SHA256:

Wake MAC:

Hello Resp: HMAC-SHA256(challenge, secret)

HMAC-SHA256(challenge || agent_id, secret)

## 6.2 Secret

• Gateway: base64, 32+ bytes, armazenada no Registry

• ESP: hex direto, mesmos bytes raw

• Geração: openssl rand -base64 32

## 6.3 Prevenção de Replay

- SessionID único por operação (UUID v4)

- Challenge aleatório de 32 bytes


- Não há reutilização de sessionID

## 7. Estados do Subagente

| STANDBY ──► CONNECTING ──► AUTHENTIC ──► COMMAND ──► ACK ──► DISCONNECTING ──► STANDBY |
| --- |
| │ |
| (timeout em qualquer estado volta para STANDBY) |

| Estado | Descrição |
| --- | --- |
| STANDBY | UDP ativo, WS fechado. Aguardando |
|   | convocação. |
| CONNECTING | UDP parado, WS abrindo. Enviando Hello. |
| AUTHENTIC | WS aberto. Aguardando Welcome. |
| COMMAND | Autenticado. Aguardando comando do Gateway. |
| ACK | Comando executado. Aguardando confirmação. |
| DISCONNECTING | Enviando Bye, fechando WS. |

## 8. Códigos de Erro

| Erro | Significado |
| --- | --- |
| agent_not_registered | AgentID não existe no Registry |
| unknown_ip | LastIP vazio no Registry |
| hmac_invalid | Wake MAC não corresponde |
| session_not_found | ESP conectou sem convocação |
| challenge_invalid | Challenge response incorreta |
| auth_timeout | ESP não autenticou a tempo |
| result_timeout | ESP não enviou resultado |
| max_retries_exhausted | Todas as 5 tentativas falharam |
| result_unconfirmed_no_retry | Comando não idempotente entregue, resultado não chegou, não reenviado (v4.1) |

## 9. Changelog

| Versão | Data | Mudanças |
| --- | --- | --- |
| v4.1 | 2026-10-24 | Campo opcional args em Command; |
|   |   | capability MOVER; comandos não |
|   |   | idempotentes não são reenviados; |
|   |   | eventos SSE gerados com json. |
| v4.0 | 2026-08-15 | Subagente Passivo + Pico de |
|   |   | Conexão. Sem heartbeat. Sem |
|   |   | reconexão automática. |
| v3.1 | 2026-08-10 | Agente autônomo com heartbeat e |
|   |   | reconexão (obsoleto) |
| v3.0 | 2026-08-05 | Primeira versão com ESP32 físico |
| v2.0 | 2026-07-20 | Gateway + cliente Go em terminal |

Generated by Kimi


*Table 12 – continued*

| Versão | Data | Mudanças |
| --- | --- | --- |
| v1.0 | 2026-07-07 | Conceito inicial, estrutura base |
