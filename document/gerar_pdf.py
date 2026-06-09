#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SENTINELA - Gerador do PDF de entrega (FIAP Global Solution 2026.1)
===================================================================
Monta o documento unico de entrega (document/SENTINELA-GS-2026.pdf)
seguindo a estrutura minima exigida pelo edital:

    Capa (integrantes + RM)  ->  Introducao  ->  Desenvolvimento
    ->  Resultados Esperados  ->  Conclusoes  ->  Links

Inclui codigos em formato de TEXTO (nao screenshots), o diagrama de
arquitetura, o fluxograma da solucao e o relatorio de eficacia.

Uso:
    python document/gerar_pdf.py

Dependencias:
    pip install fpdf2
    (fontes Arial e Courier New do Windows sao embutidas para acentos)
"""
from pathlib import Path
from datetime import datetime

from fpdf import FPDF
from PIL import Image

# ----------------------------------------------------------------------
RAIZ = Path(__file__).resolve().parent.parent
ASSETS = RAIZ / "assets"
SIM_OUT = RAIZ / "simulacao" / "output"
SAIDA = RAIZ / "document" / "SENTINELA-GS-2026.pdf"

FONTS = Path("C:/Windows/Fonts")

# Cores (RGB)
VERDE = (27, 120, 55)
AZUL = (33, 102, 172)
ROXO = (106, 61, 154)
VERM = (178, 24, 43)
CINZA = (80, 88, 98)
CINZA_CLARO = (235, 238, 242)
PRETO = (20, 24, 30)
LINK = (33, 102, 172)

# Link do video (preencher apos subir no YouTube como "Nao listado")
VIDEO_URL = "https://youtu.be/BlPoCsdbtlA"
REPO_URL = "https://github.com/JonathanfrancoIA/SENTINELA-"

# Modo gravacao: True esconde os links (YouTube/repo) para gravar o video sem
# mostrar o placeholder. Voltar para False na entrega final (com o link real).
MODO_GRAVACAO = False

INTEGRANTES = [
    ("Bruno de Souza Leite", "RM567213"),
    ("Jonathan Gomes Ribeiro Franco", "RM567109"),
    ("Marina Clara Constantino Ribeiro", "RM568576"),
    ("Yasmin Kauane Silva Lima", "RM566645"),
]

# Metricas reais da simulacao (simulacao/simular_eficacia.py, semente=42)
MET = {
    "acuracia": 95.2, "precisao": 100.0, "recall": 90.5, "f1": 95.0,
    "especificidade": 100.0, "auc": 1.000,
    "vc_poligonos": 4, "vc_area": 173.1, "vc_iou": 1.00,
    "fus_audio": 60, "fus_sat": 40, "fus_conf": 3, "fus_susp": 27, "fus_red": 50,
    "testes": 65,
}


# ======================================================================
class PDF(FPDF):
    def header(self):
        if self.page_no() == 1:
            return
        self.set_font("Arial", "", 8)
        self.set_text_color(*CINZA)
        self.cell(0, 6, "SENTINELA - O olho e o ouvido da floresta", align="L")
        self.cell(0, 6, "FIAP Global Solution 2026.1", align="R")
        self.ln(7)
        self.set_draw_color(*CINZA_CLARO)
        self.line(self.l_margin, self.get_y(), self.w - self.r_margin, self.get_y())
        self.ln(3)

    def footer(self):
        if self.page_no() == 1:
            return
        self.set_y(-12)
        self.set_font("Arial", "", 8)
        self.set_text_color(*CINZA)
        self.cell(0, 8, f"Pagina {self.page_no()}", align="C")


def setup_fonts(pdf):
    pdf.add_font("Arial", "", str(FONTS / "arial.ttf"))
    pdf.add_font("Arial", "B", str(FONTS / "arialbd.ttf"))
    pdf.add_font("Arial", "I", str(FONTS / "ariali.ttf"))
    pdf.add_font("Mono", "", str(FONTS / "cour.ttf"))
    pdf.add_font("Mono", "B", str(FONTS / "courbd.ttf"))


# --------------------------- helpers ----------------------------------
def h1(pdf, num, txt, cor=PRETO):
    pdf.ln(2)
    pdf.set_font("Arial", "B", 16)
    pdf.set_text_color(*cor)
    pdf.multi_cell(0, 8, f"{num}  {txt}")
    pdf.set_draw_color(*cor)
    y = pdf.get_y() + 1
    pdf.line(pdf.l_margin, y, pdf.w - pdf.r_margin, y)
    pdf.ln(4)


def h2(pdf, txt, cor=AZUL):
    pdf.ln(1)
    pdf.set_font("Arial", "B", 12.5)
    pdf.set_text_color(*cor)
    pdf.multi_cell(0, 7, txt)
    pdf.ln(1)


def paragrafo(pdf, txt):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Arial", "", 10.5)
    pdf.set_text_color(*PRETO)
    pdf.multi_cell(0, 5.6, txt, markdown=True)
    pdf.ln(2)


def bullet(pdf, txt):
    pdf.set_x(pdf.l_margin)
    pdf.set_font("Arial", "", 10.5)
    pdf.set_text_color(*PRETO)
    x = pdf.get_x()
    pdf.set_x(x + 4)
    pdf.cell(4, 5.6, chr(0x2022))  # bullet
    pdf.multi_cell(0, 5.6, txt, markdown=True)
    pdf.set_x(x)
    pdf.ln(0.5)


def codigo(pdf, titulo, linhas):
    """Bloco de codigo em texto (Courier) com fundo cinza."""
    if titulo:
        pdf.set_font("Arial", "I", 9.5)
        pdf.set_text_color(*CINZA)
        pdf.multi_cell(0, 5, titulo)
        pdf.ln(0.5)
    pdf.set_font("Mono", "", 8.2)
    lh = 4.0
    altura = lh * len(linhas) + 3
    # quebra de pagina se nao couber
    if pdf.get_y() + altura > pdf.h - pdf.b_margin - 12:
        pdf.add_page()
    x0, y0 = pdf.l_margin, pdf.get_y()
    largura = pdf.w - pdf.l_margin - pdf.r_margin
    pdf.set_fill_color(*CINZA_CLARO)
    pdf.rect(x0, y0, largura, altura, style="F")
    pdf.set_draw_color(200, 205, 210)
    pdf.rect(x0, y0, largura, altura, style="D")
    pdf.set_xy(x0 + 2, y0 + 1.5)
    pdf.set_text_color(30, 36, 50)
    for ln in linhas:
        pdf.set_x(x0 + 2)
        pdf.cell(largura - 4, lh, ln)
        pdf.ln(lh)
    pdf.ln(3)


def imagem(pdf, path, w=None, legenda=None):
    if not Path(path).exists():
        paragrafo(pdf, f"*[imagem nao encontrada: {Path(path).name}]*")
        return
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    w = w or usable
    iw, ih = Image.open(path).size
    h = w * ih / iw
    if pdf.get_y() + h > pdf.h - pdf.b_margin - 14:
        pdf.add_page()
    x = (pdf.w - w) / 2
    y = pdf.get_y()
    pdf.image(str(path), x=x, y=y, w=w, h=h)
    pdf.set_xy(pdf.l_margin, y + h + 2)
    if legenda:
        pdf.set_font("Arial", "I", 8.5)
        pdf.set_text_color(*CINZA)
        pdf.multi_cell(0, 4.5, legenda, align="C")
    pdf.ln(3)


# ======================================================================
def capa(pdf):
    pdf.add_page()
    pdf.ln(18)
    pdf.set_font("Arial", "B", 9)
    pdf.set_text_color(*CINZA)
    pdf.cell(0, 6, "FIAP - Faculdade de Informatica e Administracao Paulista", align="C")
    pdf.ln(8)
    pdf.cell(0, 6, "Tecnologo em Inteligencia Artificial  |  Global Solution 2026.1 - Economia Espacial", align="C")
    pdf.ln(16)

    pdf.set_font("Arial", "B", 40)
    pdf.set_text_color(*VERDE)
    pdf.cell(0, 16, "SENTINELA", align="C")
    pdf.ln(16)
    pdf.set_font("Arial", "", 15)
    pdf.set_text_color(*PRETO)
    pdf.cell(0, 8, "O olho e o ouvido da floresta", align="C")
    pdf.ln(10)
    pdf.set_font("Arial", "I", 11)
    pdf.set_text_color(*CINZA)
    pdf.multi_cell(0, 6,
                   "Deteccao de desmatamento ilegal na Amazonia pela fusao de IA de borda "
                   "(audio no ESP32) com visao computacional sobre imagens de satelite.",
                   align="C")
    pdf.ln(12)

    # Integrantes
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(*AZUL)
    pdf.cell(0, 7, "Integrantes", align="C")
    pdf.ln(9)
    pdf.set_font("Arial", "", 11.5)
    pdf.set_text_color(*PRETO)
    for nome, rm in INTEGRANTES:
        pdf.cell(0, 6.5, f"{nome}  -  {rm}", align="C")
        pdf.ln(6.5)
    pdf.ln(8)

    # QUERO CONCORRER
    pdf.set_font("Arial", "B", 15)
    pdf.set_text_color(*VERM)
    pdf.cell(0, 9, "QUERO CONCORRER", align="C")
    pdf.ln(12)

    # Links (ocultos em MODO_GRAVACAO)
    if not MODO_GRAVACAO:
        pdf.set_font("Arial", "", 10)
        pdf.set_text_color(*CINZA)
        pdf.cell(0, 6, "Repositorio:", align="C")
        pdf.ln(5)
        pdf.set_text_color(*LINK)
        pdf.cell(0, 6, REPO_URL, align="C", link=REPO_URL)
        pdf.ln(7)
        pdf.set_text_color(*CINZA)
        pdf.cell(0, 6, "Video demonstrativo (YouTube - nao listado):", align="C")
        pdf.ln(5)
        pdf.set_text_color(*LINK)
        pdf.cell(0, 6, VIDEO_URL, align="C", link=VIDEO_URL)
        pdf.ln(10)
    # (data "Sao Paulo, ..." removida da capa)


def secao_introducao(pdf):
    pdf.add_page()
    h1(pdf, "1.", "Introducao", VERDE)

    h2(pdf, "1.1  Contexto e tema")
    paragrafo(pdf,
        "A economia espacial deixou de ser apenas cientifica: satelites monitoram o clima, "
        "apoiam o agronegocio e ajudam na prevencao de desastres, gerando enormes volumes de "
        "dados. O **SENTINELA** aplica esses dados orbitais a um problema critico e brasileiro: "
        "o **desmatamento ilegal na Amazonia**, a maior floresta tropical do planeta.")

    h2(pdf, "1.2  Problema")
    paragrafo(pdf,
        "Sistemas baseados apenas em satelite (DETER/PRODES do INPE) so enxergam o dano "
        "**depois** que a floresta ja virou cicatriz visivel - e ainda sofrem com nuvens e "
        "revisita de poucos dias. Resultado: o crime e detectado tarde, quando a area ja foi "
        "derrubada. Falta um sinal **precoce**, captado no momento da invasao.")

    h2(pdf, "1.3  Hipotese e solucao")
    paragrafo(pdf,
        "O desmatamento primeiro **faz barulho** (motosserra, trator, caminhao) e so depois "
        "**vira cicatriz no satelite**. O SENTINELA combina duas formas de percepcao que se "
        "confirmam:")
    bullet(pdf, "**O ouvido (camada de solo):** um ESP32 com microfone I2S INMP441 roda um "
                "classificador de audio (CNN TFLite INT8) na propria borda e reconhece o som de "
                "motosserra, publicando o alerta via MQTT.")
    bullet(pdf, "**O olho (camada espacial):** visao computacional sobre imagens Sentinel-2 "
                "(Copernicus) e alertas DETER/INPE detecta a perda de vegetacao por change "
                "detection de NDVI.")
    bullet(pdf, "**A fusao (o diferencial):** um motor na nuvem (AWS Lambda) cruza os dois "
                "sinais no espaco e no tempo e so emite um alerta de alta confianca quando ambos "
                "concordam - reduzindo falsos positivos e gerando alertas acionaveis.")

    h2(pdf, "1.4  Objetivos")
    bullet(pdf, "Detectar invasoes **mais cedo** que o satelite sozinho, ouvindo o solo.")
    bullet(pdf, "**Reduzir falsos positivos** pela corroboracao audio + imagem.")
    bullet(pdf, "Integrar, numa unica POC, IoT/Edge AI, visao computacional, engenharia de "
                "dados, computacao em nuvem serverless e um dashboard em tempo real.")
    bullet(pdf, "Gerar **impacto na Terra**: deteccao precoce = menos area derrubada, menos "
                "carbono emitido e maior chance de flagrar o crime em andamento.")


def secao_desenvolvimento(pdf):
    pdf.add_page()
    h1(pdf, "2.", "Desenvolvimento", VERDE)

    # 2.1
    h2(pdf, "2.1  Visao geral da arquitetura")
    paragrafo(pdf,
        "A solucao tem quatro camadas: (a) **espacial** - satelite/INPE; (b) **solo** - sensor "
        "ESP32; (c) **modelos de IA** - audio (CNN) e imagem (NDVI); (d) **nuvem e persistencia** "
        "- Lambda de fusao, banco e dashboard. O diagrama abaixo resume o fluxo ponta a ponta.")
    imagem(pdf, ASSETS / "diagrama_arquitetura.png", w=170,
           legenda="Figura 1 - Diagrama de arquitetura do SENTINELA.")

    paragrafo(pdf,
        "**Tecnologias integradas:** visao computacional (NDVI, OpenCV, rasterio); audio/Edge AI "
        "(CNN, TensorFlow Lite INT8, TFLite Micro); dados espaciais (Sentinel-2 B4/B8, "
        "INPE/DETER via WFS); IoT (ESP32-WROOM, INMP441, MQTT); nuvem serverless (AWS Lambda, "
        "API Gateway, S3, SNS); bancos SQL/NoSQL (SQLite/RDS); pipeline de dados; e dashboard "
        "(Streamlit + Folium + Plotly).")

    # 2.2 camadas
    h2(pdf, "2.2  Camadas da solucao")
    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*AZUL)
    pdf.multi_cell(0, 6, "(a) Camada espacial - O olho")
    paragrafo(pdf,
        "Consome alertas oficiais do **DETER/INPE** (Amazonia Legal) em tempo de execucao, via "
        "WFS publico do TerraBrasilis (GeoServer), em GeoJSON e sem credenciais. As cenas "
        "**Sentinel-2** (bandas B4 Red e B8 NIR) sao obtidas do Copernicus Data Space para o "
        "calculo de NDVI. Ha fallback automatico para dados simulados quando a rede falha.")

    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*AZUL)
    pdf.multi_cell(0, 6, "(b) Camada de solo - O ouvido")
    paragrafo(pdf,
        "Estacao **ESP32 + INMP441** captura janelas de audio de 2 s, extrai features no proprio "
        "microcontrolador (janela de Hann + FFT) e roda a CNN quantizada (TFLite Micro). Quando "
        "P(motosserra) >= 0.70, publica um alerta MQTT com probabilidade, coordenadas e "
        "timestamp. Em ociosidade entra em **deep sleep** para poupar bateria.")

    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*AZUL)
    pdf.multi_cell(0, 6, "(c) Modelos de IA - audio e imagem")
    paragrafo(pdf,
        "**Audio:** CNN treinada com o dataset publico **ESC-50** (classe `chainsaw` como "
        "AMEACA), exportada em **TFLite INT8** (~80 KB) para caber no ESP32. **Imagem:** indice "
        "**NDVI = (NIR - Red) / (NIR + Red)**; a queda de NDVI entre duas datas (change detection) "
        "indica perda de vegetacao, segmentada em poligonos com OpenCV.")

    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*AZUL)
    pdf.multi_cell(0, 6, "(d) Camada de nuvem e persistencia")
    paragrafo(pdf,
        "O **motor de fusao** roda em **AWS Lambda** (com API Gateway), recebe os eventos de "
        "audio (MQTT) e os alertas DETER, associa-os por **Haversine (< 10 km)** e **janela "
        "temporal (< 7 dias)** e calcula a confianca final. Os dados ficam em **SQLite** (dev) / "
        "**RDS** (producao): tabelas `alertas_deter`, `eventos_audio`, `alertas_fusao` e "
        "`sensores`. Alertas confirmados disparam notificacao (SNS / e-mail / Telegram).")

    # 2.3 fluxograma
    pdf.add_page()
    h2(pdf, "2.3  Fluxograma da solucao")
    paragrafo(pdf,
        "O fluxograma detalha o caminho decisional: captura em duas camadas, inferencia local, "
        "fusao geotemporal na nuvem e a decisao por nivel de confianca (CONFIRMADO, SUSPEITO ou "
        "descartado).")
    imagem(pdf, ASSETS / "fluxograma.png", w=120,
           legenda="Figura 2 - Fluxograma decisional do SENTINELA.")

    # 2.4 codigos
    pdf.add_page()
    h2(pdf, "2.4  Codigos principais")

    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*ROXO)
    pdf.multi_cell(0, 6, "2.4.1  Motor de fusao - confianca (src/cloud_aws/handler.py)")
    paragrafo(pdf,
        "Coracao do sistema: pondera audio e visao (0.55 / 0.45) e penaliza distancia e tempo. "
        "Validado por testes automatizados.")
    codigo(pdf, None, [
        "PESO_AUDIO, PESO_VISUAL = 0.55, 0.45",
        "RAIO_FUSAO_KM, JANELA_DIAS = 10.0, 7",
        "",
        "def calcular_confianca_fusao(prob_audio, conf_visual,",
        "                             distancia_km, delta_dias):",
        "    conf_base  = PESO_AUDIO * prob_audio + PESO_VISUAL * conf_visual",
        "    fator_dist = max(0.0, 1.0 - distancia_km / RAIO_FUSAO_KM)",
        "    fator_tempo = max(0.0, 1.0 - delta_dias / JANELA_DIAS) ** 0.5",
        "    return round(conf_base * fator_dist * fator_tempo, 4)",
    ])

    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*ROXO)
    pdf.multi_cell(0, 6, "2.4.2  Distancia geoespacial - Haversine")
    codigo(pdf, None, [
        "def haversine_km(lat1, lon1, lat2, lon2):",
        "    R = 6371.0",
        "    dlat = radians(lat2 - lat1); dlon = radians(lon2 - lon1)",
        "    a = sin(dlat/2)**2 + cos(radians(lat1)) * \\",
        "        cos(radians(lat2)) * sin(dlon/2)**2",
        "    return R * 2 * atan2(sqrt(a), sqrt(1 - a))",
    ])

    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*ROXO)
    pdf.multi_cell(0, 6, "2.4.3  Visao computacional - NDVI (src/visao_computacional/detectar_desmatamento.py)")
    codigo(pdf, None, [
        "def calcular_ndvi(data, banda_red=0, banda_nir=1):",
        "    red = data[banda_red].astype(float)",
        "    nir = data[banda_nir].astype(float)",
        "    if red.max() > 1.0:          # Sentinel-2 L2A: 0..10000",
        "        red, nir = red/10000.0, nir/10000.0",
        "    denom = nir + red",
        "    ndvi = np.where(denom > 1e-4, (nir - red)/denom, 0.0)",
        "    return np.clip(ndvi, -1.0, 1.0)",
        "",
        "def detectar_mudanca(ndvi_antes, ndvi_depois):",
        "    diff = ndvi_depois - ndvi_antes     # negativo = perda",
        "    mascara = (diff < -0.15).astype('uint8')",
        "    return diff, mascara",
    ])

    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*ROXO)
    pdf.multi_cell(0, 6, "2.4.4  Modelo de audio - CNN (src/audio_edge/treinar_audio.py)")
    codigo(pdf, None, [
        "modelo = models.Sequential([",
        "    layers.Input(shape=input_shape),",
        "    layers.Conv2D(16, 3, activation='relu', padding='same'),",
        "    layers.BatchNormalization(), layers.MaxPooling2D(), layers.Dropout(.25),",
        "    layers.Conv2D(32, 3, activation='relu', padding='same'),",
        "    layers.BatchNormalization(), layers.MaxPooling2D(), layers.Dropout(.25),",
        "    layers.Conv2D(64, 3, activation='relu', padding='same'),",
        "    layers.GlobalAveragePooling2D(), layers.Dropout(.5),",
        "    layers.Dense(64, activation='relu'),",
        "    layers.Dense(1, activation='sigmoid'),   # P(motosserra)",
        "])",
        "# Export INT8 -> TFLite Micro (ESP32):",
        "converter.optimizations = [tf.lite.Optimize.DEFAULT]",
        "converter.target_spec.supported_ops = [TFLITE_BUILTINS_INT8]",
    ])

    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*ROXO)
    pdf.multi_cell(0, 6, "2.4.5  Pipeline DETER real - WFS TerraBrasilis (src/pipeline_dados/ingest_deter.py)")
    codigo(pdf, None, [
        "DETER_WFS_URL = 'https://terrabrasilis.dpi.inpe.br/geoserver/deter-amz/wfs'",
        "params = {",
        "    'service': 'WFS', 'version': '2.0.0', 'request': 'GetFeature',",
        "    'typeName': 'deter-amz:deter_public',",
        "    'outputFormat': 'application/json', 'srsName': 'EPSG:4326',",
        "    'count': '500', 'CQL_FILTER': f\"view_date>='{data_corte}'\",",
        "}",
        "r = requests.get(DETER_WFS_URL, params=params, timeout=60)",
        "feicoes = r.json().get('features', [])   # alertas reais do INPE",
    ])

    pdf.set_font("Arial", "B", 11)
    pdf.set_text_color(*ROXO)
    pdf.multi_cell(0, 6, "2.4.6  Firmware ESP32 - inferencia e alerta MQTT (src/audio_edge/sentinela_esp32)")
    codigo(pdf, None, [
        "float prob = inferir(audio_buffer);          // CNN TFLite Micro",
        "if (prob >= THRESHOLD_AMEACA) {              // 0.70",
        "    const char* tipo = (prob >= 0.85) ?",
        "        \"MOTOSSERRA_CONFIRMADO\" : \"MOTOR_SUSPEITO\";",
        "    publicar_alerta(prob, tipo);             // publica JSON via MQTT",
        "} else if (amostras_sem_ameaca >= 20) {",
        "    esp_deep_sleep_start();                   // economiza bateria",
        "}",
    ])

    # 2.5 dashboard
    pdf.add_page()
    h2(pdf, "2.5  Dashboard em tempo real")
    paragrafo(pdf,
        "O painel (Streamlit + Folium + Plotly) unifica as pontas: mapa interativo da Amazonia "
        "Legal com alertas DETER, sensores ESP32 e fusoes; graficos de serie temporal; status "
        "dos sensores (bateria, heartbeat); e o gauge de confianca das fusoes. Ele le o banco "
        "SQLite e mescla, ao vivo, os eventos REAIS publicados pelo ESP32 via MQTT.")
    bullet(pdf, "Aba **Mapa de Alertas** - camadas DETER / sensores / fusoes + heatmap.")
    bullet(pdf, "Aba **Analise de Dados** - alertas por semana e area por estado.")
    bullet(pdf, "Aba **Sensores IoT** - inventario e saude da rede de ESP32.")
    bullet(pdf, "Aba **Motor de Fusao** - confianca media e fila de alertas.")
    bullet(pdf, "Aba **Visao Computacional** - poligonos NDVI detectados e notificacao.")
    paragrafo(pdf,
        "*Execucao:* `streamlit run src/dashboard/app.py` (abre em http://localhost:8501). "
        "Os prints do painel em funcionamento estao no video e no repositorio.")


def secao_resultados(pdf):
    pdf.add_page()
    h1(pdf, "3.", "Resultados Esperados", VERDE)

    paragrafo(pdf,
        "Por ser uma **POC**, a eficacia foi medida com uma simulacao reprodutivel "
        "(`simulacao/simular_eficacia.py`, semente fixa = 42), cujas distribuicoes foram "
        "calibradas a partir do comportamento esperado de cada modelo. O relatorio abaixo "
        "(gerado automaticamente) consolida as tres camadas.")

    h2(pdf, "3.1  Metricas das camadas de IA")
    # tabela simples
    linhas = [
        ("Ouvido - Acuracia (audio)", f"{MET['acuracia']:.1f}%"),
        ("Ouvido - Precisao", f"{MET['precisao']:.1f}%"),
        ("Ouvido - Recall", f"{MET['recall']:.1f}%"),
        ("Ouvido - F1-score", f"{MET['f1']:.1f}%"),
        ("Ouvido - Especificidade", f"{MET['especificidade']:.1f}%"),
        ("Ouvido - AUC (ROC)", f"{MET['auc']:.3f}"),
        ("Olho - Poligonos detectados", f"{MET['vc_poligonos']}"),
        ("Olho - Area desmatada detectada", f"{MET['vc_area']:.1f} ha"),
        ("Olho - IoU espacial (deteccao x gabarito)", f"{MET['vc_iou']:.2f}"),
        ("Fusao - Reducao de falsos positivos", f"{MET['fus_red']}%"),
        ("Testes automatizados (pytest)", f"{MET['testes']} passando"),
    ]
    pdf.set_font("Arial", "", 10)
    w1 = 120
    w2 = pdf.w - pdf.l_margin - pdf.r_margin - w1
    for i, (k, v) in enumerate(linhas):
        pdf.set_fill_color(*(CINZA_CLARO if i % 2 == 0 else (248, 250, 252)))
        pdf.set_text_color(*PRETO)
        pdf.cell(w1, 7, "  " + k, border=0, fill=True)
        pdf.set_font("Arial", "B", 10)
        pdf.cell(w2, 7, v, border=0, fill=True, align="R")
        pdf.set_font("Arial", "", 10)
        pdf.ln(7)
    pdf.ln(4)

    paragrafo(pdf,
        "**Leitura:** o classificador de audio atinge alta acuracia e AUC, com **especificidade "
        "de 100%** (nenhum falso positivo no conjunto de teste) - exatamente o requisito de quem "
        "nao pode disparar brigada a toa. A visao computacional recupera as cicatrizes plantadas "
        "com **IoU = 1.0**. E a **fusao reduz pela metade** o numero de alertas em relacao ao "
        "audio sozinho, confirmando apenas os eventos corroborados pelo satelite.")

    h2(pdf, "3.2  Relatorio visual de eficacia")
    imagem(pdf, SIM_OUT / "relatorio_eficacia.png", w=180,
           legenda="Figura 3 - Relatorio de eficacia: matriz de confusao e ROC do audio, "
                   "deteccao NDVI, area por severidade e reducao de falsos positivos pela fusao.")

    h2(pdf, "3.3  O que esta implementado x simulado (transparencia)")
    paragrafo(pdf, "Honestidade tecnica - estado real de cada parte:")
    bullet(pdf, "**100% funcional:** pipeline DETER/INPE REAL (WFS), motor de fusao, visao "
                "computacional (NDVI), dashboard, simulacao de eficacia e a suite de testes.")
    bullet(pdf, "**Pronto, falta credencial:** download Sentinel-2 real (basta o Client "
                "ID/Secret do Copernicus no .env; sem isso, roda em modo demo com NDVI sintetico).")
    bullet(pdf, "**Simulado na POC:** a inferencia da CNN no ESP32 fisico. O firmware esta "
                "completo (I2S, features, MQTT, deep sleep) e roda hoje com um proxy de energia "
                "(RMS); a troca para o modelo `.tflite` real e a descomentar um bloco ja presente "
                "no codigo, apos treinar com o hardware em maos.")


def secao_conclusao(pdf):
    pdf.add_page()
    h1(pdf, "4.", "Conclusoes", VERDE)
    paragrafo(pdf,
        "O SENTINELA mostra, de ponta a ponta, como dados da **economia espacial** viram **acao "
        "no chao**. O diferencial nao e um sensor isolado, mas a **fusao** de dois mundos: o "
        "satelite que ve a cicatriz e o microfone que ouve a motosserra antes dela existir. Essa "
        "corroboracao geotemporal aumenta a confianca e derruba os falsos positivos - o ponto "
        "mais sensivel de qualquer sistema de fiscalizacao ambiental.")
    paragrafo(pdf,
        "Do ponto de vista academico, a POC integra de forma coerente as disciplinas do curso: "
        "**IoT e Edge AI** (ESP32, INMP441, TFLite Micro), **visao computacional** (NDVI, OpenCV), "
        "**machine learning** (CNN de audio), **engenharia de dados** (ingestao WFS, SQLite/RDS), "
        "**computacao em nuvem serverless** (AWS Lambda, API Gateway, SNS) e **analise de dados** "
        "(dashboard interativo).")
    paragrafo(pdf,
        "**Impacto na Terra:** detectar a invasao mais cedo significa menos floresta derrubada, "
        "menos carbono emitido e maior chance de flagrar o crime em andamento - alinhado a "
        "iniciativas reais como a Rainforest Connection e o proprio INPE/DETER.")
    paragrafo(pdf,
        "**Proximos passos:** treinar a CNN com o ESC-50 acrescido de ruidos de floresta e "
        "embarcar no ESP32 fisico; conectar o Sentinel-2 real (credencial Copernicus); migrar a "
        "persistencia para RDS/Timestream; e empacotar a Lambda com SAM para deploy automatizado. "
        "A arquitetura ja foi desenhada para essa evolucao.")

    h2(pdf, "5.  Links e execucao")
    if MODO_GRAVACAO:
        bullet(pdf, "**Repositorio e video:** inseridos na versao final da entrega.")
    else:
        bullet(pdf, f"**Repositorio:** {REPO_URL}")
        bullet(pdf, f"**Video demonstrativo (YouTube, nao listado):** {VIDEO_URL}")
    paragrafo(pdf, "Execucao rapida (resumo - detalhes no README):")
    codigo(pdf, None, [
        "pip install -r requirements.txt",
        "python src/pipeline_dados/ingest_deter.py --fonte real   # ingestao DETER",
        "streamlit run src/dashboard/app.py                       # dashboard",
        "python simulacao/simular_eficacia.py                     # metricas",
        "pytest -q                                                # 65 testes",
    ])
    pdf.ln(2)
    pdf.set_font("Arial", "I", 9)
    pdf.set_text_color(*CINZA)
    pdf.multi_cell(0, 5,
        "Documento gerado automaticamente por document/gerar_pdf.py. "
        "Todos os trechos de codigo estao em formato de texto, conforme o edital.")


def main():
    pdf = PDF(orientation="P", unit="mm", format="A4")
    pdf.set_margins(15, 15, 15)
    pdf.set_auto_page_break(auto=True, margin=15)
    setup_fonts(pdf)
    pdf.set_title("SENTINELA - FIAP Global Solution 2026.1")
    pdf.set_author(", ".join(n for n, _ in INTEGRANTES))

    capa(pdf)
    secao_introducao(pdf)
    secao_desenvolvimento(pdf)
    secao_resultados(pdf)
    secao_conclusao(pdf)

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    pdf.output(str(SAIDA))
    print("PDF gerado em:", SAIDA)
    print("Paginas:", pdf.page_no())


if __name__ == "__main__":
    main()
