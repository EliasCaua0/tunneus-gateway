# Dashboard v5.1

O dashboard é uma SPA em um único `index.html`, com CSS e JavaScript inline. Não utiliza bibliotecas externas nem CDN.

## 1. Visões

| Visão | Conteúdo |
|---|---|
| Visão geral | Agentes, conectividade e comandos |
| Bancada | Telemetria e controle do Agente 03 |
| Operações | Fila e desfecho das operações |
| Eventos | Histórico local dos eventos SSE |

## 2. Atualização de agentes

A interface consulta `/api/agents` a cada três segundos. Esse polling atualiza o cadastro e a disponibilidade apresentada; não realiza polling periódico de sensores.

## 3. SSE

O navegador abre `/api/events`. Resultados e mudanças de operação são recebidos por esse canal e encaminhados aos componentes da interface.

## 4. Confirmação de comandos

`START` e `MOVER` exigem dois cliques em até quatro segundos. O primeiro clique arma a confirmação; o segundo envia.

`PARE` é imediato, respeitando a disponibilidade e o estado do agente. A ausência de confirmação dupla não elimina a necessidade de procedimentos físicos de segurança.

## 5. Operações e watchdog

Operações pendentes são acompanhadas por `op_id`. O watchdog visual sinaliza operações que ultrapassam 150 segundos, sem equivaler a um cancelamento do comando físico.

## 6. Bancada

A visão apresenta cinco grandezas e gráficos locais. A memória guarda até 1.000 amostras por grandeza e aplica janela de 24 horas.

## 7. Dependência de origem

O dashboard pode ser servido pelo Gateway real ou pelo mock. A interface semelhante não torna equivalentes as fontes de dados: o mock produz valores sintéticos; o hardware produz resultados do firmware.

## 8. Arquivo e testes

- Interface: `web/dashboard/index.html`.
- Mock: `tests/dashboard/mock_gateway.py`.
- Verificações: `tests/dashboard/test_dashboard.py`.

A suíte histórica contém expectativas de versões anteriores. Consulte [Verificação](13-verificacao.md).
