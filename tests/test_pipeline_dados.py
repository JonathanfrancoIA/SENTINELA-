"""
SENTINELA — Testes: Pipeline de Dados (ingest_deter.py)
========================================================
Testa a geração e persistência de dados simulados DETER.

Execute com:
    pytest tests/test_pipeline_dados.py -v
"""
import sys
import sqlite3
import pytest
import pandas as pd
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "pipeline_dados"))
import ingest_deter as pipeline


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def db_temporario(tmp_path):
    """Cria um banco SQLite temporário para os testes."""
    db = tmp_path / "test_sentinela.db"
    pipeline.criar_banco(db)
    return db


# ─────────────────────────────────────────────────────────────
# Testes: criar_banco
# ─────────────────────────────────────────────────────────────
class TestCriarBanco:
    """Valida a criação do schema do banco de dados."""

    def test_banco_criado(self, tmp_path):
        db = tmp_path / "novo.db"
        pipeline.criar_banco(db)
        assert db.exists()

    def test_tabelas_existem(self, db_temporario):
        conn = sqlite3.connect(db_temporario)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tabelas = {row[0] for row in cursor.fetchall()}
        conn.close()
        esperadas = {"alertas_deter", "eventos_audio", "alertas_fusao", "sensores"}
        assert esperadas.issubset(tabelas), f"Tabelas faltando: {esperadas - tabelas}"

    def test_banco_idempotente(self, tmp_path):
        """Criar banco duas vezes não deve causar erro."""
        db = tmp_path / "idempotente.db"
        pipeline.criar_banco(db)
        pipeline.criar_banco(db)  # segunda vez — não deve lançar
        assert db.exists()


# ─────────────────────────────────────────────────────────────
# Testes: gerar_alertas_simulados
# ─────────────────────────────────────────────────────────────
class TestGerarAlertasSimulados:
    """Valida a geração de alertas DETER sintéticos."""

    def test_quantidade_correta(self):
        df = pipeline.gerar_alertas_simulados(n=50)
        assert len(df) == 50

    def test_colunas_obrigatorias(self):
        df = pipeline.gerar_alertas_simulados(n=10)
        colunas = ["alerta_id", "tipo", "municipio", "estado",
                   "lat", "lon", "area_km2", "data_deteccao", "confianca"]
        for col in colunas:
            assert col in df.columns, f"Coluna ausente: {col}"

    def test_area_km2_positiva(self):
        df = pipeline.gerar_alertas_simulados(n=100)
        assert (df["area_km2"] > 0).all()

    def test_coordenadas_na_amazonia(self):
        """Coordenadas devem estar na região da Amazônia Legal (aproximada)."""
        df = pipeline.gerar_alertas_simulados(n=100)
        # Amazônia Legal: lat ≈ -15 a 5, lon ≈ -75 a -44
        assert df["lat"].between(-20, 5).all()
        assert df["lon"].between(-80, -40).all()

    def test_confianca_intervalo(self):
        df = pipeline.gerar_alertas_simulados(n=100)
        assert df["confianca"].between(0.0, 1.0).all()

    def test_alerta_ids_unicos(self):
        df = pipeline.gerar_alertas_simulados(n=100)
        assert df["alerta_id"].nunique() == len(df)

    def test_tipos_validos(self):
        df = pipeline.gerar_alertas_simulados(n=100)
        tipos_validos = set(pipeline.TIPOS_ALERTA_DETER)
        assert set(df["tipo"]).issubset(tipos_validos)


