#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Intelligent all-in-one runner for Theoria (API + Web)

.DESCRIPTION
    Automatically detects environment, checks prerequisites, and starts services.
    Handles multiple scenarios: full stack, API only, web only, or development mode.

.PARAMETER Mode
    Run mode: 'full' (default), 'api', 'web', 'dev', 'test', 'check'
    - full: Start both API and Web services
    - api: Start only FastAPI backend
    - web: Start only Next.js frontend
    - dev: Start with hot reload and verbose logging
    - test: Run all test suites
    - check: Validate environment and dependencies

.PARAMETER Port
    API port (default: 8000)

.PARAMETER WebPort
    Web port (default: 3001)

.PARAMETER SkipChecks
    Skip prerequisite checks (faster startup, use with caution)

.PARAMETER Verbose
    Enable verbose logging

.EXAMPLE
    .\run.ps1
    # Starts full stack (API + Web)

.EXAMPLE
    .\run.ps1 -Mode api
    # Starts only the API backend

.EXAMPLE
    .\run.ps1 -Mode check
    # Validates environment without starting services

.EXAMPLE
    .\run.ps1 -Mode dev -Verbose
    # Development mode with detailed logging
#>

[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('full', 'api', 'web', 'dev', 'test', 'check')]
    [string]$Mode = 'full',

    [Parameter()]
    [int]$Port = 8000,

    [Parameter()]
    [int]$WebPort = 3001,

    [Parameter()]
    [switch]$SkipChecks,

    [Parameter()]
    [switch]$Verbose
)

# ============================================================================
# CONFIGURATION
# ============================================================================

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$Script:ProjectRoot = Split-Path -Parent $PSScriptRoot
$Script:ApiPath = Join-Path $ProjectRoot "theo"
$Script:WebPath = Join-Path $ProjectRoot "theo\services\web"
$Script:VenvPath = Join-Path $ProjectRoot ".venv"
$Script:EnvFile = Join-Path $ProjectRoot ".env"
$Script:WebEnvFile = Join-Path $WebPath ".env.local"

$Script:Colors = @{
    Success = 'Green'
    Info    = 'Cyan'
    Warning = 'Yellow'
    Error   = 'Red'
    Header  = 'Magenta'
}

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

function Write-Header {
    param([string]$Message)
    Write-Host "`n$('=' * 80)" -ForegroundColor $Script:Colors.Header
    Write-Host "  $Message" -ForegroundColor $Script:Colors.Header
    Write-Host "$('=' * 80)`n" -ForegroundColor $Script:Colors.Header
}

function Write-Step {
    param([string]$Message)
    Write-Host "▶ $Message" -ForegroundColor $Script:Colors.Info
}

function Write-Success {
    param([string]$Message)
    Write-Host "✓ $Message" -ForegroundColor $Script:Colors.Success
}

function Write-Warn {
    param([string]$Message)
    Write-Host "⚠ $Message" -ForegroundColor $Script:Colors.Warning
}

function Write-Fail {
    param([string]$Message)
    Write-Host "✗ $Message" -ForegroundColor $Script:Colors.Error
}

function Test-CommandExists {
    param([string]$Command)
    $null -ne (Get-Command $Command -ErrorAction SilentlyContinue)
}

function Test-PortInUse {
    param([int]$Port)
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    return $null -ne $connections
}

function Stop-ServiceOnPort {
    param([int]$Port)
    
    $connections = Get-NetTCPConnection -LocalPort $Port -ErrorAction SilentlyContinue
    if ($connections) {
        Write-Step "Stopping existing service on port $Port..."
        foreach ($conn in $connections) {
            try {
                Stop-Process -Id $conn.OwningProcess -Force -ErrorAction SilentlyContinue
                Write-Success "Stopped process $($conn.OwningProcess)"
            } catch {
                Write-Warn "Could not stop process $($conn.OwningProcess)"
            }
        }
        Start-Sleep -Seconds 2
    }
}

function Get-PythonExecutable {
    $pythonCandidates = @(
        (Join-Path $Script:VenvPath "Scripts\python.exe"),
        "python",
        "python3"
    )
    
    foreach ($candidate in $pythonCandidates) {
        if (Test-Path $candidate -ErrorAction SilentlyContinue) {
            return $candidate
        }
        if (Test-CommandExists $candidate) {
            return $candidate
        }
    }
    
    return $null
}

