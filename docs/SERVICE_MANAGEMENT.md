# Service Management & Health Monitoring

## Overview

The TheoEngine service launcher (`start-theoria.ps1`) is an intelligent orchestration system that manages the full-stack application lifecycle with built-in resilience, monitoring, and diagnostic capabilities.

## Key Features

### 🛡️ Auto-Recovery with Exponential Backoff

- Automatically restarts failed services
- Implements exponential backoff (5s → 10s → 20s → 40s → 80s)
- Prevents restart loops with intelligent cooldown periods
- Maximum 3 restart attempts per service

### 📊 Real-Time Metrics & Monitoring

- Continuous health checks every 10 seconds
- Response time tracking (current and rolling average)
- Service uptime monitoring
- Health check success rate calculation
- Optional live status dashboard

### 📝 Structured Logging

- Console output with color-coded log levels
- Optional JSON-formatted file logging
- Metadata enrichment for all events
- Searchable log files for post-mortem analysis

### 🎯 Enhanced Health Checks

- Detailed diagnostic information (status codes, response times, errors)
- HTTP timeout protection
- Connection failure detection
- Job state monitoring

### 🎨 Developer Experience

- Beautiful console UI with status dashboards
- Session summaries on shutdown
- Verbose mode for troubleshooting
- Graceful shutdown with uptime reporting

## Usage

### Basic Usage

```powershell
# Start with default settings
.\start-theoria.ps1

# Start with custom ports
.\start-theoria.ps1 -ApiPort 8010 -WebPort 3100

# Start with verbose logging
.\start-theoria.ps1 -Verbose
```

### Advanced Usage

```powershell
# Enable file logging and real-time metrics
.\start-theoria.ps1 -LogToFile -ShowMetrics

# Disable health monitoring (faster startup, less resilient)
.\start-theoria.ps1 -SkipHealthChecks

# Full monitoring setup
.\start-theoria.ps1 -Verbose -LogToFile -ShowMetrics
```

## Architecture

### Service Lifecycle

```
┌─────────────────────────────────────────────────────────┐
│                   START-THEORIA                         │
└────────────┬────────────────────────────────────────────┘
             │
             ├─► Prerequisites Check (Python, Node, npm)
             │
             ├─► Environment Setup (.env validation)
             │
             ├─► API Service Startup
             │   ├─► Port availability check
             │   ├─► Uvicorn process launch
             │   ├─► Health endpoint polling (30s timeout)
             │   └─► Ready confirmation
             │
             ├─► Web Service Startup
             │   ├─► Dependency installation (if needed)
             │   ├─► Port availability check
             │   ├─► Next.js process launch
             │   ├─► Health endpoint polling (45s timeout)
             │   └─► Ready confirmation
             │
             └─► Health Monitoring Loop
                 ├─► Service health checks (10s interval)
                 ├─► Metrics collection
                 ├─► Auto-recovery on failure
                 └─► Status dashboard (optional, 60s interval)
```

### Health Check Flow

```
┌─────────────────────────────────────────────────────────┐
│              HEALTH CHECK EXECUTION                     │
└────────────┬────────────────────────────────────────────┘
             │
             ├─► HTTP Request to Health Endpoint
             │   ├─► Success (200 OK)
             │   │   ├─► Record response time
             │   │   ├─► Update rolling average
             │   │   └─► Clear failure counter
             │   │
             │   └─► Failure (timeout/error/non-200)
             │       ├─► Increment failure counter
             │       ├─► Log error details
             │       └─► Trigger recovery logic
             │
             └─► Recovery Decision
                 ├─► Check restart count < max attempts (3)
                 ├─► Calculate backoff: 5s × 2^restart_count
                 ├─► Check cooldown period elapsed
                 ├─► Stop failed service
                 ├─► Wait 2 seconds
                 ├─► Restart service
                 └─► Log result
```

### Exponential Backoff Schedule

| Restart Attempt | Cooldown Period |
|-----------------|-----------------|
| 1st             | 5 seconds       |
| 2nd             | 10 seconds      |
| 3rd             | 20 seconds      |
| 4th+            | 40 seconds      |

