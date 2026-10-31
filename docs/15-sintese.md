# Síntese

O Tunneus organiza a operação de dispositivos ESP32 em uma arquitetura local composta por dashboard, Gateway, protocolo e agentes.

O modelo **Subagente Passivo + Pico de Conexão** mantém o WebSocket fechado em espera. Um Wake UDP autenticado inicia a sessão; o Hello comprova a posse da secret; o Command solicita a ação; o Result devolve a saída; o Bye encerra a conexão.

A API é assíncrona: HTTP 202 indica aceite, e SSE informa o desfecho. `op_id`, `session_id` e `command_id` cumprem papéis distintos. Retries renovam a sessão, e `MOVER` recebe tratamento especial por não ser idempotente.

No Agente 03, sensores e motor transformam o protocolo em uma bancada de experimentação. A telemetria chega por Result e é apresentada em gráficos SVG locais, sem streaming contínuo ou persistência após recarregar.

O projeto central é o Tunneus. Protótipos e bancadas servem à experimentação e aos testes. Registros históricos do caderno vêm da bancada real; valores do mock são sintéticos.

O acesso remoto via Tailscale já existe e precisa de otimização. A operação local não depende de Internet, mas depende de energia, rede local e configuração correta.

O repositório é expositivo, privado e destinado a professores e colaboradores autorizados. Não representa uma distribuição open source nem substitui validações formais de hardware.
