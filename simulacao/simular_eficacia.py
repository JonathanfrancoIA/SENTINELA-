#!/usr/bin/env python3
"""
SENTINELA - Simulacao de Eficacia
==================================
Demonstra, de forma reprodutivel, a eficacia das camadas de IA do
projeto SENTINELA e gera um relatorio visual (PNG + PDF) pronto para
apresentar a banca da FIAP (Global Solution 2026.1).

A simulacao cobre:
  1) OUVIDO  - classificador de audio (motosserra): matriz de confusao,
               acuracia, precisao, recall, F1, especificidade e AUC (ROC).
  2) OLHO    - visao computacional (NDVI change detection): area de
               desmatamento detectada (ha) por severidade e IoU espacial.
  3) FUSAO   - cruzamento audio + satelite: reducao de falsos positivos
               (mesma formula de src/cloud_aws/handler.py).

IMPORTANTE: e uma SIMULACAO. Os dados sao sinteticos e reprodutiveis
(semente fixa). As distribuicoes foram calibradas para refletir as
metricas esperadas descritas nos READMEs (acuracia >= 85%, AUC >= 0.92).

Uso:
    python simular_eficacia.py
    python simular_eficacia.py --semente 42 --saida output

Dependencias (minimas):
    pip install numpy matplotlib
    (scipy e opcional - acelera a rotulagem de poligonos)

Saidas (em ./output):
    relatorio_eficacia.png      - relatorio visual (300 dpi)
    relatorio_eficacia.pdf      - mesmo relatorio em PDF
    metricas_eficacia.json      - todas as metricas em JSON
    relatorio_eficacia.md       - resumo textual

SENTINELA Project - FIAP Global Solution 2026.1
"""

import argparse
import json
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np

import matplotlib
matplotlib.use("Agg")  # backend sem janela (gera arquivos)
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec
from matplotlib.patches import Patch

# Paleta SENTINELA
COR_VERDE = "#1b7837"
COR_VERMELHO = "#b2182b"
COR_LARANJA = "#e08214"
COR_AMARELO = "#fee08b"
COR_AZUL = "#2166ac"
COR_CINZA = "#4d4d4d"

PIXEL_HA = 0.01  # Sentinel-2: pixel de 10 m x 10 m = 100 m2 = 0.01 ha


# =====================================================================
# 1) OUVIDO - Classificador de audio (deteccao de motosserra)
# =====================================================================
def simular_classificador_audio(rng, n_por_classe=200):
    """Gera os scores que o modelo TFLite produziria sobre um conjunto
    de teste balanceado (AMEACA x NORMAL).

    AMEACA (1)  = motosserra / motor / trator
    NORMAL (0)  = floresta / chuva / grilos
    """
    # Scores do modelo: distribuicoes Beta com sobreposicao realista,
    # calibradas para refletir as metricas esperadas no README
    # (acuracia >= 85%, AUC >= 0.92) avaliadas no limiar de 0.70.
    scores_ameaca = rng.beta(9.0, 1.5, n_por_classe)   # media ~0.86
    scores_normal = rng.beta(1.5, 9.0, n_por_classe)   # media ~0.14

    y_true = np.concatenate([np.ones(n_por_classe), np.zeros(n_por_classe)])
    y_score = np.concatenate([scores_ameaca, scores_normal])
    return y_true, y_score


def matriz_confusao(y_true, y_pred):
    tp = int(np.sum((y_true == 1) & (y_pred == 1)))
    fn = int(np.sum((y_true == 1) & (y_pred == 0)))
    fp = int(np.sum((y_true == 0) & (y_pred == 1)))
    tn = int(np.sum((y_true == 0) & (y_pred == 0)))
    return tp, fn, fp, tn


def calcular_metricas(tp, fn, fp, tn):
    total = tp + fn + fp + tn
    acc = (tp + tn) / total if total else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    spec = tn / (tn + fp) if (tn + fp) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"acuracia": acc, "precisao": prec, "recall": rec,
            "especificidade": spec, "f1": f1}


