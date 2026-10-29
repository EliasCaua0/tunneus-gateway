# ArcanLab — Tunneus Gateway: Visão Geral do Sistema

> Documento de referência para desenvolvedores e agentes de IA que trabalham no projeto pela primeira vez.

---

## 1. O que é o ArcanLab

O ArcanLab é um ecossistema modular para computação distribuída, automação e dispositivos, desenvolvido como projeto de pesquisa acadêmica no **Instituto Federal Sul-rio-grandense — Campus Novo Hamburgo**.

O **Tunneus Gateway** é o componente central do ArcanLab: um servidor escrito em Go que orquestra a comunicação entre um operador humano (via Dashboard ou API) e dispositivos embarcados ESP32 (chamados de subagentes).

**Autores:**

- Elias Cauã de Souza — Pesquisador e Desenvolvedor
- Marcelo da Silva dos Santos — Orientador

---

## 2. Propósito do sistema

O Tunneus resolve o problema de controlar dispositivos embarcados em rede local de forma segura, eficiente e sem complexidade desnecessária.

O modelo adotado é o **Subagente Passivo com Pico de Conexão**:

- O ESP32 **nunca** inicia conexões por conta própria.
- Ele permanece em **STANDBY**, ouvindo pacotes UDP.
- Quando o Gateway precisa enviar um comando, ele envia um **Wake Packet** UDP para o ESP32.
- O ESP32 valida o pacote, abre uma conexão WebSocket, autentica-se via HMAC-SHA256 challenge-response, executa o comando, retorna o resultado e desconecta.
- Todo o ciclo dura menos de 2 segundos.

Esse modelo elimina heartbeats constantes, reconexões automáticas problemáticas, consumo de energia desnecessário e estados "online/offline" ambíguos.

---

## 3. Estado atual do projeto

**Versão de referência:** V4 (branch `migracao-v4`).

O sistema possui uma base funcional estável (v1.0.0), demonstrada em operação com protótipos físicos. Não existem testes automatizados do Gateway (Go). O dashboard tem uma suíte própria em `tests/dashboard/` (Playwright contra um Gateway simulado, ver `docs/DASHBOARD_AGENTE03.md`). Não há CI nem linter configurados.

### Fase de desenvolvimento

O ArcanLab está em uma fase de **desenvolvimento contínuo, cuidadoso e orientado à qualidade**. O projeto não está condicionado por prazos de apresentação. A prioridade é construir uma infraestrutura sólida, sustentável e preparada para evoluir gradualmente.

> Contexto histórico: a v1.0.0 foi desenvolvida e estabilizada para demonstração em uma feira científica (agosto de 2026). A pressão desse prazo moldou decisões pragmáticas que serviram ao objetivo da época. O desenvolvimento posterior segue filosofia diferente — ver `ROADMAP.md`.

### Dependências externas (Go)

| Dependência | Uso |
|:---|:---|
| `github.com/google/uuid` | Geração de UUIDs para sessions e operations |
| `github.com/gorilla/websocket` | WebSocket server (upgrade, read, write) |

### Dependências do firmware (Arduino)

| Biblioteca | Uso |
|:---|:---|
| `ArduinoWebsockets` (gilmaimon) | Cliente WebSocket no ESP32 |
| `ArduinoJson` (Benoit Blanchon) | Serialização/deserialização JSON |

---

## 4. Arquitetura geral

