#requires -Version 7.0

<#!
.SYNOPSIS
    Helper module for orchestrating Theoria services with enhanced health monitoring.

.DESCRIPTION
    Provides configuration loading, dependency validation, metrics export, alert delivery,
    and deployment slot helpers that are leveraged by start-theoria.ps1 and companion tooling.

.NOTES
    This module is intentionally self-contained so it can be imported from both
    Windows PowerShell and cross-platform PowerShell (pwsh).
#>

using namespace System.Collections.Generic

$script:Configuration = $null
$script:MetricsState = [ordered]@{
    StartTime     = Get-Date
    Services      = [ordered]@{}
    Alerts        = New-Object List[hashtable]
    MetricsPort   = 0
    MetricsFile   = $null
    MetricsServer = $null
    MetricsJob    = $null
}

function Resolve-Template {
    param(
        [Parameter(Mandatory)][string]$Value,
        [hashtable]$Tokens
    )

    if (-not $Tokens) { return $Value }

    $resolved = $Value
    foreach ($key in $Tokens.Keys) {
        $resolved = $resolved -replace "\{$key\}", [string]$Tokens[$key]
    }
    return $resolved
}

function Import-ServiceConfiguration {
    [CmdletBinding()]
    param(
        [string]$Path,
        [hashtable]$PortOverrides = @{},
        [string]$ActiveColor = "blue"
    )

    if (-not (Test-Path $Path)) {
        throw "Service configuration file not found at $Path"
    }

    try {
        $json = Get-Content -Path $Path -Raw -Encoding UTF8
        $config = $json | ConvertFrom-Json -AsHashtable
    } catch {
        throw "Failed to parse service configuration: $($_.Exception.Message)"
    }

    $config.ActiveDeploymentColor = if ($ActiveColor) { $ActiveColor.ToLowerInvariant() } else { "blue" }
    $script:Configuration = $config

    foreach ($svc in $config.services) {
        if ($PortOverrides.ContainsKey($svc.key)) {
            $override = $PortOverrides[$svc.key]
            if ($svc.deployment -and $svc.deployment.slots -and $svc.deployment.slots.ContainsKey($config.ActiveDeploymentColor)) {
                $svc.deployment.slots[$config.ActiveDeploymentColor].port = $override
            } else {
                $svc.port = $override
            }
        }
    }

    return $config
}

function Initialize-ServiceState {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]$Configuration,
        [hashtable]$ExtraTokens = @{}
    )

    $services = @{}

    foreach ($svc in $Configuration.services) {
        $tokens = @{} + $ExtraTokens
        if ($svc.port) { $tokens["Port"] = $svc.port }
        if ($svc.tokens) {
            foreach ($tokenKey in $svc.tokens.Keys) {
                $tokens[$tokenKey] = $svc.tokens[$tokenKey]
            }
        }

        $healthInterval = if ($svc.healthIntervalSeconds) { [int]$svc.healthIntervalSeconds } else { 10 }
        $processName = if ($svc.processName) { $svc.processName } else { $null }
        $deployment = $svc.deployment
        $activeSlot = $null
        if ($deployment -and $deployment.slots) {
            $color = $Configuration.ActiveDeploymentColor
            if (-not $deployment.slots.ContainsKey($color)) {
                throw "Service '$($svc.name)' does not define deployment slot '$color'."
            }
            $activeSlot = $deployment.slots[$color]
            if ($activeSlot.port) {
                $tokens["Port"] = $activeSlot.port
            }
        }

        $healthEndpoint = if ($activeSlot -and $activeSlot.healthEndpoint) { $activeSlot.healthEndpoint } elseif ($svc.healthEndpoint) { $svc.healthEndpoint } else { $null }
        if ($healthEndpoint) {
            $healthEndpoint = Resolve-Template -Value $healthEndpoint -Tokens $tokens
        }

        $metricsName = if ($svc.metricsLabel) { $svc.metricsLabel } else { $svc.key }

        $dependencies = @()
        if ($svc.ContainsKey('dependencies') -and $svc.dependencies) {
            $dependencies = @($svc.dependencies | Where-Object { $_ })
        }

        $services[$svc.key] = @{
            Name                     = $svc.name
            Key                      = $svc.key
            Port                     = if ($tokens.ContainsKey("Port")) { [int]$tokens["Port"] } else { $null }
            HealthEndpoint           = $healthEndpoint
            HealthCheckInterval      = $healthInterval
            NextHealthCheck          = Get-Date
            OverrideUrl              = if ($svc.overrideUrl) { Resolve-Template -Value $svc.overrideUrl -Tokens $tokens } else { $null }
            Dependencies             = $dependencies
            ProcessName              = $processName
            Deployment               = $deployment
            MetricsLabel             = $metricsName
            Job                      = $null
            RestartCount             = 0
            LastRestartTime          = $null
            Status                   = "Not Started"
            StartTime                = $null
            HealthCheckFailures      = 0
            TotalHealthChecks        = 0
            LastHealthCheckDuration  = 0
            AverageResponseTime      = 0
            LastError                = $null
            LastHealthCheckTimestamp = $null
            LastProfilingSnapshot    = $null
        }
    }

    return $services
}

