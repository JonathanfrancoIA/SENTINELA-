# FIAP - Faculdade de Informática e Administração Paulista

<p align="center">
  <a href="https://www.fiap.com.br/">
    <img src="https://upload.wikimedia.org/wikipedia/commons/thumb/9/9d/Logo_FIAP.svg/1200px-Logo_FIAP.svg.png" alt="FIAP" border="0" width="200">
  </a>
</p>

<br>

# 🛰️🌳 SENTINELA
## O olho e o ouvido da floresta

> POC da **Global Solution 2026.1 – Economia Espacial** (Tecnólogo em IA, FIAP).
> O Sentinela combate o **desmatamento ilegal na Amazônia** cruzando duas formas de percepção:
> o **olho** (visão computacional sobre imagens orbitais) e o **ouvido** (IA de borda em um
> ESP32 que escuta motosserras e motores no solo). O desmatamento primeiro **faz barulho** e
> só depois **vira cicatriz no satélite** — o Sentinela ouve antes e confirma vendo.

---

## Nome do grupo
**SENTINELA**

---

## 👨‍🎓 Integrantes
- Bruno de Souza Leite — RM567213
- Jonathan Gomes Ribeiro Franco — RM567109
- Marina Clara Constantino Ribeiro — RM568576
- Yasmin Kauane Silva Lima — RM566645

---

## 📜 Descrição

O **Sentinela** detecta desmatamento ilegal combinando **dois sensores que se confirmam**:

### 👁️ O olho (camada espacial)
Visão computacional sobre imagens **Sentinel-2 (Copernicus)** e alertas do **INPE/DETER** para
identificar **cicatrizes de desmatamento** (corte raso, degradação) via cálculo de **NDVI** e
**change detection** (diferença NDVI antes × depois).

- **NDVI = (NIR − Red) / (NIR + Red)** — queda de NDVI indica perda de vegetação
- Segmentação de polígonos com OpenCV (morfologia + contornos)
- Export GeoJSON com área (ha), severidade e coordenadas

### 👂 O ouvido (camada de solo / IoT)
Uma estação **ESP32 + microfone I2S INMP441** roda um classificador de áudio **na própria borda** (edge AI) que reconhece o som de **motosserra, trator e caminhão** — os primeiros sinais de invasão, que acontecem **antes** de qualquer mudança visível por satélite.

- Modelo **CNN TFLite INT8** (~80 KB) — roda diretamente no ESP32
- Dataset de treino: **ESC-50** (classe `chainsaw` → AMEAÇA)
- Publica alertas via **MQTT** com probabilidade e coordenadas GPS

### 🔗 A fusão (o diferencial)
Um motor na nuvem (**AWS Lambda**) gera um **alerta de alta confiança** quando as duas camadas concordam:

```
conf_fusão = 0.55 × prob_áudio + 0.45 × conf_DETER
           × fator_distância(< 10 km)
           × fator_temporal(< 7 dias)

conf ≥ 0.85 → CONFIRMADO → Notifica IBAMA/ICMBio
conf ≥ 0.65 → SUSPEITO   → Monitoramento contínuo
```

Isso **reduz falsos positivos** e gera alertas acionáveis: som suspeito no solo **+** mudança detectada no satélite na mesma região.

### 🌍 Impacto na Terra
A Amazônia é a maior floresta tropical do planeta e o desmatamento ilegal é uma de suas maiores ameaças. O Sentinela mostra como dados da **economia espacial** viram **ação no chão**: detecção mais cedo = menos área derrubada, menos carbono emitido, mais chance de flagrar o crime em andamento.

