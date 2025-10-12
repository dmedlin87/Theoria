# Quick Fix for Console Errors

## The Problem

You're seeing these errors in the console:

```text
Failed to load verse mentions
Failed to load discovery features
Failed to load verse graph
Failed to load reliability overview
```

## The Cause

**The FastAPI backend server is not running.** The frontend at `http://localhost:3000` is trying to connect to `http://127.0.0.1:8000` but nothing is listening on that port.

## The Solution

### Step 1: Open a NEW Terminal Window

Leave your Next.js dev server running in its current terminal.

### Step 2: Navigate to Project Root

```powershell
cd C:\Users\dmedl\Projects\TheoEngine
```

### Step 3: Set Environment Variables and Start API

```powershell
$Env:THEO_AUTH_ALLOW_ANONYMOUS="1"
$Env:THEO_ALLOW_INSECURE_STARTUP="1"
python -m uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port 8000
```

You should see output like:

```text
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
```

### Step 4: Verify API is Running

Open a third terminal and run:

```powershell
curl http://127.0.0.1:8000/docs
```

Or just visit <http://127.0.0.1:8000/docs> in your browser.

### Step 5: Refresh Your Browser

Go back to your Next.js app at <http://localhost:3000> and refresh. The errors should be gone!

## Alternative: Use the Dev Script

Instead of manually starting services, use the provided script:

```powershell
.\scripts\dev.ps1
```

This automatically starts both the API and Web servers with proper configuration.

Press `Ctrl+C` to stop both services when done.

## What I've Already Done

✅ Created `.env` file from `.env.example`
✅ Added better error logging to verse pages
✅ Started the Next.js dev server (still running)

## What You Need to Do

🔲 Start the API server (see Step 3 above)
🔲 Verify it's running (see Step 4 above)
🔲 Refresh your browser

## Why This Happened

The TheoEngine needs TWO servers running:

1. **Next.js Frontend** (Port 3000) - ✅ Already running
2. **FastAPI Backend** (Port 8000) - ❌ Was not running

The frontend makes HTTP requests to the backend for all data. Without the backend, you get "Failed to load" errors.

## Troubleshooting

### "Module not found" error when starting API

```powershell
pip install -r requirements.txt
```

### "Port 8000 already in use"

```powershell
# Find and kill the process
netstat -ano | findstr :8000
# Note the PID (last column)
taskkill /PID <PID> /F
```

### Still seeing errors after starting API

1. Check the API terminal for error messages
2. Visit <http://127.0.0.1:8000/docs> to confirm API is responding
3. Check browser DevTools Console for specific error messages
4. Hard refresh browser (Ctrl+Shift+R)

## Development Workflow

Always run BOTH servers during development:

**Terminal 1 (API):**

```powershell
$Env:THEO_AUTH_ALLOW_ANONYMOUS="1"; $Env:THEO_ALLOW_INSECURE_STARTUP="1"; python -m uvicorn theo.services.api.app.main:app --reload --host 127.0.0.1 --port 8000
```

**Terminal 2 (Web):**

```powershell
cd theo\services\web
npm run dev
```

Or use the all-in-one script:

```powershell
.\scripts\dev.ps1
```
