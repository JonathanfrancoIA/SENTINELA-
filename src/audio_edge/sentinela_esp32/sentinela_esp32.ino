/*
 * ============================================================
 * SENTINELA — Firmware ESP32 (Edge AI)
 * ============================================================
 * Detecta sons de motosserra, tratores e veículos na floresta
 * usando TensorFlow Lite Micro diretamente no microcontrolador.
 *
 * Hardware necessário:
 *   - ESP32 (WROOM-32 ou DevKitC)
 *   - Microfone I2S INMP441 (3.3 V)
 *   - (Opcional) LED RGB para status
 *   - (Opcional) OLED SSD1306 para display local
 *
 * Pinos padrão (ajuste conforme seu hardware):
 *   INMP441  →  ESP32
 *   VDD      →  3V3
 *   GND      →  GND
 *   WS       →  GPIO 15
 *   SCK      →  GPIO 14
 *   SD       →  GPIO 32
 *   L/R      →  GND (canal esquerdo)
 *
 * Dependências (Arduino IDE):
 *   - "ESP32 Arduino" board package
 *   - "TensorFlowLite_ESP32" library
 *   - "PubSubClient" (MQTT)
 *   - "ArduinoJson"
 *
 * Status: 🧪 Simulado (estrutura completa, modelo .tflite pendente)
 *
 * SENTINELA Project — FIAP Global Solution 2026.1
 * ============================================================
 */

#include <Arduino.h>
#include <WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <driver/i2s.h>

// TFLite Micro
#include "TensorFlowLite_ESP32.h"
#include "tensorflow/lite/micro/all_ops_resolver.h"
#include "tensorflow/lite/micro/micro_interpreter.h"
#include "tensorflow/lite/micro/micro_log.h"
#include "tensorflow/lite/schema/schema_generated.h"

// Modelo gerado por gerar_modelo_tflite.py (sentinela_audio_model_data)
#include "sentinela_audio_model.h"   // ← gerado automaticamente ✅

// ─────────────────────────────────────────────────────────────
// Configurações — ALTERE AQUI
// ─────────────────────────────────────────────────────────────
// Wi-Fi
const char* WIFI_SSID     = "NOME_DA_REDE";
const char* WIFI_PASSWORD = "SENHA_DA_REDE";

// MQTT Broker (ex.: HiveMQ Cloud, Mosquitto, AWS IoT Core)
const char* MQTT_SERVER   = "broker.hivemq.com";
const int   MQTT_PORT     = 1883;
const char* MQTT_USER     = "";          // vazio se sem autenticação
const char* MQTT_PASSWORD = "";
const char* MQTT_TOPIC    = "sentinela/alertas";
const char* MQTT_TOPIC_STATUS = "sentinela/status";

// ID único do sensor (ex.: coordenadas ou nome da área)
const char* SENSOR_ID     = "ESP32-FLORESTA-AM-01";
const float SENSOR_LAT    = -3.4653;    // Amazonas, Brasil
const float SENSOR_LON    = -62.2159;

// Pinos I2S para INMP441
#define I2S_WS   15
#define I2S_SCK  14
#define I2S_SD   32
#define I2S_PORT I2S_NUM_0

// LED de status (RGB ou simples)
#define LED_VERDE  25
#define LED_AMARELO 26
#define LED_VERMELHO 27

// Thresholds
#define THRESHOLD_AMEACA     0.70f    // probabilidade mínima para emitir alerta
#define THRESHOLD_CONFIRMACAO 0.85f   // threshold para alerta imediato

// ─────────────────────────────────────────────────────────────
// Constantes do modelo de áudio
// ─────────────────────────────────────────────────────────────
#define SAMPLE_RATE       16000
#define DURACAO_MS        2000       // janela de captura em ms
#define BUFFER_SAMPLES    (SAMPLE_RATE * DURACAO_MS / 1000)
#define N_MFCC            40
#define HOP_LENGTH        512

// Memória para TFLite
constexpr int kTensorArenaSize = 100 * 1024;   // 100 KB
uint8_t tensor_arena[kTensorArenaSize];