## Configuration

### Script Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `$ApiPort` | 8000 | FastAPI server port |
| `$WebPort` | 3000 | Next.js dev server port |
| `$HealthCheckInterval` | 10s | Time between health checks |
| `$MaxRestartAttempts` | 3 | Maximum auto-restart attempts |
| `$RestartCooldown` | 5s | Base cooldown before retry |
| `$HealthCheckTimeout` | 5s | HTTP request timeout |

### Service State Tracking

Each service maintains the following state:

- **Name**: Display name
- **Job**: PowerShell background job
- **Port**: Network port
- **HealthEndpoint**: Health check URL
- **RestartCount**: Number of restarts performed
- **LastRestartTime**: Timestamp of last restart
- **Status**: Current state (Not Started, Starting, Running, Stopped)
- **StartTime**: Service start timestamp
- **HealthCheckFailures**: Cumulative failure count
- **TotalHealthChecks**: Total checks performed
- **LastHealthCheckDuration**: Most recent response time (ms)
- **AverageResponseTime**: Rolling average response time (ms)
- **LastError**: Most recent error message

## Metrics & Diagnostics

### Health Check Diagnostics

Each health check returns:

```powershell
@{
    Healthy = $true/$false          # Overall health status
    StatusCode = 200                # HTTP status code
    ResponseTime = 123.45           # Response time in ms
    Error = "Connection timeout"    # Error message (if failed)
}
```

### Service Metrics

```powershell
@{
    Name = "Theoria API"
    Status = "Running"
    Uptime = "01:23:45"            # hh:mm:ss format
    UptimeSeconds = 5025           # Total seconds
    HealthRate = "98.5%"           # Success rate
    AvgResponseTime = "45.2ms"     # Rolling average
    LastResponseTime = "42.1ms"    # Most recent check
    RestartCount = 0               # Number of restarts
    TotalChecks = 125              # Total health checks
    Failures = 2                   # Failed checks
}
```

### Status Dashboard

When `ShowMetrics` is enabled, the system displays a live dashboard every 60 seconds:

```
╔══════════════════════════════════════════════════════════╗
║               SERVICE STATUS DASHBOARD                  ║
╠══════════════════════════════════════════════════════════╣
║ Theoria API [Running]                                    ║
║   Uptime: 01:23:45 | Health: 98.5% | Avg Response: 45.2ms║
║ Theoria Web [Running]                                    ║
║   Uptime: 01:23:40 | Health: 100.0% | Avg Response: 12.3ms║
╠══════════════════════════════════════════════════════════╣
║ Total Runtime: 01:23:45                                  ║
╚══════════════════════════════════════════════════════════╝
```

## Logging

### Log Levels

- **Info** (ℹ): General information
- **Success** (✓): Successful operations
- **Warning** (⚠): Non-critical issues
- **Error** (✗): Critical failures
- **Debug** (→): Detailed diagnostics (Verbose mode only)
- **Metric** (📊): Performance data (ShowMetrics mode only)

### Structured Log Format

When `LogToFile` is enabled, logs are written as JSON:

```json
{
  "timestamp": "2025-10-12 12:34:56.789",
  "level": "Warning",
  "message": "Theoria API health check failed: Connection timeout",
  "metadata": {
    "service": "Api",
    "status_code": 0,
    "error": "Connection timeout",
    "response_time_ms": 5000.0
  }
}
```

### Log File Location

```
logs/theoria-launcher.log
```

## Shutdown & Session Summary

On graceful shutdown (Ctrl+C), the system displays a comprehensive session summary:

```
╔══════════════════════════════════════════════════════════╗
║                   SESSION SUMMARY                        ║
╠══════════════════════════════════════════════════════════╣
║ Total Runtime: 02:45:30                                  ║
║ Theoria API:                                             ║
║   Uptime: 02:45:25                                       ║
║   Health Checks: 990 (99.2% success)                     ║
║ Theoria Web:                                             ║
║   Uptime: 02:45:20                                       ║
║   Health Checks: 990 (100.0% success)                    ║
║   Restarts: 1                                            ║
╚══════════════════════════════════════════════════════════╝
```

