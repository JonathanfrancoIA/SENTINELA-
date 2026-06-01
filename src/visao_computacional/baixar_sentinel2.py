#!/usr/bin/env python3
"""
SENTINELA — Download REAL de imagens Sentinel-2 (Copernicus Data Space)
=======================================================================
Baixa cenas Sentinel-2 L2A reais via API do Copernicus Data Space
Ecosystem (CDSE / Sentinel Hub Process API), recortadas para uma área
(bbox) e uma data, já com as bandas B04 (Red) e B08 (NIR) que o módulo
``detectar_desmatamento.py`` usa para calcular o NDVI.

Autenticação: OAuth2 *client credentials* (sem usuário/senha interativos).
É necessário ter uma conta gratuita no Copernicus Data Space e gerar um
par Client ID / Client Secret em:
    https://shapps.dataspace.copernicus.eu/dashboard/#/account/settings

Configure as credenciais no arquivo .env (ver .env.example):
    SH_CLIENT_ID=...
    SH_CLIENT_SECRET=...

Uso (linha de comando):
    python baixar_sentinel2.py \
        --bbox -62.30 -3.55 -62.10 -3.40 \
        --data 2026-05-20 \
        --saida data/cena_depois.tiff

Uso (importado):
    from baixar_sentinel2 import baixar_cena
    caminho = baixar_cena(bbox=(-62.30,-3.55,-62.10,-3.40),
                          data="2026-05-20", saida="cena.tiff")

Dependências:
    pip install requests python-dotenv
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Tuple

from loguru import logger

# ─────────────────────────────────────────────────────────────
# Endpoints oficiais do Copernicus Data Space Ecosystem (CDSE)
# ─────────────────────────────────────────────────────────────
CDSE_TOKEN_URL = (
    "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/"
    "protocol/openid-connect/token"
)
CDSE_PROCESS_URL = "https://sh.dataspace.copernicus.eu/api/v1/process"

# Evalscript v3 — devolve B04 (Red) e B08 (NIR) como GeoTIFF float32.
# É exatamente o que detectar_desmatamento.calcular_ndvi() espera:
#   banda 0 = Red (B4)   |   banda 1 = NIR (B8)
EVALSCRIPT = """//VERSION=3
function setup() {
  return {
    input: [{ bands: ["B04", "B08"] }],
    output: { bands: 2, sampleType: "FLOAT32" }
  };
}
function evaluatePixel(sample) {
  return [sample.B04, sample.B08];
}
"""


# ─────────────────────────────────────────────────────────────
# Credenciais
# ─────────────────────────────────────────────────────────────
def _carregar_credenciais() -> Tuple[Optional[str], Optional[str]]:
    """Lê SH_CLIENT_ID / SH_CLIENT_SECRET do ambiente (ou do .env)."""
    # Tenta carregar um .env se python-dotenv estiver disponível (opcional).
    try:
        from dotenv import load_dotenv
        # procura .env na raiz do projeto (3 níveis acima deste arquivo)
        for candidato in (Path.cwd() / ".env",
                          Path(__file__).resolve().parents[2] / ".env"):
            if candidato.exists():
                load_dotenv(candidato)
                break
    except ImportError:
        pass

    cid = os.getenv("SH_CLIENT_ID")
    csecret = os.getenv("SH_CLIENT_SECRET")
    return cid, csecret


def obter_token(client_id: str, client_secret: str, timeout: int = 30) -> str:
    """Obtém um access_token OAuth2 (client credentials) do CDSE."""
    import requests
    resp = requests.post(
        CDSE_TOKEN_URL,
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=timeout,
    )
    resp.raise_for_status()
    token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("CDSE não retornou access_token")
    logger.success("Token CDSE obtido com sucesso")
    return token


# ─────────────────────────────────────────────────────────────
# Download da cena
# ─────────────────────────────────────────────────────────────
def baixar_cena(bbox: Tuple[float, float, float, float],
                data: str,
                saida: str,
                largura: int = 512,
                altura: int = 512,
                dias_tolerancia: int = 10,
                nuvens_max: int = 40,
                client_id: Optional[str] = None,
                client_secret: Optional[str] = None) -> Optional[str]:
    """
    Baixa uma cena Sentinel-2 L2A (bandas B04+B08) recortada para ``bbox`` e
    salva como GeoTIFF em ``saida``.

    Args:
        bbox: (min_lon, min_lat, max_lon, max_lat) em EPSG:4326.
        data: data alvo "YYYY-MM-DD"; busca a melhor cena numa janela de
              ±``dias_tolerancia`` dias (Sentinel-2 não passa todo dia).
        saida: caminho do GeoTIFF de saída.
        largura/altura: resolução de saída em pixels.
        nuvens_max: cobertura máxima de nuvens aceita (%).
        client_id/client_secret: se None, lê de SH_CLIENT_ID / SH_CLIENT_SECRET.

    Retorna o caminho salvo, ou None em caso de falha (rede/credencial/sem cena).
    """
    try:
        import requests
    except ImportError:
        logger.error("Pacote 'requests' ausente — pip install requests")
        return None

    if client_id is None or client_secret is None:
        client_id, client_secret = _carregar_credenciais()

    if not client_id or not client_secret:
        logger.error(
            "Credenciais ausentes. Defina SH_CLIENT_ID e SH_CLIENT_SECRET no .env "
            "(crie em https://shapps.dataspace.copernicus.eu/dashboard/). "
            "Sem credenciais não é possível baixar imagem real — use --demo no "
            "detectar_desmatamento.py para o modo simulado."
        )
        return None

    # Janela temporal em torno da data alvo
    try:
        alvo = datetime.strptime(data, "%Y-%m-%d")
    except ValueError:
        logger.error("Data inválida: {} (use YYYY-MM-DD)", data)
        return None
    inicio = (alvo - timedelta(days=dias_tolerancia)).strftime("%Y-%m-%dT00:00:00Z")
    fim = (alvo + timedelta(days=dias_tolerancia)).strftime("%Y-%m-%dT23:59:59Z")

    try:
        token = obter_token(client_id, client_secret)
    except Exception as e:
        logger.error("Falha ao autenticar no CDSE: {}", e)
        return None

    payload = {
        "input": {
            "bounds": {
                "bbox": list(bbox),
                "properties": {
                    "crs": "http://www.opengis.net/def/crs/EPSG/0/4326"
                },
            },
            "data": [{
                "type": "sentinel-2-l2a",
                "dataFilter": {
                    "timeRange": {"from": inicio, "to": fim},
                    "maxCloudCoverage": nuvens_max,
                    "mosaickingOrder": "leastCC",  # cena menos nublada
                },
            }],
        },
        "output": {
            "width": largura,
            "height": altura,
            "responses": [{
                "identifier": "default",
                "format": {"type": "image/tiff"},
            }],
        },
        "evalscript": EVALSCRIPT,
    }

    try:
        logger.info("Solicitando cena Sentinel-2 (bbox={}, data≈{}) …", bbox, data)
        resp = requests.post(
            CDSE_PROCESS_URL,
            json=payload,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "image/tiff",
            },
            timeout=120,
        )
        resp.raise_for_status()
    except Exception as e:
        # Tenta extrair mensagem de erro útil do corpo da resposta
        detalhe = ""
        try:
            detalhe = resp.text[:300]  # type: ignore[name-defined]
        except Exception:
            pass
        logger.error("Falha na requisição Process API: {} {}", e, detalhe)
        return None

    conteudo = resp.content
    if not conteudo or len(conteudo) < 1000:
        logger.warning(
            "Resposta vazia/pequena ({} bytes) — provavelmente não há cena "
            "Sentinel-2 sem nuvens nessa janela. Tente outra data ou aumente "
            "--dias-tolerancia / --nuvens-max.", len(conteudo) if conteudo else 0
        )
        return None

    saida_path = Path(saida)
    saida_path.parent.mkdir(parents=True, exist_ok=True)
    saida_path.write_bytes(conteudo)
    logger.success("Cena Sentinel-2 salva: {} ({:.1f} KB)",
                   saida_path, len(conteudo) / 1024)
    return str(saida_path)


# ─────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description="SENTINELA — Baixa cena Sentinel-2 real (Copernicus Data Space)"
    )
    parser.add_argument("--bbox", type=float, nargs=4, required=True,
                        metavar=("MIN_LON", "MIN_LAT", "MAX_LON", "MAX_LAT"),
                        help="Área em EPSG:4326")
    parser.add_argument("--data", type=str, required=True,
                        help="Data alvo YYYY-MM-DD (busca ±tolerância)")
    parser.add_argument("--saida", type=str, default="data/cena_sentinel2.tiff",
                        help="Caminho do GeoTIFF de saída")
    parser.add_argument("--largura", type=int, default=512)
    parser.add_argument("--altura", type=int, default=512)
    parser.add_argument("--dias-tolerancia", type=int, default=10)
    parser.add_argument("--nuvens-max", type=int, default=40)
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("  SENTINELA — Download Sentinel-2 (Copernicus Data Space)")
    logger.info("=" * 60)

    caminho = baixar_cena(
        bbox=tuple(args.bbox),
        data=args.data,
        saida=args.saida,
        largura=args.largura,
        altura=args.altura,
        dias_tolerancia=args.dias_tolerancia,
        nuvens_max=args.nuvens_max,
    )

    if caminho:
        logger.success("OK — cena disponível em {}", caminho)
        sys.exit(0)
    else:
        logger.error("Não foi possível baixar a cena (ver mensagens acima).")
        sys.exit(1)


if __name__ == "__main__":
    main()
