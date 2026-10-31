[← Índice da documentação](README.md)

# Apêndice A. Mensagens exemplificadas

Os exemplos seguintes reúnem o vocabulário V4.1 em uma sequência única.
UUIDs, challenge e MACs são deliberadamente representados por
marcadores; nenhuma credencial real é incluída.

## A.1 Wake

    {
      "type": "wake",
      "agent_id": "esp32-03",
      "session_id": "SESSION_UUID",
      "challenge": "CHALLENGE_HEX_64_CARACTERES",
      "auth_mac": "HMAC_SHA256_CHALLENGE_E_AGENT_ID"
    }

## A.2 Hello

    {
      "type": "hello",
      "agent_id": "esp32-03",
      "session_id": "SESSION_UUID",
      "challenge_response": "HMAC_SHA256_DO_CHALLENGE",
      "agent": "esp32",
      "version": "4.4"
    }

## A.3 Welcome

    {
      "type": "welcome",
      "session": "SESSION_UUID",
      "authenticated": true
    }

## A.4 Command sem argumentos

    {
      "type": "command",
      "command_id": "OPERATION_UUID",
      "cmd": "LER_SENSORES"
    }

## A.5 Command com argumentos

    {
      "type": "command",
      "command_id": "OPERATION_UUID",
      "cmd": "MOVER",
      "args": {"dir": "direita", "steps": 200, "speed": "normal"}
    }

## A.6 Result de leitura

    {
      "type": "result",
      "command_id": "OPERATION_UUID",
      "stdout": "23.45 C",
      "stderr": ""
    }

## A.7 Result conjunto

    {
      "type": "result",
      "command_id": "OPERATION_UUID",
      "stdout": "TEMPERATURA=23.45 C | PRESSAO=101325 Pa | ALTITUDE=28.10 m | CORRENTE=0.123 A | DISTANCIA=35.2 cm",
      "stderr": ""
    }

## A.8 Bye

    {
      "type": "bye",
      "session_id": "SESSION_UUID",
      "reason": "ack_timeout"
    }

## A.9 Evento de resultado por SSE

    event: message
    data: {"event":"result_received","op_id":"OPERATION_UUID","agent_id":"esp32-03","stdout":"23.45 C","stderr":""}

A forma exata dos campos adicionais de cada evento depende da etapa
publicada pelo Controller. O exemplo destaca os campos necessários para
relacionar agente, operação e resultado.
---

[Voltar ao índice da documentação](README.md)