```
      USUARIO / DASHBOARD                    ESP32 SUBAGENTES
              │                                     │
              │ HTTP REST + SSE                      │ UDP (porta 18081)
              ▼                                     │
┌──────────────────────────────────────────────────────────────────┐
│                        Tunneus Gateway (:18080)                  │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────────────┐  │
│  │  Controller  │   │   Registry   │   │   EphemeralStore    │  │
│  │ (orquestra   │   │ (agentes,    │   │   (sessões com TTL  │  │
│  │  operações,  │   │  secrets,    │   │    60s, canais de   │  │
│  │  retry,      │   │  IPs,        │   │    sincronização)   │  │
│  │  SSE)        │   │  capabilities│   │                     │  │
│  └──────┬───────┘   └──────────────┘   └─────────────────────┘  │
│         │                                                        │
│  ┌──────▼───────┐   ┌──────────────┐   ┌─────────────────────┐  │
│  │ Wake Sender  │   │  WS Handler  │   │   API + SSE         │  │
│  │ (UDP unicast)│   │  (auth HMAC) │   │   (REST assíncrona) │  │
│  └──────────────┘   └──────────────┘   └─────────────────────┘  │
│                                                                  │
│  ┌──────────────┐   ┌──────────────┐                            │
│  │   Handlers   │   │  Dashboard   │                            │
│  │  (/, /health)│   │  (SPA HTML)  │                            │
│  └──────────────┘   └──────────────┘                            │
└──────────────────────────────────────────────────────────────────┘
                              │ WebSocket (:18080/ws)
                              ▼
                     ┌─────────────────┐
                     │   ESP32 Agent   │
                     │   (firmware)    │
                     └─────────────────┘
```

### Fluxo de comunicação

| Camada | Protocolo | Direção | Porta | Propósito |
|:---|:---|:---|:---|:---|
| Sinalização | UDP unicast | Gateway → ESP32 | 18081 | Wake (convocação) |
| Dados | WebSocket | ESP32 ↔ Gateway | 18080 | Hello, Welcome, Command, Result, Bye |
| Controle | REST (HTTP) | Dashboard → Gateway | 18080 | Enviar comando, listar agentes, consultar operação |
| Eventos | SSE | Gateway → Dashboard | 18080 | Eventos em tempo real |
| Persistência | File I/O | Gateway ↔ disco | — | registry.json |

---

## 5. Componentes principais

### 5.1 Gateway (Go)

**Ponto de entrada:** `cmd/gateway/main.go`

O Gateway é o servidor central. Ao iniciar (`server.Start()`), ele:

1. Carrega o Registry a partir de `registry.json`.
2. Cria o socket UDP para envio de Wake Packets.
3. Inicializa o Controller (orquestrador).
4. Monta as rotas HTTP (API, Dashboard, WebSocket, Health).
5. Escuta na porta 18080.

O binário deve ser executado a partir da raiz do repositório, pois lê `registry.json` e serve `web/dashboard/` usando caminhos relativos ao diretório de trabalho.

**Build:** `go build -o tunneus-gateway ./cmd/gateway`

> Não usar `go build ./...` — o cliente legado em `cmd/client/` não compila contra o protocolo V4.

### 5.2 Controller (`internal/controller/controller.go`)

O coração do sistema. Gerencia o ciclo de vida completo de uma operação:

1. Recebe a intenção do usuário via `Submit(agentID, command, args)` (`args` opcional, protocolo v4.1).
2. Valida agente e capability no Registry.
3. Cria uma `Operation` com UUID.
4. Executa em background (goroutine) com retry e backoff exponencial.
5. Para cada tentativa: gera novo sessionID + challenge, envia Wake, cria sessão efêmera, aguarda autenticação (canal `authCh`), envia comando, aguarda resultado (canal `resultCh`).
6. Faz broadcast de eventos SSE para clientes conectados.
7. Limpa operações antigas a cada 5 minutos (>30 min).

**Retry com backoff:** 5 tentativas com delays de 0s, 1s, 2s, 4s, 8s.

**Sem reenvio após a entrega (v4.1):** capabilities de efeito físico não idempotente (`nonIdempotentCmds`, hoje `MOVER`) não são reenviadas depois de `command_sent`. Se o resultado não chega, a operação termina com `operation_failed` / `result_unconfirmed_no_retry`. Falhas de Wake e de autenticação continuam sendo repetidas.

**Eventos SSE:** montados por `emit()` com `json.Marshal`. Eventos emitidos: `command_created` (com `args`, se houver), `wake_sent`, `wake_failed`, `auth_timeout`, `auth_ok`, `command_send_failed`, `command_sent`, `result_timeout`, `result_received` (`stdout`, `stderr`), `operation_failed` (`reason`). Todos carregam `op_id` e `agent_id`.

