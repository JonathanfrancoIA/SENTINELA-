# SENTINELA — ESP32 Virtual (Wokwi)

Demonstração ao vivo do **"ouvido" do SENTINELA** rodando 100% no
simulador online [Wokwi](https://wokwi.com) — sem precisar do hardware
físico na mesa. Ideal para apresentar à banca.

## O que ele mostra

- Um **ESP32 virtual** conectado a WiFi e a um **broker MQTT real**
  (`broker.hivemq.com`), publicando no mesmo tópico e formato do
  firmware de produção: `sentinela/alertas`.
- **OLED** com a probabilidade do modelo, barra e status local.
- **LEDs**: 🟢 normal · 🟡 processando · 🔴 ameaça detectada.
- **Potenciômetro** = saída do modelo TinyML (probabilidade de
  motosserra, 0–100%). No hardware real esse valor vem da inferência
  sobre o áudio do microfone I2S INMP441.
- **Botão "MOTOSSERRA"** = força probabilidade 0.95 por 4 s e dispara
  um alerta `CONFIRMADO` ao vivo.

## Como rodar (site, mais fácil)

1. Acesse https://wokwi.com e faça login.
2. **New Project → ESP32**.
3. Substitua o conteúdo de `sketch.ino` pelo arquivo daqui.
4. Abra a aba `diagram.json` e cole o `diagram.json` daqui.
5. Clique no ▶️ verde. O ESP32 conecta no WiFi `Wokwi-GUEST` (automático)
   e começa a publicar no MQTT.

> As bibliotecas (`PubSubClient`, `ArduinoJson`, `Adafruit SSD1306`,
> `Adafruit GFX`) são instaladas pelo Wokwi automaticamente. Se pedir,
> use o botão "Library Manager" e adicione as listadas em `libraries.txt`.

## Como demonstrar pros professores

1. Inicie a simulação → LED verde aceso, OLED mostra `NORMAL`.
2. Gire o potenciômetro até passar de 70% → LED fica vermelho,
   OLED mostra `SUSPEITO`, e o ESP32 publica no MQTT.
3. Aperte o botão **MOTOSSERRA** → vai a 95%, status `CONFIRMADO`,
   publica `MOTOSSERRA_CONFIRMADO`.
4. (Opcional, efeito "uau") Mostre a mensagem chegando:
   - Abra https://www.hivemq.com/demos/websocket-client/
   - Conecte em `broker.hivemq.com` porta `8000` (WebSocket).
   - Subscribe no tópico `sentinela/alertas`.
   - Cada alerta do Wokwi aparece em tempo real do outro lado.

## Como conectar ao dashboard SENTINELA

O firmware publica o mesmo JSON que o motor de fusão espera:

```json
{
  "sensor_id": "ESP32-FLORESTA-AM-01",
  "tipo": "MOTOSSERRA_CONFIRMADO",
  "probabilidade": 0.95,
  "lat": -3.4653,
  "lon": -62.2159,
  "timestamp_ms": 123456,
  "nivel_alerta": "ALTO"
}
```

Basta um assinante MQTT (ex.: um pequeno script `paho-mqtt`) gravando
esses eventos na tabela `eventos_audio` do SQLite para o dashboard e o
motor de fusão usarem os alertas do ESP32 virtual como se fossem de um
sensor real.

## Limitação honesta (diga isto à banca)

O Wokwi **não injeta áudio real** num microfone I2S simulado, então a
inferência TinyML sobre áudio roda no **ESP32 físico**. Aqui no Wokwi
demonstramos fielmente o **fluxo edge → nuvem** (detecção → decisão →
MQTT → dashboard/fusão) — que é a parte de integração do sistema.
