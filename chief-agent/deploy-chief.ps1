# deploy-chief.ps1
#
# Деплой Chief Agent v2.0 на Reg.ru VPS одной командой.
#
# Chief по умолчанию живёт на VPS 89.108.88.74 (Reg.ru, 2 ГБ RAM, тариф HP C1-M2-D20).
# Старый VPS 194.226.97.7 (1 ГБ) — для WL-ботов, не для Chief.
#
# Что делает:
#   1. Копирует chief-agent/ → /opt/chief-agent/ на VPS (rsync, без node_modules)
#   2. npm ci --omit=dev на VPS
#   3. Копирует systemd/chief-agent.service → /etc/systemd/system/
#   4. Копирует обновлённый nginx.conf (chief api + chief ws + tg webhook) и reload nginx
#   5. systemctl enable --now chief-agent
#   6. Smoke-test: /api/health, /api/ws/status
#
# Использование:
#   .\deploy-chief.ps1                                     # default: 89.108.88.74
#   .\deploy-chief.ps1 -VpsHost 89.108.88.74 -DryRun
#   .\deploy-chief.ps1 -VpsHost 89.108.88.74 -SkipNpmCi
#
# После этого на Kednet (ноуте kfigh):
#   .\C:\Users\kfigh\kednet_agent\nssm\install-kednet-agent.ps1
#
# Требования:
#   - SSH-ключ $HOME\.ssh\lab_vps (ed25519)
#   - rsync в PATH
#   - на VPS: Node.js ≥18, уже сделан начальный сетап (apt install nodejs npm)

[CmdletBinding()]
param(
    [string]$VpsHost = "89.108.88.74",

    [string]$SshKey = "$HOME\.ssh\lab_vps",

    [string]$SshUser = "root",

    [switch]$SkipNpmCi,

    [switch]$SkipNginx,

    [switch]$DryRun
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Step([string]$msg) {
    Write-Host ""
    Write-Host "▶ $msg" -ForegroundColor Cyan
}

function Ok([string]$msg) {
    Write-Host "  ✓ $msg" -ForegroundColor Green
}

function Warn([string]$msg) {
    Write-Host "  ⚠ $msg" -ForegroundColor Yellow
}

function Fail([string]$msg) {
    Write-Host "  ✗ $msg" -ForegroundColor Red
    exit 1
}

# ────────────────────────────────────────────────
# Проверки
# ────────────────────────────────────────────────
Step "Проверки окружения"

if (-not (Test-Path $SshKey)) {
    Fail "SSH-ключ не найден: $SshKey"
}
Ok "SSH-ключ: $SshKey"

$rsync = (Get-Command rsync -ErrorAction SilentlyContinue)
$scp  = (Get-Command scp  -ErrorAction SilentlyContinue)
if (-not $rsync -and -not $scp) {
    Fail "Ни rsync, ни scp не найдены в PATH. Поставьте Git for Windows / OpenSSH / WSL."
}
if ($rsync) {
    Ok "rsync: $($rsync.Source)"
} else {
    Warn "rsync не найден — fallback на scp (медленнее, без --delete)"
}

$ping = & ssh -i $SshKey -o BatchMode=yes -o ConnectTimeout=5 "$SshUser@$VpsHost" "echo connected" 2>&1
if ($LASTEXITCODE -ne 0) {
    Fail "Не удаётся подключиться к $SshUser@$VpsHost"
}
Ok "SSH до $SshUser@$VpsHost"

if (-not (Test-Path "$root\package.json")) {
    Fail "package.json не найден в $root. Запустите скрипт из chief-agent/"
}
Ok "package.json"

if (-not (Test-Path "$root\systemd\chief-agent.service")) {
    Fail "systemd/chief-agent.service не найден"
}
Ok "systemd/chief-agent.service"

# ────────────────────────────────────────────────
# Rsync chief-agent → /opt/chief-agent/
# ────────────────────────────────────────────────
$sshOpts = "-i `"$SshKey`" -o StrictHostKeyChecking=accept-new"

Step "Загрузка chief-agent/ → /opt/chief-agent/"
& ssh $sshOpts "${SshUser}@${VpsHost}" "sudo mkdir -p /opt/chief-agent" 2>&1 | Out-Host

if ($rsync) {
    $rsyncOpts = @("-avz", "--delete", "-e", "ssh $sshOpts",
        "--exclude=node_modules", "--exclude=data",
        "--exclude=.env", "--exclude=.DS_Store", "--exclude=*.log")
    if ($DryRun) {
        $rsyncOpts += "--dry-run"
        Warn "Dry-run mode: файлы не будут загружены"
    }
    & rsync @rsyncOpts "$root\" "${SshUser}@${VpsHost}:/opt/chief-agent/" 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "rsync failed" }
    Ok "chief-agent/ загружен (rsync)"
} else {
    # scp fallback: tar+stream через ssh (быстрее, чем scp -r посуточно).
    # Исключаем node_modules/data/.env/логи.
    $excludeArgs = @(
        "--exclude=node_modules",
        "--exclude=data",
        "--exclude=.env",
        "--exclude=.DS_Store",
        "--exclude=*.log"
    )
    $tarCmd = "tar -czf - $excludeArgs -C `"$root`" . | ssh $sshOpts ${SshUser}@${VpsHost} `'sudo rm -rf /opt/chief-agent/* && sudo tar -xzf - -C /opt/chief-agent`'"
    if ($DryRun) {
        Warn "Dry-run: пропускаем загрузку"
    } else {
        Write-Host "  (используем tar+ssh fallback)"
        & bash -c $tarCmd 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) { Fail "scp fallback failed" }
    }
    Ok "chief-agent/ загружен (tar+ssh)"
}

