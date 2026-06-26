"""
post_vk.py — Stage 3b: анонс в VK-группу pulabru (id=237295798).

Использование:
  python post_vk.py <slug>
  python post_vk.py <slug> --dry-run

Требует:
  VK_ACCESS_TOKEN  — токен сообщества pulabru (или пользовательский с правами wall.post)
  VK_GROUP_ID      — 237295798 (default)
"""
from __future__ import annotations

import argparse
import os
import sys
import json
import urllib.request
import urllib.error
import ssl
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
LAB_SITE_ROOT = Path("C:/Users/kfigh/lab_site")
TEMPLATE_PATH = SKILL_ROOT / "templates" / "announcement-vk.md"
TMP_DIR = SKILL_ROOT / "tmp"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

# MITM
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def load_metadata(slug: str) -> dict:
    p = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "metadata.json"
    if not p.exists():
        p = Path("C:/Users/kfigh/wish_librarian/output/library") / slug / "metadata.json"
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def build_text(slug: str, meta: dict, live_url: str) -> str:
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


def vk_api(method: str, params: dict, token: str) -> dict:
    """Вызов VK API."""
    params["access_token"] = token
    params["v"] = "5.199"
    url = f"https://api.vk.com/method/{method}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"error": {"error_msg": f"HTTP {e.code}: {e.read().decode()[:300]}"}}
    except Exception as e:
        return {"error": {"error_msg": str(e)}}


def upload_cover(slug: str, group_id: int, token: str) -> str | None:
    """Загрузить cover.jpg на стену группы. Возвращает attachment (photo123_456) или None."""
    cover = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "cover.jpg"
    if not cover.exists():
        cover = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "cover.png"
    if not cover.exists():
        print(f"[vk] WARN: cover не найден")
        return None

    # 1. photos.getWallUploadServer
    r = vk_api("photos.getWallUploadServer", {"group_id": group_id}, token)
    if "error" in r:
        print(f"[vk] ✗ getWallUploadServer: {r['error']}", file=sys.stderr)
        return None
    upload_url = r["response"]["upload_url"]

    # 2. multipart upload
    boundary = "----VKPubSkill"
    with open(cover, "rb") as f:
        photo_data = f.read()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"{cover.name}\"\r\nContent-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + photo_data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(upload_url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
            upload_resp = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"[vk] ✗ upload: {e}", file=sys.stderr)
        return None

    # 3. photos.saveWallPhoto
    r = vk_api("photos.saveWallPhoto", {
        "group_id": group_id,
        "photo": upload_resp["photo"],
        "server": upload_resp["server"],
        "hash": upload_resp["hash"],
    }, token)
    if "error" in r:
        print(f"[vk] ✗ saveWallPhoto: {r['error']}", file=sys.stderr)
        return None

    photo = r["response"][0]
    return f"photo{photo['owner_id']}_{photo['id']}"


def main():
    ap = argparse.ArgumentParser(description="Post VK announcement")
    ap.add_argument("slug")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    slug = args.slug
    print(f"[vk] {slug}")

    if not args.dry_run and not state.channel_pending(slug, "vk"):
        print(f"[vk] ✓ уже отправлено ранее. Пропуск.")
        return

    token = os.environ.get("VK_ACCESS_TOKEN")
    group_id = int(os.environ.get("VK_GROUP_ID", "237295798"))
    if not token and not args.dry_run:
        print("[vk] ✗ VK_ACCESS_TOKEN не задан", file=sys.stderr)
        sys.exit(1)

    data = state.load(slug)
    live_url = data.get("live_url") or f"https://pulab.online/books/{slug}"
    meta = load_metadata(slug)
    text = build_text(slug, meta, live_url)

    if args.dry_run:
        out = TMP_DIR / f"{slug}-vk-draft.txt"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(text, encoding="utf-8")
        print(f"[vk] DRY-RUN. Текст в {out}")
        return

    # 1. Загрузить cover (если есть)
    attachment = upload_cover(slug, group_id, token)
    attachments = []
    if attachment:
        attachments.append(attachment)
    else:
        # Нет обложки — НЕЛЬЗЯ класть ссылку в attachments
        # (VK правило link_photo_sizing_rule: link требует фото)
        # Решение: ссылка уже в тексте, attachments пустой.
        print(f"[vk] ℹ cover отсутствует, ссылка будет в тексте поста")

    # 2. wall.post
    params = {
        "owner_id": -group_id,  # минус = группа
        "from_group": 1,
        "message": text,
        "signed": 0,
    }
    if attachments:
        params["attachments"] = ",".join(attachments)
    r = vk_api("wall.post", params, token)
    if "error" in r:
        err = r["error"].get("error_msg", str(r["error"]))
        print(f"[vk] ✗ {err}", file=sys.stderr)
        state.mark_channel_failed(slug, "vk", err)
        sys.exit(1)

    post_id = r.get("response", {}).get("post_id", "?")
    print(f"[vk] ✓ опубликовано (post_id={post_id})")
    state.mark_channel_posted(slug, "vk")


if __name__ == "__main__":
    main()