### 5.3 Registry (`internal/registry/registry.go`)

Cadastro persistente de subagentes conhecidos. Armazena em memória (map) e persiste em `registry.json`.

Cada entrada contém: `agent_id`, `secret` (base64), `last_ip`, `mac`, `capabilities`, `last_seen`, `status`, `firmware_ver`, `name`, `type`, `icon`, `description`.

Funções importantes:

- `ComputeMAC()` — calcula HMAC-SHA256(challenge + agent_id, secret) para Wake Packets.
- `ValidateChallengeResponse()` — valida HMAC-SHA256(challenge, secret) do Hello.
- `InitRegistry()` — carrega de arquivo e sobrescreve esp32-01/esp32-02 com valores hardcoded (ver seção de limitações).

**Direção arquitetural confirmada:** o Registry deve evoluir para estado operacional puro — carregar de `registry.json` se existir, criar vazio se não existir, sem hardcoding.

### 5.4 Sessões efêmeras (`internal/session/session.go`)

Cada operação cria uma `EphemeralSession` que:

- Armazena o challenge gerado, o commandID e a conexão WebSocket (quando o ESP conecta).
- Fornece canais buffered (`authCh`, `resultCh`) para sincronização entre Controller e WS Handler.
- Possui TTL de 60 segundos com cleanup automático a cada 30s.

O `EphemeralStore` é uma variável global de pacote instanciada no carregamento do módulo.

### 5.5 Wake Sender (`internal/wake/wake.go`)

Encapsula um socket UDP efêmero (bind em `:0`) para envio de Wake Packets unicast para o IP registrado do subagente na porta 18081.

### 5.6 WebSocket Handler (`internal/websocket/handler.go`)

Ponto de entrada do ESP32 no Gateway. Fluxo:

1. Upgrade HTTP → WebSocket.
2. Timeout de leitura (10s) para receber Hello.
3. Busca sessão efêmera pelo `session_id` do Hello.
4. Valida `challenge_response` via HMAC-SHA256.
5. Associa conexão à sessão e envia Welcome.
6. Notifica Controller via `authCh`.
7. Loop de leitura: processa Result e Bye.
8. Timeout geral de sessão (30s).

### 5.7 API (`internal/api/agents.go`)

Endpoints REST:

| Rota | Método | Função |
|:---|:---|:---|
| `/api/agents` | GET | Lista todos os agentes registrados (visão pública, sem secret) |
| `/api/agents/{id}/command` | POST | Submete um comando `{"cmd":"...","args":{...}}` (`args` opcional; HTTP 202 Accepted, processamento assíncrono; HTTP 400 se `args` violar os limites) |
| `/api/operations/{id}` | GET | Consulta o estado de uma operação. Resposta: `{"success":true,"operation":{"status":...}}` |
| `/api/events` | GET | Server-Sent Events (stream de eventos em tempo real) |

A API não possui autenticação ou autorização.

### 5.8 Dashboard (`web/dashboard/index.html`)

SPA em um único arquivo HTML com CSS e JavaScript inline, sem bibliotecas nem CDN (ADR-008). Dashboard v5.1, dedicado à bancada do Agente 03 (ver `docs/DASHBOARD_AGENTE03.md` e ADR-014). Funcionalidades:

- Painel de um agente (`esp32-03` por padrão; `?agent=<id>` aponta para outro agente do Registry). Não há seletor.
- Visão geral: estado do agente, pontos de atenção, última leitura de cada grandeza e contadores.
- Timeline do Pico de Conexão (STANDBY → WAKE → AUTH → CMD → RESULT), marcada só quando o evento SSE chega.
- Bancada: gráficos de temperatura, pressão, altitude, corrente e distância (leitura sob demanda, histórico em memória) e acionamentos do motor (START, PARE e movimento programado com direção, passos e velocidade).
- Controles ativados a partir das capabilities do Registry.
- Operações e eventos desta sessão; polling de `/api/agents` a cada 3 segundos como complemento ao SSE.