function Invoke-DependencyValidation {
    [CmdletBinding()]
    param(
        [hashtable]$Services,
        [string]$ServiceKey
    )

    $svc = $Services[$ServiceKey]
    if (-not $svc -or -not $svc.Dependencies) { return $true }

    foreach ($depKey in $svc.Dependencies) {
        if (-not $Services.ContainsKey($depKey)) {
            throw "Service '$($svc.Name)' declares missing dependency '$depKey'."
        }
        $depState = $Services[$depKey]
        if ($depState.Status -ne "Running") {
            return $false
        }
    }
    return $true
}

function Register-MetricsEndpoint {
    [CmdletBinding()]
    param(
        [int]$Port,
        [string]$FilePath
    )

    $script:MetricsState.MetricsPort = $Port
    $script:MetricsState.MetricsFile = $FilePath

    if ($script:MetricsState.MetricsJob) {
        Stop-Job -Job $script:MetricsState.MetricsJob -ErrorAction SilentlyContinue
        Remove-Job -Job $script:MetricsState.MetricsJob -Force -ErrorAction SilentlyContinue
        $script:MetricsState.MetricsJob = $null
    }

    if ($Port -gt 0) {
        $modulePath = Join-Path $PSScriptRoot "SERVICE_MANAGEMENT.psm1"
        $job = Start-Job -ScriptBlock {
            param($MetricsPort, $MetricsFile, $ModulePath)
            $listener = [System.Net.HttpListener]::new()
            $prefix = "http://*:$MetricsPort/"
            $listener.Prefixes.Add($prefix)
            $listener.Start()
            try {
                while ($listener.IsListening) {
                    $context = $listener.GetContext()
                    $request = $context.Request
                    $response = $context.Response
                    if ($request.Url.AbsolutePath -eq "/metrics") {
                        $content = $null
                        if ($MetricsFile -and (Test-Path $MetricsFile)) {
                            $content = Get-Content -Path $MetricsFile -Raw -ErrorAction SilentlyContinue
                        }

                        if (-not $content) {
                            Import-Module $ModulePath -Force | Out-Null
                            $content = (Get-PrometheusMetrics) -join "`n"
                        }

                        $bytes = [System.Text.Encoding]::UTF8.GetBytes($content)
                        $response.ContentType = "text/plain; version=0.0.4"
                        $response.OutputStream.Write($bytes, 0, $bytes.Length)
                    } else {
                        $response.StatusCode = 404
                    }
                    $response.OutputStream.Close()
                }
            } finally {
                $listener.Stop()
                $listener.Close()
            }
        } -ArgumentList $Port, $FilePath, $modulePath
        $script:MetricsState.MetricsJob = $job
    }
}

function Stop-MetricsEndpoint {
    if ($script:MetricsState.MetricsJob) {
        try {
            Stop-Job -Job $script:MetricsState.MetricsJob -ErrorAction SilentlyContinue | Out-Null
            Remove-Job -Job $script:MetricsState.MetricsJob -Force -ErrorAction SilentlyContinue | Out-Null
        } catch {}
        $script:MetricsState.MetricsJob = $null
    }
}

function Get-PrometheusMetrics {
    $lines = New-Object List[string]
    $uptime = (Get-Date) - $script:MetricsState.StartTime
    $lines.Add("theoria_manager_uptime_seconds $([math]::Round($uptime.TotalSeconds, 2))")

    foreach ($svcKey in $script:MetricsState.Services.Keys) {
        $entry = $script:MetricsState.Services[$svcKey]
        $labels = "service=\"$($entry.service)\""
        $lines.Add("theoria_service_status{$labels} $($entry.status)")
        $lines.Add("theoria_service_restarts{$labels} $($entry.restart_count)")
        $lines.Add("theoria_service_healthchecks_total{$labels} $($entry.total_checks)")
        $lines.Add("theoria_service_healthcheck_failures_total{$labels} $($entry.failures)")
        $lines.Add("theoria_service_last_response_ms{$labels} $($entry.last_response_ms)")
        $lines.Add("theoria_service_average_response_ms{$labels} $([math]::Round($entry.avg_response_ms,2))")
        $lines.Add("theoria_service_uptime_seconds{$labels} $([math]::Round($entry.uptime_seconds,2))")
        if ($entry.ContainsKey('cpu_seconds_total')) {
            $lines.Add("theoria_service_cpu_seconds_total{$labels} $([math]::Round($entry.cpu_seconds_total,2))")
        }
        if ($entry.ContainsKey('working_set_bytes')) {
            $lines.Add("theoria_service_working_set_bytes{$labels} $([math]::Round($entry.working_set_bytes,2))")
        }
    }

    foreach ($alert in $script:MetricsState.Alerts) {
        $labels = "service=\"$($alert.service)\",severity=\"$($alert.severity)\""
        $lines.Add("theoria_service_alerts_total{$labels} $($alert.total)")
    }

    if ($script:MetricsState.MetricsFile) {
        try {
            $directory = Split-Path -Parent $script:MetricsState.MetricsFile
            if ($directory -and -not (Test-Path $directory)) {
                New-Item -ItemType Directory -Path $directory -Force | Out-Null
            }
            Set-Content -Path $script:MetricsState.MetricsFile -Value ($lines -join "`n") -Encoding UTF8
        } catch {}
    }

    return $lines
}

