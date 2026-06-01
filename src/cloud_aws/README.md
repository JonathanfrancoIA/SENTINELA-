# ☁️ cloud_aws — Motor de Fusão (Lambda + API Gateway)

Módulo de **fusão** do SENTINELA: cruza alertas da camada de áudio (ESP32) com alertas da camada visual (Sentinel-2/DETER) para gerar alertas de **alta confiança** acionáveis para IBAMA/ICMBio.

## Status

| Componente | Status |
|-----------|--------|
| Lógica de fusão (Haversine + janela temporal) | ✅ Funcional |
| API REST local (Flask) | ✅ Funcional |
| Handler AWS Lambda | 🧪 Pronto para deploy (requer conta AWS) |
| Notificação de órgãos (SNS/SES) | 🧪 Simulado (log no console) |

## Arquitetura

```
                     API Gateway
                         │
              ┌──────────┴──────────┐
              │                     │
         ESP32/MQTT              DETER API
         (evento audio)        (alerta satélite)
              │                     │
              └──────────┬──────────┘
                         ▼
                  AWS Lambda
                  handler(event, context)
                         │
             Fusão: Haversine + janela temporal
                         │
              conf = 0.55×audio + 0.45×visual
              × fator_dist(< 10 km)
              × fator_tempo(< 7 dias)
                         │
              ┌──────────┴──────────┐
              │                     │
         conf ≥ 0.85           conf ≥ 0.65
         CONFIRMADO             SUSPEITO
              │                     │
         Notifica IBAMA         Monitoramento
         (SNS → SES → email)
```

## Como executar

```bash
# Instalar dependências
pip install flask pandas sqlalchemy loguru

# Iniciar API local (porta 5050)
python handler.py serve

# Simular evento de áudio
python handler.py testar

# Relatório de fusões no banco
python handler.py relatorio

# Endpoints da API local
# GET  http://localhost:5050/
# POST http://localhost:5050/fusao   (body: evento JSON)
# GET  http://localhost:5050/alertas
# GET  http://localhost:5050/status
# POST http://localhost:5050/simular
```

## Formato do evento de entrada

```json
{
    "source": "audio",
    "sensor_id": "ESP32-AM-01-01",
    "tipo_evento": "MOTOSSERRA_CONFIRMADO",
    "probabilidade": 0.92,
    "lat": -3.47,
    "lon": -62.22,
    "timestamp_ms": 1748500000000,
    "nivel_alerta": "ALTO"
}
```

## Formato do alerta de saída (fusão)

```json
{
    "fusao_id": "FUSAO-A1B2C3D4",
    "nivel_confianca": 0.87,
    "status": "CONFIRMADO",
    "municipio": "Humaitá",
    "estado": "AM",
    "orgao_notificado": "IBAMA",
    "lat": -7.51,
    "lon": -63.01,
    "distancia_km": 3.2,
    "delta_dias": 2,
    "criado_em": "2026-05-30T12:00:00"
}
```

## Deploy na AWS (produção)

```bash
# Pré-requisitos: AWS CLI + SAM CLI instalados
pip install awscli aws-sam-cli

# Configurar credenciais
aws configure

# Deploy
sam build && sam deploy --guided
```

## Variáveis de ambiente (Lambda)

| Variável | Descrição | Default |
|----------|-----------|---------|
| `DB_CONNECTION_STRING` | String de conexão RDS/Aurora | `sqlite:///sentinela.db` |
| `SNS_TOPIC_ARN` | ARN do tópico SNS para notificações | — |
| `RAIO_FUSAO_KM` | Raio máximo de associação | `10` |
| `JANELA_DIAS` | Janela temporal máxima | `7` |
| `CONF_MINIMA_ALERTA` | Limiar mínimo para alerta | `0.65` |