### 5.9 Protocol (`internal/protocol/`)

Define as structs Go para cada tipo de mensagem do protocolo (v4.1):

| Arquivo | Tipo | Direção |
|:---|:---|:---|
| `wake.go` | WakePacket | Gateway → ESP (UDP) |
| `hello.go` | Hello | ESP → Gateway (WS) |
| `welcome.go` | Welcome | Gateway → ESP (WS) |
| `command.go` | Command (`args` opcional, v4.1) + `ValidateArgs` | Gateway → ESP (WS) |
| `result.go` | Result | ESP → Gateway (WS) |
| `bye.go` | Bye | ESP → Gateway (WS) |

Arquivos auxiliares: `types.go` (constantes), `message.go` (struct base), `json.go` (encode/decode), `router.go` (extrai tipo de mensagem).

---

## 6. Firmware ESP32 (`agents/esp32/esp32_agent.ino.ino`)

Firmware Arduino (v4.3-MARATHON) para o Agente 01 (controle de LED). O Agente 02 (Polias Industriais) possui firmware semelhante com comandos específicos, mas este ainda não está commitado no repositório.

O Agente 03 tem firmware próprio em `agents/esp32/agente03/agente03.ino` (v4.4): mesma máquina de estados e autenticação, mais sensores (BMP180, ACS712, HC-SR04), motor de passo não bloqueante e leitura de `args` do Command (capability `MOVER`). Detalhes em `agents/esp32/README.md`.

### Máquina de estados

```
STANDBY ──► CONNECTING ──► AUTHENTIC ──► COMMAND ──► ACK ──► DISCONNECTING ──► STANDBY
    │                                                                              ▲
    └──────────────── (timeout em qualquer estado > 15s) ─────────────────────────┘
```

### Mecanismos de resiliência

| Mecanismo | Intervalo | Ação |
|:---|:---|:---|
| State Watchdog | 15s | Força retorno a STANDBY se travado |
| WiFi Check | 5s | Reconecta ou reinicia ESP |
| UDP Socket Refresh | 5 min | Recria socket (evita morte silenciosa do LwIP) |
| Heap Check | Cada operação | Reinicia se <20KB livres |
| Reboot Preventivo | 60 min | Reinicia em STANDBY para limpar fragmentação |

### Autenticação

O ESP armazena o secret como hex bruto (`SECRET_HEX`). O Gateway armazena como base64. Ambos representam os mesmos bytes raw. A validação do Wake usa HMAC-SHA256(challenge + agent_id, secret); o Hello responde com HMAC-SHA256(challenge, secret).

> A senha Wi-Fi presente no firmware é fictícia/demonstrativa e não representa uma credencial real.

---

## 7. Fluxo completo de uma operação

```
      USUARIO                    GATEWAY                          ESP32
         │                          │                                │
    1.   │── POST /api/agents/      │                                │
         │   {id}/command           │                                │
         │   {"cmd":"LED_ON"}       │                                │
         │                          │                                │
    2.   │◄── HTTP 202             │                                │
         │   {op_id, status}        │                                │
         │                          │                                │
    3.   │   SSE ◄── command_created│                                │
         │                          │                                │
    4.   │                       controller.execute()                │
         │                          │── UDP Wake ──────────────────►│ :18081
         │                          │   {type, agent_id, session_id, │
         │                          │    challenge, auth_mac}        │
         │                          │                                │
    5.   │   SSE ◄── wake_sent     │                                │
         │                          │                   [valida HMAC]│
         │                          │                   [para UDP]   │
         │                          │                                │
    6.   │                          │◄────────── WS Connect ────────│ :18080/ws
         │                          │                                │
    7.   │                          │◄────────── Hello ─────────────│
         │                          │   {agent_id, session_id,       │
         │                          │    challenge_response}         │
         │                          │                                │
    8.   │                       [WS Handler valida HMAC]            │
         │                       [notifica Controller via authCh]    │
         │                          │                                │
    9.   │                          │──────────── Welcome ──────────►│
         │                          │                                │
   10.   │   SSE ◄── auth_ok      │                                │
         │                          │                                │
   11.   │                          │──────────── Command ──────────►│
         │                          │   {command_id, cmd}            │
         │                          │                                │
   12.   │   SSE ◄── cmd_sent     │                       [executa]│
         │                          │                                │
   13.   │                          │◄────────── Result ────────────│
         │                          │   {command_id, stdout}         │
         │                          │                                │
   14.   │   SSE ◄── result        │                                │
         │                          │                                │
   15.   │                          │◄────────── Bye ───────────────│
         │                          │                                │
   16.   │                       [cleanup sessão, save registry]     │
         │                          │                          [STANDBY]
```

