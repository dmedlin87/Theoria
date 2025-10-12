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
$script:LogBuffer = [System.Collections.Generic.List[string]]::new()

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
    
    # File output (structured JSON) - buffered for performance
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
            
            $script:LogBuffer.Add($logEntry)
            
            # Flush buffer every 10 entries to reduce I/O
            if ($script:LogBuffer.Count -ge 10) {
                Add-Content -Path $script:LogFile -Value ($script:LogBuffer -join "`n") -ErrorAction SilentlyContinue
                $script:LogBuffer.Clear()
            }
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
        $result = & $Command $VersionArg 2>&1
        if ($LASTEXITCODE -eq 0) {
            $version = if ($result -is [array]) { $result[0].ToString().Trim() } else { $result.ToString().Trim() }
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
    
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $result = @{
        Healthy = $false
        StatusCode = $null
        ResponseTime = 0
        Error = $null
    }
    
    try {
        $response = Invoke-WebRequest -Uri $Endpoint -TimeoutSec $script:HealthCheckTimeout -UseBasicParsing -ErrorAction Stop -MaximumRedirection 0
        $result.Healthy = $response.StatusCode -eq 200
        $result.StatusCode = $response.StatusCode
    } catch {
        $result.Error = $_.Exception.Message
        $result.StatusCode = if ($_.Exception.Response) { $_.Exception.Response.StatusCode.value__ } else { 0 }
    } finally {
        $stopwatch.Stop()
        $result.ResponseTime = $stopwatch.Elapsed.TotalMilliseconds
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

function Wait-ServiceReady {
    param(
        [string]$ServiceKey,
        [System.Management.Automation.Job]$Job,
        [string]$HealthEndpoint,
        [int]$MaxWaitSeconds,
        [string]$DisplayUrl
    )
    
    Write-TheoriaLog "Waiting for $($script:Services[$ServiceKey].Name) to become ready..." -Level Debug
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $checkInterval = 500  # milliseconds
    
    while ($stopwatch.Elapsed.TotalSeconds -lt $MaxWaitSeconds) {
        # Check if job failed early
        if ($Job.State -eq "Failed" -or $Job.State -eq "Stopped") {
            $stopwatch.Stop()
            $errorOutput = Receive-Job $Job 2>&1 | Out-String
            $script:Services[$ServiceKey].LastError = $errorOutput
            Write-TheoriaLog "$($script:Services[$ServiceKey].Name) failed to start:" -Level Error -Metadata @{ error = $errorOutput }
            Write-TheoriaLog $errorOutput -Level Error
            $script:Services[$ServiceKey].StartTime = $null
            return $false
        }
        
        # Test health
        $diagnostics = $null
        if (Test-ServiceHealth -Endpoint $HealthEndpoint -Diagnostics ([ref]$diagnostics)) {
            $stopwatch.Stop()
            $startupTime = [math]::Round($stopwatch.Elapsed.TotalSeconds, 1)
            $script:Services[$ServiceKey].Status = "Running"
            Write-TheoriaLog "$($script:Services[$ServiceKey].Name) is ready at $DisplayUrl (startup time: ${startupTime}s)" -Level Success -Metadata @{ startup_time_seconds = $startupTime; response_time_ms = $diagnostics.ResponseTime }
            return $true
        }
        
        Start-Sleep -Milliseconds $checkInterval
    }
    
    $stopwatch.Stop()
    
    # Capture job output on timeout for diagnostics
    $jobOutput = Receive-Job $Job -Keep 2>&1 | Out-String
    if ($jobOutput.Trim()) {
        Write-TheoriaLog "$($script:Services[$ServiceKey].Name) output during timeout:" -Level Warning
        Write-TheoriaLog $jobOutput -Level Error
    }
    
    $script:Services[$ServiceKey].LastError = "Timeout after ${MaxWaitSeconds}s"
    Write-TheoriaLog "$($script:Services[$ServiceKey].Name) did not become healthy within ${MaxWaitSeconds}s" -Level Warning -Metadata @{ timeout_seconds = $MaxWaitSeconds; job_state = $Job.State }
    Write-TheoriaLog "Job state: $($Job.State) - Check output above for errors" -Level Error
    $script:Services[$ServiceKey].StartTime = $null
    return $false
}

function Start-TheoriaApi {
    Write-TheoriaLog "Starting Theoria API on port $ApiPort..." -Level Info
    
    # Check port availability
    if (-not (Test-PortAvailable -Port $ApiPort)) {
        Write-TheoriaLog "Port $ApiPort is already in use" -Level Error
        return $false
    }
    
    # Verify virtual environment exists
    $venvPython = Join-Path $script:ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-TheoriaLog "Virtual environment not found at $venvPython" -Level Error
        Write-TheoriaLog "Please create a virtual environment first: python -m venv .venv" -Level Error
        return $false
    }
    
    # Set environment variables and start API
    $scriptBlock = {
        param($Port, $ProjectRoot, $PythonExe)
        
        $env:THEO_AUTH_ALLOW_ANONYMOUS = "1"
        $env:THEO_ALLOW_INSECURE_STARTUP = "1"
        $env:PYTHONUNBUFFERED = "1"
        
        Set-Location $ProjectRoot
        & $PythonExe -m uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port $Port 2>&1
    }
    
    try {
        $job = Start-Job -ScriptBlock $scriptBlock -ArgumentList $ApiPort, $script:ProjectRoot, $venvPython
        $script:Services.Api.Job = $job
        $script:Services.Api.Status = "Starting"
        $script:Services.Api.StartTime = Get-Date
        
        $success = Wait-ServiceReady -ServiceKey "Api" -Job $job -HealthEndpoint $script:ApiHealthEndpoint -MaxWaitSeconds 30 -DisplayUrl "http://127.0.0.1:$ApiPort"
        
        if ($success) {
            Write-TheoriaLog "API Docs: http://127.0.0.1:$ApiPort/docs" -Level Info
        }
        
        return $success
        
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
            if ($LASTEXITCODE -eq 0) {
                Write-TheoriaLog "Dependencies installed successfully" -Level Success
            } else {
                Write-TheoriaLog "npm install completed with warnings" -Level Warning
            }
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
        
        return Wait-ServiceReady -ServiceKey "Web" -Job $job -HealthEndpoint $script:WebHealthEndpoint -MaxWaitSeconds 45 -DisplayUrl "http://localhost:$WebPort"
        
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
        [math]::Round((($service.TotalHealthChecks - $service.HealthCheckFailures) / $service.TotalHealthChecks) * 100, 1)
    } else { 0 }
    
    return [PSCustomObject]@{
        Name = $service.Name
        Status = $service.Status
        Uptime = if ($uptime) { $uptime.ToString('hh\:mm\:ss') } else { "N/A" }
        UptimeSeconds = if ($uptime) { [int]$uptime.TotalSeconds } else { 0 }
        HealthRate = "${healthRate}%"
        AvgResponseTime = "$([math]::Round($service.AverageResponseTime, 1))ms"
        LastResponseTime = "$([math]::Round($service.LastHealthCheckDuration, 1))ms"
        RestartCount = $service.RestartCount
        TotalChecks = $service.TotalHealthChecks
        Failures = $service.HealthCheckFailures
    }
}

function Show-ServiceStatus {
    $sb = [System.Text.StringBuilder]::new()
    [void]$sb.AppendLine("`n╔══════════════════════════════════════════════════════════╗")
    [void]$sb.AppendLine("║               SERVICE STATUS DASHBOARD                  ║")
    [void]$sb.AppendLine("╠══════════════════════════════════════════════════════════╣")
    
    Write-Host $sb.ToString() -ForegroundColor Cyan -NoNewline
    $sb.Clear()
    
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
        $padding1 = 55 - $metrics.Name.Length - $metrics.Status.Length - 4
        Write-Host (" " * $padding1) -NoNewline
        Write-Host "║" -ForegroundColor Cyan
        
        $metricsLine = "  Uptime: $($metrics.Uptime) | Health: $($metrics.HealthRate) | Avg Response: $($metrics.AvgResponseTime)"
        Write-Host "║$metricsLine" -NoNewline
        $padding2 = 59 - $metricsLine.Length
        Write-Host (" " * $padding2) -NoNewline
        Write-Host "║" -ForegroundColor Cyan
        
        if ($metrics.RestartCount -gt 0) {
            $restartLine = "  Restarts: $($metrics.RestartCount)"
            Write-Host "║$restartLine" -ForegroundColor Yellow -NoNewline
            Write-Host (" " * (59 - $restartLine.Length)) -NoNewline
            Write-Host "║" -ForegroundColor Cyan
        }
    }
    
    $totalUptime = ((Get-Date) - $script:StartTime).ToString('hh\:mm\:ss')
    $runtimeLine = "Total Runtime: $totalUptime"
    Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
    Write-Host "║ $runtimeLine" -NoNewline
    Write-Host (" " * (59 - $runtimeLine.Length - 1)) -NoNewline
    Write-Host "║" -ForegroundColor Cyan
    Write-Host "╚══════════════════════════════════════════════════════════╝" -ForegroundColor Cyan
}

