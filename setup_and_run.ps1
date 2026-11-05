# ==============================================================================
# XiVault: Full Backend Setup & VS Code Extension Installer Script
# ==============================================================================

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "          XiVault - Complete Setup & Launcher             " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

$WorkspaceRoot = $PSScriptRoot
if (-not $WorkspaceRoot) {
    $WorkspaceRoot = "D:\SIVA\Exam"
}

$ApiDir = Join-Path $WorkspaceRoot "apps\api"
$ExtensionDir = Join-Path $WorkspaceRoot "apps\extension"

# ------------------------------------------------------------------------------
# 1. Setup Backend (apps/api)
# ------------------------------------------------------------------------------
Write-Host "`n[1/4] Setting up Python backend (FastAPI)..." -ForegroundColor Yellow
Set-Location $ApiDir

# Create virtual environment if missing
if (-not (Test-Path "$ApiDir\.venv")) {
    Write-Host "Creating Python virtual environment in .venv..." -ForegroundColor Gray
    python -m venv .venv
}

# Activate virtual environment
$VenvPython = "$ApiDir\.venv\Scripts\python.exe"
$VenvPip = "$ApiDir\.venv\Scripts\pip.exe"

Write-Host "Installing backend dependencies..." -ForegroundColor Gray
& $VenvPip install -r requirements.txt --quiet
& $VenvPip install -e . --quiet

# Ensure .env exists
if (-not (Test-Path "$ApiDir\.env")) {
    Copy-Item "$ApiDir\.env.example" -Destination "$ApiDir\.env"
    Write-Host "Created .env configuration from .env.example" -ForegroundColor Green
}

Write-Host "Backend environment ready." -ForegroundColor Green

# ------------------------------------------------------------------------------
# 2. Build and Package Extension (apps/extension)
# ------------------------------------------------------------------------------
Write-Host "`n[2/4] Building and packaging VS Code Extension..." -ForegroundColor Yellow
Set-Location $ExtensionDir

Write-Host "Installing extension npm dependencies..." -ForegroundColor Gray
npm install --quiet

Write-Host "Compiling TypeScript..." -ForegroundColor Gray
npm run compile

Write-Host "Packaging VSIX file..." -ForegroundColor Gray
npx --yes @vscode/vsce package

$VsixPath = Join-Path $ExtensionDir "xivault-0.1.0.vsix"
if (-not (Test-Path $VsixPath)) {
    Write-Host "Error: VSIX package was not created." -ForegroundColor Red
    exit 1
}

# ------------------------------------------------------------------------------
# 3. Install Extension into VS Code
# ------------------------------------------------------------------------------
Write-Host "`n[3/4] Installing XiVault extension into VS Code..." -ForegroundColor Yellow
code --install-extension "$VsixPath" --force

Write-Host "Extension successfully installed into VS Code!" -ForegroundColor Green

# ------------------------------------------------------------------------------
# 4. Start the Backend Service
# ------------------------------------------------------------------------------
Write-Host "`n[4/4] Starting FastAPI backend on http://127.0.0.1:8000..." -ForegroundColor Yellow

$UvicornCommand = "cd '$ApiDir'; .\.venv\Scripts\Activate.ps1; uvicorn xivault.main:app --reload --port 8000"
Start-Process powershell -ArgumentList "-NoExit", "-Command", $UvicornCommand

Write-Host "`n==========================================================" -ForegroundColor Green
Write-Host "  SUCCESS! XiVault is installed and backend is running.   " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "1. A new PowerShell window opened running the FastAPI backend."
Write-Host "2. API Swagger UI:  http://127.0.0.1:8000/docs"
Write-Host "3. In VS Code: Press Ctrl+Shift+P -> 'Developer: Reload Window'"
Write-Host "   or restart VS Code to see the XiVault lock icon in the sidebar."
Write-Host "==========================================================" -ForegroundColor Cyan
