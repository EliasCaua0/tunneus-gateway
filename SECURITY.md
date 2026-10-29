# Segurança e credenciais

## Configuração local

- Não versione `registry.json`, arquivos `.env`, senhas de Wi-Fi ou secrets reais.
- Utilize `configs/registry.example.json` somente como modelo.
- Substitua todas as secrets demonstrativas antes de utilizar hardware.
- Gere uma secret diferente por agente e mantenha equivalência entre Base64 no Registry e hexadecimal no firmware.
- Restrinja o acesso à rede da bancada e aos arquivos locais de configuração.

## Escopo de rede

A versão atual utiliza HTTP, WebSocket `ws://` e UDP em rede local. A exposição direta à Internet exige uma revisão de arquitetura, autenticação de clientes, proteção de transporte e políticas de rede adequadas.

## Relato de vulnerabilidades

Não abra issues públicas contendo secrets, dados de infraestrutura ou procedimentos que exponham uma instalação ativa. Descreva o comportamento com dados fictícios e utilize um canal privado do responsável pelo repositório quando a ocorrência envolver informação sensível.

## Validação

O Mock Gateway destina-se somente a demonstrações e testes. Ele não deve ser apresentado como mecanismo de segurança nem como validação elétrica ou metrológica da bancada.
