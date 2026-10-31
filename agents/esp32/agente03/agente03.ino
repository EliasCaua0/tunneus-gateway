#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>
#include "mbedtls/md.h"
#include <Wire.h>
#include <Adafruit_BMP085.h>

using namespace websockets;

// ============================================================
// Tunneus Subagent ESP32 — Agente 03 (Bancada de Sensores + Motor de Passo)
// Firmware v4.4 — Protocolo Tunneus v4.1 (comando com "args" opcional)
//
// Mudancas em relacao a v4.3 (rede, pinagem e sensores NAO foram alterados):
//   * Nova capability MOVER, com args {dir, steps, speed} (ver PROTOCOLO.md 3.4.1)
//   * START continua igual: sem argumentos, gira ate PARE ou 60 s
//   * LER_SENSORES devolve DISTANCIA=NA quando nao ha eco do HC-SR04
// ============================================================

// ============================================================
// CONFIGURAÇÕES DE REDE E AUTENTICAÇÃO (Mesmo protocolo do Agente 02)
// ============================================================
const char* WIFI_SSID     = "SUA_REDE_WIFI";
const char* WIFI_PASSWORD = "SUA_SENHA_WIFI";
const char* GATEWAY_HOST  = "192.168.1.10";
const char* AGENT_ID      = "esp32-03";

// Secret HEX de exemplo; substitua e mantenha equivalencia com o Registry.
const char* SECRET_HEX    = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f";
const size_t SECRET_LEN   = 32;

#define WAKE_PORT     18081
#define GATEWAY_PORT  18080

// ============================================================
// PINAGEM DOS SENSORES (Agente 03 - Bancada de Sensores + Motor de Passo)
// ============================================================
// BMP180 (I2C): SDA = GPIO21, SCL = GPIO22 (padrao do Wire)
// ACS712 OUT  -> GPIO34 | HC-SR04: TRIG = GPIO14, ECHO = GPIO13
// Pinos do motor de passo (dirPin/pulPin) ficam na secao do motor abaixo,
// declarados com os mesmos nomes e tempos do exemplo motordepasso.ino.

const int PIN_CORRENTE  = 34;  // GPIO34 - OUT do ACS712
const int PIN_TRIG      = 14;  // GPIO14 - Trig do HC-SR04
const int PIN_ECHO      = 13;  // GPIO13 - Echo do HC-SR04

// ============================================================
// PARÂMETROS DOS SENSORES
// ============================================================
#define SOUND_SPEED 0.034           // Velocidade do som em cm/us
const float PRESSAO_NIVEL_MAR = 102360.0; // Calibracao de altitude (~28 m)
const float SENSIBILIDADE_ACS712 = 0.185; // V/A (modelo 5A; 20A=0.100, 30A=0.066)
const float ZERO_CORRENTE = 1.406;        // Tensao de repouso calibrada do ACS712
const unsigned long SENSOR_INTERVALO_MS = 2000; // Leitura conjunta a cada 2 s

Adafruit_BMP085 bmp;

// Cache das leituras (disponivel para o dashboard via capabilities)
float temperaturaC = 0.0;
float pressaoPa    = 0.0;
float altitudeM    = 0.0;
float correnteA    = 0.0;
float distanciaCm  = 0.0;
unsigned long ultimaLeituraSensores = 0;

// ============================================================
// MOTOR DE PASSO — pinos e forma de onda identicos ao exemplo motordepasso.ino
// ============================================================
// Definicao dos pinos conforme a bancada (testados com o exemplo)
const int dirPin = 19; // GPIO19 (DIR+)
const int pulPin = 18; // GPIO18 (PUL+)

// Forma de onda do exemplo: HIGH por N us + LOW por N us em cada passo.
// Valores entre 200 e 800 us funcionam bem (nota do exemplo original).
// As tres velocidades do dashboard (args.speed) mapeiam para esses valores:
//   lenta  = 800 us  (~625 passos/s)
//   normal = 400 us  (~1250 passos/s)  <- igual ao exemplo e ao START
//   rapida = 200 us  (~2500 passos/s)  <- limite do intervalo validado
// ATENCAO: o contrato (PROTOCOLO.md) e o dashboard usam esta mesma tabela
// para estimar a duracao do movimento. Se mudar aqui, mude la.
const unsigned int PULSO_US_LENTA  = 800;
const unsigned int PULSO_US_NORMAL = 400;
const unsigned int PULSO_US_RAPIDA = 200;

