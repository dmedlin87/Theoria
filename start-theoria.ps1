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
    [switch]$ShowMetrics = $false,
    [ValidateSet('dev','staging')]
    [string]$Profile = 'dev',
    [switch]$UseHttps = $false,
    [switch]$TelemetryOptIn = $false,
    [switch]$TelemetryOptOut = $false
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
$script:TelemetryConsentFile = Join-Path $script:LogsDir "telemetry-consent.json"
$script:TelemetryDataFile = Join-Path $script:LogsDir "telemetry.jsonl"
$script:TelemetryEnabled = $false
$script:PythonCandidates = @('python', 'python3', 'py')
$script:LauncherHelper = Join-Path $ProjectRoot "scripts\launcher_helpers.py"
$script:HealthCheckInterval = 10  # seconds
$script:MaxRestartAttempts = 3
$script:RestartCooldown = 5  # seconds
$script:HealthCheckTimeout = 5  # seconds
$script:StartTime = Get-Date
$script:LogBuffer = [System.Collections.Generic.List[string]]::new()
$script:AlertConfig = $null
$script:ProfilingEnabled = $EnableProfiling.IsPresent

# Load service management helpers
$serviceModulePath = Join-Path $ProjectRoot "scripts/SERVICE_MANAGEMENT.psm1"
if (Test-Path $serviceModulePath) {
    Import-Module $serviceModulePath -Force
} else {
    throw "SERVICE_MANAGEMENT.psm1 module not found at $serviceModulePath"
}

$hasCustomApiPort = $PSBoundParameters.ContainsKey('ApiPort')
$hasCustomWebPort = $PSBoundParameters.ContainsKey('WebPort')

$script:Profiles = @{
    dev = @{
        ApiPort = 8000
        WebPort = 3000
        Env = @{
            THEORIA_ENVIRONMENT = 'development'
            THEORIA_PROFILE = 'dev'
        }
    }
    staging = @{
        ApiPort = 8100
        WebPort = 3100
        Env = @{
            THEORIA_ENVIRONMENT = 'staging'
            THEORIA_PROFILE = 'staging'
        }
    }
}

$script:ProfileName = $Profile.ToLower()
if (-not $script:Profiles.ContainsKey($script:ProfileName)) {
    throw "Unknown profile '$Profile'. Supported profiles: $($script:Profiles.Keys -join ', ')"
}

$script:CurrentProfile = $script:Profiles[$script:ProfileName]
if (-not $hasCustomApiPort) {
    $ApiPort = $script:CurrentProfile.ApiPort
}
if (-not $hasCustomWebPort) {
    $WebPort = $script:CurrentProfile.WebPort
}

$scheme = if ($UseHttps) { 'https' } else { 'http' }

$script:CurrentProfile.Env.THEORIA_API_PORT = "$ApiPort"
$script:CurrentProfile.Env.THEORIA_WEB_PORT = "$WebPort"
$script:CurrentProfile.Env.NEXT_PUBLIC_API_BASE_URL = "${scheme}://localhost:$ApiPort"

$script:ApiHealthEndpoint = "${scheme}://127.0.0.1:$ApiPort/health"
$script:WebHealthEndpoint = "${scheme}://127.0.0.1:$WebPort"

$script:Certificates = @{
    Enabled = $false
    CertPath = $null
    KeyPath = $null
}
$script:HttpsRequested = [bool]$UseHttps
$script:HttpsEnabled = $false

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

$portOverrides = @{
    Api = $ApiPort
    Web = $WebPort
}

$configuration = Import-ServiceConfiguration -Path $ConfigPath -PortOverrides $portOverrides -ActiveColor $ActiveDeploymentColor
$script:Services = Initialize-ServiceState -Configuration $configuration

$script:AlertConfig = $configuration.alerts
$script:AlertsEnabled = $EnableAlerts.IsPresent -or (
    ($configuration.alerts.email.enabled -and $configuration.alerts.email.recipients.Count -gt 0) -or
    ($configuration.alerts.slack.enabled -and $configuration.alerts.slack.webhookUrl)
)

$configMetricsPort = if ($MetricsPort -gt 0) { $MetricsPort } elseif ($configuration.metrics.port) { [int]$configuration.metrics.port } else { 0 }
$configMetricsFile = if ($MetricsFile) { $MetricsFile } else { $configuration.metrics.exportFile }

