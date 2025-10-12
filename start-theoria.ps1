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

.PARAMETER LogToFile
    Write logs to file in addition to console (logs/theoria-launcher.log)

.PARAMETER ShowMetrics
    Display real-time service metrics in the console

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
    [switch]$Verbose = $false,
    [switch]$LogToFile = $false,
    [switch]$ShowMetrics = $false
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

# ============================================================================
# CONFIGURATION
# ============================================================================

$script:ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:WebRoot = Join-Path $ProjectRoot "theo\services\web"
$script:LogsDir = Join-Path $ProjectRoot "logs"
$script:LogFile = Join-Path $script:LogsDir "theoria-launcher.log"
$script:ApiHealthEndpoint = "http://127.0.0.1:$ApiPort/health"
$script:WebHealthEndpoint = "http://127.0.0.1:$WebPort"
$script:HealthCheckInterval = 10  # seconds
$script:MaxRestartAttempts = 3
$script:RestartCooldown = 5  # seconds
$script:HealthCheckTimeout = 5  # seconds
$script:StartTime = Get-Date

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
        StartTime = $null
        HealthCheckFailures = 0
        TotalHealthChecks = 0
        LastHealthCheckDuration = 0
        AverageResponseTime = 0
        LastError = $null
    }
    Web = @{
        Name = "Theoria Web"
        Job = $null
        Port = $WebPort
        HealthEndpoint = $script:WebHealthEndpoint
        RestartCount = 0
        LastRestartTime = $null
        Status = "Not Started"
        StartTime = $null
        HealthCheckFailures = 0
        TotalHealthChecks = 0
        LastHealthCheckDuration = 0
        AverageResponseTime = 0
        LastError = $null
    }
}

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

function Write-TheoriaLog {
    param(
        [string]$Message,
        [ValidateSet("Info", "Success", "Warning", "Error", "Debug", "Metric")]
        [string]$Level = "Info",
        [hashtable]$Metadata = @{}
    )
    
    $timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss.fff"
    $colors = @{
        Info = "Cyan"
        Success = "Green"
        Warning = "Yellow"
        Error = "Red"
        Debug = "Gray"
        Metric = "Magenta"
    }
    
    $icons = @{
        Info = "ℹ"
        Success = "✓"
        Warning = "⚠"
        Error = "✗"
        Debug = "→"
        Metric = "📊"
    }
    
    if ($Level -eq "Debug" -and -not $Verbose) { return }
    if ($Level -eq "Metric" -and -not $ShowMetrics) { return }
    
    # Console output
    $color = $colors[$Level]
    $icon = $icons[$Level]
    $displayTime = Get-Date -Format "HH:mm:ss"
    Write-Host "[$displayTime] $icon " -ForegroundColor $color -NoNewline
    Write-Host $Message
    
    # File output (structured JSON)
    if ($LogToFile) {
        try {
            if (-not (Test-Path $script:LogsDir)) {
                New-Item -ItemType Directory -Path $script:LogsDir -Force | Out-Null
            }
            
            $logEntry = @{
                timestamp = $timestamp
                level = $Level
                message = $Message
                metadata = $Metadata
            } | ConvertTo-Json -Compress
            
            Add-Content -Path $script:LogFile -Value $logEntry -ErrorAction SilentlyContinue
        } catch {
            # Silently fail if logging fails to avoid disrupting main flow
        }
    }
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
    param(
        [string]$Endpoint,
        [ref]$Diagnostics
    )
    
    $startTime = Get-Date
    $result = @{
        Healthy = $false
        StatusCode = $null
        ResponseTime = 0
        Error = $null
    }
    
    try {
        $response = Invoke-WebRequest -Uri $Endpoint -TimeoutSec $script:HealthCheckTimeout -UseBasicParsing -ErrorAction Stop
        $result.Healthy = $response.StatusCode -eq 200
        $result.StatusCode = $response.StatusCode
    } catch {
        $result.Error = $_.Exception.Message
        $result.StatusCode = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
    } finally {
        $result.ResponseTime = ((Get-Date) - $startTime).TotalMilliseconds
    }
    
    if ($Diagnostics) {
        $Diagnostics.Value = $result
    }
    
    return $result.Healthy
}

