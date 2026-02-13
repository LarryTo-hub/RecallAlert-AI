<#
Team quickstart + demo runner for RecallAgent

Usage (PowerShell):
  ./team_tutorial.ps1                 # runs defaults
  ./team_tutorial.ps1 -DemoLimit 8    # fetch 8 items in demo
#>
param(
    [int] $DemoLimit = 5,
    [switch] $InstallDeps,
    [switch] $RunMain
)

$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path | Split-Path -Parent
Set-Location $root

function Info($msg){ Write-Host $msg -ForegroundColor Cyan }
function Warn($msg){ Write-Host $msg -ForegroundColor Yellow }
function Fail($msg){ Write-Host $msg -ForegroundColor Red; exit 1 }

Info "Project root: $root"
Info "Python version:"
try { python --version } catch { Fail "Python not found on PATH. Install Python 3.11+ and re-run." }

# Ensure venv
if (-not (Test-Path ".venv")) {
    Info "Creating virtualenv .venv"
    python -m venv .venv
} else {
    Info ".venv exists"
}

# Activate venv for this session
$activate = Join-Path $root ".venv\Scripts\Activate.ps1"
if (Test-Path $activate) {
    Info "Activating virtualenv"
    & $activate
} else {
    Fail "Activate script not found at $activate"
}

# Upgrade pip and optionally install deps
Info "Pip: $(python -m pip --version)"
Info "Upgrading pip"
python -m pip install --upgrade pip

if ($InstallDeps) {
    if (Test-Path "requirements.txt") {
        Info "Installing requirements.txt"
        pip install -r requirements.txt
    } else {
        Warn "requirements.txt missing; skipping install"
    }
} else {
    Info "Skipping dependency install. Use -InstallDeps to install requirements.txt"
}

# Check .env.example
if (Test-Path ".env.example") {
    Info "Read .env.example for required env variables. DO NOT commit a real .env"
} else {
    Warn ".env.example not found"
}

# Run demo script
$demoScript = Join-Path $root "scripts\demo_fetch.py"
if (Test-Path $demoScript) {
    Info "Running demo_fetch.py (limit = $DemoLimit)"
    try {
        python $demoScript $DemoLimit
    } catch {
        Warn "Demo script failed: $_.Exception.Message"
    }
} else {
    Warn "demo_fetch.py not found; please add scripts/demo_fetch.py"
}

# Optional: run main runner (persists to recalls.db)
if ($RunMain) {
    if (Test-Path ".\src\main.py") {
        Info "Running src.main (smoke run)"
        python -m src.main
    } else {
        Warn "src.main not present; skipping"
    }
} else {
    Info "Skipping src.main. Use -RunMain to execute."
}

# Show DB and demo outputs
if (Test-Path ".\demo\recalls_demo.json") {
    $fi = Get-Item .\demo\recalls_demo.json
    Info "Demo output: $($fi.FullName) ($($fi.Length) bytes)"
} else {
    Warn "demo/recalls_demo.json not found"
}
if (Test-Path ".\recalls.db") {
    $fi = Get-Item .\recalls.db
    Info "Database: $($fi.FullName) ($($fi.Length) bytes)"
} else {
    Info "No recalls.db found yet (created by src.main on run)"
}

# Git quick workflow hints
Write-Host ""
Info "GIT WORKFLOW (recommended)"
Write-Host "  Create feature branch: git checkout -b feature/your-task"
Write-Host "  Commit: git add . ; git commit -m 'Describe change'"
Write-Host "  Push: git push -u origin feature/your-task"
Write-Host "  Open PR on GitHub and request one reviewer"
Write-Host ""

# Suggested small tasks to assign
Info "SUGGESTED TASKS (small, assignable)"
Write-Host "  - fetcher: add USDA/RSS source, add tests (src/fetcher.py)"
Write-Host "  - store: add models, uniques, notifications table (src/store.py)"
Write-Host "  - notifier: Twilio + email fallback, dry-run flag (src/notifier.py)"
Write-Host "  - api/scheduler: FastAPI endpoints + APScheduler (src/app.py)"
Write-Host "  - tests/ci: pytest and GitHub Actions config (tests/, .github/workflows)"
Write-Host ""

# Security reminder
Write-Host "SECURITY: Do NOT commit real secrets." -ForegroundColor Red
Write-Host "Add .env to .gitignore. Use .env.example as template."
Write-Host ""

Info "Team tutorial finished. Provide this script and the README Quickstart during the walkthrough."
