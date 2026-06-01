#!/usr/bin/env python3
"""
SENTINELA — Módulo de Visão Computacional
==========================================
Detecta desmatamento em imagens de satélite Sentinel-2 comparando
NDVI (antes vs. depois) e segmentando áreas de corte raso/degradação.

Status: ✅ Funcional (dados reais ou simulados)

Uso:
    # Com imagens GeoTIFF reais do Copernicus:
    python detectar_desmatamento.py --antes antes.tif --depois depois.tif

    # Modo demo (gera imagens sintéticas):
    python detectar_desmatamento.py --demo

    # Com visualização interativa:
    python detectar_desmatamento.py --demo --visualizar

Dependências:
    pip install rasterio numpy opencv-python Pillow matplotlib
"""

import os
import sys
import argparse
import json
import warnings
from pathlib import Path
from datetime import datetime, timedelta
import random

import numpy as np
from loguru import logger

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────
# Constantes
# ─────────────────────────────────────────────────────────────
OUTPUT_DIR = Path("output")
NDVI_THRESHOLD_DESMATAMENTO = -0.15  # queda mínima de NDVI para considerar desmatamento
AREA_MINIMA_PIXELS = 50              # mínimo de pixels para um polígono ser reportado
RESOLUCAO_M_POR_PIXEL = 10           # Sentinel-2 B4/B8 = 10 m/pixel

# Bandas Sentinel-2 usadas:
#   B4 (Red)     = 665 nm → reflectância vegetação
#   B8 (NIR)     = 842 nm → absorção clorofila
#   B12 (SWIR)   = 2190 nm → umidade / queimada


# ─────────────────────────────────────────────────────────────
# Leitura de imagens GeoTIFF (Sentinel-2)
# ─────────────────────────────────────────────────────────────
def ler_geotiff(path: str) -> tuple[np.ndarray, dict]:
    """
    Lê um GeoTIFF multibanda e retorna (array, metadata).
    Espera ao menos 2 bandas: índice 0 = Red (B4), índice 1 = NIR (B8).
    """
    try:
        import rasterio
        with rasterio.open(path) as src:
            data = src.read().astype(np.float32)  # (bandas, H, W)
            meta = {
                "crs": str(src.crs),
                "transform": src.transform,
                "bounds": src.bounds,
                "width": src.width,
                "height": src.height,
                "count": src.count,
            }
        logger.info("GeoTIFF lido: {} | shape={} | CRS={}", path, data.shape, meta["crs"])
        return data, meta
    except ImportError:
        logger.warning("rasterio não disponível — usando modo simulado")
        return None, {}


def calcular_ndvi(data: np.ndarray, banda_red: int = 0, banda_nir: int = 1) -> np.ndarray:
    """
    NDVI = (NIR - Red) / (NIR + Red)
    Valores: floresta densa ≈ 0.6–0.9, desmatamento ≈ 0.0–0.2, solo exposto ≈ -0.2–0.1
    """
    red = data[banda_red].astype(np.float64)
    nir = data[banda_nir].astype(np.float64)

    # Normaliza reflectância (Sentinel-2 Level-2A: 0–10000)
    if red.max() > 1.0:
        red = red / 10000.0
        nir = nir / 10000.0

    denom = nir + red
    ndvi = np.where(denom > 0.0001, (nir - red) / denom, 0.0)
    ndvi = np.clip(ndvi, -1.0, 1.0)
    return ndvi.astype(np.float32)


# ─────────────────────────────────────────────────────────────
# Detecção de mudança (change detection)
# ─────────────────────────────────────────────────────────────
def detectar_mudanca(ndvi_antes: np.ndarray, ndvi_depois: np.ndarray) -> np.ndarray:
    """
    Calcula diferença de NDVI e cria máscara binária de desmatamento.
    Desmatamento = NDVI caiu mais que o threshold (floresta → solo).
    """
    diff = ndvi_depois - ndvi_antes  # negativo = perda de vegetação
    mascara = (diff < NDVI_THRESHOLD_DESMATAMENTO).astype(np.uint8)
    return diff, mascara


