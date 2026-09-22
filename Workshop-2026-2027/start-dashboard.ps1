# Demarre le broker MQTT, le backend Flask et le simulateur, puis ouvre le dashboard.
# Usage (depuis Workshop-2026-2027) :
#   powershell -ExecutionPolicy Bypass -File .\start-dashboard.ps1

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Backend = Join-Path $Root "backend"
$Python = Join-Path $Backend "venv\Scripts\python.exe"

Write-Host "== BiOrbite dashboard ==" -ForegroundColor Cyan
Set-Location $Backend

if (-not (Test-Path ".env")) {
  Copy-Item ".env.example" ".env"
}

if (-not (Test-Path $Python)) {
  Write-Host "Creation du venv..."
  python -m venv venv
}

& $Python -c "import flask, paho.mqtt, dotenv, amqtt" 2>$null
if ($LASTEXITCODE -ne 0) {
  Write-Host "Installation des dependances..."
  & $Python -m pip install -r requirements.txt
}

function Test-PortOpen([int]$Port) {
  try {
    $c = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue
    return [bool]$c
  } catch {
    return $false
  }
}

if (Test-PortOpen 1883) {
  Write-Host "Port 1883 deja utilise — broker existant conserve."
} else {
  Write-Host "Demarrage du broker MQTT..."
  Start-Process -FilePath $Python -ArgumentList "run_broker.py" -WorkingDirectory $Backend -WindowStyle Minimized
  Start-Sleep -Seconds 2
}

if (Test-PortOpen 5000) {
  Write-Host "Port 5000 deja utilise — backend existant conserve."
} else {
  Write-Host "Demarrage du backend sur http://127.0.0.1:5000 ..."
  Start-Process -FilePath $Python -ArgumentList "app.py" -WorkingDirectory $Backend -WindowStyle Minimized
  Start-Sleep -Seconds 2
}

Write-Host "Demarrage du simulateur de capteurs..."
Start-Process -FilePath $Python -ArgumentList "simulator.py" -WorkingDirectory $Backend -WindowStyle Minimized
Start-Sleep -Seconds 1

Start-Process "http://127.0.0.1:5000"
Write-Host ""
Write-Host "Dashboard : http://127.0.0.1:5000" -ForegroundColor Green
Write-Host "Pour arreter : ferme les fenetres Python minimisees dans la barre des taches."
