# Arranca ATLAS (Windows PowerShell). Uso: .\scripts\start.ps1 [-Rebuild]
param([switch]$Rebuild)
$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $PSScriptRoot

# ---------- Backend (Python) ----------
Set-Location "$Root\backend"
$Py = ".venv\Scripts\python.exe"
if (-not (Test-Path $Py)) {
  Write-Host "> Creando entorno Python..."
  if (Get-Command uv -ErrorAction SilentlyContinue) { uv venv -q --python ">=3.11" .venv } else { py -3 -m venv .venv }
}
$depsHash = (Get-FileHash pyproject.toml).Hash
$stamp = ".venv\.atlas-deps"
if (-not (Test-Path $stamp) -or (Get-Content $stamp) -ne $depsHash) {
  Write-Host "> Instalando dependencias del backend..."
  if (Get-Command uv -ErrorAction SilentlyContinue) { uv pip install -q --python .venv -e ".[dev]" } else { & $Py -m pip install -q -e ".[dev]" }
  Set-Content $stamp $depsHash
}
if (-not (Test-Path ".env") -and (Test-Path ".env.example")) { Copy-Item ".env.example" ".env" }

# ---------- Frontend (interfaz) ----------
Set-Location "$Root\frontend"
if (-not (Get-Command npm -ErrorAction SilentlyContinue)) { Write-Host "Falta Node.js: instalalo desde https://nodejs.org (LTS)"; exit 1 }
$lockHash = (Get-FileHash package-lock.json).Hash
$lockStamp = "node_modules\.atlas-deps"
if (-not (Test-Path "node_modules") -or -not (Test-Path $lockStamp) -or (Get-Content $lockStamp) -ne $lockHash) {
  Write-Host "> Instalando dependencias de la interfaz..."
  npm install --no-fund --no-audit
  Set-Content $lockStamp $lockHash
}
$needBuild = $Rebuild -or -not (Test-Path "dist\index.html")
if (-not $needBuild) {
  $built = (Get-Item "dist\index.html").LastWriteTime
  $needBuild = [bool](Get-ChildItem src, index.html, package.json -Recurse -File | Where-Object { $_.LastWriteTime -gt $built } | Select-Object -First 1)
}
if ($needBuild) { Write-Host "> Compilando la interfaz..."; npm run build }

# ---------- Arranque ----------
Set-Location "$Root\backend"
Write-Host "> ATLAS en http://127.0.0.1:8000  (Ctrl+C para detener)"
& $Py -m atlas
