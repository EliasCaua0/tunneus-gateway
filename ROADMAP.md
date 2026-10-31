# ROADMAP.md

> Plano de desenvolvimento do Tunneus Gateway

---

## Fase atual de desenvolvimento

O ArcanLab está em uma fase de **desenvolvimento contínuo, cuidadoso e orientado à qualidade**.

O projeto não está mais condicionado por prazos de apresentação. A prioridade é construir uma base sólida, sustentável e bem fundamentada. Quando aplicável, alterações relevantes devem seguir o processo:

**Compreender → Analisar → Documentar → Planejar → Implementar → Testar → Revisar → Validar → Documentar novamente**

A ordem e o momento de execução das melhorias serão definidos com base em justificativa, impacto, dependências e validação. As previsões de versões e datas registradas neste documento representam o planejamento original; não constituem prazos rígidos para a fase atual.

---

## ✅ v1.0.0 — Subagente Passivo + Pico de Conexão (base atual)

**Data:** 2026-08-15

> Contexto histórico: esta versão foi desenvolvida e estabilizada para demonstração em uma feira científica do IFSul. A pressão desse prazo moldou decisões pragmáticas que serviram ao objetivo da época. O desenvolvimento posterior segue a filosofia descrita acima.

### O que foi entregue

- [x] Arquitetura Subagente Passivo (ESP fica em STANDBY, só conecta quando convocado)
- [x] Protocolo v4.0 com 6 tipos de mensagem (wake, hello, welcome, command, result, bye)
- [x] Autenticação HMAC-SHA256 challenge-response
- [x] Gateway orquestrador assíncrono com retry e backoff exponencial
- [x] Sessões efêmeras com TTL automático
- [x] Dashboard SPA com SSE em tempo real
- [x] Registry persistente em JSON
- [x] Firmware ESP32 estável (watchdog, reconexão WiFi, cleanup robusto)
- [x] Suporte a múltiplos agentes

### Estabilidade

- [x] Testado por 30+ minutos sem falhas
- [x] 3 protótipos configurados para feira científica
- [x] Memory leak corrigido (ESP + Gateway)
- [x] Socket UDP recriado do zero a cada ciclo

---

## 🚧 v1.1.0 — Melhorias de UX e Descoberta

> As funcionalidades abaixo permanecem como direção planejada. A priorização e a implementação serão avaliadas gradualmente, com planejamento, testes e validação compatíveis com a fase atual de desenvolvimento.

### Features

- [ ] **Descoberta automática** de agentes via UDP broadcast
  - O Gateway envia broadcast na rede local
  - Agentes respondem com seu agent_id e capabilities
  - Elimina necessidade de configurar IP manualmente no Registry

- [ ] **Múltiplos comandos por sessão** (batch)
  - Permitir enviar 2+ comandos em uma única sessão WS
  - Reduz overhead de abrir/fechar conexão

- [ ] **Dashboard melhorado**
  - Gráfico de operações ao longo do tempo
  - Status de múltiplos agentes simultâneos
  - Controles por agente (não apenas um)

- [ ] **Métricas e telemetria**
  - Tempo médio de resposta por agente
  - Taxa de sucesso/falha
  - RSSI do WiFi do ESP

### Refatorações

- [ ] Extrair configuração para arquivo YAML/ENV
- [ ] Adicionar testes unitários (Go)
- [ ] Documentação de API OpenAPI/Swagger

---

## 🔮 v2.0.0 — Ecossistema ArcanLab

> A visão desta versão orienta pesquisa e planejamento de longo prazo. Não representa arquitetura definitiva nem funcionalidades já definidas para implementação.

### Novos transportes

- [ ] **MQTT** como transporte alternativo ao WebSocket
  - Para cenários com broker MQTT existente
  - Retenção de mensagens para offline

- [ ] **Agente Linux** (Raspberry Pi, etc.)
  - Subagente escrito em Go
  - Mesmo protocolo, plataforma diferente

### Integrações

- [ ] **ArcanLab Storage**
  - Persistência de resultados de comandos
  - Histórico de operações por agente

- [ ] **ArcanLab AI**
  - Análise de padrões de uso
  - Predição de falhas

### Segurança

- [ ] **TLS/SSL** no WebSocket (`wss://`)
- [ ] **Rotação de secrets** automática
- [ ] **Autenticação de dashboard** (OAuth2/JWT)

---

## 🧪 Ideias em pesquisa

| Ideia | Status | Descrição |
|:---|:---|:---|
| Mesh networking | 🔍 Explorando | ESPs se comunicam entre si sem Gateway |
| OTA updates | 🔍 Explorando | Atualização de firmware via Gateway |
| Modo sleep profundo | 🔍 Explorando | ESP dorme entre comandos (economia de energia) |
| Protocolo binário | 🔍 Explorando | Substituir JSON por protobuf/msgpack |

---

## 📅 Histórico e direção

```
2026-07 ──► v1.0 conceito
2026-08 ──► v1.0.0 estável (demonstração em feira científica)
2026-09 ──► v1.1.0 descoberta automática (planejamento original)
2026-10 ──► v1.1.x estabilidade (planejamento original)
2027-Q1 ──► v2.0.0 ecossistema ArcanLab (planejamento original)
```

> O cronograma acima preserva o planejamento original. Na fase atual, versões e melhorias serão desenvolvidas e validadas sem pressão de prazo artificial.

---

<p align="center">
  <sub>🦉 Tunneus Connect — ArcanLab 2026</sub>
</p>