Se a autenticação ou o resultado sofrer timeout, o Controller remove a sessão atual, gera novo sessionID + challenge, aguarda o backoff e reenvia o Wake. Após 5 tentativas sem sucesso, a operação é marcada como `failed` e o agente como `unreachable`.

---

## 8. Estrutura do repositório

```
tunneus-gateway/
├── cmd/
│   ├── gateway/main.go            # Ponto de entrada do Gateway (V4)
│   └── client/main.go             # [HISTÓRICO] Cliente Go da era v3 — não compila na V4
│
├── internal/
│   ├── server/server.go           # Inicialização de subsistemas, HTTP mux
│   ├── controller/controller.go   # Orquestrador assíncrono, retry, SSE
│   ├── registry/registry.go       # Cadastro persistente de agentes, HMAC
│   ├── session/session.go         # Sessões efêmeras, canais de sincronização
│   ├── wake/wake.go               # UDP Wake sender
│   ├── websocket/handler.go       # WebSocket handler, autenticação
│   ├── api/agents.go              # REST API + SSE
│   ├── handlers/root.go           # Rota /
│   ├── handlers/health.go         # Rota /health
│   └── protocol/                  # Structs de mensagem (1 arquivo por tipo)
│       ├── types.go               # Constantes de tipo
│       ├── message.go             # Struct base
│       ├── json.go                # Encode/Decode
│       ├── router.go              # Extração de tipo
│       ├── wake.go, hello.go, welcome.go, command.go, result.go, bye.go
│
├── agents/esp32/
│   ├── esp32_agent.ino.ino        # Firmware do Agente 01 (LED) — v4.3-MARATHON
│   ├── agente03/agente03.ino      # Firmware do Agente 03 (sensores + motor de passo) — v4.4
│   └── README.md                  # Instruções de configuração do firmware
│
├── web/
│   ├── dashboard/index.html       # Dashboard SPA completo (HTML+CSS+JS inline)
│   └── assets/Logo.png            # Logo ArcanLab
│
├── tests/dashboard/               # Testes do dashboard (mock do Gateway + Playwright)
├── docs/
│   ├── DASHBOARD_AGENTE03.md      # Dashboard v5.1: contrato, estados e testes
│   ├── DECISOES_ARQUITETURAIS.md  # 14 ADRs (inclui históricos pré-v4)
│   ├── GLOSSARIO.md               # Glossário de termos do projeto
│   └── SYSTEM_OVERVIEW.md         # Este documento
│
├── registry.json                  # Estado operacional dos subagentes
├── go.mod / go.sum                # Dependências Go
├── PROTOCOLO.md                   # Especificação do protocolo v4.1
├── ROADMAP.md                     # Plano de evolução
├── README.md                      # Documentação principal
├── AGENTS.md                      # Instruções para agentes de IA
├── .gitignore
└── pkg/                           # [POSTERGADO] Identidade visual para futuro site
```

---

## 9. Agentes registrados

### Agente 01 — esp32-01 (Protótipo LED)

- **Tipo:** `led`
- **Capabilities:** `LED_ON`, `LED_OFF`
- **Firmware:** commitado (`agents/esp32/esp32_agent.ino.ino`)
- **Status:** produção (demonstrado em operação)

### Agente 02 — esp32-02 (Polias Industriais)

