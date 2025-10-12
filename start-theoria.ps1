<#
.SYNOPSIS
    Intelligent launcher for Theoria - ensures API and Web services run reliably.

.DESCRIPTION
    Smart service manager that:
    - Validates all prerequisites (Python, Node, dependencies)
    - Starts both API (port 8000) and Web (port 3000) services
    - Continuously monitors health with auto-recovery
    - Handles graceful shutdown on Ctrl+C
    - Provides clear status updates and error diagnostics

.PARAMETER ApiPort
    Port for the FastAPI server (default: 8000)

.PARAMETER WebPort
    Port for the Next.js dev server (default: 3000)

.PARAMETER SkipHealthChecks
    Disable continuous health monitoring (faster startup, less resilient)

.PARAMETER Verbose
    Show detailed logging for troubleshooting

.EXAMPLE
    .\start-theoria.ps1
    Start both services with default ports and health monitoring

.EXAMPLE
    .\start-theoria.ps1 -ApiPort 8010 -WebPort 3100
    Start with custom ports

.EXAMPLE
    .\start-theoria.ps1 -Verbose
    Start with detailed logging

.NOTES
    Theoria Engine - Intelligent Service Launcher
    Press Ctrl+C to stop all services gracefully
#>

param(
    [int]$ApiPort = 8000,
    [int]$WebPort = 3000,
    [switch]$SkipHealthChecks = $false,
    [switch]$Verbose = $false
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ============================================================================
# CONFIGURATION
# ============================================================================

$script:ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:WebRoot = Join-Path $ProjectRoot "theo\services\web"
$script:ApiHealthEndpoint = "http://127.0.0.1:$ApiPort/health"
$script:WebHealthEndpoint = "http://127.0.0.1:$WebPort"
$script:HealthCheckInterval = 10  # seconds
$script:MaxRestartAttempts = 3
$script:RestartCooldown = 5  # seconds

# Service state tracking
$script:Services = @{
    Api = @{
        Name = "Theoria API"
        Job = $null
        Port = $ApiPort
        HealthEndpoint = $script:ApiHealthEndpoint
        RestartCount = 0
        LastRestartTime = $null
        Status = "Not Started"
    }
    Web = @{
        Name = "Theoria Web"
        Job = $null
        Port = $WebPort
        HealthEndpoint = $script:WebHealthEndpoint
        RestartCount = 0
        LastRestartTime = $null
        Status = "Not Started"
    }
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

function Write-TheoriaLog {
    param(
        [string]$Message,
        [ValidateSet("Info", "Success", "Warning", "Error", "Debug")]
        [string]$Level = "Info"
    )
    
    $timestamp = Get-Date -Format "HH:mm:ss"
    $colors = @{
        Info = "Cyan"
        Success = "Green"
        Warning = "Yellow"
        Error = "Red"
        Debug = "Gray"
    }
    
    $icons = @{
        Info = "ℹ"
        Success = "✓"
        Warning = "⚠"
        Error = "✗"
        Debug = "→"
    }
    
    if ($Level -eq "Debug" -and -not $Verbose) { return }
    
    $color = $colors[$Level]
    $icon = $icons[$Level]
    Write-Host "[$timestamp] $icon " -ForegroundColor $color -NoNewline
    Write-Host $Message
}

function Write-TheoriaBanner {
    Write-Host "`n" -NoNewline
    Write-Host "╔══════════════════════════════════════════════════════════╗" -ForegroundColor Magenta
    Write-Host "║                                                          ║" -ForegroundColor Magenta
    Write-Host "║              " -ForegroundColor Magenta -NoNewline
    Write-Host "THEORIA ENGINE" -ForegroundColor White -NoNewline
    Write-Host " - Service Launcher            ║" -ForegroundColor Magenta
    Write-Host "║                                                          ║" -ForegroundColor Magenta
    Write-Host "║          Research workspace for theology                ║" -ForegroundColor Magenta
    Write-Host "║                                                          ║" -ForegroundColor Magenta
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Magenta
    Write-Host ""
}

function Test-Prerequisite {
    param(
        [string]$Name,
        [string]$Command,
        [string]$VersionArg = "--version",
        [string]$MinVersion = $null
    )
    
    Write-TheoriaLog "Checking $Name..." -Level Debug
    
    try {
        $result = & $Command $VersionArg 2>&1 | Out-String
        if ($LASTEXITCODE -eq 0) {
            $version = ($result -split "`n")[0].Trim()
            Write-TheoriaLog "$Name detected: $version" -Level Success
            return $true
        }
    } catch {
        Write-TheoriaLog "$Name not found: $_" -Level Error
        return $false
    }
    
    Write-TheoriaLog "$Name not found or invalid" -Level Error
    return $false
}

function Test-PortAvailable {
    param([int]$Port)
    
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Any, $Port)
        $listener.Start()
        $listener.Stop()
        return $true
    } catch {
        return $false
    }
}