// Sentido: "direita" = nivel de DIR usado no 1o. giro do exemplo (HIGH).
// Se na bancada "direita" girar para o lado errado, inverta esta constante.
const bool DIR_DIREITA_NIVEL_ALTO = true;

// Limite de passos por MOVER. Em "lenta" (1600 us/passo) 30000 passos = 48 s,
// dentro da janela de seguranca de 60 s.
const unsigned long MOTOR_MAX_PASSOS = 30000;

bool motorRodando             = false;
bool estadoPulso              = false;
unsigned long ultimoPulsoUs   = 0;
unsigned long inicioMotorMs   = 0;
unsigned int  motorPulseDelay = PULSO_US_NORMAL; // meio-periodo atual (us)
bool motorFinito              = false;           // true = MOVER; false = START continuo
unsigned long motorPassosRestantes = 0;
const unsigned long TEMPO_MAX_MOTOR_MS = 60000; // Seguranca: para apos 60 s

// ============================================================
// VARIÁVEIS DE ESTADO DE REDE (Identicas ao Agente 02)
// ============================================================
enum State {
  STATE_STANDBY,
  STATE_CONNECTING,
  STATE_AUTHENTIC,
  STATE_COMMAND,
  STATE_ACK,
  STATE_DISCONNECTING
};

WiFiUDP*            udp = nullptr;
WebsocketsClient*   wsClient = nullptr;
State               currentState = STATE_STANDBY;
uint8_t             secretRaw[64];
size_t              secretRawLen = 0;
String              pendingSessionID;
String              pendingChallenge;
String              currentCommandID;

String              usedSessions[4];
int                 usedSessionCount = 0;
unsigned long       stateStartTime = 0;
unsigned long       totalOps = 0;
bool                inCleanup = false;
unsigned long       lastHeapCheck = 0;
unsigned long       lastWiFiCheck = 0;

String resultadoStdout = "";
String resultadoStderr = "";

// Prototipos de Funcoes de Rede e Protocolo
void setState(State s);
void startUDP();
void stopUDP();
void createWSClient();
void destroyWSClient();
void handleStandby();
void handleConnecting();
void handleAuthentic();
void handleCommand();
void handleAck();
void handleDisconnecting();
void cleanupAndStandby();
void onMessageCallback(WebsocketsMessage msg);
void onEventsCallback(WebsocketsEvent ev, String data);
bool parseHex(const char* hex, uint8_t* out, size_t maxLen, size_t* outLen);
String hmacSha256(const char* message, size_t msgLen, const uint8_t* key, size_t keyLen);
bool isSessionUsed(const String& sid);
void markSessionUsed(const String& sid);
void sendHello();
void sendResult(const char* resultOut, const char* resultErr);
void sendBye(const char* reason);
void executeHardware(const char* cmd, JsonObject args);
void checkHeap();
void checkWiFi();
void connectWiFi();

// Prototipos de Hardware
void lerTodosSensores();
float lerCorrenteA();
float lerDistanciaCm();
void atualizarMotorPasso();
void desligarSaidaMotor();
void iniciarMotor();
void pararMotor(const char* motivo);
void moverMotor(JsonObject args);
void erroMotor(const char* msg);
void executarSensores(const char* cmd);
void executarMotor(const char* cmd, JsonObject args);

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(500);

  // Configuracao dos Pinos de Hardware
  pinMode(PIN_CORRENTE, INPUT);
  pinMode(PIN_TRIG, OUTPUT);
  pinMode(PIN_ECHO, INPUT);
  pinMode(dirPin, OUTPUT);
  pinMode(pulPin, OUTPUT);

  digitalWrite(PIN_TRIG, LOW);
  digitalWrite(dirPin, LOW);   // mesmo estado inicial do exemplo
  digitalWrite(pulPin, LOW);

  Serial.println("\n===================================");
  Serial.println("Tunneus Subagent ESP32 — Agente 03 (Sensores + Motor de Passo) v4.4");
  Serial.println("===================================");

  // Inicializa o BMP180
  Wire.begin(21, 22);
  if (!bmp.begin()) {
    Serial.println("[HW] Sensor BMP180 nao encontrado! Verifique o barramento I2C.");
  } else {
    Serial.println("[HW] BMP180 OK (I2C: SDA=21, SCL=22).");
  }

  if (!parseHex(SECRET_HEX, secretRaw, sizeof(secretRaw), &secretRawLen)) {
    Serial.println("[Auth] FALHA ao decodificar secret HEX!");
    while (true) { delay(1000); }
  }
  Serial.printf("[Auth] Secret decodificada: %d bytes\n", secretRawLen);

  connectWiFi();
  createWSClient();
  startUDP();
  setState(STATE_STANDBY);

  // Primeira leitura conjunta dos sensores
  lerTodosSensores();

  Serial.println("[Setup] === PRONTO ===");
  checkHeap();
  Serial.flush();
}

