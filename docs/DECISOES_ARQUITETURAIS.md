# Decisões Arquiteturais

> Este documento registra as principais decisões de arquitetura tomadas durante o desenvolvimento do Tunneus, bem como as motivações por trás de cada uma delas.

O objetivo é preservar o contexto das decisões, facilitando a evolução do projeto e evitando mudanças que contrariem seus princípios fundamentais.

---

# ADR-001 — Arquitetura Baseada em Agentes

## Decisão

O Tunneus utilizará uma arquitetura baseada em agentes.

Cada dispositivo gerenciado executará um Agent responsável por estabelecer comunicação com o Gateway.

## Motivação

Essa abordagem permite:

- Escalabilidade.
- Independência entre dispositivos.
- Comunicação coordenada pelo Gateway.
- Menor complexidade de rede.
- Compatibilidade com diferentes sistemas operacionais.

## Consequências

Todo dispositivo gerenciado deverá possuir um Agent instalado.

---

# ADR-002 — O Agent inicia a conexão

> **Status: substituído na v4.** Na v4 o Gateway convoca o agente por UDP (Wake) e o agente abre o WebSocket somente quando convocado ("Subagente Passivo"). O Gateway ainda não abre conexão TCP para o agente. Ver `PROTOCOLO.md` e `docs/SYSTEM_OVERVIEW.md`. O texto abaixo é mantido como registro histórico.

## Decisão

O Gateway nunca abrirá conexões diretamente para um Agent.

Sempre será o Agent quem iniciará a conexão.

## Motivação

Essa decisão resolve diversos problemas comuns:

- NAT.
- Firewalls.
- Redes domésticas.
- Ambientes corporativos.
- Dispositivos móveis.
- Raspberry Pi em redes locais.

Além disso, reduz significativamente a configuração necessária.

## Consequências

O Gateway apenas aceita conexões.

Os Agents são responsáveis por manter a comunicação ativa.

---

# ADR-003 — Comunicação via WebSocket

## Decisão

Toda a comunicação entre Gateway e Agents utilizará WebSocket.

## Motivação

O WebSocket permite:

- Comunicação bidirecional.
- Baixa latência.
- Canal temporário durante cada operação.
- Menor overhead do que HTTP repetitivo.

## Alternativas consideradas

- HTTP Polling
- Long Polling
- gRPC Streaming

O WebSocket foi escolhido por oferecer simplicidade de implementação, excelente suporte em Go e ampla compatibilidade.

---

# ADR-004 — JSON como protocolo

## Decisão

As mensagens serão serializadas em JSON.

## Motivação

JSON é:

- Simples.
- Legível.
- Fácil de depurar.
- Amplamente suportado.

Durante o desenvolvimento inicial, a facilidade de inspeção foi considerada mais importante do que desempenho máximo.

## Futuro

O protocolo poderá evoluir para um formato binário caso seja necessário aumentar a eficiência.

---

# ADR-005 — Sessões armazenam a conexão

## Decisão

A estrutura Session mantém uma referência para a conexão WebSocket.

```go
Conn *websocket.Conn
```

## Motivação

Inicialmente apenas o Handler conhecia a conexão.

Após a refatoração, cada Session passou a encapsular sua própria comunicação.

Isso permitiu:

- Melhor organização.
- Desacoplamento.
- Maior reutilização.
- Facilidade para envio de comandos.

---

# ADR-006 — Session Manager

## Decisão

Todas as sessões são administradas por um gerenciador central.

## Motivação

Evitar acesso direto a estruturas internas.

Centralizar:

- Busca.
- Inclusão.
- Remoção.
- Listagem.

---

# ADR-007 — Heartbeat

> **Status: substituído na v4.** Não existe heartbeat no protocolo atual: o estado do agente é conhecido apenas pelo resultado das operações. O texto abaixo é mantido como registro histórico.

## Decisão

Cada Agent envia um Heartbeat periodicamente.

## Motivação

Permitir que o Gateway saiba quais dispositivos continuam ativos.

Evita depender apenas do encerramento da conexão TCP.

---

