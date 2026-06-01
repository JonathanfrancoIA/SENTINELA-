# 📦 SENTINELA — Checklist de Entrega

**O olho e o ouvido da floresta** · FIAP Global Solution 2026.1
Status consolidado do projeto em 31/05/2026.

---

## 1. O que está PRONTO (código completo)

| Camada | Módulo | Estado |
|--------|--------|--------|
| 👂 Ouvido (áudio) | `src/audio_edge/sentinela_esp32/` | Firmware ESP32 completo; inferência em modo proxy (RMS), pronto para o modelo `.tflite` real |
| 👁️ Olho (satélite) | `src/visao_computacional/detectar_desmatamento.py` | Pipeline NDVI completo (demo + GeoTIFF local + **download real**) |
| 🛰️ Download Sentinel-2 | `src/visao_computacional/baixar_sentinel2.py` | **NOVO** — baixa cenas reais do Copernicus Data Space (requer credenciais) |
| 🌳 DETER/INPE | `src/pipeline_dados/ingest_deter.py` | **Conexão REAL** via WFS TerraBrasilis (sem credenciais) |
| 🔗 Fusão | `src/cloud_aws/handler.py` | Motor de fusão áudio+satélite (Haversine <10 km, janela <7 dias) |
| 📊 Dashboard | `src/dashboard/` | Streamlit + Folium + Plotly (lê o banco SQLite) |
| 🧪 Simulação | `simulacao/simular_eficacia.py` | Relatório de eficácia reprodutível (PNG/PDF/JSON/MD) |

---

## 2. O que está CONECTADO em tempo real

- **DETER/INPE (REAL):** `python ingest_deter.py --fonte real` baixa os alertas
  oficiais de desmatamento via WFS público do TerraBrasilis. O INPE publica os
  dados **diariamente**; o sistema os busca **sob demanda** (não fica puxando
  sozinho). Há fallback automático para dados simulados se a rede falhar.

- **Sentinel-2 (REAL, mediante credenciais):** o código de download está pronto.
  Assim que você adicionar `SH_CLIENT_ID`/`SH_CLIENT_SECRET` no `.env`, o comando
  `--baixar` puxa cenas reais do Copernicus. **Sem as credenciais, roda em modo
  demo (NDVI sintético).**

> ⚠️ Honestidade técnica: nada é "streaming" segundo a segundo. As duas fontes
> são *pull* sob demanda. Para automatizar, agende os comandos (cron/Agendador
> de Tarefas do Windows) — posso configurar isso se você quiser.

---

## 3. O que SÓ VOCÊ pode concluir

Estes três itens dependem de conta/hardware/dados pessoais e não posso fazer:

### 3.1 Credenciais Copernicus (para Sentinel-2 real)
1. Crie conta gratuita: https://dataspace.copernicus.eu/
2. Gere Client ID/Secret: https://shapps.dataspace.copernicus.eu/dashboard/#/account/settings
3. Cole em `.env`:
   ```
   SH_CLIENT_ID=...
   SH_CLIENT_SECRET=...
   ```
4. Teste:
   ```bash
   cd src/visao_computacional
   python detectar_desmatamento.py --baixar \
       --bbox -62.30 -3.55 -62.10 -3.40 \
       --data-antes 2026-04-15 --data-depois 2026-05-20 \
       --visualizar
   ```

### 3.2 Modelo de IA do ESP32 (para inferência real)
- Treine a CNN com o dataset ESC-50 (classe "chainsaw") + ruídos de floresta.
- Exporte como TFLite INT8 e gere o header `sentinela_audio_model.h`.
- No firmware, descomente os trechos de carregamento/inferência reais em
  `inicializar_modelo()` e `inferir()`.

### 3.3 Dados administrativos (README)
Preencher os placeholders em `README.md`:
- Nome do grupo, integrantes e RMs
- Professores orientadores
- Link do vídeo no YouTube
- Datas de release

---

## 4. Como rodar o projeto inteiro (ordem)

```bash
# 1. Dependências
pip install pandas sqlalchemy requests loguru numpy matplotlib streamlit folium plotly
pip install rasterio python-dotenv   # para Sentinel-2 real

# 2. Ingestão de dados (REAL do DETER + eventos)
cd src/pipeline_dados
python ingest_deter.py --fonte real

# 3. (Opcional) Baixar e analisar Sentinel-2 real
cd ../visao_computacional
python detectar_desmatamento.py --baixar --bbox -62.30 -3.55 -62.10 -3.40 \
    --data-antes 2026-04-15 --data-depois 2026-05-20 --visualizar

# 4. Dashboard
cd ../..
streamlit run src/dashboard/app.py     # abre em http://localhost:8501
#   → aperte R na página para recarregar após nova ingestão

# 5. Simulação de eficácia (para a banca)
cd simulacao
python simular_eficacia.py
```

---

## 5. Resumo honesto do "100% funcional"

| Item | Conectado em tempo real? | Observação |
|------|--------------------------|------------|
| DETER/INPE | ✅ Sim (sob demanda, diário) | Funciona já, sem credenciais |
| Sentinel-2 | ⚙️ Pronto, falta credencial | Código completo; cole Client ID/Secret |
| ESP32 áudio | ❌ Modo simulação | Precisa do modelo treinado + hardware |
| Dashboard/Fusão | ✅ Funcional | Lê o que estiver no banco |

O **software está pronto**. O que falta para "100% real" são acessos externos
(conta Copernicus, modelo/hardware ESP32) e os dados administrativos — tudo
listado acima com o passo a passo.