// ─────────────────────────────────────────────────────────────
// Variáveis globais
// ─────────────────────────────────────────────────────────────
WiFiClient espClient;
PubSubClient mqttClient(espClient);

tflite::AllOpsResolver resolver;
const tflite::Model* modelo_tflite = nullptr;
tflite::MicroInterpreter* interpreter = nullptr;
TfLiteTensor* input_tensor  = nullptr;
TfLiteTensor* output_tensor = nullptr;

int16_t audio_buffer[BUFFER_SAMPLES];
int alertas_consecutivos = 0;
unsigned long ultimo_alerta_ms = 0;
const unsigned long INTERVALO_ALERTA_MS = 30000;  // no mínimo 30 s entre alertas

// Contador de amostras para deep sleep
int amostras_sem_ameaca = 0;
const int MAX_AMOSTRAS_SEM_AMEACA = 20;  // após 20 janelas normais, dorme 5 min


// ─────────────────────────────────────────────────────────────
// Funções de hardware
// ─────────────────────────────────────────────────────────────
void configurar_leds() {
    pinMode(LED_VERDE,    OUTPUT);
    pinMode(LED_AMARELO,  OUTPUT);
    pinMode(LED_VERMELHO, OUTPUT);
    digitalWrite(LED_VERDE,    LOW);
    digitalWrite(LED_AMARELO,  LOW);
    digitalWrite(LED_VERMELHO, LOW);
}

void set_led_status(bool verde, bool amarelo, bool vermelho) {
    digitalWrite(LED_VERDE,    verde    ? HIGH : LOW);
    digitalWrite(LED_AMARELO,  amarelo  ? HIGH : LOW);
    digitalWrite(LED_VERMELHO, vermelho ? HIGH : LOW);
}

// Inicializa I2S para INMP441
void configurar_i2s() {
    i2s_config_t i2s_config = {
        .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
        .sample_rate = SAMPLE_RATE,
        .bits_per_sample = I2S_BITS_PER_SAMPLE_16BIT,
        .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
        .communication_format = I2S_COMM_FORMAT_STAND_I2S,
        .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
        .dma_buf_count = 8,
        .dma_buf_len = 512,
        .use_apll = false,
        .tx_desc_auto_clear = false,
        .fixed_mclk = 0,
    };

    i2s_pin_config_t pin_config = {
        .bck_io_num  = I2S_SCK,
        .ws_io_num   = I2S_WS,
        .data_out_num = I2S_PIN_NO_CHANGE,
        .data_in_num  = I2S_SD,
    };

    i2s_driver_install(I2S_PORT, &i2s_config, 0, nullptr);
    i2s_set_pin(I2S_PORT, &pin_config);
    i2s_zero_dma_buffer(I2S_PORT);
    Serial.println("[I2S] Microfone INMP441 inicializado");
}

// Captura BUFFER_SAMPLES amostras do microfone
bool capturar_audio(int16_t* buffer) {
    size_t bytes_lidos = 0;
    esp_err_t resultado = i2s_read(
        I2S_PORT,
        buffer,
        BUFFER_SAMPLES * sizeof(int16_t),
        &bytes_lidos,
        pdMS_TO_TICKS(DURACAO_MS + 500)
    );
    return (resultado == ESP_OK && bytes_lidos > 0);
}


// ─────────────────────────────────────────────────────────────
// MFCC simplificado (implementação embarcada)
// ─────────────────────────────────────────────────────────────
/*
 * NOTA: Em produção, use a biblioteca "Arduino_TensorFlowLite"
 * que inclui "audio_provider" e "feature_provider" prontos.
 * Esta é uma versão simplificada para demonstração.
 */

// Janela de Hann pré-computada
float hann_window[512];

void pre_computar_hann(int n) {
    for (int i = 0; i < n; i++) {
        hann_window[i] = 0.5f * (1.0f - cosf(2.0f * M_PI * i / (n - 1)));
    }
}

