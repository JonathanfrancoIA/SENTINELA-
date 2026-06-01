"""
SENTINELA — Testes: Visão Computacional (detectar_desmatamento.py)
==================================================================
Testa o pipeline de detecção de desmatamento via NDVI.

Execute com:
    pytest tests/test_visao_computacional.py -v
"""
import sys
import pytest
import numpy as np
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "visao_computacional"))
import detectar_desmatamento as vc


# ─────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────
@pytest.fixture
def imagem_floresta():
    """NDVI alto — floresta densa."""
    return np.full((64, 64), 0.75, dtype=np.float32)


@pytest.fixture
def imagem_desmatada():
    """NDVI baixo — solo exposto."""
    return np.full((64, 64), 0.10, dtype=np.float32)


@pytest.fixture
def imagem_com_mancha():
    """NDVI alto com mancha central de desmatamento."""
    img = np.full((64, 64), 0.75, dtype=np.float32)
    img[20:44, 20:44] = 0.05  # mancha 24x24 pixels
    return img


@pytest.fixture
def par_sintetico():
    """Par antes/depois gerado pelo modo demo."""
    return vc.gerar_imagem_sintetica(h=128, w=128, n_manchas=3)


# ─────────────────────────────────────────────────────────────
# Testes: calcular_ndvi
# ─────────────────────────────────────────────────────────────
class TestCalcularNDVI:
    """Valida o cálculo de NDVI a partir de bandas Red/NIR."""

    def test_floresta_ndvi_alto(self):
        """Floresta densa deve ter NDVI próximo de 1."""
        # NIR muito maior que Red → NDVI alto
        data = np.array([
            [[0.05] * 10],  # Red baixo (banda 0)
            [[0.80] * 10],  # NIR alto (banda 1)
        ], dtype=np.float32).reshape(2, 1, 10)
        ndvi = vc.calcular_ndvi(data)
        assert ndvi.mean() > 0.8

    def test_solo_exposto_ndvi_baixo(self):
        """Solo exposto tem NDVI baixo (próximo de 0 ou negativo)."""
        data = np.array([
            [[0.30] * 10],  # Red alto
            [[0.10] * 10],  # NIR baixo
        ], dtype=np.float32).reshape(2, 1, 10)
        ndvi = vc.calcular_ndvi(data)
        assert ndvi.mean() < 0.0

    def test_ndvi_limites(self):
        """NDVI deve estar sempre entre -1 e +1."""
        np.random.seed(0)
        data = np.random.uniform(0, 1, (2, 50, 50)).astype(np.float32)
        ndvi = vc.calcular_ndvi(data)
        assert ndvi.min() >= -1.0
        assert ndvi.max() <= 1.0

    def test_ndvi_formato_saida(self):
        """NDVI deve ter mesma forma espacial que as bandas de entrada."""
        data = np.random.uniform(0, 1, (2, 32, 32)).astype(np.float32)
        ndvi = vc.calcular_ndvi(data)
        assert ndvi.shape == (32, 32)

    def test_ndvi_sentinela2_scale(self):
        """Valores Sentinel-2 Level-2A (0–10000) devem ser normalizados."""
        data = np.random.uniform(0, 8000, (2, 10, 10)).astype(np.float32)
        ndvi = vc.calcular_ndvi(data)
        assert -1.0 <= ndvi.min() and ndvi.max() <= 1.0


# ─────────────────────────────────────────────────────────────
# Testes: detectar_mudanca
# ─────────────────────────────────────────────────────────────
class TestDetectarMudanca:
    """Valida a detecção de mudança por diferença de NDVI."""

    def test_sem_mudanca_mascara_vazia(self, imagem_floresta):
        """NDVI idêntico antes e depois → nenhum pixel de desmatamento."""
        diff, mascara = vc.detectar_mudanca(imagem_floresta, imagem_floresta)
        assert mascara.sum() == 0

    def test_desmatamento_total_mascara_cheia(self, imagem_floresta, imagem_desmatada):
        """NDVI caiu em toda a imagem → toda a área é desmatamento."""
        diff, mascara = vc.detectar_mudanca(imagem_floresta, imagem_desmatada)
        total = mascara.shape[0] * mascara.shape[1]
        assert mascara.sum() == total

    def test_mancha_detectada(self, imagem_floresta, imagem_com_mancha):
        """Mancha central no 'depois' deve ser detectada."""
        diff, mascara = vc.detectar_mudanca(imagem_floresta, imagem_com_mancha)
        assert mascara.sum() > 0, "Nenhum pixel de desmatamento detectado"

    def test_diff_negativo_em_area_desmatada(self, imagem_floresta, imagem_com_mancha):
        """Diferença deve ser negativa onde houve desmatamento."""
        diff, _ = vc.detectar_mudanca(imagem_floresta, imagem_com_mancha)
        assert diff[30, 30] < 0  # Centro da mancha

    def test_diff_zero_em_area_preservada(self, imagem_floresta, imagem_com_mancha):
        """Diferença deve ser zero onde não houve mudança."""
        diff, _ = vc.detectar_mudanca(imagem_floresta, imagem_com_mancha)
        assert diff[0, 0] == pytest.approx(0.0, abs=0.01)

    def test_mascara_binaria(self, imagem_floresta, imagem_com_mancha):
        """Máscara deve conter apenas 0 e 1."""
        _, mascara = vc.detectar_mudanca(imagem_floresta, imagem_com_mancha)
        valores_unicos = set(np.unique(mascara))
        assert valores_unicos.issubset({0, 1})


