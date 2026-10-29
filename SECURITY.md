# Segurança, acesso e credenciais

## Acesso ao repositório

O repositório destina-se à exposição técnica do projeto a professores, avaliadores e colaboradores autorizados. O acesso deve permanecer restrito até que o titular decida explicitamente sobre uma eventual licença e forma de distribuição. Não publique capturas, clones ou trechos que contenham configuração, dados pessoais ou informações de infraestrutura.

## Configuração local

- Não versione `registry.json`, arquivos `.env`, senhas de Wi-Fi ou secrets reais.
- Utilize `configs/registry.example.json` somente como modelo.
- Substitua todas as secrets demonstrativas antes de utilizar hardware.
- Gere uma secret diferente por agente e mantenha equivalência entre Base64 no Registry e hexadecimal no firmware.
- Restrinja o acesso à rede da bancada e aos arquivos locais de configuração.

## Escopo de rede e acesso remoto

A versão atual utiliza HTTP, WebSocket `ws://` e UDP na comunicação entre os componentes. A rede local preserva a operação sem Internet, enquanto o acesso remoto já pode ser realizado por uma rede privada Tailscale com dispositivos autorizados. Esse acesso remoto existe e está em processo de otimização; não deve ser interpretado como autorização para expor o Gateway diretamente à Internet.

Não publique endereços da tailnet, identificadores de dispositivos, chaves, regras de acesso ou qualquer configuração que facilite o alcance de uma instalação ativa. Uma eventual exposição fora da rede privada exige revisão de autenticação de clientes, proteção de transporte e políticas de rede.

## Relato de vulnerabilidades

Utilize somente os canais privados do responsável pelo projeto. Não abra issues ou discussões contendo secrets, dados de infraestrutura ou procedimentos que exponham uma instalação ativa. Descreva o comportamento com dados fictícios sempre que possível.

## Validação e proveniência

O Mock Gateway destina-se somente a demonstrações e testes com dados sintéticos. Registros históricos da bancada real devem ser identificados como evidências experimentais do projeto, sem apresentá-los como certificação elétrica, metrológica ou mecânica.
