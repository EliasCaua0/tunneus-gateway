# Colaboração autorizada com o Tunneus

Este repositório possui finalidade expositiva e acadêmica. Contribuições são recebidas de professores, avaliadores e colaboradores autorizados; a disponibilização do conteúdo para leitura não representa uma chamada pública para reutilização ou distribuição do código.

## Antes de alterar

1. Leia a [trajetória](docs/00-trajetoria-e-bancadas.md), a [visão geral](docs/01-visao-geral.md) e a [arquitetura](docs/02-arquitetura.md).
2. Identifique a camada afetada: interface, orquestração, protocolo ou firmware.
3. Preserve os contratos existentes ou documente explicitamente uma evolução de versão.
4. Não inclua credenciais, endereços de infraestrutura real, dados pessoais ou artefatos locais nos commits.
5. Não redistribua o conteúdo; a licença de distribuição ainda não foi definida.

## Organização das mudanças

- Mantenha o núcleo multiagente independente das regras físicas de um experimento.
- Implemente regras de sensores e atuadores no firmware correspondente.
- Documente novas capabilities no Registry de exemplo, no protocolo e na interface quando aplicável.
- Utilize o Mock Gateway para verificar a apresentação sem acionar hardware.
- Diferencie ensaios de software, testes de comunicação, dados sintéticos e resultados da bancada real.
- Preserve o funcionamento local e trate o acesso remoto via Tailscale como uma capacidade existente em aprimoramento.

## Documentação

Alterações de comportamento devem atualizar os capítulos relacionados em `docs/`. Exemplos executáveis devem usar dados sintéticos e secrets exclusivamente demonstrativas; resultados históricos da bancada devem ser identificados como tais, sem misturá-los à saída do mock.

## Verificação sugerida

```bash
go vet ./cmd/gateway ./internal/...
go build -o tunneus-gateway ./cmd/gateway
```

O componente histórico `cmd/client` não integra o build atual. Para o dashboard, utilize o ambiente Python + Playwright descrito na documentação de verificação.
