# Run Django development server on all interfaces (localhost + LAN)
# Usage: .\run.ps1
# Access: http://localhost:8000 or http://<your-ip>:8000 from LAN devices

$VenvPath = Join-Path $PSScriptRoot "venv\Scripts\Activate.ps1"
$ManagePath = Join-Path $PSScriptRoot "manage.py"

if (-not (Test-Path $VenvPath)) {
    Write-Host "ERROR: Virtual environment not found at $VenvPath" -ForegroundColor Red
    exit 1
}

# Get local IP address
$LocalIP = (Get-NetIPAddress -AddressFamily IPv4 | Where-Object {$_.InterfaceAlias -like "*Ethernet*" -or $_.InterfaceAlias -like "*WiFi*"} | Select-Object -First 1).IPAddress
if (-not $LocalIP) {
    $LocalIP = "localhost"
}

# Activate virtual environment
& $VenvPath

# Run development server on all interfaces
Write-Host "Starting Django development server" -ForegroundColor Green
Write-Host "Local: http://localhost:8000" -ForegroundColor Cyan
Write-Host "LAN:   http://${LocalIP}:8000" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop the server" -ForegroundColor Yellow
python $ManagePath runserver 0.0.0.0:8000