function Stop-TheoriaService {
    param(
        [string]$ServiceKey,
        [switch]$Force = $false
    )
    
    $service = $script:Services[$ServiceKey]
    if (-not $service.Job) { return }
    
    Write-TheoriaLog "Stopping $($service.Name)..." -Level Info
    
    try {
        # Graceful shutdown attempt
        if (-not $Force) {
            Stop-Job $service.Job -ErrorAction SilentlyContinue | Out-Null
            Start-Sleep -Milliseconds 500
        }
        
        # Capture final output
        $output = Receive-Job $service.Job -ErrorAction SilentlyContinue
        
        if ($Verbose -and $output) {
            Write-TheoriaLog "Service output:" -Level Debug
            $output | ForEach-Object { Write-TheoriaLog "  $_" -Level Debug }
        }
        
        # Force removal
        Remove-Job $service.Job -Force -ErrorAction SilentlyContinue | Out-Null
        $service.Job = $null
        $service.Status = "Stopped"
        
        # Calculate uptime
        if ($service.StartTime) {
            $uptime = (Get-Date) - $service.StartTime
            Write-TheoriaLog "$($service.Name) stopped (uptime: $($uptime.ToString('hh\:mm\:ss')))" -Level Success -Metadata @{ uptime_seconds = $uptime.TotalSeconds }
            $service.StartTime = $null
        } else {
            Write-TheoriaLog "$($service.Name) stopped" -Level Success
        }
    } catch {
        Write-TheoriaLog "Error stopping $($service.Name): $_" -Level Error -Metadata @{ error = $_.Exception.Message }
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
        $script:Services.Api.StartTime = Get-Date
        
        # Wait for API to become healthy
        Write-TheoriaLog "Waiting for API to become ready..." -Level Debug
        $maxWait = 30
        $waited = 0
        
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 1
            $waited++
            
            $diagnostics = $null
            if (Test-ServiceHealth -Endpoint $script:ApiHealthEndpoint -Diagnostics ([ref]$diagnostics)) {
                $script:Services.Api.Status = "Running"
                Write-TheoriaLog "Theoria API is ready at http://127.0.0.1:$ApiPort (startup time: ${waited}s)" -Level Success -Metadata @{ startup_time_seconds = $waited; response_time_ms = $diagnostics.ResponseTime }
                Write-TheoriaLog "API Docs: http://127.0.0.1:$ApiPort/docs" -Level Info
                return $true
            }
            
            # Check if job failed
            if ($job.State -eq "Failed" -or $job.State -eq "Stopped") {
                $apiError = Receive-Job $job 2>&1 | Out-String
                $script:Services.Api.LastError = $apiError
                Write-TheoriaLog "API failed to start:" -Level Error -Metadata @{ error = $apiError }
                Write-TheoriaLog $apiError -Level Error
                $script:Services.Api.StartTime = $null
                return $false
            }
        }
        
        $script:Services.Api.LastError = "Timeout after ${maxWait}s"
        Write-TheoriaLog "API did not become healthy within ${maxWait}s" -Level Warning -Metadata @{ timeout_seconds = $maxWait }
        $script:Services.Api.StartTime = $null
        return $false
        
    } catch {
        $script:Services.Api.LastError = $_.Exception.Message
        Write-TheoriaLog "Failed to start API: $_" -Level Error -Metadata @{ error = $_.Exception.Message }
        $script:Services.Api.StartTime = $null
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
        $script:Services.Web.StartTime = Get-Date
        
        # Wait for Web to become healthy
        Write-TheoriaLog "Waiting for Web UI to become ready..." -Level Debug
        $maxWait = 45
        $waited = 0
        
        while ($waited -lt $maxWait) {
            Start-Sleep -Seconds 1
            $waited++
            
            $diagnostics = $null
            if (Test-ServiceHealth -Endpoint $script:WebHealthEndpoint -Diagnostics ([ref]$diagnostics)) {
                $script:Services.Web.Status = "Running"
                Write-TheoriaLog "Theoria Web UI is ready at http://localhost:$WebPort (startup time: ${waited}s)" -Level Success -Metadata @{ startup_time_seconds = $waited; response_time_ms = $diagnostics.ResponseTime }
                return $true
            }
            
            # Check if job failed
            if ($job.State -eq "Failed" -or $job.State -eq "Stopped") {
                $webError = Receive-Job $job 2>&1 | Out-String
                $script:Services.Web.LastError = $webError
                Write-TheoriaLog "Web UI failed to start:" -Level Error -Metadata @{ error = $webError }
                Write-TheoriaLog $webError -Level Error
                $script:Services.Web.StartTime = $null
                return $false
            }
        }
        
        $script:Services.Web.LastError = "Timeout after ${maxWait}s"
        Write-TheoriaLog "Web UI did not become healthy within ${maxWait}s" -Level Warning -Metadata @{ timeout_seconds = $maxWait }
        $script:Services.Web.StartTime = $null
        return $false
        
    } catch {
        $script:Services.Web.LastError = $_.Exception.Message
        Write-TheoriaLog "Failed to start Web UI: $_" -Level Error -Metadata @{ error = $_.Exception.Message }
        $script:Services.Web.StartTime = $null
        return $false
    }
}

