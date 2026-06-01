#!/usr/bin/env python3
"""
SENTINELA — Pipeline de Dados / Ingestão INPE-DETER
====================================================
Ingere alertas de desmatamento do INPE/DETER (dados públicos),
normaliza e persiste em banco SQLite, pronto para consulta
pelo motor de fusão e pelo dashboard.

Fontes de dados:
    - INPE/DETER (REAL): WFS público do TerraBrasilis (GeoServer), camada
      deter-amz:deter_public — GeoJSON, sem credenciais.
    - INPE/PRODES: dados anuais consolidados
    - IBGE: malha municipal (referência geográfica)

Status: ✅ Funcional — ingestão REAL do DETER/INPE via WFS, com fallback
        automático para dados simulados caso a rede/serviço esteja indisponível.

Uso:
    python ingest_deter.py                   # ingestão completa (simulada)
    python ingest_deter.py --fonte real      # baixa DETER REAL (WFS TerraBrasilis)
    python ingest_deter.py --exportar-json   # exporta banco para JSON
    python ingest_deter.py --stats           # mostra estatísticas

Dependências:
    pip install pandas sqlalchemy requests loguru
    # (geopandas NÃO é mais necessário — o GeoJSON é parseado diretamente)
"""

import os
import sys
import json
import sqlite3
import argparse
import warnings
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from loguru import logger

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────
DB_PATH = Path("data/sentinela.db")

# ── INPE / DETER — TerraBrasilis WFS (GeoServer público, sem credenciais) ──
# Endpoint OWS/WFS do GeoServer do TerraBrasilis e camada pública do DETER
# para a Amazônia Legal. A requisição GetFeature devolve GeoJSON diretamente.
DETER_WFS_URL = "https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/wfs"
DETER_LAYER = "deter-amz:deter_public"
# (Legado) ZIP estático — mantido apenas como referência histórica.
DETER_URL = "http://terrabrasilis.dpi.inpe.br/downloads/DETER-B.zip"

# Municípios reais da Amazônia Legal (para simulação realista)
MUNICIPIOS_AMAZONIA = [
    ("Altamira", "PA", -52.2, -3.2),
    ("Itaituba", "PA", -55.98, -4.28),
    ("São Félix do Xingu", "PA", -51.99, -6.64),
    ("Porto Velho", "RO", -63.9, -8.76),
    ("Humaitá", "AM", -63.01, -7.51),
    ("Apuí", "AM", -59.89, -7.2),
    ("Novo Progresso", "PA", -55.4, -7.12),
    ("Lábrea", "AM", -64.8, -7.26),
    ("Boca do Acre", "AM", -67.38, -8.75),
    ("Colniza", "MT", -59.0, -9.36),
    ("Juruena", "MT", -58.49, -10.31),
    ("Guarantã do Norte", "MT", -54.89, -9.8),
    ("Alta Floresta", "MT", -56.08, -9.87),
    ("Sinop", "MT", -55.5, -11.86),
    ("Parana", "MT", -57.9, -12.6),
]

TIPOS_ALERTA_DETER = ["DETER-B CORTE RASO", "DETER-B DEGRADACAO",
                       "DETER-B MINERACAO", "DETER-B QUEIMADA"]
CLASSES_VEGETACAO = ["FLORESTA", "CERRADO", "CAMPO"]


