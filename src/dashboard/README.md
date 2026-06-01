# 🗺️ dashboard — Mapa de Alertas e Status dos Sensores

Dashboard interativo do SENTINELA: visualiza alertas de desmatamento (DETER + fusão) e status dos sensores IoT (ESP32) em tempo real.

## Status

| Componente | Status |
|-----------|--------|
| Mapa interativo (Folium) | ✅ Funcional |
| Camada DETER (círculos de severidade) | ✅ Funcional |
| Camada sensores ESP32 (ícones) | ✅ Funcional |
| Camada fusões (alertas vermelhos) | ✅ Funcional |
| Heatmap de intensidade | ✅ Funcional |
| KPIs em tempo real | ✅ Funcional |
| Gráficos Plotly (timeline, área, áudio) | ✅ Funcional |
| Gauge de confiança das fusões | ✅ Funcional |
| Painel de sensores com status de bateria | ✅ Funcional |

## Como executar

```bash
# Instalar dependências
pip install streamlit folium streamlit-folium pandas plotly numpy loguru

# Iniciar dashboard
streamlit run app.py

# Acesse: http://localhost:8501
```

## Funcionalidades

### 🗺️ Mapa de Alertas
- **Tile layers**: Satélite (Google), Dark (CartoDB), OpenStreetMap
- **Alertas DETER**: círculos com tamanho proporcional à área afetada, cor por severidade
- **Sensores ESP32**: ícones com status online/offline e popup detalhado
- **Alertas de Fusão**: marcadores vermelhos com círculo de raio de 8 km
- **Heatmap**: mapa de calor de intensidade de alertas
- **Controle de camadas**: ativar/desativar cada tipo de alerta

### 📊 Análise de Dados
- Timeline de alertas por semana (por severidade)
- Área desmatada por estado (barras horizontais)
- Scatter plot de probabilidade de áudio ao longo do tempo
- Tabela dos top 15 alertas críticos

### 📡 Sensores IoT
- Status por estado (ativos/total, bateria média)
- Lista completa de sensores com heartbeat e bateria
- Eventos do dia por sensor

### 🔗 Motor de Fusão
- Gauge de confiança média
- Distribuição de status (confirmado/suspeito)
- Lista de alertas de alta confiança com órgão notificado
- Diagrama explicativo do algoritmo de fusão

## Integração com dados reais

Para integrar com dados reais do banco SQLite:

```python
# Em app.py, substitua a função gerar_dados() por:

import sqlite3
import pandas as pd

DB_PATH = "../pipeline_dados/data/sentinela.db"

def carregar_dados_reais():
    conn = sqlite3.connect(DB_PATH)
    df_deter   = pd.read_sql("SELECT * FROM alertas_deter", conn)
    df_sensores = pd.read_sql("SELECT * FROM sensores", conn)
    df_eventos  = pd.read_sql("SELECT * FROM eventos_audio", conn)
    df_fusoes   = pd.read_sql("SELECT * FROM alertas_fusao", conn)
    conn.close()
    return df_deter, df_sensores, df_eventos, df_fusoes
```

## Arquitetura do Dashboard

```
app.py
├── gerar_dados()           # dados simulados (ou banco SQLite)
├── criar_mapa()            # mapa Folium com 4 camadas
├── renderizar_sidebar()    # controles e filtros
├── plot_timeline_alertas() # Plotly bar chart
├── plot_area_por_estado()  # Plotly horizontal bar
├── plot_audio_timeline()   # Plotly scatter
├── plot_fusao_gauge()      # Plotly gauge
└── main()                  # orquestra a UI Streamlit
```
