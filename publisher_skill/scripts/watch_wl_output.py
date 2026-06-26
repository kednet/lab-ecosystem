"""
watch_wl_output.py — фоновый watcher: автопубликация при появлении новой книги.

Использование:
  python watch_wl_output.py                # запустить в фоне (polling каждые N сек)
  python watch_wl_output.py --once         # один проход и выход
  python watch_wl_output.py --interval=30  # каждые 30 сек (default: 60)
  python watch_wl_output.py --dry-run      # не запускать /publish, только лог

Что делает:
  Каждые N секунд сканирует wish_librarian/output/library/.
  Если появилась новая папка с готовыми артефактами (metadata.json + cover + summary.md + ...)
  и ещё не опубликована — вызывает subprocess для publish (render → deploy → announce).

Завершение: Ctrl+C.

Хранит прогресс в .watched.json (рядом со скриптом), чтобы не повторять.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
WL_OUTPUT = Path("C:/Users/kfigh/wish_librarian/output/library")
STATE_DIR = SKILL_ROOT / "state"
WATCHED_FILE = SKILL_ROOT / "scripts" / ".watched.json"

REQUIRED = ["metadata.json", "summary.md", "practical_tips.md", "reviews.md", "workbook.md", "buy_links.md"]

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def load_watched() -> dict:
    if not WATCHED_FILE.exists():
        return {"published": [], "last_seen": {}}
    try:
        return json.loads(WATCHED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"published": [], "last_seen": {}}


def save_watched(data: dict) -> None:
    WATCHED_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_ready(slug: str) -> bool:
    """Все обязательные артефакты WL на месте?"""
    p = WL_OUTPUT / slug
    if not p.exists():
        return False
    for f in REQUIRED:
        if not (p / f).exists():
            return False
    if not (p / "cover.jpg").exists() and not (p / "cover.png").exists():
        return False
    return True


def run_publish(slug: str, dry_run: bool = False) -> tuple[bool, str]:
    """Запустить /publish (render → deploy → announce) для slug."""
    print(f"[watch] → publish {slug}")
    if dry_run:
        return True, "dry-run"

    # В v0.2 — простой последовательный запуск скриптов
    # (Phase 3+ — единый CLI `publisher publish <slug>`)
    steps = [
        ("render", [sys.executable, str(SKILL_ROOT / "scripts" / "render_book.py"), slug]),
        ("deploy", [sys.executable, str(SKILL_ROOT / "scripts" / "deploy_pages.py"), slug]),
        ("tg",     [sys.executable, str(SKILL_ROOT / "scripts" / "post_telegram.py"), slug]),
        ("vk",     [sys.executable, str(SKILL_ROOT / "scripts" / "post_vk.py"), slug]),
        ("email",  [sys.executable, str(SKILL_ROOT / "scripts" / "send_email.py"), slug]),
        ("notify", [sys.executable, str(SKILL_ROOT / "scripts" / "notify_admin.py"), slug]),
    ]
    for name, cmd in steps:
        print(f"[watch]   step={name}: {' '.join(cmd[1].split('/')[-1:])}")
        try:
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            if r.returncode != 0:
                msg = f"{name} failed (rc={r.returncode}): {r.stderr[-300:]}"
                print(f"[watch]   ✗ {msg}", file=sys.stderr)
                return False, msg
            # last line of stdout = status
            last = r.stdout.strip().splitlines()[-1] if r.stdout.strip() else ""
            print(f"[watch]   ✓ {last[:120]}")
        except subprocess.TimeoutExpired:
            return False, f"{name} timeout"
        except Exception as e:
            return False, f"{name} error: {e}"
    return True, "ok"


def main():
    ap = argparse.ArgumentParser(description="Watch WL output for new books and auto-publish")
    ap.add_argument("--interval", type=int, default=60, help="Seconds between scans (default 60)")
    ap.add_argument("--once", action="store_true", help="Single pass and exit")
    ap.add_argument("--dry-run", action="store_true", help="Don't actually publish, just log")
    args = ap.parse_args()

    watched = load_watched()
    print(f"[watch] WL_OUTPUT = {WL_OUTPUT}")
    print(f"[watch] interval = {args.interval}s, once={args.once}, dry_run={args.dry_run}")
    print(f"[watch] already published: {len(watched['published'])}")

    iteration = 0
    try:
        while True:
            iteration += 1
            # Сканируем папки WL
            if not WL_OUTPUT.exists():
                print(f"[watch] WARN: {WL_OUTPUT} не существует")
            else:
                current_slugs = [p.name for p in WL_OUTPUT.iterdir() if p.is_dir()]
                watched["last_seen"] = {s: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z") for s in current_slugs}
                save_watched(watched)

                new_or_updated = []
                for s in current_slugs:
                    if s in watched["published"]:
                        # Уже опубликована — пропускаем (если не --force, Phase 2+)
                        continue
                    if is_ready(s):
                        new_or_updated.append(s)

                if new_or_updated:
                    print(f"[watch] iter={iteration} found {len(new_or_updated)} ready: {new_or_updated}")
                    for slug in new_or_updated:
                        ok, info = run_publish(slug, dry_run=args.dry_run)
                        if ok:
                            watched["published"].append(slug)
                            save_watched(watched)
                            print(f"[watch] ✓ {slug} done")
                        else:
                            print(f"[watch] ✗ {slug}: {info}")
                else:
                    if iteration == 1 or iteration % 10 == 0:
                        print(f"[watch] iter={iteration} ничего нового (всего папок: {len(current_slugs)})")

            if args.once:
                break
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[watch] остановлено пользователем (Ctrl+C)")
        save_watched(watched)
        return 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