# ────────────────────────────────────────────────
# npm ci на VPS
# ────────────────────────────────────────────────
if (-not $DryRun -and -not $SkipNpmCi) {
    # `npm ci` требует package-lock.json — если его нет (как сейчас в chief-agent/),
    # используем `npm install --omit=dev`. Это идемпотентно: ставит по package.json.
    Step "npm install --omit=dev на VPS"
    $cmd = "cd /opt/chief-agent && (npm ci --omit=dev 2>&1 || npm install --omit=dev 2>&1) | tail -15"
    & ssh $sshOpts "${SshUser}@${VpsHost}" $cmd 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "npm install failed" }
    Ok "node_modules установлены"

    # Sanity: chown root:root (User=root в unit)
    & ssh $sshOpts "${SshUser}@${VpsHost}" "sudo chown -R root:root /opt/chief-agent" 2>&1 | Out-Host
    Ok "ownership = root:root"
}

# ────────────────────────────────────────────────
# .env (если есть локально — скопировать; иначе — создать заглушку)
# ────────────────────────────────────────────────
if (-not $DryRun) {
    Step ".env"
    if (Test-Path "$root\.env") {
        & scp $sshOpts "$root\.env" "${SshUser}@${VpsHost}:/opt/chief-agent/.env" 2>&1 | Out-Host
        Ok ".env скопирован с локалки"
    } else {
        Warn ".env не найден на локалке. Создайте на VPS вручную: sudo nano /opt/chief-agent/.env"
        Warn "Минимум: CHIEF_API_TOKEN (openssl rand -hex 32), CHIEF_PORT=7070"
    }

    # Гарантируем, что .env имеет mode 600.
    & ssh $sshOpts "${SshUser}@${VpsHost}" "sudo chmod 600 /opt/chief-agent/.env 2>/dev/null || true" 2>&1 | Out-Host
}

# ────────────────────────────────────────────────
# systemd unit
# ────────────────────────────────────────────────
if (-not $DryRun) {
    Step "Установка systemd unit"
    & ssh $sshOpts "${SshUser}@${VpsHost}" "sudo cp /opt/chief-agent/systemd/chief-agent.service /etc/systemd/system/ && sudo systemctl daemon-reload && sudo systemctl enable --now chief-agent" 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "systemctl failed" }
    Ok "chief-agent запущен"

    Start-Sleep -Seconds 2
    $status = & ssh $sshOpts "${SshUser}@${VpsHost}" "systemctl is-active chief-agent" 2>&1
    if ($status.Trim() -ne "active") {
        Warn "chief-agent не active (статус: $status). Проверьте: sudo journalctl -u chief-agent -n 50"
    } else {
        Ok "chief-agent status = active"
    }
}

