# API, implantação e acesso remoto

## 1. Execução local

Compile o Gateway, defina `TUNNEUS_SECRET` e execute a partir da raiz do projeto para que o caminho relativo `configs/registry.json` seja o esperado.

```bash
go build -o bin/gateway ./cmd/gateway
export TUNNEUS_SECRET="$(openssl rand -base64 32)"
./bin/gateway
```

Abra `http://localhost:18080`.

## 2. Rede

Computador, Gateway e agentes precisam de conectividade IP. Firewalls devem permitir TCP 18080 e UDP 18081. Redes com isolamento de clientes podem bloquear Wake ou WebSocket.

## 3. Registry

Cadastre capabilities compatíveis com o firmware. O `last_ip` é necessário para Wake e é atualizado após autenticação WebSocket.

Não publique o registry real. O arquivo de exemplo usa endereços de documentação e secret exclusivamente demonstrativa.

## 4. Firmware

Configure SSID, senha, IP do Gateway e secret hexadecimal. Confira pinagem e alimentação antes de conectar atuadores.

## 5. Funcionamento sem Internet

Não existe um “modo offline” especial a ativar: a arquitetura já opera localmente. O dashboard, o REST, o SSE, o Wake e o WebSocket podem usar apenas a rede local.

Para testar uma queda de Internet, mantenha a rede local e desconecte a WAN no roteador. Desligar o Wi-Fi do computador também elimina sua conectividade local e impede o acesso ao dashboard.

Se faltar energia ou o roteador local desligar, a operação é interrompida. O acesso remoto habitual pode ficar indisponível sem conectividade externa.

O repositório não registra ensaio físico formal com a WAN desconectada.

## 6. Tailscale

O acesso remoto via Tailscale já funciona e precisa ser otimizado. Ele pode permitir que um computador autorizado alcance o Gateway por uma rede privada.

Tailscale não substitui:

- o cadastro do agente;
- o Wake UDP;
- o WebSocket;
- o HMAC;
- as regras de operação e segurança.

Não publique endereços da tailnet, chaves ou regras de acesso.

## 7. Mock

Execute `python3 tests/dashboard/mock_gateway.py` para demonstrar a interface sem hardware. O mock usa a mesma porta HTTP padrão; não execute dois servidores simultaneamente na mesma porta.
