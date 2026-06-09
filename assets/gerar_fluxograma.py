#!/usr/bin/env python3
"""
SENTINELA - Gerador do Fluxograma da Solucao
=============================================
Desenha o fluxograma decisional do SENTINELA (captura -> inferencia ->
fusao -> decisao -> acao) e salva em assets/fluxograma.png.

Uso:
    python assets/gerar_fluxograma.py

Dependencias:
    pip install matplotlib
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Polygon

# Paleta
C_FUNDO   = "#0d1117"
C_SOLO    = "#1b7837"   # verde - camada de solo (ouvido)
C_ESPACO  = "#2166ac"   # azul  - camada espacial (olho)
C_NUVEM   = "#6a3d9a"   # roxo  - nuvem / fusao
C_DECISAO = "#e08214"   # laranja - decisoes
C_CONF    = "#b2182b"   # vermelho - confirmado
C_SUSP    = "#d9a200"   # amarelo  - suspeito
C_ACAO    = "#00897b"   # teal  - acao final
C_TXT     = "#e6edf3"
C_BORDA   = "#30363d"


def caixa(ax, x, y, w, h, texto, cor, fonte=10, fcor=C_TXT, neg=True):
    """Retangulo arredondado com texto centralizado."""
    p = FancyBboxPatch((x - w / 2, y - h / 2), w, h,
                       boxstyle="round,pad=0.02,rounding_size=0.06",
                       linewidth=1.5, edgecolor="white", facecolor=cor,
                       alpha=0.95, mutation_aspect=1)
    ax.add_patch(p)
    ax.text(x, y, texto, ha="center", va="center", color=fcor,
            fontsize=fonte, fontweight="bold" if neg else "normal",
            zorder=5, wrap=True)


def losango(ax, x, y, w, h, texto, cor=C_DECISAO, fonte=9):
    """Diamante de decisao."""
    pts = [(x, y + h / 2), (x + w / 2, y), (x, y - h / 2), (x - w / 2, y)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=cor, edgecolor="white",
                         linewidth=1.5, alpha=0.95))
    ax.text(x, y, texto, ha="center", va="center", color="white",
            fontsize=fonte, fontweight="bold", zorder=5)


def seta(ax, x1, y1, x2, y2, texto="", cor="#9da7b3", curva=0.0):
    arr = FancyArrowPatch((x1, y1), (x2, y2),
                          connectionstyle=f"arc3,rad={curva}",
                          arrowstyle="-|>", mutation_scale=16,
                          linewidth=1.6, color=cor, zorder=1)
    ax.add_patch(arr)
    if texto:
        mx, my = (x1 + x2) / 2, (y1 + y2) / 2
        ax.text(mx + 0.15, my, texto, ha="left", va="center",
                color=cor, fontsize=8, fontstyle="italic",
                bbox=dict(boxstyle="round,pad=0.2", fc=C_FUNDO, ec="none", alpha=0.7))


def faixa(ax, y, texto, cor):
    """Rotulo lateral de camada."""
    ax.text(0.35, y, texto, ha="left", va="center", rotation=90,
            color=cor, fontsize=11, fontweight="bold", alpha=0.9)


def main():
    fig, ax = plt.subplots(figsize=(13, 16))
    fig.patch.set_facecolor(C_FUNDO)
    ax.set_facecolor(C_FUNDO)
    ax.set_xlim(0, 12)
    ax.set_ylim(0, 20)
    ax.axis("off")

    # Titulo
    ax.text(6, 19.5, "SENTINELA - Fluxograma da Solucao",
            ha="center", color="#00ff88", fontsize=18, fontweight="bold")
    ax.text(6, 19.0, "O olho e o ouvido da floresta  |  FIAP Global Solution 2026.1",
            ha="center", color="#9da7b3", fontsize=10)

    # ===================== INICIO =====================
    caixa(ax, 6, 18.1, 6.4, 0.7,
          "Ameaca na floresta: motosserra / trator / caminhao", "#444c56", 10)

    # ===================== CAMADA SOLO (OUVIDO) - esquerda =====================
    faixa(ax, 15.2, "CAMADA DE SOLO (OUVIDO)", C_SOLO)
    caixa(ax, 3.2, 16.9, 4.4, 0.8,
          "ESP32 + microfone I2S INMP441\ncaptura janela de audio (2 s)", C_SOLO, 9)
    caixa(ax, 3.2, 15.5, 4.4, 0.8,
          "CNN TFLite INT8 (TFLite Micro)\ninfere P(motosserra) na borda", C_SOLO, 9)
    losango(ax, 3.2, 13.9, 3.0, 1.5, "P_audio\n>= 0.70 ?", C_DECISAO, 9)
    caixa(ax, 3.2, 12.1, 4.2, 0.7,
          "Publica alerta via MQTT\n(prob, lat, lon, timestamp)", C_SOLO, 9)

    # ===================== CAMADA ESPACIAL (OLHO) - direita =====================
    faixa(ax, 15.2, "", C_ESPACO)
    ax.text(11.55, 15.2, "CAMADA ESPACIAL (OLHO)", ha="left", va="center",
            rotation=90, color=C_ESPACO, fontsize=11, fontweight="bold", alpha=0.9)
    caixa(ax, 8.8, 16.9, 4.4, 0.8,
          "Sentinel-2 (Copernicus) +\nalertas DETER/INPE", C_ESPACO, 9)
    caixa(ax, 8.8, 15.5, 4.4, 0.8,
          "NDVI change detection\n(B4 Red, B8 NIR) + OpenCV", C_ESPACO, 9)
    losango(ax, 8.8, 13.9, 3.0, 1.5, "dNDVI\n< -0.15 ?", C_DECISAO, 9)
    caixa(ax, 8.8, 12.1, 4.2, 0.7,
          "Gera alerta DETER\n(poligono, area ha, conf)", C_ESPACO, 9)

    # ===================== NUVEM / FUSAO =====================
    ax.text(11.55, 8.4, "NUVEM (AWS) - FUSAO", ha="left", va="center",
            rotation=90, color=C_NUVEM, fontsize=11, fontweight="bold", alpha=0.9)
    caixa(ax, 6, 10.4, 7.6, 0.8,
          "MOTOR DE FUSAO (AWS Lambda)\nrecebe evento de audio + alerta DETER", C_NUVEM, 10)
    losango(ax, 6, 8.5, 4.2, 1.7,
            "Haversine < 10 km\nE  delta < 7 dias ?", C_DECISAO, 9)
    caixa(ax, 9.7, 8.5, 3.2, 0.9,
          "Registra evento\ne aguarda par", "#444c56", 8)

    caixa(ax, 6, 6.5, 8.2, 0.9,
          "conf = 0.55 x P_audio + 0.45 x conf_DETER\nx fator_distancia x fator_temporal",
          C_NUVEM, 9)

    # ===================== DECISAO FINAL =====================
    losango(ax, 6, 4.6, 3.6, 1.6, "nivel de\nconfianca ?", C_DECISAO, 9)

    caixa(ax, 2.3, 2.7, 3.6, 1.0,
          "CONFIRMADO (conf >= 0.85)\nnotifica IBAMA / ICMBio", C_CONF, 9)
    caixa(ax, 6, 2.7, 3.2, 1.0,
          "SUSPEITO (conf >= 0.65)\nmonitoramento continuo", C_SUSP, 9, fcor="#1a1a1a")
    caixa(ax, 9.5, 2.7, 3.0, 1.0,
          "DESCARTADO\n(conf < 0.65)", "#444c56", 9)

    # ===================== ACAO =====================
    caixa(ax, 4.1, 0.8, 6.6, 0.9,
          "DASHBOARD (Streamlit + Folium): mapa, sensores, fusoes\n+ notificacao (e-mail / Telegram)",
          C_ACAO, 9)

    # ===================== SETAS =====================
    # inicio -> capturas
    seta(ax, 6, 17.75, 3.4, 17.35, curva=0.1)
    seta(ax, 6, 17.75, 8.6, 17.35, curva=-0.1)
    # camada solo
    seta(ax, 3.2, 16.5, 3.2, 15.95)
    seta(ax, 3.2, 15.1, 3.2, 14.7)
    seta(ax, 3.2, 13.1, 3.2, 12.5, "sim")
    seta(ax, 1.7, 13.9, 0.95, 13.9, "nao: ignora")
    # camada espacial
    seta(ax, 8.8, 16.5, 8.8, 15.95)
    seta(ax, 8.8, 15.1, 8.8, 14.7)
    seta(ax, 8.8, 13.1, 8.8, 12.5, "sim")
    seta(ax, 10.3, 13.9, 11.05, 13.9, "nao: ignora")
    # capturas -> fusao
    seta(ax, 3.2, 11.7, 4.4, 10.85, curva=-0.2)
    seta(ax, 8.8, 11.7, 7.6, 10.85, curva=0.2)
    # fusao -> decisao geo
    seta(ax, 6, 10.0, 6, 9.4)
    # decisao geo -> registra (nao) / formula (sim)
    seta(ax, 8.1, 8.5, 8.15, 8.5, "nao")
    seta(ax, 6, 7.6, 6, 7.0, "sim")
    # formula -> decisao confianca
    seta(ax, 6, 6.05, 6, 5.45)
    # decisao confianca -> 3 saidas
    seta(ax, 4.6, 4.2, 2.7, 3.25, "conf >= 0.85", curva=-0.15)
    seta(ax, 6, 3.8, 6, 3.25, "conf >= 0.65")
    seta(ax, 7.4, 4.2, 9.3, 3.25, "conf < 0.65", curva=0.15)
    # confirmado / suspeito -> dashboard
    seta(ax, 2.3, 2.2, 3.6, 1.3, curva=-0.1)
    seta(ax, 6, 2.2, 4.6, 1.3, curva=0.1)

    plt.tight_layout()
    saida = Path(__file__).resolve().parent / "fluxograma.png"
    fig.savefig(saida, dpi=160, bbox_inches="tight", facecolor=C_FUNDO)
    plt.close(fig)
    print("Fluxograma salvo em:", saida)


if __name__ == "__main__":
    main()
