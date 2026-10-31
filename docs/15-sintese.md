[← Índice da documentação](README.md)

# 15. Síntese do funcionamento

> **Visão integrada:** Depois do percurso progressivo, o sistema pode
> ser lido como uma única cadeia: intenção, operação, sessão, ação
> física, resultado e apresentação.

## 15.1 A arquitetura em dez ideias

1.  **O dashboard representa a intenção.** O operador escolhe agente e
    capability, mas não conversa diretamente com o ESP32.
2.  **O Gateway cria uma operação.** HTTP 202 devolve `op_id` e libera o
    cliente enquanto a goroutine trabalha.
3.  **O Registry orienta a operação.** Identidade, secret, endereço e
    capabilities determinam o que pode ser executado.
4.  **O Wake convoca sem manter conexão permanente.** UDP 18081
    transporta sessão, challenge e WakeMAC.
5.  **O agente comprova a convocação e responde ao desafio.** O Wake é
    validado antes do WebSocket; o Hello é validado antes do Welcome.
6.  **A sessão existe apenas durante o trabalho.** Canais sincronizam
    Controller e handler; TTL e cleanup liberam recursos.
7.  **O firmware transforma comando em física.** Pode ler cache, forçar
    aquisição, alterar um LED ou gerar pulsos para o motor.
8.  **O Result fecha a operação de rede.** O texto retorna pelo
    WebSocket e chega ao navegador por SSE.
9.  **O dashboard interpreta antes de apresentar.** Filtra agente,
    deduplica, confere unidade e cria amostras em memória.
10. **Cada camada conserva sua responsabilidade.** Interface,
    orquestração e hardware evoluem sem misturar contratos.

## 15.2 O ciclo que permanece em todos os experimentos

Uma leitura de temperatura e um movimento de motor parecem ações muito
diferentes, mas compartilham o mesmo percurso de comunicação. Em ambos,
o Gateway seleciona o agente, cria a operação, convoca, autentica e
envia um Command. A diferença começa no firmware: uma capability
consulta um valor; outra configura um atuador.

Também muda a interpretação do desfecho. Em uma leitura, o Result contém
a grandeza que será transformada em amostra. Em MOVER, o Result confirma
que o movimento foi iniciado; a contagem de passos continua localmente.
O protocolo é comum, mas a semântica física permanece explícita.

## 15.3 Considerações finais

O Tunneus Gateway apresenta uma arquitetura de automação distribuída
construída em torno de sessões curtas e responsabilidades bem
delimitadas. A ausência de conexão permanente não elimina a
observabilidade: operações, eventos e estados tornam visível cada etapa
da comunicação.

A combinação de Gateway em Go, firmware ESP32, protocolo JSON
autenticado e dashboard semi-offline forma uma base didática e
extensível. O mesmo documento que descreve o sistema também evidencia
seu método: compreender a intenção, seguir a operação, identificar a
sessão, examinar a ação física e interpretar corretamente o resultado.

> **Síntese final:** O projeto conecta software e bancada por um ciclo
> curto, autenticado e rastreável. É esse ciclo — e não um dispositivo
> isolado — que constitui a arquitetura Tunneus.
---

[Voltar ao índice da documentação](README.md)