function Initialize-VirtualEnvironment {
    Write-Step "Checking Python virtual environment..."
    
    if (-not (Test-Path $Script:VenvPath)) {
        Write-Step "Creating virtual environment..."
        $python = Get-PythonExecutable
        if (-not $python) {
            throw "Python not found. Please install Python 3.11+ and try again."
        }
        
        & $python -m venv $Script:VenvPath
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to create virtual environment"
        }
        Write-Success "Virtual environment created"
    }
    
    $venvPython = Join-Path $Script:VenvPath "Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        throw "Virtual environment Python not found at: $venvPython"
    }
    
    Write-Success "Virtual environment ready"
    return $venvPython
}

function Install-PythonDependencies {
    param([string]$PythonExe)
    
    Write-Step "Checking Python dependencies..."
    
    $requirementsFile = Join-Path $Script:ProjectRoot "requirements.txt"
    if (-not (Test-Path $requirementsFile)) {
        Write-Warn "requirements.txt not found, skipping Python dependencies"
        return
    }
    
    # Check if dependencies are already installed
    $pipList = & $PythonExe -m pip list --format=json 2>&1 | ConvertFrom-Json
    $installedPackages = $pipList.name
    
    $requiresInstall = $false
    Get-Content $requirementsFile | ForEach-Object {
        $line = $_.Trim()
        if ($line -and -not $line.StartsWith('#')) {
            $packageName = ($line -split '[>=<]')[0].Trim()
            if ($packageName -notin $installedPackages) {
                $requiresInstall = $true
            }
        }
    }
    
    if ($requiresInstall) {
        Write-Step "Installing Python dependencies..."
        & $PythonExe -m pip install -q --upgrade pip
        & $PythonExe -m pip install -q -r $requirementsFile
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install Python dependencies"
        }
        Write-Success "Python dependencies installed"
    } else {
        Write-Success "Python dependencies up to date"
    }
}

function Install-NodeDependencies {
    Write-Step "Checking Node.js dependencies..."
    
    $nodeModules = Join-Path $Script:WebPath "node_modules"
    $packageLock = Join-Path $Script:WebPath "package-lock.json"
    
    if (-not (Test-Path $nodeModules) -or 
        (Test-Path $packageLock) -and 
        ((Get-Item $packageLock).LastWriteTime -gt (Get-Item $nodeModules).LastWriteTime)) {
        
        Write-Step "Installing Node.js dependencies..."
        Push-Location $Script:WebPath
        try {
            npm install --silent
            if ($LASTEXITCODE -ne 0) {
                throw "Failed to install Node.js dependencies"
            }
            Write-Success "Node.js dependencies installed"
        } finally {
            Pop-Location
        }
    } else {
        Write-Success "Node.js dependencies up to date"
    }
}

function Initialize-EnvironmentFiles {
    Write-Step "Checking environment configuration..."
    
    # Main .env file
    if (-not (Test-Path $Script:EnvFile)) {
        $envExample = Join-Path $Script:ProjectRoot ".env.example"
        if (Test-Path $envExample) {
            Write-Step "Creating .env from .env.example..."
            Copy-Item $envExample $Script:EnvFile
            Write-Success "Created .env file"
        } else {
            Write-Warn ".env.example not found, creating minimal .env"
            @"
# Theoria Configuration
database_url=sqlite:///./theo.db
storage_root=./storage
redis_url=redis://localhost:6379/0
THEO_AUTH_ALLOW_ANONYMOUS=1
embedding_model=BAAI/bge-m3
embedding_dim=1024
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$Port
API_BASE_URL=http://127.0.0.1:$Port
"@ | Out-File -FilePath $Script:EnvFile -Encoding UTF8
            Write-Success "Created minimal .env file"
        }
    } else {
        Write-Success "Environment file exists"
    }
    
    # Web .env.local file
    if (-not (Test-Path $Script:WebEnvFile)) {
        Write-Step "Creating web/.env.local..."
        @"
# Theoria Web - Local Development
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:$Port
API_BASE_URL=http://127.0.0.1:$Port
"@ | Out-File -FilePath $Script:WebEnvFile -Encoding UTF8
        Write-Success "Created web/.env.local"
    } else {
        Write-Success "Web environment file exists"
    }
}

