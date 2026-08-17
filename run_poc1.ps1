[CmdletBinding()]
param(
    [switch]$InstallDependencies
)

$ErrorActionPreference = "Stop"

$repositoryRoot = $PSScriptRoot
$pythonExecutable = Join-Path $repositoryRoot ".venv\Scripts\python.exe"
$backendRequirements = Join-Path $repositoryRoot "SystemCode\src\backend\requirements.txt"
$frontendDirectory = Join-Path $repositoryRoot "SystemCode\src\frontend"
$frontendEnvironment = Join-Path $frontendDirectory ".env.local"
$frontendEnvironmentExample = Join-Path $frontendDirectory ".env.local.example"
$neo4jEnvironment = Join-Path $repositoryRoot ".env"

function Stop-WithMessage {
    param([string]$Message)
    Write-Host "`nCannot start KinderCompass PoC 1: $Message" -ForegroundColor Red
    exit 1
}

Write-Host "`nKinderCompass PoC 1 launcher" -ForegroundColor Green
Write-Host "Repository: $repositoryRoot"

if (-not (Test-Path -LiteralPath $pythonExecutable)) {
    Stop-WithMessage "Python virtual environment not found at $pythonExecutable"
}

if (-not (Test-Path -LiteralPath $neo4jEnvironment)) {
    Stop-WithMessage "Neo4j environment file not found at $neo4jEnvironment"
}

$requiredNeo4jKeys = @("NEO4J_URI", "NEO4J_USERNAME", "NEO4J_PASSWORD")
$environmentText = Get-Content -LiteralPath $neo4jEnvironment -Raw
$missingKeys = @($requiredNeo4jKeys | Where-Object { $environmentText -notmatch "(?m)^$([regex]::Escape($_))\s*=" })
if ($missingKeys.Count -gt 0) {
    Stop-WithMessage "The PoC .env file is missing: $($missingKeys -join ', ')"
}

if (-not (Get-Command npm.cmd -ErrorAction SilentlyContinue)) {
    Stop-WithMessage "npm was not found. Install the Node.js LTS release and open a new PowerShell window."
}

if (-not (Test-Path -LiteralPath $frontendEnvironment)) {
    Copy-Item -LiteralPath $frontendEnvironmentExample -Destination $frontendEnvironment
    Write-Host "Created frontend .env.local from the example configuration." -ForegroundColor Yellow
}

if ($InstallDependencies) {
    Write-Host "Installing backend dependencies..." -ForegroundColor Cyan
    & $pythonExecutable -m pip install -r $backendRequirements
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "Backend dependency installation failed."
    }

    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    & npm.cmd install --prefix $frontendDirectory
    if ($LASTEXITCODE -ne 0) {
        Stop-WithMessage "Frontend dependency installation failed."
    }
}

$backendDependencyCheck = & $pythonExecutable -c "import fastapi, uvicorn, neo4j, dotenv, openai" 2>&1
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage "Backend packages are missing. Run this script once with -InstallDependencies."
}

if (-not (Test-Path -LiteralPath (Join-Path $frontendDirectory "node_modules"))) {
    Stop-WithMessage "Frontend packages are missing. Run this script once with -InstallDependencies."
}

$backendCommand = "Set-Location -LiteralPath '$($repositoryRoot.Replace("'", "''"))'; & '$($pythonExecutable.Replace("'", "''"))' -m uvicorn SystemCode.src.backend.main:app --reload"
$frontendCommand = "Set-Location -LiteralPath '$($frontendDirectory.Replace("'", "''"))'; & npm.cmd run dev"

Write-Host "Starting FastAPI backend in a new PowerShell window..." -ForegroundColor Cyan
Start-Process powershell.exe -WorkingDirectory $repositoryRoot -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-Command",
    $backendCommand
)

Write-Host "Starting Next.js frontend in a new PowerShell window..." -ForegroundColor Cyan
Start-Process powershell.exe -WorkingDirectory $frontendDirectory -ArgumentList @(
    "-NoExit",
    "-NoProfile",
    "-Command",
    $frontendCommand
)

Write-Host "`nPoC 1 is starting:" -ForegroundColor Green
Write-Host "  Frontend:    http://localhost:3000"
Write-Host "  Backend API: http://127.0.0.1:8000"
Write-Host "  API docs:    http://127.0.0.1:8000/docs"
Write-Host "`nWait until both windows report that their servers are ready, then open the frontend URL."
Write-Host "Press Ctrl+C in each server window to stop PoC 1."
