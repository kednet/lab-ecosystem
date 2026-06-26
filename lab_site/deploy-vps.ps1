# deploy-vps.ps1
#
# Полный деплой Lab site на Reg.ru VPS одной командой.
#
# Что делает:
#   1. Собирает Astro (npm run build)  → dist/
#   2. Собирает воркер (cd worker && npm ci --omit=dev && npm run build)
#   3. rsync-ит dist/ → /var/www/lab-site/dist/ на VPS
#   4. rsync-ит worker/ → /home/deploy/app/worker/ на VPS
#   5. rsync-ит deploy/ → /home/deploy/app/deploy/ на VPS
#   6. systemctl restart lab-api + nginx reload
#   7. Проверяет /health
#
# Использование:
#   .\deploy-vps.ps1 -VpsHost 185.244.xx.xx
#   .\deploy-vps.ps1 -VpsHost 185.244.xx.xx -SkipBuild
#   .\deploy-vps.ps1 -VpsHost 185.244.xx.xx -DryRun
#
# Требования:
#   - SSH-ключ $HOME\.ssh\lab_vps (ed25519)
#   - rsync в PATH (Git Bash / WSL / OpenSSH build)
#   - на VPS уже сделан начальный сетап (см. deploy/README.md, шаги 1-5)

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$VpsHost,

    [string]$SshKey = "$HOME\.ssh\lab_vps",

    [string]$SshUser = "deploy",

    [switch]$SkipBuild,

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
    Fail "SSH-ключ не найден: $SshKey. Сгенерируйте: ssh-keygen -t ed25519 -C lab-vps -f $SshKey"
}
Ok "SSH-ключ: $SshKey"

# rsync (встроен в Windows 10+ через OpenSSH, иначе — Git Bash)
$rsync = (Get-Command rsync -ErrorAction SilentlyContinue)
if (-not $rsync) {
    Fail "rsync не найден в PATH. Поставьте Git for Windows или активируйте WSL."
}
Ok "rsync: $($rsync.Source)"

# ssh ping
$ping = & ssh -i $SshKey -o BatchMode=yes -o ConnectTimeout=5 "$SshUser@$VpsHost" "echo connected" 2>&1
if ($LASTEXITCODE -ne 0) {
    Fail "Не удаётся подключиться к $SshUser@$VpsHost. Проверьте ключ, IP и ufw."
}
Ok "SSH до $SshUser@$VpsHost"

# ────────────────────────────────────────────────
# Сборка Astro
# ────────────────────────────────────────────────
if (-not $SkipBuild) {
    Step "Сборка Astro (npm run build)"
    Push-Location $root
    try {
        npm run build 2>&1 | Tee-Object -Variable buildOut | Out-Host
        if ($LASTEXITCODE -ne 0) { Fail "Astro build failed" }
    } finally {
        Pop-Location
    }
    Ok "dist/ собран"
} else {
    Warn "Сборка пропущена (SkipBuild)"
}

# ────────────────────────────────────────────────
# Сборка воркера
# ────────────────────────────────────────────────
if (-not $SkipBuild) {
    Step "Сборка воркера (worker)"
    Push-Location "$root\worker"
    try {
        # Установим прод-зависимости (без dev)
        npm ci --omit=dev 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) { Fail "npm ci failed" }

        # Build
        npm run build 2>&1 | Out-Host
        if ($LASTEXITCODE -ne 0) { Fail "worker build failed" }
    } finally {
        Pop-Location
    }
    Ok "worker/dist/ собран"
}

# ────────────────────────────────────────────────
# Проверка артефактов
# ────────────────────────────────────────────────
Step "Проверка артефактов"

if (-not (Test-Path "$root\dist\index.html")) {
    Fail "dist/index.html не найден. Запустите npm run build."
}
Ok "dist/index.html"

if (-not (Test-Path "$root\dist\fonts\manrope-400.woff2")) {
    Warn "dist/fonts/manrope-400.woff2 отсутствует — шрифты не попадут в деплой"
} else {
    Ok "dist/fonts/ содержит шрифты"
}

if (-not (Test-Path "$root\worker\dist\server.js")) {
    Fail "worker/dist/server.js не найден. Запустите npm run build в worker/."
}
Ok "worker/dist/server.js"

