# 构建 Windows onedir 版。产物: dist\robolabel\robolabel.exe（双击即用，无需 Python 环境）
# 用法: powershell -ExecutionPolicy Bypass -File scripts\build_windows.ps1
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$py = "python"   # 或 "py -3.12"
$venv = "build-venv-win"
if (-not (Test-Path "$venv\Scripts\python.exe")) {
    & $py -m venv $venv
    & "$venv\Scripts\python.exe" -m pip install -i https://mirrors.aliyun.com/pypi/simple/ -r requirements.txt
}

& "$venv\Scripts\python.exe" -m PyInstaller robolabel-win.spec --clean --noconfirm

# 可选（方案 B，需先评估 GPL 许可）：内嵌 ffmpeg，双击即用
# New-Item -ItemType Directory -Force dist\robolabel\bin | Out-Null
# Copy-Item (Get-Command ffmpeg.exe).Source dist\robolabel\bin\ -Force
# Copy-Item (Get-Command ffprobe.exe).Source dist\robolabel\bin\ -Force

Write-Host "完成: dist\robolabel\robolabel.exe"
