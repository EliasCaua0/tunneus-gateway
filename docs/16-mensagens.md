# Mensagens e diagnóstico

Esta referência reúne mensagens e situações frequentes. Os textos exatos podem variar por componente e versão.

## 1. HTTP e API

| Situação | Interpretação |
|---|---|
| HTTP 202 | Operação aceita, não concluída |
| Agente inexistente | Cadastro ausente ou ID incorreto |
| Capability inválida | Comando não cadastrado para o agente |
| Secret inválida | Base64 ou tamanho decodificado incorreto |

## 2. Wake e sessão

| Situação | Verificação |
|---|---|
| Agente offline | `last_ip`, rota UDP e energia |
| Hello não chega | IP do Gateway no firmware e TCP 18080 |
| `AUTH_FAILED` | Mesma secret em bytes e challenge correto |
| `SESSION_EXPIRED` | Tempo entre Wake e Hello |
| `SESSION_NOT_FOUND` | Sessão limpa ou ID incorreto |

## 3. Result

- `status: success`: o firmware respondeu sucesso para a operação lógica.
- `status: error`: consultar `stderr` e `exit_code`.
- `MOVER` com sucesso: início aceito, não conclusão física.

## 4. Dashboard

| Sintoma | Possível causa |
|---|---|
| Sem eventos | SSE desconectado ou Gateway indisponível |
| Agentes desatualizados | Polling sem resposta |
| Gráficos vazios | Nenhum Result reconhecido |
| Dados somem ao recarregar | Retenção apenas em memória |
| Operação antiga destacada | Watchdog visual de 150 s |

## 5. Rede local

Se o dashboard parar quando o Wi-Fi do computador for desligado, a rede local também foi perdida. Para testar ausência de Internet, mantenha a LAN ativa e desconecte somente a WAN.

## 6. Diagnóstico seguro

Não enviar comandos a hardware de terceiros. Não publicar logs com secrets, endereços privados ou configuração de tailnet. Em falhas de movimento, priorizar segurança física e os procedimentos da bancada.