void connectWiFi() {
  Serial.printf("[WiFi] Conectando a %s\n", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  int wifiRetries = 0;
  while (WiFi.status() != WL_CONNECTED && wifiRetries < 30) {
    delay(500); Serial.print("."); wifiRetries++;
  }
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n[WiFi] FALHA! Reiniciando...");
    ESP.restart();
  }
  Serial.printf("\n[WiFi] OK! IP: %s RSSI: %d dBm\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
}

// ============================================================
// LOOP PRINCIPAL
// ============================================================
void loop() {
  unsigned long now = millis();

  if (now - lastWiFiCheck > 30000) {
    lastWiFiCheck = now;
    checkWiFi();
  }

  // Leitura conjunta periodica dos sensores (nao-bloqueante)
  if (now - ultimaLeituraSensores >= SENSOR_INTERVALO_MS) {
    lerTodosSensores();
  }

  // Geracao de pulsos do motor de passo (nao-bloqueante) —
  // roda em TODOS os estados da maquina de rede: o motor continua
  // girando mesmo apos a sessao fechar, ate chegar PARE, o fim dos passos
  // (MOVER) ou o timeout de seguranca.
  atualizarMotorPasso();

  switch (currentState) {
    case STATE_STANDBY:       handleStandby();       break;
    case STATE_CONNECTING:    handleConnecting();    break;
    case STATE_AUTHENTIC:     handleAuthentic();     break;
    case STATE_COMMAND:       handleCommand();       break;
    case STATE_ACK:           handleAck();           break;
    case STATE_DISCONNECTING: handleDisconnecting(); break;
  }
}

void checkHeap() {
  Serial.printf("[Heap] Livre: %d | Maior bloco: %d | Fragmentacao: %d%%\n",
                ESP.getFreeHeap(), ESP.getMaxAllocHeap(),
                100 - (ESP.getMaxAllocHeap() * 100 / ESP.getFreeHeap()));
}

void checkWiFi() {
  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("[WiFi] Desconectado! Reconectando...");
    WiFi.reconnect();
    int retries = 0;
    while (WiFi.status() != WL_CONNECTED && retries < 20) {
      delay(500); retries++;
    }
    if (WiFi.status() == WL_CONNECTED) {
      Serial.println("[WiFi] Reconectado.");
    } else {
      Serial.println("[WiFi] Falha na reconexao. Reiniciando...");
      ESP.restart();
    }
  }
}

// ============================================================
// UDP (Protocolo padrao identico ao Agente 02)
// ============================================================
void stopUDP() {
  if (udp != nullptr) {
    udp->stop();
    delay(50);
    delete udp;
    udp = nullptr;
  }
}

void startUDP() {
  stopUDP();
  delay(100);
  udp = new WiFiUDP();
  if (!udp->begin(WAKE_PORT)) {
    Serial.println("[UDP] FALHA ao iniciar!");
    delete udp;
    udp = nullptr;
    return;
  }
  delay(100);
  Serial.printf("[UDP] Ouvindo na porta %d\n", WAKE_PORT);
}

// ============================================================
// WEBSOCKET CLIENT (Protocolo padrao identico ao Agente 02)
// ============================================================
void destroyWSClient() {
  if (wsClient != nullptr) {
    wsClient->close();
    delay(100);
    delete wsClient;
    wsClient = nullptr;
  }
}

void createWSClient() {
  destroyWSClient();
  delay(100);
  wsClient = new WebsocketsClient();
  wsClient->onMessage(onMessageCallback);
  wsClient->onEvent(onEventsCallback);
}

