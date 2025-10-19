# Theoria Run Scripts

Intelligent all-in-one scripts for running Theoria services with automatic environment setup, dependency management, and error handling.

---

## 🚀 Quick Start

### Windows (PowerShell)

```powershell
# Navigate to project root
cd C:\Users\dmedl\Projects\Theoria

# Run full stack (API + Web)
.\scripts\run.ps1

# Or specify mode
.\scripts\run.ps1 -Mode full
```

---

## 📚 Documentation Governance

Run the governance check script locally or in CI to ensure docs stay in sync:

```bash
python scripts/check_docs_governance.py
```

This verifies that:

- All canonical docs in `docs/status/FEATURE_INDEX.md` exist and use approved status tags.
- The bug ledger (`docs/status/KnownBugs.md`) only references existing documentation.

### Linux/macOS (Bash)

```bash
# Navigate to project root
cd ~/Projects/Theoria

# Make script executable (first time only)
chmod +x scripts/run.sh

# Run full stack (API + Web)
./scripts/run.sh full
```

---

## 📋 Available Modes

### `full` (Default)

Starts both FastAPI backend and Next.js frontend

```powershell
# PowerShell
.\scripts\run.ps1

# Bash
./scripts/run.sh full
```

**Output:**

- API: <http://127.0.0.1:8000>
- Web: <http://127.0.0.1:3001>
- Docs: <http://127.0.0.1:8000/docs>

### `api`

Starts only the FastAPI backend

```powershell
# PowerShell
.\scripts\run.ps1 -Mode api

# Bash
./scripts/run.sh api
```

**Use when:** You want to test API endpoints or develop API features separately.

### `web`

Starts only the Next.js frontend

```powershell
# PowerShell
.\scripts\run.ps1 -Mode web

# Bash
./scripts/run.sh web
```

**⚠️ Warning:** The web app requires the API to be running. Start API first or use `full` mode.

### `dev`

Development mode with enhanced logging (same as `full` but more verbose)

```powershell
# PowerShell
.\scripts\run.ps1 -Mode dev -Verbose

# Bash
./scripts/run.sh dev
```

### `check`

Validates environment and dependencies without starting services

```powershell
# PowerShell
.\scripts\run.ps1 -Mode check

# Bash
./scripts/run.sh check
```

**Checks:**

- Python 3.11+ installed
- Node.js installed
- npm installed
- Port availability (8000, 3001)
- Virtual environment
- Dependencies

### `test`

Runs all test suites (Python, Node.js, E2E)

```powershell
# PowerShell only
.\scripts\run.ps1 -Mode test
```

---

## 🎛️ Advanced Options (PowerShell Only)

### Custom Ports

```powershell
# Change API port
.\scripts\run.ps1 -Port 8080

# Change Web port
.\scripts\run.ps1 -WebPort 3000

# Both
.\scripts\run.ps1 -Port 8080 -WebPort 3000
```

### Skip Checks (Faster Startup)

```powershell
# Skip dependency checks for faster startup
.\scripts\run.ps1 -SkipChecks
```

**⚠️ Use only when:** You've already verified everything is installed and up to date.

### Verbose Logging

```powershell
# Enable detailed logging
.\scripts\run.ps1 -Verbose
```

---

## 🔧 What the Scripts Do Automatically

### 1. **Environment Setup**

- Creates virtual environment if missing
- Installs/updates Python dependencies
- Installs/updates Node.js dependencies
- Creates `.env` and `.env.local` files if missing

### 2. **Prerequisite Checks**

- Verifies Python 3.11+
- Verifies Node.js and npm
- Checks port availability
- Validates directory structure

### 3. **Service Management**

- Stops existing services on required ports
- Starts services with proper configuration
- Waits for health checks before confirming startup
- Monitors service health

### 4. **Error Handling**

- Graceful shutdown on Ctrl+C
- Detailed error messages
- Automatic cleanup of failed starts
- Recovery suggestions

---

## 📁 File Structure Created

The scripts automatically create these files if they don't exist:

```text
Theoria/
├── .env                    # Main environment variables
├── .venv/                  # Python virtual environment
└── theo/services/web/
    └── .env.local          # Web-specific environment
```

### `.env` (Auto-generated)

```bash
database_url=sqlite:///./theo.db
storage_root=./storage
redis_url=redis://localhost:6379/0
THEO_AUTH_ALLOW_ANONYMOUS=1
embedding_model=BAAI/bge-m3
embedding_dim=1024
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
```

### `.env.local` (Auto-generated)

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000
API_BASE_URL=http://127.0.0.1:8000
```

---

## 🐛 Troubleshooting

### Port Already in Use

**Symptom:** Error about port 8000 or 3001 being in use

**Solution:** The script automatically stops existing services, but if it fails:

```powershell
# PowerShell - Find and kill process
Get-NetTCPConnection -LocalPort 8000 | ForEach-Object { Stop-Process -Id $_.OwningProcess -Force }

