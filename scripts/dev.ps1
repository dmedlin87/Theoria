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

function Test-PortOpen {
  param(
    [string]$TargetHost,
    [int]$Port,
    [int]$TimeoutMilliseconds = 2000
  )

  $client = [System.Net.Sockets.TcpClient]::new()
  try {
    $asyncResult = $client.BeginConnect($TargetHost, $Port, $null, $null)
    if (-not $asyncResult.AsyncWaitHandle.WaitOne($TimeoutMilliseconds)) {
      return $false
    }
    $client.EndConnect($asyncResult)
    return $true
  } catch {
    return $false
  } finally {
    $client.Dispose()
  }
}

function Get-ApiReadinessHost {
  param([string]$BindHost)

  if (-not $BindHost) { return '127.0.0.1' }

  $normalizedHost = $BindHost.Trim()

  $parsedAddress = $null
  if ([System.Net.IPAddress]::TryParse($normalizedHost, [ref]$parsedAddress)) {
    if ($parsedAddress.Equals([System.Net.IPAddress]::Any)) { return '127.0.0.1' }
    if ($parsedAddress.Equals([System.Net.IPAddress]::IPv6Any)) { return '::1' }
    return $normalizedHost
  }

  if ($normalizedHost.StartsWith('[') -and $normalizedHost.EndsWith(']')) {
    $inner = $normalizedHost.TrimStart('[').TrimEnd(']')
    if ([System.Net.IPAddress]::TryParse($inner, [ref]$parsedAddress)) {
      if ($parsedAddress.Equals([System.Net.IPAddress]::IPv6Any)) { return '::1' }
    }
  }

  return $normalizedHost
}

function Stop-ApiJob {
  param($Job)

  if (-not $Job) { return }

  Stop-Job $Job -ErrorAction SilentlyContinue | Out-Null
  $output = Receive-Job $Job -ErrorAction SilentlyContinue
  if ($output) { Write-Host $output }
  Remove-Job $Job -Force -ErrorAction SilentlyContinue | Out-Null
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
$ApiExe = 'uvicorn'
$ApiArgs = @(
  $ApiModule,
  '--reload',
  '--host', $BindHost,
  '--port', $ApiPort
)
Write-Host ("{0} {1}" -f $ApiExe, ($ApiArgs -join ' ')) -ForegroundColor Green

# Start API in background job
$ApiJob = Start-Job -ScriptBlock {
  param($exe, $exeArgs, $wd)
  Set-Location $wd
  & $exe @exeArgs
} -ArgumentList $ApiExe, $ApiArgs, $RepoRoot

$ApiReady = $false
$TimeoutSeconds = 45
$Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
$ReadinessHost = Get-ApiReadinessHost $BindHost
while ($Stopwatch.Elapsed.TotalSeconds -lt $TimeoutSeconds) {
  if ($ApiJob.State -eq 'Failed' -or $ApiJob.State -eq 'Stopped') {
    Write-Host 'API process failed to start.' -ForegroundColor Red
    $jobOutput = Receive-Job $ApiJob -ErrorAction SilentlyContinue
    if ($jobOutput) { Write-Host $jobOutput }
    Stop-ApiJob $ApiJob
    exit 1
  }

  if (Test-PortOpen -TargetHost $ReadinessHost -Port $ApiPort) {
    $ApiReady = $true
    break
  }

  Start-Sleep -Milliseconds 500
}

if (-not $ApiReady) {
  Write-Host "API did not become ready within $TimeoutSeconds seconds." -ForegroundColor Red
  Stop-ApiJob $ApiJob
  exit 1
}

Write-Host "API is listening on ${BindHost}:${ApiPort}" -ForegroundColor Green

if (-not (Test-Path $WebDir)) {
  Write-Host "Web directory not found: $WebDir" -ForegroundColor Red
  Stop-ApiJob $ApiJob
  exit 1
}

Write-Section 'Preparing Web'
Set-Location $WebDir

if (-not (Test-Path (Join-Path $WebDir 'package.json'))) {
  Write-Host 'package.json missing in web directory.' -ForegroundColor Red
  Stop-ApiJob $ApiJob
  exit 1
}

# Ensure Node is installed
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
  Write-Host 'Node.js (node) not found on PATH. Please install Node 18+.' -ForegroundColor Red
  Stop-ApiJob $ApiJob
  exit 1
}

# Install node modules if node_modules missing
if (-not (Test-Path (Join-Path $WebDir 'node_modules'))) {
  Write-Host 'Installing npm dependencies...' -ForegroundColor Yellow
  npm install
}

$env:NEXT_PUBLIC_API_BASE_URL = ('http://{0}:{1}' -f $BindHost, $ApiPort)
$env:API_BASE_URL = $env:NEXT_PUBLIC_API_BASE_URL
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
Stop-ApiJob $ApiJob