// ============================================================
// MÁQUINA DE ESTADOS (Protocolo padrao identico ao Agente 02)
// ============================================================
void setState(State s) {
  currentState = s;
  stateStartTime = millis();
  inCleanup = false;
  const char* names[] = {"STANDBY","CONNECTING","AUTHENTIC","COMMAND","ACK","DISCONNECTING"};
  Serial.printf("[State] -> %s\n", names[s]);
  Serial.flush();
}

void handleStandby() {
  yield();

  if (udp == nullptr) {
    startUDP();
    return;
  }

  int packetSize = udp->parsePacket();
  if (packetSize <= 0) return;

  char buffer[512];
  int len = udp->read(buffer, sizeof(buffer) - 1);
  if (len <= 0) return;
  buffer[len] = '\0';

  Serial.printf("[UDP] Pacote (%d bytes)\n", len);

  StaticJsonDocument<512> doc;
  if (deserializeJson(doc, buffer)) {
    Serial.println("[UDP] JSON invalido");
    return;
  }

  const char* pktType   = doc["type"];
  const char* agentID   = doc["agent_id"];
  const char* sessionID = doc["session_id"];
  const char* challenge = doc["challenge"];
  const char* authMAC   = doc["auth_mac"];

  if (!pktType || strcmp(pktType, "wake") != 0) return;
  if (!agentID || strcmp(agentID, AGENT_ID) != 0) return;
  if (!sessionID || !challenge || !authMAC) return;

  if (isSessionUsed(sessionID)) {
    Serial.println("[UDP] Rejeitado: session usada");
    return;
  }

  String payload = String(challenge) + String(agentID);
  String expected = hmacSha256(payload.c_str(), payload.length(), secretRaw, secretRawLen);

  if (!expected.equalsIgnoreCase(authMAC)) {
    Serial.println("[UDP] Rejeitado: HMAC invalido");
    return;
  }

  Serial.println("[UDP] Wake VALIDO!");
  pendingSessionID = sessionID;
  pendingChallenge = challenge;
  stopUDP();
  setState(STATE_CONNECTING);
}

void handleConnecting() {
  yield();

  if (millis() - stateStartTime > 10000) {
    Serial.println("[WS] Timeout (10s).");
    cleanupAndStandby();
    return;
  }

  if (wsClient == nullptr) {
    createWSClient();
  }

  String url = "ws://" + String(GATEWAY_HOST) + ":" + String(GATEWAY_PORT) + "/ws";
  Serial.printf("[WS] Conectando: %s\n", url.c_str());

  if (!wsClient->connect(url.c_str())) {
    Serial.println("[WS] Falha. Retry...");
    delay(500);
    return;
  }

  Serial.println("[WS] Conectado!");
  sendHello();
  setState(STATE_AUTHENTIC);
}

void handleAuthentic() {
  yield();
  if (wsClient) wsClient->poll();

  if (millis() - stateStartTime > 8000) {
    Serial.println("[Auth] Timeout (8s).");
    cleanupAndStandby();
    return;
  }
}

void handleCommand() {
  yield();
  if (wsClient) wsClient->poll();

  if (millis() - stateStartTime > 10000) {
    Serial.println("[Command] Timeout (10s).");
    cleanupAndStandby();
    return;
  }
}

void handleAck() {
  yield();
  if (wsClient) wsClient->poll();

  if (millis() - stateStartTime > 5000) {
    Serial.println("[ACK] Timeout.");
    sendBye("ack_timeout");
    setState(STATE_DISCONNECTING);
  }
}

void handleDisconnecting() {
  yield();
  if (wsClient) wsClient->poll();

  if (millis() - stateStartTime > 2000) {
    cleanupAndStandby();
  }
}

