<#
.SYNOPSIS
    Setup completo do Freky em ambiente de desenvolvimento.

.DESCRIPTION
    1. Verifica pre-requisitos (Git, Docker Desktop)
    2. Clona o repositorio em -ProjectDir (default: C:\Projetos\Projetos\Freky)
    3. Gera .env com credenciais seguras para dev
    4. Cria diretorios de scans e model/weights
    5. Sobe a stack com hot-reload (docker compose dev)
    6. Aguarda SQL Server e cria o banco de dados 'freky'
    7. Aguarda a API ficar saudavel
    8. Exibe todas as URLs

.EXAMPLE
    # Caminho padrao
    .\setup-dev.ps1

    # Caminho customizado
    .\setup-dev.ps1 -ProjectDir "D:\Projetos"

    # Sem clonar (ja tem o repo)
    .\setup-dev.ps1 -SkipClone

.PARAMETER ProjectDir
    Pasta pai onde o repositorio sera clonado. Default: C:\Projetos\Projetos

.PARAMETER Branch
    Branch a usar apos o clone. Default: claude/xray-item-detection-14guG

.PARAMETER SkipClone
    Pula o clone/pull — usa o diretorio atual como raiz do projeto.
#>

param(
    [string]$ProjectDir = "C:\Projetos\Projetos",
    [string]$Branch    = "claude/xray-item-detection-14guG",
    [switch]$SkipClone
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ─── Helpers de output ────────────────────────────────────────────────────────

function Step  { param($m) Write-Host "`n[>>] $m" -ForegroundColor Cyan }
function Ok    { param($m) Write-Host "  [OK]  $m" -ForegroundColor Green }
function Warn  { param($m) Write-Host "  [!]   $m" -ForegroundColor Yellow }
function Fail  { param($m) Write-Host "  [ERR] $m" -ForegroundColor Red; exit 1 }

# ─── 1. Pre-requisitos ────────────────────────────────────────────────────────

Step "Verificando pre-requisitos"

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
    Fail "Git nao encontrado. Instale em: https://git-scm.com/download/win"
}
Ok "git $(git --version)"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Fail "Docker nao encontrado. Instale o Docker Desktop: https://www.docker.com/products/docker-desktop/"
}

try {
    docker info 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { throw }
    Ok "Docker Desktop rodando"
} catch {
    Fail "Docker Desktop nao esta rodando. Inicie-o e execute o script novamente."
}

# ─── 2. Clonar / atualizar repositorio ───────────────────────────────────────

if ($SkipClone) {
    $repoDir = (Get-Location).Path
    Ok "SkipClone ativo — usando diretorio atual: $repoDir"
} else {
    Step "Configurando repositorio em $ProjectDir"

    if (-not (Test-Path $ProjectDir)) {
        New-Item -ItemType Directory -Path $ProjectDir -Force | Out-Null
        Ok "Pasta $ProjectDir criada"
    }

    $repoDir = Join-Path $ProjectDir "Freky"

    if (Test-Path (Join-Path $repoDir ".git")) {
        Warn "Repositorio ja existe — atualizando branch $Branch..."
        git -C $repoDir fetch origin
        git -C $repoDir checkout $Branch
        git -C $repoDir pull origin $Branch
        Ok "Repositorio atualizado"
    } else {
        git clone https://github.com/GiovaneXavier/Freky.git $repoDir
        git -C $repoDir checkout $Branch
        Ok "Repositorio clonado em $repoDir (branch $Branch)"
    }
}

Set-Location $repoDir

# ─── 3. Criar .env ────────────────────────────────────────────────────────────

Step "Configurando .env"

$envFile = Join-Path $repoDir ".env"

if (Test-Path $envFile) {
    Warn ".env ja existe — mantendo o arquivo atual (delete-o para regenerar)."
} else {
    $sqlPass = "FrekyDev@2024"

    # Cada linha sem espacos extras ao redor do '=' para compatibilidade com Docker
    $envContent = @"
# ============================================================
# Freky — Ambiente de Desenvolvimento
# Gerado por setup-dev.ps1 — NAO use estas credenciais em prod
# ============================================================

# Ambiente
FREKY_ENV=dev
DEBUG=true

# ─── Banco de dados (SQL Server no Docker) ──────────────────
MSSQL_SA_PASSWORD=$sqlPass
DATABASE_URL=mssql://sa:$sqlPass@sqlserver:1433/freky?driver=ODBC+Driver+18+for+SQL+Server&TrustServerCertificate=yes

# ─── Redis ──────────────────────────────────────────────────
REDIS_URL=redis://redis:6379/0

# ─── Segurança (valores INSEGUROS para dev) ─────────────────
# Em producao: python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=freky-dev-inseguro-nao-use-em-producao-pelo-amor-de-deus
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

# ─── Usuarios ───────────────────────────────────────────────
# FREKY_ENV=dev aceita senha em texto puro — use bcrypt em producao
FREKY_USERS=[{"username":"admin","password":"admin","role":"admin"},{"username":"operador","password":"operador","role":"operator"}]

# ─── Modelo ONNX ────────────────────────────────────────────
# Deixe em branco para rodar sem modelo (modo mock)
MODEL_PATH=
CONFIDENCE_THRESHOLD=0.60
HIGH_CONFIDENCE_THRESHOLD=0.85

# ─── Diretorios de scan ─────────────────────────────────────
SCAN_INPUT_DIR=/scans/incoming
SCAN_ARCHIVE_DIR=/scans/archive

# ─── Grafana ────────────────────────────────────────────────
GRAFANA_USER=admin
GRAFANA_PASSWORD=admin
"@

    # Salva com LF (Linux) para o Docker nao ter problemas
    $envContent = $envContent -replace "`r`n", "`n"
    [System.IO.File]::WriteAllText($envFile, $envContent, [System.Text.Encoding]::UTF8)
    Ok ".env criado com credenciais padrao de dev"
}