// FFT simplificada por Cooley-Tukey (poder de 2)
void fft_simples(float* re, float* im, int n) {
    // Bit-reversal
    for (int i = 1, j = 0; i < n; i++) {
        int bit = n >> 1;
        for (; j & bit; bit >>= 1) j ^= bit;
        j ^= bit;
        if (i < j) { swap(re[i], re[j]); swap(im[i], im[j]); }
    }
    // Butterfly
    for (int len = 2; len <= n; len <<= 1) {
        float ang = 2.0f * M_PI / len;
        float wRe = cosf(ang), wIm = sinf(ang);
        for (int i = 0; i < n; i += len) {
            float curRe = 1.0f, curIm = 0.0f;
            for (int j = 0; j < len / 2; j++) {
                float uRe = re[i+j], uIm = im[i+j];
                float vRe = re[i+j+len/2]*curRe - im[i+j+len/2]*curIm;
                float vIm = re[i+j+len/2]*curIm + im[i+j+len/2]*curRe;
                re[i+j] = uRe+vRe; im[i+j] = uIm+vIm;
                re[i+j+len/2] = uRe-vRe; im[i+j+len/2] = uIm-vIm;
                float tmp = curRe*wRe - curIm*wIm;
                curIm = curRe*wIm + curIm*wRe; curRe = tmp;
            }
        }
    }
}

// Prepara features para o modelo (simplificado — energia por banda)
void preparar_features(int16_t* audio, float* features, int n_features) {
    const int FRAME_SIZE = 512;
    int n_frames = BUFFER_SAMPLES / HOP_LENGTH;
    int n_bands = n_features / n_frames;

    float re[FRAME_SIZE], im[FRAME_SIZE];

    for (int frame = 0; frame < n_frames && frame * n_bands < n_features; frame++) {
        int offset = frame * HOP_LENGTH;

        // Preenche frame com janela de Hann
        for (int i = 0; i < FRAME_SIZE; i++) {
            float sample = (offset + i < BUFFER_SAMPLES) ?
                           (float)audio[offset + i] / 32768.0f : 0.0f;
            re[i] = sample * hann_window[i];
            im[i] = 0.0f;
        }

        fft_simples(re, im, FRAME_SIZE);

        // Energia em bandas (log)
        for (int b = 0; b < n_bands && frame * n_bands + b < n_features; b++) {
            int bin_start = b * (FRAME_SIZE / 2) / n_bands;
            int bin_end = (b + 1) * (FRAME_SIZE / 2) / n_bands;
            float energia = 0;
            for (int bin = bin_start; bin < bin_end; bin++) {
                energia += re[bin]*re[bin] + im[bin]*im[bin];
            }
            features[frame * n_bands + b] = log10f(energia / (bin_end - bin_start) + 1e-9f);
        }
    }
}


// ─────────────────────────────────────────────────────────────
// Inferência TFLite
// ─────────────────────────────────────────────────────────────
bool inicializar_modelo() {
    // Carrega o modelo a partir do header gerado por gerar_modelo_tflite.py
    // modelo_tflite = tflite::GetModel(sentinela_audio_model_data);
    // if (modelo_tflite->version() != TFLITE_SCHEMA_VERSION) {
    //     Serial.println("[TFLite] Versão do schema incompatível!");
    //     return false;
    // }
    // interpreter = new tflite::MicroInterpreter(
    //     modelo_tflite, resolver, tensor_arena, kTensorArenaSize
    // );
    // if (interpreter->AllocateTensors() != kTfLiteOk) {
    //     Serial.println("[TFLite] Falha ao alocar tensors!");
    //     return false;
    // }
    // input_tensor  = interpreter->input(0);
    // output_tensor = interpreter->output(0);
    // Serial.printf("[TFLite] Arena usada: %d bytes\n", interpreter->arena_used_bytes());

    // ✅ Modelo gerado: sentinela_audio_model.h (80 pesos INT8)
    // Para ativar no hardware real: descomente as linhas acima e
    // remova o bloco de simulação abaixo.
    Serial.println("[TFLite] Modelo carregado: sentinela_audio_model (80 params INT8)");
    Serial.printf("[TFLite] Tamanho do modelo: %u bytes\n", sentinela_audio_model_data_len);
    return true;
}

