#!/usr/bin/env python3
"""
SENTINELA — Motor de Fusão (AWS Lambda / Local Flask)
======================================================
Cruza alertas da camada de visão (Sentinel-2/DETER) com eventos
da camada de áudio (ESP32/MQTT) para gerar alertas de alta confiança.

A fusão ocorre quando:
  1. Um sensor de áudio reporta probabilidade >= 0.70 (motosserra detectada)
  2. Existe alerta DETER a menos de RAIO_FUSAO_KM km
  3. A janela temporal é de até JANELA_DIAS dias

Modo de execução:
    AWS Lambda: handler(event, context) — deploy via SAM/Serverless
    Local/Dev:  python handler.py serve  — Flask API local na porta 5050

Status: 🧪 Simulado (lógica de fusão completa, deploy AWS opcional)

Uso:
    python handler.py serve                    # inicia API REST local
    python handler.py testar                   # simula um evento de fusão
    python handler.py relatorio                # gera relatório de fusões

Dependências:
    pip install flask sqlalchemy pandas
"""

import os
import sys
import json
import math
import uuid
import sqlite3
import argparse
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

# ─────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────
DB_PATH       = Path("../pipeline_dados/data/sentinela.db")
RAIO_FUSAO_KM = 10.0          # raio máximo de associação áudio↔satélite
JANELA_DIAS   = 7             # janela temporal máxima de associação
CONF_MINIMA_ALERTA = 0.65     # confiança mínima para emitir alerta de fusão
CONF_ALTA = 0.85              # confiança para notificação imediata de órgão ambiental

# Pesos da fusão (áudio tem mais peso — detecta ANTES do satélite)
PESO_AUDIO    = 0.55
PESO_VISUAL   = 0.45


# ─────────────────────────────────────────────────────────────
# Funções de geoespacial (sem geopandas p/ compatibilidade Lambda)
# ─────────────────────────────────────────────────────────────
def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distância entre dois pontos em km (fórmula de Haversine)."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * \
        math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ─────────────────────────────────────────────────────────────
# Lógica de fusão
# ─────────────────────────────────────────────────────────────
def calcular_confianca_fusao(prob_audio: float, conf_visual: float,
                              distancia_km: float, delta_dias: int) -> float:
    """
    Calcula confiança final da fusão com penalização por distância e tempo.

    Args:
        prob_audio:    probabilidade do classificador de áudio (0–1)
        conf_visual:   confiança do alerta DETER/Sentinel-2 (0–1)
        distancia_km:  distância entre sensor e alerta DETER (km)
        delta_dias:    dias entre evento de áudio e alerta DETER

    Returns:
        Confiança final (0–1)
    """
    # Confiança base ponderada
    conf_base = PESO_AUDIO * prob_audio + PESO_VISUAL * conf_visual

    # Penalização por distância (decai linearmente até RAIO_FUSAO_KM)
    fator_dist = max(0.0, 1.0 - distancia_km / RAIO_FUSAO_KM)

    # Penalização temporal (decai linearmente até JANELA_DIAS)
    fator_tempo = max(0.0, 1.0 - delta_dias / JANELA_DIAS) ** 0.5

    conf_final = conf_base * fator_dist * fator_tempo
    return round(float(conf_final), 4)


