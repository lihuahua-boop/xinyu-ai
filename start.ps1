# 心屿 AI 一键启动
$ErrorActionPreference = "Stop"
Set-Location -LiteralPath $PSScriptRoot

if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot "data"))) {
    New-Item -ItemType Directory -Path (Join-Path $PSScriptRoot "data") | Out-Null
}

# 优先使用本机已验证的 Python 3.7（3.14 缺依赖）
$python = "D:\biyesheji\python37\python.exe"
if (-not (Test-Path -LiteralPath $python)) { $python = "python" }

Write-Host "心屿 AI 启动中…" -ForegroundColor Magenta
Write-Host "  Python：$python" -ForegroundColor DarkGray
Write-Host "  模型：$(if ($env:XINYU_LLM_PROVIDER) { $env:XINYU_LLM_PROVIDER } else { 'mock（本地情感引擎）' })" -ForegroundColor DarkGray
& $python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
