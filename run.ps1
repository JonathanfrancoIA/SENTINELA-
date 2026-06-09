# ==============================================================
# SENTINELA - Script de Execucao (PowerShell / Windows)
# ==============================================================
# Uso:
#   .\run.ps1 dashboard       -> Inicia o dashboard
#   .\run.ps1 pipeline        -> Roda ingestao de dados
#   .\run.ps1 treinar         -> Treina o modelo de audio (demo)
#   .\run.ps1 visao           -> Roda deteccao de desmatamento (demo)
#   .\run.ps1 fusao           -> Inicia API do motor de fusao
#   .\run.ps1 testes          -> Executa todos os testes
#   .\run.ps1 instalar        -> Instala todas as dependencias
#   .\run.ps1 tudo            -> Pipeline completo (sem dashboard)
# ==============================================================

param(
    [Parameter(Position=0)]
    [ValidateSet("dashboard","pipeline","treinar","visao","fusao","testes","instalar","tudo","help")]
    [string]$Comando = "help"
)

$ErrorActionPreference = "Stop"

# Cores
function Write-Header($msg) {
    Write-Host ""
    Write-Host "  [SENTINELA]" -ForegroundColor Green
    Write-Host "  $msg" -ForegroundColor Cyan
    Write-Host ("-" * 55) -ForegroundColor DarkGreen
}

function Write-OK($msg)   { Write-Host "  [OK] $msg" -ForegroundColor Green }
function Write-Info($msg) { Write-Host "  [i]  $msg" -ForegroundColor Cyan }
function Write-Warn($msg) { Write-Host "  [!]  $msg" -ForegroundColor Yellow }

# Verifica Python
function Test-Python {
    try {
        $ver = python --version 2>&1
        Write-OK "Python: $ver"
    } catch {
        Write-Host "  [ERRO] Python nao encontrado! Instale Python 3.10+ em https://python.org" -ForegroundColor Red
        exit 1
    }
}

switch ($Comando) {

    "instalar" {
        Write-Header "Instalando dependencias..."
        Test-Python
        pip install -r requirements.txt
        Write-OK "Dependencias instaladas com sucesso!"
    }

    "pipeline" {
        Write-Header "Executando pipeline de dados (INPE/DETER)..."
        Test-Python
        Push-Location src\pipeline_dados
        python ingest_deter.py --fonte real --exportar-json
        Pop-Location
        Write-OK "Pipeline concluido! Banco em src/pipeline_dados/data/sentinela.db"
    }

    "dashboard" {
        Write-Header "Iniciando Dashboard (http://localhost:8501)..."
        Test-Python

        # Verifica se o banco existe, se nao, roda pipeline primeiro
        if (-not (Test-Path "src\pipeline_dados\data\sentinela.db")) {
            Write-Warn "Banco nao encontrado - rodando pipeline primeiro..."
            Push-Location src\pipeline_dados
            python ingest_deter.py --fonte real | Out-Null
            Pop-Location
        }

        Write-Info "Abrindo http://localhost:8501 ..."
        Start-Process "http://localhost:8501"

        Push-Location src\dashboard
        streamlit run app.py --server.port 8501
        Pop-Location
    }

    "treinar" {
        Write-Header "Treinando classificador de audio (modo demo)..."
        Test-Python
        Push-Location src\audio_edge
        python treinar_audio.py --demo --epochs 5
        Pop-Location
        Write-OK "Modelo TFLite salvo em src/audio_edge/models/sentinela_audio.tflite"
    }

    "visao" {
        Write-Header "Executando deteccao de desmatamento (modo demo)..."
        Test-Python
        Push-Location src\visao_computacional
        python detectar_desmatamento.py --demo --visualizar --n-manchas 8
        Pop-Location
        Write-OK "Resultados em src/visao_computacional/output/"
    }

    "fusao" {
        Write-Header "Iniciando Motor de Fusao (http://localhost:5050)..."
        Test-Python

        # Verifica banco
        if (-not (Test-Path "src\pipeline_dados\data\sentinela.db")) {
            Write-Warn "Banco nao encontrado - rodando pipeline primeiro..."
            Push-Location src\pipeline_dados
            python ingest_deter.py --fonte real | Out-Null
            Pop-Location
        }

        Write-Info "API disponivel em http://localhost:5050"
        Write-Info "Endpoints: GET / | POST /fusao | GET /alertas | POST /simular"
        Push-Location src\cloud_aws
        python handler.py serve --porta 5050
        Pop-Location
    }

    "testes" {
        Write-Header "Executando suite de testes..."
        Test-Python

        # Instala pytest se necessario
        pip show pytest | Out-Null
        if ($LASTEXITCODE -ne 0) {
            Write-Info "Instalando pytest..."
            pip install pytest pytest-cov -q
        }

        pytest tests/ -v --tb=short --cov=src --cov-report=term-missing
        Write-OK "Testes concluidos!"
    }

    "tudo" {
        Write-Header "Executando pipeline completo..."
        Test-Python

        Write-Info "[1/4] Pipeline de dados..."
        Push-Location src\pipeline_dados
        python ingest_deter.py --fonte real --exportar-json
        Pop-Location

        Write-Info "[2/4] Treinando modelo de audio (demo)..."
        Push-Location src\audio_edge
        python treinar_audio.py --demo --epochs 3
        Pop-Location

        Write-Info "[3/4] Deteccao de desmatamento (demo)..."
        Push-Location src\visao_computacional
        python detectar_desmatamento.py --demo --n-manchas 5
        Pop-Location

        Write-Info "[4/4] Testando motor de fusao..."
        Push-Location src\cloud_aws
        python handler.py testar
        Pop-Location

        Write-OK "Pipeline completo executado com sucesso!"
        Write-Info "Para ver o dashboard: .\run.ps1 dashboard"
    }

    "help" {
        Write-Header "Comandos disponiveis"
        Write-Host ""
        Write-Host "  .\run.ps1 instalar    Instala todas as dependencias Python" -ForegroundColor Cyan
        Write-Host "  .\run.ps1 pipeline    Ingere dados DETER + gera banco SQLite" -ForegroundColor Cyan
        Write-Host "  .\run.ps1 dashboard   Inicia dashboard Streamlit (porta 8501)" -ForegroundColor Cyan
        Write-Host "  .\run.ps1 treinar     Treina classificador de audio (modo demo)" -ForegroundColor Cyan
        Write-Host "  .\run.ps1 visao       Detecta desmatamento em imagens sinteticas" -ForegroundColor Cyan
        Write-Host "  .\run.ps1 fusao       Inicia API do motor de fusao (porta 5050)" -ForegroundColor Cyan
        Write-Host "  .\run.ps1 testes      Executa todos os testes unitarios" -ForegroundColor Cyan
        Write-Host "  .\run.ps1 tudo        Executa pipeline completo (sem dashboard)" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  Inicio rapido:" -ForegroundColor Yellow
        Write-Host "    .\run.ps1 instalar" -ForegroundColor Yellow
        Write-Host "    .\run.ps1 dashboard" -ForegroundColor Yellow
        Write-Host ""
    }
}
