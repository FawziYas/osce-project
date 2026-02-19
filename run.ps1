# Run Django development server on localhost:8000
# Usage: .\run.ps1

$VenvPath = Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"
$ManagePath = Join-Path $PSScriptRoot "manage.py"

if (-not (Test-Path $VenvPath)) {
    Write-Host "ERROR: Virtual environment not found at $VenvPath" -ForegroundColor Red
    exit 1
}

# Activate virtual environment
& $VenvPath

# Run development server
Write-Host "Starting Django development server on http://localhost:8000" -ForegroundColor Green
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
python $ManagePath runserver localhost:8000
