# 👁️ visao_computacional — Detecção de Desmatamento (Sentinel-2)

Módulo de **visão computacional** do SENTINELA: analisa imagens de satélite Sentinel-2 comparando o NDVI (índice de vegetação) antes e depois para detectar manchas de desmatamento.

## Status

| Componente | Status |
|-----------|--------|
| Leitura de GeoTIFF (Sentinel-2) | ✅ Funcional (com rasterio) |
| Cálculo de NDVI | ✅ Funcional |
| Detecção de mudança (change detection) | ✅ Funcional |
| Segmentação de polígonos (OpenCV) | ✅ Funcional |
| Export GeoJSON | ✅ Funcional |
| Relatório visual (PNG) | ✅ Funcional |
| Modo demo (dados sintéticos) | ✅ Funcional |

## O que é NDVI?

**NDVI = (NIR − Red) / (NIR + Red)**

Índice de vegetação baseado na diferença entre a banda do infravermelho próximo (NIR, B8 do Sentinel-2) e a banda do vermelho (Red, B4). Quanto maior o NDVI, mais densa a vegetação.

| Cobertura | NDVI típico |
|-----------|------------|
| Floresta densa (Amazônia) | 0,6 – 0,9 |
| Vegetação degradada | 0,3 – 0,6 |
| Pastagem / capoeira | 0,1 – 0,4 |
| Solo exposto / queimada | −0,2 – 0,15 |
| Água | −0,5 – 0,0 |

## Pipeline de Detecção

```
Imagem Sentinel-2 (ANTES)     Imagem Sentinel-2 (DEPOIS)
     B4 (Red) + B8 (NIR)           B4 (Red) + B8 (NIR)
              │                               │
              ▼                               ▼
        NDVI_antes                      NDVI_depois
              │                               │
              └───────────┬───────────────────┘
                          ▼
              ΔNDVI = NDVI_depois − NDVI_antes
                          │
              ΔNDVI < −0.15 → DESMATAMENTO
                          │
                          ▼
              Segmentação (OpenCV: morfologia + contornos)
                          │
                          ▼
              Polígonos com área (ha), severidade, centróide
                          │
                          ▼
              Export GeoJSON → Motor de Fusão / Dashboard
```

## Como executar

```bash
# Instalar dependências
pip install rasterio numpy opencv-python Pillow matplotlib loguru

# Modo demo (sem dados reais)
python detectar_desmatamento.py --demo --visualizar

# Com imagens GeoTIFF reais do Copernicus
python detectar_desmatamento.py --antes antes.tif --depois depois.tif --visualizar
```

## Obter dados Sentinel-2

1. Acesse [Copernicus Data Space](https://dataspace.copernicus.eu/) (gratuito)
2. Selecione a região de interesse (Amazônia)
3. Baixe imagens **Sentinel-2 Level-2A** (reflectância de superfície)
4. Use as bandas **B04** (Red) e **B08** (NIR)
5. Ou use os alertas diretamente do [INPE/DETER](http://terrabrasilis.dpi.inpe.br/)

## Saídas geradas

| Arquivo | Descrição |
|---------|-----------|
| `output/desmatamento_YYYYMMDD_HHMMSS.geojson` | Polígonos detectados em formato GeoJSON |
| `output/relatorio_desmatamento.png` | Relatório visual com 4 subplots (NDVI antes/depois, diff, detecções) |

## Classificação de Severidade

| Severidade | Área |
|-----------|------|
| 🔴 CRÍTICO | > 100 ha |
| 🟠 ALTO | 25–100 ha |
| 🟡 MÉDIO | 5–25 ha |
| 🟢 BAIXO | < 5 ha |