# ────────────────────────────────────────────────
# Rsync на VPS
# ────────────────────────────────────────────────
$sshOpts = "-i `"$SshKey`" -o StrictHostKeyChecking=accept-new"
$rsyncOpts = @("-avz", "--delete", "-e", "ssh $sshOpts")

if ($DryRun) {
    $rsyncOpts += "--dry-run"
    Warn "Dry-run mode: файлы не будут загружены"
}

Step "Загрузка dist/ → /var/www/lab-site/dist/"
& rsync @rsyncOpts "$root\dist\" "${SshUser}@${VpsHost}:/var/www/lab-site/dist/" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "rsync dist/ failed" }
Ok "dist/ загружен"

Step "Загрузка worker/ → /home/deploy/app/worker/"
$workerRsync = @("-avz", "--delete", "-e", "ssh $sshOpts",
    "--exclude=.wrangler", "--exclude=.wrangler-state", "--exclude=node_modules")
if ($DryRun) { $workerRsync += "--dry-run" }
& rsync @workerRsync "$root\worker\" "${SshUser}@${VpsHost}:/home/deploy/app/worker/" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "rsync worker/ failed" }
Ok "worker/ загружен"

Step "Загрузка deploy/ → /home/deploy/app/deploy/"
$deployRsync = @("-avz", "-e", "ssh $sshOpts")
if ($DryRun) { $deployRsync += "--dry-run" }
& rsync @deployRsync "$root\deploy\" "${SshUser}@${VpsHost}:/home/deploy/app/deploy/" 2>&1 | Out-Host
if ($LASTEXITCODE -ne 0) { Fail "rsync deploy/ failed" }
Ok "deploy/ загружен"

# ────────────────────────────────────────────────
# Установка прод-зависимостей на VPS
# ────────────────────────────────────────────────
if (-not $DryRun) {
    Step "Установка prod-зависимостей воркера на VPS"
    $cmd = "cd /home/deploy/app/worker && npm ci --omit=dev 2>&1 | tail -5"
    & ssh $sshOpts "${SshUser}@${VpsHost}" $cmd 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "npm ci on VPS failed" }
    Ok "node_modules обновлены"
}

# ────────────────────────────────────────────────
# Перезапуск сервисов
# ────────────────────────────────────────────────
if (-not $DryRun) {
    Step "Перезапуск lab-api + reload nginx"

    # Применяем обновлённый nginx.conf (если менялся)
    & ssh $sshOpts "${SshUser}@${VpsHost}" "sudo cp /home/deploy/app/deploy/nginx.conf /etc/nginx/sites-available/lab-site 2>/dev/null && sudo ln -sf /etc/nginx/sites-available/lab-site /etc/nginx/sites-enabled/ && sudo nginx -t && sudo systemctl reload nginx" 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { Warn "nginx reload — что-то не так (проверьте: ssh $SshUser@$VpsHost 'sudo nginx -t')" }
    else { Ok "nginx перезагружен" }

    # Применяем обновлённый systemd unit (если менялся)
    & ssh $sshOpts "${SshUser}@${VpsHost}" "sudo cp /home/deploy/app/deploy/lab-api.service /etc/systemd/system/ 2>/dev/null && sudo systemctl daemon-reload && sudo systemctl restart lab-api" 2>&1 | Out-Host
    if ($LASTEXITCODE -ne 0) { Fail "systemctl restart lab-api failed" }
    Ok "lab-api перезапущен"

    Start-Sleep -Seconds 2
}

# ────────────────────────────────────────────────
# Smoke-test
# ────────────────────────────────────────────────
if (-not $DryRun) {
    Step "Smoke-test: /health"

    $health = & ssh $sshOpts "${SshUser}@${VpsHost}" "curl -s --max-time 5 http://127.0.0.1:8787/health" 2>&1
    if ($LASTEXITCODE -ne 0) {
        Warn "Не удалось подключиться к воркеру. Проверьте: ssh $SshUser@$VpsHost 'sudo journalctl -u lab-api -n 50'"
    } else {
        Write-Host "  → $health" -ForegroundColor Yellow
        if ($health -match '"status":"ok"') {
            Ok "lab-api отвечает OK"
        } else {
            Warn "lab-api ответил, но ответ неожиданный"
        }
    }

    Step "Smoke-test: главная страница"
    try {
        $resp = Invoke-WebRequest -Uri "https://app.pulab.online/" -UseBasicParsing -TimeoutSec 10 -SkipHttpErrorCheck
        if ($resp.StatusCode -eq 200) {
            Ok "https://app.pulab.online/  HTTP 200"
        } else {
            Warn "https://app.pulab.online/  HTTP $($resp.StatusCode)"
        }
    } catch {
        Warn "Не удалось открыть https://app.pulab.online/ — проверьте DNS и сертификат"
    }
}

Step "Готово"
Write-Host "  Сайт:   https://app.pulab.online/" -ForegroundColor Green
Write-Host "  API:    https://app.pulab.online/health" -ForegroundColor Green
Write-Host "  Логи:   ssh $SshUser@$VpsHost 'sudo journalctl -u lab-api -f'" -ForegroundColor Green