def curva_roc(y_true, y_score, n=200):
    """ROC + AUC (integral trapezoidal, sem dependencia externa)."""
    thresholds = np.linspace(0.0, 1.0, n)
    p = np.sum(y_true == 1)
    neg = np.sum(y_true == 0)
    tpr, fpr = [], []
    for t in thresholds:
        pred = (y_score >= t).astype(int)
        tp = np.sum((y_true == 1) & (pred == 1))
        fp = np.sum((y_true == 0) & (pred == 1))
        tpr.append(tp / p if p else 0.0)
        fpr.append(fp / neg if neg else 0.0)
    fpr = np.array(fpr)
    tpr = np.array(tpr)
    ordem = np.argsort(fpr)
    fpr_o, tpr_o = fpr[ordem], tpr[ordem]
    # integral trapezoidal manual (robusto entre versoes do numpy)
    auc = 0.0
    for i in range(1, len(fpr_o)):
        auc += (fpr_o[i] - fpr_o[i - 1]) * (tpr_o[i] + tpr_o[i - 1]) / 2.0
    return fpr, tpr, abs(auc)


# =====================================================================
# 2) OLHO - Visao computacional (NDVI change detection)
# =====================================================================
def rotular_componentes(mask):
    """Rotula componentes conectados (4-conectividade). Usa scipy se
    disponivel; caso contrario, BFS proprio em numpy puro."""
    try:
        from scipy import ndimage
        labels, n = ndimage.label(mask)
        return labels, int(n)
    except Exception:
        pass
    labels = np.zeros(mask.shape, dtype=int)
    cur = 0
    h, w = mask.shape
    for i in range(h):
        for j in range(w):
            if mask[i, j] and labels[i, j] == 0:
                cur += 1
                pilha = [(i, j)]
                labels[i, j] = cur
                while pilha:
                    y, x = pilha.pop()
                    for dy, dx in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        ny, nx = y + dy, x + dx
                        if 0 <= ny < h and 0 <= nx < w and mask[ny, nx] and labels[ny, nx] == 0:
                            labels[ny, nx] = cur
                            pilha.append((ny, nx))
    return labels, cur


def severidade(area_ha):
    if area_ha > 100:
        return "CRITICO"
    if area_ha >= 25:
        return "ALTO"
    if area_ha >= 5:
        return "MEDIO"
    return "BAIXO"