def segmentar_poligonos(mascara: np.ndarray) -> list[dict]:
    """
    Encontra contornos contíguos na máscara e retorna lista de polígonos
    com área, centróide e bounding box.
    """
    import cv2

    # Morfologia para limpar ruído
    kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
    mascara_limpa = cv2.morphologyEx(mascara, cv2.MORPH_OPEN, kernel)
    mascara_limpa = cv2.morphologyEx(mascara_limpa, cv2.MORPH_CLOSE, kernel)

    contornos, _ = cv2.findContours(
        mascara_limpa, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
    )

    poligonos = []
    for cnt in contornos:
        area_pixels = cv2.contourArea(cnt)
        if area_pixels < AREA_MINIMA_PIXELS:
            continue

        M = cv2.moments(cnt)
        if M["m00"] == 0:
            continue

        cx = int(M["m10"] / M["m00"])
        cy = int(M["m01"] / M["m00"])
        x, y, w, h = cv2.boundingRect(cnt)

        area_ha = area_pixels * (RESOLUCAO_M_POR_PIXEL ** 2) / 10000  # hectares

        poligonos.append({
            "area_pixels": int(area_pixels),
            "area_hectares": round(area_ha, 2),
            "centroide_pixel": [cx, cy],
            "bbox_pixel": [x, y, x + w, y + h],
            "contorno": cnt.reshape(-1, 2).tolist(),
        })

    poligonos.sort(key=lambda p: p["area_hectares"], reverse=True)
    return poligonos


# ─────────────────────────────────────────────────────────────
# Conversão para coordenadas geográficas
# ─────────────────────────────────────────────────────────────
def pixel_para_geo(pixel_x: int, pixel_y: int, transform) -> tuple[float, float]:
    """Converte pixel (col, row) para coordenadas geográficas (lon, lat) usando rasterio."""
    try:
        from rasterio.transform import xy
        lon, lat = xy(transform, pixel_y, pixel_x)
        return float(lon), float(lat)
    except Exception:
        # Fallback com coordenadas simuladas da Amazônia
        base_lon, base_lat = -62.2, -3.4
        lon = base_lon + pixel_x * 0.0001
        lat = base_lat - pixel_y * 0.0001
        return lon, lat


def poligonos_para_geojson(poligonos: list[dict], transform=None,
                            data_deteccao: str = None) -> dict:
    """Converte lista de polígonos para GeoJSON com metadados de desmatamento."""
    features = []

    for i, poly in enumerate(poligonos):
        cx, cy = poly["centroide_pixel"]
        lon, lat = pixel_para_geo(cx, cy, transform)

        # Classifica severidade
        area = poly["area_hectares"]
        if area > 100:
            severidade = "CRITICO"
        elif area > 25:
            severidade = "ALTO"
        elif area > 5:
            severidade = "MEDIO"
        else:
            severidade = "BAIXO"

        feature = {
            "type": "Feature",
            "geometry": {
                "type": "Point",
                "coordinates": [lon, lat],
            },
            "properties": {
                "id": f"DES-{i+1:04d}",
                "area_hectares": area,
                "severidade": severidade,
                "centroide_lon": lon,
                "centroide_lat": lat,
                "data_deteccao": data_deteccao or datetime.now().isoformat(),
                "fonte": "Sentinel-2 NDVI Change Detection",
                "confianca": 0.85,  # seria calculada por modelo ML em produção
            },
        }
        features.append(feature)

    return {
        "type": "FeatureCollection",
        "features": features,
        "metadata": {
            "total_poligonos": len(poligonos),
            "area_total_ha": sum(p["area_hectares"] for p in poligonos),
            "data_analise": datetime.now().isoformat(),
            "metodo": "NDVI Change Detection (Sentinel-2)",
            "threshold_ndvi": NDVI_THRESHOLD_DESMATAMENTO,
        },
    }


