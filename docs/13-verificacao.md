# Verificação e evidências

O repositório combina testes de software, demonstrações com mock e registros de bancada real. Cada evidência responde a uma pergunta diferente.

## 1. Verificação controlada do dashboard

Na verificação documentada das cinco grandezas, foram registradas **109 de 109 verificações aprovadas**. Esse número pertence ao roteiro controlado de dashboard e telemetria.

Ele não significa que toda a suíte histórica foi aprovada integralmente.

## 2. Suíte histórica

`tests/dashboard/test_dashboard.py` contém expectativas de versões anteriores, incluindo um cartão de fluxo que não existe no dashboard v5.1.

Não se deve alterar o projeto apenas para produzir aprovação. O resultado precisa ser lido com a versão da interface e o escopo do teste.

## 3. Mock

O mock permite verificar:

- navegação;
- envio de comandos;
- recepção SSE;
- parser;
- gráficos;
- limites de retenção.

Ele não verifica sensores, GPIO, motor, Wi-Fi de ESP32 ou Wake UDP físico.

## 4. Bancada real

Os registros históricos do caderno são dados da bancada real. Eles documentam a evolução até a primeira versão estável apresentada em feira.

Uma demonstração física não equivale automaticamente a ensaio de certificação elétrica, metrológica ou mecânica.

## 5. Matriz de evidências

| Afirmação | Evidência adequada |
|---|---|
| Parser e gráficos funcionam | Mock + verificações do dashboard |
| Agente executa comando físico | Bancada com hardware |
| Protocolo está especificado | PROTOCOLO.md + código |
| Operação local dispensa Internet | Arquitetura e ensaio controlado de WAN |
| Motor atingiu posição | Sensor de posição; ausente no firmware atual |

## 6. Reprodutibilidade

Antes de uma demonstração, registrar versões, origem dos dados, configuração de rede e se o Gateway é real ou mock. Nunca apresentar valores sintéticos como medições físicas.