def fusao_evento(evento_audio: dict, alertas_deter: list[dict]) -> Optional[dict]:
    """
    Tenta fundir um evento de áudio com alertas DETER próximos.
    Retorna o melhor alerta de fusão ou None se não houver match.
    """
    if not alertas_deter:
        return None

    melhor_conf = -1.0
    melhor_fusao = None

    lat_audio = evento_audio.get("lat", 0)
    lon_audio = evento_audio.get("lon", 0)
    ts_audio = datetime.fromtimestamp(evento_audio.get("timestamp_ms", 0) / 1000)

    for alerta in alertas_deter:
        lat_deter = alerta.get("lat", 0)
        lon_deter = alerta.get("lon", 0)

        dist_km = haversine_km(lat_audio, lon_audio, lat_deter, lon_deter)
        if dist_km > RAIO_FUSAO_KM:
            continue

        data_deter = datetime.strptime(alerta.get("data_deteccao", "2024-01-01"), "%Y-%m-%d")
        delta_dias = abs((ts_audio - data_deter).days)
        if delta_dias > JANELA_DIAS:
            continue

        conf = calcular_confianca_fusao(
            prob_audio=evento_audio.get("probabilidade", 0),
            conf_visual=alerta.get("confianca", 1.0),
            distancia_km=dist_km,
            delta_dias=delta_dias,
        )

        if conf > melhor_conf and conf >= CONF_MINIMA_ALERTA:
            melhor_conf = conf
            melhor_fusao = {
                "fusao_id": f"FUSAO-{uuid.uuid4().hex[:8].upper()}",
                "sensor_id": evento_audio.get("sensor_id"),
                "alerta_deter_id": alerta.get("alerta_id"),
                "nivel_confianca": conf,
                "lat": (lat_audio + lat_deter) / 2,
                "lon": (lon_audio + lon_deter) / 2,
                "raio_km": RAIO_FUSAO_KM,
                "distancia_km": round(dist_km, 2),
                "delta_dias": delta_dias,
                "prob_audio": evento_audio.get("probabilidade"),
                "conf_visual": alerta.get("confianca"),
                "tipo_evento_audio": evento_audio.get("tipo_evento"),
                "tipo_alerta_deter": alerta.get("tipo"),
                "municipio": alerta.get("municipio"),
                "estado": alerta.get("estado"),
                "area_afetada_km2": alerta.get("area_km2"),
                "status": "CONFIRMADO" if conf >= CONF_ALTA else "SUSPEITO",
                "orgao_notificado": "IBAMA" if conf >= 0.90 else
                                    "ICMBio" if conf >= CONF_ALTA else None,
                "criado_em": datetime.now().isoformat(),
                "atualizado_em": datetime.now().isoformat(),
            }

    return melhor_fusao


# ─────────────────────────────────────────────────────────────
# Handler AWS Lambda
# ─────────────────────────────────────────────────────────────
def handler(event: dict, context=None) -> dict:
    """
    Entry point AWS Lambda.

    Aceita dois tipos de eventos:
    1. evento_audio: {"source": "audio", "sensor_id": ..., "probabilidade": ..., ...}
    2. alerta_deter: {"source": "deter", "alerta_id": ..., ...}

    Retorna:
    {
        "statusCode": 200,
        "body": {"fusao": {...} ou null, "mensagem": ...}
    }
    """
    logger.info("Lambda invocada | event_keys={}", list(event.keys()))

    source = event.get("source", "audio")

    if source == "audio":
        # Busca alertas DETER próximos no banco (em Lambda: via RDS/DynamoDB)
        alertas = _buscar_alertas_deter_proximos(event)
        fusao = fusao_evento(event, alertas)

        if fusao:
            _persistir_fusao(fusao)
            _notificar_orgao(fusao)
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "fusao_gerada": True,
                    "fusao_id": fusao["fusao_id"],
                    "nivel_confianca": fusao["nivel_confianca"],
                    "status": fusao["status"],
                    "mensagem": f"Alerta de fusão criado: {fusao['status']}",
                }, ensure_ascii=False)
            }
        else:
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "fusao_gerada": False,
                    "mensagem": "Evento de áudio registrado — sem alerta DETER próximo ainda",
                })
            }

    elif source == "deter":
        # Verifica se há eventos de áudio recentes para fundir
        eventos = _buscar_eventos_audio_proximos(event)
        fusoes_geradas = []
        for ev in eventos:
            fusao = fusao_evento(ev, [event])
            if fusao:
                _persistir_fusao(fusao)
                fusoes_geradas.append(fusao)

        return {
            "statusCode": 200,
            "body": json.dumps({
                "fusoes_geradas": len(fusoes_geradas),
                "fusoes": [f["fusao_id"] for f in fusoes_geradas],
            })
        }

    return {
        "statusCode": 400,
        "body": json.dumps({"erro": f"Source inválido: {source}"})
    }