// ============================================================
// CALLBACKS WEBSOCKET (Mantido identico ao Agente 02, exceto "args")
// ============================================================
void onMessageCallback(WebsocketsMessage msg) {
  Serial.printf("[WS] Msg: %s\n", msg.data().c_str());

  // 768 bytes: comando v4.1 = command_id (UUID) + cmd + args (max. 256 B no Gateway)
  StaticJsonDocument<768> doc;
  if (deserializeJson(doc, msg.data())) return;

  const char* msgType = doc["type"];
  if (!msgType) return;

  if (strcmp(msgType, "welcome") == 0) {
    bool auth = doc["authenticated"] | false;
    if (auth) {
      Serial.println("[Auth] Welcome OK!");
      markSessionUsed(pendingSessionID);
      setState(STATE_COMMAND);
    } else {
      Serial.println("[Auth] REJEITADO!");
      cleanupAndStandby();
    }
  }
  else if (strcmp(msgType, "command") == 0) {
    currentCommandID = doc["command_id"].as<String>();
    const char* cmd   = doc["cmd"];
    if (!currentCommandID.length() || !cmd) return;

    // "args" e opcional (v4.1). Ausente => objeto nulo.
    JsonObject args = doc["args"].as<JsonObject>();

    Serial.printf("[Hardware] Executando comando: %s%s\n", cmd, args.isNull() ? "" : " (com args)");
    executeHardware(cmd, args);

    sendResult(resultadoStdout.c_str(), resultadoStderr.c_str());
    setState(STATE_ACK);
  }
}

void onEventsCallback(WebsocketsEvent ev, String data) {
  if (ev == WebsocketsEvent::ConnectionClosed) {
    Serial.println("[WS] Conexao fechada.");
    if (currentState != STATE_STANDBY && !inCleanup) {
      cleanupAndStandby();
    }
  }
}

// ============================================================
// FUNÇÕES DE COMUNICAÇÃO (Protocolo padrao identico ao Agente 02)
// ============================================================
void sendHello() {
  if (!wsClient) return;
  StaticJsonDocument<512> doc;
  doc["type"] = "hello";
  doc["agent_id"] = AGENT_ID;
  doc["session_id"] = pendingSessionID;
  String response = hmacSha256(pendingChallenge.c_str(), pendingChallenge.length(), secretRaw, secretRawLen);
  doc["challenge_response"] = response;
  doc["agent"] = "esp32-agent-sensores-motor";
  doc["version"] = "4.4";

  String out;
  serializeJson(doc, out);
  wsClient->send(out);
  Serial.println("[Hello] Enviado");
}

void sendResult(const char* resultOut, const char* resultErr) {
  if (!wsClient) return;
  StaticJsonDocument<512> doc;
  doc["type"] = "result";
  doc["command_id"] = currentCommandID;
  doc["stdout"] = resultOut;
  doc["stderr"] = resultErr;

  String out;
  serializeJson(doc, out);
  wsClient->send(out);
  Serial.printf("[Result] Out: %s | Err: %s\n", resultOut, resultErr);
}

void sendBye(const char* reason) {
  if (!wsClient) return;
  StaticJsonDocument<256> doc;
  doc["type"] = "bye";
  doc["session_id"] = pendingSessionID;
  doc["reason"] = reason;

  String out;
  serializeJson(doc, out);
  wsClient->send(out);
  Serial.printf("[Bye] %s\n", reason);
}

// ============================================================
// LÓGICA DE HARDWARE ESPECÍFICA (Agente 03 - Sensores + Motor)
// ============================================================

// ---------- SENSORES (leituras em conjunto, cache para o dashboard) ----------

float lerCorrenteA() {
  long soma = 0;
  const int amostras = 64; // Media de 64 amostras (rapido, sem delay bloqueante)
  for (int i = 0; i < amostras; i++) {
    soma += analogRead(PIN_CORRENTE);
  }
  int bruto = soma / amostras;
  float tensao = bruto * (3.3f / 4095.0f);
  return (tensao - ZERO_CORRENTE) / SENSIBILIDADE_ACS712;
}

float lerDistanciaCm() {
  digitalWrite(PIN_TRIG, LOW);
  delayMicroseconds(2);
  digitalWrite(PIN_TRIG, HIGH);
  delayMicroseconds(10);
  digitalWrite(PIN_TRIG, LOW);

  // Timeout de 30 ms (~5 m de alcance maximo)
  long duracao = pulseIn(PIN_ECHO, HIGH, 30000UL);
  if (duracao == 0) return -1.0f; // Sem eco: fora de alcance
  return duracao * SOUND_SPEED / 2.0f;
}

