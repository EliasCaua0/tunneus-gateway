# Glossário de Termos

| Termo | Definição |
|---|---|
| **Subagente Passivo** | Modelo onde o agente permanece em standby até receber um Wake |
| **Pico de Conexão** | Padrão de conexão temporária: conecta → executa → desconecta |
| **Wake** | Pacote UDP enviado pelo Gateway para acordar um agente |
| **Hello** | Primeira mensagem WebSocket do agente, com autenticação |
| **Challenge** | Valor aleatório usado para autenticação HMAC |
| **HMAC** | Hash-based Message Authentication Code |
| **Session** | Contexto temporário de uma operação Gateway↔Agente |
| **Registry** | Cadastro persistente de agentes com suas capabilities |
| **Capability** | Comando que um agente suporta (ex: LED, RELAY) |
| **Operation** | Comando em execução com seu estado e resultado |
| **SSE** | Server-Sent Events — push HTTP unidirecional |
| **Backoff** | Espera crescente entre tentativas de retry |
| **TTL** | Time To Live — tempo de expiração de uma sessão |
| **STANDBY** | Estado do agente aguardando Wake |
| **CONNECTING** | Estado durante handshake WebSocket |
| **ACTIVE** | Estado executando comando |
| **Bye** | Mensagem de encerramento de sessão |
| **Telemetry** | Telemetria: coleta de métricas dos agentes |
| **Jitter** | Variação aleatória no tempo de backoff |
| **Dead Connection** | Conexão TCP/WebSocket que parece ativa mas não responde |
| **Tailscale** | Rede privada usada como camada complementar de acesso remoto, já funcional e em otimização |
| **Mock Gateway** | Servidor de teste que produz dados sintéticos para o dashboard |
| **Bancada real** | Montagem física usada nos registros históricos e ensaios do projeto |
| **Telemetria sob demanda** | Leituras geradas por comandos, não por streaming contínuo |
| **Watchdog visual** | Indicação de operação antiga no dashboard, sem cancelamento físico |
| **Malha aberta** | Controle sem realimentação da posição ou do resultado físico |
| **Repositório expositivo** | Material privado de apresentação, sem licença open source concedida |
