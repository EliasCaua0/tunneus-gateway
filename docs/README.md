# Documentação técnica do Tunneus

Esta documentação apresenta o sistema de forma progressiva a professores, avaliadores e colaboradores autorizados. Cada capítulo parte de uma pergunta e acrescenta um nível de detalhe, permitindo primeiro compreender a trajetória e a arquitetura e depois consultar a implementação. O repositório tem finalidade expositiva; não constitui uma distribuição de código aberto.

## Trilha recomendada

### 1. Compreender o sistema

0. [Trajetória do projeto e papel das bancadas](00-trajetoria-e-bancadas.md)
1. [Visão geral: o que é o Tunneus](01-visao-geral.md)
2. [Arquitetura: quem conversa com quem](02-arquitetura.md)
3. [Uma operação de ponta a ponta](03-operacao-ponta-a-ponta.md)
4. [Subagente Passivo e Pico de Conexão](04-subagente-passivo.md)

### 2. Aprofundar comunicação e núcleo

5. [Protocolo Tunneus V4.1](05-protocolo.md)
6. [Autenticação e segurança da sessão](06-autenticacao.md)
7. [O Gateway por dentro](07-gateway.md)
8. [Confiabilidade, timeouts e retries](08-timeouts-e-retries.md)

### 3. Aplicar ao experimento

9. [Firmwares e integração com o hardware](09-firmware-e-hardware.md)
10. [Telemetria: do sensor ao gráfico](10-telemetria.md)
11. [Dashboard: a arquitetura vista pelo operador](11-dashboard.md)

### 4. Operar e evoluir

12. [API, implantação e diagnóstico](12-api-e-implantacao.md)
13. [Verificação funcional do sistema](13-verificacao.md)
14. [Escopo atual e evolução do projeto](14-escopo-e-evolucao.md)
15. [Síntese do funcionamento](15-sintese.md)

### Material de consulta

- [Mensagens exemplificadas](16-mensagens.md)
- [Guia dos arquivos e dependências](17-guia-de-arquivos.md)
- [Glossário técnico](glossario.md)
- [Protocolo — documento original](../PROTOCOLO.md)
- [Visão do sistema — documento original](SYSTEM_OVERVIEW.md)
- [Decisões arquiteturais](DECISOES_ARQUITETURAIS.md)
- [Dashboard do Agente 03 — documento original](DASHBOARD_AGENTE03.md)
- [Roadmap](../ROADMAP.md)

## Convenções

- “Implementado” descreve o comportamento da versão atual.
- “Planejado” indica evolução registrada no roadmap.
- Comandos e campos aparecem em fonte monoespaçada.
- Secrets e endereços dos exemplos são demonstrativos.
- Os dados produzidos pelo Mock Gateway são sintéticos e não representam medições físicas.
- Os dados históricos do caderno de campo são provenientes da bancada real.
- Os protótipos são instrumentos de experimentação e teste; o projeto central é o Tunneus.
- O acesso remoto via Tailscale já existe e permanece em otimização.

Para uma primeira apresentação, recomenda-se ler os capítulos 0 a 4 e, em seguida, executar a demonstração descrita no [README principal](../README.md).
