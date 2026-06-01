# 👂 audio_edge — Classificador de Áudio + Firmware ESP32

Módulo de **Edge AI** do SENTINELA: detecta sons de motosserra, trator e veículos na floresta usando um classificador TinyML embarcado no ESP32.

## Status dos Componentes

| Arquivo | Descrição | Status |
|---------|-----------|--------|
| `treinar_audio.py` | Treino CNN com ESC-50 + export TFLite INT8 | ✅ Funcional |
| `sentinela_esp32.ino` | Firmware: mic I2S + TFLite Micro + MQTT | 🧪 Estrutura completa (modelo pendente) |
| `models/sentinela_audio.tflite` | Modelo exportado (gerado pelo treino) | ⚙️ Gerado ao executar treinar_audio.py |

## Arquitetura de Detecção

```
INMP441 (microfone I2S)
        │
        ▼
  Captura 2s de áudio (16 kHz)
        │
        ▼
  Extração de features
  (Energia por bandas de frequência)
        │
        ▼
  CNN TFLite Micro (INT8, ~80 KB)
  ┌──────────────────┐
  │ Conv2D × 3       │
  │ BatchNorm        │
  │ GlobalAvgPool    │
  │ Dense → Sigmoid  │
  └──────────────────┘
        │
  prob ≥ 0.70 → Publica MQTT → Motor de Fusão
  prob < 0.70 → normal (floresta/chuva)
```

## Dataset: ESC-50

O [ESC-50](https://github.com/karolpiczak/ESC-50) é um dataset público com 2000 clipes de áudio de 5 segundos em 50 classes.

Classes usadas pelo SENTINELA:
- `chainsaw` → **label 1** (AMEAÇA — principal alvo)
- `engine` → **label 1** (motor/trator)
- `crickets`, `thunderstorm`, `car_horn` → **label 0** (normal/floresta)

## Como executar

```bash
# Instalar dependências
pip install tensorflow librosa soundfile numpy tqdm loguru

# Treino completo (baixa ESC-50 ~600 MB)
python treinar_audio.py --epochs 20

# Modo demo (dados sintéticos, rápido)
python treinar_audio.py --demo --epochs 5

# Saída: models/sentinela_audio.tflite
```

## Métricas esperadas (ESC-50 real)

| Métrica | Valor esperado |
|---------|---------------|
| Acurácia (val) | ≥ 85% |
| AUC | ≥ 0.92 |
| Tamanho do modelo TFLite | ~60–120 KB |
| Latência no ESP32 | ~100–300 ms |

## Hardware necessário

```
ESP32 DevKitC V4
├── INMP441 (microfone I2S, 3.3V)
│   ├── WS  → GPIO 15
│   ├── SCK → GPIO 14
│   └── SD  → GPIO 32
├── LED verde  → GPIO 25 (normal)
├── LED amarelo → GPIO 26 (processando)
└── LED vermelho → GPIO 27 (ameaça)

Broker MQTT: HiveMQ Cloud (gratuito)
```

## Incluir modelo no firmware

```bash
# Gerar header C++ a partir do .tflite
xxd -i models/sentinela_audio.tflite > sentinela_audio_model.h

# Descomente no .ino:
# #include "sentinela_audio_model.h"
# modelo_tflite = tflite::GetModel(sentinela_audio_model_data);
```

## Consumo de energia

| Modo | Corrente estimada |
|------|------------------|
| Captura + inferência | ~120 mA |
| Wi-Fi + MQTT | +80 mA |
| Deep sleep (5 min) | ~10 µA |
| **Ciclo médio** | **~20 mA** |

> 💡 Com bateria de 3000 mAh: autonomia ~6 dias em campo.