- **Tipo:** `industrial`
- **Capabilities:** `LIGAR`, `ELEVACAO_A`, `ELEVACAO_B`, `DESLIGAR`
- **Firmware:** base semelhante ao Agente 01 com comandos específicos; **não commitado** no repositório (limitação de rastreabilidade conhecida)
- **Status:** produção (demonstrado em operação)

### Agente 03 — esp32-03 (Bancada de sensores e motor de passo)

- **Tipo:** `sensor`
- **Capabilities:** `LER_SENSORES`, `TEMPERATURA`, `PRESSAO`, `ALTITUDE`, `CORRENTE`, `DISTANCIA`, `START`, `PARE`, `MOVER`
- **Firmware:** commitado (`agents/esp32/agente03/agente03.ino`, v4.4)
- **Dashboard:** `web/dashboard/index.html` (v5.1) é dedicado a este agente
- **Status:** em desenvolvimento ativo. Seu `last_ip` precisa ser preenchido no `registry.json` (IP exibido no Serial Monitor do ESP) para o Wake funcionar.

---

## 10. Versões e evolução histórica

| Versão | Data | Descrição |
|:---|:---|:---|
| v1.0 | 2026-07 | Conceito inicial, estrutura base |
| v2.0 | 2026-07 | Gateway + cliente Go em terminal |
| v3.0 | 2026-08 | Primeira versão com ESP32 físico |
| v3.1 | 2026-08 | Agente autônomo com heartbeat e reconexão (obsoleto) |
| **v4.0** | **2026-08** | **Subagente Passivo + Pico de Conexão — arquitetura atual** |

A migração de v3 para v4 foi uma mudança fundamental de arquitetura: de "agente autônomo com heartbeat" para "subagente passivo convocado via UDP". O heartbeat e a reconexão automática foram eliminados.

### Componentes históricos

- **`cmd/client/main.go`** — Cliente Go da era v3. Referencia tipos (`protocol.TypeHeartbeat`, `protocol.Heartbeat`) que não existem mais no protocolo V4. Não compila. Mantido intencionalmente como referência histórica.

### Branches

| Branch | Descrição |
|:---|:---|
| `migracao-v4` | Branch de trabalho principal (V4) |
| `main` | Existe, relação com v4 a confirmar |
| `develop` | Existe, relação com v4 a confirmar |

---

## 11. Decisões arquiteturais importantes

Os ADRs completos estão em `docs/DECISOES_ARQUITETURAIS.md`. As decisões mais relevantes para a arquitetura V4:

### Vigentes na V4

| ADR | Decisão | Relevância |
|:---|:---|:---|
| ADR-001 | Arquitetura baseada em agentes | Princípio fundamental |
| ADR-003 | Comunicação via WebSocket | Transporte principal |
| ADR-004 | JSON como formato de mensagens | Legibilidade e debug |
| ADR-005 | Session encapsula a conexão WS | Desacoplamento Handler/Controller |
| ADR-006 | Session Manager centralizado | Gerenciamento de sessões |
| ADR-008 | Arquitetura Semi-Offline | Funciona sem Internet |
| ADR-009 | Gateway único por infraestrutura | Simplicidade |
| ADR-010 | Go como linguagem principal | Desempenho e portabilidade |
| ADR-011 | API REST | Integração com dashboard e scripts |
| ADR-012 | Open Source | Transparência e colaboração |

### Históricos (pré-v4, substituídos)

| ADR | Decisão original | Situação na V4 |
|:---|:---|:---|
| ADR-002 | "O Agent inicia a conexão" | Na V4 o Gateway convoca via UDP; o ESP conecta apenas quando convocado |
| ADR-007 | "Heartbeat periódico" | Eliminado na V4; não existe heartbeat no protocolo atual |

Esses dois ADRs estão marcados como **substituídos na v4** em `docs/DECISOES_ARQUITETURAIS.md` e permanecem lá apenas como registro histórico.

### Acoplamento via globais de pacote

