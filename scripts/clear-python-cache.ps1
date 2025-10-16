#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Clears Python bytecode cache to prevent stale schema issues

.DESCRIPTION
    Removes all __pycache__ directories and .pyc files from the project.
    This prevents SQLAlchemy from using cached model definitions that don't
    match the current source code.

.NOTES
    Run this script before pytest if you've made schema changes or are
    experiencing "no such column" errors in tests.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot

Write-Host "Clearing Python bytecode cache..." -ForegroundColor Cyan

# Find all __pycache__ directories
$pycacheDirs = Get-ChildItem -Path $projectRoot -Recurse -Directory -Filter "__pycache__" -ErrorAction SilentlyContinue

if ($pycacheDirs) {
    Write-Host "Found $($pycacheDirs.Count) __pycache__ directories" -ForegroundColor Yellow
    foreach ($dir in $pycacheDirs) {
        Write-Verbose "Removing: $($dir.FullName)"
        Remove-Item -Path $dir.FullName -Recurse -Force -ErrorAction SilentlyContinue
    }
    Write-Host "✓ Cleared __pycache__ directories" -ForegroundColor Green
} else {
    Write-Host "No __pycache__ directories found" -ForegroundColor Gray
}

# Find all .pyc files (in case they're outside __pycache__)
$pycFiles = Get-ChildItem -Path $projectRoot -Recurse -Filter "*.pyc" -File -ErrorAction SilentlyContinue

if ($pycFiles) {
    Write-Host "Found $($pycFiles.Count) orphaned .pyc files" -ForegroundColor Yellow
    foreach ($file in $pycFiles) {
        Write-Verbose "Removing: $($file.FullName)"
        Remove-Item -Path $file.FullName -Force -ErrorAction SilentlyContinue
    }
    Write-Host "✓ Cleared .pyc files" -ForegroundColor Green
} else {
    Write-Host "No orphaned .pyc files found" -ForegroundColor Gray
}

# Check for stale cache relative to models.py
$modelsPath = Join-Path $projectRoot "theo\services\api\app\db\models.py"
if (Test-Path $modelsPath) {
    $modelsTime = (Get-Item $modelsPath).LastWriteTime
    Write-Host "`nModels last modified: $modelsTime" -ForegroundColor Cyan
    
    # Re-check for any remaining .pyc files that are older than models.py
    $stalePyc = Get-ChildItem -Path $projectRoot -Recurse -Filter "*.pyc" -File -ErrorAction SilentlyContinue |
        Where-Object { $_.LastWriteTime -lt $modelsTime }
    
    if ($stalePyc) {
        Write-Warning "WARNING: Found $($stalePyc.Count) .pyc files older than models.py that weren't deleted"
        $stalePyc | ForEach-Object { Write-Warning "  - $($_.FullName)" }
    } else {
        Write-Host "✓ No stale cache detected" -ForegroundColor Green
    }
}

Write-Host "`nCache cleared successfully!" -ForegroundColor Green
Write-Host "You can now run: pytest" -ForegroundColor Cyan
