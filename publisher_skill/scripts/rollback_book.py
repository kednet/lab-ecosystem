"""
rollback_book.py — откатить деплой книги к предыдущему коммиту.

Использование:
  python rollback_book.py <slug>                  # rollback последний deploy
  python rollback_book.py <slug> --to=<commit>   # откатить к конкретному commit

NB: Cloudflare Pages поддерживает rollback через `wrangler pages deployment rollback`.
NB: state/<slug>.json не меняется автоматически (мы «откатываем публикацию», а не state).
"""
from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
LAB_SITE_ROOT = Path("C:/Users/kfigh/lab_site")

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def list_deploys(project: str) -> str:
    """wrangler pages deployment list."""
    r = subprocess.run(
        ["npx", "wrangler", "pages", "deployment", "list", f"--project-name={project}"],
        cwd=str(LAB_SITE_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )
    return r.stdout


def rollback(project: str, commit: str | None = None) -> tuple[bool, str]:
    args = ["npx", "wrangler", "pages", "deployment", "rollback"]
    if commit:
        args.append(commit)
    args.append(f"--project-name={project}")
    print(f"[rollback] {' '.join(args)}")
    r = subprocess.run(args, cwd=str(LAB_SITE_ROOT), capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        return False, r.stderr[-500:]
    return True, r.stdout[-500:]


def main():
    ap = argparse.ArgumentParser(description="Rollback book page deploy")
    ap.add_argument("slug")
    ap.add_argument("--to", default=None, help="Commit hash to rollback to (default: previous)")
    ap.add_argument("--list", action="store_true", help="Show recent deployments and exit")
    ap.add_argument("--yes", action="store_true", help="Skip confirmation prompt")
    args = ap.parse_args()

    slug = args.slug
    project = os.environ.get("CF_PAGES_PROJECT", "pulab")
    print(f"[rollback] slug={slug} project={project}")

    if args.list:
        print(list_deploys(project))
        return

    # Подтверждение
    if not args.yes:
        ans = input(f"Откатить {slug} на предыдущий deploy? (yes/no): ")
        if ans != "yes":
            print("Отменено.")
            return

    ok, info = rollback(project, args.to)
    if not ok:
        print(f"[rollback] ✗ {info}", file=sys.stderr)
        sys.exit(1)
    print(f"[rollback] ✓ {info}")
    print(f"\n[rollback] Готово. Проверь https://pulab.online/books/{slug}")
    print(f"NB: state/<slug>.json НЕ обновлён — если что-то пошло не так, используй --force при следующем /publish")


if __name__ == "__main__":
    main()
