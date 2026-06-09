# 📄 document/ — Documentação da Entrega

Este diretório contém a documentação formal da POC SENTINELA para a FIAP Global Solution 2026.1.

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `README.md` | Este arquivo |
| `gerar_pdf.py` | Gera o PDF de entrega a partir do código/métricas (reprodutível) |
| `SENTINELA-GS-2026.pdf` | **PDF único de entrega (gerado)** — 11 páginas |

## Checklist de Entrega

- [x] Repositório GitHub público com estrutura de pastas
- [x] README raiz completo (integrantes + RM preenchidos)
- [x] README em cada subpasta de `src/`
- [x] Código-fonte comentado em português
- [x] `requirements.txt` atualizado
- [x] PDF com relatório técnico (`SENTINELA-GS-2026.pdf`, via `gerar_pdf.py`)
- [x] Diagrama de arquitetura (`assets/diagrama_arquitetura.png`)
- [x] Fluxograma da solução (`assets/fluxograma.png`, via `gerar_fluxograma.py`)
- [ ] Vídeo demonstrativo (YouTube, não listado) — gravar e colar o link
- [ ] Preencher link do vídeo no PDF (`VIDEO_URL` em `gerar_pdf.py`) e no README raiz
- [ ] Preencher professores (tutor/coordenador) no README raiz

## Como gerar o PDF

Você pode gerar o PDF a partir do README raiz usando:

```bash
# Opção 1: Pandoc (recomendado)
pandoc ../README.md -o SENTINELA-GS-2026.pdf --pdf-engine=weasyprint

# Opção 2: Exportar do GitHub (Print → Save as PDF no navegador)

# Opção 3: grip (preview local do GitHub Markdown)
pip install grip
grip ../README.md
# Abrir http://localhost:6419 e imprimir como PDF
```

## Critérios de Avaliação FIAP GS 2026.1

| Critério | Pontuação | Nossa entrega |
|---------|-----------|--------------|
| Originalidade e criatividade | — | Fusão áudio+satélite (diferencial) |
| Uso de dados espaciais/orbitais | — | Sentinel-2, INPE/DETER, PRODES |
| Machine Learning / IA | — | CNN TFLite (áudio) + NDVI (visão) |
| IoT / Sensores | — | ESP32 + INMP441 + TFLite Micro + MQTT |
| Impacto ambiental | — | Amazônia: detecção precoce de desmatamento |
| Qualidade do código | — | Modular, comentado, funcional |
| Apresentação / Vídeo | — | Dashboard Streamlit + vídeo |