Os subsistemas se comunicam via variáveis globais: `registry.DefaultRegistry`, `wake.DefaultSender`, `controller.DefaultController`, `session.EphemeralStore`. Não há injeção de dependência. Adequado para o estágio atual (MVP), mas limitante para testes unitários e múltiplas instâncias.

---

## 12. Limitações e lacunas conhecidas

### Limitações técnicas

**Resolvidas na v4.1**

- **JSON SSE via `fmt.Sprintf`** — os eventos SSE agora são montados por `emit()` com `json.Marshal`; aspas, quebras de linha e barras no stdout/stderr não quebram mais o JSON.
- **Timeouts e retries divergentes entre especificação e código** — `PROTOCOLO.md` foi alinhado ao código: 5 tentativas (0, 1, 2, 4 e 8 s), autenticação 8 s no ESP e 10 s no Gateway, resultado 15 s.

**Abertas**

1. **API e dashboard sem autenticação** — qualquer dispositivo na rede local pode enviar comandos, inclusive `MOVER`. É a lacuna de segurança mais importante.

2. **Sem criptografia de transporte** — API/dashboard em HTTP, WebSocket em `ws://` e Wake em UDP sem cifra. A segurança depende de a rede local ser confiável. Secrets reais não devem ser versionadas: o `registry.json` é local e o repositório fornece somente `configs/registry.example.json`.

3. **MAC do Wake não cobre o `session_id`** — o MAC é HMAC(challenge + agent_id). O ESP guarda apenas as últimas 4 sessões usadas e zera esse cache a cada 4 operações, então um pacote Wake capturado pode ser aceito de novo e fazer o ESP conectar sem necessidade. O Gateway só aceita WebSocket de sessão pendente, logo isso não executa comandos, mas pode acordar o agente indevidamente.

4. **Escritas sem trava em `Operation`** — `Result`, `Error`, `SessionID`, `Challenge` e `Retries` são escritos pelo Controller sem lock, enquanto `GetOperation` devolve o ponteiro que a API serializa. Há risco de data race; verificar com `go test -race` quando houver testes.

5. **Ausência de testes automatizados do Gateway** — não há testes unitários em Go, CI ou linter. O dashboard tem suíte própria em `tests/dashboard/` (ver `docs/DASHBOARD_AGENTE03.md`). O Controller (retry, estados, concorrência) é a parte que mais precisa de testes.

6. **Erros silenciosos** — falhas em `protocol.Encode(welcome)`, `base64.StdEncoding.DecodeString()` e `registry.Save()` são descartadas sem log.

7. **Registry mistura configuração e estado, e `InitRegistry()` hardcoda esp32-01 e esp32-02** — `registry.json` guarda tanto secrets e capabilities quanto `status`, `last_seen` e `last_ip`. A cada startup, esp32-01 e esp32-02 são sobrescritos com valores fixos, revertendo edições manuais. O esp32-03 não é afetado.

8. **`GenerateSecret()` usa pseudo-random fixo** — não é chamada em produção, mas produziria secrets previsíveis se usada.

9. **Portas hardcoded** — HTTP/WS 18080 e UDP 18081 são constantes no código. As variáveis `TUNNEUS_*` do README não estão implementadas.

10. **Duração da sessão** — o README diz que a conexão dura menos de 2 s. No firmware, depois do resultado a sessão pode permanecer até 7 s no pior caso (ACK 5 s + DISCONNECTING 2 s). O modelo "um pico de conexão por comando" não serve para controle em tempo real; é adequado a leituras e movimentos programados. Medir o tempo real e corrigir o texto do README.

11. **Firmware: heap e bloqueios** — o cliente WebSocket é destruído e recriado a cada operação, o que pode fragmentar o heap em operação longa (o firmware já imprime a fragmentação). `delay()` e `pulseIn()` (até 30 ms) bloqueiam o loop, e a leitura periódica dos sensores pode causar uma pausa nos pulsos do motor durante um movimento.

### Lacunas de documentação/rastreabilidade