// Le TODOS os sensores em um unico ciclo e atualiza o cache.
// Os valores ficam disponiveis para o dashboard via capabilities.
void lerTodosSensores() {
  temperaturaC = bmp.readTemperature();
  pressaoPa    = bmp.readPressure();
  altitudeM    = bmp.readAltitude(PRESSAO_NIVEL_MAR);
  correnteA    = lerCorrenteA();
  distanciaCm  = lerDistanciaCm();
  ultimaLeituraSensores = millis();

  Serial.printf("[Sensores] T=%.2fC | P=%.0fPa | Alt=%.2fm | I=%.3fA | d=%.1fcm\n",
                temperaturaC, pressaoPa, altitudeM, correnteA, distanciaCm);
}

// Capabilities de leitura (nomes exatos exibidos no dashboard).
// Formato do stdout (o parser do dashboard e estrito):
//   individual : "<valor> <unidade>"            ex.: "23.45 C"
//   LER_SENSORES: "CHAVE=<valor> <unidade> | ..." ; "CHAVE=NA" quando sem leitura
void executarSensores(const char* cmd) {
  char buf[320];

  if (strcmp(cmd, "LER_SENSORES") == 0) {
    lerTodosSensores(); // Forca leitura conjunta fresca na hora da consulta

    // HC-SR04 sem eco => "NA" (o dashboard marca a amostra como invalida)
    char dist[24];
    if (distanciaCm < 0) snprintf(dist, sizeof(dist), "NA");
    else                 snprintf(dist, sizeof(dist), "%.1f cm", distanciaCm);

    snprintf(buf, sizeof(buf),
             "TEMPERATURA=%.2f C | PRESSAO=%.0f Pa | ALTITUDE=%.2f m | CORRENTE=%.3f A | DISTANCIA=%s",
             temperaturaC, pressaoPa, altitudeM, correnteA, dist);
    resultadoStdout = buf;
    resultadoStderr = "";
  }
  else if (strcmp(cmd, "TEMPERATURA") == 0) {
    snprintf(buf, sizeof(buf), "%.2f C", temperaturaC);
    resultadoStdout = buf; resultadoStderr = "";
  }
  else if (strcmp(cmd, "PRESSAO") == 0) {
    snprintf(buf, sizeof(buf), "%.0f Pa", pressaoPa);
    resultadoStdout = buf; resultadoStderr = "";
  }
  else if (strcmp(cmd, "ALTITUDE") == 0) {
    snprintf(buf, sizeof(buf), "%.2f m", altitudeM);
    resultadoStdout = buf; resultadoStderr = "";
  }
  else if (strcmp(cmd, "CORRENTE") == 0) {
    snprintf(buf, sizeof(buf), "%.3f A", correnteA);
    resultadoStdout = buf; resultadoStderr = "";
  }
  else if (strcmp(cmd, "DISTANCIA") == 0) {
    if (distanciaCm < 0) {
      resultadoStdout = "";
      resultadoStderr = "Distancia fora de alcance (sem eco do HC-SR04).";
    } else {
      snprintf(buf, sizeof(buf), "%.1f cm", distanciaCm);
      resultadoStdout = buf; resultadoStderr = "";
    }
  }
  else {
    resultadoStdout = "";
    resultadoStderr = "";
  }
}

// ---------- MOTOR DE PASSO (pulsos identicos ao exemplo, porem nao-bloqueante) ----------

void atualizarMotorPasso() {
  if (!motorRodando) return;

  // Seguranca: para automaticamente apos o tempo maximo de operacao
  // (um novo START/MOVER renova esta janela: inicioMotorMs = millis())
  if (millis() - inicioMotorMs >= TEMPO_MAX_MOTOR_MS) {
    pararMotor("timeout de seguranca (60s)");
    return;
  }

  // Pulso identico ao exemplo do motordepasso.ino:
  //   digitalWrite(pulPin, HIGH); delayMicroseconds(pulseDelay);
  //   digitalWrite(pulPin, LOW);  delayMicroseconds(pulseDelay);
  // A mesma forma de onda e gerada aqui sem travar o loop,
  // mantendo a rede (UDP/WebSocket) e os sensores ativos.
  if (micros() - ultimoPulsoUs >= motorPulseDelay) {
    ultimoPulsoUs = micros();
    estadoPulso = !estadoPulso;
    digitalWrite(pulPin, estadoPulso ? HIGH : LOW);

    // MOVER: um passo completo = HIGH + LOW. Conta na borda de descida.
    if (motorFinito && !estadoPulso) {
      if (motorPassosRestantes > 0) motorPassosRestantes--;
      if (motorPassosRestantes == 0) {
        desligarSaidaMotor();
        Serial.println("[Motor] Movimento concluido (passos esgotados).");
      }
    }
  }
}

