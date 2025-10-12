# 🚀 Start Theoria - The Smart Way

## Quick Start (Recommended)

**Just run this one command:**

```powershell
.\start-theoria.ps1
```

That's it! The intelligent launcher will:

- ✅ Check all prerequisites (Python, Node.js, npm)
- ✅ Create `.env` file if missing
- ✅ Install Node dependencies if needed
- ✅ Start both API and Web services
- ✅ Monitor health and auto-restart on failures
- ✅ Show you exactly where to connect

## What You'll See

When you run the script, you'll see:

```text
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║              THEORIA ENGINE - Service Launcher           ║
║                                                          ║
║          Research workspace for theology                 ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

--- Pre-flight Checks ---

✓ Python detected: Python 3.12.6
✓ Node.js detected: v20.11.0
✓ npm detected: 10.2.4

--- Starting Services ---

ℹ Starting Theoria API on port 8000...
✓ Theoria API is ready at http://127.0.0.1:8000
ℹ API Docs: http://127.0.0.1:8000/docs

ℹ Starting Theoria Web UI on port 3000...
✓ Theoria Web UI is ready at http://localhost:3000

╔══════════════════════════════════════════════════════════╗
║                                                          ║
║                 🚀 THEORIA IS READY! 🚀                  ║
║                                                          ║
║  API:     http://127.0.0.1:8000                          ║
║  Web UI:  http://localhost:3000                          ║
║  Docs:    http://127.0.0.1:8000/docs                     ║
║                                                          ║
║  Press Ctrl+C to stop all services                       ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝

ℹ Starting health monitor (checking every 10s)...
```

## Features of the Smart Launcher

### 1. **Automatic Prerequisites Check**

- Verifies Python, Node.js, and npm are installed
- Shows version information for debugging
- Provides helpful error messages if something is missing

### 2. **Environment Setup**

- Automatically creates `.env` file from `.env.example`
- Sets proper environment variables for local development
- No manual configuration needed!

### 3. **Intelligent Startup**

- Checks if ports are available before starting
- Starts services in correct order (API first, then Web)
- Waits for each service to become healthy before continuing

### 4. **Health Monitoring**

- Continuously checks if services are responsive
- Auto-restarts failed services (up to 3 attempts)
- Implements cooldown periods to prevent restart loops
- Shows clear status messages

### 5. **Graceful Shutdown**

- Press `Ctrl+C` to stop everything
- Both services shut down cleanly
- No orphaned processes left behind

## Advanced Usage

### Custom Ports

```powershell
.\start-theoria.ps1 -ApiPort 8010 -WebPort 3100
```

### Skip Health Monitoring

For faster startup (less resilient):

```powershell
.\start-theoria.ps1 -SkipHealthChecks
```

### Verbose Logging

See detailed logs for debugging:

```powershell
.\start-theoria.ps1 -Verbose
```

### Combine Options

```powershell
.\start-theoria.ps1 -ApiPort 8010 -Verbose
```

## How It Works

### Startup Sequence

1. **Pre-flight Checks**
   - Validates Python installation
   - Validates Node.js and npm installation
   - Checks for `.env` file (creates if missing)

2. **API Server Startup**
   - Checks if port 8000 is available
   - Sets environment variables (`THEO_AUTH_ALLOW_ANONYMOUS=1`, etc.)
   - Starts `uvicorn` with hot reload
   - Waits up to 30 seconds for health check to pass
   - Confirms API is responding at `/health` endpoint

3. **Web Server Startup**
   - Checks if port 3000 is available
   - Installs `node_modules` if missing (first time only)
   - Sets `NEXT_PUBLIC_API_BASE_URL` environment variable
   - Starts Next.js dev server
   - Waits up to 45 seconds for health check to pass

4. **Health Monitoring Loop**
   - Checks both services every 10 seconds
   - If a service fails health check:
     - Attempts restart (max 3 attempts)
     - Implements 5-second cooldown between restarts
     - Shows clear error messages
   - Continues until you press `Ctrl+C`

### Auto-Recovery Example

If the API crashes or becomes unresponsive:

```text
⚠ Theoria API health check failed
⚠ Attempting to restart Theoria API (attempt 1/3)...
ℹ Stopping Theoria API...
✓ Theoria API stopped
ℹ Starting Theoria API on port 8000...
✓ Theoria API restarted successfully
```

