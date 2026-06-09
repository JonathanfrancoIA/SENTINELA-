#!/usr/bin/env python3
"""
SENTINELA — Assinante MQTT (ponte ESP32 → SQLite)
=================================================
Escuta o tópico MQTT onde os ESP32 (reais OU o ESP32 virtual do Wokwi)
publicam alertas de áudio e grava cada evento na tabela `eventos_audio`
do banco SQLite — o mesmo que o dashboard e o motor de fusão consomem.

Fecha o ciclo:
    ESP32 (Wokwi) ──MQTT──► este script ──► SQLite ──► Dashboard / Fusão

Payload esperado (igual ao firmware):
    {
      "sensor_id": "ESP32-FLORESTA-AM-01",
      "tipo": "MOTOSSERRA_CONFIRMADO",
      "probabilidade": 0.95,
      "lat": -3.4653, "lon": -62.2159,
      "timestamp_ms": 123456,
      "nivel_alerta": "ALTO"
    }

Dependências:
    pip install paho-mqtt

Uso:
    python src/pipeline_dados/mqtt_subscriber.py
    python src/pipeline_dados/mqtt_subscriber.py --broker broker.hivemq.com \
        --topic sentinela/alertas --db src/pipeline_dados/data/sentinela.db
"""

import os
import sys
import json
import time
import argparse
import sqlite3
from datetime import datetime
from pathlib import Path

# Console do Windows às vezes usa cp1252 e quebra em caracteres como "→".
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

try:
    import paho.mqtt.client as mqtt
except ImportError:
    print("ERRO: paho-mqtt não instalado. Rode:  pip install paho-mqtt")
    sys.exit(1)

# Carrega .env se disponível (opcional)
try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
except Exception:
    pass


def garantir_tabela(db_path: str):
    """Cria a tabela eventos_audio se ainda não existir (mesmo schema do ingest)."""
    conn = sqlite3.connect(db_path)
    # Schema IDÊNTICO ao criado por ingest_deter.py (e lido pelo dashboard).
    # Sem colunas extras — assinante e dashboard usam exatamente o mesmo formato.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS eventos_audio (
            sensor_id       TEXT,
            tipo_evento     TEXT,
            probabilidade   REAL,
            lat             REAL,
            lon             REAL,
            timestamp_ms    INTEGER,
            nivel_alerta    TEXT
        )
    """)
    conn.commit()
    conn.close()


def gravar_evento(db_path: str, dados: dict):
    # O ESP32 (Wokwi) envia timestamp_ms = millis() desde o boot (número pequeno).
    # Para o evento cair na hora certa do dashboard, usamos o tempo real atual
    # quando o valor recebido não for um epoch-ms plausível.
    ts = dados.get("timestamp_ms")
    try:
        ts = int(ts)
    except (TypeError, ValueError):
        ts = 0
    if ts < 1_000_000_000_000:  # menor que ~2001 em ms → não é epoch real
        ts = int(time.time() * 1000)

    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO eventos_audio
           (sensor_id, tipo_evento, probabilidade, lat, lon, timestamp_ms, nivel_alerta)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            dados.get("sensor_id", "DESCONHECIDO"),
            dados.get("tipo", dados.get("tipo_evento", "EVENTO")),
            float(dados.get("probabilidade", 0) or 0),
            dados.get("lat"),
            dados.get("lon"),
            ts,
            dados.get("nivel_alerta"),
        ),
    )
    conn.commit()
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="SENTINELA — assinante MQTT → SQLite")
    parser.add_argument("--broker", default=os.getenv("MQTT_SERVER", "broker.hivemq.com"))
    parser.add_argument("--port", type=int, default=int(os.getenv("MQTT_PORT", 1883)))
    parser.add_argument("--topic", default=os.getenv("MQTT_TOPIC", "sentinela/alertas"))
    # Caminho do banco SEMPRE relativo a este script (não ao diretório atual),
    # garantindo que assinante e dashboard usem o MESMO arquivo sentinela.db.
    _db_padrao = str(Path(__file__).resolve().parent / "data" / "sentinela.db")
    parser.add_argument("--db", default=os.getenv("DB_PATH", _db_padrao))
    parser.add_argument("--user", default=os.getenv("MQTT_USER", ""))
    parser.add_argument("--password", default=os.getenv("MQTT_PASSWORD", ""))
    args = parser.parse_args()

    Path(args.db).parent.mkdir(parents=True, exist_ok=True)
    garantir_tabela(args.db)

    contador = {"n": 0}

    def on_connect(client, userdata, flags, rc, *_):
        if rc == 0:
            print(f"[MQTT] Conectado a {args.broker}:{args.port}")
            client.subscribe(args.topic)
            print(f"[MQTT] Assinando '{args.topic}' — aguardando alertas do ESP32 …")
        else:
            print(f"[MQTT] Falha na conexão (rc={rc})")

    def on_message(client, userdata, msg):
        try:
            dados = json.loads(msg.payload.decode("utf-8"))
        except Exception as e:
            print(f"[MQTT] Payload inválido ignorado: {e}")
            return
        gravar_evento(args.db, dados)
        contador["n"] += 1
        prob = float(dados.get("probabilidade", 0) or 0)
        print(f"[#{contador['n']:03d}] {dados.get('sensor_id','?'):>22} | "
              f"{dados.get('tipo','?'):<22} | prob={prob:.2f} | "
              f"nivel={dados.get('nivel_alerta','?')} → gravado em eventos_audio")

    # Compatível com paho-mqtt 1.x e 2.x
    try:
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    except (AttributeError, TypeError):
        client = mqtt.Client()

    if args.user:
        client.username_pw_set(args.user, args.password)
    client.on_connect = on_connect
    client.on_message = on_message

    print("=" * 60)
    print("  SENTINELA — Ponte MQTT → SQLite (ESP32 Wokwi → Dashboard)")
    print(f"  Broker: {args.broker}:{args.port}  |  Tópico: {args.topic}")
    print(f"  Banco:  {args.db}")
    print("=" * 60)

    client.connect(args.broker, args.port, keepalive=60)
    try:
        client.loop_forever()
    except KeyboardInterrupt:
        print(f"\n[FIM] {contador['n']} eventos gravados. Encerrando.")
        client.disconnect()


if __name__ == "__main__":
    main()