# ────────────────────────────────────────────────
# nginx: добавить /chief/api/ + /chief/ws/ + /chief/api/tg/webhook (если ещё не добавлен)
# ────────────────────────────────────────────────
if (-not $DryRun -and -not $SkipNginx) {
    Step "nginx: добавить /chief/api/ + /chief/ws/ + /chief/api/tg/webhook"
    # Копируем новый nginx.conf из lab-site/deploy/.
    $nginxSrc = "$root\..\lab_site\deploy\nginx.conf"
    $nginxSrc = (Resolve-Path $nginxSrc -ErrorAction SilentlyContinue).Path
    if ($nginxSrc -and (Test-Path $nginxSrc)) {
        & scp $sshOpts "$nginxSrc" "${SshUser}@${VpsHost}:/tmp/lab-site-nginx.conf" 2>&1 | Out-Host
        & ssh $sshOpts "${SshUser}@${VpsHost}" "sudo cp /tmp/lab-site-nginx.conf /etc/nginx/sites-available/lab-site && sudo ln -sf /etc/nginx/sites-available/lab-site /etc/nginx/sites-enabled/lab-site && sudo nginx -t && sudo systemctl reload nginx" 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) { Warn "nginx reload — что-то не так" }
        else { Ok "nginx reloaded (chief api + ws + tg webhook)" }
    } else {
        Warn "lab_site/deploy/nginx.conf не найден (нужен для /chief/api/, /chief/ws/). Деплойте lab-site отдельно."
    }
}

# ────────────────────────────────────────────────
# Smoke-test
# ────────────────────────────────────────────────
if (-not $DryRun) {
    Step "Smoke-test: /api/health"
    $health = & ssh $sshOpts "${SshUser}@${VpsHost}" "curl -s --max-time 5 http://127.0.0.1:7070/api/health" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Warn "Не удалось подключиться к Chief. Проверьте: ssh $SshUser@$VpsHost 'sudo journalctl -u chief-agent -n 50'"
    } else {
        Write-Host "  → $health" -ForegroundColor Yellow
        if ($health -match '"status":"ok"') {
            Ok "Chief Agent отвечает OK"
        } else {
            Warn "Chief ответил, но ответ неожиданный"
        }
    }
}

Step "Готово"
Write-Host "  UI пульт:    https://app.pulab.online/chief/" -ForegroundColor Green
Write-Host "  API:         https://app.pulab.online/chief/api/health" -ForegroundColor Green
Write-Host "  WS endpoint: wss://app.pulab.online/chief/ws/  (для Kednet-агента)" -ForegroundColor Green
Write-Host "  Локально:    curl http://127.0.0.1:7070/api/health" -ForegroundColor Green
Write-Host "  Логи:        ssh $SshUser@$VpsHost 'sudo journalctl -u chief-agent -f'" -ForegroundColor Green
Write-Host ""
Write-Host "  Дальше: установить Kednet-агент на ноуте (Windows):" -ForegroundColor Yellow
Write-Host "    1. Скопировать KEDNET_AGENT_TOKEN:" -ForegroundColor Yellow
Write-Host "       ssh $SshUser@$VpsHost 'grep KEDNET_AGENT_TOKEN /opt/chief-agent/.env'" -ForegroundColor Yellow
Write-Host "    2. Вписать токен в C:\Users\kfigh\kednet_agent\kednet_agent.config.json" -ForegroundColor Yellow
Write-Host "    3. cd C:\Users\kfigh\kednet_agent ; .\nssm\install-kednet-agent.ps1" -ForegroundColor Yellow
Write-Host "    4. Проверить: curl -H 'Authorization: Bearer <CHIEF_API_TOKEN>' http://$VpsHost`:7070/api/ws/status" -ForegroundColor Yellow
