# PowerShell script to run complete Flake Doctor live demo from fresh clone
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

Write-Host "====================================================" -ForegroundColor Cyan
Write-Host "Flake Doctor Live Demo" -ForegroundColor Cyan
Write-Host "====================================================" -ForegroundColor Cyan

# Check or create venv
if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
    Write-Host "Creating virtual environment..." -ForegroundColor Yellow
    python -m venv .venv
    & ".\.venv\Scripts\python.exe" -m pip install --upgrade pip
    & ".\.venv\Scripts\python.exe" -m pip install -r requirements.txt
}

Write-Host "`n[1/2] Running Flake Doctor scan with --verify-fix..." -ForegroundColor Green
& ".\.venv\Scripts\python.exe" -m flakedoctor.cli scan demo_sick_repo/test_patient_zero.py --json autopsy_report.json --verify-fix

Write-Host "`n[2/2] Running verify_demo.py verification checks..." -ForegroundColor Green
& ".\.venv\Scripts\python.exe" verify_demo.py

if ($LASTEXITCODE -eq 0) {
    Write-Host "`nSUCCESS: All Flake Doctor verifications PASSED!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "`nFAILURE: Flake Doctor verification failed!" -ForegroundColor Red
    exit 1
}