function Test-Prerequisites {
    Write-Header "Checking Prerequisites"
    
    $issues = @()
    
    # Check Python
    Write-Step "Checking Python..."
    $python = Get-PythonExecutable
    if ($python) {
        $version = & $python --version 2>&1
        Write-Success "Python found: $version"
    } else {
        $issues += "Python 3.11+ not found"
        Write-Fail "Python not found"
    }
    
    # Check Node.js
    Write-Step "Checking Node.js..."
    if (Test-CommandExists 'node') {
        $version = node --version
        Write-Success "Node.js found: $version"
    } else {
        $issues += "Node.js not found"
        Write-Fail "Node.js not found"
    }
    
    # Check npm
    Write-Step "Checking npm..."
    if (Test-CommandExists 'npm') {
        $version = npm --version
        Write-Success "npm found: v$version"
    } else {
        $issues += "npm not found"
        Write-Fail "npm not found"
    }
    
    # Check ports
    Write-Step "Checking port availability..."
    if (Test-PortInUse $Port) {
        Write-Warn "Port $Port is in use (will attempt to stop existing service)"
    } else {
        Write-Success "Port $Port is available"
    }
    
    if (Test-PortInUse $WebPort) {
        Write-Warn "Port $WebPort is in use (will attempt to stop existing service)"
    } else {
        Write-Success "Port $WebPort is available"
    }
    
    if ($issues.Count -gt 0) {
        Write-Host ""
        Write-Fail "Prerequisites check failed:"
        $issues | ForEach-Object { Write-Host "  - $_" -ForegroundColor Red }
        throw "Please install missing prerequisites"
    }
    
    Write-Success "All prerequisites satisfied"
}

function Start-ApiService {
    Write-Header "Starting API Service"
    
    # Stop any existing service on API port
    if (Test-PortInUse $Port) {
        Stop-ServiceOnPort $Port
    }
    
    Write-Step "Initializing Python environment..."
    $python = Initialize-VirtualEnvironment
    
    if (-not $SkipChecks) {
        Install-PythonDependencies $python
    }
    
    Write-Step "Starting FastAPI server on port $Port..."
    
    $uvicornArgs = @(
        '-m', 'uvicorn',
        'theo.services.api.main:app',
        '--host', '127.0.0.1',
        '--port', $Port,
        '--reload'
    )
    
    if ($Verbose) {
        $uvicornArgs += '--log-level', 'debug'
    }
    
    Push-Location $Script:ProjectRoot
    try {
        $apiJob = Start-Job -ScriptBlock {
            param($Python, $Args, $ProjectRoot)
            Set-Location $ProjectRoot
            & $Python @Args
        } -ArgumentList $python, $uvicornArgs, $Script:ProjectRoot
        
        # Wait for API to be ready
        Write-Step "Waiting for API to start..."
        $maxAttempts = 30
        $attempt = 0
        $apiReady = $false
        
        while ($attempt -lt $maxAttempts -and -not $apiReady) {
            Start-Sleep -Seconds 1
            $attempt++
            
            try {
                $response = Invoke-WebRequest -Uri "http://127.0.0.1:$Port/health" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
                if ($response.StatusCode -eq 200) {
                    $apiReady = $true
                }
            } catch {
                # Keep waiting
            }
            
            # Check if job failed
            if ($apiJob.State -eq 'Failed' -or $apiJob.State -eq 'Stopped') {
                $jobOutput = Receive-Job -Job $apiJob
                throw "API service failed to start: $jobOutput"
            }
        }
        
        if ($apiReady) {
            Write-Success "API service started successfully"
            Write-Host "  → API:    http://127.0.0.1:$Port" -ForegroundColor Cyan
            Write-Host "  → Docs:   http://127.0.0.1:$Port/docs" -ForegroundColor Cyan
            Write-Host "  → Health: http://127.0.0.1:$Port/health" -ForegroundColor Cyan
            return $apiJob
        } else {
            throw "API service did not respond within 30 seconds"
        }
    } finally {
        Pop-Location
    }
}

