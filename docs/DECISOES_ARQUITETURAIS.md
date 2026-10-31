# Decisões Arquiteturais — Tunneus Gateway

Este documento registra as decisões arquiteturais (ADRs) do projeto Tunneus.

---

## ADR-001: Modelo Subagente Passivo + Pico de Conexão

**Data:** 2026-02-16
**Status:** Aceito

### Contexto
Precisamos controlar dispositivos ESP32 em rede local com baixo consumo de recursos e sem manter conexões persistentes.

### Decisão
Adotar o modelo "Subagente Passivo": o agente fica em standby (UDP aberto) e só abre WebSocket quando recebe um Wake válido. Após executar o comando, envia Bye e fecha a conexão.

### Alternativas Consideradas
1. **WebSocket persistente**: Agentes mantêm conexão aberta
2. **MQTT**: Broker centraliza comunicação
3. **CoAP**: Protocolo leve para IoT
4. **HTTP polling**: Agentes consultam Gateway periodicamente

### Consequências
- ✅ Baixo consumo de recursos no ESP32
- ✅ Sem necessidade de broker externo
- ✅ Funciona offline na rede local
- ⚠️ Latência adicional para acordar agente
- ⚠️ Wake UDP pode ser perdido (mitigado com retry)

---

## ADR-002: Autenticação HMAC-SHA256

**Data:** 2026-02-16
**Status:** Aceito

### Contexto
Precisamos autenticar agentes sem depender de infraestrutura de certificados (PKI).

### Decisão
Usar HMAC-SHA256 com secret compartilhada por agente. O Gateway envia um challenge no Wake e o agente responde com HMAC no Hello.

### Alternativas Consideradas
1. **mTLS**: Certificados cliente/servidor
2. **Tokens JWT**: Tokens assinados
3. **Senha simples**: Autenticação básica

### Consequências
- ✅ Simples de implementar
- ✅ Sem dependência externa
- ✅ Timing-safe comparison
- ⚠️ Gerenciamento manual de secrets
- ⚠️ Sem revogação automática

---

## ADR-003: Comunicação Híbrida UDP + WebSocket

**Data:** 2026-02-16
**Status:** Aceito

### Contexto
UDP é ideal para wake (fire-and-forget), mas não garante entrega. WebSocket oferece canal confiável bidirecional.

### Decisão
Usar UDP apenas para Wake e WebSocket para toda comunicação subsequente (Hello, Command, Result, Bye).

### Consequências
- ✅ Wake é leve e rápido
- ✅ WebSocket garante entrega ordenada
- ✅ Separação clara de responsabilidades
- ⚠️ Dois protocolos para manter

---

## ADR-004: Retry com Backoff Exponencial

**Data:** 2026-02-16
**Status:** Aceito

### Decisão
Implementar retry com backoff exponencial (1s, 2s, 4s, 8s, 16s) e jitter de ±20%.

### Consequências
- ✅ Tolera falhas transitórias de rede
- ✅ Evita tempestade de retries
- ⚠️ Latência máxima de ~31s em caso de falha total

---

## ADR-005: Registry em JSON (sem banco de dados)

**Data:** 2026-02-16
**Status:** Aceito

### Decisão
Usar arquivo JSON para persistir o registry de agentes, com escrita atômica (tmp + rename).

### Alternativas Consideradas
1. **SQLite**: Banco embarcado
2. **PostgreSQL**: Banco relacional
3. **etcd**: Distributed KV store

### Consequências
- ✅ Zero dependências externas
- ✅ Funciona offline
- ✅ Fácil backup e inspeção
- ⚠️ Não escala para milhares de agentes
- ⚠️ Sem queries complexas

---

## ADR-006: Dashboard Server-Sent Events (SSE)

**Data:** 2026-02-16
**Status:** Aceito

### Decisão
Usar SSE para push de eventos do Gateway ao dashboard, em vez de WebSocket bidirecional.

### Alternativas Consideradas
1. **WebSocket**: Bidirecional
2. **Long polling**: HTTP polling

