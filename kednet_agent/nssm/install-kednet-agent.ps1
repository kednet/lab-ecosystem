# install-kednet-agent.ps1
#
# Устанавливает Kednet Agent (kednet_agent.py) как Windows-сервис через nssm.
#
# Что делает:
#   1. Проверяет наличие nssm.exe, python.exe, kednet_agent.py
#   2. Проверяет, что kednet_agent.config.json валидный
#   3. nssm install KednetAgent (если ещё не установлен)
#   4. nssm set: AppPath, AppDirectory, AppStdout/Err, Start=SERVICE_AUTO_START
#   5. nssm start KednetAgent
#   6. Smoke: показать первые строки лога
#
# Использование:
#   .\install-kednet-agent.ps1
#   .\install-kednet-agent.ps1 -NssmPath C:\Tools\nssm-2.24\win64\nssm.exe
#   .\install-kednet-agent.ps1 -PythonPath C:\Python312\python.exe
#   .\install-kednet-agent.ps1 -Reinstall
#
# Требования:
#   - nssm 2.24+ (https://nssm.cc/download)
#   - Python 3.11+ с установленным websockets (см. README.md)

[CmdletBinding()]
param(
    [string]$NssmPath = "C:\Tools\nssm-2.24\win64\nssm.exe",

    [string]$PythonPath = "$HOME\AppData\Local\Programs\Python\Python312\python.exe",

    [string]$AgentDir = "$PSScriptRoot\..",

    [string]$ServiceName = "KednetAgent",

    [switch]$Reinstall
)

$ErrorActionPreference = "Stop"