## Troubleshooting

### "Python is required"

Install Python from <https://python.org> (version 3.10 or higher recommended)

### "Node.js and npm are required"

Install Node.js from <https://nodejs.org> (includes npm)

### "Port 8000 is already in use"

Something else is using port 8000. Options:

1. Stop the other service
2. Use a custom port: `.\start-theoria.ps1 -ApiPort 8010`

### "Port 3000 is already in use"

Something else is using port 3000. Options:

1. Stop the other service
2. Use a custom port: `.\start-theoria.ps1 -WebPort 3100`

### Services won't start

Try with verbose logging:

```powershell
.\start-theoria.ps1 -Verbose
```

Look for error messages in the output.

### API starts but Web doesn't

The script will automatically stop the API if Web fails to start. Check the error message and try again.

### Health checks keep failing

If you see repeated restart attempts:

1. Check the verbose logs
2. Verify `.env` file exists and is configured correctly
3. Ensure no firewall is blocking localhost connections
4. Try manually: see "Manual Startup" section below

## Manual Startup (If Script Fails)

If the smart launcher doesn't work, you can start services manually:

### Terminal 1 - API

```powershell
cd C:\Users\dmedl\Projects\TheoEngine
$Env:THEO_AUTH_ALLOW_ANONYMOUS="1"
$Env:THEO_ALLOW_INSECURE_STARTUP="1"
python -m uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port 8000
```

### Terminal 2 - Web

```powershell
cd C:\Users\dmedl\Projects\TheoEngine\theo\services\web
$Env:NEXT_PUBLIC_API_BASE_URL="http://127.0.0.1:8000"
npm run dev
```

## What Changed from TheoEngine?

### Branding Updates ✨

- **TheoEngine** → **Theoria**
- Updated in:
  - Navigation header
  - Page titles
  - Footer
  - Chat interface
  - Upload forms
  - All user-facing text

### New Smart Launcher

- **Old**: Had to manually start two services in separate terminals
- **New**: One command starts everything with monitoring
- **Benefit**: No more "Failed to load" errors from forgetting to start the API!

## Why This Matters

Previously, you had to:

1. Remember to start the API server
2. Remember to start the Web server
3. Hope they both stay running
4. Manually restart if something crashed
5. Kill orphaned processes if shutdown failed

Now you just run `.\start-theoria.ps1` and everything works! 🎉

## System Requirements

- **Operating System**: Windows (PowerShell)
- **Python**: 3.10+ (3.12 recommended)
- **Node.js**: 18+ (20 recommended)
- **npm**: 9+ (10 recommended)
- **RAM**: 4GB minimum, 8GB+ recommended
- **Disk**: 2GB free space for dependencies

## Next Steps

1. **Run the launcher**: `.\start-theoria.ps1`
2. **Open your browser**: <http://localhost:3000>
3. **Start researching**: Upload documents, search verses, use the copilot!

## Support

If you encounter issues:

1. Check this guide's Troubleshooting section
2. Run with `-Verbose` flag for detailed logs
3. Check `QUICK_FIX.md` for common connection issues
4. Review `API_CONNECTION_FIX.md` for technical details

## Development Workflow

For active development with the smart launcher running:

1. **Edit code** - Changes auto-reload (API and Web both have hot reload)
2. **Check logs** - The launcher shows real-time status
3. **Stop services** - Press `Ctrl+C` once (waits for graceful shutdown)
4. **Restart** - Run `.\start-theoria.ps1` again

## Comparison with Other Scripts

| Script | Use Case | Features |
|--------|----------|----------|
| `start-theoria.ps1` | **Recommended for everyone** | Smart checks, auto-recovery, health monitoring |
| `scripts/dev.ps1` | Alternative launcher | Simpler, less monitoring |
| `scripts/run.sh` | Linux/Mac users | Bash version of dev.ps1 |
| Manual commands | When scripts fail | Direct control, no automation |

**Recommendation**: Always use `start-theoria.ps1` unless you have a specific reason not to.

---

**Welcome to Theoria!** 🎓📖

Your intelligent research workspace for theology is ready to use.
