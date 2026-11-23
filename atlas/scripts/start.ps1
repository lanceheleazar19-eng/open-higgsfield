# Arranca ATLAS (Windows PowerShell). Uso: .\scripts\start.ps1 [-Rebuild]
param([switch]$Rebuild)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot
Set-Location "$Root\backend"

$Py = ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
  Write-Host "> Creando entorno Python..."
  if (Get-Command uv -ErrorAction SilentlyContinue) { uv venv -q .venv } else { py -3 -m venv .venv }
}
& $Py -c "import atlas" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "> Instalando backend..."
  if (Get-Command uv -ErrorAction SilentlyContinue) { uv pip install -q --python .venv -e ".[dev]" } else { & $Py -m pip install -q -e ".[dev]" }
}
if (-not (Test-Path ".env")) { Copy-Item ".env.example" ".env" }

Set-Location "$Root\frontend"
if (-not (Test-Path "node_modules")) { Write-Host "> Instalando frontend..."; npm install --no-fund --no-audit }
if ($Rebuild -or -not (Test-Path "dist\index.html")) { Write-Host "> Compilando interfaz..."; npm run build }

Set-Location "$Root\backend"
Write-Host "> ATLAS en http://127.0.0.1:8000"
& $Py -m atlas