> Inspirado em iniciativas reais como a [Rainforest Connection](https://rfcx.org/) e o [INPE/DETER](http://terrabrasilis.dpi.inpe.br/).

### Tecnologias e conceitos integrados

| Área | Tecnologia |
|------|------------|
| Visão computacional | NDVI change detection, segmentação OpenCV, rasterio (Sentinel-2) |
| Áudio / Edge AI | CNN para áudio (ESC-50 `chainsaw`), TensorFlow Lite INT8 no ESP32 |
| Machine Learning | CNN para áudio e NDVI para visão |
| Dados espaciais | Sentinel-2 B4/B8 (Copernicus), INPE/DETER, INPE/PRODES |
| IoT / Sensores | ESP32-WROOM, microfone I2S INMP441, MQTT (HiveMQ/Mosquitto) |
| Nuvem / Serverless | AWS Lambda, API Gateway, S3, SNS |
| Banco de dados | SQLite (dev) / RDS Aurora (produção) |
| Pipeline de dados | Ingestão → fusão → alerta → notificação |
| Dashboard | Streamlit + Folium + Plotly |
| Protocolo IoT | MQTT com deep sleep para autonomia de bateria |

---

## 📁 Estrutura de pastas

```
SENTINELA/
│
├── assets/                  # logo FIAP, diagramas, prints do dashboard, fotos da bancada
│
├── document/                # documentação da entrega
│   ├── README.md
│   └── SENTINELA-GS-2026.pdf  # PDF único da entrega
│
├── src/                     # código-fonte
│   ├── README.md
│   │
│   ├── audio_edge/          # 👂 classificador de motosserra + firmware ESP32
│   │   ├── README.md
│   │   ├── treinar_audio.py       # treino com ESC-50 → TFLite INT8
│   │   └── sentinela_esp32/        # firmware ESP32 (.ino) + wokwi_simulador/
│   │
│   ├── visao_computacional/ # 👁️ segmentação/detecção de desmatamento (Sentinel-2)
│   │   ├── README.md
│   │   └── detectar_desmatamento.py  # NDVI change detection + GeoJSON
│   │
│   ├── pipeline_dados/      # ingestão Sentinel-2 / DETER + tratamento
│   │   ├── README.md
│   │   └── ingest_deter.py        # ingestão DETER + SQLite + dados simulados
│   │
│   ├── cloud_aws/           # motor de fusão (Lambda) + API Gateway
│   │   ├── README.md
│   │   └── handler.py             # Haversine fusion + Flask API local
│   │
│   └── dashboard/           # mapa de alertas e status dos sensores
│       ├── README.md
│       └── app.py                 # Streamlit + Folium + Plotly
│
├── requirements.txt         # dependências Python
└── README.md                # este arquivo (raiz)
```

> ⚠️ Cada pasta tem seu próprio `README.md`, conforme exige o edital.

---

## 🔧 Como executar o código

### Pré-requisitos
```bash
Python 3.10+
pip install -r requirements.txt
```

### 1. Pipeline de dados (gera banco SQLite)
```bash
cd src/pipeline_dados
python ingest_deter.py
```

### 2. Dashboard (abre em http://localhost:8501)
```bash
cd src/dashboard
streamlit run app.py
```

### 3. Treinar o ouvido (classificador de áudio)
```bash
cd src/audio_edge

# Modo demo (rápido, sem baixar ESC-50)
python treinar_audio.py --demo

# Treino completo (baixa ESC-50 ~600 MB)
python treinar_audio.py --epochs 20
```

### 4. Visão computacional (detecção de desmatamento)
```bash
cd src/visao_computacional

# Modo demo com imagens sintéticas
python detectar_desmatamento.py --demo --visualizar

# Com imagens GeoTIFF reais (Copernicus)
python detectar_desmatamento.py --antes antes.tif --depois depois.tif --visualizar
```

### 5. Motor de fusão (API REST local)
```bash
cd src/cloud_aws

# Iniciar API na porta 5050
python handler.py serve

# Testar fusão
python handler.py testar
```

### 6. Firmware ESP32
```
1. Abrir src/audio_edge/sentinela_esp32/sentinela_esp32.ino na Arduino IDE
2. Configurar WIFI_SSID, WIFI_PASSWORD e MQTT_SERVER no .ino
3. Gerar header do modelo: xxd -i models/sentinela_audio.tflite > sentinela_audio_model.h
4. Incluir e gravar na placa ESP32
```

> 💡 É uma **POC**: o que está funcional vem marcado com ✅ e o que está simulado com 🧪 no README de cada pasta.

---

## 🏗️ Diagrama de Arquitetura

```
┌─────────────────────────────────────────────────────────────────────┐
│                         FLORESTA AMAZÔNICA                          │
│                                                                     │
│  ┌─────────────────┐          ┌──────────────────────────────────┐  │
│  │  ESP32 + INMP441 │          │   Satélite Sentinel-2            │  │
│  │  (sensor de áudio)│         │   (Copernicus / INPE-DETER)     │  │
│  │                  │          │                                  │  │
│  │  TFLite Micro    │          │   NDVI Change Detection          │  │
│  │  CNN INT8        │          │   (B4 Red + B8 NIR)              │  │
│  │  prob_motosserra │          │   GeoJSON de polígonos           │  │
│  └──────┬───────────┘          └───────────────┬──────────────────┘  │
│         │ MQTT                                 │ HTTP/API            │
└─────────┼───────────────────────────────────────┼───────────────────┘
          │                                       │
          ▼                                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        NUVEM (AWS)                                  │
│                                                                     │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              MOTOR DE FUSÃO (AWS Lambda)                      │  │
│  │                                                               │  │
│  │  Haversine(audio, DETER) < 10 km AND delta < 7 dias          │  │
│  │  conf = 0.55×audio + 0.45×visual × dist_factor × time_factor │  │
│  │                                                               │  │
│  │  conf ≥ 0.85 → CONFIRMADO → SNS → IBAMA/ICMBio (email/SMS)  │  │
│  │  conf ≥ 0.65 → SUSPEITO → Dashboard (monitoramento)          │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │         SQLite / RDS Aurora (banco de dados)                  │  │
│  │  alertas_deter | eventos_audio | alertas_fusao | sensores     │  │
│  └───────────────────────────────────────────────────────────────┘  │
│                              │                                      │
│                              ▼                                      │
│  ┌───────────────────────────────────────────────────────────────┐  │
│  │              DASHBOARD (Streamlit + Folium)                   │  │
│  │  🗺️ Mapa | 📊 Análise | 📡 Sensores | 🔗 Fusões              │  │
│  └───────────────────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 🎥 Vídeo demonstrativo
📺 **[Assista no YouTube (não listado)](https://youtu.be/BlPoCsdbtlA)**

---

## 🗃 Histórico de lançamentos
- **0.1.0** — 2026-05-29 — Estrutura inicial, pipeline DETER e dashboard base
- **0.2.0** — 2026-05-30 — Classificador de áudio (motosserra) + firmware ESP32 + motor de fusão
- **0.3.0** — 2026-06-09 — Integração com dados DETER reais + visão computacional com GeoTIFF real
- **1.0.0** — 2026-06-09 — POC integrada, vídeo demonstrativo e ESP32 no simulador (Wokwi)

---

## 📋 Licença
[MODELO GIT FIAP](https://github.com/CaiqueFiap-2026/TEMPLATE-TIAO-2026) por
[FIAP](https://fiap.com.br) está licenciado sob
[Attribution 4.0 International](http://creativecommons.org/licenses/by/4.0/?ref=chooser-v1).
