/*
  Tunneus Subagent ESP32 v4.2-STABLE

  CORRECOES CRITICAS:
  - State Watchdog: nunca fica travado fora de STANDBY (>15s)
  - WiFi auto-reconnect + check a cada 5s (era 30s)
  - Delays maiores em stopUDP/destroyWSClient (liberacao de porta/socket)
 /*
  Tunneus Subagent ESP32 v4.3-MARATHON

  CORRECOES PARA LONGA DURACAO (3+ horas na feira):

  1. UDP Socket Refresh: recria o socket UDP a cada 5 minutos em STANDBY
     - Resolve: socket LwIP morre silenciosamente apos ~20 minutos

  2. Reboot Preventivo: reinicia o ESP a cada 60 minutos automaticamente
     - Limpa fragmentacao de heap, estados fantasmas, leaks do WiFi stack

  3. WiFi Recovery Agresivo: se nao reconecta em 5s, reinicia imediatamente
     - Nao fica tentando indefinidamente

  4. Heap Check a cada operacao + reinicio automatico < 20KB

  5. State Watchdog: nunca fica travado >15s fora de STANDBY

  6. ACK Instantaneo: envia Bye imediatamente apos Result

  7. Delays maiores em cleanup (300ms) para garantir liberacao de recursos
*/

#include <WiFi.h>
#include <WiFiUdp.h>
#include <ArduinoWebsockets.h>
#include <ArduinoJson.h>

using namespace websockets;

// ============================================================
// CONFIGURACOES
// ============================================================
const char* WIFI_SSID     = "SUA_REDE_WIFI";
const char* WIFI_PASSWORD = "SUA_SENHA_WIFI";
const char* GATEWAY_HOST  = "192.168.1.10";
const char* AGENT_ID      = "esp32-01";
const char* SECRET_HEX    = "000102030405060708090a0b0c0d0e0f101112131415161718191a1b1c1d1e1f";

// IP ESTATICO (descomente para eliminar variacao de DHCP na feira)
// const bool USE_STATIC_IP = true;
// IPAddress LOCAL_IP(192, 168, 18, 100);
// IPAddress GATEWAY_IP(192, 168, 18, 1);
// IPAddress SUBNET(255, 255, 255, 0);
// IPAddress DNS(192, 168, 18, 1);

#include "mbedtls/md.h"

#define WAKE_PORT      18081
#define GATEWAY_PORT   18080
#define LED_PIN        2

// Timeouts
#define T_CONNECTING    10000
#define T_AUTHENTIC     8000
#define T_COMMAND       10000
#define T_ACK           500
#define T_DISCONNECTING 1000
#define T_WATCHDOG      15000

// Intervalos de manutencao
#define WIFI_CHECK_MS       5000     // Verifica WiFi a cada 5s
#define UDP_REFRESH_MS      300000   // Recria socket UDP a cada 5 min
#define REBOOT_INTERVAL_MS  3600000  // Reboot preventivo a cada 60 min
#define HEAP_LOG_INTERVAL   60000    // Loga heap a cada 60s

enum State {
  STATE_STANDBY,
  STATE_CONNECTING,
  STATE_AUTHENTIC,
  STATE_COMMAND,
  STATE_ACK,
  STATE_DISCONNECTING
};

// ============================================================
// GLOBAIS
// ============================================================
WiFiUDP*          udp = nullptr;
WebsocketsClient* wsClient = nullptr;
State             currentState = STATE_STANDBY;
uint8_t           secretRaw[64];
size_t            secretRawLen = 0;
String            pendingSessionID;
String            pendingChallenge;
String            currentCommandID;

String            usedSessions[4];
int               usedSessionCount = 0;
unsigned long     stateStartTime = 0;
unsigned long     totalOps = 0;
bool              inCleanup = false;
unsigned long     lastWiFiCheck = 0;
unsigned long     lastUDPRefresh = 0;
unsigned long     lastHeapLog = 0;
unsigned long     bootTime = 0;

