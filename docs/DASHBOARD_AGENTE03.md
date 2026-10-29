# Dashboard v5.1 — painel do Agente 03

Arquivo: `web/dashboard/index.html` (HTML, CSS e JS inline, sem bibliotecas, sem CDN — ADR-008).
Escopo: o painel atende a bancada do `esp32-03`; não há lista de agentes nem seletor (ADR-014). O Gateway continua multiagente, e `?agent=<id>` aponta o painel para outro agente do Registry (id com letras, números, `_` ou `-`; valor inválido cai em `esp32-03`).

## Fonte de dados
| Dado | Origem | Observação |
|:---|:---|:---|
| Agente (nome, tipo, descrição, estado, capabilities) | `GET /api/agents`, filtrado pelo agente do painel | Polling de 3 s, sem consultas extras |
| Envio de comando | `POST /api/agents/{id}/command` com `{"cmd": "..."}` | Só `MOVER` envia também `"args"` |
| Progresso e resultado | `GET /api/events` (SSE) | Eventos de outros agentes são ignorados |
| Consulta de operação | `GET /api/operations/{id}` | Só após 150 s sem evento final; lê `operation.status` e apenas registra no log |

Verificado no código do Gateway (`controller.go`, `agents.go`): schema SSE (`event`, `op_id`, `agent_id`, `command`, `args`, `attempt`, `stdout`, `stderr`, `reason`, `error`), eventos emitidos, `result_received` também com `stderr`, e resposta de `/api/operations/{id}` como `{success, operation:{status,...}}`. O pior caso do Gateway (5 tentativas) fica abaixo dos 150 s do watchdog.

## Capabilities e estados de uma operação
A lista de capabilities do Registry decide quais controles ficam ativos. O painel conhece 9: `LER_SENSORES`, `TEMPERATURA`, `PRESSAO`, `ALTITUDE`, `CORRENTE`, `DISTANCIA`, `START`, `PARE`, `MOVER`. As ausentes do Registry ficam desabilitadas e aparecem em "Atenção". Capabilities do Registry sem mapeamento não ganham botão.

Estados: disponível → **aceito (HTTP 202)** → **em andamento** (Wake, Auth, Cmd) → **confirmado** (`stdout` e `stderr` vazio) ou **falhou** (`stderr`, saída vazia ou `operation_failed`). Também **recusado pela API** e **sem confirmação** (150 s). O 202 nunca é tratado como execução. Uma operação por vez.

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
1. `registry.json`: preencher `last_ip` do `esp32-03` (o valor anterior era o IP do esp32-02). `InitRegistry` ainda sobrescreve esp32-01/02 com valores fixos.
2. Calibrar na bancada: sentido físico de "direita" (`DIR_DIREITA_NIVEL_ALTO`) e se `rapida` (200 µs) mantém o torque com carga.
3. Opcional: fluxo (YF-S201) e DS18B20 no firmware.
4. Go: o ambiente onde estas mudanças foram feitas não tinha o compilador; rodar `gofmt -l .`, `go vet ./cmd/gateway/... ./internal/...` e `go build -o tunneus-gateway ./cmd/gateway`.

## Testes
`tests/dashboard/`: `mock_gateway.py` (REST + SSE simulados, com a mesma validação de `MOVER` do firmware e o formato real de `/api/operations`) e `test_dashboard.py` (Playwright/Chromium, 109 verificações). Nenhum comando vai ao Gateway real nem ao hardware.
Executar a partir de `tests/dashboard/`: `PLAYWRIGHT_BROWSERS_PATH=... python3 test_dashboard.py`
