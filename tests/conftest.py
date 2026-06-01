"""
SENTINELA — conftest.py
========================
Configuração global dos testes e fixtures compartilhadas.
"""
import sys
import os
from pathlib import Path
import pytest

# Adiciona os módulos ao path
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "cloud_aws"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "pipeline_dados"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "visao_computacional"))


# ─────────────────────────────────────────────────────────────
# Fixtures compartilhadas
# ─────────────────────────────────────────────────────────────

@pytest.fixture
def evento_audio_alto():
    """Evento de áudio de alta probabilidade (motosserra confirmada)."""
    from datetime import datetime
    return {
        "source": "audio",
        "sensor_id": "ESP32-AM-01-01",
        "tipo_evento": "MOTOSSERRA_CONFIRMADO",
        "probabilidade": 0.92,
        "lat": -3.47,
        "lon": -62.22,
        "timestamp_ms": int(datetime(2026, 5, 1, 10, 0).timestamp() * 1000),
        "nivel_alerta": "ALTO",
    }


@pytest.fixture
def evento_audio_baixo():
    """Evento de áudio de baixa probabilidade (ruído ambiente)."""
    from datetime import datetime
    return {
        "source": "audio",
        "sensor_id": "ESP32-AM-01-02",
        "tipo_evento": "RUIDO_AMBIENTE",
        "probabilidade": 0.15,
        "lat": -3.50,
        "lon": -62.30,
        "timestamp_ms": int(datetime(2026, 5, 1, 11, 0).timestamp() * 1000),
        "nivel_alerta": "BAIXO",
    }


@pytest.fixture
def alerta_deter_proximo(evento_audio_alto):
    """Alerta DETER muito próximo ao evento de áudio (~1 km, 2 dias antes)."""
    return {
        "alerta_id": "DETER-20260429-00001",
        "tipo": "DETER-B CORTE RASO",
        "municipio": "Humaita",
        "estado": "AM",
        "lat": -3.471,   # ~0.1 grau = ~1 km do sensor em -3.47
        "lon": -62.221,
        "area_km2": 25.5,
        "data_deteccao": "2026-04-29",   # 2 dias antes do audio (2026-05-01)
        "confianca": 0.90,
    }


@pytest.fixture
def alerta_deter_distante():
    """Alerta DETER longe do evento de áudio (>10 km)."""
    return {
        "alerta_id": "DETER-20260429-99999",
        "tipo": "DETER-B DEGRADACAO",
        "municipio": "Lábrea",
        "estado": "AM",
        "lat": -8.26,    # centenas de km de distância
        "lon": -64.80,
        "area_km2": 5.0,
        "data_deteccao": "2026-04-29",
        "confianca": 0.75,
    }


@pytest.fixture
def alerta_deter_antigo(evento_audio_alto):
    """Alerta DETER fora da janela temporal (>7 dias)."""
    return {
        "alerta_id": "DETER-20260401-00001",
        "tipo": "DETER-B CORTE RASO",
        "municipio": "Humaitá",
        "estado": "AM",
        "lat": -3.48,
        "lon": -62.23,
        "area_km2": 10.0,
        "data_deteccao": "2026-04-01",  # 30 dias antes — fora da janela
        "confianca": 0.85,
    }