// Leva as saidas ao repouso (PUL em LOW, igual ao exemplo) sem mexer no
// resultado do comando em andamento.
void desligarSaidaMotor() {
  motorRodando = false;
  motorFinito = false;
  motorPassosRestantes = 0;
  estadoPulso = false;
  digitalWrite(pulPin, LOW);
}

// START: giro continuo, sem argumentos, sempre com os padroes do exemplo
// (sentido "direita", 400 us). Substitui qualquer movimento em curso.
void iniciarMotor() {
  digitalWrite(dirPin, DIR_DIREITA_NIVEL_ALTO ? HIGH : LOW);

  motorPulseDelay = PULSO_US_NORMAL;
  motorFinito = false;
  motorPassosRestantes = 0;
  estadoPulso = false;
  digitalWrite(pulPin, LOW);
  ultimoPulsoUs = micros();
  inicioMotorMs = millis();   // (re)inicia a janela de seguranca de 60s
  motorRodando = true;

  resultadoStdout = "Motor de passo INICIADO (padrao do exemplo: 400us/pulso).";
  resultadoStderr = "";
}

void pararMotor(const char* motivo) {
  desligarSaidaMotor();

  char buf[160];
  snprintf(buf, sizeof(buf), "Motor de passo PARADO (%s).", motivo);
  resultadoStdout = buf;
  resultadoStderr = "";
}

void erroMotor(const char* msg) {
  resultadoStdout = "";
  resultadoStderr = msg;
  Serial.printf("[Motor] MOVER recusado: %s\n", msg);
}

// MOVER: args {"dir":"direita|esquerda","steps":1..MOTOR_MAX_PASSOS,"speed":"lenta|normal|rapida"}
// Valida tudo ANTES de tocar no hardware: argumento invalido nunca move o motor.
// O resultado confirma que o movimento foi INICIADO; o firmware nao informa
// quando termina (a sessao fecha antes). O movimento continua apos o Bye.
void moverMotor(JsonObject args) {
  if (args.isNull()) {
    erroMotor("MOVER requer args {dir, steps, speed}.");
    return;
  }

  const char* dir   = args["dir"];
  const char* speed = args["speed"];

  if (!dir || (strcmp(dir, "direita") != 0 && strcmp(dir, "esquerda") != 0)) {
    erroMotor("MOVER: dir invalido (use direita ou esquerda).");
    return;
  }

  unsigned int pulso = 0;
  if (speed && strcmp(speed, "lenta") == 0)       pulso = PULSO_US_LENTA;
  else if (speed && strcmp(speed, "normal") == 0) pulso = PULSO_US_NORMAL;
  else if (speed && strcmp(speed, "rapida") == 0) pulso = PULSO_US_RAPIDA;
  else {
    erroMotor("MOVER: speed invalido (use lenta, normal ou rapida).");
    return;
  }

  if (!args["steps"].is<long>()) {
    erroMotor("MOVER: steps deve ser um inteiro.");
    return;
  }
  long steps = args["steps"].as<long>();
  if (steps < 1 || (unsigned long)steps > MOTOR_MAX_PASSOS) {
    char msg[80];
    snprintf(msg, sizeof(msg), "MOVER: steps fora do limite (1 a %lu).", MOTOR_MAX_PASSOS);
    erroMotor(msg);
    return;
  }

  bool direita = (strcmp(dir, "direita") == 0);
  digitalWrite(dirPin, (direita == DIR_DIREITA_NIVEL_ALTO) ? HIGH : LOW);

  motorPulseDelay = pulso;
  motorFinito = true;
  motorPassosRestantes = (unsigned long)steps;
  estadoPulso = false;
  digitalWrite(pulPin, LOW);
  ultimoPulsoUs = micros();   // 1o pulso so depois de 'pulso' us: DIR ja estabilizou
  inicioMotorMs = millis();   // janela de seguranca de 60 s
  motorRodando = true;

  char buf[160];
  snprintf(buf, sizeof(buf), "Movimento INICIADO: %s, %ld passos, %s (%uus/pulso).",
           dir, steps, speed, pulso);
  resultadoStdout = buf;
  resultadoStderr = "";
  Serial.printf("[Motor] %s\n", buf);
}