def simular_visao_computacional(rng, tam=300):
    """Cria uma cena Sentinel-2 sintetica (NDVI antes/depois) com manchas
    de desmatamento plantadas, aplica change detection (dNDVI < -0.15) e
    mede a area detectada (ha) por severidade + IoU contra o gabarito."""
    # NDVI "antes": floresta densa (~0.80) com textura
    ndvi_antes = 0.80 + rng.normal(0, 0.03, (tam, tam))

    # Manchas de desmatamento plantadas (gabarito): (linha, col, alt, larg)
    scars = [
        (30, 40, 120, 100),   # ~120 ha -> CRITICO
        (60, 200, 60, 60),    # ~36 ha  -> ALTO
        (210, 60, 40, 35),    # ~14 ha  -> MEDIO
        (230, 230, 18, 18),   # ~3.2 ha -> BAIXO
    ]
    gabarito = np.zeros((tam, tam), dtype=bool)
    ndvi_depois = ndvi_antes.copy()
    for (r, c, h, w) in scars:
        gabarito[r:r + h, c:c + w] = True
        # corte raso: NDVI cai para ~0.15 (solo exposto)
        ndvi_depois[r:r + h, c:c + w] = 0.15 + rng.normal(0, 0.04, (h, w))

    # ruido geral (nuvens leves / variacao sazonal)
    ndvi_depois += rng.normal(0, 0.03, (tam, tam))

    # change detection
    dndvi = ndvi_depois - ndvi_antes
    detec = dndvi < -0.15

    # limpeza morfologica simples: remove pixels isolados
    detec = _abertura(detec)

    # metricas espaciais (IoU)
    inter = np.sum(detec & gabarito)
    uniao = np.sum(detec | gabarito)
    iou = inter / uniao if uniao else 0.0

    # poligonos detectados
    labels, n = rotular_componentes(detec)
    poligonos = []
    contagem_sev = {"CRITICO": 0, "ALTO": 0, "MEDIO": 0, "BAIXO": 0}
    area_sev = {"CRITICO": 0.0, "ALTO": 0.0, "MEDIO": 0.0, "BAIXO": 0.0}
    for k in range(1, n + 1):
        px = int(np.sum(labels == k))
        area_ha = px * PIXEL_HA
        if area_ha < 0.5:   # descarta ruido residual
            continue
        sev = severidade(area_ha)
        contagem_sev[sev] += 1
        area_sev[sev] += area_ha
        poligonos.append({"id": k, "area_ha": round(area_ha, 2), "severidade": sev})

    area_total = round(sum(p["area_ha"] for p in poligonos), 2)
    return {
        "ndvi_antes": ndvi_antes,
        "ndvi_depois": ndvi_depois,
        "dndvi": dndvi,
        "detec": detec,
        "gabarito": gabarito,
        "iou": iou,
        "n_poligonos": len(poligonos),
        "poligonos": poligonos,
        "area_total_ha": area_total,
        "contagem_sev": contagem_sev,
        "area_sev": area_sev,
        "area_cena_ha": round(tam * tam * PIXEL_HA, 2),
    }


def _abertura(mask):
    """Erosao + dilatacao 3x3 (abertura morfologica) em numpy puro."""
    def erode(m):
        out = m.copy()
        out[1:, :] &= m[:-1, :]
        out[:-1, :] &= m[1:, :]
        out[:, 1:] &= m[:, :-1]
        out[:, :-1] &= m[:, 1:]
        return out

    def dilate(m):
        out = m.copy()
        out[1:, :] |= m[:-1, :]
        out[:-1, :] |= m[1:, :]
        out[:, 1:] |= m[:, :-1]
        out[:, :-1] |= m[:, 1:]
        return out

    return dilate(erode(mask))


# =====================================================================
# 3) FUSAO - audio + satelite (mesma formula de handler.py)
# =====================================================================
def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlon / 2) ** 2)
    return r * 2 * math.asin(math.sqrt(a))


def confianca_fusao(prob_audio, conf_deter, dist_km, delta_dias,
                    raio=10.0, janela=7):
    # decaimento suave: no limite (raio/janela) o fator cai para 0.5,
    # no acerto perfeito (dist 0 / mesmo dia) vale 1.0
    fator_dist = max(0.0, 1.0 - 0.5 * dist_km / raio)
    fator_tempo = max(0.0, 1.0 - 0.5 * delta_dias / janela)
    base = 0.55 * prob_audio + 0.45 * conf_deter
    return base * fator_dist * fator_tempo