# ADR-008 — Arquitetura Semi-Offline

## Decisão

A Internet não será um requisito para o funcionamento da plataforma.

## Motivação

Laboratórios.

Robótica.

Edge Computing.

Redes industriais.

Infraestrutura local.

Todos esses ambientes precisam continuar operando mesmo quando não existe acesso constante à Internet.

## Consequências

Toda funcionalidade crítica deverá funcionar apenas utilizando a rede local.

A Internet servirá apenas para:

- acesso remoto;
- sincronização;
- descoberta;
- integração entre Gateways.

---

# ADR-009 — Gateway único

## Decisão

Cada infraestrutura possui apenas um Gateway principal.

## Motivação

Centralizar:

- autenticação;
- sessões;
- comandos;
- API;
- interface Web.

Isso reduz complexidade e facilita a administração.

---

# ADR-010 — Go como linguagem principal

## Decisão

Todo o núcleo do Tunneus será desenvolvido em Go.

## Motivação

Go oferece:

- binários únicos;
- baixo consumo de memória;
- concorrência nativa;
- excelente suporte para redes;
- ótima portabilidade.

Além disso, permite distribuir o Agent sem dependências externas.

---

# ADR-011 — API REST

## Decisão

O Gateway disponibilizará uma API REST.

## Motivação

Permitir integração com:

- Painel Web.
- Scripts.
- CLI.
- Ferramentas externas.
- APIs de terceiros.

---

# ADR-012 — Exposição técnica e direitos reservados

> **Status: vigente.** Em outubro de 2026, esta decisão substituiu a possibilidade de distribuição como software livre considerada durante o desenvolvimento.

## Decisão

Nesta etapa, o Tunneus é apresentado em repositório privado, com finalidade expositiva e acadêmica, a professores, avaliadores e colaboradores autorizados. O código e a documentação permanecem com todos os direitos reservados.

A disponibilização para leitura não concede direitos de uso, cópia, modificação, redistribuição, sublicenciamento ou comercialização. Uma eventual licença de distribuição será definida explicitamente em decisão futura.

## Motivação

Permitir a avaliação técnica e o acompanhamento acadêmico do projeto enquanto sua forma de distribuição ainda não está decidida.

---

# ADR-013 — Comandos com argumentos opcionais e sem reenvio de efeitos físicos

## Decisão

A mensagem Command ganha o campo opcional `args` (protocolo v4.1). O Gateway valida apenas a forma de `args` (poucos campos, valores escalares, tamanho limitado) e o repassa sem interpretar. O significado de cada argumento é contrato da capability e é validado pelo firmware.

Capabilities cujo efeito físico não pode ser repetido (hoje, `MOVER`) nunca são reenviadas depois que o comando foi entregue. Falhas anteriores à entrega (Wake, autenticação) continuam com retry.

## Motivação

O dashboard do Agente 03 precisa escolher direção, passos e velocidade do motor. Criar uma capability por combinação não escala e esconderia o contrato. Manter o Gateway agnóstico preserva o núcleo genérico para outros agentes.

O retry do Controller assume idempotência. Para `MOVER` isso é falso: se o resultado se perde depois de o motor girar, um reenvio giraria o motor duas vezes.

## Consequências

- Comandos sem parâmetros mantêm o formato da v4.0 byte a byte.
- Todo firmware que aceitar `args` deve validar tudo antes de acionar o hardware.
- Uma nova capability física não idempotente deve ser incluída em `nonIdempotentCmds` (`internal/controller/controller.go`).
- O resultado de `MOVER` confirma o início do movimento, não o fim.

---

# ADR-014 — Dashboard dedicado ao Agente 03, Gateway multiagente

> **Status: substituído pelo ADR-016.** O dashboard passou a listar todos os agentes e a manter painéis independentes. O texto abaixo permanece como registro histórico.

## Decisão

O dashboard (`web/dashboard/index.html`) atende a bancada do Agente 03 (`esp32-03`), sem lista nem seletor de agentes. O Gateway, o Registry, a API, o SSE e o protocolo continuam multiagente, e o dashboard aceita `?agent=<id>` para apontar para outro agente do Registry.

