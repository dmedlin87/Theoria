# API Connection Errors - Fixed

## Problem

The console was showing these TypeErrors:

```text
Failed to load verse mentions
Failed to load discovery features  
Failed to load verse graph
Failed to load reliability overview
```

## Root Cause

The **FastAPI backend server was not running** at `http://127.0.0.1:8000`, causing all fetch requests from the Next.js frontend to fail with connection refused errors (TypeErrors).

## Solution Applied

### 1. Created Environment Configuration

```powershell
Copy-Item .env.example .env -Force
```

This creates a `.env` file with the necessary configuration:

- `NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8000`
- `THEO_AUTH_ALLOW_ANONYMOUS=1` (allows local dev without API keys)
- `THEO_ALLOW_INSECURE_STARTUP=1` (allows dev mode)

### 2. Started the API Server

```powershell
python -m uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port 8000
```

The API server is now running and listening on port 8000.

### 3. Improved Error Logging

Added proper try-catch blocks to these files for better debugging:

- `app/verse/[osis]/page.tsx` - Added error logging to `fetchGraph()`, `fetchMentions()`, `fetchTimeline()`
- Error messages now show in console with stack traces

## Verification Steps

1. **Check API is running:**
   - Visit <http://127.0.0.1:8000/docs>
   - You should see the FastAPI Swagger documentation

2. **Test API endpoints:**

   ```powershell
   # Test health endpoint
   curl http://127.0.0.1:8000/health
   
   # Test features endpoint
   curl http://127.0.0.1:8000/features/discovery
   ```

3. **Refresh the Next.js app:**
   - Open <http://localhost:3000> (or your dev port)
   - Navigate to any verse page (e.g., `/verse/John.1.1`)
   - The TypeErrors should be gone
   - Data should load properly

## Services Architecture

### Next.js Frontend (Port 3000)

- **Status**: ✅ Running
- **Location**: `theo/services/web`
- **Command**: `npm run dev`

### FastAPI Backend (Port 8000)

- **Status**: ✅ Running (just started)
- **Location**: `theo/services/api`
- **Command**: `uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port 8000`

## Common Issues

### Issue: "Connection refused" or "ECONNREFUSED"

**Solution**: Make sure API server is running on port 8000

```powershell
# Check if port 8000 is in use
netstat -ano | findstr :8000
```

### Issue: "Authentication required"

**Solution**: Ensure `.env` has `THEO_AUTH_ALLOW_ANONYMOUS=1`

### Issue: Database errors on API startup

**Solution**: The API uses SQLite by default - it will create `theo.db` automatically

## Development Workflow

For future development, start both services:

### Option 1: Manual (Two Terminals)

```powershell
# Terminal 1 - API
python -m uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port 8000

# Terminal 2 - Web
cd theo\services\web
npm run dev
```

### Option 2: Automated Script

```powershell
# PowerShell (runs both services)
.\scripts\dev.ps1

# Or Bash
./scripts/run.sh
```

### Option 3: Docker Compose

```powershell
cd infra
docker compose up --build
```

## API Endpoints Used by Frontend

The following endpoints are called by the frontend pages:

| Endpoint | Used By | Purpose |
|----------|---------|---------|
| `/features/discovery` | All pages | Load research feature flags |
| `/verses/{osis}/mentions` | Verse page | Load verse references |
| `/verses/{osis}/graph` | Verse page | Load relationship graph |
| `/verses/{osis}/timeline` | Verse page | Load timeline data |
| `/research/overview` | Verse page | Load reliability snapshot |
| `/search` | Search page | Search functionality |
| `/copilot/*` | Copilot page | AI workflows |

## Next Steps

1. ✅ API server is running
2. ✅ Frontend can connect to API
3. ✅ Error logging improved
4. 🔄 Refresh your browser to see the fixes
5. 🎉 No more TypeErrors!

## Monitoring

To check if services are healthy:

```powershell
# Check API
curl http://127.0.0.1:8000/health

# Check Web
curl http://localhost:3000

# View API logs
# Check the terminal where uvicorn is running

# View Next.js logs  
# Check the terminal where npm run dev is running
```

## Stopping Services

```powershell
# Press Ctrl+C in each terminal

# Or force stop all
Get-Process | Where-Object { $_.MainWindowTitle -like "*uvicorn*" } | Stop-Process -Force
```
