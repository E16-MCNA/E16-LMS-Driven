Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

Set-Location -Path $PSScriptRoot

python -m pip install -r requirements.txt

$env:FLASK_APP = "manage.py"
flask db upgrade

# Seed chỉ chạy lần đầu, nếu đã có dữ liệu sẽ tự bỏ qua.
python -c "from e16_app import create_app; app=create_app(); c=app.test_client(); print(c.get('/seed').status_code)"

Write-Host "E16 is running at http://127.0.0.1:5000" -ForegroundColor Green
python app.py
