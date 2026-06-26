"""
post_telegram.py — Stage 3a: анонс в Telegram-канал.

Использование:
  python post_telegram.py <slug>
  python post_telegram.py <slug> --dry-run   # не шлёт, только в tmp/

Требует:
  TG_BOT_TOKEN   — bot token от @BotFather
  TG_CHANNEL_ID  — @pulaab_ru (например)
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime
from pathlib import Path

import urllib.request
import urllib.error
import urllib.parse
import json
import ssl

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
LAB_SITE_ROOT = Path("C:/Users/kfigh/lab_site")
TEMPLATE_PATH = SKILL_ROOT / "templates" / "announcement-tg.md"
TMP_DIR = SKILL_ROOT / "tmp"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# Корпоративный MITM
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def load_metadata(slug: str) -> dict:
    p = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "metadata.json"
    if not p.exists():
        # Fallback: WL
        p = Path("C:/Users/kfigh/wish_librarian/output/library") / slug / "metadata.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def build_text(slug: str, meta: dict, live_url: str) -> str:
    """Сгенерировать текст анонса по шаблону."""
    template = TEMPLATE_PATH.read_text(encoding="utf-8")
    title = meta.get("title", "")
    author = meta.get("author", "")
    year = meta.get("year", "")

    # 3 идеи — из metadata.json::key_ideas (готовый список в WL)
    key_ideas = meta.get("key_ideas") or []
    ideas = (key_ideas + ["(дополните вручную)"] * 3)[:3]

    text = template
    text = text.replace("{title}", title)
    text = text.replace("{author}", author)
    text = text.replace("{year}", f", {year}" if year else "")
    text = text.replace("{live_url}", live_url)
    text = text.replace("{idea_1}", ideas[0])
    text = text.replace("{idea_2}", ideas[1])
    text = text.replace("{idea_3}", ideas[2])
    return text


def tg_api(method: str, token: str, data: dict, files: dict | None = None) -> dict:
    """Вызов Telegram Bot API."""
    url = f"https://api.telegram.org/bot{token}/{method}"
    if files is None:
        # JSON
        req = urllib.request.Request(
            url,
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
    else:
        # multipart/form-data
        boundary = "----PubSkillBoundary"
        body = []
        for k, v in data.items():
            body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n")
        for k, (filename, content) in files.items():
            body.append(f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{filename}\"\r\nContent-Type: application/octet-stream\r\n\r\n")
            body_bytes = "".join(body).encode("utf-8") + content + f"\r\n--{boundary}--\r\n".encode("utf-8")
        req = urllib.request.Request(url, data=body_bytes, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})

    try:
        with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        return {"ok": False, "error": f"HTTP {e.code}: {err_body[:300]}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


def main():
    ap = argparse.ArgumentParser(description="Post TG announcement")
    ap.add_argument("slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    slug = args.slug
    print(f"[tg] {slug}")

    # 1. Идемпотентность
    if not args.dry_run and not state.channel_pending(slug, "tg"):
        print(f"[tg] ✓ уже отправлено ранее (state.channels_posted.tg != null). Пропуск.")
        return

    # 2. Данные
    token = os.environ.get("TG_BOT_TOKEN")
    channel = os.environ.get("TG_CHANNEL_ID", "@pulaab_ru")
    if not token and not args.dry_run:
        print("[tg] ✗ TG_BOT_TOKEN не задан", file=sys.stderr)
        sys.exit(1)

    data = state.load(slug)
    live_url = data.get("live_url") or f"https://pulab.online/books/{slug}"
    meta = load_metadata(slug)
    text = build_text(slug, meta, live_url)

    cover = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "cover.jpg"
    if not cover.exists():
        cover = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "cover.png"

    # 3. Dry-run
    if args.dry_run:
        out = TMP_DIR / f"{slug}-tg-draft.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"[tg] DRY-RUN. Текст в {out}")
        return

    # 4. Реальная отправка: sendPhoto + caption (HTML)
    payload = {
        "chat_id": channel,
        "caption": text,
        "parse_mode": "HTML",
        "disable_notification": "false",
    }
    files = None
    if cover.exists():
        with open(cover, "rb") as f:
            files = {"photo": (cover.name, f.read())}
        resp = tg_api("sendPhoto", token, payload, files)
    else:
        print(f"[tg] WARN: cover не найден ({cover}). Шлю только текст.")
        resp = tg_api("sendMessage", token, payload)

    if resp.get("ok"):
        msg_id = resp.get("result", {}).get("message_id", "?")
        print(f"[tg] ✓ отправлено (msg_id={msg_id})")
        state.mark_channel_posted(slug, "tg")
    else:
        err = resp.get("error", "unknown")
        print(f"[tg] ✗ {err}", file=sys.stderr)
        state.mark_channel_failed(slug, "tg", err)
        sys.exit(1)


if __name__ == "__main__":
    main()