1. **Firmware do Agente 02 não commitado** — Existe, mas não está no repositório.
2. **Versão inconsistente** — `main.go` diz "v0.1", `server.go` diz "v4.0", `health.go` diz "0.1.0", README diz "v1.0.0", Dashboard diz "v5.1", Firmware do Agente 01 diz "v4.3-MARATHON" e o do Agente 03 "v4.4". Não há constante centralizada.
3. **Arquivo com extensão dupla** — `esp32_agent.ino.ino`.

---

## 13. Direção futura

O roadmap completo está em `ROADMAP.md`. Resumo das direções planejadas:

### Próximo (v1.1.0)

- Descoberta automática de agentes via UDP broadcast.
- Múltiplos comandos por sessão (batch).
- Dashboard melhorado (multi-agente).
- Métricas e telemetria.
- Testes unitários.
- Configuração via YAML/ENV.

### Longo prazo (v2.0.0)

- MQTT como transporte alternativo.
- Agente Linux (Go) para Raspberry Pi.
- TLS/SSL, rotação de secrets, autenticação do dashboard.
- Integrações ArcanLab (Storage, AI).

### Visão de longo prazo

Existe uma direção de pesquisa envolvendo múltiplos agentes científicos, diferentes experimentos, comunicação entre agentes, infraestrutura ArcanLab e possível servidor na escola. **Essa arquitetura futura ainda não está completamente definida.** Não deve ser tratada como funcionalidade existente ou planejada para implementação imediata.

### Ideias em pesquisa

Mesh networking, OTA updates, deep sleep, protocolo binário (protobuf/msgpack).

> Versões e melhorias serão desenvolvidas e validadas sem pressão de prazo artificial. As datas no roadmap representam o planejamento original.

---

## 14. Como começar a trabalhar no sistema

### Para desenvolvedores

1. **Leia primeiro:** este documento, `README.md`, `PROTOCOLO.md` e `ROADMAP.md`.
2. **Entenda o fluxo:** REST POST → Controller → UDP Wake → ESP conecta WS → Hello auth → Command → Result → Bye → cleanup.
3. **Build:** `go build -o tunneus-gateway ./cmd/gateway` (não use `go build ./...`).
4. **Vet:** `go vet ./cmd/gateway ./internal/...`
5. **Execute da raiz do repo:** o binário lê `registry.json` e serve `web/dashboard/` com caminhos relativos.
6. **Documentação adicional:** ADRs em `docs/DECISOES_ARQUITETURAIS.md`, glossário em `docs/GLOSSARIO.md`.

### Para agentes de IA

1. **Leia `AGENTS.md`** — contém instruções operacionais específicas (build, hardcoded behavior, protocol changes, flow map, conventions).
2. **Código-fonte em português** — docs, comentários, logs e commits são em português.
3. **Não compile `cmd/client/`** — é legado v3 e não compila.
4. **`registry.json` é sobrescrito parcialmente no startup** — esp32-01 e esp32-02 são hardcoded em `InitRegistry()`.
5. **HMAC secrets:** base64 no `registry.json`, hex no firmware. Mesmos bytes raw.
6. **Mensagens do protocolo** vivem em `internal/protocol/*.go` e devem estar em sincronia com `PROTOCOLO.md` e o firmware Arduino. Renomear campos JSON quebra dispositivos implantados.
7. **Processo de desenvolvimento:** compreender → analisar → documentar → planejar → implementar → testar → revisar → validar → documentar.

---

## 15. Documentos relacionados

| Documento | Propósito |
|:---|:---|
| `README.md` | Documentação principal do projeto |
| `PROTOCOLO.md` | Especificação técnica do protocolo v4.1 |
| `ROADMAP.md` | Plano de evolução e filosofia de desenvolvimento |
| `AGENTS.md` | Instruções operacionais para agentes de IA |
| `docs/DECISOES_ARQUITETURAIS.md` | Registro de decisões arquiteturais (ADRs) |
| `docs/GLOSSARIO.md` | Glossário de termos |
| `agents/esp32/README.md` | Instruções de configuração do firmware |

---

<p align="center">
  <sub>ArcanLab — Tunneus Gateway — Documento gerado em setembro de 2026</sub>
</p>
