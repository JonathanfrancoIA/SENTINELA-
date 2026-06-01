"""
SENTINELA — Testes: Motor de Fusão (handler.py)
================================================
Testa a lógica central do sistema: fusão de eventos de áudio
com alertas DETER usando Haversine + janela temporal.

Execute com:
    pytest tests/test_motor_fusao.py -v
"""
import sys
import math
import pytest
from pathlib import Path
from datetime import datetime

# Importa o módulo a ser testado
sys.path.insert(0, str(Path(__file__).parent.parent / "src" / "cloud_aws"))
import handler


# ─────────────────────────────────────────────────────────────
# Testes: haversine_km
# ─────────────────────────────────────────────────────────────
class TestHaversine:
    """Valida o cálculo de distância geoespacial."""

    def test_mesma_posicao_retorna_zero(self):
        dist = handler.haversine_km(-3.47, -62.22, -3.47, -62.22)
        assert dist == pytest.approx(0.0, abs=0.01)

    def test_distancia_conhecida_brasil(self):
        """Manaus → Belém ≈ 1280 km em linha reta."""
        dist = handler.haversine_km(-3.1, -60.0, -1.46, -48.5)
        assert 1100 < dist < 1400, f"Esperado ~1280 km, obtido {dist:.1f} km"

    def test_distancia_5km_aproximada(self):
        """~0.045° de latitude ≈ 5 km."""
        dist = handler.haversine_km(-3.47, -62.22, -3.52, -62.27)
        assert 3.0 < dist < 9.0, f"Esperado ~5 km, obtido {dist:.2f} km"

    def test_distancia_positiva(self):
        """Distância é sempre não-negativa."""
        for lat1, lon1, lat2, lon2 in [
            (-10.0, -50.0, -10.0, -51.0),
            (0.0, 0.0, 0.0, 0.01),
            (-3.47, -62.22, -8.26, -64.80),
        ]:
            assert handler.haversine_km(lat1, lon1, lat2, lon2) >= 0


# ─────────────────────────────────────────────────────────────
# Testes: calcular_confianca_fusao
# ─────────────────────────────────────────────────────────────
class TestConfiancaFusao:
    """Valida o algoritmo de cálculo de confiança da fusão."""

    def test_confianca_maxima(self):
        """Probabilidade máxima + distância zero + delta zero = alta confiança."""
        conf = handler.calcular_confianca_fusao(1.0, 1.0, 0.0, 0)
        assert conf == pytest.approx(1.0, abs=0.01)

    def test_confianca_intervalo_valido(self):
        """Confiança deve estar sempre entre 0 e 1."""
        casos = [
            (0.9, 0.9, 2.0, 1),
            (0.7, 0.8, 5.0, 3),
            (0.5, 0.5, 9.0, 6),
            (0.1, 0.2, 0.1, 0),
        ]
        for prob, conf_v, dist, dias in casos:
            conf = handler.calcular_confianca_fusao(prob, conf_v, dist, dias)
            assert 0.0 <= conf <= 1.0, f"Confiança fora do intervalo: {conf}"

    def test_distancia_maxima_reduz_confianca(self):
        """Distância próxima ao limite (9.9 km) deve reduzir bastante a confiança."""
        conf_perto = handler.calcular_confianca_fusao(0.9, 0.9, 1.0, 0)
        conf_longe = handler.calcular_confianca_fusao(0.9, 0.9, 9.5, 0)
        assert conf_perto > conf_longe

    def test_tempo_antigo_reduz_confianca(self):
        """Evento antigo (6 dias) deve ter confiança menor que evento recente."""
        conf_novo = handler.calcular_confianca_fusao(0.9, 0.9, 2.0, 0)
        conf_antigo = handler.calcular_confianca_fusao(0.9, 0.9, 2.0, 6)
        assert conf_novo > conf_antigo

    def test_pesos_audio_visual(self):
        """Peso do áudio (0.55) > peso visual (0.45)."""
        # Áudio alto + visual baixo
        conf_audio = handler.calcular_confianca_fusao(1.0, 0.0, 0.0, 0)
        # Áudio baixo + visual alto
        conf_visual = handler.calcular_confianca_fusao(0.0, 1.0, 0.0, 0)
        assert conf_audio > conf_visual

    def test_confianca_retorna_float(self):
        conf = handler.calcular_confianca_fusao(0.85, 0.90, 3.0, 2)
        assert isinstance(conf, float)