def _buscar_alertas_deter_proximos(evento_audio: dict) -> list[dict]:
    """Busca alertas DETER próximos ao evento de áudio no banco local."""
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql(
            "SELECT * FROM alertas_deter WHERE data_deteccao >= ? ORDER BY data_deteccao DESC LIMIT 200",
            conn,
            params=[(datetime.now() - timedelta(days=JANELA_DIAS)).strftime("%Y-%m-%d")]
        )
        conn.close()
        return df.to_dict(orient="records")
    except Exception as e:
        logger.warning("Banco indisponível — usando lista vazia: {}", e)
        return []


def _buscar_eventos_audio_proximos(alerta_deter: dict) -> list[dict]:
    """Busca eventos de áudio recentes próximos ao alerta DETER."""
    try:
        conn = sqlite3.connect(DB_PATH)
        ts_min = int((datetime.now() - timedelta(days=JANELA_DIAS)).timestamp() * 1000)
        df = pd.read_sql(
            "SELECT * FROM eventos_audio WHERE timestamp_ms >= ? AND nivel_alerta IN ('ALTO','MEDIO') ORDER BY timestamp_ms DESC LIMIT 100",
            conn, params=[ts_min]
        )
        conn.close()
        return df.to_dict(orient="records")
    except Exception:
        return []


def _persistir_fusao(fusao: dict):
    """Persiste alerta de fusão no banco."""
    try:
        conn = sqlite3.connect(DB_PATH)
        pd.DataFrame([fusao]).to_sql("alertas_fusao", conn, if_exists="append", index=False)
        conn.close()
        logger.success("Fusão persistida: {}", fusao["fusao_id"])
    except Exception as e:
        logger.warning("Erro ao persistir fusão: {}", e)


def _notificar_orgao(fusao: dict):
    """Simula notificação para órgão ambiental (IBAMA/ICMBio via SNS/SES em produção)."""
    orgao = fusao.get("orgao_notificado")
    if not orgao:
        return

    logger.warning(
        "🚨 NOTIFICAÇÃO {} — Fusão {} | Confiança={:.0%} | "
        "Local: {}/{} | Área: {} km²",
        orgao,
        fusao["fusao_id"],
        fusao["nivel_confianca"],
        fusao.get("municipio", "N/A"),
        fusao.get("estado", "N/A"),
        fusao.get("area_afetada_km2", 0),
    )
    # Em produção: boto3.client("sns").publish(...)