# Bash - Find and kill process
lsof -ti :8000 | xargs kill -9
```

### Python Not Found

**Symptom:** "Python 3.11+ not found"

**Solution:**

1. Install Python 3.11 or higher
2. Ensure `python` or `python3` is in PATH
3. Run `.\scripts\run.ps1 -Mode check` to verify

### Node.js Not Found

**Symptom:** "Node.js not found"

**Solution:**

1. Install Node.js 18+ from <https://nodejs.org>
2. Verify with: `node --version`
3. Run `.\scripts\run.ps1 -Mode check` to verify

### API Won't Start

**Symptom:** "API service did not respond within 30 seconds"

**Possible causes:**

1. **Missing dependencies:** Run `.\scripts\run.ps1 -Mode check`
2. **Database issues:** Delete `theo.db` and restart
3. **Port conflict:** Change port with `-Port 8080`

**Debug:**

```powershell
# Check API logs
.\scripts\run.ps1 -Mode api -Verbose
```

### Web App Blank/Spinning

**Symptom:** Browser shows blank page or infinite spinner

**Cause:** API is not running or not reachable

**Solution:**

```powershell
# Always run full stack
.\scripts\run.ps1 -Mode full

# Or start API first, then Web
.\scripts\run.ps1 -Mode api    # Terminal 1
.\scripts\run.ps1 -Mode web    # Terminal 2
```

### Dependencies Out of Date

**Symptom:** Import errors or missing modules

**Solution:**

```powershell
# Force reinstall all dependencies
Remove-Item -Recurse -Force .venv, theo\services\web\node_modules
.\scripts\run.ps1 -Mode check
```

---

## 🎯 Common Workflows

### First-Time Setup

```powershell
# 1. Clone repository
git clone https://github.com/yourorg/Theoria.git
cd Theoria

# 2. Run environment check
.\scripts\run.ps1 -Mode check

# 3. Start full stack
.\scripts\run.ps1
```

### Daily Development

```powershell
# Morning: Start everything
.\scripts\run.ps1

# Work on features...
# Ctrl+C when done

# Afternoon: Restart with fresh state
.\scripts\run.ps1
```

### API Development Only

```powershell
# Terminal 1: API with hot reload
.\scripts\run.ps1 -Mode api -Verbose

# Terminal 2: Run API tests
cd Theoria
.venv\Scripts\Activate.ps1
pytest tests/ -v
```

### Frontend Development Only

```powershell
# Terminal 1: Keep API running
.\scripts\run.ps1 -Mode api

# Terminal 2: Web with hot reload
.\scripts\run.ps1 -Mode web

# Terminal 3: Run E2E tests
cd theo\services\web
npm run test:e2e
```

### Running Tests

```powershell
# All tests
.\scripts\run.ps1 -Mode test

# Or individually
cd Theoria
.venv\Scripts\Activate.ps1
pytest tests/ -v                    # Python tests

cd theo\services\web
npm test                            # Unit tests
npm run test:e2e                    # E2E tests (requires services running)
```

---

## 🔒 Security Notes

### `.env` Files

- Never commit `.env` or `.env.local` files
- They contain sensitive configuration
- Scripts create them from `.env.example`

### Default Configuration

The auto-generated config uses:

- SQLite (local file database)
- Anonymous auth (development only)
- Local storage (not S3/cloud)

**⚠️ For production:** Manually configure `.env` with:

- PostgreSQL database
- JWT authentication
- API keys
- Cloud storage

---

## 📊 Performance Tips

### Faster Startup

```powershell
# Skip dependency checks (after first run)
.\scripts\run.ps1 -SkipChecks
```

### Reduce Memory Usage

```powershell
# Run only what you need
.\scripts\run.ps1 -Mode api    # API only (lower memory)
```

### Development Optimization

```bash
# Use separate terminals for better control
# Terminal 1: API
.\scripts\run.ps1 -Mode api

# Terminal 2: Web
.\scripts\run.ps1 -Mode web

# Benefit: Restart services independently
```

---

## 🆘 Getting Help

### Script Help

```powershell
# PowerShell: View all options
Get-Help .\scripts\run.ps1 -Detailed

# Or read comments in script
.\scripts\run.ps1 -?
```

### Check Logs

```powershell
# Verbose output
.\scripts\run.ps1 -Verbose

# API logs only
.\scripts\run.ps1 -Mode api -Verbose
```

### Validate Environment

```powershell
# Run full diagnostics
.\scripts\run.ps1 -Mode check