// ============================================================
// PROTOTIPOS
// ============================================================
void setState(State s);
void startUDP();
void stopUDP();
void refreshUDPIfNeeded();
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
void executeHardware(const char* cmd);
void checkHeap();
void logHeap();
void checkWiFi();
void connectWiFi();
void maybeReboot();

// ============================================================
// SETUP
// ============================================================
void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(LED_PIN, OUTPUT);
  digitalWrite(LED_PIN, LOW);

  // Pisca LED 3x = boot
  for (int i = 0; i < 3; i++) {
    digitalWrite(LED_PIN, HIGH); delay(80);
    digitalWrite(LED_PIN, LOW);  delay(80);
  }

  Serial.println("\n===================================");
  Serial.println("Tunneus Subagent ESP32 v4.3-MARATHON");
  Serial.println("===================================");

  if (!parseHex(SECRET_HEX, secretRaw, sizeof(secretRaw), &secretRawLen)) {
    Serial.println("[FATAL] Secret HEX invalido!");
    while (true) { delay(1000); }
  }
  Serial.printf("[Auth] Secret: %d bytes\n", secretRawLen);

  bootTime = millis();
  connectWiFi();
  createWSClient();
  startUDP();
  setState(STATE_STANDBY);

  Serial.println("[Setup] === PRONTO ===");
  logHeap();
  Serial.flush();
}

void connectWiFi() {
  Serial.printf("[WiFi] Conectando a %s\n", WIFI_SSID);

  WiFi.setAutoReconnect(true);
  WiFi.persistent(true);

  // IP estatico opcional
  // if (USE_STATIC_IP) WiFi.config(LOCAL_IP, GATEWAY_IP, SUBNET, DNS);

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 40) {
    delay(250);
    Serial.print(".");
    retries++;
  }

  if (WiFi.status() != WL_CONNECTED) {
    Serial.println("\n[WiFi] FALHA! Reiniciando...");
    ESP.restart();
  }

  Serial.printf("\n[WiFi] OK! IP=%s RSSI=%d dBm\n",
                WiFi.localIP().toString().c_str(), WiFi.RSSI());
}

// ============================================================
// LOOP
// ============================================================
void loop() {
  unsigned long now = millis();

  // 1. STATE WATCHDOG — nunca ficar >15s fora de STANDBY
  if (currentState != STATE_STANDBY && now - stateStartTime > T_WATCHDOG) {
    Serial.printf("[WATCHDOG] Travado em estado %d por %lu ms! Forcando STANDBY.\n",
                  currentState, now - stateStartTime);
    cleanupAndStandby();
  }

  // 2. WiFi CHECK a cada 5s
  if (now - lastWiFiCheck > WIFI_CHECK_MS) {
    lastWiFiCheck = now;
    checkWiFi();
  }

  // 3. UDP REFRESH a cada 5 min em STANDBY
  if (currentState == STATE_STANDBY && now - lastUDPRefresh > UDP_REFRESH_MS) {
    lastUDPRefresh = now;
    Serial.println("[UDP] Refresh preventivo do socket...");
    startUDP();  // stopUDP + startUDP
  }

  // 4. HEAP LOG a cada 60s
  if (now - lastHeapLog > HEAP_LOG_INTERVAL) {
    lastHeapLog = now;
    logHeap();
  }

  // 5. REBOOT PREVENTIVO a cada 60 min
  maybeReboot();

  // Maquina de estados
  switch (currentState) {
    case STATE_STANDBY:       handleStandby();       break;
    case STATE_CONNECTING:    handleConnecting();    break;
    case STATE_AUTHENTIC:     handleAuthentic();     break;
    case STATE_COMMAND:       handleCommand();       break;
    case STATE_ACK:           handleAck();           break;
    case STATE_DISCONNECTING: handleDisconnecting(); break;
  }
}