function Step([string]$msg) { Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Ok([string]$msg) { Write-Host "  ✓ $msg" -ForegroundColor Green }
function Warn([string]$msg) { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Fail([string]$msg) { Write-Host "  ✗ $msg" -ForegroundColor Red; exit 1 }

# ────────────────────────────────────────────────
# Проверки
# ────────────────────────────────────────────────
Step "Проверки окружения"

if (-not (Test-Path $NssmPath)) {
    Fail "nssm.exe не найден: $NssmPath`n  Скачайте: https://nssm.cc/download → распакуйте, например в C:\Tools\nssm-2.24\"
}
Ok "nssm: $NssmPath"

if (-not (Test-Path $PythonPath)) {
    Fail "Python не найден: $PythonPath`n  Поставьте Python 3.11+ или укажите -PythonPath"
}
Ok "Python: $PythonPath"

$AgentDir = (Resolve-Path $AgentDir).Path
$agentPy = Join-Path $AgentDir "kednet_agent.py"
if (-not (Test-Path $agentPy)) {
    Fail "kednet_agent.py не найден: $agentPy"
}
Ok "kednet_agent.py: $agentPy"

$cfgPath = Join-Path $AgentDir "kednet_agent.config.json"
if (-not (Test-Path $cfgPath)) {
    Fail "kednet_agent.config.json не найден: $cfgPath"
}
$cfg = Get-Content $cfgPath -Raw | ConvertFrom-Json
if ($cfg.token -match "REPLACE_WITH_") {
    Fail "В kednet_agent.config.json не заменён token. Получите KEDNET_AGENT_TOKEN из /opt/chief-agent/.env на VPS"
}
Ok "Config: chiefUrl=$($cfg.chiefUrl), skillsDir=$($cfg.skillsDir)"

# Проверить, что websockets установлен (в PYTHONPATH или vendor/)
$pySys = & $PythonPath -c "import websockets; print(websockets.__version__)" 2>&1
if ($LASTEXITCODE -ne 0) {
    Warn "websockets не установлен в system Python. Попробуйте установить:"
    Warn "  $PythonPath -m pip install --target=`"$AgentDir\vendor`" websockets==12.0"
    Warn "  (или активируйте .venv с предустановленным пакетом)"
    $ans = Read-Host "  Продолжить установку сервиса? (y/N)"
    if ($ans -ne "y" -and $ans -ne "Y") { exit 1 }
} else {
    Ok "websockets version: $pySys"
}

# ────────────────────────────────────────────────
# nssm install / reinstall
# ────────────────────────────────────────────────
$existing = & $NssmPath status $ServiceName 2>&1
if ($LASTEXITCODE -eq 0) {
    if ($Reinstall) {
        Step "Удаляю существующий сервис $ServiceName"
        & $NssmPath stop $ServiceName 2>&1 | Out-Host
        Start-Sleep -Seconds 2
        & $NssmPath remove $ServiceName confirm 2>&1 | Out-Host
        Ok "Удалён"
    } else {
        Warn "Сервис $ServiceName уже установлен. Используйте -Reinstall для переустановки."
        $status = & $NssmPath status $ServiceName
        Write-Host "  Статус: $status"
        exit 0
    }
}

Step "Установка сервиса $ServiceName"
& $NssmPath install $ServiceName $PythonPath (Resolve-Path $agentPy).Path 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "nssm install failed" }
Ok "nssm install: OK"

# ────────────────────────────────────────────────
# Параметры сервиса
# ────────────────────────────────────────────────
Step "Настройка параметров"

& $NssmPath set $ServiceName AppDirectory $AgentDir 2>&1 | Out-Host
Ok "AppDirectory = $AgentDir"

& $NssmPath set $ServiceName DisplayName "Kednet Agent (Chief bridge)" 2>&1 | Out-Host
Ok "DisplayName"

& $NssmPath set $ServiceName Description "Persistent WebSocket bridge between Kednet (Windows) and Chief Agent (VPS). Spawns .venv Python agents on command." 2>&1 | Out-Host
Ok "Description"

$logsDir = Join-Path $AgentDir "logs"
if (-not (Test-Path $logsDir)) { New-Item -ItemType Directory -Path $logsDir -Force | Out-Null }

& $NssmPath set $ServiceName AppStdout (Join-Path $logsDir "service.out.log") 2>&1 | Out-Host
& $NssmPath set $ServiceName AppStderr (Join-Path $logsDir "service.err.log") 2>&1 | Out-Host
& $NssmPath set $ServiceName AppStdoutCreationDisposition 4 2>&1 | Out-Host   # 4 = APPEND
& $NssmPath set $ServiceName AppStderrCreationDisposition 4 2>&1 | Out-Host
& $NssmPath set $ServiceName AppRotateFiles 1 2>&1 | Out-Host                  # rotate
& $NssmPath set $ServiceName AppRotateBytes 10485760 2>&1 | Out-Host          # 10MB
Ok "Logs: $logsDir\service.{out,err}.log (rotate 10MB)"

& $NssmPath set $ServiceName Start SERVICE_AUTO_START 2>&1 | Out-Host
Ok "Start = SERVICE_AUTO_START"

& $NssmPath set $ServiceName AppEnvironmentExtra "PYTHONIOENCODING=utf-8`PYTHONUNBUFFERED=1" 2>&1 | Out-Host
Ok "Env: PYTHONIOENCODING=utf-8, PYTHONUNBUFFERED=1"

# Restart on failure
& $NssmPath set $ServiceName AppExit Default Restart 2>&1 | Out-Host
& $NssmPath set $ServiceName AppRestartDelay 5000 2>&1 | Out-Host
Ok "Restart policy: on exit → restart after 5s"

# ────────────────────────────────────────────────
# Запуск
# ────────────────────────────────────────────────
Step "Запуск сервиса"
& $NssmPath start $ServiceName 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "nssm start failed" }
Start-Sleep -Seconds 3

$status = & $NssmPath status $ServiceName 2>&1
if ($status -match "SERVICE_RUNNING") {
    Ok "SERVICE_RUNNING"
} else {
    Warn "Статус: $status. Лог: $logsDir\service.err.log"
}

# ────────────────────────────────────────────────
# Smoke
# ────────────────────────────────────────────────
Step "Smoke: первые строки лога"
$logFile = Join-Path $logsDir "kednet_agent.log"
if (Test-Path $logFile) {
    Get-Content $logFile -Tail 15 | ForEach-Object { Write-Host "  $_" }
} else {
    Warn "Лог $logFile ещё не создан. Подождите 5 сек и проверьте: Get-Content $logFile -Tail 20 -Wait"
}

Step "Готово"
Write-Host "  Сервис:     Get-Service $ServiceName" -ForegroundColor Green
Write-Host "  Лог:        Get-Content '$logFile' -Tail 20 -Wait" -ForegroundColor Green
Write-Host "  Рестарт:    Restart-Service $ServiceName" -ForegroundColor Green
Write-Host "  Остановить: Stop-Service $ServiceName" -ForegroundColor Green
Write-Host "  Удалить:    & '$NssmPath' remove $ServiceName confirm" -ForegroundColor Green
Write-Host ""
Write-Host "  Проверить, что Chief видит Kednet-агент:" -ForegroundColor Yellow
Write-Host "    curl -H 'Authorization: Bearer <CHIEF_API_TOKEN>' http://89.108.88.74:7070/api/ws/status" -ForegroundColor Yellow