function Test-ServiceHealth {
    param([string]$Endpoint)
    
    try {
        $response = Invoke-WebRequest -Uri $Endpoint -TimeoutSec 2 -UseBasicParsing -ErrorAction Stop
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Stop-TheoriaService {
    param(
        [string]$ServiceKey
    )
    
    $service = $script:Services[$ServiceKey]
    if (-not $service.Job) { return }
    
    Write-TheoriaLog "Stopping $($service.Name)..." -Level Info
    
    try {
        Stop-Job $service.Job -ErrorAction SilentlyContinue | Out-Null
        $output = Receive-Job $service.Job -ErrorAction SilentlyContinue
        
        if ($Verbose -and $output) {
            Write-TheoriaLog "Service output:" -Level Debug
            $output | ForEach-Object { Write-TheoriaLog "  $_" -Level Debug }
        }
        
        Remove-Job $service.Job -Force -ErrorAction SilentlyContinue | Out-Null
        $service.Job = $null
        $service.Status = "Stopped"
        
        Write-TheoriaLog "$($service.Name) stopped" -Level Success
    } catch {
        Write-TheoriaLog "Error stopping $($service.Name): $_" -Level Error
    }
}

function Start-TheoriaApi {
    Write-TheoriaLog "Starting Theoria API on port $ApiPort..." -Level Info
    
    # Check port availability
    if (-not (Test-PortAvailable -Port $ApiPort)) {
        Write-TheoriaLog "Port $ApiPort is already in use" -Level Error
        return $false
    }
    
    # Set environment variables and start API
    $scriptBlock = {
        param($Port, $ProjectRoot)
        
        $env:THEO_AUTH_ALLOW_ANONYMOUS = "1"
        $env:THEO_ALLOW_INSECURE_STARTUP = "1"
        $env:PYTHONUNBUFFERED = "1"
        
        Set-Location $ProjectRoot
        python -m uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port $Port 2>&1
    }
    
    try {
        $job = Start-Job -ScriptBlock $scriptBlock -ArgumentList $ApiPort, $script:ProjectRoot
        $script:Services.Api.Job = $job
        $script:Services.Api.Status = "Starting"
        
        # Wait for API to become healthy
        Write-TheoriaLog "Waiting for API to become ready..." -Level Debug
        $maxWait = 30
        $waited = 0
        
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 1
            $waited++
            
            if (Test-ServiceHealth -Endpoint $script:ApiHealthEndpoint) {
                $script:Services.Api.Status = "Running"
                Write-TheoriaLog "Theoria API is ready at http://127.0.0.1:$ApiPort" -Level Success
                Write-TheoriaLog "API Docs: http://127.0.0.1:$ApiPort/docs" -Level Info
                return $true
            }
            
            # Check if job failed
            if ($job.State -eq "Failed" -or $job.State -eq "Stopped") {
                $apiError = Receive-Job $job 2>&1 | Out-String
                Write-TheoriaLog "API failed to start:" -Level Error
                Write-TheoriaLog $apiError -Level Error
                return $false
            }
        }
        
        Write-TheoriaLog "API did not become healthy within ${maxWait}s" -Level Warning
        return $false
        
    } catch {
        Write-TheoriaLog "Failed to start API: $_" -Level Error
        return $false
    }
}

function Start-TheoriaWeb {
    Write-TheoriaLog "Starting Theoria Web UI on port $WebPort..." -Level Info
    
    # Check port availability
    if (-not (Test-PortAvailable -Port $WebPort)) {
        Write-TheoriaLog "Port $WebPort is already in use" -Level Error
        return $false
    }
    
    # Check if node_modules exists
    $nodeModulesPath = Join-Path $script:WebRoot "node_modules"
    if (-not (Test-Path $nodeModulesPath)) {
        Write-TheoriaLog "Installing Node.js dependencies (first time only)..." -Level Info
        Push-Location $script:WebRoot
        try {
            npm install 2>&1 | Out-Null
            Write-TheoriaLog "Dependencies installed successfully" -Level Success
        } catch {
            Write-TheoriaLog "Failed to install dependencies: $_" -Level Error
            Pop-Location
            return $false
        }
        Pop-Location
    }
    
    # Start Web server
    $scriptBlock = {
        param($Port, $WebRoot, $ApiPort)
        
        $env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:$ApiPort"
        $env:PORT = $Port
        
        Set-Location $WebRoot
        npm run dev 2>&1
    }
    
    try {
        $job = Start-Job -ScriptBlock $scriptBlock -ArgumentList $WebPort, $script:WebRoot, $ApiPort
        $script:Services.Web.Job = $job
        $script:Services.Web.Status = "Starting"
        
        # Wait for Web to become healthy
        Write-TheoriaLog "Waiting for Web UI to become ready..." -Level Debug
        $maxWait = 45
        $waited = 0
        
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 1
            $waited++
            
            if (Test-ServiceHealth -Endpoint $script:WebHealthEndpoint) {
                $script:Services.Web.Status = "Running"
                Write-TheoriaLog "Theoria Web UI is ready at http://localhost:$WebPort" -Level Success
                return $true
            }
            
            # Check if job failed
            if ($job.State -eq "Failed" -or $job.State -eq "Stopped") {
                $webError = Receive-Job $job 2>&1 | Out-String
                Write-TheoriaLog "Web UI failed to start:" -Level Error
                Write-TheoriaLog $webError -Level Error
                return $false
            }
        }
        
        Write-TheoriaLog "Web UI did not become healthy within ${maxWait}s" -Level Warning
        return $false
        
    } catch {
        Write-TheoriaLog "Failed to start Web UI: $_" -Level Error
        return $false
    }
}

