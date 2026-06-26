"""
deploy_pages.py — Stage 2: Astro build + wrangler pages deploy + HTTP 200 check.

Использование:
  python deploy_pages.py <slug>                  # build + deploy + check
  python deploy_pages.py <slug> --no-build       # только deploy (если build уже был)
  python deploy_pages.py <slug> --skip-check     # не проверять 200 (быстрее)
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
LAB_SITE_ROOT = Path("C:/Users/kfigh/lab_site")
TMP_DIR = SKILL_ROOT / "tmp"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def run_build() -> tuple[bool, float]:
    """npm run build в lab_site. Возвращает (ok, duration_sec)."""
    print(f"[deploy] npm run build → {LAB_SITE_ROOT}")
    start = time.time()
    try:
        result = subprocess.run(
            ["npm", "run", "build"],
            cwd=str(LAB_SITE_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        print(f"[deploy] ✗ build timeout (300s)", file=sys.stderr)
        return False, 300.0
    dur = time.time() - start

    if result.returncode != 0:
        print(f"[deploy] ✗ build failed (rc={result.returncode})", file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        return False, dur

    print(f"[deploy] ✓ build OK ({dur:.1f}s)")
    return True, dur


def run_wrangler_deploy() -> tuple[bool, str]:
    """wrangler pages deploy. Возвращает (ok, deploy_url)."""
    cf_project = os.environ.get("CF_PAGES_PROJECT", "pulab")
    print(f"[deploy] wrangler pages deploy → {cf_project}")
    dist = LAB_SITE_ROOT / "dist"
    if not dist.exists():
        return False, f"нет {dist} — сначала build"

    try:
        result = subprocess.run(
            ["npx", "wrangler", "pages", "deploy", str(dist), f"--project-name={cf_project}"],
            cwd=str(LAB_SITE_ROOT),
            capture_output=True,
            text=True,
            timeout=300,
        )
    except subprocess.TimeoutExpired:
        return False, "wrangler timeout (300s)"

    if result.returncode != 0:
        print(f"[deploy] ✗ wrangler failed (rc={result.returncode})", file=sys.stderr)
        print(result.stderr[-2000:], file=sys.stderr)
        return False, f"wrangler rc={result.returncode}"

    out = result.stdout
    print(f"[deploy] ✓ wrangler OK")
    # Достать URL из вывода (формат: "Deployment complete! https://...")
    deploy_url = ""
    for line in out.splitlines():
        if "https://" in line:
            deploy_url = line.strip()
            break
    return True, deploy_url


def check_live(slug: str) -> tuple[bool, str]:
    """GET https://pulab.online/books/<slug> → проверить 200."""
    url = f"https://pulab.online/books/{slug}"
    print(f"[deploy] GET {url}")
    try:
        result = subprocess.run(
            ["curl", "-sI", "-o", "NUL", "-w", "%{http_code}", url],
            capture_output=True,
            text=True,
            timeout=30,
        )
        code = result.stdout.strip()
    except Exception as e:
        return False, f"curl error: {e}"

    if code == "200":
        return True, url
    return False, f"HTTP {code}"


def main():
    ap = argparse.ArgumentParser(description="Deploy book page to Cloudflare Pages")
    ap.add_argument("slug")
    ap.add_argument("--no-build", action="store_true")
    ap.add_argument("--skip-check", action="store_true")
    args = ap.parse_args()

    slug = args.slug
    print(f"[deploy] {slug}")

    # 1. Build (если не --no-build)
    build_dur = 0.0
    if not args.no_build:
        ok, build_dur = run_build()
        if not ok:
            state.update(slug, status="failed", error=f"build failed")
            sys.exit(1)
    else:
        print(f"[deploy] --no-build: пропускаю npm run build")

    # 2. Wrangler deploy
    ok, deploy_info = run_wrangler_deploy()
    if not ok:
        state.update(slug, status="failed", error=f"deploy failed: {deploy_info}")
        sys.exit(1)

    # 3. Проверка 200
    live_url = f"https://pulab.online/books/{slug}"
    if not args.skip_check:
        ok, info = check_live(slug)
        if not ok:
            print(f"[deploy] ✗ {info}", file=sys.stderr)
            state.update(slug, status="failed", error=f"live check: {info}")
            sys.exit(1)
        print(f"[deploy] ✓ live: {live_url}")

    # 4. State
    state.update(
        slug,
        status="deployed",
        deployed_at=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        live_url=live_url,
        build_duration_sec=round(build_dur, 2),
    )
    print(f"[deploy] ✓ state: deployed")
    print(f"\n[deploy] Готово. Следующий шаг: announce (scripts/post_telegram.py {slug})")


if __name__ == "__main__":
    main()
