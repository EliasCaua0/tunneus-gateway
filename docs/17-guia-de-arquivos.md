[← Índice da documentação](README.md)

# Apêndice B. Guia dos arquivos do projeto

A árvore abaixo orienta a navegação pelo repositório. A leitura
recomendada acompanha o mesmo percurso didático do documento: visão e
decisões, protocolo e núcleo, firmware, interface e verificação.

    tunneus/
    ├── cmd/gateway/                 ponto de entrada atual
    ├── cmd/client/                  cliente histórico V3
    ├── internal/
    │   ├── api/                     REST e SSE
    │   ├── controller/              operações, retries e broadcast
    │   ├── handlers/                raiz e health
    │   ├── protocol/                mensagens e validação de args
    │   ├── registry/                agentes, HMAC e persistência
    │   ├── server/                  inicialização e rotas
    │   ├── session/                 sessões, canais e TTL
    │   ├── wake/                    socket UDP
    │   └── websocket/               upgrade, autenticação e recepção
    ├── agents/esp32/                firmwares e instruções
    ├── web/dashboard/               SPA v5.1
    ├── web/assets/                  recursos visuais
    ├── tests/dashboard/             mock e testes Playwright
    └── docs/                        visão, ADRs, dashboard e glossário

**Tabela 25 — Arquivos principais e pontos de leitura**

| Arquivo                              | Conteúdo                          | O que observar                                   |
|--------------------------------------|-----------------------------------|--------------------------------------------------|
| `README.md`                          | Apresentação e instruções gerais. | Finalidade, execução e organização do projeto.   |
| `PROTOCOLO.md`                       | Contrato Tunneus V4.1.            | Mensagens, HMAC, sessão e argumentos.            |
| `docs/SYSTEM_OVERVIEW.md`            | Visão arquitetural.               | Subagente Passivo e Pico de Conexão.             |
| `docs/DECISOES_ARQUITETURAIS.md`     | Decisões e registros ADR.         | Motivação das escolhas e evolução histórica.     |
| `internal/controller/controller.go`  | Núcleo das operações.             | HTTP assíncrono, retries, canais e eventos.      |
| `internal/registry/registry.go`      | Cadastro de agentes.              | Capabilities, secrets e último IP.               |
| `internal/session/session.go`        | Sessões efêmeras.                 | Estado, authCh, resultCh, TTL e cleanup.         |
| `internal/websocket/handler.go`      | Conversa WebSocket.               | Hello, Welcome, Result, Bye e timers.            |
| `internal/wake/wake.go`              | Convocação UDP.                   | Challenge, WakeMAC e destino.                    |
| `internal/protocol/command.go`       | Mensagens e argumentos.           | Envelope, omissão de args e limites estruturais. |
| `agents/esp32/esp32_agent.ino.ino`   | Agente 01 V4.3-MARATHON.          | LED, estados e mecanismos de longa duração.      |
| `agents/esp32/agente03/agente03.ino` | Agente 03 V4.4.                   | Sensores, cache e motor não bloqueante.          |
| `web/dashboard/index.html`           | Interface completa.               | REST, SSE, parser, gráficos e controles.         |
| `tests/dashboard/mock_gateway.py`    | Gateway simulado.                 | Cenários REST/SSE e dados sintéticos.            |
| `tests/dashboard/test_dashboard.py`  | Automação do navegador.           | Verificações funcionais com Playwright.          |

## B.1 Dependências por ambiente

**Tabela 26 — Dependências e finalidade**

| Ambiente  | Dependência                           | Uso                                   |
|-----------|---------------------------------------|---------------------------------------|
| Go        | `github.com/google/uuid v1.6.0`       | UUIDs de operações e sessões.         |
| Go        | `github.com/gorilla/websocket v1.5.3` | Servidor WebSocket.                   |
| Go        | Módulo declara Go 1.24.4.             | Versão de linguagem do módulo.        |
| Arduino   | ArduinoWebsockets.                    | Cliente WebSocket nos ESP32.          |
| Arduino   | ArduinoJson 6.x.                      | Documentos JSON de tamanho fixo.      |
| Agente 03 | Adafruit BMP085.                      | Leitura do BMP180 por I²C.            |
| Agente 03 | `mbedtls/md`.                         | HMAC-SHA256.                          |
| Testes    | Python, Playwright e Chromium.        | Automação do navegador contra o mock. |

## B.2 Documentos internos de referência

-   ARCANLAB. **Tunneus Gateway — README**. Documento do repositório.
-   ARCANLAB. **Protocolo Tunneus V4.1**. Especificação do repositório.
-   ARCANLAB. **System Overview**. Visão da arquitetura e do modelo
    operacional.
-   ARCANLAB. **Decisões Arquiteturais**. Registros ADR do projeto.
-   ARCANLAB. **Dashboard Agente 03**. Contratos e comportamento da
    interface v5.1.
---

[Voltar ao índice da documentação](README.md)