function Start-HealthMonitor {
    if ($SkipHealthChecks) {
        Write-TheoriaLog "Health monitoring disabled" -Level Warning
        return
    }
    
    Write-TheoriaLog "Starting health monitor (checking every ${script:HealthCheckInterval}s)..." -Level Info
    
    while ($true) {
        Start-Sleep -Seconds $script:HealthCheckInterval
        
        foreach ($serviceKey in $script:Services.Keys) {
            $service = $script:Services[$serviceKey]
            
            if ($service.Status -ne "Running") { continue }
            
            # Check health
            $isHealthy = Test-ServiceHealth -Endpoint $service.HealthEndpoint
            
            if (-not $isHealthy) {
                Write-TheoriaLog "$($service.Name) health check failed" -Level Warning
                
                # Check if we should restart
                if ($service.RestartCount -lt $script:MaxRestartAttempts) {
                    $timeSinceLastRestart = if ($service.LastRestartTime) {
                        (Get-Date) - $service.LastRestartTime
                    } else {
                        New-TimeSpan -Seconds 999
                    }
                    
                    if ($timeSinceLastRestart.TotalSeconds -gt $script:RestartCooldown) {
                        Write-TheoriaLog "Attempting to restart $($service.Name) (attempt $($service.RestartCount + 1)/$script:MaxRestartAttempts)..." -Level Warning
                        
                        Stop-TheoriaService -ServiceKey $serviceKey
                        Start-Sleep -Seconds 2
                        
                        $success = if ($serviceKey -eq "Api") {
                            Start-TheoriaApi
                        } else {
                            Start-TheoriaWeb
                        }
                        
                        if ($success) {
                            $service.RestartCount++
                            $service.LastRestartTime = Get-Date
                            Write-TheoriaLog "$($service.Name) restarted successfully" -Level Success
                        } else {
                            Write-TheoriaLog "$($service.Name) restart failed" -Level Error
                        }
                    }
                } else {
                    Write-TheoriaLog "$($service.Name) has exceeded maximum restart attempts" -Level Error
                    Write-TheoriaLog "Manual intervention required" -Level Error
                }
            } else {
                Write-TheoriaLog "$($service.Name) health check passed" -Level Debug
            }
        }
    }
}