function Start-WebService {
    Write-Header "Starting Web Service"
    
    # Stop any existing service on web port
    if (Test-PortInUse $WebPort) {
        Stop-ServiceOnPort $WebPort
    }
    
    if (-not $SkipChecks) {
        Install-NodeDependencies
    }
    
    Write-Step "Starting Next.js server on port $WebPort..."
    
    Push-Location $Script:WebPath
    try {
        $env:PORT = $WebPort
        $webJob = Start-Job -ScriptBlock {
            param($WebPath, $Port)
            Set-Location $WebPath
            $env:PORT = $Port
            npm run dev
        } -ArgumentList $Script:WebPath, $WebPort
        
        # Wait for web service to be ready
        Write-Step "Waiting for web service to start..."
        $maxAttempts = 30
        $attempt = 0
        $webReady = $false
        
        while ($attempt -lt $maxAttempts -and -not $webReady) {
            Start-Sleep -Seconds 1
            $attempt++
            
            try {
                $response = Invoke-WebRequest -Uri "http://127.0.0.1:$WebPort" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
                if ($response.StatusCode -eq 200 -or $response.StatusCode -eq 404) {
                    $webReady = $true
                }
            } catch {
                # Keep waiting
            }
            
            # Check if job failed
            if ($webJob.State -eq 'Failed' -or $webJob.State -eq 'Stopped') {
                $jobOutput = Receive-Job -Job $webJob
                throw "Web service failed to start: $jobOutput"
            }
        }
        
        if ($webReady) {
            Write-Success "Web service started successfully"
            Write-Host "  → Web:  http://127.0.0.1:$WebPort" -ForegroundColor Cyan
            Write-Host "  → Chat: http://127.0.0.1:$WebPort/chat" -ForegroundColor Cyan
            return $webJob
        } else {
            throw "Web service did not respond within 30 seconds"
        }
    } finally {
        Pop-Location
    }
}

function Start-TestSuite {
    Write-Header "Running Test Suite"
    
    # Python tests
    Write-Step "Running Python tests..."
    $python = Initialize-VirtualEnvironment
    Push-Location $Script:ProjectRoot
    try {
        & $python -m pytest tests/ -v
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Python tests passed"
        } else {
            Write-Fail "Python tests failed"
        }
    } finally {
        Pop-Location
    }
    
    # Node.js tests
    Write-Step "Running Node.js tests..."
    Push-Location $Script:WebPath
    try {
        npm test
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Node.js tests passed"
        } else {
            Write-Fail "Node.js tests failed"
        }
    } finally {
        Pop-Location
    }
    
    # E2E tests (if API and Web are running)
    if ((Test-PortInUse $Port) -and (Test-PortInUse $WebPort)) {
        Write-Step "Running E2E tests..."
        Push-Location $Script:WebPath
        try {
            npm run test:e2e
            if ($LASTEXITCODE -eq 0) {
                Write-Success "E2E tests passed"
            } else {
                Write-Fail "E2E tests failed"
            }
        } finally {
            Pop-Location
        }
    }
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

