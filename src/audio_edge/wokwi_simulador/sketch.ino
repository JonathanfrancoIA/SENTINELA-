/*
 * ============================================================
 * SENTINELA — ESP32 VIRTUAL (Wokwi)
 * ============================================================
 * Versão de DEMONSTRAÇÃO do "ouvido" do SENTINELA para rodar
 * 100% online no simulador Wokwi (https://wokwi.com), sem
 * hardware físico — ideal para apresentar à banca.
 *
 * O que esta versão simula:
 *   - O ESP32 conectado ao WiFi e a um broker MQTT REAL
 *     (broker.hivemq.com), publicando no mesmo tópico/payload
 *     do firmware de produção: "sentinela/alertas".
 *   - A SAÍDA do modelo TinyML (probabilidade de motosserra) é
 *     controlada pelo POTENCIÔMETRO (0.00–1.00). No hardware
 *     real, esse valor vem da inferência sobre o áudio do
 *     microfone I2S INMP441.
 *   - O BOTÃO "simular motosserra" força prob = 0.95 por alguns
 *     segundos (dispara um alerta CONFIRMADO ao vivo).
 *   - LEDs de status: verde = normal, amarelo = processando,
 *     vermelho = ameaça detectada.
 *   - OLED mostra probabilidade, barra e status local.
 *
 * Diferença para o hardware: o Wokwi não injeta áudio real num
 * microfone I2S simulado, então a inferência de áudio em si roda
 * no ESP32 físico. Aqui demonstramos o FLUXO edge → nuvem.
 *
 * SENTINELA Project — FIAP Global Solution 2026.1
 * ============================================================
 */

#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ── WiFi (no Wokwi use SEMPRE "Wokwi-GUEST", sem senha) ──────
const char* WIFI_SSID     = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";

// ── MQTT (broker público para a demo) ───────────────────────
const char* MQTT_SERVER       = "broker.hivemq.com";
const int   MQTT_PORT         = 1883;
const char* MQTT_TOPIC        = "sentinela/alertas";
const char* MQTT_TOPIC_STATUS = "sentinela/status";

// ── Identidade do sensor ────────────────────────────────────
const char* SENSOR_ID  = "ESP32-FLORESTA-AM-01";
const float SENSOR_LAT = -3.4653;
const float SENSOR_LON = -62.2159;

// ── Pinos (iguais ao firmware de produção) ──────────────────
#define LED_VERDE    25
#define LED_AMARELO  26
#define LED_VERMELHO 27
#define PINO_POT     34   // ADC1 — entrada do potenciômetro
#define PINO_BOTAO    4   // botão "simular motosserra" (INPUT_PULLUP)

// ── Thresholds (iguais ao firmware) ─────────────────────────
#define THRESHOLD_AMEACA       0.70f
#define THRESHOLD_CONFIRMACAO  0.85f
const unsigned long INTERVALO_ALERTA_MS = 8000;  // 8 s entre publicações

// ── OLED ────────────────────────────────────────────────────
#define OLED_W 128
#define OLED_H 64
Adafruit_SSD1306 display(OLED_W, OLED_H, &Wire, -1);

// ── Estado ──────────────────────────────────────────────────
WiFiClient   espClient;
PubSubClient mqtt(espClient);
unsigned long ultimo_alerta_ms = 0;
unsigned long botao_ate_ms = 0;
int alertas_consecutivos = 0;

// ─────────────────────────────────────────────────────────────
void set_leds(bool v, bool a, bool r) {
  digitalWrite(LED_VERDE,    v ? HIGH : LOW);
  digitalWrite(LED_AMARELO,  a ? HIGH : LOW);
  digitalWrite(LED_VERMELHO, r ? HIGH : LOW);
}

void conectar_wifi() {
  Serial.printf("[WiFi] Conectando a %s ", WIFI_SSID);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  while (WiFi.status() != WL_CONNECTED) {
    delay(250);
    Serial.print(".");
  }
  Serial.printf("\n[WiFi] OK! IP: %s\n", WiFi.localIP().toString().c_str());
}

void reconectar_mqtt() {
  int tentativas = 0;
  while (!mqtt.connected() && tentativas < 5) {
    String clientId = String("SENTINELA-") + SENSOR_ID + "-" + String(random(0xffff), HEX);
    Serial.print("[MQTT] Conectando ...");
    if (mqtt.connect(clientId.c_str())) {
      Serial.println(" conectado!");
      mqtt.publish(MQTT_TOPIC_STATUS,
        (String("{\"status\":\"online\",\"sensor_id\":\"") + SENSOR_ID + "\"}").c_str());
    } else {
      Serial.printf(" falhou (rc=%d). Nova tentativa em 2s\n", mqtt.state());
      delay(2000);
      tentativas++;
    }
  }
}

