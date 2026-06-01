#!/usr/bin/env python3
"""
SENTINELA — Dashboard de Alertas
=================================
Mapa interativo de alertas de desmatamento em tempo real.
Combina alertas DETER (satélite), eventos de áudio (ESP32)
e alertas de fusão em um painel unificado.

Status: ✅ Funcional

Uso:
    cd src/dashboard
    streamlit run app.py

Dependências:
    pip install streamlit folium streamlit-folium pandas plotly
"""

import sys
import json
import sqlite3
import random
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import folium
from folium.plugins import MarkerCluster, HeatMap, MiniMap
from streamlit_folium import st_folium

# ─────────────────────────────────────────────────────────────
# Configuração da página
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="SENTINELA — Detecção de Desmatamento",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─────────────────────────────────────────────────────────────
# CSS customizado — Dark Theme Premium
# ─────────────────────────────────────────────────────────────
st.markdown("""
<style>
/* Import Google Font */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

/* Global */
html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
}

/* Background */
.stApp {
    background: linear-gradient(135deg, #0a0f1e 0%, #0d1527 50%, #0a1a0f 100%);
}

/* Sidebar */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1a2e 0%, #0a1a0f 100%);
    border-right: 1px solid rgba(0,255,100,0.1);
}

/* Metric cards */
div[data-testid="metric-container"] {
    background: linear-gradient(135deg, rgba(0,255,100,0.05) 0%, rgba(0,100,255,0.05) 100%);
    border: 1px solid rgba(0,255,100,0.15);
    border-radius: 12px;
    padding: 16px;
    backdrop-filter: blur(10px);
}

div[data-testid="metric-container"] label {
    color: rgba(200,255,220,0.7) !important;
    font-size: 0.75rem !important;
    letter-spacing: 0.1em !important;
    text-transform: uppercase !important;
}

div[data-testid="metric-container"] [data-testid="stMetricValue"] {
    color: #00ff64 !important;
    font-size: 2rem !important;
    font-weight: 700 !important;
}

div[data-testid="metric-container"] [data-testid="stMetricDelta"] {
    color: #ff6b35 !important;
}

/* Headers */
h1, h2, h3 {
    color: #e0ffe8 !important;
    letter-spacing: -0.02em;
}

/* Selectbox, multiselect */
.stSelectbox > div > div, .stMultiSelect > div > div {
    background: rgba(13,25,46,0.8) !important;
    border-color: rgba(0,255,100,0.2) !important;
    color: #e0ffe8 !important;
}

/* Dataframe */
.stDataFrame {
    border: 1px solid rgba(0,255,100,0.15);
    border-radius: 8px;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    background: rgba(13,25,46,0.5);
    border-radius: 10px;
    padding: 4px;
}

.stTabs [data-baseweb="tab"] {
    color: rgba(200,255,220,0.6);
    border-radius: 8px;
}

.stTabs [aria-selected="true"] {
    background: rgba(0,255,100,0.15) !important;
    color: #00ff64 !important;
}

/* Alert badge */
.alert-badge {
    display: inline-block;
    padding: 2px 10px;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    letter-spacing: 0.05em;
}
.badge-critico { background: rgba(255,50,50,0.2); color: #ff5050; border: 1px solid rgba(255,50,50,0.4); }
.badge-alto    { background: rgba(255,140,0,0.2);  color: #ff8c00; border: 1px solid rgba(255,140,0,0.4); }
.badge-medio   { background: rgba(255,200,0,0.2);  color: #ffc800; border: 1px solid rgba(255,200,0,0.4); }
.badge-baixo   { background: rgba(0,200,100,0.2);  color: #00c864; border: 1px solid rgba(0,200,100,0.4); }

/* Scrollbar */
::-webkit-scrollbar { width: 6px; }
::-webkit-scrollbar-track { background: rgba(0,0,0,0.2); }
::-webkit-scrollbar-thumb { background: rgba(0,255,100,0.3); border-radius: 3px; }

/* Banner */
.sentinela-banner {
    background: linear-gradient(135deg, rgba(0,40,20,0.8) 0%, rgba(0,20,60,0.8) 100%);
    border: 1px solid rgba(0,255,100,0.2);
    border-radius: 16px;
    padding: 20px 28px;
    margin-bottom: 20px;
    backdrop-filter: blur(20px);
}
</style>
""", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Dados simulados (coerentes com o pipeline_dados)
# ─────────────────────────────────────────────────────────────
MUNICIPIOS = [
    ("Altamira", "PA", -52.2, -3.2),
    ("Itaituba", "PA", -55.98, -4.28),
    ("São Félix do Xingu", "PA", -51.99, -6.64),
    ("Porto Velho", "RO", -63.9, -8.76),
    ("Humaitá", "AM", -63.01, -7.51),
    ("Apuí", "AM", -59.89, -7.2),
    ("Novo Progresso", "PA", -55.4, -7.12),
    ("Lábrea", "AM", -64.8, -7.26),
    ("Colniza", "MT", -59.0, -9.36),
    ("Alta Floresta", "MT", -56.08, -9.87),
    ("Sinop", "MT", -55.5, -11.86),
    ("Guarantã do Norte", "MT", -54.89, -9.8),
    ("Boca do Acre", "AM", -67.38, -8.75),
    ("Juruena", "MT", -58.49, -10.31),
    ("Parana", "MT", -57.9, -12.6),
]


@st.cache_data(ttl=30)
def gerar_dados():
    """Gera dados simulados para o dashboard."""
    random.seed(42)
    np.random.seed(42)
    now = datetime.now()

    # ── Alertas DETER ──────────────────────────────────────────
    deter = []
    for i in range(120):
        mun, est, lon, lat = random.choice(MUNICIPIOS)
        area = round(float(np.random.lognormal(2.0, 1.5)) / 100, 2)
        area = max(0.01, min(area, 150.0))
        data = now - timedelta(days=random.randint(0, 89))
        deter.append({
            "id": f"DET-{i+1:04d}",
            "tipo": random.choice(["CORTE RASO", "DEGRADACAO", "QUEIMADA"]),
            "municipio": mun, "estado": est,
            "lat": lat + random.gauss(0, 0.4),
            "lon": lon + random.gauss(0, 0.4),
            "area_km2": area,
            "severidade": "CRITICO" if area > 50 else "ALTO" if area > 10 else "MEDIO" if area > 1 else "BAIXO",
            "data": data.strftime("%Y-%m-%d"),
            "confianca": round(random.uniform(0.7, 1.0), 2),
        })
    df_deter = pd.DataFrame(deter)

    # ── Sensores ESP32 ─────────────────────────────────────────
    sensores = []
    for i, (mun, est, lon, lat) in enumerate(MUNICIPIOS):
        for j in range(random.randint(1, 2)):
            ativo = random.random() > 0.2
            hb = now - timedelta(minutes=random.randint(1, 180) if ativo else random.randint(200, 2000))
            sensores.append({
                "sensor_id": f"ESP32-{est}-{i+1:02d}-{j+1}",
                "nome": f"{mun} #{j+1}",
                "lat": lat + random.gauss(0, 0.15),
                "lon": lon + random.gauss(0, 0.15),
                "municipio": mun, "estado": est,
                "ativo": ativo,
                "ultimo_hb": hb.strftime("%Y-%m-%d %H:%M"),
                "bateria_pct": random.randint(20, 100) if ativo else random.randint(0, 15),
                "eventos_hoje": random.randint(0, 12) if ativo else 0,
            })
    df_sensores = pd.DataFrame(sensores)

    # ── Eventos de áudio ───────────────────────────────────────
    eventos = []
    for i in range(300):
        sensor = df_sensores[df_sensores["ativo"]].sample(1).iloc[0]
        prob = random.betavariate(2, 5)
        ts = now - timedelta(hours=random.randint(0, 720))
        eventos.append({
            "id": i + 1,
            "sensor_id": sensor["sensor_id"],
            "prob": round(prob, 3),
            "tipo": "MOTOSSERRA" if prob >= 0.85 else "MOTOR" if prob >= 0.65 else "AMBIENTE",
            "nivel": "ALTO" if prob >= 0.85 else "MEDIO" if prob >= 0.65 else "BAIXO",
            "lat": sensor["lat"],
            "lon": sensor["lon"],
            "municipio": sensor["municipio"],
            "timestamp": ts,
        })
    df_eventos = pd.DataFrame(eventos).sort_values("timestamp", ascending=False)

    # ── Alertas de fusão ───────────────────────────────────────
    fusoes = []
    alertas_altos = df_eventos[df_eventos["nivel"] == "ALTO"].head(20)
    for i, (_, ev) in enumerate(alertas_altos.iterrows()):
        conf = round(random.uniform(0.65, 0.98), 3)
        mun, est, lon, lat = random.choice(MUNICIPIOS)
        fusoes.append({
            "fusao_id": f"FUSAO-{i+1:04d}",
            "nivel_confianca": conf,
            "status": "CONFIRMADO" if conf >= 0.85 else "SUSPEITO",
            "lat": ev["lat"] + random.gauss(0, 0.05),
            "lon": ev["lon"] + random.gauss(0, 0.05),
            "municipio": ev["municipio"],
            "sensor_id": ev["sensor_id"],
            "orgao": "IBAMA" if conf >= 0.90 else "ICMBio" if conf >= 0.85 else None,
            "criado_em": ev["timestamp"].strftime("%Y-%m-%d %H:%M"),
        })
    # Garante schema mesmo quando a lista está vazia
    FUSAO_COLS = ["fusao_id", "nivel_confianca", "status", "lat", "lon",
                  "municipio", "sensor_id", "orgao", "criado_em"]
    if fusoes:
        df_fusoes = pd.DataFrame(fusoes).sort_values("nivel_confianca", ascending=False)
    else:
        df_fusoes = pd.DataFrame(columns=FUSAO_COLS)

    return df_deter, df_sensores, df_eventos, df_fusoes


# ─────────────────────────────────────────────────────────────
# Mapa principal (Folium)
# ─────────────────────────────────────────────────────────────
def criar_mapa(df_deter, df_sensores, df_eventos, df_fusoes,
               mostrar_deter=True, mostrar_sensores=True,
               mostrar_fusoes=True, mostrar_heatmap=False):
    """Cria mapa Folium com todas as camadas do SENTINELA."""

    # Centrado na Amazônia
    m = folium.Map(
        location=[-6.5, -57.0],
        zoom_start=5,
        tiles=None,
        prefer_canvas=True,
    )

    # Tile layers
    folium.TileLayer(
        "https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
        name="🛰️ Satélite", attr="Google", show=True
    ).add_to(m)
    folium.TileLayer(
        "CartoDB dark_matter",
        name="🌑 Dark", attr="CartoDB"
    ).add_to(m)
    folium.TileLayer(
        "OpenStreetMap",
        name="🗺️ Mapa", attr="OSM"
    ).add_to(m)

    # MiniMap
    MiniMap(position="bottomright", width=150, height=100).add_to(m)

    # ── Heatmap (alertas DETER) ────────────────────────────────
    if mostrar_heatmap and len(df_deter) > 0:
        heat_data = [[row["lat"], row["lon"], row["area_km2"]]
                     for _, row in df_deter.iterrows()]
        HeatMap(heat_data, name="🌡️ Mapa de Calor", radius=20,
                gradient={"0.2": "#00ff64", "0.5": "#ffcc00", "1.0": "#ff2020"}).add_to(m)

    # ── Alertas DETER (satélite) ───────────────────────────────
    if mostrar_deter:
        grupo_deter = folium.FeatureGroup(name="👁️ Alertas DETER (Satélite)", show=True)
        cluster_deter = MarkerCluster(name="DETER").add_to(grupo_deter)

        cores_sev = {"CRITICO": "#ff2020", "ALTO": "#ff8c00", "MEDIO": "#ffc800", "BAIXO": "#00c864"}

        for _, row in df_deter.iterrows():
            cor = cores_sev.get(row["severidade"], "#aaaaaa")
            popup_html = f"""
            <div style="font-family:Inter,sans-serif;min-width:200px;background:#0d1527;color:#e0ffe8;padding:12px;border-radius:8px;border:1px solid {cor}">
                <b style="color:{cor};font-size:14px">⚠️ {row['tipo']}</b><br><br>
                📍 <b>{row['municipio']}</b>, {row['estado']}<br>
                📐 Área: <b>{row['area_km2']:.2f} km²</b><br>
                📅 Data: {row['data']}<br>
                🎯 Confiança: {row['confianca']:.0%}<br>
                🚨 Severidade: <b style="color:{cor}">{row['severidade']}</b>
            </div>
            """
            folium.CircleMarker(
                location=[row["lat"], row["lon"]],
                radius=max(5, min(20, row["area_km2"] * 0.5)),
                color=cor, fill=True, fill_color=cor, fill_opacity=0.5,
                weight=1.5,
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"⚠️ {row['tipo']} — {row['area_km2']:.1f} km² ({row['municipio']})",
            ).add_to(cluster_deter)

        grupo_deter.add_to(m)

    # ── Sensores ESP32 ─────────────────────────────────────────
    if mostrar_sensores:
        grupo_sens = folium.FeatureGroup(name="👂 Sensores IoT (ESP32)", show=True)

        for _, row in df_sensores.iterrows():
            cor = "#00ff64" if row["ativo"] else "#666666"
            icon_color = "green" if row["ativo"] else "gray"
            bat_icon = "🔋" if row["bateria_pct"] > 30 else "🪫"

            popup_html = f"""
            <div style="font-family:Inter,sans-serif;min-width:220px;background:#0d1527;color:#e0ffe8;padding:12px;border-radius:8px;border:1px solid {cor}">
                <b style="color:{cor};font-size:13px">📡 {row['sensor_id']}</b><br><br>
                📍 {row['municipio']}, {row['estado']}<br>
                🕐 Último HB: {row['ultimo_hb']}<br>
                {bat_icon} Bateria: <b>{row['bateria_pct']}%</b><br>
                📊 Eventos hoje: <b>{row['eventos_hoje']}</b><br>
                🟢 Status: <b style="color:{cor}">{'ATIVO' if row['ativo'] else 'OFFLINE'}</b>
            </div>
            """
            folium.Marker(
                location=[row["lat"], row["lon"]],
                icon=folium.Icon(color=icon_color, icon="microphone", prefix="fa"),
                popup=folium.Popup(popup_html, max_width=260),
                tooltip=f"📡 {row['sensor_id']} | {'🟢 Online' if row['ativo'] else '⚫ Offline'}",
            ).add_to(grupo_sens)

        grupo_sens.add_to(m)

    # ── Alertas de Fusão ───────────────────────────────────────
    if mostrar_fusoes and len(df_fusoes) > 0:
        grupo_fusao = folium.FeatureGroup(name="🔗 Alertas de Fusão (Alta Confiança)", show=True)

        for _, row in df_fusoes.iterrows():
            cor = "#ff2020" if row["status"] == "CONFIRMADO" else "#ff8c00"
            conf_pct = f"{row['nivel_confianca']:.0%}"

            popup_html = f"""
            <div style="font-family:Inter,sans-serif;min-width:230px;background:#1a0505;color:#ffe8e8;padding:14px;border-radius:8px;border:2px solid {cor}">
                <b style="color:{cor};font-size:15px">🚨 ALERTA FUSÃO</b><br>
                <span style="color:#ffaa00;font-size:12px">ID: {row['fusao_id']}</span><br><br>
                📍 <b>{row['municipio']}</b><br>
                📡 Sensor: {row['sensor_id']}<br>
                🎯 Confiança: <b style="color:{cor};font-size:16px">{conf_pct}</b><br>
                ⚡ Status: <b style="color:{cor}">{row['status']}</b><br>
                🏛️ Órgão: <b>{row['orgao'] or 'Monitoramento'}</b><br>
                🕐 {row['criado_em']}
            </div>
            """

            # Círculo de alerta pulsante
            folium.Circle(
                location=[row["lat"], row["lon"]],
                radius=8000,  # 8 km
                color=cor, fill=True, fill_color=cor, fill_opacity=0.1,
                weight=2, dash_array="6"
            ).add_to(grupo_fusao)

            folium.Marker(
                location=[row["lat"], row["lon"]],
                icon=folium.Icon(color="red" if row["status"] == "CONFIRMADO" else "orange",
                                  icon="warning-sign", prefix="glyphicon"),
                popup=folium.Popup(popup_html, max_width=270),
                tooltip=f"🚨 FUSÃO {conf_pct} — {row['status']} | {row['municipio']}",
            ).add_to(grupo_fusao)

        grupo_fusao.add_to(m)

    folium.LayerControl(position="topright", collapsed=False).add_to(m)

    return m


# ─────────────────────────────────────────────────────────────
# Sidebar
# ─────────────────────────────────────────────────────────────
def renderizar_sidebar(df_sensores, df_fusoes):
    with st.sidebar:
        st.markdown("""
        <div style="text-align:center;padding:10px 0 20px">
            <div style="font-size:2.5rem">🛰️🌳</div>
            <div style="color:#00ff64;font-size:1.3rem;font-weight:700;letter-spacing:0.1em">SENTINELA</div>
            <div style="color:rgba(200,255,220,0.5);font-size:0.7rem;letter-spacing:0.15em">O OLHO E O OUVIDO DA FLORESTA</div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🗺️ Camadas do Mapa")
        mostrar_deter    = st.checkbox("👁️ Alertas DETER (satélite)", value=True)
        mostrar_sensores = st.checkbox("👂 Sensores ESP32", value=True)
        mostrar_fusoes   = st.checkbox("🔗 Alertas de Fusão", value=True)
        mostrar_heatmap  = st.checkbox("🌡️ Mapa de Calor", value=False)

        st.markdown("---")
        st.markdown("### 🔽 Filtros")

        periodo = st.selectbox(
            "Período", ["Últimas 24h", "Últimos 7 dias", "Últimos 30 dias", "Últimos 90 dias"],
            index=2
        )
        severidade = st.multiselect(
            "Severidade DETER",
            ["CRITICO", "ALTO", "MEDIO", "BAIXO"],
            default=["CRITICO", "ALTO", "MEDIO"],
        )

        st.markdown("---")
        st.markdown("### 📡 Sensores Ativos")
        n_ativos = df_sensores["ativo"].sum()
        n_total = len(df_sensores)
        pct = int(n_ativos / n_total * 100)

        st.markdown(f"""
        <div style="background:rgba(0,255,100,0.05);border:1px solid rgba(0,255,100,0.2);border-radius:10px;padding:12px;margin-bottom:8px">
            <div style="color:#00ff64;font-size:1.5rem;font-weight:700">{n_ativos}/{n_total}</div>
            <div style="color:rgba(200,255,220,0.6);font-size:0.75rem">sensores online ({pct}%)</div>
            <div style="background:rgba(0,0,0,0.3);border-radius:4px;height:6px;margin-top:8px">
                <div style="background:linear-gradient(90deg,#00ff64,#00cc50);width:{pct}%;height:100%;border-radius:4px"></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

        st.markdown("### 🚨 Últimas Fusões")
        for _, f in df_fusoes.head(5).iterrows():
            cor = "#ff2020" if f["status"] == "CONFIRMADO" else "#ff8c00"
            st.markdown(f"""
            <div style="background:rgba(40,0,0,0.4);border:1px solid {cor}33;border-radius:8px;padding:8px 10px;margin-bottom:6px">
                <span style="color:{cor};font-weight:600;font-size:0.8rem">{f['status']}</span>
                <span style="color:rgba(255,220,220,0.6);font-size:0.7rem;float:right">{f['nivel_confianca']:.0%}</span><br>
                <span style="color:rgba(255,220,220,0.8);font-size:0.75rem">{f['municipio']}</span>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown(f"""
        <div style="color:rgba(200,255,220,0.3);font-size:0.7rem;text-align:center">
            FIAP · Global Solution 2026.1<br>
            Última atualização: {datetime.now().strftime('%H:%M:%S')}
        </div>
        """, unsafe_allow_html=True)

    return mostrar_deter, mostrar_sensores, mostrar_fusoes, mostrar_heatmap, severidade


# ─────────────────────────────────────────────────────────────
# Gráficos Plotly
# ─────────────────────────────────────────────────────────────
PLOT_TEMPLATE = {
    "layout": {
        "paper_bgcolor": "rgba(13,21,39,0.8)",
        "plot_bgcolor": "rgba(13,21,39,0.4)",
        "font": {"color": "#c8ffd4", "family": "Inter"},
        "margin": {"t": 40, "b": 30, "l": 40, "r": 20},
    }
}

_GRID_COLOR = "rgba(0,255,100,0.08)"

def plot_timeline_alertas(df_deter):
    """Timeline de alertas por semana."""
    df = df_deter.copy()
    df["data"] = pd.to_datetime(df["data"])
    df["semana"] = df["data"].dt.to_period("W").dt.start_time
    df_agg = df.groupby(["semana", "severidade"]).size().reset_index(name="n")

    fig = px.bar(
        df_agg, x="semana", y="n", color="severidade",
        color_discrete_map={"CRITICO": "#ff2020", "ALTO": "#ff8c00",
                             "MEDIO": "#ffc800", "BAIXO": "#00c864"},
        title="Alertas DETER por Semana",
        labels={"n": "Alertas", "semana": "Semana", "severidade": "Severidade"},
    )
    fig.update_layout(**PLOT_TEMPLATE["layout"])
    fig.update_xaxes(gridcolor=_GRID_COLOR)
    fig.update_yaxes(gridcolor=_GRID_COLOR)
    return fig


def plot_area_por_estado(df_deter):
    """Área desmatada por estado."""
    df = df_deter.groupby("estado")["area_km2"].sum().reset_index()
    df = df.sort_values("area_km2", ascending=True)

    fig = px.bar(
        df, x="area_km2", y="estado", orientation="h",
        title="Área Desmatada por Estado (km²)",
        labels={"area_km2": "Área (km²)", "estado": "Estado"},
        color="area_km2",
        color_continuous_scale=["#004d20", "#00c864", "#ffc800", "#ff8c00", "#ff2020"],
    )
    fig.update_layout(**PLOT_TEMPLATE["layout"])
    fig.update_coloraxes(showscale=False)
    return fig


def plot_audio_timeline(df_eventos):
    """Probabilidade dos eventos de áudio ao longo do tempo."""
    df = df_eventos.copy()
    df["hora"] = pd.to_datetime(df["timestamp"]).dt.floor("6H")
    df_agg = df.groupby(["hora", "nivel"])["prob"].mean().reset_index()

    fig = px.scatter(
        df.head(200), x="timestamp", y="prob",
        color="nivel",
        color_discrete_map={"ALTO": "#ff2020", "MEDIO": "#ff8c00", "BAIXO": "#00c864"},
        title="Eventos de Áudio — Probabilidade de Ameaça",
        labels={"prob": "Probabilidade", "timestamp": "Timestamp", "nivel": "Nível"},
        opacity=0.7,
        size_max=8,
    )
    fig.add_hline(y=0.85, line_dash="dash", line_color="#ff2020",
                   annotation_text="Threshold CONFIRMADO", annotation_font_color="#ff2020")
    fig.add_hline(y=0.65, line_dash="dash", line_color="#ff8c00",
                   annotation_text="Threshold SUSPEITO", annotation_font_color="#ff8c00")
    fig.update_layout(**PLOT_TEMPLATE["layout"])
    return fig


def plot_fusao_gauge(df_fusoes):
    """Gauge de confiança média das fusões."""
    conf_media = df_fusoes["nivel_confianca"].mean() if len(df_fusoes) > 0 else 0

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=conf_media * 100,
        title={"text": "Confiança Média das Fusões", "font": {"color": "#c8ffd4"}},
        number={"suffix": "%", "font": {"color": "#00ff64", "size": 36}},
        delta={"reference": 80, "increasing": {"color": "#ff2020"}, "decreasing": {"color": "#00c864"}},
        gauge={
            "axis": {"range": [0, 100], "tickcolor": "#c8ffd4"},
            "bar": {"color": "#00c864"},
            "steps": [
                {"range": [0, 65], "color": "rgba(0,200,100,0.1)"},
                {"range": [65, 85], "color": "rgba(255,140,0,0.2)"},
                {"range": [85, 100], "color": "rgba(255,50,50,0.25)"},
            ],
            "threshold": {
                "line": {"color": "#ff2020", "width": 3},
                "thickness": 0.8,
                "value": 85,
            },
            "bgcolor": "rgba(13,21,39,0)",
            "bordercolor": "rgba(0,255,100,0.3)",
        }
    ))
    fig.update_layout(
        paper_bgcolor="rgba(13,21,39,0.8)",
        font={"color": "#c8ffd4", "family": "Inter"},
        height=200,
        margin={"t": 40, "b": 10},
    )
    return fig


# ─────────────────────────────────────────────────────────────
# Eventos REAIS do ESP32 (MQTT → SQLite → dashboard)
# ─────────────────────────────────────────────────────────────
DB_REAL = Path(__file__).resolve().parent.parent / "pipeline_dados" / "data" / "sentinela.db"


@st.cache_data(ttl=5)
def carregar_eventos_reais(db_path: str = str(DB_REAL)):
    """Lê os alertas de áudio gravados pelo assinante MQTT (ESP32 → eventos_audio).
    Retorna lista de dicts (vazia se o banco/tabela não existir)."""
    try:
        if not Path(db_path).exists():
            return []
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        cur = conn.execute(
            "SELECT id, sensor_id, tipo_evento, probabilidade, lat, lon, "
            "timestamp_ms, nivel_alerta, criado_em "
            "FROM eventos_audio ORDER BY id DESC LIMIT 200"
        )
        linhas = [dict(r) for r in cur.fetchall()]
        conn.close()
        return linhas
    except Exception:
        return []


def _ts_real(linha):
    v = linha.get("criado_em")
    if v:
        try:
            return datetime.fromisoformat(str(v).replace("T", " ")[:19])
        except Exception:
            pass
    return datetime.now()


def mesclar_eventos_reais(df_deter, df_sensores, df_eventos, df_fusoes):
    """Injeta os eventos REAIS do ESP32 (gravados via MQTT) nos DataFrames do
    dashboard, para que apareçam no mapa, nos feeds e nas métricas — ao vivo."""
    linhas = carregar_eventos_reais()
    if not linhas:
        return df_deter, df_sensores, df_eventos, df_fusoes, 0

    nov_eventos, nov_sensores, nov_fusoes = [], {}, []
    for ln in linhas:
        sid = ln.get("sensor_id") or "ESP32-AO-VIVO"
        prob = float(ln.get("probabilidade") or 0)
        lat = ln.get("lat")
        lon = ln.get("lon")
        if lat is None or lon is None:
            continue
        ts = _ts_real(ln)
        nivel = ln.get("nivel_alerta") or (
            "ALTO" if prob >= 0.85 else "MEDIO" if prob >= 0.65 else "BAIXO")
        tipo = ln.get("tipo_evento") or "EVENTO"

        nov_eventos.append({
            "id": 900000 + int(ln.get("id") or 0),
            "sensor_id": sid, "prob": round(prob, 3), "tipo": tipo,
            "nivel": nivel, "lat": float(lat), "lon": float(lon),
            "municipio": "ESP32 ao vivo", "timestamp": ts,
        })

        # 1 marcador de sensor por ESP32 (usa o evento mais recente)
        if sid not in nov_sensores:
            nov_sensores[sid] = {
                "sensor_id": sid, "nome": f"{sid} (AO VIVO)",
                "lat": float(lat), "lon": float(lon),
                "municipio": "ESP32 ao vivo", "estado": "AM",
                "ativo": True, "ultimo_hb": ts.strftime("%Y-%m-%d %H:%M"),
                "bateria_pct": 100, "eventos_hoje": 0,
            }
        nov_sensores[sid]["eventos_hoje"] += 1

        # Alerta de fusão para eventos relevantes (vira marcador vermelho no mapa)
        if prob >= 0.70 or nivel in ("ALTO", "MEDIO"):
            nov_fusoes.append({
                "fusao_id": f"FUSAO-ESP32-{int(ln.get('id') or 0):04d}",
                "nivel_confianca": round(prob, 3),
                "status": "CONFIRMADO" if prob >= 0.85 else "SUSPEITO",
                "lat": float(lat), "lon": float(lon),
                "municipio": "ESP32 ao vivo", "sensor_id": sid,
                "orgao": "IBAMA" if prob >= 0.90 else "ICMBio" if prob >= 0.85 else None,
                "criado_em": ts.strftime("%Y-%m-%d %H:%M"),
            })

    if nov_eventos:
        df_eventos = pd.concat(
            [pd.DataFrame(nov_eventos), df_eventos], ignore_index=True
        ).sort_values("timestamp", ascending=False)
    if nov_sensores:
        df_sensores = pd.concat(
            [pd.DataFrame(list(nov_sensores.values())), df_sensores], ignore_index=True
        )
    if nov_fusoes:
        df_fusoes = pd.concat(
            [pd.DataFrame(nov_fusoes), df_fusoes], ignore_index=True
        ).sort_values("nivel_confianca", ascending=False)

    return df_deter, df_sensores, df_eventos, df_fusoes, len(nov_eventos)


# ─────────────────────────────────────────────────────────────
# App principal
# ─────────────────────────────────────────────────────────────
def main():
    # Carrega dados (simulados) e mescla os eventos REAIS do ESP32 (MQTT → SQLite)
    df_deter, df_sensores, df_eventos, df_fusoes = gerar_dados()
    df_deter, df_sensores, df_eventos, df_fusoes, n_reais = \
        mesclar_eventos_reais(df_deter, df_sensores, df_eventos, df_fusoes)
    if n_reais:
        try:
            st.toast(f"📡 {n_reais} evento(s) REAL(is) do ESP32 carregado(s) do banco",
                     icon="📡")
        except Exception:
            pass

    # Sidebar
    mostrar_deter, mostrar_sensores, mostrar_fusoes, mostrar_heatmap, filtro_sev = \
        renderizar_sidebar(df_sensores, df_fusoes)

    # Filtra por severidade
    df_deter_f = df_deter[df_deter["severidade"].isin(filtro_sev)] if filtro_sev else df_deter

    # ── Banner ────────────────────────────────────────────────
    st.markdown("""
    <div class="sentinela-banner">
        <div style="display:flex;align-items:center;gap:16px">
            <div style="font-size:2.8rem">🛰️🌳</div>
            <div>
                <div style="color:#00ff64;font-size:1.6rem;font-weight:700;letter-spacing:0.05em">SENTINELA</div>
                <div style="color:rgba(200,255,220,0.6);font-size:0.85rem">Sistema de Detecção de Desmatamento Ilegal · Amazônia Brasileira</div>
                <div style="color:rgba(200,255,220,0.4);font-size:0.75rem;margin-top:4px">FIAP · Global Solution 2026.1 · Economia Espacial</div>
            </div>
            <div style="margin-left:auto;text-align:right">
                <div style="color:#00ff64;font-size:0.8rem;letter-spacing:0.1em">● MONITORAMENTO ATIVO</div>
                <div style="color:rgba(200,255,220,0.5);font-size:0.7rem">{}</div>
            </div>
        </div>
    </div>
    """.format(datetime.now().strftime("%d/%m/%Y %H:%M:%S")), unsafe_allow_html=True)

    # ── KPIs ──────────────────────────────────────────────────
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric("⚠️ Alertas DETER",
                  len(df_deter_f),
                  f"+{len(df_deter_f[df_deter_f['data'] >= (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')])} (7d)")

    with col2:
        area_total = df_deter_f["area_km2"].sum()
        st.metric("🌲 Área Afetada",
                  f"{area_total:.0f} km²",
                  f"≈ {int(area_total * 100):.0f} campos de futebol")

    with col3:
        n_ativos = df_sensores["ativo"].sum()
        st.metric("📡 Sensores Online",
                  f"{n_ativos}/{len(df_sensores)}",
                  f"{int(n_ativos/len(df_sensores)*100)}% operacional")

    with col4:
        n_confirmados = len(df_fusoes[df_fusoes["status"] == "CONFIRMADO"])
        st.metric("🚨 Fusões Confirmadas",
                  n_confirmados,
                  f"+{len(df_fusoes[df_fusoes['status'] == 'SUSPEITO'])} suspeitos")

    with col5:
        eventos_alto = len(df_eventos[df_eventos["nivel"] == "ALTO"])
        st.metric("👂 Eventos de Áudio (ALTO)",
                  eventos_alto,
                  f"de {len(df_eventos)} total")

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Tabs ──────────────────────────────────────────────────
    tab_mapa, tab_analise, tab_sensores, tab_fusoes, tab_visao = st.tabs([
        "🗺️ Mapa de Alertas",
        "📊 Análise de Dados",
        "📡 Sensores IoT",
        "🔗 Motor de Fusão",
        "🛰️ Visão Computacional",
    ])

    # ── Tab: Mapa ─────────────────────────────────────────────
    with tab_mapa:
        st.markdown("#### Mapa Interativo — Amazônia Legal")
        st.caption("Alertas DETER (círculos), Sensores ESP32 (ícones) e Fusões (marcadores vermelhos). Use o controle de camadas no canto superior direito.")

        mapa = criar_mapa(
            df_deter_f, df_sensores, df_eventos, df_fusoes,
            mostrar_deter, mostrar_sensores, mostrar_fusoes, mostrar_heatmap
        )
        st_folium(mapa, width="100%", height=580, returned_objects=[])

        # Legenda
        cols = st.columns(4)
        legendas = [
            ("🔴 CRÍTICO", "> 50 km² | Notificação IBAMA imediata"),
            ("🟠 ALTO", "10–50 km² | Alerta prioritário"),
            ("🟡 MÉDIO", "1–10 km² | Monitoramento"),
            ("🟢 BAIXO", "< 1 km² | Registro"),
        ]
        for col, (badge, desc) in zip(cols, legendas):
            col.markdown(f"**{badge}**  \n{desc}")

    # ── Tab: Análise ──────────────────────────────────────────
    with tab_analise:
        col_g1, col_g2 = st.columns(2)

        with col_g1:
            st.plotly_chart(plot_timeline_alertas(df_deter_f),
                            use_container_width=True)

        with col_g2:
            st.plotly_chart(plot_area_por_estado(df_deter_f),
                            use_container_width=True)

        st.plotly_chart(plot_audio_timeline(df_eventos),
                        use_container_width=True)

        # Tabela de alertas críticos
        st.markdown("#### 🔴 Top 15 Alertas Críticos")
        df_top = df_deter_f.sort_values("area_km2", ascending=False).head(15)[
            ["id", "tipo", "municipio", "estado", "area_km2", "severidade", "data", "confianca"]
        ]
        st.dataframe(
            df_top.rename(columns={
                "id": "ID", "tipo": "Tipo", "municipio": "Município",
                "estado": "UF", "area_km2": "Área (km²)",
                "severidade": "Severidade", "data": "Data", "confianca": "Confiança"
            }),
            use_container_width=True, hide_index=True
        )

    # ── Tab: Sensores ──────────────────────────────────────────
    with tab_sensores:
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.metric("Total de Sensores", len(df_sensores))
        with col_s2:
            st.metric("Ativos", int(df_sensores["ativo"].sum()),
                      delta=f"{int(df_sensores['ativo'].sum()/len(df_sensores)*100)}%")
        with col_s3:
            bat_media = df_sensores[df_sensores["ativo"]]["bateria_pct"].mean()
            st.metric("Bateria Média (ativos)", f"{bat_media:.0f}%")

        # Mapa simplificado dos sensores
        st.markdown("#### Status dos Sensores por Estado")
        df_sens_est = df_sensores.groupby("estado").agg(
            total=("sensor_id", "count"),
            ativos=("ativo", "sum"),
            bateria_media=("bateria_pct", "mean"),
            eventos_dia=("eventos_hoje", "sum"),
        ).reset_index()
        df_sens_est["pct_ativo"] = (df_sens_est["ativos"] / df_sens_est["total"] * 100).round(0)
        df_sens_est["bateria_media"] = df_sens_est["bateria_media"].round(0)

        st.dataframe(
            df_sens_est.rename(columns={
                "estado": "Estado", "total": "Total", "ativos": "Ativos",
                "bateria_media": "Bateria Média (%)", "eventos_dia": "Eventos Hoje",
                "pct_ativo": "Online (%)"
            }),
            use_container_width=True, hide_index=True
        )

        st.markdown("#### Lista Completa de Sensores")
        df_s = df_sensores.copy()
        df_s["status"] = df_s["ativo"].map({True: "🟢 ATIVO", False: "⚫ OFFLINE"})
        st.dataframe(
            df_s[["sensor_id", "municipio", "estado", "status", "ultimo_hb", "bateria_pct", "eventos_hoje"]].rename(columns={
                "sensor_id": "Sensor ID", "municipio": "Município", "estado": "UF",
                "status": "Status", "ultimo_hb": "Último HB",
                "bateria_pct": "Bateria (%)", "eventos_hoje": "Eventos Hoje"
            }),
            use_container_width=True, hide_index=True
        )

    # ── Tab: Fusões ───────────────────────────────────────────
    with tab_fusoes:
        col_f1, col_f2 = st.columns([1, 2])

        with col_f1:
            st.plotly_chart(plot_fusao_gauge(df_fusoes), use_container_width=True)

            # Distribuição de status
            status_counts = df_fusoes["status"].value_counts().reset_index()
            status_counts.columns = ["Status", "Count"]
            fig_pie = px.pie(
                status_counts, names="Status", values="Count",
                color="Status",
                color_discrete_map={"CONFIRMADO": "#ff2020", "SUSPEITO": "#ff8c00"},
                title="Distribuição de Status",
                hole=0.4,
            )
            fig_pie.update_layout(**PLOT_TEMPLATE["layout"], height=220)
            st.plotly_chart(fig_pie, use_container_width=True)

        with col_f2:
            st.markdown("#### 🚨 Alertas de Fusão — Alta Confiança")
            st.caption("Alertas gerados quando áudio (ESP32) + satélite (DETER) concordam na mesma região e janela temporal.")

            for _, f in df_fusoes.head(10).iterrows():
                cor = "#ff2020" if f["status"] == "CONFIRMADO" else "#ff8c00"
                orgao_html = f'🏛️ <b style="color:{cor}">{f["orgao"]}</b> notificado' if f["orgao"] else "📋 Monitoramento"
                st.markdown(f"""
                <div style="background:linear-gradient(135deg,rgba(40,0,0,0.6),rgba(20,0,30,0.4));
                            border:1px solid {cor}55;border-radius:10px;padding:12px 16px;margin-bottom:8px;
                            border-left:4px solid {cor}">
                    <div style="display:flex;justify-content:space-between;align-items:center">
                        <span style="color:{cor};font-weight:700;font-size:0.9rem">🚨 {f['status']}</span>
                        <span style="color:{cor};font-size:1.1rem;font-weight:700">{f['nivel_confianca']:.0%}</span>
                    </div>
                    <div style="color:rgba(255,220,220,0.8);font-size:0.8rem;margin-top:4px">
                        📍 {f['municipio']} · 📡 {f['sensor_id']} · {orgao_html}
                    </div>
                    <div style="color:rgba(255,220,220,0.5);font-size:0.72rem;margin-top:2px">
                        ID: {f['fusao_id']} · {f['criado_em']}
                    </div>
                </div>
                """, unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("#### Como funciona o Motor de Fusão?")
        st.markdown("""
        ```
        EVENTO DE ÁUDIO (ESP32)          ALERTA DETER (Sentinel-2)
             prob ≥ 0.70                      confiança ≥ 0.70
                   │                                │
                   ▼                                ▼
        ┌─────────────────────────────────────────────────┐
        │         MOTOR DE FUSÃO (AWS Lambda)             │
        │                                                 │
        │  conf = 0.55 × prob_audio + 0.45 × conf_deter  │
        │  × fator_distancia(< 10 km)                     │
        │  × fator_temporal(< 7 dias)                     │
        │                                                 │
        │  conf ≥ 0.85 → CONFIRMADO → Notifica IBAMA     │
        │  conf ≥ 0.65 → SUSPEITO   → Monitoramento      │
        └─────────────────────────────────────────────────┘
        ```
        """)

    # ── Tab: Visão Computacional ──────────────────────────────
    with tab_visao:
        st.markdown("#### 🛰️ Detecção de Desmatamento por Satélite (NDVI)")
        st.caption("Análise de mudança de cobertura vegetal em imagens Sentinel-2 (bandas B04/B08). "
                   "ΔNDVI < -0.15 indica perda de vegetação.")

        # Diretório de saída do detector de visão computacional
        vc_output = Path(__file__).resolve().parent.parent / "visao_computacional" / "output"
        png_relatorio = vc_output / "relatorio_desmatamento.png"
        meta_path = vc_output / "metadata_analise.json"
        geojsons = sorted(vc_output.glob("desmatamento_*.geojson"),
                          key=lambda p: p.stat().st_mtime, reverse=True) if vc_output.exists() else []

        # ── Métricas do GeoJSON mais recente ──
        geo_data = None
        if geojsons:
            try:
                with open(geojsons[0], "r", encoding="utf-8") as fh:
                    geo_data = json.load(fh)
            except Exception as e:
                st.warning(f"Não foi possível ler {geojsons[0].name}: {e}")

        # ── Metadados da análise (região + período) ──
        meta = None
        if meta_path.exists():
            try:
                with open(meta_path, "r", encoding="utf-8") as fh:
                    meta = json.load(fh)
            except Exception:
                meta = None

        if geo_data:
            feats = geo_data.get("features", [])

            def _props(f):
                return f.get("properties", {}) or {}

            # ── Região e período analisados ──
            if meta:
                bbox_txt = meta.get("bbox_legivel", "—")
                centro = f"{meta.get('centro_lat', '—')}, {meta.get('centro_lon', '—')}"
                periodo = f"{meta.get('data_antes', '—')}  →  {meta.get('data_depois', '—')}"
            else:
                # Fallback: estima a região a partir dos centroides dos polígonos
                lats = [_props(f).get("centroide_lat") for f in feats if _props(f).get("centroide_lat") is not None]
                lons = [_props(f).get("centroide_lon") for f in feats if _props(f).get("centroide_lon") is not None]
                if lats and lons:
                    bbox_txt = f"{min(lons):.4f}, {min(lats):.4f} → {max(lons):.4f}, {max(lats):.4f}"
                    centro = f"{(min(lats)+max(lats))/2:.4f}, {(min(lons)+max(lons))/2:.4f}"
                else:
                    bbox_txt = centro = "—"
                periodo = "Disponível após reexecutar o detector"

            st.markdown(f"""
            <div style="background:linear-gradient(135deg,rgba(0,40,30,0.5),rgba(0,20,40,0.4));
                        border:1px solid rgba(0,200,150,0.3);border-radius:10px;
                        padding:14px 18px;margin-bottom:14px">
                <div style="display:flex;gap:32px;flex-wrap:wrap">
                    <div><span style="color:rgba(180,255,220,0.6);font-size:0.75rem">🗺️ ÁREA ANALISADA (bbox)</span><br>
                         <b style="color:#9ff;font-size:0.95rem">{bbox_txt}</b></div>
                    <div><span style="color:rgba(180,255,220,0.6);font-size:0.75rem">📍 CENTRO (lat, lon)</span><br>
                         <b style="color:#9ff;font-size:0.95rem">{centro}</b></div>
                    <div><span style="color:rgba(180,255,220,0.6);font-size:0.75rem">🕓 PERÍODO (antes → depois)</span><br>
                         <b style="color:#9ff;font-size:0.95rem">{periodo}</b></div>
                </div>
            </div>
            """, unsafe_allow_html=True)

            area_total = sum(_props(f).get("area_hectares", 0) for f in feats)
            n_critico = sum(1 for f in feats if _props(f).get("severidade") == "CRITICO")

            # Data da análise: do primeiro feature ou do nome do arquivo
            data_analise = "—"
            if feats:
                dt = _props(feats[0]).get("data_deteccao", "")
                data_analise = dt.split("T")[0] if dt else "—"
            if data_analise == "—":
                data_analise = geojsons[0].name.replace("desmatamento_", "").replace(".geojson", "")

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("🔺 Polígonos Detectados", len(feats))
            c2.metric("🌳 Área Total Perdida", f"{area_total:.2f} ha")
            c3.metric("🔴 Severidade CRÍTICA", n_critico)
            c4.metric("📅 Análise", str(data_analise))
        else:
            st.info(
                "Nenhum relatório de visão computacional encontrado ainda.\n\n"
                "Gere um executando, na raiz do projeto:\n\n"
                "```\n"
                "python src/visao_computacional/detectar_desmatamento.py --baixar \\\n"
                "    --bbox -60.05 -3.15 -59.90 -3.00 \\\n"
                "    --data-antes 2024-07-01 --data-depois 2025-07-01 \\\n"
                "    --dias-tolerancia 15 --nuvens-max 60\n"
                "```"
            )

        st.markdown("<br>", unsafe_allow_html=True)

        # ── Relatório visual (PNG) ──
        if png_relatorio.exists():
            st.markdown("#### 📷 Relatório Visual")
            st.image(str(png_relatorio),
                     caption="Antes / Depois / ΔNDVI / Polígonos de desmatamento detectados",
                     use_container_width=True)
        elif geo_data:
            st.caption("Relatório visual (relatorio_desmatamento.png) não encontrado.")

        # ── Tabela de polígonos ──
        if geo_data and geo_data.get("features"):
            st.markdown("#### 📋 Polígonos de Desmatamento")
            linhas = []
            for f in geo_data["features"]:
                p = f.get("properties", {}) or {}
                sev = p.get("severidade", "—")
                emoji = {"CRITICO": "🔴", "ALTO": "🟠", "MEDIO": "🟡", "BAIXO": "🟢"}.get(sev, "⚪")
                linhas.append({
                    "ID": p.get("id", "—"),
                    "Área (ha)": round(p.get("area_hectares", 0), 2),
                    "Severidade": f"{emoji} {sev}",
                    "Confiança": f"{p.get('confianca', 0):.0%}",
                    "Latitude": round(p.get("centroide_lat", 0), 4),
                    "Longitude": round(p.get("centroide_lon", 0), 4),
                })
            df_poly = pd.DataFrame(linhas).sort_values("Área (ha)", ascending=False)
            st.dataframe(df_poly, use_container_width=True, hide_index=True)

            if geojsons:
                st.caption(f"Fonte: {geojsons[0].name} · {geo_data['features'][0].get('properties', {}).get('fonte', '')}")

            # ── Mapa dos polígonos detectados ──
            pts = [(_props(f).get("centroide_lat"), _props(f).get("centroide_lon"), _props(f))
                   for f in feats
                   if _props(f).get("centroide_lat") is not None and _props(f).get("centroide_lon") is not None]
            if pts:
                st.markdown("#### 🗺️ Localização dos Polígonos Detectados")
                lat_c = sum(p[0] for p in pts) / len(pts)
                lon_c = sum(p[1] for p in pts) / len(pts)
                m_vc = folium.Map(location=[lat_c, lon_c], zoom_start=11, tiles=None, prefer_canvas=True)
                folium.TileLayer("https://mt1.google.com/vt/lyrs=s&x={x}&y={y}&z={z}",
                                 name="🛰️ Satélite", attr="Google", show=True).add_to(m_vc)
                folium.TileLayer("CartoDB dark_matter", name="🌑 Dark", attr="CartoDB").add_to(m_vc)
                cores_sev = {"CRITICO": "#ff2020", "ALTO": "#ff8c00", "MEDIO": "#ffc800", "BAIXO": "#00c864"}
                for lat, lon, p in pts:
                    cor = cores_sev.get(p.get("severidade"), "#aaaaaa")
                    area_h = p.get("area_hectares", 0)
                    popup = (f"<b style='color:{cor}'>{p.get('id','—')} · {p.get('severidade','—')}</b><br>"
                             f"📐 {area_h:.2f} ha<br>🎯 {p.get('confianca',0):.0%}")
                    folium.CircleMarker(
                        location=[lat, lon],
                        radius=max(6, min(22, (area_h ** 0.5))),
                        color=cor, fill=True, fill_color=cor, fill_opacity=0.55,
                        weight=2, popup=folium.Popup(popup, max_width=220),
                    ).add_to(m_vc)
                folium.LayerControl(collapsed=True).add_to(m_vc)
                st_folium(m_vc, width="100%", height=460, returned_objects=[])

            # ── Fechar o ciclo: notificar órgão responsável ──
            st.markdown("#### 📨 Notificação Automática")
            st.caption("Ao detectar um polígono CRÍTICO, o SENTINELA pode notificar o IBAMA/brigada "
                       "por e-mail e Telegram. (Pré-visualização — não envia de verdade.)")
            criticos = [_props(f) for f in feats if _props(f).get("severidade") == "CRITICO"]
            alvo = max((_props(f) for f in feats),
                       key=lambda p: p.get("area_hectares", 0), default=None)
            if alvo and st.button("📨 Pré-visualizar notificação do maior alerta"):
                import sys as _sys
                _nt = str(Path(__file__).resolve().parent.parent)
                if _nt not in _sys.path:
                    _sys.path.insert(0, _nt)
                try:
                    from notificacao.notificar import _formatar_texto
                    alerta = {
                        "tipo": "DESMATAMENTO (Satélite NDVI)",
                        "status": alvo.get("severidade", "—"),
                        "severidade": alvo.get("severidade", "—"),
                        "municipio": "Amazônia Legal",
                        "estado": "AM",
                        "area_ha": alvo.get("area_hectares", 0),
                        "confianca": alvo.get("confianca", 0),
                        "lat": alvo.get("centroide_lat"),
                        "lon": alvo.get("centroide_lon"),
                        "fonte": alvo.get("fonte", "Sentinel-2 NDVI"),
                    }
                    st.code(_formatar_texto(alerta), language="text")
                    st.success(f"{len(criticos)} polígono(s) CRÍTICO(s) acionariam notificação real "
                               "(configure SMTP_*/TELEGRAM_* no .env e use src/notificacao/notificar.py).")
                except Exception as e:
                    st.warning(f"Módulo de notificação indisponível: {e}")


if __name__ == "__main__":
    main()