function Invoke-Main {
    try {
        Write-Host @"

████████╗██╗  ██╗███████╗ ██████╗     ███████╗███╗   ██╗ ██████╗ ██╗███╗   ██╗███████╗
╚══██╔══╝██║  ██║██╔════╝██╔═══██╗    ██╔════╝████╗  ██║██╔════╝ ██║████╗  ██║██╔════╝
   ██║   ███████║█████╗  ██║   ██║    █████╗  ██╔██╗ ██║██║  ███╗██║██╔██╗ ██║█████╗  
   ██║   ██╔══██║██╔══╝  ██║   ██║    ██╔══╝  ██║╚██╗██║██║   ██║██║██║╚██╗██║██╔══╝  
   ██║   ██║  ██║███████╗╚██████╔╝    ███████╗██║ ╚████║╚██████╔╝██║██║ ╚████║███████╗
   ╚═╝   ╚═╝  ╚═╝╚══════╝ ╚═════╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝╚══════╝
                                                                                        
"@ -ForegroundColor Magenta
        
        Write-Host "  Research Engine for Theological Corpora" -ForegroundColor Cyan
        Write-Host "  Mode: $Mode" -ForegroundColor Yellow
        Write-Host ""
        
        # Run prerequisite checks unless skipped
        if (-not $SkipChecks -and $Mode -ne 'check') {
            Test-Prerequisites
            Initialize-EnvironmentFiles
        }
        
        # Execute based on mode
        switch ($Mode) {
            'check' {
                Test-Prerequisites
                Write-Success "Environment check complete"
                return
            }
            
            'test' {
                Start-TestSuite
                return
            }
            
            'api' {
                $apiJob = Start-ApiService
                
                Write-Host ""
                Write-Success "API service is running"
                Write-Host "  Press Ctrl+C to stop" -ForegroundColor Yellow
                Write-Host ""
                
                # Keep script alive and show logs
                try {
                    while ($true) {
                        $output = Receive-Job -Job $apiJob
                        if ($output) {
                            Write-Host $output
                        }
                        Start-Sleep -Seconds 1
                    }
                } finally {
                    Stop-Job -Job $apiJob
                    Remove-Job -Job $apiJob
                }
            }
            
            'web' {
                # Check if API is running
                if (-not (Test-PortInUse $Port)) {
                    Write-Warn "API is not running on port $Port"
                    Write-Host "  The web app requires the API to function properly." -ForegroundColor Yellow
                    Write-Host "  Start the API first with: .\run.ps1 -Mode api" -ForegroundColor Yellow
                    Write-Host ""
                    $continue = Read-Host "Continue anyway? (y/N)"
                    if ($continue -ne 'y') {
                        return
                    }
                }
                
                $webJob = Start-WebService
                
                Write-Host ""
                Write-Success "Web service is running"
                Write-Host "  Press Ctrl+C to stop" -ForegroundColor Yellow
                Write-Host ""
                
                # Keep script alive and show logs
                try {
                    while ($true) {
                        $output = Receive-Job -Job $webJob
                        if ($output) {
                            Write-Host $output
                        }
                        Start-Sleep -Seconds 1
                    }
                } finally {
                    Stop-Job -Job $webJob
                    Remove-Job -Job $webJob
                }
            }
            
            { $_ -in 'full', 'dev' } {
                # Start both services
                $apiJob = Start-ApiService
                Start-Sleep -Seconds 2  # Give API a moment to fully initialize
                $webJob = Start-WebService
                
                Write-Host ""
                Write-Header "Services Running"
                Write-Success "All services started successfully!"
                Write-Host ""
                Write-Host "  API:  http://127.0.0.1:$Port" -ForegroundColor Cyan
                Write-Host "  Web:  http://127.0.0.1:$WebPort" -ForegroundColor Cyan
                Write-Host "  Docs: http://127.0.0.1:$Port/docs" -ForegroundColor Cyan
                Write-Host ""
                Write-Host "  Press Ctrl+C to stop all services" -ForegroundColor Yellow
                Write-Host ""
                
                # Keep script alive and show logs
                try {
                    while ($true) {
                        $apiOutput = Receive-Job -Job $apiJob
                        $webOutput = Receive-Job -Job $webJob
                        
                        if ($apiOutput) {
                            Write-Host "[API] $apiOutput" -ForegroundColor Blue
                        }
                        if ($webOutput) {
                            Write-Host "[WEB] $webOutput" -ForegroundColor Green
                        }
                        
                        # Check if jobs are still running
                        if ($apiJob.State -eq 'Failed' -or $apiJob.State -eq 'Stopped') {
                            Write-Fail "API service stopped unexpectedly"
                            break
                        }
                        if ($webJob.State -eq 'Failed' -or $webJob.State -eq 'Stopped') {
                            Write-Fail "Web service stopped unexpectedly"
                            break
                        }
                        
                        Start-Sleep -Seconds 1
                    }
                } finally {
                    Write-Host ""
                    Write-Step "Stopping services..."
                    Stop-Job -Job $apiJob -ErrorAction SilentlyContinue
                    Stop-Job -Job $webJob -ErrorAction SilentlyContinue
                    Remove-Job -Job $apiJob -ErrorAction SilentlyContinue
                    Remove-Job -Job $webJob -ErrorAction SilentlyContinue
                    Write-Success "Services stopped"
                }
            }
        }
        
    } catch {
        Write-Host ""
        Write-Fail "Error: $($_.Exception.Message)"
        Write-Host $_.ScriptStackTrace -ForegroundColor Red
        exit 1
    }
}

# Run main function
Invoke-Main