// Comandos do motor: START e PARE (sem argumentos) e MOVER (com args).
void executarMotor(const char* cmd, JsonObject args) {
  if (strcmp(cmd, "START") == 0) {
    iniciarMotor();
  }
  else if (strcmp(cmd, "PARE") == 0) {
    pararMotor("comando PARE do dashboard");
  }
  else if (strcmp(cmd, "MOVER") == 0) {
    moverMotor(args);
  }
  else {
    resultadoStdout = "";
    resultadoStderr = "";
  }
}

void executeHardware(const char* cmd, JsonObject args) {
  // 1) Sensores (leituras em conjunto / valores individuais do cache)
  executarSensores(cmd);
  if (resultadoStdout.length() > 0 || resultadoStderr.length() > 0) return;

  // 2) Motor de passo (START, PARE e MOVER)
  executarMotor(cmd, args);
  if (resultadoStdout.length() > 0 || resultadoStderr.length() > 0) return;

  // 3) Comando desconhecido
  resultadoStdout = "";
  resultadoStderr = "Comando desconhecido pelo agente.";
}

// ============================================================
// CLEANUP E UTILITÁRIOS (Protocolo padrao identico ao Agente 02)
// ============================================================
void cleanupAndStandby() {
  if (inCleanup) return;
  inCleanup = true;

  // IMPORTANTE: o motor NAO para aqui! A sessao sempre fecha apos o comando
  // (ACK 5s + DISCONNECTING 2s), mas o motor deve continuar girando ate o
  // PARE chegar numa nova sessao, o MOVER terminar seus passos, ou o timeout
  // de seguranca de 60s. Os pulsos sao gerados no loop(), fora da maquina
  // de estados de rede.

  totalOps++;
  Serial.println("\n[Cleanup] Retornando para STANDBY...");
  Serial.printf("[Cleanup] Total ops: %lu | Motor rodando: %s\n",
                totalOps, motorRodando ? "SIM" : "nao");

  destroyWSClient();

  pendingSessionID = "";
  pendingChallenge = "";
  currentCommandID = "";

  createWSClient();
  startUDP();

  setState(STATE_STANDBY);
  checkHeap();

  if (totalOps % 4 == 0) {
    Serial.println("[Cache] Limpando sessoes usadas.");
    usedSessionCount = 0;
  }

  Serial.println("[STANDBY] Pronto.\n");
  Serial.flush();
}

bool parseHex(const char* hex, uint8_t* out, size_t maxLen, size_t* outLen) {
  size_t len = strlen(hex);
  if (len % 2 != 0 || len / 2 > maxLen) return false;
  for (size_t i = 0; i < len / 2; i++) {
    char buf[3] = {hex[i*2], hex[i*2+1], '\0'};
    out[i] = (uint8_t) strtol(buf, NULL, 16);
  }
  *outLen = len / 2;
  return true;
}

String hmacSha256(const char* message, size_t msgLen, const uint8_t* key, size_t keyLen) {
  uint8_t out[32];
  mbedtls_md_context_t ctx;
  const mbedtls_md_info_t* info = mbedtls_md_info_from_type(MBEDTLS_MD_SHA256);

  mbedtls_md_init(&ctx);
  mbedtls_md_setup(&ctx, info, 1);
  mbedtls_md_hmac_starts(&ctx, key, keyLen);
  mbedtls_md_hmac_update(&ctx, (const uint8_t*)message, msgLen);
  mbedtls_md_hmac_finish(&ctx, out);
  mbedtls_md_free(&ctx);

  char hexStr[65];
  for (int i = 0; i < 32; i++) {
    sprintf(&hexStr[i*2], "%02x", out[i]);
  }
  hexStr[64] = '\0';
  return String(hexStr);
}

bool isSessionUsed(const String& sid) {
  for (int i = 0; i < usedSessionCount; i++) {
    if (usedSessions[i] == sid) return true;
  }
  return false;
}

void markSessionUsed(const String& sid) {
  if (isSessionUsed(sid)) return;
  if (usedSessionCount >= 4) {
    Serial.println("[Cache] Cheio! Limpando.");
    usedSessionCount = 0;
  }
  usedSessions[usedSessionCount++] = sid;
}