function Invoke-ServiceRestart {
    param(
        [string]$ServiceKey
    )
    
    $service = $script:Services[$ServiceKey]
    
    Stop-TheoriaService -ServiceKey $ServiceKey
    Start-Sleep -Seconds 2
    
    $success = switch ($ServiceKey) {
        "Api" { Start-TheoriaApi }
        "Web" { Start-TheoriaWeb }
        default { $false }
    }
    
    if ($success) {
        $service.RestartCount++
        $service.LastRestartTime = Get-Date
        Write-TheoriaLog "$($service.Name) restarted successfully" -Level Success -Metadata @{ restart_count = $service.RestartCount }
    } else {
        Write-TheoriaLog "$($service.Name) restart failed" -Level Error
    }
    
    return $success
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
            
            # Calculate rolling average response time (exponential moving average)
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
                        
                        Invoke-ServiceRestart -ServiceKey $serviceKey
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
        
        # Flush any remaining logs
        if ($LogToFile -and $script:LogBuffer.Count -gt 0) {
            try {
                Add-Content -Path $script:LogFile -Value ($script:LogBuffer -join "`n") -ErrorAction SilentlyContinue
                $script:LogBuffer.Clear()
            } catch {}
        }
        
        # Graceful shutdown with timeout
        Stop-TheoriaService -ServiceKey "Web"
        Stop-TheoriaService -ServiceKey "Api"
        
        # Generate session summary
        $totalRuntime = (Get-Date) - $script:StartTime
        Write-Host "`n╔══════════════════════════════════════════════════════════╗" -ForegroundColor Cyan
        Write-Host "║                   SESSION SUMMARY                        ║" -ForegroundColor Cyan
        Write-Host "╠══════════════════════════════════════════════════════════╣" -ForegroundColor Cyan
        $runtimeStr = $totalRuntime.ToString('hh\:mm\:ss')
        $runtimeLine = "Total Runtime: $runtimeStr"
        Write-Host "║ $runtimeLine" -NoNewline
        Write-Host (" " * (59 - $runtimeLine.Length - 1)) -NoNewline
        Write-Host "║" -ForegroundColor Cyan
        
        foreach ($serviceKey in $script:Services.Keys) {
            $metrics = Get-ServiceMetrics -ServiceKey $serviceKey
            $nameLine = "$($metrics.Name):"
            Write-Host "║ $nameLine" -NoNewline
            Write-Host (" " * (59 - $nameLine.Length - 1)) -NoNewline
            Write-Host "║" -ForegroundColor Cyan
            
            $uptimeLine = "  Uptime: $($metrics.Uptime)"
            Write-Host "║$uptimeLine" -NoNewline
            Write-Host (" " * (59 - $uptimeLine.Length)) -NoNewline
            Write-Host "║" -ForegroundColor Cyan
            
            $healthLine = "  Health Checks: $($metrics.TotalChecks) ($($metrics.HealthRate) success)"
            Write-Host "║$healthLine" -NoNewline
            Write-Host (" " * (59 - $healthLine.Length)) -NoNewline
            Write-Host "║" -ForegroundColor Cyan
            
            if ($metrics.RestartCount -gt 0) {
                $restartLine = "  Restarts: $($metrics.RestartCount)"
                Write-Host "║$restartLine" -ForegroundColor Yellow -NoNewline
                Write-Host (" " * (59 - $restartLine.Length)) -NoNewline
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