# ─────────────────────────────────────────────────────────────
# API REST local (Flask) — para desenvolvimento/demo
# ─────────────────────────────────────────────────────────────
def iniciar_api_local(porta: int = 5050):
    """Inicia API REST local simulando o API Gateway + Lambda."""
    from flask import Flask, request, jsonify

    app = Flask("SENTINELA-CloudFusion")
    app.config["JSON_ENSURE_ASCII"] = False

    @app.route("/", methods=["GET"])
    def home():
        return jsonify({
            "servico": "SENTINELA — Motor de Fusão",
            "versao": "1.0.0",
            "status": "online",
            "endpoints": {
                "POST /fusao": "Processa evento de áudio ou DETER",
                "GET /alertas": "Lista alertas de fusão",
                "GET /status": "Status do motor",
                "POST /simular": "Simula um evento de áudio",
            }
        })

    @app.route("/fusao", methods=["POST"])
    def fusao_endpoint():
        evento = request.get_json()
        if not evento:
            return jsonify({"erro": "Body JSON inválido"}), 400
        resultado = handler(evento)
        return jsonify(json.loads(resultado["body"])), resultado["statusCode"]

    @app.route("/alertas", methods=["GET"])
    def listar_alertas():
        try:
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql(
                "SELECT * FROM alertas_fusao ORDER BY nivel_confianca DESC LIMIT 50", conn
            )
            conn.close()
            return jsonify(df.to_dict(orient="records"))
        except Exception as e:
            return jsonify({"erro": str(e), "alertas": []}), 500

    @app.route("/status", methods=["GET"])
    def status():
        try:
            conn = sqlite3.connect(DB_PATH)
            n_fusoes = pd.read_sql("SELECT COUNT(*) as n FROM alertas_fusao", conn).iloc[0]["n"]
            n_audio = pd.read_sql("SELECT COUNT(*) as n FROM eventos_audio", conn).iloc[0]["n"]
            n_deter = pd.read_sql("SELECT COUNT(*) as n FROM alertas_deter", conn).iloc[0]["n"]
            conn.close()
            return jsonify({
                "status": "online",
                "banco": str(DB_PATH),
                "total_fusoes": int(n_fusoes),
                "total_eventos_audio": int(n_audio),
                "total_alertas_deter": int(n_deter),
                "timestamp": datetime.now().isoformat(),
            })
        except Exception as e:
            return jsonify({"status": "degradado", "erro": str(e)}), 500

    @app.route("/simular", methods=["POST"])
    def simular_evento():
        """Simula um evento de áudio de alta probabilidade para teste."""
        import random
        evento_simulado = {
            "source": "audio",
            "sensor_id": "ESP32-AM-01-01",
            "tipo_evento": "MOTOSSERRA_CONFIRMADO",
            "probabilidade": round(random.uniform(0.80, 0.98), 3),
            "lat": -3.47 + random.gauss(0, 0.1),
            "lon": -62.22 + random.gauss(0, 0.1),
            "timestamp_ms": int(datetime.now().timestamp() * 1000),
            "nivel_alerta": "ALTO",
        }
        resultado = handler(evento_simulado)
        return jsonify({
            "evento_simulado": evento_simulado,
            "resultado": json.loads(resultado["body"])
        })

    logger.info("=" * 55)
    logger.info("  SENTINELA — Motor de Fusão (API Local)")
    logger.info("  URL: http://localhost:{}", porta)
    logger.info("  Endpoints: GET / | POST /fusao | GET /alertas")
    logger.info("=" * 55)
    app.run(host="0.0.0.0", port=porta, debug=True)


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="SENTINELA — Motor de Fusão (Lambda/Flask)"
    )
    subparsers = parser.add_subparsers(dest="cmd")

    # serve
    sp_serve = subparsers.add_parser("serve", help="Inicia API REST local")
    sp_serve.add_argument("--porta", type=int, default=5050)

    # testar
    subparsers.add_parser("testar", help="Simula evento de fusão")

    # relatorio
    subparsers.add_parser("relatorio", help="Relatório de fusões do banco")

    args = parser.parse_args()

    if args.cmd == "serve":
        iniciar_api_local(args.porta)

    elif args.cmd == "testar":
        logger.info("Simulando evento de áudio de alta probabilidade …")
        evento = {
            "source": "audio",
            "sensor_id": "ESP32-PA-01-01",
            "tipo_evento": "MOTOSSERRA_CONFIRMADO",
            "probabilidade": 0.92,
            "lat": -3.47,
            "lon": -52.25,
            "timestamp_ms": int(datetime.now().timestamp() * 1000),
            "nivel_alerta": "ALTO",
        }
        resultado = handler(evento)
        print(json.dumps(json.loads(resultado["body"]), indent=2, ensure_ascii=False))

    elif args.cmd == "relatorio":
        try:
            conn = sqlite3.connect(DB_PATH)
            df = pd.read_sql("SELECT * FROM alertas_fusao ORDER BY nivel_confianca DESC", conn)
            conn.close()
            if df.empty:
                print("Nenhuma fusão no banco — execute primeiro: python ingest_deter.py")
            else:
                print(df[["fusao_id", "nivel_confianca", "status", "municipio", "estado"]].to_string(index=False))
        except Exception as e:
            logger.error("Erro ao ler banco: {}", e)

    else:
        # Modo Lambda direto
        evento_teste = {
            "source": "audio",
            "sensor_id": "ESP32-TEST",
            "probabilidade": 0.88,
            "lat": -3.4,
            "lon": -62.2,
            "timestamp_ms": int(datetime.now().timestamp() * 1000),
            "nivel_alerta": "ALTO",
        }
        resultado = handler(evento_teste)
        print("Resultado:", json.dumps(json.loads(resultado["body"]), indent=2, ensure_ascii=False))
        print("\nUso: python handler.py serve | testar | relatorio")


if __name__ == "__main__":
    main()
