# ROADMAP.md — Tunneus Gateway

## v4.0 — Subagente Passivo + Pico de Conexão
- [x] UDP Wake com HMAC-SHA256
- [x] WebSocket com autenticação por challenge-response
- [x] Session Store com TTL
- [x] Controller com retry exponencial
- [x] Registry persistente de agentes
- [x] API REST + SSE
- [x] Dashboard web em tempo real
- [x] Firmware ESP32 de referência

## v4.1 — Documentação e apresentação
- [x] PROTOCOLO.md revisado
- [x] Documentação didática da arquitetura
- [x] Explicação ponta a ponta
- [x] Segredos sanitizados nos exemplos
- [x] Dashboard v5.1 com Bancada do Agente 03
- [x] Telemetria local e gráficos SVG
- [x] Mock Gateway para demonstrações

## v4.2 — Próximos passos técnicos
- [ ] Otimizar o acesso remoto via Tailscale já existente
- [ ] TLS no WebSocket (WSS)
- [ ] mTLS entre Gateway e agentes
- [ ] Descoberta automática via mDNS
- [ ] OTA updates para firmware
- [ ] Persistência de telemetria com política de retenção
- [ ] Métricas Prometheus
- [ ] Testes de integração automatizados
- [ ] Docker Compose para deploy
- [ ] Suporte a ESP32-S3 e ESP32-C6

## v5.0 — Visão futura
- [ ] Múltiplos gateways com failover
- [ ] RBAC no dashboard
- [ ] Audit log
- [ ] Plugin system para comandos customizados
- [ ] gRPC para comunicação inter-gateway
- [ ] App mobile

## Reavaliações de projeto
- Tornar o acesso remoto mais robusto e simples de operar.
- Rever `MOVER` para representar início, conclusão e parada física.
- Acrescentar realimentação de posição quando houver requisito mecânico.
- Revisitar timeouts e o watchdog visual de 150 s com ensaios.
- Alinhar testes históricos ao dashboard v5.1 sem apagar expectativas antigas.
- Definir o licenciamento futuro somente após decisão dos titulares.

Este roadmap registra intenções, não funcionalidades já entregues.
