[← Índice da documentação](README.md)

# Apêndice C. Glossário técnico

**Tabela 27 — Termos utilizados na arquitetura**

| Termo                  | Significado no Tunneus                                                       |
|------------------------|------------------------------------------------------------------------------|
| Agente                 | Dispositivo cadastrado que executa capabilities por meio de seu firmware.    |
| `agent_id`             | Identidade estável usada para selecionar configuração, secret e dispositivo. |
| API REST               | Interface HTTP para listar agentes, criar comandos e consultar operações.    |
| Backoff                | Espera crescente entre tentativas de uma mesma operação.                     |
| Capability             | Nome público de uma ação autorizada e implementada pelo agente.              |
| Challenge              | Desafio aleatório criado por tentativa e usado nas provas HMAC.              |
| Command                | Mensagem que solicita uma capability e pode carregar argumentos.             |
| Controller             | Módulo que coordena operação, sessões, retries, Result e eventos.            |
| Dashboard              | SPA que apresenta o experimento e envia intenções ao Gateway.                |
| Ephemeral Store        | Gerenciador das sessões temporárias e de seus canais.                        |
| Gateway                | Núcleo de orquestração entre clientes e agentes.                             |
| Goroutine              | Fluxo concorrente Go no qual a operação prossegue após o HTTP 202.           |
| Hello                  | Primeira mensagem do agente no WebSocket, com resposta ao challenge.         |
| HMAC-SHA256            | Código de autenticação calculado com secret e mensagem.                      |
| HTTP 202               | Aceite da intenção; não representa execução concluída.                       |
| Idempotência           | Propriedade de uma repetição não acrescentar novo efeito a cada execução.    |
| Mock Gateway           | Simulador das rotas e eventos usado na verificação do dashboard.             |
| `op_id`                | Identificador da intenção lógica, preservado entre retries.                  |
| Pico de Conexão        | Intervalo em que o WebSocket é aberto, usado e encerrado.                    |
| Registry               | Cadastro de identidade, capabilities, secret e endereço dos agentes.         |
| Result                 | Mensagem com `stdout` e `stderr` associada ao command_id.                    |
| Retry                  | Nova tentativa da mesma operação, com nova sessão e challenge.               |
| SSE                    | Server-Sent Events; stream unidirectional do Gateway para o navegador.       |
| `session_id`           | Identificador de uma tentativa de conexão.                                   |
| STANDBY                | Repouso lógico com UDP aberto e WebSocket fechado.                           |
| Subagente Passivo      | Agente que aguarda Wake antes de abrir a conexão WebSocket.                  |
| Telemetria sob demanda | Aquisição entregue ao cliente somente após uma capability de leitura.        |
| TTL                    | Tempo máximo de vida usado na limpeza de sessões.                            |
| Wake                   | Datagrama UDP autenticado que convoca o agente.                              |
| WebSocket              | Canal bidirecional temporário para Hello, Welcome, Command, Result e Bye.    |
---

[Voltar ao índice da documentação](README.md)