void publicar_alerta(float prob, const char* tipo) {
  StaticJsonDocument<256> doc;
  doc["sensor_id"]     = SENSOR_ID;
  doc["tipo"]          = tipo;
  doc["probabilidade"] = prob;
  doc["lat"]           = SENSOR_LAT;
  doc["lon"]           = SENSOR_LON;
  doc["timestamp_ms"]  = millis();
  doc["nivel_alerta"]  = (prob >= THRESHOLD_CONFIRMACAO) ? "ALTO" : "MEDIO";

  char payload[256];
  serializeJson(doc, payload);
  if (mqtt.connected()) {
    mqtt.publish(MQTT_TOPIC, payload);
    Serial.printf("[MQTT] >> %s\n", payload);
  }
}

void desenhar_oled(float prob, const char* status, uint16_t cor_status) {
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);

  // Cabeçalho
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.print("SENTINELA  ");
  display.print(WiFi.status() == WL_CONNECTED ? "WiFi:OK" : "WiFi:--");

  display.drawFastHLine(0, 10, OLED_W, SSD1306_WHITE);

  // Probabilidade grande
  display.setTextSize(2);
  display.setCursor(0, 16);
  display.printf("%.0f%%", prob * 100.0f);

  // Status
  display.setTextSize(1);
  display.setCursor(58, 16);
  display.print("MOTOSSERRA");
  display.setCursor(58, 26);
  display.print(status);

  // Barra de probabilidade
  int barW = (int)(prob * (OLED_W - 4));
  display.drawRect(0, 40, OLED_W, 12, SSD1306_WHITE);
  display.fillRect(2, 42, barW, 8, SSD1306_WHITE);

  // Linha do threshold (70%)
  int xth = (int)(THRESHOLD_AMEACA * (OLED_W - 4)) + 2;
  display.drawFastVLine(xth, 38, 16, SSD1306_WHITE);

  // Rodapé
  display.setCursor(0, 56);
  display.print(SENSOR_ID);
  display.display();
}

// ─────────────────────────────────────────────────────────────
void setup() {
  Serial.begin(115200);
  delay(300);

  pinMode(LED_VERDE,    OUTPUT);
  pinMode(LED_AMARELO,  OUTPUT);
  pinMode(LED_VERMELHO, OUTPUT);
  pinMode(PINO_BOTAO,   INPUT_PULLUP);
  set_leds(false, true, false);

  Wire.begin(21, 22);
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println("[OLED] SSD1306 nao encontrado");
  } else {
    display.clearDisplay();
    display.setTextSize(1);
    display.setTextColor(SSD1306_WHITE);
    display.setCursor(0, 24);
    display.println("  SENTINELA v1.0");
    display.println("  Iniciando...");
    display.display();
  }

  Serial.println("=============================================");
  Serial.println("  SENTINELA — ESP32 VIRTUAL (Wokwi)");
  Serial.println("  FIAP Global Solution 2026.1");
  Serial.println("=============================================");

  conectar_wifi();
  mqtt.setServer(MQTT_SERVER, MQTT_PORT);
  mqtt.setBufferSize(256);
  Serial.printf("[INFO] Sensor: %s  (%.4f, %.4f)\n", SENSOR_ID, SENSOR_LAT, SENSOR_LON);
  Serial.println("[INFO] Gire o potenciometro = probabilidade do modelo.");
  Serial.println("[INFO] Botao = simular motosserra (prob 0.95).");
}

void loop() {
  if (WiFi.status() == WL_CONNECTED && !mqtt.connected()) reconectar_mqtt();
  mqtt.loop();

  // 1. "Saída do modelo" = potenciômetro (0..1)
  float prob = analogRead(PINO_POT) / 4095.0f;

  // 2. Botão força motosserra por 4 s
  if (digitalRead(PINO_BOTAO) == LOW) botao_ate_ms = millis() + 4000;
  if (millis() < botao_ate_ms) prob = max(prob, 0.95f);

  // 3. Decisão + LEDs + OLED
  const char* status;
  if (prob >= THRESHOLD_AMEACA) {
    alertas_consecutivos++;
    set_leds(false, false, true);                 // vermelho
    status = (prob >= THRESHOLD_CONFIRMACAO) ? "CONFIRMADO" : "SUSPEITO";

    unsigned long agora = millis();
    if (agora - ultimo_alerta_ms >= INTERVALO_ALERTA_MS) {
      const char* tipo = (prob >= THRESHOLD_CONFIRMACAO)
                         ? "MOTOSSERRA_CONFIRMADO" : "MOTOR_SUSPEITO";
      publicar_alerta(prob, tipo);
      ultimo_alerta_ms = agora;
    }
    Serial.printf("[ALERTA] prob=%.2f tipo=%s evento#%d\n",
                  prob, status, alertas_consecutivos);
  } else {
    alertas_consecutivos = 0;
    set_leds(true, false, false);                 // verde
    status = "NORMAL";
  }

  desenhar_oled(prob, status,
                prob >= THRESHOLD_AMEACA ? SSD1306_WHITE : SSD1306_WHITE);
  delay(400);
}
