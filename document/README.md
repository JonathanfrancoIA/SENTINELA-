# 📄 document/ — Documentação da Entrega

Este diretório contém a documentação formal da POC SENTINELA para a FIAP Global Solution 2026.1.

## Arquivos

| Arquivo | Descrição |
|---------|-----------|
| `README.md` | Este arquivo |
| `SENTINELA-GS-2026.pdf` | PDF único de entrega *(a ser gerado)* |

## Checklist de Entrega

- [x] Repositório GitHub público com estrutura de pastas
- [x] README raiz completo
- [x] README em cada subpasta de `src/`
- [x] Código-fonte comentado em português
- [x] `requirements.txt` atualizado
- [ ] PDF com relatório técnico (gerar com base neste README)
- [ ] Vídeo demonstrativo (YouTube, não listado)
- [ ] Diagrama de arquitetura (adicionar em `assets/`)

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
