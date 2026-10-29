[← Índice da documentação](README.md)

# 14. Escopo atual e evolução do projeto

> **Neste capítulo:** A versão atual é delimitada como uma arquitetura
> funcional de laboratório. As expansões são organizadas a partir das
> camadas já existentes, preservando o núcleo comum.

## 14.1 O que a arquitetura já estabelece

O projeto estabelece um ciclo completo e reutilizável: identidade do
agente, autorização por capability, operação assíncrona, convocação,
autenticação mútua por desafio, sessão temporária, resultado e
apresentação. Sensores e atuadores entram nesse ciclo por meio do
firmware, sem alterar os contratos centrais.

**Tabela 23 — Escopo funcional da versão apresentada**

| Dimensão     | Forma atual                                       | Consequência arquitetural                              |
|--------------|---------------------------------------------------|--------------------------------------------------------|
| Comunicação  | Rede local, HTTP, SSE, UDP e WebSocket.           | Operação autônoma sem Internet.                        |
| Dispositivos | Gateway multiagente e dashboard especializado.    | Núcleo comum com apresentação dedicada à bancada.      |
| Aquisição    | Cache local e leituras sob demanda.               | Sem streaming contínuo para o Gateway.                 |
| Histórico    | Memória do navegador, até 1000 pontos e 24 h.     | Visualização da sessão, sem banco de séries temporais. |
| Movimento    | Pulsos programados, sem realimentação de posição. | Result confirma início; conclusão permanece local.     |
| Operação     | Sessões e operações efêmeras.                     | Reinício do processo não preserva o histórico.         |

## 14.2 Expansões organizadas por camada

A separação entre núcleo, protocolo, firmware e apresentação oferece
pontos claros de evolução. Novas funções podem ser incorporadas sem
abandonar o modelo de convocação e operação local.

**Tabela 24 — Direções de evolução registradas para o ecossistema**

| Camada       | Possível evolução                                                  | Contribuição                                              |
|--------------|--------------------------------------------------------------------|-----------------------------------------------------------|
| Telemetria   | Dados estruturados, timestamp do dispositivo, latência e métricas. | Histórico mais rico e comparação entre experimentos.      |
| Bancada      | Novas grandezas, conclusão do movimento e leitura de posição.      | Mais formas de aquisição e realimentação física.          |
| Multiagente  | Seleção de dispositivos e composição por capabilities.             | Vários experimentos apresentados sobre o mesmo núcleo.    |
| Comunicação  | Descoberta UDP, comandos em batch e integração MQTT.               | Configuração simplificada e integração externa.           |
| Persistência | Histórico de operações e séries temporais.                         | Consulta posterior e acompanhamento de longa duração.     |
| Pesquisa     | OTA, deep sleep, mesh e protocolos binários.                       | Novos compromissos entre energia, desempenho e autonomia. |

## 14.3 Como um novo experimento se encaixa

1.  **Definir a capability.** Escolher um nome público e o significado
    físico da ação.
2.  **Cadastrar o agente.** Criar identidade, secret, endereço e lista
    de capabilities no Registry.
3.  **Implementar o firmware.** Reutilizar a máquina de estados e
    acrescentar a lógica local do hardware.
4.  **Definir o contrato de resultado.** Estabelecer texto, unidade e
    condições de erro compreensíveis pelo cliente.
5.  **Adaptar a apresentação.** Criar controles e visualizações sem
    transferir regras físicas para o Gateway.
6.  **Verificar por camadas.** Exercitar contrato, comunicação,
    interface e bancada com evidências próprias.

Esse percurso mostra a principal qualidade estrutural do projeto: o
experimento pode mudar sem exigir uma nova arquitetura de comunicação. O
que se expande é o conjunto de capacidades e de apresentações, não a
responsabilidade de cada plano.
---

[Voltar ao índice da documentação](README.md)
