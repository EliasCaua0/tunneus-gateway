# Guia de arquivos

Este mapa relaciona cada parte da documentação ao código correspondente.

## 1. Entrada do Gateway

| Arquivo | Conteúdo |
|---|---|
| `cmd/gateway/main.go` | Inicialização, embed do dashboard e servidor HTTP |
| `cmd/client/main.go` | Cliente CLI |
| `go.mod` / `go.sum` | Módulo e dependências |

## 2. Componentes internos

| Diretório | Responsabilidade |
|---|---|
| `internal/api` | REST, SSE e arquivos estáticos |
| `internal/controller` | Operações, retries e estados |
| `internal/protocol` | Tipos e comandos |
| `internal/registry` | Agentes e persistência |
| `internal/session` | Sessões, challenges e TTL |
| `internal/wake` | Wake UDP e HMAC |
| `internal/websocket` | Upgrade, autenticação e Result |

## 3. Interface

| Arquivo | Conteúdo |
|---|---|
| `web/dashboard/index.html` | HTML, CSS e JavaScript da SPA v5.1 |

## 4. Firmware

| Arquivo | Agente |
|---|---|
| `agents/esp32/esp32_agent.ino.ino` | Agente 01 |
| `agents/esp32/agente03/agente03.ino` | Agente 03 |

## 5. Configuração

| Arquivo | Uso |
|---|---|
| `configs/registry.example.json` | Exemplo sanitizado |
| `configs/registry.json` | Runtime local; não versionado |
| `.gitignore` | Exclusão de segredos e artefatos |

## 6. Testes

| Arquivo | Finalidade |
|---|---|
| `tests/dashboard/mock_gateway.py` | API e dados sintéticos |
| `tests/dashboard/test_dashboard.py` | Verificações históricas do dashboard |

## 7. Documentação

| Arquivo | Finalidade |
|---|---|
| `README.md` | Entrada e execução |
| `PROTOCOLO.md` | Especificação das mensagens |
| `docs/00` a `docs/17` | Explicação progressiva |
| `docs/SYSTEM_OVERVIEW.md` | Visão técnica complementar |
| `docs/DECISOES_ARQUITETURAIS.md` | ADRs |
| `ROADMAP.md` | Evolução futura |
| `LICENSE` | Direitos e ausência de licença de distribuição |
| `SECURITY.md` | Cuidados de segurança |
| `CONTRIBUTING.md` | Colaboração autorizada |

## 8. Ordem sugerida de leitura

1. README.
2. Visão geral.
3. Arquitetura.
4. Operação ponta a ponta.
5. Protocolo e autenticação.
6. Gateway e firmware.
7. Telemetria e dashboard.
8. API, verificação e limites.