// ============================================================
// MANUTENCAO
// ============================================================
void checkWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println("[WiFi] DESCONECTADO! Tentando reconectar...");
  WiFi.reconnect();

  int retries = 0;
  while (WiFi.status() != WL_CONNECTED && retries < 20) {
    delay(250);
    retries++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("[WiFi] Reconectado. IP=%s\n", WiFi.localIP().toString().c_str());
  } else {
    Serial.println("[WiFi] FALHA na reconexao. Reiniciando ESP...");
    ESP.restart();
  }
}

void logHeap() {
  int freeHeap = ESP.getFreeHeap();
  int maxBlock = ESP.getMaxAllocHeap();
  int frag = (freeHeap > 0) ? (100 - (maxBlock * 100 / freeHeap)) : 0;
  Serial.printf("[Heap] Livre=%d | BlocoMax=%d | Frag=%d%% | Ops=%lu | Uptime=%.1fmin\n",
                freeHeap, maxBlock, frag, totalOps, (millis() - bootTime) / 60000.0);
}

void checkHeap() {
  int freeHeap = ESP.getFreeHeap();
  if (freeHeap < 20000) {
    Serial.printf("[Heap] CRITICO: %d bytes! Reiniciando...\n", freeHeap);
    ESP.restart();
  }
}

void maybeReboot() {
  unsigned long uptime = millis() - bootTime;
  if (uptime > REBOOT_INTERVAL_MS) {
    // So reinicia se estiver em STANDBY (seguro)
    if (currentState == STATE_STANDBY) {
      Serial.println("[Reboot] Reboot preventivo de 60min em STANDBY.");
      ESP.restart();
    } else {
      Serial.println("[Reboot] Aguardando STANDBY para reboot preventivo...");
    }
  }
}

// ============================================================
// UDP
// ============================================================
void stopUDP() {
  if (udp != nullptr) {
    udp->stop();
    delay(200);
    delete udp;
    udp = nullptr;
  }
}

void startUDP() {
  stopUDP();
  delay(200);
  udp = new WiFiUDP();
  if (!udp->begin(WAKE_PORT)) {
    Serial.println("[UDP] FALHA ao iniciar! Tentando novamente...");
    delete udp;
    udp = nullptr;
    delay(500);
    udp = new WiFiUDP();
    if (!udp->begin(WAKE_PORT)) {
      Serial.println("[UDP] FALHA definitiva! Reiniciando ESP...");
      ESP.restart();
    }
  }
  Serial.printf("[UDP] Ouvindo na porta %d\n", WAKE_PORT);
}

// ============================================================
// WEBSOCKET
// ============================================================
void destroyWSClient() {
  if (wsClient != nullptr) {
    wsClient->close();
    delay(200);
    delete wsClient;
    wsClient = nullptr;
  }
}

void createWSClient() {
  destroyWSClient();
  delay(200);
  wsClient = new WebsocketsClient();
  wsClient->onMessage(onMessageCallback);
  wsClient->onEvent(onEventsCallback);
}

// ============================================================
// ESTADOS
// ============================================================
void setState(State s) {
  currentState = s;
  stateStartTime = millis();
  inCleanup = false;
  const char* names[] = {"STANDBY","CONNECTING","AUTHENTIC","COMMAND","ACK","DISCONNECTING"};
  Serial.printf("[State] -> %s\n", names[s]);
  Serial.flush();
}