## Motivação

O foco atual de desenvolvimento é a bancada de sensores e o motor de passo. Uma interface específica permite controles e gráficos corretos para essa bancada, sem reduzir a capacidade multiagente do sistema.

## Consequências

- Um painel multiagente genérico é trabalho futuro e não deve exigir mudanças no Gateway.
- Eventos SSE de outros agentes são ignorados pelo painel.
- Capabilities do Registry sem controle no painel não ganham botão.

---

# ADR-015 — Exclusão mútua por agente e paralelismo entre agentes

## Decisão

Cada agente pode ter no máximo uma operação ativa, reservada atomicamente no Registry antes de a operação ser aceita. A reserva pertence ao `op_id` e só pode ser liberada por ele. Agentes diferentes podem executar operações simultaneamente.

O estado operacional é exposto separadamente do estado de conectividade: `operation_state` assume `available` ou `in_operation`, com `active_op_id` quando ocupado. Mudanças são publicadas por `agent_state_changed` via SSE. Uma submissão concorrente para o mesmo agente é recusada imediatamente com HTTP 409, sem criar operação nem enviar outro Wake.

## Motivação

O Gateway já executava cada operação em uma goroutine, mas não impedia duas operações de disputarem o mesmo dispositivo. Serializar todo o Gateway evitaria a disputa ao custo de bloquear agentes sem relação entre si. A reserva por agente preserva o paralelismo e torna explícita a restrição física de cada dispositivo.

## Consequências

- A reserva é transitória e não é persistida em `registry.json`.
- Todo encerramento de operação, inclusive falha ou esgotamento de retries, deve liberar a reserva.
- `PARE` também é recusado enquanto o agente estiver ocupado; não existe canal prioritário paralelo.
- O retry após HTTP 409 é manual e somente pode ocorrer quando o agente estiver disponível.
- A consulta pública de operações e entradas do Registry usa cópias para não expor estruturas mutáveis entre goroutines.

---

# ADR-016 — Dashboard multiagente com estado isolado por guia

## Decisão

O dashboard lista todos os agentes registrados e permite selecionar vários simultaneamente. Cada guia mantém em memória sua própria seleção, operações, logs e amostras, sem armazenamento compartilhado. Eventos são roteados por `agent_id` e `op_id`.

Os controles específicos de sensores e motor continuam condicionados às capabilities, enquanto comandos genéricos conhecidos podem ser apresentados para os demais agentes.

## Motivação

Operar protótipos simultaneamente exige observar cada operação sem misturar resultados nem permitir que a seleção de uma guia altere outra. O estado operacional em tempo real também precisa bloquear comandos do agente ocupado antes do POST, mantendo o HTTP 409 do Gateway como proteção definitiva contra concorrência entre clientes.

## Consequências

- Recarregar a página descarta o histórico local daquela guia.
- O SSE continua compartilhado pelo Gateway, mas eventos de agentes não selecionados não criam painéis nem operações visíveis na guia.
- O polling de `/api/agents` permanece apenas como sincronização complementar; resultados e mudanças de ocupação chegam por SSE.
- Testes de interface devem cobrir duas guias, agentes concorrentes, HTTP 409, retry manual, isolamento de Result e layout móvel.

---

# Princípios Fundamentais

Toda contribuição ao projeto deve respeitar os seguintes princípios:

- Simplicidade.
- Clareza.
- Código legível.
- Modularidade.
- Segurança.
- Baixo consumo de recursos.
- Independência da Internet.
- Arquitetura baseada em agentes.
- Protocolos transparentes.
- Facilidade de implantação.

---

# Filosofia

O Tunneus não pretende ser apenas uma ferramenta de acesso remoto.

Seu objetivo é tornar-se uma plataforma completa de gerenciamento de infraestrutura distribuída, capaz de administrar servidores, dispositivos embarcados, robôs e ambientes de computação de borda utilizando uma arquitetura simples, eficiente e resiliente.

A Internet deve ampliar as capacidades do sistema, nunca limitar seu funcionamento.