def simular_fusao(rng, n_audio=60, n_deter=40):
    """Gera eventos de audio e alertas DETER e cruza-os. Mede quantos
    alertas a fusao confirma vs. o que cada sensor sozinho geraria."""
    centro_lat, centro_lon = -5.0, -62.0

    # alertas DETER (satelite)
    deter = []
    for i in range(n_deter):
        deter.append({
            "lat": centro_lat + rng.uniform(-3, 3),
            "lon": centro_lon + rng.uniform(-3, 3),
            "conf": rng.uniform(0.80, 0.95),
            "dia": int(rng.integers(0, 30)),
        })

    # eventos de audio: metade "reais" (junto de um DETER), metade ruido
    eventos = []
    for i in range(n_audio):
        if i < n_audio // 2:
            base = deter[int(rng.integers(0, n_deter))]
            lat = base["lat"] + rng.normal(0, 0.008)  # ~0.9 km
            lon = base["lon"] + rng.normal(0, 0.008)
            prob = rng.uniform(0.88, 0.99)            # motosserra confirmada
            dia = base["dia"] + int(rng.integers(0, 3))
        else:
            lat = centro_lat + rng.uniform(-3, 3)
            lon = centro_lon + rng.uniform(-3, 3)
            prob = rng.uniform(0.70, 0.95)            # falso positivo de audio
            dia = int(rng.integers(0, 30))
        eventos.append({"lat": lat, "lon": lon, "prob": prob, "dia": dia})

    # audio sozinho: todo evento >= 0.70 viraria alerta
    audio_only = sum(1 for e in eventos if e["prob"] >= 0.70)
    # satelite sozinho: todo alerta DETER
    sat_only = n_deter

    confirmados, suspeitos = 0, 0
    for e in eventos:
        melhor = 0.0
        for d in deter:
            dist = haversine_km(e["lat"], e["lon"], d["lat"], d["lon"])
            delta = abs(e["dia"] - d["dia"])
            if dist <= 10.0 and delta <= 7:
                c = confianca_fusao(e["prob"], d["conf"], dist, delta)
                melhor = max(melhor, c)
        if melhor >= 0.85:
            confirmados += 1
        elif melhor >= 0.65:
            suspeitos += 1

    alertas_fusao = confirmados + suspeitos
    reducao_fp = (audio_only - alertas_fusao) / audio_only if audio_only else 0.0
    return {
        "audio_only": int(audio_only),
        "sat_only": int(sat_only),
        "confirmados": int(confirmados),
        "suspeitos": int(suspeitos),
        "alertas_fusao": int(alertas_fusao),
        "reducao_fp": reducao_fp,
    }