function Update-ServiceMetricsEntry {
    [CmdletBinding()]
    param(
        [hashtable]$ServiceState,
        [hashtable]$Diagnostics,
        [hashtable]$Profiling
    )

    if (-not $ServiceState) { return }

    $key = $ServiceState.Key
    $entry = @{
        service           = $ServiceState.MetricsLabel
        status            = if ($ServiceState.Status -eq "Running") { 1 } else { 0 }
        restart_count     = $ServiceState.RestartCount
        total_checks      = $ServiceState.TotalHealthChecks
        failures          = $ServiceState.HealthCheckFailures
        last_response_ms  = [math]::Round($ServiceState.LastHealthCheckDuration, 2)
        avg_response_ms   = [math]::Round($ServiceState.AverageResponseTime, 2)
        uptime_seconds    = if ($ServiceState.StartTime) { ((Get-Date) - $ServiceState.StartTime).TotalSeconds } else { 0 }
    }

    if ($Profiling) {
        if ($Profiling.ContainsKey('CpuSecondsTotal')) {
            $entry.cpu_seconds_total = $Profiling.CpuSecondsTotal
        }
        if ($Profiling.ContainsKey('WorkingSetBytes')) {
            $entry.working_set_bytes = $Profiling.WorkingSetBytes
        }
    }

    $script:MetricsState.Services[$key] = $entry
}

function Register-AlertEvent {
    param(
        [string]$ServiceName,
        [string]$Severity
    )

    $existing = $script:MetricsState.Alerts | Where-Object { $_.service -eq $ServiceName -and $_.severity -eq $Severity }
    if ($existing) {
        $existing[0].total++
    } else {
        $script:MetricsState.Alerts.Add(@{ service = $ServiceName; severity = $Severity; total = 1 }) | Out-Null
    }
}

function Send-ServiceAlert {
    [CmdletBinding()]
    param(
        [hashtable]$AlertConfig,
        [string]$ServiceName,
        [string]$Message,
        [string]$Severity = "warning"
    )

    if (-not $AlertConfig) { return }

    Register-AlertEvent -ServiceName $ServiceName -Severity $Severity

    if ($AlertConfig.email -and $AlertConfig.email.enabled -and $AlertConfig.email.recipients) {
        try {
            $smtp = $AlertConfig.email
            $mailParams = @{
                To       = $smtp.recipients -join ','
                From     = $smtp.from
                Subject  = "[Theoria] $ServiceName - $Severity"
                Body     = $Message
                SmtpServer = $smtp.smtpServer
            }
            if ($smtp.containsKey('port')) { $mailParams['Port'] = [int]$smtp.port }
            if ($smtp.containsKey('credential')) { $mailParams['Credential'] = $smtp.credential }
            Send-MailMessage @mailParams
        } catch {
            Write-Verbose "Failed to send email alert: $($_.Exception.Message)"
        }
    }

    if ($AlertConfig.slack -and $AlertConfig.slack.enabled -and $AlertConfig.slack.webhookUrl) {
        try {
            $payload = @{ text = "[$Severity] $ServiceName - $Message" } | ConvertTo-Json
            Invoke-RestMethod -Uri $AlertConfig.slack.webhookUrl -Method Post -ContentType 'application/json' -Body $payload -ErrorAction Stop
        } catch {
            Write-Verbose "Failed to send Slack alert: $($_.Exception.Message)"
        }
    }
}

function Get-ProfilingSnapshot {
    param(
        [string]$ProcessName
    )

    if (-not $ProcessName) { return $null }

    try {
        $proc = Get-Process -Name $ProcessName -ErrorAction Stop | Select-Object -First 1
        return @{
            CpuSecondsTotal = $proc.TotalProcessorTime.TotalSeconds
            WorkingSetBytes = [double]$proc.WorkingSet64
        }
    } catch {
        return $null
    }
}

Export-ModuleMember -Function *
