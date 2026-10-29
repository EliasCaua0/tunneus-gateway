# Tunneus Gateway

Sistema de automação em rede local que conecta um dashboard, um Gateway em Go e agentes ESP32 por meio de operações assíncronas e sessões temporárias autenticadas.

**Protocolo Tunneus V4.1 · Dashboard v5.1 · Ecossistema ArcanLab**

## Visão geral

O operador escolhe uma capability no dashboard. O Gateway cria uma operação, convoca o agente por UDP, autentica uma sessão WebSocket temporária, envia o comando e publica o resultado por SSE. O ESP32 executa a ação física e retorna ao estado STANDBY.

```mermaid
flowchart LR
    U[Operador] --> D[Dashboard]
    D -->|HTTP REST| G[Tunneus Gateway]
    G -->|SSE| D
    G -->|Wake UDP 18081| E[ESP32]
    E -->|WebSocket temporário| G
    E --> H[Sensores e atuadores]
```

Esse modelo é denominado **Subagente Passivo + Pico de Conexão**: o WebSocket permanece fechado em repouso e existe somente durante a execução da operação.

## O que está implementado

- Gateway multiagente em Go, com API REST e eventos SSE.
- Operações assíncronas com HTTP 202 e identificação por `op_id`.
- Convocação UDP e sessões WebSocket efêmeras.
- Autenticação por desafio com HMAC-SHA256.
- Registry de agentes, capabilities e endereços.
- Firmware para LED, sensores e motor de passo.
- Dashboard SPA sem bibliotecas externas, com gráficos SVG.
- Mock Gateway e verificação da interface com Playwright.

## Documentação

A documentação foi organizada como uma trilha progressiva: primeiro a arquitetura e uma operação completa; depois protocolo, segurança e componentes internos; por fim hardware, telemetria, dashboard, implantação e validação.

**[Abrir o índice completo da documentação](docs/README.md)**

| Atalho | Conteúdo |
|---|---|
| [Visão geral](docs/01-visao-geral.md) | Finalidade, agentes e capacidades do sistema |
| [Arquitetura](docs/02-arquitetura.md) | Planos, responsabilidades, canais e portas |
| [Operação ponta a ponta](docs/03-operacao-ponta-a-ponta.md) | Do clique ao gráfico, passo a passo |
| [Protocolo V4.1](docs/05-protocolo.md) | Wake, Hello, Welcome, Command, Result e Bye |
| [Telemetria](docs/10-telemetria.md) | Do sensor ao gráfico no navegador |
| [API e implantação](docs/12-api-e-implantacao.md) | Rotas, configuração, execução e diagnóstico |
| [Glossário](docs/glossario.md) | Termos empregados no projeto |

## Demonstração sem hardware

O mock reproduz as rotas REST e os eventos SSE do Gateway. Ele não se comunica com dispositivos reais e utiliza somente dados sintéticos.

```bash
python3 tests/dashboard/mock_gateway.py web/dashboard/index.html 18555
```

Abra `http://127.0.0.1:18555/dashboard/` no navegador. É possível solicitar leituras, acompanhar o Pico de Conexão, observar gráficos e exercitar os controles de movimento sem acionar a bancada.

## Execução do Gateway

### Requisitos

- Go compatível com a versão declarada em `go.mod`;
- Arduino IDE e suporte ao ESP32 para os firmwares;
- ArduinoWebsockets, ArduinoJson 6.x e Adafruit BMP085 para o Agente 03;
- Python e Playwright somente para a verificação automatizada do dashboard.

### Configuração

O arquivo `registry.json` é local e não é versionado. Comece pelo exemplo:

```bash
cp configs/registry.example.json registry.json
```

Substitua as secrets demonstrativas, os endereços IP e as credenciais dos firmwares antes de utilizar hardware. A secret do Registry é representada em Base64; no firmware, os mesmos bytes são representados em hexadecimal.

### Build e execução

```bash
go mod tidy
go build -o tunneus-gateway ./cmd/gateway
./tunneus-gateway
```

O dashboard estará disponível em `http://localhost:18080/dashboard/`.

## Exemplo de operação

```bash
curl -X POST http://localhost:18080/api/agents/esp32-03/command \
  -H 'Content-Type: application/json' \
  -d '{"cmd":"LER_SENSORES"}'
```

A resposta HTTP 202 confirma o aceite da intenção, não a conclusão da leitura. O desfecho pode ser acompanhado por `/api/events` ou consultado em `/api/operations/{op_id}`.

## Estrutura do repositório

```text
cmd/gateway/          ponto de entrada do Gateway
internal/             Controller, API, Registry, sessões e transportes
agents/esp32/         firmwares e instruções
web/dashboard/        dashboard v5.1
tests/dashboard/      mock e verificação com Playwright
docs/                 documentação técnica progressiva
configs/              exemplos públicos de configuração
```

O diretório `cmd/client` preserva um componente histórico da V3 e não integra o build atual.

## Escopo e validação

O projeto foi concebido para bancadas e experimentos em rede local. A telemetria atual é sob demanda, e o histórico visual permanece na memória do navegador. A verificação com mock avalia a interface e os contratos simulados; não substitui ensaios elétricos, calibração de sensores ou caracterização mecânica.

## Autoria

- **Elias Cauã de Souza** — desenvolvimento do projeto
- **Marcelo da Silva dos Santos** — orientação

Instituto Federal Sul-rio-grandense — Campus Novo Hamburgo · Ecossistema ArcanLab.

## Licença

O código é distribuído sob a [Licença MIT](LICENSE). Consulte também as [orientações de segurança](SECURITY.md) antes de configurar uma instalação pública ou compartilhar credenciais.