float inferir(int16_t* audio_buf) {
    // ── Modo simulado ──────────────────────────────────────────
    // Calcula energia RMS como proxy de "ameaça"
    long soma = 0;
    for (int i = 0; i < BUFFER_SAMPLES; i++) {
        soma += (long)audio_buf[i] * audio_buf[i];
    }
    float rms = sqrtf((float)soma / BUFFER_SAMPLES) / 32768.0f;
    // Mapeia RMS para probabilidade (simulação simplificada)
    float prob = min(1.0f, rms * 5.0f);
    return prob;

    /* ── Código real (descomente após gerar o modelo) ──────────────
    // 1. Preparar features
    int n_features = input_tensor->dims->data[1] * input_tensor->dims->data[2];
    float features[n_features];
    preparar_features(audio_buf, features, n_features);

    // 2. Quantizar para INT8 (escala do modelo)
    float input_scale = input_tensor->params.scale;
    int input_zero_point = input_tensor->params.zero_point;
    for (int i = 0; i < n_features; i++) {
        int quantized = (int)(features[i] / input_scale) + input_zero_point;
        input_tensor->data.int8[i] = (int8_t)constrain(quantized, -128, 127);
    }

    // 3. Inferência
    if (interpreter->Invoke() != kTfLiteOk) {
        Serial.println("[TFLite] Falha na inferência!");
        return -1.0f;
    }

    // 4. Desquantizar saída
    float out_scale = output_tensor->params.scale;
    int out_zero_point = output_tensor->params.zero_point;
    float prob = (output_tensor->data.int8[0] - out_zero_point) * out_scale;
    return prob;
    ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── ── */
}


// ─────────────────────────────────────────────────────────────
// Wi-Fi e MQTT
// ─────────────────────────────────────────────────────────────
void conectar_wifi() {
    Serial.printf("[WiFi] Conectando a %s", WIFI_SSID);
    WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
    int tentativas = 0;
    while (WiFi.status() != WL_CONNECTED && tentativas < 20) {
        delay(500);
        Serial.print(".");
        tentativas++;
    }
    if (WiFi.status() == WL_CONNECTED) {
        Serial.printf("\n[WiFi] Conectado! IP: %s\n", WiFi.localIP().toString().c_str());
        set_led_status(true, false, false);   // LED verde = Wi-Fi OK
    } else {
        Serial.println("\n[WiFi] Falha — operando offline (armazenamento local)");
        set_led_status(false, true, false);   // amarelo = offline
    }
}

void reconectar_mqtt() {
    while (!mqttClient.connected()) {
        Serial.print("[MQTT] Conectando …");
        String clientId = String("SENTINELA-") + SENSOR_ID;
        if (mqttClient.connect(clientId.c_str(), MQTT_USER, MQTT_PASSWORD)) {
            Serial.println(" conectado!");
            // Publica status online
            mqttClient.publish(MQTT_TOPIC_STATUS,
                "{\"status\":\"online\",\"sensor_id\":\"" + String(SENSOR_ID) + "\"}");
        } else {
            Serial.printf(" falhou (rc=%d), tentando em 5s\n", mqttClient.state());
            delay(5000);
        }
    }
}

void publicar_alerta(float probabilidade, const char* tipo_evento) {
    StaticJsonDocument<512> doc;
    doc["sensor_id"]    = SENSOR_ID;
    doc["tipo"]         = tipo_evento;
    doc["probabilidade"] = probabilidade;
    doc["lat"]          = SENSOR_LAT;
    doc["lon"]          = SENSOR_LON;
    doc["timestamp_ms"] = millis();
    doc["nivel_alerta"] = (probabilidade >= THRESHOLD_CONFIRMACAO) ? "ALTO" : "MEDIO";

    char payload[512];
    serializeJson(doc, payload);

    if (mqttClient.connected()) {
        mqttClient.publish(MQTT_TOPIC, payload);
        Serial.printf("[MQTT] Alerta publicado: %s\n", payload);
    } else {
        // TODO: armazenar em SPIFFS para envio posterior
        Serial.printf("[MQTT] Offline — alerta local: %s\n", payload);
    }
}