function Get-ServiceMetrics {
    param([string]$ServiceKey)
    
    $service = $script:Services[$ServiceKey]
    $uptime = if ($service.StartTime) { (Get-Date) - $service.StartTime } else { $null }
    $healthRate = if ($service.TotalHealthChecks -gt 0) {
        [math]::Round((($service.TotalHealthChecks - $service.HealthCheckFailures) / $service.TotalHealthChecks) * 100, 2)
    } else { 0 }
    
    return @{
        Name = $service.Name
        Status = $service.Status
        Uptime = if ($uptime) { $uptime.ToString('hh\:mm\:ss') } else { "N/A" }
        UptimeSeconds = if ($uptime) { [int]$uptime.TotalSeconds } else { 0 }
        HealthRate = "${healthRate}%"
        AvgResponseTime = "$([math]::Round($service.AverageResponseTime, 2))ms"
        LastResponseTime = "$([math]::Round($service.LastHealthCheckDuration, 2))ms"
        RestartCount = $service.RestartCount
        TotalChecks = $service.TotalHealthChecks
        Failures = $service.HealthCheckFailures
    }
}

function Show-ServiceStatus {
    Write-Host "`n╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
    Write-Host "║               SERVICE STATUS DASHBOARD                  ║" -ForegroundColor Cyan
    Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
    
    foreach ($serviceKey in $script:Services.Keys) {
        $metrics = Get-ServiceMetrics -ServiceKey $serviceKey
        $statusColor = switch ($metrics.Status) {
            "Running" { "Green" }
            "Starting" { "Yellow" }
            "Stopped" { "Red" }
            default { "Gray" }
        }
        
        Write-Host "║ " -ForegroundColor Cyan -NoNewline
        Write-Host "$($metrics.Name)" -ForegroundColor White -NoNewline
        Write-Host " [" -NoNewline
        Write-Host "$($metrics.Status)" -ForegroundColor $statusColor -NoNewline
        Write-Host "]" -NoNewline
        Write-Host " " * (55 - $metrics.Name.Length - $metrics.Status.Length - 4) -NoNewline
        Write-Host "║" -ForegroundColor Cyan
        Write-Host "║   Uptime: $($metrics.Uptime) | Health: $($metrics.HealthRate) | Avg Response: $($metrics.AvgResponseTime)" -NoNewline
        $padding = 59 - "  Uptime: $($metrics.Uptime) | Health: $($metrics.HealthRate) | Avg Response: $($metrics.AvgResponseTime)".Length
        Write-Host " " * $padding -NoNewline
        Write-Host "║" -ForegroundColor Cyan
        
        if ($metrics.RestartCount -gt 0) {
            Write-Host "║   Restarts: $($metrics.RestartCount)" -ForegroundColor Yellow -NoNewline
            Write-Host " " * (45 - "  Restarts: $($metrics.RestartCount)".Length) -NoNewline
            Write-Host "║" -ForegroundColor Cyan
        }
    }
    
    $totalUptime = ((Get-Date) - $script:StartTime).ToString('hh\:mm\:ss')
    Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
    Write-Host "║ Total Runtime: $totalUptime" -NoNewline
    Write-Host " " * (45 - "Total Runtime: $totalUptime".Length) -NoNewline
    Write-Host "║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
}