# ─────────────────────────────────────────────────────────────
# Testes: gerar_imagem_sintetica
# ─────────────────────────────────────────────────────────────
class TestGerarImagemSintetica:
    """Valida o gerador de imagens sintéticas para modo demo."""

    def test_shape_correto(self):
        antes, depois = vc.gerar_imagem_sintetica(h=64, w=64, n_manchas=3)
        assert antes.shape == (64, 64)
        assert depois.shape == (64, 64)

    def test_ndvi_antes_alto(self):
        """NDVI antes deve representar floresta densa (> 0.4)."""
        antes, _ = vc.gerar_imagem_sintetica(h=128, w=128, n_manchas=3)
        assert antes.mean() > 0.4

    def test_ndvi_depois_menor_que_antes(self):
        """NDVI depois (com manchas) deve ser menor que NDVI antes."""
        antes, depois = vc.gerar_imagem_sintetica(h=128, w=128, n_manchas=5)
        assert depois.mean() < antes.mean()

    def test_manchas_detectaveis(self):
        """As manchas sintéticas devem ser detectáveis pelo algoritmo."""
        antes, depois = vc.gerar_imagem_sintetica(h=256, w=256, n_manchas=5)
        _, mascara = vc.detectar_mudanca(antes, depois)
        assert mascara.sum() > 0, "Manchas sintéticas não foram detectadas"

    def test_ndvi_no_intervalo_valido(self):
        """Imagens sintéticas devem ter NDVI em [-1, 1]."""
        antes, depois = vc.gerar_imagem_sintetica(h=64, w=64, n_manchas=2)
        assert antes.min() >= -1.0 and antes.max() <= 1.0
        assert depois.min() >= -1.0 and depois.max() <= 1.0

    def test_sem_manchas_igual_ao_antes(self):
        """Sem manchas, imagem depois deve ser quase igual ao antes."""
        antes, depois = vc.gerar_imagem_sintetica(h=64, w=64, n_manchas=0)
        diff_media = abs(antes.mean() - depois.mean())
        assert diff_media < 0.5  # pode ter pequena variação por noise


# ─────────────────────────────────────────────────────────────
# Testes: pipeline completo
# ─────────────────────────────────────────────────────────────
class TestPipelineCompleto:
    """Testa o pipeline end-to-end com dados sintéticos."""

    def test_pipeline_retorna_resultado_valido(self, tmp_path, monkeypatch):
        """Pipeline completo deve retornar dicionário com campos esperados."""
        # Redireciona OUTPUT_DIR para tmp_path
        monkeypatch.setattr(vc, "OUTPUT_DIR", tmp_path)

        antes, depois = vc.gerar_imagem_sintetica(h=128, w=128, n_manchas=5)
        resultado = vc.pipeline(antes, depois, transform=None, visualizar=False)

        assert resultado["status"] == "OK"
        assert isinstance(resultado["n_poligonos"], int)
        assert isinstance(resultado["area_total_ha"], float)
        assert resultado["area_total_ha"] >= 0
        assert "geojson_path" in resultado

    def test_pipeline_area_ha_positiva(self, tmp_path, monkeypatch):
        """Área total detectada deve ser positiva quando há manchas."""
        monkeypatch.setattr(vc, "OUTPUT_DIR", tmp_path)
        antes, depois = vc.gerar_imagem_sintetica(h=256, w=256, n_manchas=8)
        resultado = vc.pipeline(antes, depois, transform=None, visualizar=False)
        assert resultado["area_total_ha"] > 0