# ─────────────────────────────────────────────────────────────
# Banco de dados
# ─────────────────────────────────────────────────────────────
def criar_banco(db_path: Path = DB_PATH):
    """Cria o banco SQLite com schema do SENTINELA."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    c = conn.cursor()

    # Alertas do DETER/PRODES
    c.execute("""
        CREATE TABLE IF NOT EXISTS alertas_deter (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            alerta_id       TEXT UNIQUE NOT NULL,
            tipo            TEXT NOT NULL,
            classe_veg      TEXT,
            municipio       TEXT,
            estado          TEXT,
            lon             REAL,
            lat             REAL,
            area_km2        REAL,
            data_deteccao   TEXT NOT NULL,
            data_imagem     TEXT,
            satellite       TEXT DEFAULT 'Sentinel-2',
            confianca       REAL DEFAULT 1.0,
            processado      INTEGER DEFAULT 0,
            criado_em       TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Eventos de áudio dos sensores ESP32
    c.execute("""
        CREATE TABLE IF NOT EXISTS eventos_audio (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id       TEXT NOT NULL,
            tipo_evento     TEXT NOT NULL,
            probabilidade   REAL NOT NULL,
            lat             REAL,
            lon             REAL,
            timestamp_ms    INTEGER,
            nivel_alerta    TEXT,
            processado      INTEGER DEFAULT 0,
            criado_em       TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Alertas de fusão (saída do motor)
    c.execute("""
        CREATE TABLE IF NOT EXISTS alertas_fusao (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            fusao_id        TEXT UNIQUE NOT NULL,
            alerta_deter_id TEXT,
            evento_audio_id INTEGER,
            nivel_confianca REAL NOT NULL,
            lat             REAL,
            lon             REAL,
            raio_km         REAL DEFAULT 5.0,
            status          TEXT DEFAULT 'PENDENTE',
            orgao_notificado TEXT,
            criado_em       TEXT DEFAULT CURRENT_TIMESTAMP,
            atualizado_em   TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Sensores cadastrados
    c.execute("""
        CREATE TABLE IF NOT EXISTS sensores (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            sensor_id       TEXT UNIQUE NOT NULL,
            nome            TEXT,
            lat             REAL,
            lon             REAL,
            municipio       TEXT,
            estado          TEXT,
            ativo           INTEGER DEFAULT 1,
            ultimo_heartbeat TEXT,
            firmware_ver    TEXT DEFAULT '1.0.0',
            instalado_em    TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()
    logger.success("Banco de dados criado/verificado em {}", db_path)


# ─────────────────────────────────────────────────────────────
# Geração de dados sintéticos realistas
# ─────────────────────────────────────────────────────────────
def gerar_alertas_simulados(n: int = 120) -> pd.DataFrame:
    """
    Gera alertas do DETER simulados com distribuição realista.
    Baseado na distribuição real do DETER-B (2023-2024).
    """
    random.seed(42)
    np.random.seed(42)

    alertas = []
    data_base = datetime.now() - timedelta(days=90)

    for i in range(n):
        mun, est, lon, lat = random.choice(MUNICIPIOS_AMAZONIA)
        # Dispersão espacial em torno do município
        lon_r = lon + random.gauss(0, 0.5)
        lat_r = lat + random.gauss(0, 0.5)

        # Área log-normal (maioria pequenas, algumas grandes — distribuição DETER real)
        area = round(float(np.random.lognormal(2.0, 1.5)) / 100, 4)  # km²
        area = max(0.01, min(area, 150.0))

        tipo = random.choices(
            TIPOS_ALERTA_DETER,
            weights=[60, 25, 5, 10],  # corte raso mais frequente
        )[0]

        data_det = data_base + timedelta(days=random.randint(0, 89))
        data_img = data_det - timedelta(days=random.randint(1, 10))

        alertas.append({
            "alerta_id": f"DETER-{data_det.strftime('%Y%m%d')}-{i+1:05d}",
            "tipo": tipo,
            "classe_veg": random.choice(CLASSES_VEGETACAO),
            "municipio": mun,
            "estado": est,
            "lon": round(lon_r, 6),
            "lat": round(lat_r, 6),
            "area_km2": area,
            "data_deteccao": data_det.strftime("%Y-%m-%d"),
            "data_imagem": data_img.strftime("%Y-%m-%d"),
            "satellite": "Sentinel-2",
            "confianca": round(random.uniform(0.7, 1.0), 2),
        })

    df = pd.DataFrame(alertas)
    logger.info("Gerados {} alertas DETER simulados", len(df))
    return df


def gerar_sensores_simulados() -> pd.DataFrame:
    """Gera sensores ESP32 simulados posicionados na floresta."""
    sensores = []
    for i, (mun, est, lon, lat) in enumerate(MUNICIPIOS_AMAZONIA):
        # 1-2 sensores por município
        n_sens = random.randint(1, 2)
        for j in range(n_sens):
            sensor_id = f"ESP32-{est}-{i+1:02d}-{j+1:02d}"
            ultimo_hb = datetime.now() - timedelta(minutes=random.randint(1, 120))
            sensores.append({
                "sensor_id": sensor_id,
                "nome": f"Sensor {mun} {j+1}",
                "lat": round(lat + random.gauss(0, 0.2), 6),
                "lon": round(lon + random.gauss(0, 0.2), 6),
                "municipio": mun,
                "estado": est,
                "ativo": random.choice([1, 1, 1, 0]),  # 75% ativos
                "ultimo_heartbeat": ultimo_hb.isoformat(),
                "firmware_ver": "1.0.0",
            })

    return pd.DataFrame(sensores)


def gerar_eventos_audio_simulados(sensores_df: pd.DataFrame, n: int = 200) -> pd.DataFrame:
    """Gera eventos de áudio simulados dos sensores."""
    eventos = []
    data_base = datetime.now() - timedelta(days=30)

    for _ in range(n):
        sensor = sensores_df.sample(1).iloc[0]
        ts = data_base + timedelta(
            days=random.randint(0, 29),
            hours=random.randint(5, 20),  # mais eventos durante o dia
            minutes=random.randint(0, 59)
        )
        prob = random.betavariate(2, 5)  # maioria baixa prob, alguns altos
        nivel = "ALTO" if prob >= 0.85 else "MEDIO" if prob >= 0.70 else "BAIXO"
        tipo = "MOTOSSERRA_CONFIRMADO" if prob >= 0.85 else \
               "MOTOR_SUSPEITO" if prob >= 0.60 else "RUIDO_AMBIENTE"

        eventos.append({
            "sensor_id": sensor["sensor_id"],
            "tipo_evento": tipo,
            "probabilidade": round(prob, 4),
            "lat": sensor["lat"],
            "lon": sensor["lon"],
            "timestamp_ms": int(ts.timestamp() * 1000),
            "nivel_alerta": nivel,
        })

    return pd.DataFrame(eventos)


def gerar_alertas_fusao_simulados(alertas_deter: pd.DataFrame,
                                   eventos_audio: pd.DataFrame,
                                   n: int = 15) -> pd.DataFrame:
    """
    Simula saída do motor de fusão: cruza alertas DETER com eventos de áudio
    próximos (janela de 10 km e 7 dias).
    """
    fusoes = []
    for i in range(min(n, len(alertas_deter))):
        alerta = alertas_deter.iloc[i]
        evento = eventos_audio[eventos_audio["nivel_alerta"] == "ALTO"].sample(1).iloc[0] \
                 if len(eventos_audio[eventos_audio["nivel_alerta"] == "ALTO"]) > 0 \
                 else eventos_audio.sample(1).iloc[0]

        conf = min(1.0, round(alerta["confianca"] * 0.6 + evento["probabilidade"] * 0.4, 3))
        status = "CONFIRMADO" if conf >= 0.80 else "SUSPEITO"

        fusoes.append({
            "fusao_id": f"FUSAO-{datetime.now().strftime('%Y%m%d')}-{i+1:04d}",
            "alerta_deter_id": alerta["alerta_id"],
            "nivel_confianca": conf,
            "lat": (alerta["lat"] + evento["lat"]) / 2,
            "lon": (alerta["lon"] + evento["lon"]) / 2,
            "raio_km": 5.0,
            "status": status,
            "orgao_notificado": "IBAMA" if conf >= 0.90 else "ICMBio" if conf >= 0.80 else None,
        })

    return pd.DataFrame(fusoes)


# ─────────────────────────────────────────────────────────────
# Ingestão de dados reais (INPE/DETER via TerraBrasilis WFS)
# ─────────────────────────────────────────────────────────────
def _primeiro_valor(props: dict, *chaves, default=None):
    """Retorna o primeiro valor não-nulo dentre uma lista de chaves possíveis.

    O esquema da camada pública do DETER já mudou de nome de coluna algumas
    vezes (ex.: 'class_name' vs 'classname', 'areamunkm' vs 'areauckm'), então
    tentamos várias chaves para ficar robustos a essas variações.
    """
    for c in chaves:
        if c in props and props[c] not in (None, ""):
            return props[c]
    return default


def _centroide_geojson(geom: dict):
    """Calcula um centroide aproximado (média dos vértices) de uma geometria
    GeoJSON Polygon ou MultiPolygon, sem depender de shapely/geopandas.

    Retorna (lon, lat) ou (None, None) se não for possível.
    """
    if not geom:
        return None, None

    coords_planas = []

    def _coletar(seq):
        # Desce recursivamente até encontrar pares [lon, lat]
        if (isinstance(seq, (list, tuple)) and len(seq) >= 2
                and isinstance(seq[0], (int, float))
                and isinstance(seq[1], (int, float))):
            coords_planas.append((float(seq[0]), float(seq[1])))
            return
        if isinstance(seq, (list, tuple)):
            for item in seq:
                _coletar(item)

    _coletar(geom.get("coordinates", []))
    if not coords_planas:
        return None, None

    lon = sum(p[0] for p in coords_planas) / len(coords_planas)
    lat = sum(p[1] for p in coords_planas) / len(coords_planas)
    return round(lon, 6), round(lat, 6)


def _mapear_tipo_deter(class_name: str) -> str:
    """Mapeia a classe crua do DETER para os rótulos usados no SENTINELA."""
    if not class_name:
        return "DETER-B CORTE RASO"
    c = str(class_name).upper()
    if "MINERA" in c:
        return "DETER-B MINERACAO"
    if "QUEIMAD" in c or "FOGO" in c or "INCEND" in c:
        return "DETER-B QUEIMADA"
    if "DEGRADA" in c:
        return "DETER-B DEGRADACAO"
    if "CICATRIZ" in c:
        return "DETER-B QUEIMADA"
    # CORTE_RASO, DESMATAMENTO_CR, DESMATAMENTO_VEG, MINERACAO etc.
    return "DETER-B CORTE RASO"


def tentar_ingestao_real(limite: int = 500, dias: int = 90) -> Optional[pd.DataFrame]:
    """
    Baixa alertas REAIS do INPE/DETER (Amazônia Legal) via WFS público do
    TerraBrasilis (GeoServer), em GeoJSON, sem necessidade de credenciais.

    Args:
        limite: nº máximo de feições a baixar (param WFS ``count``).
        dias:   janela temporal — só alertas com ``view_date`` nos últimos N dias.

    Retorna um DataFrame no mesmo esquema de ``gerar_alertas_simulados`` ou
    ``None`` se a requisição falhar (o chamador faz fallback para simulado).
    """
    try:
        import requests
    except ImportError:
        logger.warning("Pacote 'requests' ausente — instale com 'pip install requests'. "
                       "Usando dados simulados.")
        return None

    data_corte = (datetime.now() - timedelta(days=dias)).strftime("%Y-%m-%d")

    params = {
        "service": "WFS",
        "version": "2.0.0",
        "request": "GetFeature",
        "typeName": DETER_LAYER,
        "outputFormat": "application/json",
        "srsName": "EPSG:4326",
        "count": str(limite),
        # Só alertas recentes (filtro CQL no atributo de data de detecção).
        "CQL_FILTER": f"view_date>='{data_corte}'",
    }

    try:
        logger.info("Consultando DETER real (WFS) em {} …", DETER_WFS_URL)
        r = requests.get(DETER_WFS_URL, params=params, timeout=60,
                         headers={"User-Agent": "SENTINELA/1.0 (FIAP GS 2026)"})
        r.raise_for_status()
        data = r.json()
    except Exception as e:
        # Se o atributo de data tiver outro nome nesta versão da camada, o
        # CQL_FILTER causa erro 400 — tenta de novo sem o filtro temporal.
        logger.warning("1ª tentativa WFS falhou ({}); tentando consulta simplificada …", e)
        try:
            params.pop("CQL_FILTER", None)
            r = requests.get(DETER_WFS_URL, params=params, timeout=60,
                             headers={"User-Agent": "SENTINELA/1.0 (FIAP GS 2026)"})
            r.raise_for_status()
            data = r.json()
        except Exception as e2:
            logger.warning("Falha na ingestão real: {} — usando dados simulados", e2)
            return None

    feicoes = data.get("features", []) if isinstance(data, dict) else []
    if not feicoes:
        logger.warning("WFS respondeu sem feições — usando dados simulados")
        return None

    registros = []
    for i, feat in enumerate(feicoes):
        props = feat.get("properties", {}) or {}
        geom = feat.get("geometry", {}) or {}

        lon, lat = _centroide_geojson(geom)
        if lon is None:
            continue  # sem geometria utilizável

        class_name = _primeiro_valor(props, "class_name", "classname", "classe")
        view_date = _primeiro_valor(props, "view_date", "date", "data",
                                    default=datetime.now().strftime("%Y-%m-%d"))
        area = _primeiro_valor(props, "areamunkm", "areauckm", "areakm2",
                               "area_km2", "area", default=0.0)
        try:
            area = round(float(area), 4)
        except (TypeError, ValueError):
            area = 0.0

        gid = _primeiro_valor(props, "origin_gid", "gid", "uuid", "id", default=i + 1)
        data_str = str(view_date)[:10]

        registros.append({
            "alerta_id": f"DETER-{data_str.replace('-', '')}-{str(gid)[:12]}",
            "tipo": _mapear_tipo_deter(class_name),
            "classe_veg": "FLORESTA",
            "municipio": _primeiro_valor(props, "municipality", "municipio",
                                         "county", "nome_municipio", default=""),
            "estado": _primeiro_valor(props, "uf", "estado", "sigla_uf", default=""),
            "lon": lon,
            "lat": lat,
            "area_km2": area,
            "data_deteccao": data_str,
            "data_imagem": str(_primeiro_valor(props, "date_image", "image_date",
                                               default=""))[:10],
            "satellite": _primeiro_valor(props, "satellite", "sensor", default="DETER/INPE"),
            # Alerta oficial do DETER → confiança máxima na fonte.
            "confianca": 1.0,
        })

    if not registros:
        logger.warning("Nenhuma feição com geometria válida — usando dados simulados")
        return None

    df = pd.DataFrame(registros)
    logger.success("DETER REAL baixado via WFS: {} alertas (últimos {} dias)",
                   len(df), dias)
    return df


# ─────────────────────────────────────────────────────────────
# Persistência
# ─────────────────────────────────────────────────────────────
def persistir_dataframe(df: pd.DataFrame, tabela: str,
                         db_path: Path = DB_PATH,
                         if_exists: str = "append") -> int:
    """Persiste DataFrame no banco SQLite."""
    from sqlalchemy import create_engine
    engine = create_engine(f"sqlite:///{db_path}")
    df.to_sql(tabela, engine, if_exists=if_exists, index=False)
    logger.success("Persistidos {} registros em {}.{}", len(df), db_path.name, tabela)
    return len(df)


# ─────────────────────────────────────────────────────────────
# Consultas e estatísticas
# ─────────────────────────────────────────────────────────────
def estatisticas(db_path: Path = DB_PATH):
    """Exibe estatísticas do banco."""
    conn = sqlite3.connect(db_path)

    print("\n" + "=" * 60)
    print("  SENTINELA — Estatísticas do Banco de Dados")
    print("=" * 60)

    tabelas = ["alertas_deter", "eventos_audio", "alertas_fusao", "sensores"]
    for t in tabelas:
        try:
            count = pd.read_sql(f"SELECT COUNT(*) as n FROM {t}", conn).iloc[0]["n"]
            print(f"  {t:<25} {count:>6} registros")
        except Exception:
            print(f"  {t:<25} (tabela não encontrada)")

    print()

    # Top estados com mais alertas
    try:
        df = pd.read_sql(
            "SELECT estado, COUNT(*) as n, SUM(area_km2) as area_total "
            "FROM alertas_deter GROUP BY estado ORDER BY n DESC LIMIT 5",
            conn
        )
        print("  Top estados — Alertas DETER:")
        for _, row in df.iterrows():
            print(f"    {row['estado']}: {int(row['n'])} alertas | {row['area_total']:.2f} km²")
    except Exception as e:
        logger.warning("Erro nas estatísticas: {}", e)

    print()

    # Fusões por status
    try:
        df = pd.read_sql(
            "SELECT status, COUNT(*) as n, AVG(nivel_confianca) as conf_media "
            "FROM alertas_fusao GROUP BY status",
            conn
        )
        print("  Alertas de Fusão por Status:")
        for _, row in df.iterrows():
            print(f"    {row['status']}: {int(row['n'])} | confiança média={row['conf_media']:.2f}")
    except Exception:
        pass

    print("=" * 60 + "\n")
    conn.close()


def exportar_json(db_path: Path = DB_PATH, output_path: Path = Path("data/export.json")):
    """Exporta banco para JSON (para o dashboard)."""
    conn = sqlite3.connect(db_path)

    export = {
        "gerado_em": datetime.now().isoformat(),
        "alertas_deter": pd.read_sql("SELECT * FROM alertas_deter ORDER BY data_deteccao DESC", conn).to_dict(orient="records"),
        "eventos_audio": pd.read_sql("SELECT * FROM eventos_audio ORDER BY timestamp_ms DESC LIMIT 500", conn).to_dict(orient="records"),
        "alertas_fusao": pd.read_sql("SELECT * FROM alertas_fusao ORDER BY nivel_confianca DESC", conn).to_dict(orient="records"),
        "sensores": pd.read_sql("SELECT * FROM sensores", conn).to_dict(orient="records"),
    }

    conn.close()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export, f, indent=2, ensure_ascii=False, default=str)

    logger.success("Banco exportado para {}", output_path)
    return output_path


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="SENTINELA — Ingestão de dados INPE/DETER e eventos IoT"
    )
    parser.add_argument("--fonte", choices=["simulado", "real"], default="simulado",
                        help="Fonte dos dados (simulado usa dados sintéticos)")
    parser.add_argument("--exportar-json", action="store_true",
                        help="Exporta banco para JSON após ingestão")
    parser.add_argument("--stats", action="store_true",
                        help="Mostra estatísticas do banco")
    parser.add_argument("--db", type=Path, default=DB_PATH,
                        help="Caminho do banco SQLite")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("  SENTINELA — Pipeline de Dados / Ingestão DETER")
    logger.info("  Fonte: {}", args.fonte.upper())
    logger.info("=" * 60)

    criar_banco(args.db)

    # Alertas DETER
    if args.fonte == "real":
        df_deter = tentar_ingestao_real()
        if df_deter is None:
            logger.info("Fallback para dados simulados")
            df_deter = gerar_alertas_simulados()
    else:
        df_deter = gerar_alertas_simulados()

    persistir_dataframe(df_deter, "alertas_deter", args.db, if_exists="replace")

    # Sensores
    df_sensores = gerar_sensores_simulados()
    persistir_dataframe(df_sensores, "sensores", args.db, if_exists="replace")

    # Eventos de áudio
    df_audio = gerar_eventos_audio_simulados(df_sensores)
    persistir_dataframe(df_audio, "eventos_audio", args.db, if_exists="replace")

    # Alertas de fusão
    df_fusao = gerar_alertas_fusao_simulados(df_deter, df_audio)
    persistir_dataframe(df_fusao, "alertas_fusao", args.db, if_exists="replace")

    if args.stats or True:  # sempre mostra estatísticas
        estatisticas(args.db)

    if args.exportar_json:
        exportar_json(args.db)

    logger.success("Ingestão concluída! Banco em: {}", args.db)


if __name__ == "__main__":
    main()