# ─────────────────────────────────────────────────────────────
# Visualização
# ─────────────────────────────────────────────────────────────
def gerar_relatorio_visual(ndvi_antes: np.ndarray, ndvi_depois: np.ndarray,
                           diff: np.ndarray, mascara: np.ndarray,
                           poligonos: list[dict], output_path: Path):
    """Gera relatório visual em PNG com subplots de NDVI e detecções."""
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.colors import LinearSegmentedColormap
    import cv2

    fig, axes = plt.subplots(2, 2, figsize=(16, 14))
    fig.patch.set_facecolor("#0d1117")

    cmap_ndvi = LinearSegmentedColormap.from_list(
        "ndvi", ["#8B4513", "#FFFF00", "#00AA00", "#006400"]
    )
    cmap_diff = LinearSegmentedColormap.from_list(
        "diff", ["#FF0000", "#FF6600", "#FFFF00", "#FFFFFF", "#00FF00"]
    )

    for ax in axes.flat:
        ax.set_facecolor("#0d1117")

    # 1. NDVI Antes
    im1 = axes[0, 0].imshow(ndvi_antes, cmap=cmap_ndvi, vmin=-0.3, vmax=0.9)
    axes[0, 0].set_title("NDVI — Antes", color="white", fontsize=13, pad=10)
    axes[0, 0].axis("off")
    plt.colorbar(im1, ax=axes[0, 0], fraction=0.046, label="NDVI").ax.yaxis.label.set_color("white")

    # 2. NDVI Depois
    im2 = axes[0, 1].imshow(ndvi_depois, cmap=cmap_ndvi, vmin=-0.3, vmax=0.9)
    axes[0, 1].set_title("NDVI — Depois", color="white", fontsize=13, pad=10)
    axes[0, 1].axis("off")
    plt.colorbar(im2, ax=axes[0, 1], fraction=0.046, label="NDVI").ax.yaxis.label.set_color("white")

    # 3. Diferença de NDVI
    im3 = axes[1, 0].imshow(diff, cmap=cmap_diff, vmin=-0.6, vmax=0.3)
    axes[1, 0].set_title("Diferença NDVI (Perda de Vegetação)", color="white", fontsize=13, pad=10)
    axes[1, 0].axis("off")
    plt.colorbar(im3, ax=axes[1, 0], fraction=0.046, label="ΔNDVI").ax.yaxis.label.set_color("white")

    # 4. Detecções (máscara + contornos)
    display = np.zeros((*ndvi_depois.shape, 3), dtype=np.uint8)
    # Fundo: verde = floresta
    ndvi_rgb = ((ndvi_depois + 0.3) / 1.2 * 255).clip(0, 255).astype(np.uint8)
    display[:, :, 1] = ndvi_rgb  # canal verde

    # Desmatamento em vermelho
    display[mascara == 1, 0] = 220
    display[mascara == 1, 1] = 50
    display[mascara == 1, 2] = 50

    # Contornos em laranja
    contours_cv = [np.array(p["contorno"]) for p in poligonos]
    cv2.drawContours(display, [np.array(c, dtype=np.int32).reshape(-1, 1, 2)
                                for c in contours_cv], -1, (255, 165, 0), 2)

    axes[1, 1].imshow(display)
    axes[1, 1].set_title(
        f"Áreas Desmatadas Detectadas ({len(poligonos)} polígonos)",
        color="white", fontsize=13, pad=10
    )
    axes[1, 1].axis("off")

    # Legenda
    verde_patch  = mpatches.Patch(color="#006400", label="Floresta")
    vermelho_patch = mpatches.Patch(color="#DC3232", label="Desmatamento detectado")
    laranja_patch  = mpatches.Patch(color="#FFA500", label="Contorno do polígono")
    axes[1, 1].legend(handles=[verde_patch, vermelho_patch, laranja_patch],
                      loc="lower right", facecolor="#1a1a2e", labelcolor="white", fontsize=9)

    # Título geral
    area_total = sum(p["area_hectares"] for p in poligonos)
    fig.suptitle(
        f"SENTINELA — Detecção de Desmatamento via Sentinel-2\n"
        f"Total: {len(poligonos)} áreas | {area_total:.1f} ha afetados",
        color="white", fontsize=15, y=0.98, fontweight="bold"
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="#0d1117")
    plt.close()
    logger.success("Relatório visual salvo em {}", output_path)


# ─────────────────────────────────────────────────────────────
# Geração de dados sintéticos (modo demo)
# ─────────────────────────────────────────────────────────────
def gerar_imagem_sintetica(h: int = 256, w: int = 256, n_manchas: int = 5):
    """
    Gera par de imagens sintéticas (antes/depois) com manchas de desmatamento.
    Simula reflectâncias Sentinel-2 B4 (Red) e B8 (NIR) normalizadas 0–1.
    """
    random.seed(42)
    np.random.seed(42)

    def criar_ndvi_floresta(h, w):
        """NDVI base de floresta densa com variação natural."""
        base = np.random.normal(0.75, 0.08, (h, w))
        # Gradiente suave de umidade
        grad_x = np.linspace(0, 0.1, w)
        grad_y = np.linspace(0, 0.05, h)[:, None]
        base += grad_x + grad_y
        return np.clip(base, 0.4, 0.95).astype(np.float32)

    ndvi_antes = criar_ndvi_floresta(h, w)
    ndvi_depois = ndvi_antes.copy()

    # Adiciona manchas de desmatamento
    manchas_criadas = []
    for _ in range(n_manchas):
        # Centro e tamanho aleatórios
        cy = random.randint(20, h - 20)
        cx = random.randint(20, w - 20)
        raio = random.randint(8, 25)
        intensidade = random.uniform(0.4, 0.7)  # queda de NDVI

        y, x = np.ogrid[:h, :w]
        mascara_elipse = ((y - cy)**2 / (raio**2) + (x - cx)**2 / ((raio * 1.4)**2)) <= 1

        ndvi_depois[mascara_elipse] -= intensidade
        ndvi_depois[mascara_elipse] += np.random.normal(0, 0.05, mascara_elipse.sum())
        ndvi_depois = np.clip(ndvi_depois, -0.3, 0.95)

        manchas_criadas.append({"cy": cy, "cx": cx, "raio": raio})

    logger.info("Imagem sintética gerada: {} manchas de desmatamento", n_manchas)
    return ndvi_antes, ndvi_depois


