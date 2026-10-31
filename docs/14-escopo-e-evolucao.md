# Escopo, limites e evolução

O Tunneus é um protótipo acadêmico funcional em evolução. A documentação separa capacidades presentes de melhorias planejadas.

## 1. Capacidades presentes

- Operação local com Gateway Go.
- Wake UDP autenticado.
- WebSocket temporário com HMAC.
- API REST e SSE.
- Dashboard sem dependências externas.
- Telemetria sob demanda.
- Firmwares dos Agentes 01 e 03.
- Mock para testes.
- Acesso remoto via Tailscale já funcional, com otimização pendente.

## 2. Limites técnicos

- Sem TLS nativo.
- Sem mDNS ou descoberta automática.
- Sem persistência de telemetria no navegador.
- Sem confirmação física de posição.
- Sem RBAC e audit log.
- Sem alta disponibilidade do Gateway.
- Sem distribuição open source definida.

## 3. Evolução técnica

Prioridades documentadas no roadmap:

1. Otimizar o acesso remoto existente.
2. Melhorar segurança de transporte.
3. Acrescentar descoberta e atualização de firmware.
4. Persistir telemetria com retenção definida.
5. Ampliar testes de integração.
6. Reavaliar confirmação e parada de movimento.

## 4. Evolução da apresentação

O repositório deve manter clara a diferença entre Tunneus, protótipos, bancadas e mock. Exemplos sanitizados não devem ser confundidos com credenciais operacionais.

## 5. Licenciamento

O material é expositivo e privado, destinado a professores e colaboradores autorizados. A licença de distribuição ainda não foi decidida. Direitos reservados e aviso de copyright não equivalem a uma decisão de open source.

## 6. Roadmap não é implementação

Itens futuros descrevem intenção. A referência para comportamento atual é o código acompanhada das notas de verificação e dos limites documentados.
