# Glossário do Tunneus

> Este documento reúne os principais conceitos, componentes e termos utilizados durante o desenvolvimento do Tunneus.

---

# A

## Agent

O Agent é o software instalado em uma máquina que será gerenciada pelo Gateway.

Ele é responsável por:

- estabelecer a conexão com o Gateway;
- executar comandos recebidos;
- enviar resultados;
- informar seu estado através de Heartbeats.

O Agent nunca espera conexões de entrada. Ele sempre inicia a conexão com o Gateway.

---

# C

## Command

Mensagem enviada pelo Gateway para solicitar que um Agent execute alguma ação.

Exemplo:

```json
{
    "type":"command",
    "id":"1",
    "cmd":"hostname"
}
```

No futuro, um Command poderá representar:

- comandos do sistema operacional;
- operações Docker;
- gerenciamento de arquivos;
- controle de serviços;
- atualizações OTA;
- automações.

---

## Connected

Data e hora em que uma sessão foi criada.

---

# G

## Gateway

O Gateway é o núcleo do Tunneus.

Ele centraliza toda a comunicação com os Agents.

Responsabilidades:

- aceitar conexões;
- autenticar Agents (futuramente);
- manter sessões;
- encaminhar comandos;
- receber resultados;
- disponibilizar API;
- hospedar o painel Web.

Em uma instalação típica existe apenas um Gateway por infraestrutura.

---

# H

## Heartbeat

Mensagem enviada periodicamente pelo Agent para informar que continua conectado.

Exemplo:

```json
{
    "type":"heartbeat"
}
```

O Gateway utiliza essas mensagens para atualizar o campo `LastHeartbeat` da sessão.

Caso o Heartbeat deixe de ser recebido por um determinado período, o Agent poderá ser considerado offline.

---

# I

## ID da Sessão

Identificador único (UUID) criado quando um Agent estabelece conexão com o Gateway.

Exemplo:

```
9d54c380-51ba-4243-b145-a65f1e63eb6c
```

Esse identificador é utilizado para localizar a sessão correta ao enviar comandos.

---

# J

## JSON

Formato utilizado para todas as mensagens do protocolo Tunneus.

Foi escolhido por ser:

- simples;
- legível;
- multiplataforma;
- amplamente suportado.

---

# L

## LastHeartbeat

Data e hora do último Heartbeat recebido.

Utilizado para identificar sessões inativas.

---

# M

## Manager

Responsável por administrar um conjunto de objetos.

No Tunneus existe o Session Manager.

Funções:

- adicionar sessões;
- remover sessões;
- localizar sessões;
- listar sessões.

---

# P

## Protocolo

Conjunto de mensagens trocadas entre Gateway e Agent.

Atualmente:

- Hello
- Welcome
- Heartbeat
- Command
- Result

---

# R

## Result

Mensagem enviada pelo Agent após executar um Command.

Exemplo:

```json
{
    "type":"result",
    "id":"1",
    "stdout":"arcan",
    "stderr":""
}
```

Ela contém:

- saída padrão (stdout);
- erros (stderr);
- identificação do comando executado.

---

# S

## Semi-Offline

Princípio arquitetural do Tunneus.

A infraestrutura continua funcionando mesmo sem acesso constante à Internet.

A Internet amplia as funcionalidades do sistema, mas não é necessária para sua operação principal.

---

## Session

Representa um Agent conectado ao Gateway.

Cada Session armazena:

- ID
- Nome do Agent
- Horário da conexão
- Último Heartbeat
- Conexão WebSocket

A Session é responsável por representar o estado atual do Agent.

---

## Session Manager

Componente responsável por gerenciar todas as sessões ativas.

É utilizado pela API, pelo WebSocket e pelo monitor de sessões.

---

## STDOUT

Saída padrão produzida por um comando executado.

Exemplo:

```
hostname
```

Resultado:

```
arcan
```

---

## STDERR

Saída de erro produzida durante a execução de um comando.

Exemplo:

```
ping
```

Sem parâmetros:

```
Endereço de destino requerido.
```

---

# T

## Tunneus

Plataforma distribuída de gerenciamento de infraestrutura desenvolvida em Go.

Seu objetivo é administrar:

- servidores;
- computadores;
- Raspberry Pis;
- robôs;
- dispositivos embarcados;
- containers.

Tudo através de uma arquitetura baseada em agentes.

---

# W

## WebSocket

Protocolo utilizado para manter uma conexão persistente entre o Gateway e os Agents.

Permite comunicação bidirecional em tempo real.

No Tunneus, todas as mensagens do protocolo trafegam através do WebSocket.

Fluxo:

Agent

↓

Hello

↓

Gateway

↓

Welcome

↓

Heartbeat

↓

Commands

↓

Results

---

# Conceitos Importantes

## Arquitetura Baseada em Agentes

No Tunneus, o Gateway nunca inicia conexões diretamente com os dispositivos.

Cada Agent estabelece sua própria conexão com o Gateway.

Essa abordagem simplifica o funcionamento em redes protegidas por NAT e firewalls.

---

## Comunicação Bidirecional

Após a conexão WebSocket ser estabelecida, tanto o Gateway quanto o Agent podem enviar mensagens a qualquer momento.

Isso elimina a necessidade de consultas constantes (polling), reduz a latência e melhora a eficiência da comunicação.

---

## Sessão

Uma sessão representa a comunicação ativa entre um Agent e o Gateway.

Enquanto a sessão existir, o Gateway pode:

- enviar comandos;
- receber resultados;
- acompanhar o estado do Agent.

Quando a conexão é encerrada, a sessão é removida.

---

## Filosofia do Projeto

O Tunneus não é apenas uma ferramenta de acesso remoto.

Ele é uma plataforma de gerenciamento de infraestrutura.

Executar comandos remotos é apenas uma das funcionalidades possíveis.

A arquitetura foi projetada para evoluir e incorporar recursos como:

- gerenciamento de containers;
- administração de serviços;
- transferência de arquivos;
- monitoramento;
- robótica;
- automação;
- inteligência artificial.

Todos esses recursos compartilham a mesma base: um Gateway central e Agents distribuídos.