// --- STANDBY ---
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
  DeserializationError err = deserializeJson(doc, buffer);
  if (err) {
    Serial.printf("[UDP] JSON invalido: %s\n", err.c_str());
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

// --- CONNECTING ---
void handleConnecting() {
  yield();

  if (millis() - stateStartTime > T_CONNECTING) {
    Serial.println("[WS] Timeout CONNECTING.");
    cleanupAndStandby();
    return;
  }

  if (wsClient == nullptr) createWSClient();

  String url = "ws://" + String(GATEWAY_HOST) + ":" + String(GATEWAY_PORT) + "/ws";
  Serial.printf("[WS] Conectando: %s\n", url.c_str());

  if (!wsClient->connect(url.c_str())) {
    Serial.println("[WS] Falha. Retry rapido...");
    delay(200);
    return;
  }

  Serial.println("[WS] Conectado!");
  sendHello();
  setState(STATE_AUTHENTIC);
}

// --- AUTHENTIC ---
void handleAuthentic() {
  yield();
  if (wsClient) wsClient->poll();

  if (millis() - stateStartTime > T_AUTHENTIC) {
    Serial.println("[Auth] Timeout.");
    cleanupAndStandby();
    return;
  }
}

// --- COMMAND ---
void handleCommand() {
  yield();
  if (wsClient) wsClient->poll();

  if (millis() - stateStartTime > T_COMMAND) {
    Serial.println("[Command] Timeout.");
    cleanupAndStandby();
    return;
  }
}

// --- ACK ---
void handleAck() {
  yield();
  if (wsClient) wsClient->poll();

  // Envia Bye imediatamente — o Gateway ja processou o result
  Serial.println("[ACK] Enviando Bye imediato.");
  sendBye("completed");
  setState(STATE_DISCONNECTING);
}

// --- DISCONNECTING ---
void handleDisconnecting() {
  yield();
  if (wsClient) wsClient->poll();

  if (millis() - stateStartTime > T_DISCONNECTING) {
    cleanupAndStandby();
  }
}

// ============================================================
// CALLBACKS WS
// ============================================================
void onMessageCallback(WebsocketsMessage msg) {
  Serial.printf("[WS] Msg: %s\n", msg.data().c_str());

  StaticJsonDocument<512> doc;
  DeserializationError err = deserializeJson(doc, msg.data());
  if (err) {
    Serial.printf("[WS] JSON invalido: %s\n", err.c_str());
    return;
  }

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
    const char* cmdID = doc["command_id"];
    const char* cmd   = doc["cmd"];
    if (!cmdID || !cmd) return;

    currentCommandID = cmdID;
    Serial.printf("[HW] Executando: %s\n", cmd);
    executeHardware(cmd);

    const char* resultText = (digitalRead(LED_PIN) == HIGH) ? "LED ligado" : "LED desligado";
    Serial.printf("[HW] Resultado: %s\n", resultText);
    sendResult(resultText, "");
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
// ACOES
// ============================================================
void sendHello() {
  if (!wsClient) return;
  StaticJsonDocument<512> doc;
  doc["type"] = "hello";
  doc["agent_id"] = AGENT_ID;
  doc["session_id"] = pendingSessionID;
  String response = hmacSha256(pendingChallenge.c_str(), pendingChallenge.length(), secretRaw, secretRawLen);
  doc["challenge_response"] = response;
  doc["agent"] = "esp32-agent";
  doc["version"] = "4.3";

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
  Serial.printf("[Result] %s\n", resultOut);
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

void executeHardware(const char* cmd) {
  if (strcmp(cmd, "LED_ON") == 0) {
    digitalWrite(LED_PIN, HIGH);
  } else if (strcmp(cmd, "LED_OFF") == 0) {
    digitalWrite(LED_PIN, LOW);
  } else {
    Serial.printf("[HW] Comando desconhecido: %s\n", cmd);
  }
}

// ============================================================
// CLEANUP
// ============================================================
void cleanupAndStandby() {
  if (inCleanup) return;
  inCleanup = true;

  totalOps++;
  Serial.println("\n[Cleanup] Retornando para STANDBY...");

  destroyWSClient();
  delay(100);

  pendingSessionID = "";
  pendingChallenge = "";
  currentCommandID = "";

  createWSClient();
  startUDP();

  setState(STATE_STANDBY);
  checkHeap();

  // Limpa cache a cada 4 operacoes
  if (totalOps % 4 == 0) {
    Serial.println("[Cache] Limpando.");
    usedSessionCount = 0;
  }

  Serial.printf("[STANDBY] Pronto. Total ops=%lu\n\n", totalOps);
  Serial.flush();
}

// ============================================================
// UTILITARIOS
// ============================================================
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