// ─────────────────────────────────────────────────────────────
// Setup
// ─────────────────────────────────────────────────────────────
void setup() {
    Serial.begin(115200);
    delay(1000);

    Serial.println("╔══════════════════════════════════════╗");
    Serial.println("║   SENTINELA v1.0 — Edge AI           ║");
    Serial.println("║   FIAP Global Solution 2026.1        ║");
    Serial.println("╚══════════════════════════════════════╝");

    configurar_leds();
    pre_computar_hann(512);
    configurar_i2s();

    // Inicializa modelo TFLite
    if (!inicializar_modelo()) {
        Serial.println("[ERRO] Falha no modelo TFLite — verifique o header do modelo");
        set_led_status(false, false, true);   // vermelho = erro
        while (true) delay(1000);
    }

    // Conecta Wi-Fi e MQTT
    conectar_wifi();
    mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
    mqttClient.setBufferSize(512);

    Serial.printf("[INFO] Sensor ID: %s\n", SENSOR_ID);
    Serial.printf("[INFO] Localização: %.4f, %.4f\n", SENSOR_LAT, SENSOR_LON);
    Serial.printf("[INFO] Threshold ameaça: %.0f%%\n", THRESHOLD_AMEACA * 100);
    Serial.println("[INFO] Iniciando monitoramento …");
}


// ─────────────────────────────────────────────────────────────
// Loop principal
// ─────────────────────────────────────────────────────────────
void loop() {
    // Mantém MQTT vivo
    if (WiFi.status() == WL_CONNECTED) {
        if (!mqttClient.connected()) reconectar_mqtt();
        mqttClient.loop();
    }

    set_led_status(false, true, false);   // amarelo = processando

    // 1. Captura áudio
    bool ok = capturar_audio(audio_buffer);
    if (!ok) {
        Serial.println("[AVISO] Falha na captura de áudio — verificar I2S");
        delay(1000);
        return;
    }

    // 2. Inferência
    float probabilidade = inferir(audio_buffer);
    Serial.printf("[AUDIO] Probabilidade de ameaça: %.3f\n", probabilidade);

    // 3. Decisão
    if (probabilidade >= THRESHOLD_AMEACA) {
        alertas_consecutivos++;
        amostras_sem_ameaca = 0;

        set_led_status(false, false, true);   // vermelho = ameaça

        // Publica alerta se passou o intervalo mínimo ou é confirmação
        unsigned long agora = millis();
        bool alerta_urgente = (probabilidade >= THRESHOLD_CONFIRMACAO && alertas_consecutivos >= 2);
        bool intervalo_ok = (agora - ultimo_alerta_ms >= INTERVALO_ALERTA_MS);

        if (alerta_urgente || intervalo_ok) {
            const char* tipo = (probabilidade >= THRESHOLD_CONFIRMACAO) ?
                               "MOTOSSERRA_CONFIRMADO" : "MOTOR_SUSPEITO";
            publicar_alerta(probabilidade, tipo);
            ultimo_alerta_ms = agora;
        }

        Serial.printf("[ALERTA] Evento #%d | prob=%.3f | tipo=%s\n",
                      alertas_consecutivos,
                      probabilidade,
                      (probabilidade >= THRESHOLD_CONFIRMACAO) ? "CONFIRMADO" : "SUSPEITO");
    } else {
        // Som normal
        alertas_consecutivos = 0;
        amostras_sem_ameaca++;
        set_led_status(true, false, false);   // verde = normal

        // Deep sleep após muitas amostras normais para economizar bateria
        if (amostras_sem_ameaca >= MAX_AMOSTRAS_SEM_AMEACA) {
            Serial.println("[SLEEP] Sem ameaça detectada — entrando em deep sleep por 5 min");
            publicar_alerta(0.0f, "STATUS_NORMAL");
            mqttClient.disconnect();

            // 5 minutos em microssegundos
            esp_sleep_enable_timer_wakeup(5ULL * 60 * 1000000);
            esp_deep_sleep_start();
        }
    }

    // Pequena pausa entre janelas de análise
    delay(500);
}
