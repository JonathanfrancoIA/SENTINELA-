# src/ — Código-Fonte do SENTINELA

Este diretório contém todo o código-fonte da POC, organizado por camada.

## Estrutura

| Pasta | Camada | Status |
|-------|--------|--------|
| [`audio_edge/`](audio_edge/) | 👂 Ouvido — Edge AI (ESP32 + classificador de áudio) | ✅ Treino funcional · 🧪 Firmware simulado |
| [`visao_computacional/`](visao_computacional/) | 👁️ Olho — Segmentação/detecção de desmatamento Sentinel-2 | ✅ Funcional |
| [`pipeline_dados/`](pipeline_dados/) | 🔄 Ingestão e persistência de dados (DETER + IoT) | ✅ Funcional (dados simulados) |
| [`cloud_aws/`](cloud_aws/) | ☁️ Motor de fusão (Lambda) + API Gateway | 🧪 Simulado com Flask local |
| [`dashboard/`](dashboard/) | 🗺️ Mapa de alertas e painel de sensores | ✅ Funcional |

## Fluxo de Dados

```
ESP32 (som)                    Sentinel-2 / DETER (satélite)
    │                                     │
    ▼                                     ▼
audio_edge/               visao_computacional/ + pipeline_dados/
(TFLite inferência)           (NDVI change detection + SQLite)
    │                                     │
    └─────────────┬───────────────────────┘
                  ▼
            cloud_aws/handler.py
            (Motor de Fusão)
                  │
                  ▼
            dashboard/app.py
            (Mapa + Alertas)
```

## Como executar tudo

```bash
# 1. Instalar dependências
pip install -r ../../requirements.txt

# 2. Pipeline (gera banco de dados)
cd pipeline_dados && python ingest_deter.py && cd ..

# 3. Dashboard (abre no navegador)
cd dashboard && streamlit run app.py
```
