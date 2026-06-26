"""
deploy_experts.py
=================

Узкий деплой ТОЛЬКО экспертов из expert-reviews-hub на lab_site (app.pulab.ru).

Пайплайн:
  1. Preflight (slug, ssh-key, ssh-ping)
  2. sync_reviews_hub.py --experts → lab_site/src/data/experts/
  3. npm run build → lab_site/dist/
  4. rebuild_deploy.py → lab-site-deploy.tar.gz
  5. scp → root@89.108.88.74:/tmp/
  6. Атомарная распаковка с backup + chown deploy:deploy
  7. 4 smoke-проверки через curl
  8. Печать команды отката

Не трогает:
  ❌ lab-api (Node-воркер) и nginx config
  ❌ /etc/lab-site.env
  ❌ Отдельные HTML-страницы (льёт ВСЮ dist/ — иначе partial-deploy-pitfall)

Использование:
  python scripts/deploy_experts.py mark-rozin             # деплой
  python scripts/deploy_experts.py mark-rozin --dry-run    # план без выполнения
  python scripts/deploy_experts.py mark-rozin --skip-build # если dist/ уже собран
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

# UTF-8 fix for Windows
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


# ── Константы ──────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
LAB_SITE_ROOT = SCRIPT_DIR.parent
HUB_ROOT = LAB_SITE_ROOT.parent / "expert-reviews-hub"

VPS_HOST = "89.108.88.74"
VPS_USER = "root"  # нужен для chown deploy:deploy
SSH_KEY = Path.home() / ".ssh" / "lab_vps"
REMOTE_DIST = "/var/www/lab-site/dist"
REMOTE_TMP_TAR = "/tmp/lab-site-deploy.tar.gz"
LOCAL_TARBALL = Path(r"C:/Users/kfigh/temp/lab-site-deploy.tar.gz")

PUBLIC_BASE = "https://app.pulab.ru"


# ── Утилиты ───────────────────────────────────────────────
def log(msg: str):
    print(f"  {msg}", flush=True)


def step(title: str):
    print(f"\n▶ {title}", flush=True)


def fail(msg: str):
    print(f"\n  ✗ {msg}", file=sys.stderr, flush=True)
    sys.exit(1)


def run(cmd: list, cwd: Path | None = None, timeout: int = 300, check: bool = True) -> subprocess.CompletedProcess:
    """Запуск subprocess с UTF-8 stdout (Windows-safe)."""
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    return subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=check,
        env=env,
    )


# ── Preflight ─────────────────────────────────────────────
def preflight(slug: str) -> dict:
    """Проверки: файл есть, ssh-key на месте, ssh-ping, lab_site на месте."""
    step("Preflight")

    md_path = HUB_ROOT / "experts" / f"{slug}.md"
    if not md_path.exists():
        fail(f"Файл не найден: {md_path}. Сначала /experts add.")
    log(f"✅ Файл: {md_path}")

    # Проверка status: published
    text = md_path.read_text(encoding="utf-8")
    if "status: published" not in text:
        log(f"⚠️  status != published. Сначала /experts edit {slug} → 'готово'.")
        if not _confirm("Продолжить (slug будет задеплоен как draft)?"):
            fail("Отменено пользователем")
    else:
        log("✅ status: published")

    # SSH ключ
    if not SSH_KEY.exists():
        fail(f"SSH ключ не найден: {SSH_KEY}")
    log(f"✅ SSH-ключ: {SSH_KEY}")

    # ssh-ping
    log(f"Пингую {VPS_USER}@{VPS_HOST}...")
    try:
        result = run(
            ["ssh", "-i", str(SSH_KEY), "-o", "BatchMode=yes", "-o", "ConnectTimeout=5",
             f"{VPS_USER}@{VPS_HOST}", "echo connected"],
            timeout=10,
            check=False,
        )
        if result.returncode != 0 or "connected" not in result.stdout:
            fail(f"Не удаётся подключиться к {VPS_USER}@{VPS_HOST}\n  {result.stderr}")
    except Exception as e:
        fail(f"Ошибка ssh-ping: {e}")
    log(f"✅ SSH до {VPS_USER}@{VPS_HOST}")

    # lab_site на месте
    if not (LAB_SITE_ROOT / "package.json").exists():
        fail(f"lab_site/package.json не найден в {LAB_SITE_ROOT}")
    log(f"✅ lab_site: {LAB_SITE_ROOT}")

    # rebuild_deploy.py
    rebuild_script = Path(r"C:/Users/kfigh/temp/rebuild_deploy.py")
    if not rebuild_script.exists():
        fail(f"rebuild_deploy.py не найден: {rebuild_script}")
    log(f"✅ rebuild_deploy.py: {rebuild_script}")

    return {
        "md_path": md_path,
        "slug": slug,
    }


def _confirm(prompt: str) -> bool:
    """Спросить y/n (по умолчанию yes в --yes режиме)."""
    try:
        ans = input(f"{prompt} [y/N]: ").strip().lower()
    except EOFError:
        return False
    return ans in ("y", "yes")


# ── Этапы пайплайна ──────────────────────────────────────
def stage_sync(dry_run: bool = False) -> None:
    step(f"Stage: sync_reviews_hub.py --experts{' (dry-run)' if dry_run else ''}")
    cmd = [
        sys.executable,
        str(LAB_SITE_ROOT / "scripts" / "sync_reviews_hub.py"),
        "--experts",
        "--verbose",
    ]
    if dry_run:
        cmd.append("--dry-run")
    result = run(cmd, cwd=LAB_SITE_ROOT, timeout=60)
    log(result.stdout.strip() or "(no stdout)")


def build_site(skip_build: bool = False, dry_run: bool = False) -> None:
    step(f"Build: npm run build{' (skip)' if skip_build else ''}{' (dry-run)' if dry_run else ''}")
    if skip_build or dry_run:
        log("Пропускаю")
        return
    log("Это займёт ~60-90 секунд (prebuild: sitemap + spheres)...")
    # shell=True нужен на Windows — npm.bat/npm.cmd не находятся без shell
    proc = subprocess.Popen(
        "npm run build",
        cwd=LAB_SITE_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=True,
    )
    for line in proc.stdout:
        print("    " + line.rstrip(), flush=True)
    proc.wait()
    if proc.returncode != 0:
        fail(f"npm run build failed (exit {proc.returncode})")
    log("✅ dist/ собран")


def make_tarball(dry_run: bool = False) -> None:
    step(f"Tarball: rebuild_deploy.py → {LOCAL_TARBALL}{' (dry-run)' if dry_run else ''}")
    if dry_run:
        log("Пропускаю")
        return
    rebuild_script = Path(r"C:/Users/kfigh/temp/rebuild_deploy.py")
    # Запускаем rebuild_deploy.py — он кладёт в C:/Users/kfigh/temp/lab-site-deploy.tar.gz
    result = run([sys.executable, str(rebuild_script)], cwd=Path(r"C:/Users/kfigh"), timeout=120)
    log(result.stdout.strip())
    if not LOCAL_TARBALL.exists():
        fail(f"Tarball не создан: {LOCAL_TARBALL}")
    size_mb = LOCAL_TARBALL.stat().st_size / 1024 / 1024
    log(f"✅ {LOCAL_TARBALL} ({size_mb:.1f} МБ)")


def upload_tarball(dry_run: bool = False) -> None:
    step(f"Upload: scp → {VPS_USER}@{VPS_HOST}:{REMOTE_TMP_TAR}{' (dry-run)' if dry_run else ''}")
    if dry_run:
        log("Пропускаю")
        return
    result = run(
        ["scp", "-i", str(SSH_KEY), str(LOCAL_TARBALL), f"{VPS_USER}@{VPS_HOST}:{REMOTE_TMP_TAR}"],
        timeout=180,
        check=False,
    )
    if result.returncode != 0:
        fail(f"scp failed: {result.stderr}")
    log("✅ Залито")


def deploy_remote(dry_run: bool = False) -> str:
    """Атомарная распаковка на VPS с backup.
    Возвращает имя backup-папки (для команды отката)."""
    step(f"Remote: атомарная распаковка в {REMOTE_DIST}{' (dry-run)' if dry_run else ''}")
    backup_name = f"dist.bak.experts-{datetime.now().strftime('%Y%m%d-%H%M%S')}"

    cmd_ssh = (
        f"BACKUP={REMOTE_DIST}.bak.experts-$(date +%Y%m%d-%H%M%S) && "
        f"cp -a {REMOTE_DIST} \"$BACKUP\" && "
        f"cd {REMOTE_DIST}/.. && "
        f"rm -rf dist/_astro dist/experts dist/books && "
        f"tar -xzf {REMOTE_TMP_TAR} -C dist && "
        f"rm {REMOTE_TMP_TAR} && "
        f"chown -R deploy:deploy dist && "
        f'echo "BACKUP=$BACKUP"'
    )

    if dry_run:
        log(f"Bash: {cmd_ssh[:120]}...")
        return backup_name

    result = run(
        ["ssh", "-i", str(SSH_KEY), f"{VPS_USER}@{VPS_HOST}", cmd_ssh],
        timeout=300,
        check=False,
    )
    if result.returncode != 0:
        fail(f"ssh failed: {result.stderr}")
    log(result.stdout.strip())

    # Извлечь имя backup
    backup = ""
    for line in result.stdout.splitlines():
        if line.startswith("BACKUP="):
            backup = line.split("=", 1)[1].strip()
            break
    if not backup:
        log("⚠️ Не удалось извлечь имя backup, проверь вручную")
    return backup


def smoke(slug: str, dry_run: bool = False) -> dict:
    """4 smoke-проверки."""
    step(f"Smoke: 4 проверки{' (dry-run)' if dry_run else ''}")
    results = {}

    checks = [
        ("/experts/", f"{PUBLIC_BASE}/experts/"),
        (f"/experts/{slug}/", f"{PUBLIC_BASE}/experts/{slug}/"),
    ]
    for name, url in checks:
        if dry_run:
            log(f"  [DRY] curl -sI {url}")
            results[name] = "dry"
            continue
        result = run(
            ["curl", "-sI", "-o", "NUL", "-w", "%{http_code}", url],
            timeout=15,
            check=False,
        )
        code = result.stdout.strip()
        ok = code == "200"
        results[name] = code
        log(f"  {'✅' if ok else '❌'} {name} → HTTP {code}")

    # 3) Число превью экспертов на /experts/
    if dry_run:
        log("  [DRY] curl /experts/ | grep expert-card__name")
        results["preview_count"] = "dry"
    else:
        result = run(
            ["curl", "-s", f"{PUBLIC_BASE}/experts/"],
            timeout=15,
            check=False,
        )
        count = result.stdout.count("expert-card__name")
        results["preview_count"] = count
        ok = count >= 1
        log(f"  {'✅' if ok else '❌'} Превью expert-card__name: {count} шт")

    # 4) _astro/*.js отдаётся (нет white screen)
    if dry_run:
        log("  [DRY] curl /_astro/")
        results["_astro"] = "dry"
    else:
        result = run(
            ["curl", "-sI", f"{PUBLIC_BASE}/experts/"],
            timeout=15,
            check=False,
        )
        # Ищем ссылку на _astro в HTML
        if "_astro/" in result.stdout:
            # Извлечь URL _astro
            import re
            m = re.search(r'(https?://app\.pulab\.ru)?(/_astro/[\w./-]+)', result.stdout)
            astro_url = (m.group(1) or "") + m.group(2) if m else ""
            if astro_url:
                r2 = run(["curl", "-sI", "-o", "NUL", "-w", "%{http_code}", astro_url], timeout=10, check=False)
                code = r2.stdout.strip()
                results["_astro"] = code
                log(f"  {'✅' if code == '200' else '❌'} {astro_url} → HTTP {code}")
            else:
                log("  ⚠️ Не нашёл ссылку на _astro/ в HTML — пропускаю")
                results["_astro"] = "skip"
        else:
            log("  ℹ /experts/ HTML не содержит ссылок на _astro/ (статика без JS?)")
            results["_astro"] = "skip"

    return results


# ── Main ──────────────────────────────────────────────────
def main():
    p = argparse.ArgumentParser(
        description="deploy_experts.py — узкий деплой экспертов на lab_site VPS"
    )
    p.add_argument("slug", help="Slug эксперта (например, mark-rozin)")
    p.add_argument("--dry-run", action="store_true", help="Только показать план, ничего не делать")
    p.add_argument("--skip-build", action="store_true", help="Пропустить npm run build (dist/ уже собран)")
    p.add_argument("--yes", "-y", action="store_true", help="Пропустить подтверждение 'продолжить?'")
    args = p.parse_args()

    print("=" * 60)
    print(f"  deploy_experts.py")
    print(f"  Slug:   {args.slug}")
    print(f"  Режим:  {'DRY-RUN' if args.dry_run else 'REAL'}")
    print(f"  VPS:    {VPS_USER}@{VPS_HOST}")
    print(f"  Build:  {'skip' if args.skip_build else 'npm run build'}")
    print("=" * 60)

    # Preflight
    info = preflight(args.slug)

    if args.dry_run and not args.yes:
        log("Это dry-run — ничего не изменится")

    if not args.dry_run and not args.yes:
        if not _confirm(f"Задеплоить {info['slug']} на {VPS_HOST}?"):
            fail("Отменено пользователем")

    # Пайплайн
    stage_sync(dry_run=args.dry_run)
    build_site(skip_build=args.skip_build, dry_run=args.dry_run)
    make_tarball(dry_run=args.dry_run)
    upload_tarball(dry_run=args.dry_run)
    backup = deploy_remote(dry_run=args.dry_run)
    results = smoke(args.slug, dry_run=args.dry_run)

    # Итог
    print()
    print("=" * 60)
    print("  SUMMARY")
    if args.dry_run:
        print(f"  ✅ DRY-RUN завершён. Проверьте план и запустите без --dry-run.")
    else:
        all_ok = (
            results.get("/experts/") == "200"
            and results.get(f"/experts/{args.slug}/") == "200"
            and (isinstance(results.get("preview_count"), int) and results["preview_count"] >= 1)
            and results.get("_astro") in ("200", "skip")
        )
        print(f"  Backup: {backup}")
        print(f"  Smoke:  {'✅ OK' if all_ok else '❌ ЕСТЬ ПРОБЛЕМЫ'}")
        if not all_ok:
            print()
            print("  ⚠️ Не все smoke-проверки прошли. Команда отката:")
            print(f'    ssh -i {SSH_KEY} {VPS_USER}@{VPS_HOST} \\')
            print(f"      'rm -rf {REMOTE_DIST} && \\")
            print(f"       mv {backup} {REMOTE_DIST} && \\")
            print(f"       chown -R deploy:deploy {REMOTE_DIST}'")
            sys.exit(1)
        else:
            print()
            print(f"  👉 Проверь в браузере:")
            print(f"     {PUBLIC_BASE}/experts/")
            print(f"     {PUBLIC_BASE}/experts/{args.slug}/")
            print()
            print(f"  ⚠️ Откатить если что:")
            print(f'    ssh -i {SSH_KEY} {VPS_USER}@{VPS_HOST} \\')
            print(f"      'rm -rf {REMOTE_DIST} && \\")
            print(f"       mv {backup} {REMOTE_DIST} && \\")
            print(f"       chown -R deploy:deploy {REMOTE_DIST}'")
    print("=" * 60)


if __name__ == "__main__":
    main()