# ─── 4. Diretorios de dados ───────────────────────────────────────────────────

Step "Criando diretorios de dados"

@(
    "scans\incoming",
    "scans\archive",
    "model\weights"
) | ForEach-Object {
    $dir = Join-Path $repoDir $_
    if (-not (Test-Path $dir)) {
        New-Item -ItemType Directory -Path $dir -Force | Out-Null
    }
}
Ok "scans/incoming, scans/archive, model/weights prontos"

# ─── 5. Subir containers (modo dev com hot-reload) ────────────────────────────

Step "Iniciando stack de desenvolvimento (primeira vez pode levar ~5 min)"
Warn "A API tera hot-reload, o Dashboard tera HMR via Vite."

docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d --build

if ($LASTEXITCODE -ne 0) {
    Fail "Falha ao subir os containers. Execute: docker compose logs"
}
Ok "Containers iniciados"

# ─── 6. Aguardar SQL Server ───────────────────────────────────────────────────

Step "Aguardando SQL Server inicializar (pode levar ate 60 s)"

$sqlPass = ""
Get-Content $envFile | Where-Object { $_ -match "^MSSQL_SA_PASSWORD=(.+)$" } | ForEach-Object {
    $sqlPass = $Matches[1]
}

$sqlReady = $false
for ($i = 1; $i -le 20; $i++) {
    Start-Sleep -Seconds 4
    $result = docker compose exec -T sqlserver /opt/mssql-tools18/bin/sqlcmd `
        -S localhost -U sa -P $sqlPass -Q "SELECT 1" -C -b 2>&1
    if ($LASTEXITCODE -eq 0) {
        $sqlReady = $true
        Ok "SQL Server pronto ($($i * 4) s)"
        break
    }
    Write-Host "  aguardando... $($i * 4)s" -ForegroundColor DarkGray
}

if (-not $sqlReady) {
    Warn "SQL Server nao respondeu. Crie o banco manualmente apos ele iniciar:"
    Warn "  docker compose exec sqlserver /opt/mssql-tools18/bin/sqlcmd -S localhost -U sa -P $sqlPass -Q ""CREATE DATABASE freky"" -C"
} else {
    # Cria o banco se ainda nao existir
    $createDb = @"
IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = N'freky')
    CREATE DATABASE freky;
"@
    docker compose exec -T sqlserver /opt/mssql-tools18/bin/sqlcmd `
        -S localhost -U sa -P $sqlPass -C -b -Q $createDb 2>&1 | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Ok "Banco de dados 'freky' criado/verificado"
    } else {
        Warn "Nao foi possivel criar o banco automaticamente — a API tentara criar na inicializacao."
    }
}

# ─── 7. Aguardar API ──────────────────────────────────────────────────────────

Step "Aguardando API ficar saudavel"

$apiReady = $false
for ($i = 1; $i -le 15; $i++) {
    Start-Sleep -Seconds 3
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:8000/health" -TimeoutSec 3 -UseBasicParsing -ErrorAction SilentlyContinue
        if ($r.StatusCode -eq 200) { $apiReady = $true; break }
    } catch {}
    Write-Host "  aguardando... $($i * 3)s" -ForegroundColor DarkGray
}

if ($apiReady) {
    Ok "API respondendo em http://localhost:8000"
} else {
    Warn "API ainda nao respondeu. Veja os logs: docker compose logs api -f"
}

# ─── 8. Resumo final ──────────────────────────────────────────────────────────

$banner = @"

  ╔═══════════════════════════════════════════════════════╗
  ║           Freky esta rodando em modo DEV              ║
  ╠═══════════════════════════════════════════════════════╣
  ║  Dashboard (HMR)  http://localhost:5173               ║
  ║  API + Swagger    http://localhost:8000/docs          ║
  ║  Health ready     http://localhost:8000/health/ready  ║
  ║  Grafana          http://localhost:3001  (admin/admin)║
  ║  Prometheus       http://localhost:9090               ║
  ╠═══════════════════════════════════════════════════════╣
  ║  Login            admin / admin                       ║
  ║                   operador / operador                 ║
  ╠═══════════════════════════════════════════════════════╣
  ║  Parar stack      docker compose down                 ║
  ║  Ver logs API     docker compose logs api -f          ║
  ║  Gerar scans mock make mock-scans                     ║
  ╚═══════════════════════════════════════════════════════╝
"@

Write-Host $banner -ForegroundColor Cyan