### Consequências
- ✅ Mais simples que WebSocket
- ✅ Funciona através de proxies HTTP
- ✅ Reconexão automática pelo browser
- ⚠️ Unidirecional (server → client)

---

## ADR-007: Go como linguagem do Gateway

**Data:** 2026-02-16
**Status:** Aceito

### Decisão
Usar Go para o Gateway devido a: goroutines para concorrência, binário único, excelente suporte a rede, e gorilla/websocket maduro.

### Consequências
- ✅ Deploy simples (binário único)
- ✅ Concorrência nativa
- ✅ Cross-compilation fácil
- ⚠️ Curva de aprendizado para quem vem de outras linguagens

---

## ADR-008: Protocolo JSON (não binário)

**Data:** 2026-02-16
**Status:** Aceito

### Decisão
Usar JSON para todas as mensagens do protocolo.

### Alternativas Consideradas
1. **Protocol Buffers**: Binário, tipado
2. **MessagePack**: Binário, compacto
3. **CBOR**: Binário, IoT-friendly

### Consequências
- ✅ Legível e debugável
- ✅ Fácil de implementar em qualquer linguagem
- ⚠️ Maior overhead de bytes
- ⚠️ Parsing mais lento que binário

---

## ADR-009: Telemetria sob demanda e parser textual

**Data:** 2026-10-28
**Status:** Aceito

### Contexto
A Bancada do Agente 03 precisa apresentar grandezas sem manter streaming contínuo nem adicionar um banco de dados ao protótipo.

### Decisão
Transportar leituras em `Result.stdout`, publicar o Result por SSE e interpretar os formatos textuais no dashboard. As séries permanecem na memória do navegador, com limite de 1.000 amostras e janela de 24 horas.

### Alternativas consideradas
1. Streaming contínuo por WebSocket do navegador.
2. Payload JSON específico para cada grandeza.
3. Persistência imediata em banco de séries temporais.

### Consequências
- ✅ Reutiliza o ciclo de comando e o SSE já existentes.
- ✅ Não exige biblioteca de gráficos ou serviço externo.
- ✅ A deduplicação por `op_id + grandeza` evita pontos repetidos.
- ⚠️ O parser depende do formato textual do firmware.
- ⚠️ O timestamp representa o recebimento no navegador.
- ⚠️ Recarregar a página elimina o histórico local.

---

## ADR-010: Dashboard sem framework e sem CDN

**Data:** 2026-10-28
**Status:** Aceito

### Decisão
Manter o dashboard v5.1 em HTML, CSS e JavaScript puro, desenhar gráficos em SVG e incorporar os arquivos ao binário Go.

### Consequências
- ✅ Funciona sem Internet e sem etapa de build.
- ✅ Reduz a cadeia de dependências e facilita auditoria.
- ✅ Gateway e interface podem ser executados como um único serviço local.
- ⚠️ O arquivo único concentra apresentação e lógica.
- ⚠️ Escalas, parser e componentes visuais exigem implementação própria.

---

## ADR-011: Tratamento de `MOVER` como comando não idempotente

**Data:** 2026-10-28
**Status:** Aceito

### Contexto
A perda do Result de um movimento não comprova que o hardware não recebeu o comando. Reenviar `MOVER` poderia produzir deslocamento adicional.

### Decisão
Após `command_sent`, não reenviar automaticamente `MOVER` apenas porque o Result não chegou. O Result desse comando representa início da geração de pulsos, não conclusão física.

### Consequências
- ✅ Evita duplicar um movimento cuja recepção é incerta.
- ✅ Torna explícita a diferença entre estado de rede e estado físico.
- ⚠️ Uma operação pode ficar sem confirmação mesmo com movimento em andamento.
- ⚠️ A determinação da posição final exige realimentação adicional, ausente no firmware atual.

---

## ADR-012: Licença MIT

**Data:** 2026-02-16
**Status:** Aceito

### Decisão
O Tunneus será desenvolvido como software livre.

### Consequências
- ✅ Comunidade pode contribuir
- ✅ Transparência total
- ✅ Adoção facilitada

---

*Documento gerado em 2026-02-16 pelo ArcanLab Methodology (Fase 3: Extração).*