# ─────────────────────────────────────────────────────────────
# Testes: gerar_sensores_simulados
# ─────────────────────────────────────────────────────────────
class TestGerarSensoresSimulados:
    """Valida a geração de sensores ESP32 simulados."""

    def test_sensores_gerados(self):
        df = pipeline.gerar_sensores_simulados()
        assert len(df) >= len(pipeline.MUNICIPIOS_AMAZONIA)

    def test_colunas_sensores(self):
        df = pipeline.gerar_sensores_simulados()
        colunas = ["sensor_id", "lat", "lon", "municipio", "estado", "ativo"]
        for col in colunas:
            assert col in df.columns

    def test_ids_unicos(self):
        df = pipeline.gerar_sensores_simulados()
        assert df["sensor_id"].nunique() == len(df)

    def test_campo_ativo_booleano(self):
        df = pipeline.gerar_sensores_simulados()
        assert df["ativo"].dtype == bool or set(df["ativo"].unique()).issubset({0, 1, True, False})


# ─────────────────────────────────────────────────────────────
# Testes: persistir_dataframe
# ─────────────────────────────────────────────────────────────
class TestPersistirDataframe:
    """Valida a persistência de dados no banco."""

    def test_persistencia_e_contagem(self, db_temporario):
        df = pipeline.gerar_alertas_simulados(n=30)
        n = pipeline.persistir_dataframe(df, "alertas_deter", db_temporario, "replace")
        assert n == 30

        conn = sqlite3.connect(db_temporario)
        count = conn.execute("SELECT COUNT(*) FROM alertas_deter").fetchone()[0]
        conn.close()
        assert count == 30

    def test_replace_sobrescreve(self, db_temporario):
        """if_exists='replace' deve substituir dados anteriores."""
        df1 = pipeline.gerar_alertas_simulados(n=20)
        df2 = pipeline.gerar_alertas_simulados(n=10)

        pipeline.persistir_dataframe(df1, "alertas_deter", db_temporario, "replace")
        pipeline.persistir_dataframe(df2, "alertas_deter", db_temporario, "replace")

        conn = sqlite3.connect(db_temporario)
        count = conn.execute("SELECT COUNT(*) FROM alertas_deter").fetchone()[0]
        conn.close()
        assert count == 10

    def test_append_acumula(self, db_temporario):
        """if_exists='append' deve acumular dados."""
        df = pipeline.gerar_alertas_simulados(n=15)
        pipeline.persistir_dataframe(df, "alertas_deter", db_temporario, "replace")
        pipeline.persistir_dataframe(df, "alertas_deter", db_temporario, "append")

        conn = sqlite3.connect(db_temporario)
        count = conn.execute("SELECT COUNT(*) FROM alertas_deter").fetchone()[0]
        conn.close()
        assert count == 30


# ─────────────────────────────────────────────────────────────
# Testes: exportar_json
# ─────────────────────────────────────────────────────────────
class TestExportarJson:
    """Valida a exportação do banco para JSON."""

    def test_json_gerado(self, db_temporario, tmp_path):
        # Popula o banco
        df_d = pipeline.gerar_alertas_simulados(n=10)
        df_s = pipeline.gerar_sensores_simulados()
        df_a = pipeline.gerar_eventos_audio_simulados(df_s, n=20)
        pipeline.persistir_dataframe(df_d, "alertas_deter", db_temporario, "replace")
        pipeline.persistir_dataframe(df_s, "sensores", db_temporario, "replace")
        pipeline.persistir_dataframe(df_a, "eventos_audio", db_temporario, "replace")

        output = tmp_path / "export.json"
        pipeline.exportar_json(db_temporario, output)
        assert output.exists()

    def test_json_estrutura(self, db_temporario, tmp_path):
        """JSON exportado deve ter as chaves esperadas."""
        import json
        # Popula apenas alertas_deter (as outras tabelas já existem do criar_banco)
        df_d = pipeline.gerar_alertas_simulados(n=5)
        pipeline.persistir_dataframe(df_d, "alertas_deter", db_temporario, "replace")

        output = tmp_path / "export_test.json"
        pipeline.exportar_json(db_temporario, output)

        with open(output) as f:
            data = json.load(f)

        assert "alertas_deter" in data
        assert "gerado_em" in data
        assert isinstance(data["alertas_deter"], list)
