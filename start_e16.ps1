Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

if (-not (Test-Path ".env")) {
  Write-Host "Missing .env. Copy .env.example to .env and update values first." -ForegroundColor Red
  exit 1
}

python -m pip install -r requirements.txt

$env:FLASK_APP = "app.py"
flask db upgrade

# Seed chỉ chạy lần đầu, nếu đã có dữ liệu sẽ tự bỏ qua.
python -c "from e16_app import create_app; app=create_app(); c=app.test_client(); r=c.get('/seed'); print(r.status_code, r.data.decode())"

Write-Host "E16 is running at http://127.0.0.1:5000" -ForegroundColor Green
python app.py