# ============================================================================
# MAIN EXECUTION
# ============================================================================

function Start-Theoria {
    Write-TheoriaBanner
    
    Write-TheoriaLog "Initializing Theoria Engine..." -Level Info
    Write-TheoriaLog "Project Root: $script:ProjectRoot" -Level Debug
    
    # Pre-flight checks
    Write-Host "`n--- Pre-flight Checks ---`n" -ForegroundColor Yellow
    
    $pythonOk = Test-Prerequisite -Name "Python" -Command "python" -VersionArg "--version"
    $nodeOk = Test-Prerequisite -Name "Node.js" -Command "node" -VersionArg "--version"
    $npmOk = Test-Prerequisite -Name "npm" -Command "npm" -VersionArg "--version"
    
    if (-not $pythonOk) {
        Write-TheoriaLog "Python is required. Install from https://python.org" -Level Error
        return
    }
    
    if (-not $nodeOk -or -not $npmOk) {
        Write-TheoriaLog "Node.js and npm are required. Install from https://nodejs.org" -Level Error
        return
    }
    
    # Check for .env file
    $envPath = Join-Path $script:ProjectRoot ".env"
    if (-not (Test-Path $envPath)) {
        Write-TheoriaLog ".env file not found, creating from template..." -Level Warning
        $envExample = Join-Path $script:ProjectRoot ".env.example"
        if (Test-Path $envExample) {
            Copy-Item $envExample $envPath
            Write-TheoriaLog ".env file created successfully" -Level Success
        } else {
            Write-TheoriaLog ".env.example not found, cannot create .env" -Level Error
            return
        }
    }
    
    Write-Host "`n--- Starting Services ---`n" -ForegroundColor Yellow
    
    # Start API first
    $apiStarted = Start-TheoriaApi
    if (-not $apiStarted) {
        Write-TheoriaLog "Failed to start API, aborting" -Level Error
        return
    }
    
    # Start Web UI
    $webStarted = Start-TheoriaWeb
    if (-not $webStarted) {
        Write-TheoriaLog "Failed to start Web UI, stopping API" -Level Error
        Stop-TheoriaService -ServiceKey "Api"
        return
    }
    
    # Success banner
    Write-Host "`n╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                                                          ║" -ForegroundColor Green
    Write-Host "║                 " -ForegroundColor Green -NoNewline
    Write-Host "🚀 THEORIA IS READY! 🚀" -ForegroundColor White -NoNewline
    Write-Host "                 ║" -ForegroundColor Green
    Write-Host "║                                                          ║" -ForegroundColor Green
    Write-Host "║  API:     http://127.0.0.1:$ApiPort                               ║" -ForegroundColor Green
    Write-Host "║  Web UI:  http://localhost:$WebPort                             ║" -ForegroundColor Green
    Write-Host "║  Docs:    http://127.0.0.1:$ApiPort/docs                        ║" -ForegroundColor Green
    Write-Host "║                                                          ║" -ForegroundColor Green
    Write-Host "║  Press Ctrl+C to stop all services                      ║" -ForegroundColor Green
    Write-Host "║                                                          ║" -ForegroundColor Green
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Green
    Write-Host ""
    
    # Set up Ctrl+C handler
    $null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action {
        Write-Host "`n`nShutting down Theoria services..." -ForegroundColor Yellow
        Stop-TheoriaService -ServiceKey "Web"
        Stop-TheoriaService -ServiceKey "Api"
    }
    
    # Start health monitoring
    try {
        Start-HealthMonitor
    } finally {
        Write-Host "`n`n--- Shutting Down ---`n" -ForegroundColor Yellow
        Stop-TheoriaService -ServiceKey "Web"
        Stop-TheoriaService -ServiceKey "Api"
        Write-TheoriaLog "All services stopped. Goodbye!" -Level Success
    }
}

# Execute
Start-Theoria
