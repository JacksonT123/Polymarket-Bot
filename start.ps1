# Start Polymarket copy trader
Set-Location $PSScriptRoot
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
pip install -e . -q
python -m bot.main
