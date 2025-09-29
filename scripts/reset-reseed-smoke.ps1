param(
    [string]$DatabaseUrl,
    [string]$MigrationsPath,
    [string]$ApiKey,
    [string]$Osis,
    [ValidateSet('DEBUG','INFO','WARNING','ERROR','CRITICAL')]
    [string]$LogLevel = 'INFO'
)

$scriptPath = Join-Path $PSScriptRoot 'reset_reseed_smoke.py'

if (-not (Test-Path $scriptPath)) {
    Write-Error "Unable to locate reset script at $scriptPath"
    exit 1
}

$python = 'python'
if (-not (Get-Command $python -ErrorAction SilentlyContinue)) {
    if (Get-Command 'py' -ErrorAction SilentlyContinue) {
        $python = 'py'
    } else {
        Write-Error 'Python interpreter not found. Install Python or add it to PATH.'
        exit 1
    }
}

$argsList = @($scriptPath, '--log-level', $LogLevel)
if ($DatabaseUrl) {
    $argsList += @('--database-url', $DatabaseUrl)
}
if ($MigrationsPath) {
    $argsList += @('--migrations-path', $MigrationsPath)
}
if ($ApiKey) {
    $argsList += @('--api-key', $ApiKey)
}
if ($Osis) {
    $argsList += @('--osis', $Osis)
}

& $python @argsList
exit $LASTEXITCODE