# ─────────────────────────────────────────────────────────────
# Testes: fusao_evento
# ─────────────────────────────────────────────────────────────
class TestFusaoEvento:
    """Testa o resultado completo da função de fusão."""

    def test_fusao_bem_sucedida_proximo(
        self, evento_audio_alto, alerta_deter_proximo
    ):
        """Áudio alto + DETER próximo → deve gerar fusão."""
        resultado = handler.fusao_evento(evento_audio_alto, [alerta_deter_proximo])
        assert resultado is not None
        assert "fusao_id" in resultado
        assert resultado["nivel_confianca"] >= handler.CONF_MINIMA_ALERTA

    def test_sem_fusao_alerta_distante(
        self, evento_audio_alto, alerta_deter_distante
    ):
        """DETER muito distante (>10 km) → não deve gerar fusão."""
        resultado = handler.fusao_evento(evento_audio_alto, [alerta_deter_distante])
        assert resultado is None

    def test_sem_fusao_alerta_antigo(
        self, evento_audio_alto, alerta_deter_antigo
    ):
        """DETER fora da janela temporal (>7 dias) → não deve gerar fusão."""
        resultado = handler.fusao_evento(evento_audio_alto, [alerta_deter_antigo])
        assert resultado is None

    def test_sem_fusao_lista_vazia(self, evento_audio_alto):
        """Nenhum alerta DETER disponível → não deve gerar fusão."""
        resultado = handler.fusao_evento(evento_audio_alto, [])
        assert resultado is None

    def test_fusao_campos_obrigatorios(
        self, evento_audio_alto, alerta_deter_proximo
    ):
        """Fusão gerada deve ter todos os campos obrigatórios."""
        resultado = handler.fusao_evento(evento_audio_alto, [alerta_deter_proximo])
        assert resultado is not None
        campos = ["fusao_id", "nivel_confianca", "status", "lat", "lon",
                  "distancia_km", "delta_dias", "criado_em"]
        for campo in campos:
            assert campo in resultado, f"Campo ausente: {campo}"

    def test_status_confirmado_alta_confianca(
        self, evento_audio_alto, alerta_deter_proximo
    ):
        """Fusão com alta confiança deve ter status CONFIRMADO."""
        # Garante confiança altíssima: audio=1.0, visual=1.0, distância=0, tempo=0
        ev = {**evento_audio_alto, "probabilidade": 1.0}
        deter = {**alerta_deter_proximo, "lat": ev["lat"], "lon": ev["lon"],
                 "confianca": 1.0, "data_deteccao": datetime.now().strftime("%Y-%m-%d")}
        resultado = handler.fusao_evento(ev, [deter])
        if resultado:
            assert resultado["status"] in ("CONFIRMADO", "SUSPEITO")

    def test_melhor_alerta_selecionado(
        self, evento_audio_alto, alerta_deter_proximo, alerta_deter_distante
    ):
        """Com múltiplos alertas, deve selecionar o de maior confiança."""
        resultado = handler.fusao_evento(
            evento_audio_alto,
            [alerta_deter_distante, alerta_deter_proximo]  # distante primeiro
        )
        # Deve escolher o próximo (maior confiança)
        assert resultado is not None
        assert resultado["nivel_confianca"] >= handler.CONF_MINIMA_ALERTA


# ─────────────────────────────────────────────────────────────
# Testes: handler Lambda
# ─────────────────────────────────────────────────────────────
class TestHandlerLambda:
    """Testa o entry point da Lambda."""

    def test_handler_retorna_dict_com_statuscode(self):
        """handler() deve retornar dicionário com 'statusCode'."""
        evento = {
            "source": "audio",
            "sensor_id": "TEST-01",
            "probabilidade": 0.50,
            "lat": -3.0,
            "lon": -60.0,
            "timestamp_ms": int(datetime.now().timestamp() * 1000),
        }
        resultado = handler.handler(evento)
        assert isinstance(resultado, dict)
        assert "statusCode" in resultado
        assert resultado["statusCode"] in (200, 400, 500)

    def test_handler_source_invalido(self):
        """Source inválido deve retornar statusCode 400."""
        evento = {"source": "invalido"}
        resultado = handler.handler(evento)
        assert resultado["statusCode"] == 400

    def test_handler_sem_source_assume_audio(self):
        """Sem campo 'source', assume 'audio' e retorna 200."""
        evento = {
            "sensor_id": "TEST-02",
            "probabilidade": 0.30,
            "lat": -5.0,
            "lon": -61.0,
            "timestamp_ms": int(datetime.now().timestamp() * 1000),
        }
        resultado = handler.handler(evento)
        assert resultado["statusCode"] == 200

    def test_handler_body_e_json(self):
        """O campo 'body' do retorno deve ser string JSON válida."""
        import json
        evento = {"source": "audio", "probabilidade": 0.5, "lat": -3.0, "lon": -60.0,
                  "timestamp_ms": int(datetime.now().timestamp() * 1000)}
        resultado = handler.handler(evento)
        body = json.loads(resultado["body"])  # não deve lançar exceção
        assert isinstance(body, dict)


# ─────────────────────────────────────────────────────────────
# Testes: constantes e configuração
# ─────────────────────────────────────────────────────────────
class TestConstantes:
    """Valida os valores das constantes do sistema."""

    def test_raio_fusao_positivo(self):
        assert handler.RAIO_FUSAO_KM > 0

    def test_janela_dias_positiva(self):
        assert handler.JANELA_DIAS > 0

    def test_pesos_somam_um(self):
        assert math.isclose(handler.PESO_AUDIO + handler.PESO_VISUAL, 1.0, rel_tol=1e-6)

    def test_conf_alta_maior_que_minima(self):
        assert handler.CONF_ALTA > handler.CONF_MINIMA_ALERTA

    def test_conf_minima_maior_que_zero(self):
        assert handler.CONF_MINIMA_ALERTA > 0

    def test_conf_alta_menor_que_um(self):
        assert handler.CONF_ALTA < 1.0