# ─────────────────────────────────────────────────────────────
# Pipeline principal
# ─────────────────────────────────────────────────────────────
def pipeline(ndvi_antes: np.ndarray, ndvi_depois: np.ndarray,
             transform=None, visualizar: bool = False) -> dict:
    """Executa o pipeline completo de detecção de desmatamento."""

    logger.info("Calculando diferença de NDVI …")
    diff, mascara = detectar_mudanca(ndvi_antes, ndvi_depois)

    n_pixels_desmatados = int(mascara.sum())
    area_total_ha = n_pixels_desmatados * (RESOLUCAO_M_POR_PIXEL ** 2) / 10000
    logger.info("Pixels desmatados: {} ({:.1f} ha)", n_pixels_desmatados, area_total_ha)

    logger.info("Segmentando polígonos de desmatamento …")
    try:
        poligonos = segmentar_poligonos(mascara)
    except ImportError:
        logger.warning("OpenCV não disponível — sem segmentação de polígonos")
        poligonos = []

    logger.info("{} polígonos detectados", len(poligonos))
    for p in poligonos[:5]:  # top 5
        logger.info("  → {:.2f} ha | severidade={}", p["area_hectares"],
                    "CRITICO" if p["area_hectares"] > 100 else "ALTO" if p["area_hectares"] > 25 else "MEDIO")

    # Gera GeoJSON
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    geojson = poligonos_para_geojson(poligonos, transform)
    geojson_path = OUTPUT_DIR / f"desmatamento_{datetime.now().strftime('%Y%m%d_%H%M%S')}.geojson"
    with open(geojson_path, "w") as f:
        json.dump(geojson, f, indent=2, ensure_ascii=False)
    logger.success("GeoJSON salvo em {}", geojson_path)

    # Visualização
    if visualizar:
        try:
            png_path = OUTPUT_DIR / "relatorio_desmatamento.png"
            gerar_relatorio_visual(ndvi_antes, ndvi_depois, diff, mascara, poligonos, png_path)
        except Exception as e:
            logger.warning("Visualização falhou: {}", e)

    resultado = {
        "status": "OK",
        "n_poligonos": len(poligonos),
        "area_total_ha": round(area_total_ha, 2),
        "geojson_path": str(geojson_path),
        "poligonos": poligonos[:10],  # top 10 para API
        "timestamp": datetime.now().isoformat(),
    }
    return resultado


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="SENTINELA — Detecta desmatamento via comparação de NDVI (Sentinel-2)"
    )
    parser.add_argument("--antes", type=str, help="GeoTIFF imagem anterior (bandas Red+NIR)")
    parser.add_argument("--depois", type=str, help="GeoTIFF imagem posterior")
    parser.add_argument("--demo", action="store_true", help="Usa imagens sintéticas para demo")
    parser.add_argument("--visualizar", action="store_true", help="Gera relatório visual PNG")
    parser.add_argument("--n-manchas", type=int, default=7, help="(demo) nº de manchas sintéticas")
    # ── Download REAL de Sentinel-2 (Copernicus Data Space) ──
    parser.add_argument("--baixar", action="store_true",
                        help="Baixa cenas Sentinel-2 REAIS (requer --bbox, --data-antes, "
                             "--data-depois e credenciais SH_CLIENT_ID/SH_CLIENT_SECRET no .env)")
    parser.add_argument("--bbox", type=float, nargs=4,
                        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
                        help="(--baixar) Área de interesse em EPSG:4326")
    parser.add_argument("--data-antes", type=str, help="(--baixar) Data da cena anterior YYYY-MM-DD")
    parser.add_argument("--data-depois", type=str, help="(--baixar) Data da cena posterior YYYY-MM-DD")
    parser.add_argument("--dias-tolerancia", type=int, default=10,
                        help="(--baixar) Busca a melhor cena em ±N dias da data alvo (padrão 10)")
    parser.add_argument("--nuvens-max", type=int, default=40,
                        help="(--baixar) Cobertura máxima de nuvens aceita em %% (padrão 40)")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("  SENTINELA — Visão Computacional")
    logger.info("  Detecção de Desmatamento via Sentinel-2")
    logger.info("=" * 60)

    if args.baixar:
        if not (args.bbox and args.data_antes and args.data_depois):
            logger.error("--baixar exige --bbox, --data-antes e --data-depois")
            sys.exit(1)
        try:
            from baixar_sentinel2 import baixar_cena
        except ImportError:
            logger.error("baixar_sentinel2.py não encontrado no mesmo diretório")
            sys.exit(1)

        logger.info("Modo REAL — baixando cenas Sentinel-2 do Copernicus …")
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        path_antes = baixar_cena(bbox=tuple(args.bbox), data=args.data_antes,
                                 saida=str(OUTPUT_DIR / "cena_antes.tiff"),
                                 dias_tolerancia=args.dias_tolerancia,
                                 nuvens_max=args.nuvens_max)
        path_depois = baixar_cena(bbox=tuple(args.bbox), data=args.data_depois,
                                  saida=str(OUTPUT_DIR / "cena_depois.tiff"),
                                  dias_tolerancia=args.dias_tolerancia,
                                  nuvens_max=args.nuvens_max)
        if not path_antes or not path_depois:
            logger.error("Falha no download das cenas reais (ver mensagens acima). "
                         "Verifique credenciais/data ou use --demo.")
            sys.exit(1)

        data_antes, meta_antes = ler_geotiff(path_antes)
        data_depois, meta_depois = ler_geotiff(path_depois)
        if data_antes is None or data_depois is None:
            logger.error("rasterio necessário para ler os GeoTIFFs baixados — "
                         "pip install rasterio")
            sys.exit(1)
        ndvi_antes = calcular_ndvi(data_antes)
        ndvi_depois = calcular_ndvi(data_depois)
        transform = meta_antes.get("transform")

        # Registra metadados da análise (região + período) p/ o dashboard
        min_lon, min_lat, max_lon, max_lat = args.bbox
        metadados = {
            "bbox": list(args.bbox),
            "bbox_legivel": f"{min_lon}, {min_lat} → {max_lon}, {max_lat}",
            "centro_lon": round((min_lon + max_lon) / 2, 5),
            "centro_lat": round((min_lat + max_lat) / 2, 5),
            "data_antes": args.data_antes,
            "data_depois": args.data_depois,
            "dias_tolerancia": args.dias_tolerancia,
            "nuvens_max": args.nuvens_max,
            "fonte": "Sentinel-2 (Copernicus Data Space) — NDVI Change Detection",
            "gerado_em": datetime.now().isoformat(timespec="seconds"),
        }
        with open(OUTPUT_DIR / "metadata_analise.json", "w", encoding="utf-8") as fh:
            json.dump(metadados, fh, ensure_ascii=False, indent=2)
        logger.info("Metadados salvos em {}", OUTPUT_DIR / "metadata_analise.json")
    elif args.demo:
        logger.info("Modo DEMO — gerando imagens sintéticas …")
        ndvi_antes, ndvi_depois = gerar_imagem_sintetica(n_manchas=args.n_manchas)
        transform = None
    elif args.antes and args.depois:
        logger.info("Lendo imagens reais …")
        data_antes, meta_antes = ler_geotiff(args.antes)
        data_depois, meta_depois = ler_geotiff(args.depois)
        if data_antes is None or data_depois is None:
            logger.error("Falha ao ler GeoTIFFs — use --demo para testar sem dados reais")
            sys.exit(1)
        ndvi_antes = calcular_ndvi(data_antes)
        ndvi_depois = calcular_ndvi(data_depois)
        transform = meta_antes.get("transform")
    else:
        logger.error("Informe --antes e --depois (ou use --demo)")
        parser.print_help()
        sys.exit(1)

    resultado = pipeline(ndvi_antes, ndvi_depois, transform=transform,
                         visualizar=args.visualizar)

    logger.success("=" * 60)
    logger.success("  RESULTADO FINAL")
    logger.success("  Polígonos detectados: {}", resultado["n_poligonos"])
    logger.success("  Área total afetada: {} ha", resultado["area_total_ha"])
    logger.success("  GeoJSON: {}", resultado["geojson_path"])
    logger.success("=" * 60)


if __name__ == "__main__":
    main()
