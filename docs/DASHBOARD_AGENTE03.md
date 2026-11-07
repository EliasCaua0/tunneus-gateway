# Dashboard multiagente

Arquivo: `web/dashboard/index.html` (HTML, CSS e JavaScript inline, sem bibliotecas nem CDN — ADR-008).

O dashboard lista todos os agentes do Registry e permite abrir um ou mais painéis na mesma guia. Cada guia possui seleção, histórico, logs e gráficos independentes, mantidos somente em memória; nenhum desses dados usa `localStorage`. A seleção inicial pode ser indicada por `?agent=<id>`. Um id inválido ou ausente seleciona `esp32-03` quando disponível.

## Operações concorrentes

- Agentes diferentes executam operações simultaneamente, inclusive quando os comandos partem de guias diferentes.
- Cada agente aceita no máximo uma operação ativa. Enquanto `operation_state` for `in_operation`, todos os seus comandos ficam desabilitados, inclusive `PARE`.
- Um POST concorrente para um agente ocupado recebe HTTP 409 com `error: "agent_busy"` e `active_op_id`. O dashboard não repete automaticamente: apresenta a recusa e oferece retry manual quando o agente voltar a ficar disponível.
- `operation_state` representa a reserva da operação; `status` continua representando conectividade/execução. Os dois estados são independentes.
- Eventos são associados pelo par `agent_id` + `op_id`, de modo que cada Result atualiza somente a operação e o painel correspondentes.

## Fonte de dados
| Dado | Origem | Observação |
|:---|:---|:---|
| Agentes, capabilities e estados | `GET /api/agents` | Polling complementar de 3 s |
| Envio de comando | `POST /api/agents/{id}/command` | `MOVER` também envia `args` |
| Progresso, resultado e ocupação | `GET /api/events` (SSE) | Inclui `agent_state_changed` com `operation_state`, `op_id` e, quando ocupado, `active_op_id` |
| Consulta de operação | `GET /api/operations/{id}` | Só após 150 s sem evento final; lê `operation.status` e apenas registra no log |

Verificado no código do Gateway (`controller.go`, `agents.go`): schema SSE (`event`, `op_id`, `agent_id`, `command`, `args`, `attempt`, `stdout`, `stderr`, `reason`, `error`), eventos emitidos, `result_received` também com `stderr`, e resposta de `/api/operations/{id}` como `{success, operation:{status,...}}`. O pior caso do Gateway (5 tentativas) fica abaixo dos 150 s do watchdog.

## Capabilities e estados de uma operação
A lista de capabilities do Registry decide quais controles ficam ativos. O painel conhece 9: `LER_SENSORES`, `TEMPERATURA`, `PRESSAO`, `ALTITUDE`, `CORRENTE`, `DISTANCIA`, `START`, `PARE`, `MOVER`. As ausentes do Registry ficam desabilitadas e aparecem em "Atenção". Capabilities do Registry sem mapeamento não ganham botão.

Estados: disponível → **aceito (HTTP 202)** → **em andamento** (Wake, Auth, Cmd) → **confirmado** (`stdout` e `stderr` vazio) ou **falhou** (`stderr`, saída vazia ou `operation_failed`). Também **recusado pela API** (inclusive HTTP 409 de agente ocupado) e **sem confirmação** (150 s). O 202 nunca é tratado como execução. Uma operação ativa por agente; agentes diferentes operam em paralelo.

Motivos de `operation_failed` são traduzidos (`REASONS` no código). `result_unconfirmed_no_retry` significa: comando entregue, resultado perdido, **não reenviado**.

## Gráficos
1. Leitura sob demanda (`LER_SENSORES` ou individual). Sem leitura automática.
2. Resultado por SSE associado ao `op_id`.
3. Parser estrito: `CHAVE=valor unidade | ...` ou `valor unidade`. `NA`, formato ou unidade inesperados, valor não numérico e `DISTANCIA < 0` viram amostra inválida (marca vermelha no eixo X).
4. Pressão: Pa → hPa só na exibição. Fluxo: indisponível (sem fonte no firmware).
5. Deduplicação por `op_id + grandeza`.
6. Retenção em memória: 1000 amostras por grandeza, 24 h. Recarregar apaga.
7. Horário da amostra = recebimento no navegador. "Desatualizada" = mais de 5 min.

O firmware v4.4 envia `DISTANCIA=NA` na leitura conjunta quando não há eco; a leitura individual de `DISTANCIA` segue devolvendo `stderr`.

## Motor de passo
- `START` e `MOVER` exigem dois cliques (confirmação de 4 s); mudar qualquer parâmetro desarma. `PARE` é imediato.
- `START`: giro contínuo até `PARE` ou 60 s (400 µs, direita).
- `MOVER`: `{dir: direita|esquerda, steps: 1..30000, speed: lenta|normal|rapida}` (contrato em `PROTOCOLO.md` 3.4.1). O painel valida antes de enviar, o Gateway valida a forma e o firmware valida tudo de novo.
- Tabela de velocidades duplicada no painel (`MOTOR.speeds`) e no firmware; deve ser mantida igual.
- O estado exibido é "último comando confirmado" e "possivelmente em movimento até X" (estimativa = passos × 2 × meio-período + 1,5 s, limitada a 60 s). Nunca é estado verificado: o firmware não informa posição nem fim do movimento.
- `MOVER` com resultado perdido: o motor é marcado como "possivelmente em movimento" e o Gateway não reenvia.

## Pendências de integração
1. Calibrar na bancada: sentido físico de "direita" (`DIR_DIREITA_NIVEL_ALTO`) e se `rapida` (200 µs) mantém o torque com carga.
2. Opcional: fluxo (YF-S201) e DS18B20 no firmware.

## Testes

A suíte `tests/dashboard/test_dashboard.py` executa 34 verificações com Playwright/Chromium contra `tests/dashboard/mock_gateway.py`. O mock simula REST, SSE, concorrência, ocupação e falhas; nenhum teste aciona o Gateway real ou hardware físico. A verificação controlada das cinco grandezas atuais está documentada em `docs/13-verificacao.md`.

```bash
python3 tests/dashboard/test_dashboard.py
```

As capturas versionadas documentam três situações:

- `tests/dashboard/shots/multiagent_busy.png`: agentes ocupados e comandos bloqueados.
- `tests/dashboard/shots/multiagent_parallel.png`: resultados independentes após execução paralela.
- `tests/dashboard/shots/multiagent_mobile.png`: painel do Agente 03 em viewport móvel, sem rolagem horizontal.
