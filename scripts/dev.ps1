<#!
.SYNOPSIS
  Launch Theo Engine API (FastAPI) and Web (Next.js) in development mode.
.DESCRIPTION
  Starts the FastAPI server with live reload (SQLite backend by default) and the Next.js dev server
  with the correct NEXT_PUBLIC_API_BASE_URL. Automatically installs Node dependencies if missing.
.PARAMETER ApiPort
  Port for the FastAPI server (default 8000)
.PARAMETER WebPort
  Port for the Next.js dev server (default 3000)
.PARAMETER BindHost
  Host interface to bind (default 127.0.0.1)
.EXAMPLE
  ./scripts/dev.ps1
.EXAMPLE
  ./scripts/dev.ps1 -ApiPort 8010 -WebPort 3100
#>
param(
  [int]$ApiPort = 8000,
  [int]$WebPort = 3000,
  [string]$BindHost = '127.0.0.1'
)

$ErrorActionPreference = 'Stop'

function Write-Section($msg) {
  Write-Host "`n=== $msg ===" -ForegroundColor Cyan
}

# Resolve repo root (directory containing this script's parent)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RepoRoot = Split-Path -Parent $ScriptDir

$ApiModule = 'theo.services.api.app.main:app'
$WebDir = Join-Path $RepoRoot 'theo/services/web'

if (-not (Test-Path (Join-Path $RepoRoot 'requirements.txt'))) {
  Write-Host 'Could not find requirements.txt at repo root. Aborting.' -ForegroundColor Red
  exit 1
}

# Check venv activation (optional advisory)
if (-not $env:VIRTUAL_ENV) {
  Write-Host 'NOTE: No virtual environment detected; using global python.' -ForegroundColor Yellow
}

Write-Section 'Starting API'
$ApiCmd = "uvicorn $ApiModule --reload --host $BindHost --port $ApiPort"
Write-Host $ApiCmd -ForegroundColor Green

# Start API in background job
$ApiJob = Start-Job -ScriptBlock { param($cmd, $wd) Set-Location $wd; & $cmd } -ArgumentList $ApiCmd, $RepoRoot
Start-Sleep -Seconds 2

if (-not (Test-Path $WebDir)) {
  Write-Host "Web directory not found: $WebDir" -ForegroundColor Red
  Stop-Job $ApiJob | Out-Null
  exit 1
}

Write-Section 'Preparing Web'
Set-Location $WebDir

if (-not (Test-Path (Join-Path $WebDir 'package.json'))) {
  Write-Host 'package.json missing in web directory.' -ForegroundColor Red
  Stop-Job $ApiJob | Out-Null
  exit 1
}

# Ensure Node is installed
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host 'Node.js (node) not found on PATH. Please install Node 18+.' -ForegroundColor Red
  Stop-Job $ApiJob | Out-Null
  exit 1
}

# Install node modules if node_modules missing
if (-not (Test-Path (Join-Path $WebDir 'node_modules'))) {
  Write-Host 'Installing npm dependencies...' -ForegroundColor Yellow
  npm install
}

$env:NEXT_PUBLIC_API_BASE_URL = ('http://{0}:{1}' -f $BindHost, $ApiPort)
Write-Section "Starting Web (NEXT_PUBLIC_API_BASE_URL=$env:NEXT_PUBLIC_API_BASE_URL)"
<#
 Use explicit executable + argument array so PowerShell does not treat the entire
 command line as a single (non-existent) executable name.
 Prefer local next binary if present; otherwise rely on npx.
#>
$LocalNextCmd = Join-Path $WebDir 'node_modules/.bin/next.cmd'
if (-not (Test-Path $LocalNextCmd)) { $LocalNextCmd = Join-Path $WebDir 'node_modules/.bin/next' }

if (Test-Path $LocalNextCmd) {
  $NextExe = $LocalNextCmd
  $NextArgs = @('dev','-p', $WebPort)
} else {
  $NextExe = 'npx'
  $NextArgs = @('next','dev','-p', $WebPort)
}

Write-Host ("{0} {1}" -f $NextExe, ($NextArgs -join ' ')) -ForegroundColor Green

# Start web in foreground so user can stop with Ctrl+C
& $NextExe @NextArgs

Write-Host 'Shutting down API job...' -ForegroundColor Yellow
Stop-Job $ApiJob | Out-Null
Receive-Job $ApiJob | Out-Null
Remove-Job $ApiJob | Out-Null