# =====================================================================
# RELATORIO VISUAL
# =====================================================================
def gerar_relatorio(audio, visao, fusao, saida):
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle("SENTINELA  -  Relatorio de Eficacia (Simulacao)",
                 fontsize=20, fontweight="bold", color=COR_CINZA, y=0.98)
    fig.text(0.5, 0.935,
             "O olho e o ouvido da floresta  |  FIAP Global Solution 2026.1  |  "
             + datetime.now().strftime("%d/%m/%Y %H:%M"),
             ha="center", fontsize=11, color=COR_CINZA)

    gs = GridSpec(2, 3, figure=fig, hspace=0.38, wspace=0.30,
                  top=0.88, bottom=0.07, left=0.06, right=0.97)

    # --- Painel A: matriz de confusao (audio) ---
    ax = fig.add_subplot(gs[0, 0])
    cm = np.array([[audio["tp"], audio["fn"]],
                   [audio["fp"], audio["tn"]]])
    ax.imshow(cm, cmap="Greens")
    rotulos = ["AMEACA", "NORMAL"]
    ax.set_xticks([0, 1]); ax.set_yticks([0, 1])
    ax.set_xticklabels(["Prev. AMEACA", "Prev. NORMAL"])
    ax.set_yticklabels(rotulos)
    ax.set_ylabel("Verdadeiro")
    ax.set_title("Matriz de Confusao - Audio (motosserra)", fontweight="bold")
    vmax = cm.max()
    for (i, j), v in np.ndenumerate(cm):
        ax.text(j, i, str(v), ha="center", va="center", fontsize=18,
                color="white" if v > vmax * 0.5 else COR_CINZA, fontweight="bold")

    # --- Painel B: curva ROC ---
    ax = fig.add_subplot(gs[0, 1])
    ax.plot(audio["fpr"], audio["tpr"], color=COR_AZUL, lw=2.5,
            label="AUC = %.3f" % audio["auc"])
    ax.plot([0, 1], [0, 1], "--", color="grey", lw=1)
    ax.fill_between(np.sort(audio["fpr"]),
                    audio["tpr"][np.argsort(audio["fpr"])], alpha=0.15,
                    color=COR_AZUL)
    ax.set_xlim(0, 1); ax.set_ylim(0, 1.02)
    ax.set_xlabel("Falsos Positivos (FPR)")
    ax.set_ylabel("Verdadeiros Positivos (TPR)")
    ax.set_title("Curva ROC - Classificador de Audio", fontweight="bold")
    ax.legend(loc="lower right", fontsize=12)

    # --- Painel C: barras de metricas ---
    ax = fig.add_subplot(gs[0, 2])
    nomes = ["Acuracia", "Precisao", "Recall", "F1", "Especif.", "AUC"]
    valores = [audio["m"]["acuracia"], audio["m"]["precisao"], audio["m"]["recall"],
               audio["m"]["f1"], audio["m"]["especificidade"], audio["auc"]]
    cores = [COR_VERDE if v >= 0.85 else COR_LARANJA for v in valores]
    barras = ax.bar(nomes, valores, color=cores)
    ax.axhline(0.85, ls="--", color=COR_VERMELHO, lw=1)
    ax.text(5.4, 0.86, "meta 0.85", color=COR_VERMELHO, fontsize=9, ha="right")
    ax.set_ylim(0, 1.05)
    ax.set_title("Metricas do Modelo de Audio", fontweight="bold")
    for b, v in zip(barras, valores):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.015, "%.2f" % v,
                ha="center", fontsize=9, fontweight="bold")
    plt.setp(ax.get_xticklabels(), rotation=25, ha="right")

    # --- Painel D: deteccao NDVI (mapa) ---
    ax = fig.add_subplot(gs[1, 0])
    rgb = np.zeros(visao["dndvi"].shape + (3,))
    # verde para floresta, vermelho onde detectou desmatamento
    rgb[..., 1] = np.clip(visao["ndvi_depois"], 0, 1)
    rgb[visao["detec"]] = [0.85, 0.1, 0.1]
    ax.imshow(rgb)
    ax.set_xticks([]); ax.set_yticks([])
    ax.set_title("Deteccao NDVI (vermelho = desmatamento)", fontweight="bold")
    ax.text(0.02, 0.04,
            "IoU espacial = %.2f" % visao["iou"],
            transform=ax.transAxes, color="white", fontsize=11,
            fontweight="bold",
            bbox=dict(boxstyle="round", fc=COR_CINZA, alpha=0.7))

    # --- Painel E: area por severidade ---
    ax = fig.add_subplot(gs[1, 1])
    sev_ordem = ["CRITICO", "ALTO", "MEDIO", "BAIXO"]
    sev_cores = {"CRITICO": COR_VERMELHO, "ALTO": COR_LARANJA,
                 "MEDIO": "#fdae61", "BAIXO": COR_VERDE}
    areas = [visao["area_sev"][s] for s in sev_ordem]
    barras = ax.bar(sev_ordem, areas, color=[sev_cores[s] for s in sev_ordem])
    ax.set_ylabel("Area detectada (ha)")
    ax.set_title("Desmatamento por Severidade", fontweight="bold")
    for b, a in zip(barras, areas):
        if a > 0:
            ax.text(b.get_x() + b.get_width() / 2, a + max(areas) * 0.01,
                    "%.1f ha" % a, ha="center", fontsize=9, fontweight="bold")
    ax.text(0.97, 0.95,
            "TOTAL: %.1f ha\n%d poligonos\n(cena: %.0f ha)" % (
                visao["area_total_ha"], visao["n_poligonos"], visao["area_cena_ha"]),
            transform=ax.transAxes, ha="right", va="top", fontsize=10,
            bbox=dict(boxstyle="round", fc=COR_AMARELO, alpha=0.8))

    # --- Painel F: fusao / reducao de falsos positivos ---
    ax = fig.add_subplot(gs[1, 2])
    cats = ["Audio\nsozinho", "Satelite\nsozinho", "FUSAO\n(corrobor.)"]
    vals = [fusao["audio_only"], fusao["sat_only"], fusao["alertas_fusao"]]
    cores = [COR_AMARELO, COR_AZUL, COR_VERDE]
    barras = ax.bar(cats, vals, color=cores, edgecolor=COR_CINZA)
    ax.set_ylabel("Nº de alertas")
    ax.set_ylim(0, max(vals) * 1.25)
    ax.set_title("Fusao reduz falsos positivos", fontweight="bold")
    for b, v in zip(barras, vals):
        ax.text(b.get_x() + b.get_width() / 2, v + 0.5, str(v),
                ha="center", fontsize=11, fontweight="bold")
    ax.text(0.5, 0.93,
            "Reducao de alertas: %.0f%%\n%d confirmados + %d suspeitos" % (
                fusao["reducao_fp"] * 100, fusao["confirmados"], fusao["suspeitos"]),
            transform=ax.transAxes, ha="center", va="top", fontsize=10,
            bbox=dict(boxstyle="round", fc="#d9f0d3", alpha=0.9))

    png = saida / "relatorio_eficacia.png"
    pdf = saida / "relatorio_eficacia.pdf"
    fig.savefig(png, dpi=300, bbox_inches="tight")
    fig.savefig(pdf, bbox_inches="tight")
    plt.close(fig)
    return png, pdf


