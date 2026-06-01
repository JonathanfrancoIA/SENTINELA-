# 📊 simulacao — Simulação de Eficácia do SENTINELA

Demonstra, de forma **reprodutível**, a eficácia das camadas de IA do projeto e gera um **relatório visual** (PNG + PDF) pronto para apresentar à banca.

> ⚠️ É uma **simulação**: os dados são sintéticos e gerados com semente fixa (`--semente 42`), calibrados para refletir as métricas esperadas descritas nos READMEs de cada módulo. Não substitui o treino real com o dataset ESC-50 nem imagens Sentinel-2 reais — serve para **comprovar o conceito** e o comportamento do sistema.

## Como executar

```bash
# Dependências mínimas
pip install numpy matplotlib

# Rodar a simulação (gera os relatórios em ./output)
python simular_eficacia.py

# Opções
python simular_eficacia.py --semente 42 --threshold 0.70 --saida output
```

> `scipy` é opcional — se estiver instalado, acelera a rotulagem de polígonos; senão, o script usa um rotulador próprio em NumPy puro.

## O que a simulação mede

### 👂 Ouvido — Classificador de áudio (motosserra)
Conjunto de teste balanceado (AMEAÇA × NORMAL). O script avalia o modelo no limiar de alerta do projeto (0,70) e calcula:

- **Matriz de confusão** (TP / FN / FP / TN)
- **Acurácia, Precisão, Recall, F1, Especificidade**
- **Curva ROC + AUC**

### 👁️ Olho — Visão computacional (NDVI change detection)
Cena Sentinel-2 sintética (NDVI antes/depois) com manchas de desmatamento plantadas. Aplica `ΔNDVI < -0,15`, segmenta polígonos e mede:

- **Área desmatada detectada (ha)** por severidade (CRÍTICO / ALTO / MÉDIO / BAIXO)
- **IoU espacial** (sobreposição entre detecção e gabarito) — precisão da localização

### 🔗 Fusão — áudio + satélite
Usa a mesma fórmula de `src/cloud_aws/handler.py` (Haversine < 10 km e janela < 7 dias) para mostrar como a fusão **reduz falsos positivos** frente a cada sensor isolado.

## Saídas geradas (em `output/`)

| Arquivo | Descrição |
|---------|-----------|
| `relatorio_eficacia.png` | Relatório visual em 300 dpi (6 painéis) |
| `relatorio_eficacia.pdf` | Mesmo relatório em PDF (para a entrega) |
| `metricas_eficacia.json` | Todas as métricas em JSON |
| `relatorio_eficacia.md` | Resumo textual em Markdown |

## Layout do relatório visual

```
┌────────────────────┬────────────────────┬────────────────────┐
│ Matriz de Confusão │   Curva ROC (AUC)  │ Métricas do modelo │
│      (áudio)       │                    │  (barras + meta)   │
├────────────────────┼────────────────────┼────────────────────┤
│  Detecção NDVI     │ Área por           │ Fusão reduz        │
│  (mapa + IoU)      │ severidade (ha)    │ falsos positivos   │
└────────────────────┴────────────────────┴────────────────────┘
```

## Reprodutibilidade

Com a mesma semente, os números são idênticos a cada execução — importante para a banca poder reproduzir. Mude `--semente` para gerar cenários alternativos.
