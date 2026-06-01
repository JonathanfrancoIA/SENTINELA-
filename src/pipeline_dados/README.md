# 🔄 pipeline_dados — Ingestão de Dados DETER/PRODES + IoT

Módulo de **pipeline de dados** do SENTINELA: ingere alertas do INPE/DETER, normaliza e persiste em SQLite junto com eventos de áudio dos sensores ESP32.

## Status

| Componente | Status |
|-----------|--------|
| Schema do banco SQLite | ✅ Funcional |
| Geração de dados simulados (DETER) | ✅ Funcional |
| Ingestão de dados reais (DETER/TerraBrasilis) | ✅ Funcional (requer internet) |
| Persistência (SQLAlchemy + SQLite) | ✅ Funcional |
| Export para JSON | ✅ Funcional |
| Geração de eventos de áudio simulados | ✅ Funcional |

## Fontes de dados suportadas

| Fonte | URL | Dados |
|-------|-----|-------|
| INPE/DETER-B | [terrabrasilis.dpi.inpe.br](http://terrabrasilis.dpi.inpe.br/downloads/) | Alertas diários de desmatamento |
| INPE/PRODES | [prodes.dpi.inpe.br](http://www.obt.inpe.br/OBT/assuntos/programas/amazonia/prodes) | Dados anuais consolidados |
| Copernicus | [dataspace.copernicus.eu](https://dataspace.copernicus.eu/) | Imagens Sentinel-2 |

## Schema do Banco (SQLite)

```sql
alertas_deter   -- alertas INPE/DETER (satélite)
eventos_audio   -- eventos ESP32 (áudio/MQTT)
alertas_fusao   -- resultado do motor de fusão
sensores        -- cadastro de dispositivos ESP32
```

## Como executar

```bash
# Instalar dependências
pip install pandas sqlalchemy geopandas requests tqdm loguru

# Ingestão com dados simulados (padrão)
python ingest_deter.py

# Tenta baixar DETER real (fallback para simulado)
python ingest_deter.py --fonte real

# Exportar banco para JSON (para dashboard)
python ingest_deter.py --exportar-json

# Ver estatísticas
python ingest_deter.py --stats
```

## Distribuição dos dados simulados

Os dados simulados são baseados na distribuição real do DETER-B:

| Tipo | Frequência simulada |
|------|-------------------|
| Corte Raso | 60% |
| Degradação | 25% |
| Queimada | 10% |
| Mineração | 5% |

Municípios: 15 municípios reais da Amazônia Legal com distribuição espacial realista.

## Fluxo de dados

```
DETER (HTTP/ZIP) ──► parser ──► DataFrame ──► SQLite (alertas_deter)
ESP32 (MQTT)    ──► parser ──► DataFrame ──► SQLite (eventos_audio)
                                                      │
                                                      ▼
                                          cloud_aws/handler.py
                                          (Motor de Fusão)
```