# =====================================================================
# MAIN
# =====================================================================
def main():
    ap = argparse.ArgumentParser(description="SENTINELA - Simulacao de eficacia")
    ap.add_argument("--semente", type=int, default=42, help="semente aleatoria")
    ap.add_argument("--saida", type=str, default="output", help="pasta de saida")
    ap.add_argument("--threshold", type=float, default=0.70,
                    help="limiar de deteccao de motosserra (default 0.70)")
    args = ap.parse_args()

    rng = np.random.default_rng(args.semente)
    saida = Path(__file__).parent / args.saida
    saida.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("  SENTINELA - SIMULACAO DE EFICACIA")
    print("=" * 60)

    # --- 1) Audio ---
    y_true, y_score = simular_classificador_audio(rng)
    y_pred = (y_score >= args.threshold).astype(int)
    tp, fn, fp, tn = matriz_confusao(y_true, y_pred)
    m = calcular_metricas(tp, fn, fp, tn)
    fpr, tpr, auc = curva_roc(y_true, y_score)
    audio = {"tp": tp, "fn": fn, "fp": fp, "tn": tn, "m": m,
             "fpr": fpr, "tpr": tpr, "auc": auc}

    print("\n[OUVIDO] Classificador de audio (limiar %.2f)" % args.threshold)
    print("  Matriz de confusao: TP=%d FN=%d FP=%d TN=%d" % (tp, fn, fp, tn))
    print("  Acuracia ....... %.1f%%" % (m["acuracia"] * 100))
    print("  Precisao ....... %.1f%%" % (m["precisao"] * 100))
    print("  Recall ......... %.1f%%" % (m["recall"] * 100))
    print("  F1-score ....... %.1f%%" % (m["f1"] * 100))
    print("  Especificidade . %.1f%%" % (m["especificidade"] * 100))
    print("  AUC ............ %.3f" % auc)

    # --- 2) Visao ---
    visao = simular_visao_computacional(rng)
    print("\n[OLHO] Visao computacional (NDVI change detection)")
    print("  Poligonos detectados ... %d" % visao["n_poligonos"])
    print("  Area total desmatada ... %.1f ha (cena de %.0f ha)" % (
        visao["area_total_ha"], visao["area_cena_ha"]))
    print("  IoU espacial ........... %.2f" % visao["iou"])
    for s in ["CRITICO", "ALTO", "MEDIO", "BAIXO"]:
        if visao["contagem_sev"][s]:
            print("    %-8s %d poligono(s)  %.1f ha" % (
                s, visao["contagem_sev"][s], visao["area_sev"][s]))

    # --- 3) Fusao ---
    fusao = simular_fusao(rng)
    print("\n[FUSAO] Audio + satelite")
    print("  Audio sozinho .......... %d alertas" % fusao["audio_only"])
    print("  Satelite sozinho ....... %d alertas" % fusao["sat_only"])
    print("  FUSAO confirmados ...... %d" % fusao["confirmados"])
    print("  FUSAO suspeitos ........ %d" % fusao["suspeitos"])
    print("  Reducao de alertas ..... %.0f%%" % (fusao["reducao_fp"] * 100))

    # --- Relatorio visual ---
    png, pdf = gerar_relatorio(audio, visao, fusao, saida)

    # --- JSON + Markdown ---
    metricas = {
        "gerado_em": datetime.now().isoformat(timespec="seconds"),
        "semente": args.semente,
        "audio": {"matriz_confusao": {"TP": tp, "FN": fn, "FP": fp, "TN": tn},
                  "metricas": m, "auc": auc, "threshold": args.threshold},
        "visao": {"n_poligonos": visao["n_poligonos"],
                  "area_total_ha": visao["area_total_ha"],
                  "iou": visao["iou"],
                  "area_por_severidade": visao["area_sev"],
                  "poligonos": visao["poligonos"]},
        "fusao": fusao,
    }
    (saida / "metricas_eficacia.json").write_text(
        json.dumps(metricas, indent=2, ensure_ascii=False), encoding="utf-8")

    md = []
    md.append("# SENTINELA - Relatorio de Eficacia (Simulacao)\n")
    md.append("Gerado em %s | semente=%d\n" % (
        datetime.now().strftime("%d/%m/%Y %H:%M"), args.semente))
    md.append("\n## Ouvido - Classificador de audio (motosserra)\n")
    md.append("| Metrica | Valor |\n|---|---|\n")
    md.append("| Acuracia | %.1f%% |\n" % (m["acuracia"] * 100))
    md.append("| Precisao | %.1f%% |\n" % (m["precisao"] * 100))
    md.append("| Recall | %.1f%% |\n" % (m["recall"] * 100))
    md.append("| F1-score | %.1f%% |\n" % (m["f1"] * 100))
    md.append("| Especificidade | %.1f%% |\n" % (m["especificidade"] * 100))
    md.append("| AUC | %.3f |\n" % auc)
    md.append("| Matriz | TP=%d FN=%d FP=%d TN=%d |\n" % (tp, fn, fp, tn))
    md.append("\n## Olho - Visao computacional (NDVI)\n")
    md.append("- Area total desmatada: **%.1f ha** em %d poligono(s)\n" % (
        visao["area_total_ha"], visao["n_poligonos"]))
    md.append("- IoU espacial (deteccao x gabarito): **%.2f**\n" % visao["iou"])
    md.append("\n## Fusao - audio + satelite\n")
    md.append("- Audio sozinho: %d alertas\n" % fusao["audio_only"])
    md.append("- Fusao confirmados: %d | suspeitos: %d\n" % (
        fusao["confirmados"], fusao["suspeitos"]))
    md.append("- Reducao de alertas (menos falsos positivos): **%.0f%%**\n" % (
        fusao["reducao_fp"] * 100))
    (saida / "relatorio_eficacia.md").write_text("".join(md), encoding="utf-8")

    print("\n" + "=" * 60)
    print("  RELATORIO GERADO:")
    print("  - %s" % png)
    print("  - %s" % pdf)
    print("  - %s" % (saida / "metricas_eficacia.json"))
    print("  - %s" % (saida / "relatorio_eficacia.md"))
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
