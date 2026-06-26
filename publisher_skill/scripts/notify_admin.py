"""
notify_admin.py — Stage 4: уведомление @kfigh в Telegram.

Использование:
  python notify_admin.py <slug>              # автоматически берёт данные из state
  python notify_admin.py <slug> --error "что-то сломалось"

Требует:
  TG_BOT_TOKEN
  TG_ADMIN_CHAT_ID  — личка @kfigh
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
import ssl
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def send_tg(token: str, chat_id: str, text: str) -> bool:
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": "true",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            data = json.loads(r.read().decode("utf-8"))
            return data.get("ok", False)
    except Exception as e:
        print(f"[notify] ✗ {e}", file=sys.stderr)
        return False


def main():
    ap = argparse.ArgumentParser(description="Notify admin @kfigh")
    ap.add_argument("slug")
    ap.add_argument("--error", default=None, help="Текст ошибки (если что-то упало)")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    slug = args.slug
    print(f"[notify] {slug}")

    data = state.load(slug)
    title = data.get("page_path") or slug

    # Достать title из metadata
    meta_p = Path("C:/Users/kfigh/lab_site/src/data/books") / slug / "metadata.json"
    if meta_p.exists():
        try:
            with open(meta_p, "r", encoding="utf-8") as f:
                meta = json.load(f)
                title = f"{meta.get('title', title)} — {meta.get('author', '')}"
        except Exception:
            pass

    token = os.environ.get("TG_BOT_TOKEN")
    admin = os.environ.get("TG_ADMIN_CHAT_ID", "@kfigh")
    if not token and not args.dry_run:
        print("[notify] ✗ TG_BOT_TOKEN не задан", file=sys.stderr)
        sys.exit(1)

    if args.error:
        # Failure-формат
        text = (
            f"<b>❌ Ошибка публикации:</b> {title}\n\n"
            f"Slug: <code>{slug}</code>\n"
            f"Ошибка: {args.error}\n"
        )
    else:
        # Success-формат
        live = data.get("live_url") or f"https://pulab.online/books/{slug}"
        posted = data.get("channels_posted") or {}
        tg_ok = "✓" if posted.get("tg") else "—"
        vk_ok = "✓" if posted.get("vk") else "—"
        em_ok = "✓" if posted.get("email") else "(Phase 2+)"
        preview = data.get("preview_path") or f"tmp/{slug}-deploy.png"
        text = (
            f"<b>📚 Опубликовано:</b> {title}\n\n"
            f"Страница: <a href=\"{live}\">{live}</a>\n"
            f"Превью: <code>{preview}</code>\n\n"
            f"<b>Каналы анонса:</b>\n"
            f"• Telegram: {tg_ok}\n"
            f"• VK: {vk_ok}\n"
            f"• Email: {em_ok}\n"
        )

    if args.dry_run:
        print(f"[notify] DRY-RUN. Текст:\n{text}")
        return

    ok = send_tg(token, admin, text)
    if ok:
        print(f"[notify] ✓ отправлено админу")
    else:
        print(f"[notify] ✗ не удалось отправить", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