if ($configMetricsFile -and -not [System.IO.Path]::IsPathRooted($configMetricsFile)) {
    $configMetricsFile = Join-Path $script:ProjectRoot $configMetricsFile
}

if (-not $script:ProfilingEnabled) {
    $script:ProfilingEnabled = $configuration.profiling.enabled
}

if ($script:Services.ContainsKey('Api')) {
    $ApiPort = $script:Services.Api.Port
    $script:ApiHealthEndpoint = $script:Services.Api.HealthEndpoint
}

if ($script:Services.ContainsKey('Web')) {
    $WebPort = $script:Services.Web.Port
    $script:WebHealthEndpoint = $script:Services.Web.HealthEndpoint
}

Register-MetricsEndpoint -Port $configMetricsPort -FilePath $configMetricsFile | Out-Null
if ($configMetricsPort -gt 0) {
    Write-TheoriaLog "Metrics endpoint available at http://localhost:$configMetricsPort/metrics" -Level Info
}
if ($configMetricsFile) {
    Write-TheoriaLog "Metrics snapshot file: $configMetricsFile" -Level Debug
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

function Get-PythonInterpreter {
    foreach ($candidate in $script:PythonCandidates) {
        try {
            $command = Get-Command $candidate -ErrorAction Stop
            if ($command) { return $command.Path }
        } catch {
            continue
        }
    }

    return $null
}

function Invoke-LauncherHelper {
    param(
        [string[]]$Arguments
    )

    if (-not (Test-Path $script:LauncherHelper)) { return $null }
    $pythonExe = Get-PythonInterpreter
    if (-not $pythonExe) { return $null }

    $processArgs = @($script:LauncherHelper) + $Arguments + @('--project-root', $script:ProjectRoot)

    try {
        $output = & $pythonExe $processArgs 2>&1
        if ($LASTEXITCODE -ne 0) {
            Write-TheoriaLog "Launcher helper exited with code $LASTEXITCODE" -Level Debug -Metadata @{ args = $Arguments }
            return $null
        }
        return $output
    } catch {
        Write-TheoriaLog "Failed to invoke launcher helper: $_" -Level Debug
        return $null
    }
}

function Get-PrerequisiteReport {
    $result = Invoke-LauncherHelper -Arguments @('check-prereqs', '--format', 'json')
    if (-not $result) { return $null }

    try {
        return $result | ConvertFrom-Json
    } catch {
        Write-TheoriaLog "Unable to parse prerequisite report: $_" -Level Debug
        return $null
    }
}

function Get-AvailablePackageManagers {
    $managers = @()
    foreach ($tool in @('winget', 'choco', 'brew')) {
        try {
            if (Get-Command $tool -ErrorAction Stop) {
                $managers += $tool
            }
        } catch {
        }
    }
    return $managers
}

function Invoke-RuntimeInstallation {
    param(
        [pscustomobject]$Runtime,
        [string[]]$AvailableManagers
    )

    if (-not $Runtime.installers) { return $false }

    foreach ($installer in $Runtime.installers) {
        if ($AvailableManagers -notcontains $installer.tool) { continue }

        $command = $installer.tool
        $args = @($installer.args)

        Write-TheoriaLog "Attempting to install $($Runtime.name) using $command..." -Level Info

        try {
            $process = Start-Process -FilePath $command -ArgumentList $args -Wait -NoNewWindow -PassThru -ErrorAction Stop
            if ($process.ExitCode -eq 0) {
                Write-TheoriaLog "$($Runtime.name) installation completed" -Level Success
                return $true
            }
        } catch {
            Write-TheoriaLog "Automatic installation failed: $_" -Level Warning
        }
    }

    return $false
}

function Get-DockerComposeCommand {
    try {
        $docker = Get-Command 'docker' -ErrorAction Stop
        $composeCheck = & $docker.Source 'compose' 'version' 2>$null
        if ($LASTEXITCODE -eq 0) {
            return @{ Command = $docker.Source; Arguments = @('compose') }
        }
    } catch {
    }

    try {
        $dockerCompose = Get-Command 'docker-compose' -ErrorAction Stop
        return @{ Command = $dockerCompose.Source; Arguments = @() }
    } catch {
    }

    return $null
}

function Invoke-DockerFallback {
    param(
        [hashtable]$ComposeCommand
    )

    if (-not $ComposeCommand) {
        Write-TheoriaLog "Docker Compose is not available on this system" -Level Error
        return
    }

    Write-TheoriaLog "Launching Docker Compose fallback (this will replace local processes)..." -Level Warning

    $env:THEORIA_PROFILE = $script:ProfileName
    $env:THEORIA_API_PORT = "$ApiPort"
    $env:THEORIA_WEB_PORT = "$WebPort"
    $env:THEORIA_USE_HTTPS = if ($script:HttpsEnabled) { '1' } else { '0' }

    $arguments = @()
    $arguments += $ComposeCommand.Arguments
    $arguments += @('up', '--build')

    try {
        & $ComposeCommand.Command $arguments
    } finally {
        $env:THEORIA_PROFILE = $null
        $env:THEORIA_API_PORT = $null
        $env:THEORIA_WEB_PORT = $null
        $env:THEORIA_USE_HTTPS = $null
    }
}

function Ensure-DevCertificates {
    if (-not $script:HttpsRequested) { return }

    $certOutputDir = Join-Path $script:ProjectRoot "infra\certs"
    $result = Invoke-LauncherHelper -Arguments @('generate-cert', '--profile', $script:ProfileName, '--output-dir', $certOutputDir)

    if (-not $result) {
        Write-TheoriaLog "Failed to generate development certificates. HTTPS mode will be disabled." -Level Warning
        $script:Certificates.Enabled = $false
        $script:HttpsEnabled = $false
        return
    }

    try {
        $certInfo = $result | ConvertFrom-Json
        $script:Certificates.Enabled = $true
        $script:Certificates.CertPath = $certInfo.cert_path
        $script:Certificates.KeyPath = $certInfo.key_path
        $script:HttpsEnabled = $true
        Write-TheoriaLog "Development certificates ready at $($certInfo.cert_path)" -Level Success
    } catch {
        Write-TheoriaLog "Could not parse certificate metadata: $_" -Level Warning
        $script:Certificates.Enabled = $false
        $script:HttpsEnabled = $false
    }
}

function Initialize-Telemetry {
    if (-not (Test-Path $script:LogsDir)) {
        New-Item -ItemType Directory -Path $script:LogsDir -Force | Out-Null
    }

    if ($TelemetryOptIn -and $TelemetryOptOut) {
        throw "Cannot specify both -TelemetryOptIn and -TelemetryOptOut"
    }

    $consent = $null

    if ($TelemetryOptIn) {
        $consent = @{ enabled = $true; updated = (Get-Date).ToString('o'); source = 'command' }
    } elseif ($TelemetryOptOut) {
        $consent = @{ enabled = $false; updated = (Get-Date).ToString('o'); source = 'command' }
    } elseif (Test-Path $script:TelemetryConsentFile) {
        try {
            $consent = Get-Content $script:TelemetryConsentFile | ConvertFrom-Json
        } catch {
            $consent = $null
        }
    }

    if (-not $consent) {
        $consent = @{ enabled = $false; updated = (Get-Date).ToString('o'); source = 'default' }
        Write-TheoriaLog "Telemetry is disabled by default. Run with -TelemetryOptIn to contribute anonymous launcher metrics." -Level Info
    } elseif ($TelemetryOptIn) {
        Write-TheoriaLog "Telemetry opt-in recorded. Thank you for helping improve Theoria!" -Level Success
    } elseif ($TelemetryOptOut) {
        Write-TheoriaLog "Telemetry has been disabled." -Level Warning
    }

    $script:TelemetryEnabled = [bool]$consent.enabled
    try {
        $consent | ConvertTo-Json -Depth 3 | Set-Content -Path $script:TelemetryConsentFile
    } catch {
        Write-TheoriaLog "Unable to persist telemetry preference: $_" -Level Debug
    }
}

function Write-TelemetryEvent {
    param(
        [string]$EventName,
        [hashtable]$Metadata
    )

    if (-not $script:TelemetryEnabled) { return }

    $payload = @{
        timestamp = (Get-Date).ToString('o')
        event = $EventName
        profile = $script:ProfileName
        metadata = $Metadata
    }

    try {
        $json = $payload | ConvertTo-Json -Compress
        Invoke-LauncherHelper -Arguments @('record-telemetry', '--event', $EventName, '--profile', $script:ProfileName, '--metadata', $json) | Out-Null
    } catch {
        Write-TheoriaLog "Failed to write telemetry event: $_" -Level Debug
    }
}

function New-ServiceEnvironment {
    $envClone = @{}
    foreach ($key in $script:CurrentProfile.Env.Keys) {
        $envClone[$key] = $script:CurrentProfile.Env[$key]
    }

    $envClone['THEORIA_USE_HTTPS'] = if ($script:HttpsEnabled) { '1' } else { '0' }
    $envClone['THEORIA_PROFILE'] = $script:ProfileName
    $envClone['THEORIA_API_PORT'] = "$ApiPort"
    $envClone['THEORIA_WEB_PORT'] = "$WebPort"

    return $envClone
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

    Update-ServiceMetricsEntry -ServiceState $service -Diagnostics $null -Profiling $null
    Get-PrometheusMetrics | Out-Null
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
    if (-not (Test-PortAvailable -Port $servicePort)) {
        Write-TheoriaLog "Port $servicePort is already in use" -Level Error
        return $false
    }

    # Verify virtual environment exists
    $venvPython = Join-Path $script:ProjectRoot ".venv\Scripts\python.exe"
    if (-not (Test-Path $venvPython)) {
        Write-TheoriaLog "Virtual environment not found at $venvPython" -Level Error
        Write-TheoriaLog "Please create a virtual environment first: python -m venv .venv" -Level Error
        return $false
    }

    $apiEnv = New-ServiceEnvironment
    $apiEnv['THEO_AUTH_ALLOW_ANONYMOUS'] = '1'
    $apiEnv['THEO_ALLOW_INSECURE_STARTUP'] = '1'
    $apiEnv['PYTHONUNBUFFERED'] = '1'

    $httpsEnabled = $script:HttpsEnabled
    if ($httpsEnabled) {
        $apiEnv['THEORIA_CERT_PATH'] = $script:Certificates.CertPath
        $apiEnv['THEORIA_KEY_PATH'] = $script:Certificates.KeyPath
    } elseif ($script:HttpsRequested) {
        Write-TheoriaLog "HTTPS requested but certificates were not generated. Falling back to HTTP." -Level Warning
        $script:ApiHealthEndpoint = "http://127.0.0.1:$ApiPort/health"
        $script:Services.Api.HealthEndpoint = $script:ApiHealthEndpoint
    }

    # Set environment variables and start API
    $scriptBlock = {
        param($Port, $ProjectRoot, $PythonExe, [hashtable]$EnvVars, [bool]$UseHttps, [hashtable]$Certificate)

        foreach ($key in $EnvVars.Keys) {
            $env:$key = $EnvVars[$key]
        }

        Set-Location $ProjectRoot
        $arguments = @('-m', 'uvicorn', 'theo.services.api.app.main:app', '--reload', '--host', '127.0.0.1', '--port', $Port)
        if ($UseHttps -and $Certificate -and $Certificate.KeyPath -and $Certificate.CertPath) {
            $arguments += @('--ssl-keyfile', $Certificate.KeyPath, '--ssl-certfile', $Certificate.CertPath)
        }
        & $PythonExe $arguments 2>&1
    }

    try {
        $job = Start-Job -ScriptBlock $scriptBlock -ArgumentList $ApiPort, $script:ProjectRoot, $venvPython, $apiEnv, $httpsEnabled, $script:Certificates
        $script:Services.Api.Job = $job
        $script:Services.Api.Status = "Starting"
        $script:Services.Api.StartTime = Get-Date

        if ($httpsEnabled) {
            $script:ApiHealthEndpoint = "https://127.0.0.1:$ApiPort/health"
            $script:Services.Api.HealthEndpoint = $script:ApiHealthEndpoint
        }

        $displayUrl = if ($httpsEnabled) { "https://localhost:$ApiPort" } else { "http://127.0.0.1:$ApiPort" }

        $success = Wait-ServiceReady -ServiceKey "Api" -Job $job -HealthEndpoint $script:ApiHealthEndpoint -MaxWaitSeconds 30 -DisplayUrl $displayUrl

        if ($success) {
            $docsUrl = if ($httpsEnabled) { "https://localhost:$ApiPort/docs" } else { "http://127.0.0.1:$ApiPort/docs" }
            Write-TheoriaLog "API Docs: $docsUrl" -Level Info
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
    if (-not (Test-PortAvailable -Port $servicePort)) {
        Write-TheoriaLog "Port $servicePort is already in use" -Level Error
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

    $webEnv = New-ServiceEnvironment
    $webEnv['PORT'] = "$WebPort"
    $webEnv['NODE_ENV'] = 'development'
    $webEnv['NEXT_PUBLIC_API_BASE_URL'] = if ($script:HttpsEnabled) { "https://localhost:$ApiPort" } else { "http://localhost:$ApiPort" }

    $httpsEnabled = $script:HttpsEnabled
    if ($httpsEnabled) {
        $webEnv['THEORIA_CERT_PATH'] = $script:Certificates.CertPath
        $webEnv['THEORIA_KEY_PATH'] = $script:Certificates.KeyPath
        $script:WebHealthEndpoint = "https://127.0.0.1:$WebPort"
    } else {
        $script:WebHealthEndpoint = "http://127.0.0.1:$WebPort"
    }
    $script:Services.Web.HealthEndpoint = $script:WebHealthEndpoint

    # Start Next.js development server
    $scriptBlock = {
        param($Port, $WebRoot, [hashtable]$EnvVars, [bool]$UseHttps, [hashtable]$Certificate)

        foreach ($key in @('THEO_AUTH_ALLOW_ANONYMOUS', 'THEO_ALLOW_INSECURE_STARTUP')) {
            Remove-Item "Env:$key" -ErrorAction SilentlyContinue
        }

        foreach ($key in $EnvVars.Keys) {
            $env:$key = $EnvVars[$key]
        }

        Push-Location $WebRoot
        try {
            $npxCommand = if ($env:OS -and $env:OS -like '*Windows*') { 'npx.cmd' } else { 'npx' }
            $arguments = @('next', 'dev', '--hostname', '0.0.0.0', '--port', $Port)
            if ($UseHttps -and $Certificate -and $Certificate.KeyPath -and $Certificate.CertPath) {
                $arguments += @('--experimental-https', '--experimental-https-key', $Certificate.KeyPath, '--experimental-https-cert', $Certificate.CertPath)
            }
            & $npxCommand $arguments 2>&1
        } finally {
            Pop-Location
        }
    }

    try {
        $job = Start-Job -ScriptBlock $scriptBlock -ArgumentList $WebPort, $script:WebRoot, $webEnv, $httpsEnabled, $script:Certificates
        $script:Services.Web.Job = $job
        $script:Services.Web.Status = "Starting"
        $script:Services.Web.StartTime = Get-Date

        $displayUrl = if ($httpsEnabled) { "https://localhost:$WebPort" } else { "http://localhost:$WebPort" }
        return Wait-ServiceReady -ServiceKey "Web" -Job $job -HealthEndpoint $script:WebHealthEndpoint -MaxWaitSeconds 60 -DisplayUrl $displayUrl

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

        if ($script:ProfilingEnabled -and $script:Services[$serviceKey].LastProfilingSnapshot) {
            $snapshot = $script:Services[$serviceKey].LastProfilingSnapshot
            $cpuSeconds = if ($snapshot.ContainsKey('CpuSecondsTotal')) { [math]::Round($snapshot.CpuSecondsTotal, 2) } else { 0 }
            $memoryMb = if ($snapshot.ContainsKey('WorkingSetBytes')) { [math]::Round($snapshot.WorkingSetBytes / 1MB, 2) } else { 0 }
            $profileLine = "  CPU(s): $cpuSeconds | Memory: ${memoryMb}MB"
            Write-Host "║$profileLine" -ForegroundColor Magenta -NoNewline
            Write-Host (" " * (59 - $profileLine.Length)) -NoNewline
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
        $service.NextHealthCheck = Get-Date
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

    $intervalSummary = ($script:Services.Keys | ForEach-Object { "$($_): $($script:Services[$_].HealthCheckInterval)s" }) -join ", "
    Write-TheoriaLog "Starting health monitor (per-service intervals: $intervalSummary)" -Level Info

    $secondsElapsed = 0

    while ($true) {
        Start-Sleep -Seconds 1
        $secondsElapsed++

        if ($ShowMetrics -and $secondsElapsed % 60 -eq 0) {
            Show-ServiceStatus
        }

        foreach ($serviceKey in $script:Services.Keys) {
            $service = $script:Services[$serviceKey]

            if ($service.Status -ne "Running") { continue }
            if (-not $service.HealthEndpoint) { continue }
            if ($service.NextHealthCheck -and (Get-Date) -lt $service.NextHealthCheck) { continue }

            $service.NextHealthCheck = (Get-Date).AddSeconds($service.HealthCheckInterval)

            $diagnostics = $null
            $isHealthy = Test-ServiceHealth -Endpoint $service.HealthEndpoint -Diagnostics ([ref]$diagnostics)
            $service.TotalHealthChecks++
            $service.LastHealthCheckDuration = $diagnostics.ResponseTime

            if ($service.AverageResponseTime -eq 0) {
                $service.AverageResponseTime = $diagnostics.ResponseTime
            } else {
                $service.AverageResponseTime = ($service.AverageResponseTime * 0.8) + ($diagnostics.ResponseTime * 0.2)
            }

            $profiling = $null
            if ($script:ProfilingEnabled) {
                $profiling = Get-ProfilingSnapshot -ProcessName $service.ProcessName
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

                if ($script:AlertsEnabled -and $service.HealthCheckFailures -eq 1) {
                    Send-ServiceAlert -AlertConfig $script:AlertConfig -ServiceName $service.Name -Message "Health check failed with status $($diagnostics.StatusCode). $($diagnostics.Error)" -Severity "critical"
                }

                $backoffMultiplier = [math]::Pow(2, [math]::Min($service.RestartCount, 4))
                $currentCooldown = $script:RestartCooldown * $backoffMultiplier

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
                if ($service.HealthCheckFailures -gt 0) {
                    Write-TheoriaLog "$($service.Name) recovered (response: $($diagnostics.ResponseTime)ms)" -Level Success
                    if ($script:AlertsEnabled) {
                        Send-ServiceAlert -AlertConfig $script:AlertConfig -ServiceName $service.Name -Message "Service recovered" -Severity "info"
                    }
                }

                $service.HealthCheckFailures = 0
                Write-TheoriaLog "$($service.Name) health check passed" -Level Debug -Metadata @{
                    response_time_ms = $diagnostics.ResponseTime
                    avg_response_time_ms = $service.AverageResponseTime
                }
            }

            Update-ServiceMetricsEntry -ServiceState $service -Diagnostics $diagnostics -Profiling $profiling
            $service.LastProfilingSnapshot = $profiling
            Get-PrometheusMetrics | Out-Null
        }
    }
}

function Resolve-Prerequisites {
    Write-Host "`n--- Pre-flight Checks ---`n" -ForegroundColor Yellow

    $report = Get-PrerequisiteReport
    $missingLocal = @()

    if ($report -and $report.runtimes) {
        foreach ($runtime in $report.runtimes) {
            $level = if ($runtime.present) { 'Success' } else { 'Warning' }
            $message = if ($runtime.present) {
                if ($runtime.version) { "$($runtime.name) detected: $($runtime.version)" } else { "$($runtime.name) detected" }
            } else {
                "$($runtime.name) missing"
            }

            Write-TheoriaLog $message -Level $level

            if (-not $runtime.present -and $runtime.category -ne 'container') {
                $missingLocal += $runtime
            }
        }
    } else {
        $pythonOk = Test-Prerequisite -Name "Python" -Command "python" -VersionArg "--version"
        $nodeOk = Test-Prerequisite -Name "Node.js" -Command "node" -VersionArg "--version"
        $npmOk = Test-Prerequisite -Name "npm" -Command "npm" -VersionArg "--version"

        if (-not $pythonOk) {
            $missingLocal += [pscustomobject]@{ name = 'Python'; guidance = 'Install Python 3.11 or newer from https://python.org'; installers = @(); category = 'local' }
        }
        if (-not $nodeOk) {
            $missingLocal += [pscustomobject]@{ name = 'Node.js'; guidance = 'Install Node.js 18+ from https://nodejs.org'; installers = @(); category = 'local' }
        }
        if (-not $npmOk) {
            $missingLocal += [pscustomobject]@{ name = 'npm'; guidance = 'Install npm (included with Node.js)'; installers = @(); category = 'local' }
        }
    }

    if ($missingLocal.Count -eq 0) {
        return 'Local'
    }

    foreach ($runtime in $missingLocal) {
        Write-TheoriaLog "$($runtime.name) is required." -Level Warning
        if ($runtime.guidance) {
            Write-TheoriaLog $runtime.guidance -Level Info
        }
    }

    $availableManagers = Get-AvailablePackageManagers
    if ($availableManagers.Count -gt 0) {
        foreach ($runtime in $missingLocal) {
            if (-not $runtime.installers) { continue }
            $installer = $runtime.installers | Where-Object { $availableManagers -contains $_.tool } | Select-Object -First 1
            if (-not $installer) { continue }

            $promptResponse = $null
            try {
                $promptResponse = Read-Host "Install $($runtime.name) now with '$($installer.display)'? (Y/N)"
            } catch {
                $promptResponse = $null
            }

            if ($promptResponse -and $promptResponse.Trim().ToLower() -in @('y', 'yes')) {
                $installed = Invoke-RuntimeInstallation -Runtime $runtime -AvailableManagers $availableManagers
                if ($installed) {
                    Write-TheoriaLog "Re-checking $($runtime.name) availability..." -Level Info
                }
            } else {
                Write-TheoriaLog "Skipped automatic installation for $($runtime.name)." -Level Warning
            }
        }
    } else {
        Write-TheoriaLog "No supported package manager (winget/choco/brew) detected for automatic installation." -Level Warning
    }

    $postReport = if ($report) { Get-PrerequisiteReport } else { $null }
    if ($postReport -and $postReport.runtimes) {
        $missingLocal = @()
        foreach ($runtime in $postReport.runtimes) {
            if (-not $runtime.present -and $runtime.category -ne 'container') {
                $missingLocal += $runtime
            }
        }
    } else {
        $remaining = @()
        if (-not (Test-Prerequisite -Name "Python" -Command "python" -VersionArg "--version")) {
            $remaining += 'Python'
        }
        if (-not (Test-Prerequisite -Name "Node.js" -Command "node" -VersionArg "--version")) {
            $remaining += 'Node.js'
        }
        if (-not (Test-Prerequisite -Name "npm" -Command "npm" -VersionArg "--version")) {
            $remaining += 'npm'
        }
        if ($remaining.Count -eq 0) {
            $missingLocal = @()
        }
    }

    if ($missingLocal.Count -eq 0) {
        return 'Local'
    }

    $composeCommand = Get-DockerComposeCommand
    if ($composeCommand) {
        Write-TheoriaLog "Local prerequisites missing; attempting Docker Compose fallback." -Level Warning
        Write-TelemetryEvent -EventName 'docker_fallback' -Metadata @{ missing = ($missingLocal.name -join ','); profile = $script:ProfileName }
        Invoke-DockerFallback -ComposeCommand $composeCommand
        return 'Docker'
    }

    Write-TheoriaLog "Cannot proceed without required runtimes. Install the missing tools listed above and try again." -Level Error
    return 'Failed'
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

    Initialize-Telemetry
    Write-TelemetryEvent -EventName 'launcher_invoked' -Metadata @{
        profile = $script:ProfileName
        requested_https = $script:HttpsRequested
        api_port = $ApiPort
        web_port = $WebPort
    }

    $prereqResult = Resolve-Prerequisites
    if ($prereqResult -eq 'Docker') {
        return
    }
    if ($prereqResult -eq 'Failed') {
        Write-TheoriaLog "Prerequisite resolution failed" -Level Error
        Write-TelemetryEvent -EventName 'launcher_failed' -Metadata @{ stage = 'prereq'; profile = $script:ProfileName }
        return
    }

    if ($script:HttpsRequested) {
        Ensure-DevCertificates
        if ($script:HttpsEnabled) {
            try {
                Add-Type @"
using System.Net;
using System.Security.Cryptography.X509Certificates;
using System.Net.Security;
public class TheoriaBypassCerts {
    public static bool Ignore(object sender, X509Certificate certificate, X509Chain chain, System.Net.Security.SslPolicyErrors sslPolicyErrors) {
        return true;
    }
}
"@
            } catch {}

            try {
                [System.Net.ServicePointManager]::ServerCertificateValidationCallback = {[TheoriaBypassCerts]::Ignore}
            } catch {}
        }
    }

    $schemeForEnv = if ($script:HttpsEnabled) { 'https' } else { 'http' }
    $script:CurrentProfile.Env.NEXT_PUBLIC_API_BASE_URL = "${schemeForEnv}://localhost:$ApiPort"
    $script:ApiHealthEndpoint = "${schemeForEnv}://127.0.0.1:$ApiPort/health"
    $script:WebHealthEndpoint = "${schemeForEnv}://127.0.0.1:$WebPort"
    $script:Services.Api.HealthEndpoint = $script:ApiHealthEndpoint
    $script:Services.Web.HealthEndpoint = $script:WebHealthEndpoint

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
            Write-TelemetryEvent -EventName 'launcher_failed' -Metadata @{ stage = 'env'; profile = $script:ProfileName }
            return
        }
    }

    Write-Host "`n--- Starting Services ---`n" -ForegroundColor Yellow

    # Start API first
    $apiStarted = Start-TheoriaApi
    if (-not $apiStarted) {
        Write-TheoriaLog "Failed to start API, aborting" -Level Error
        Write-TelemetryEvent -EventName 'launcher_failed' -Metadata @{ stage = 'api'; profile = $script:ProfileName }
        return
    }

    # Start Web UI
    $webStarted = Start-TheoriaWeb
    if (-not $webStarted) {
        Write-TheoriaLog "Failed to start Web UI, stopping API" -Level Error
        Stop-TheoriaService -ServiceKey "Api"
        Write-TelemetryEvent -EventName 'launcher_failed' -Metadata @{ stage = 'web'; profile = $script:ProfileName }
        return
    }

    # Success banner
    $apiDisplay = if ($script:HttpsEnabled) { "https://localhost:$ApiPort" } else { "http://127.0.0.1:$ApiPort" }
    $webDisplay = if ($script:HttpsEnabled) { "https://localhost:$WebPort" } else { "http://localhost:$WebPort" }
    $docsDisplay = if ($script:HttpsEnabled) { "https://localhost:$ApiPort/docs" } else { "http://127.0.0.1:$ApiPort/docs" }

    Write-Host "`n╔══════════════════════════════════════════════════════════╗" -ForegroundColor Green
    Write-Host "║                                                          ║" -ForegroundColor Green
    Write-Host "║                 " -ForegroundColor Green -NoNewline
    Write-Host "🚀 THEORIA IS READY! 🚀" -ForegroundColor White -NoNewline
    Write-Host "                 ║" -ForegroundColor Green
    Write-Host "║                                                          ║" -ForegroundColor Green
    Write-Host ("║" + ("  API:     $apiDisplay").PadRight(58) + "║") -ForegroundColor Green
    Write-Host ("║" + ("  Web UI:  $webDisplay").PadRight(58) + "║") -ForegroundColor Green
    Write-Host ("║" + ("  Docs:    $docsDisplay").PadRight(58) + "║") -ForegroundColor Green
    Write-Host "║                                                          ║" -ForegroundColor Green
    Write-Host "║  Features:                                               ║" -ForegroundColor Green
    Write-Host "║    ✓ Auto-recovery with exponential backoff             ║" -ForegroundColor Green
    $intervalSummary = ($script:Services.Keys | ForEach-Object { "$($script:Services[$_].Name): $($script:Services[$_].HealthCheckInterval)s" }) -join ", "
    Write-Host "║    ✓ Health monitoring (intervals: $intervalSummary)            ║" -ForegroundColor Green
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

    Write-TelemetryEvent -EventName 'launcher_ready' -Metadata @{ profile = $script:ProfileName; https = $script:HttpsEnabled; api_port = $ApiPort; web_port = $WebPort }

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

        Stop-MetricsEndpoint

        # Graceful shutdown with timeout
        Stop-TheoriaService -ServiceKey "Web"
        Stop-TheoriaService -ServiceKey "Api"
        
        # Generate session summary
        $totalRuntime = (Get-Date) - $script:StartTime
        Write-TelemetryEvent -EventName 'launcher_shutdown' -Metadata @{ profile = $script:ProfileName; runtime_seconds = [math]::Round($totalRuntime.TotalSeconds, 2) }
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
