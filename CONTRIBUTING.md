# Contribuindo com o Tunneus

## Antes de alterar

1. Leia a [visão geral](docs/01-visao-geral.md) e a [arquitetura](docs/02-arquitetura.md).
2. Identifique a camada afetada: interface, orquestração, protocolo ou firmware.
3. Preserve os contratos existentes ou documente explicitamente uma evolução de versão.
4. Não inclua credenciais, endereços de infraestrutura real ou artefatos locais nos commits.

## Organização das mudanças

- Mantenha o núcleo multiagente independente das regras físicas de um experimento.
- Implemente regras de sensores e atuadores no firmware correspondente.
- Documente novas capabilities no Registry de exemplo, no protocolo e na interface quando aplicável.
- Utilize o Mock Gateway para verificar a apresentação sem acionar hardware.
- Diferencie ensaios de software, testes de comunicação e validação física da bancada.

## Documentação

Alterações de comportamento devem atualizar os capítulos relacionados em `docs/`. Exemplos devem usar dados sintéticos e secrets exclusivamente demonstrativas.

## Verificação sugerida

```bash
go vet ./cmd/gateway ./internal/...
go build -o tunneus-gateway ./cmd/gateway
```

O componente histórico `cmd/client` não integra o build atual. Para o dashboard, utilize o ambiente Python + Playwright descrito na documentação de verificação.