## Troubleshooting

### Service Won't Start

1. **Check port availability**

   ```powershell
   netstat -ano | findstr :8000
   netstat -ano | findstr :3000
   ```

2. **Enable verbose logging**

   ```powershell
   .\start-theoria.ps1 -Verbose
   ```

3. **Check logs**

   ```powershell
   Get-Content logs/theoria-launcher.log | Select-Object -Last 50
   ```

### Service Keeps Restarting

1. Check the last error message in the session summary
2. Review structured logs for failure patterns
3. Verify database/external service availability
4. Check environment variables in `.env`

### Health Checks Failing

1. Verify health endpoints are accessible:

   ```powershell
   Invoke-WebRequest http://127.0.0.1:8000/health
   Invoke-WebRequest http://127.0.0.1:3000
   ```

2. Check service logs for startup errors
3. Increase health check timeout if network is slow
4. Disable health checks temporarily: `-SkipHealthChecks`

## Best Practices

### Development Workflow

1. **Daily Development**

   ```powershell
   .\start-theoria.ps1
   ```

2. **Debugging Issues**

   ```powershell
   .\start-theoria.ps1 -Verbose -LogToFile
   ```

3. **Performance Monitoring**

   ```powershell
   .\start-theoria.ps1 -ShowMetrics
   ```

4. **CI/CD Testing**

   ```powershell
   .\start-theoria.ps1 -SkipHealthChecks
   ```

### Performance Tips

- Use `-SkipHealthChecks` for faster startup in development
- Enable `-LogToFile` only when investigating issues
- `-ShowMetrics` adds minimal overhead (<1% CPU)
- Keep health check interval at 10s for balance

### Monitoring in Production

For production deployments, consider:

1. Exporting metrics to monitoring systems
2. Alerting on restart count thresholds
3. Aggregating logs to centralized logging
4. Tracking response time trends
5. Setting up external health checks

## API Reference

### Functions

#### `Start-Theoria`

Main entry point that orchestrates the complete lifecycle.

#### `Start-TheoriaApi`

Launches FastAPI service with health check polling.

**Returns**: `$true` if started successfully, `$false` otherwise

#### `Start-TheoriaWeb`

Launches Next.js service with dependency installation.

**Returns**: `$true` if started successfully, `$false` otherwise

#### `Stop-TheoriaService`

Gracefully stops a service and captures final output.

**Parameters**:

- `ServiceKey`: "Api" or "Web"
- `Force`: Skip graceful shutdown delay

#### `Test-ServiceHealth`

Performs HTTP health check with diagnostics.

**Parameters**:

- `Endpoint`: Health check URL
- `Diagnostics`: Reference to diagnostic results

**Returns**: `$true` if healthy, `$false` otherwise

#### `Get-ServiceMetrics`

Retrieves comprehensive service metrics.

**Parameters**:

- `ServiceKey`: "Api" or "Web"

**Returns**: Hashtable of metrics

#### `Show-ServiceStatus`

Displays formatted status dashboard in console.

#### `Start-HealthMonitor`

Main monitoring loop with auto-recovery logic.

## Future Enhancements

### Planned Features

- [ ] Configurable health check intervals per service
- [ ] Custom health check endpoints
- [ ] Prometheus metrics export
- [ ] Email/Slack notifications on failures
- [ ] Service dependency graph validation
- [ ] Blue-green deployment support
- [ ] Performance profiling mode
- [ ] Docker container support
- [ ] Cross-platform support (Linux, macOS)
- [ ] Web-based monitoring dashboard

### Contributing

To improve the service management system:

1. Test changes with both services
2. Verify graceful shutdown behavior
3. Add logging for new features
4. Update this documentation
5. Include metrics where applicable

## License

Part of the TheoEngine project. See root LICENSE file.