function Start-HealthMonitor {
    if ($SkipHealthChecks) {
        Write-TheoriaLog "Health monitoring disabled" -Level Warning
        return
    }
    
    Write-TheoriaLog "Starting health monitor (checking every ${script:HealthCheckInterval}s)..." -Level Info
    $checkCount = 0
    
    while ($true) {
        Start-Sleep -Seconds $script:HealthCheckInterval
        $checkCount++
        
        # Show status dashboard every 6 checks (1 minute with 10s intervals)
        if ($ShowMetrics -and $checkCount % 6 -eq 0) {
            Show-ServiceStatus
        }
        
        foreach ($serviceKey in $script:Services.Keys) {
            $service = $script:Services[$serviceKey]
            
            if ($service.Status -ne "Running") { continue }
            
            # Check health with diagnostics
            $diagnostics = $null
            $isHealthy = Test-ServiceHealth -Endpoint $service.HealthEndpoint -Diagnostics ([ref]$diagnostics)
            
            # Update metrics
            $service.TotalHealthChecks++
            $service.LastHealthCheckDuration = $diagnostics.ResponseTime
            
            # Calculate rolling average response time
            if ($service.AverageResponseTime -eq 0) {
                $service.AverageResponseTime = $diagnostics.ResponseTime
            } else {
                $service.AverageResponseTime = ($service.AverageResponseTime * 0.8) + ($diagnostics.ResponseTime * 0.2)
            }
            
            if (-not $isHealthy) {
                $service.HealthCheckFailures++
                $service.LastError = $diagnostics.Error
                
                Write-TheoriaLog "$($service.Name) health check failed: $($diagnostics.Error)" -Level Warning -Metadata @{
                    service = $serviceKey
                    status_code = $diagnostics.StatusCode
                    error = $diagnostics.Error
                    response_time_ms = $diagnostics.ResponseTime
                }
                
                # Calculate exponential backoff cooldown
                $backoffMultiplier = [math]::Pow(2, [math]::Min($service.RestartCount, 4))
                $currentCooldown = $script:RestartCooldown * $backoffMultiplier
                
                # Check if we should restart
                if ($service.RestartCount -lt $script:MaxRestartAttempts) {
                    $timeSinceLastRestart = if ($service.LastRestartTime) {
                        (Get-Date) - $service.LastRestartTime
                    } else {
                        New-TimeSpan -Seconds 999
                    }
                    
                    if ($timeSinceLastRestart.TotalSeconds -gt $currentCooldown) {
                        Write-TheoriaLog "Attempting to restart $($service.Name) (attempt $($service.RestartCount + 1)/$script:MaxRestartAttempts, cooldown: ${currentCooldown}s)..." -Level Warning -Metadata @{
                            restart_attempt = $service.RestartCount + 1
                            max_attempts = $script:MaxRestartAttempts
                            cooldown_seconds = $currentCooldown
                        }
                        
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
                            Write-TheoriaLog "$($service.Name) restarted successfully" -Level Success -Metadata @{ restart_count = $service.RestartCount }
                        } else {
                            Write-TheoriaLog "$($service.Name) restart failed" -Level Error
                        }
                    } else {
                        $remainingCooldown = [int]($currentCooldown - $timeSinceLastRestart.TotalSeconds)
                        Write-TheoriaLog "$($service.Name) in cooldown period (${remainingCooldown}s remaining)" -Level Debug
                    }
                } else {
                    Write-TheoriaLog "$($service.Name) has exceeded maximum restart attempts ($script:MaxRestartAttempts)" -Level Error
                    Write-TheoriaLog "Manual intervention required - check logs for details" -Level Error
                }
            } else {
                # Reset failure counter on successful health check
                if ($service.HealthCheckFailures -gt 0) {
                    Write-TheoriaLog "$($service.Name) recovered (response: $($diagnostics.ResponseTime)ms)" -Level Success
                }
                
                Write-TheoriaLog "$($service.Name) health check passed" -Level Debug -Metadata @{
                    response_time_ms = $diagnostics.ResponseTime
                    avg_response_time_ms = $service.AverageResponseTime
                }
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
    
    if ($LogToFile) {
        Write-TheoriaLog "Logging to file: $script:LogFile" -Level Info
    }
    if ($ShowMetrics) {
        Write-TheoriaLog "Real-time metrics enabled (status dashboard every 60s)" -Level Info
    }
    
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
    Write-Host "║  Features:                                               ║" -ForegroundColor Green
    Write-Host "║    ✓ Auto-recovery with exponential backoff             ║" -ForegroundColor Green
    Write-Host "║    ✓ Health monitoring every ${script:HealthCheckInterval}s                           ║" -ForegroundColor Green
    if ($ShowMetrics) {
        Write-Host "║    ✓ Real-time metrics dashboard                        ║" -ForegroundColor Green
    }
    if ($LogToFile) {
        Write-Host "║    ✓ Structured logging enabled                         ║" -ForegroundColor Green
    }
    Write-Host "║                                                          ║" -ForegroundColor Green
    Write-Host "║  Press Ctrl+C to stop all services gracefully           ║" -ForegroundColor Green
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
        Write-Host "`n`n╔══════════════════════════════════════════════════════════╗" -ForegroundColor Yellow
        Write-Host "║                SHUTTING DOWN SERVICES                    ║" -ForegroundColor Yellow
        Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Yellow
        Write-Host ""
        
        # Graceful shutdown with timeout
        Stop-TheoriaService -ServiceKey "Web"
        Stop-TheoriaService -ServiceKey "Api"
        
        # Generate session summary
        $totalRuntime = (Get-Date) - $script:StartTime
        Write-Host "`n╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
        Write-Host "║                   SESSION SUMMARY                        ║" -ForegroundColor Cyan
        Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
        Write-Host "║ Total Runtime: $($totalRuntime.ToString('hh\:mm\:ss'))" -NoNewline
        Write-Host " " * (42 - "Total Runtime: $($totalRuntime.ToString('hh\:mm\:ss'))".Length) -NoNewline
        Write-Host "║" -ForegroundColor Cyan
        
        foreach ($serviceKey in $script:Services.Keys) {
            $metrics = Get-ServiceMetrics -ServiceKey $serviceKey
            Write-Host "║ $($metrics.Name):" -NoNewline
            Write-Host " " * (57 - $metrics.Name.Length - 1) -NoNewline
            Write-Host "║" -ForegroundColor Cyan
            Write-Host "║   Uptime: $($metrics.Uptime)" -NoNewline
            Write-Host " " * (50 - "  Uptime: $($metrics.Uptime)".Length) -NoNewline
            Write-Host "║" -ForegroundColor Cyan
            Write-Host "║   Health Checks: $($metrics.TotalChecks) ($($metrics.HealthRate) success)" -NoNewline
            Write-Host " " * (50 - "  Health Checks: $($metrics.TotalChecks) ($($metrics.HealthRate) success)".Length) -NoNewline
            Write-Host "║" -ForegroundColor Cyan
            if ($metrics.RestartCount -gt 0) {
                Write-Host "║   Restarts: $($metrics.RestartCount)" -ForegroundColor Yellow -NoNewline
                Write-Host " " * (50 - "  Restarts: $($metrics.RestartCount)".Length) -NoNewline
                Write-Host "║" -ForegroundColor Cyan
            }
        }
        
        Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
        
        if ($LogToFile) {
            Write-TheoriaLog "Session logs saved to: $script:LogFile" -Level Info
        }
        
        Write-TheoriaLog "All services stopped. Goodbye!" -Level Success
    }
}

# Execute
Start-Theoria