# Check specific components
python --version
node --version
npm --version
```

---

## 🎨 Script Output Example

```text
████████╗██╗  ██╗███████╗ ██████╗     ███████╗███╗   ██╗ ██████╗ ██╗███╗   ██╗███████╗
╚══██╔══╝██║  ██║██╔════╝██╔═══██╗    ██╔════╝████╗  ██║██╔════╝ ██║████╗  ██║██╔════╝
   ██║   ███████║█████╗  ██║   ██║    █████╗  ██╔██╗ ██║██║  ███╗██║██╔██╗ ██║█████╗  
   ██║   ██╔══██║██╔══╝  ██║   ██║    ██╔══╝  ██║╚██╗██║██║   ██║██║██║╚██╗██║██╔══╝  
   ██║   ██║  ██║███████╗╚██████╔╝    ███████╗██║ ╚████║╚██████╔╝██║██║ ╚████║███████╗
   ╚═╝   ╚═╝  ╚═╝╚══════╝ ╚═════╝     ╚══════╝╚═╝  ╚═══╝ ╚═════╝ ╚═╝╚═╝  ╚═══╝╚══════╝

  Research Engine for Theological Corpora
  Mode: full

================================================================================
  Checking Prerequisites
================================================================================

▶ Checking Python...
✓ Python found: Python 3.11.5
▶ Checking Node.js...
✓ Node.js found: v20.11.0
▶ Checking npm...
✓ npm found: v10.2.4
✓ All prerequisites satisfied

================================================================================
  Starting API Service
================================================================================

▶ Initializing Python environment...
✓ Virtual environment ready
✓ Python dependencies up to date
▶ Starting FastAPI server on port 8000...
▶ Waiting for API to start...
✓ API service started successfully
  → API:    http://127.0.0.1:8000
  → Docs:   http://127.0.0.1:8000/docs
  → Health: http://127.0.0.1:8000/health

================================================================================
  Starting Web Service
================================================================================

▶ Checking Node.js dependencies...
✓ Node.js dependencies up to date
▶ Starting Next.js server on port 3001...
▶ Waiting for web service to start...
✓ Web service started successfully
  → Web:  http://127.0.0.1:3001
  → Chat: http://127.0.0.1:3001/chat

================================================================================
  Services Running
================================================================================

✓ All services started successfully!

  API:  http://127.0.0.1:8000
  Web:  http://127.0.0.1:3001
  Docs: http://127.0.0.1:8000/docs

  Press Ctrl+C to stop all services
```

---

## 📝 Notes

### Platform Differences

| Feature | PowerShell | Bash |
|---------|-----------|------|
| Custom ports | ✅ | ❌ (use env vars) |
| Skip checks | ✅ | ❌ |
| Verbose mode | ✅ | ❌ |
| Test mode | ✅ | ❌ |
| Auto-cleanup | ✅ | ✅ |
| Color output | ✅ | ✅ |

### Environment Variables (Bash)

```bash
# Customize ports
export THEO_API_PORT=8080
export THEO_WEB_PORT=3000
./scripts/run.sh full
```

### Stopping Services

**Graceful shutdown:** Press `Ctrl+C`

- Services stop cleanly
- Connections closed properly
- Resources released

**Force stop:**

```powershell
# PowerShell
Get-Process | Where-Object { $_.MainWindowTitle -like "*uvicorn*" } | Stop-Process -Force

# Bash
pkill -f uvicorn
pkill -f "next dev"
```

---

## 🎓 Understanding the Scripts

### Script Architecture

```text
run.ps1 / run.sh
├── Prerequisite checks
│   ├── Python version
│   ├── Node.js version
│   └── Port availability
├── Environment setup
│   ├── Create .venv
│   ├── Install dependencies
│   └── Create .env files
├── Service startup
│   ├── FastAPI (uvicorn)
│   ├── Next.js (npm dev)
│   └── Health checks
└── Monitoring
    ├── Process management
    ├── Log streaming
    └── Graceful shutdown
```

### Why Two Scripts?

- **`run.ps1`**: Full-featured PowerShell version for Windows
- **`run.sh`**: Simpler bash version for Linux/macOS

Both achieve the same goal with platform-appropriate approaches.

---

## 🔄 Updates & Maintenance

### Updating Dependencies

The scripts automatically check for outdated dependencies. To force update:

```powershell
# Delete caches and reinstall
Remove-Item -Recurse -Force .venv, theo\services\web\node_modules, theo\services\web\.next
.\scripts\run.ps1
```

### Script Updates

```bash
# Pull latest scripts
git pull origin main

# Verify changes
git log scripts/
```

---

## 📚 Additional Resources

- **Main Documentation**: See `README.md` in project root
- **API Documentation**: <http://127.0.0.1:8000/docs> (when running)
- **UI Documentation**: `theo/services/web/UI_IMPROVEMENTS.md`
- **Architecture**: `docs/BLUEPRINT.md`

---

**Questions or Issues?**

- Check troubleshooting section above
- Run `.\scripts\run.ps1 -Mode check` for diagnostics
- Enable verbose mode: `.\scripts\run.ps1 -Verbose`
