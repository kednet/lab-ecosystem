"""
post_channels.py — универсальный постер для 4 каналов: VK, Telegram, OK, RSS (Дзен).

Не привязан к книгам — работает с произвольным контентом (лид-магнит, статья, анонс).

Использование:
  python post_channels.py --content detector --channels vk,tg,ok
  python post_channels.py --content detector --channels vk --dry-run
  python post_channels.py --text-file post.txt --image image.jpg --channels vk,tg

Контент:
  --content detector          # встроенный шаблон для /detector/
  --content type:free         # кастомный текст (см. templates/post-channels/)
  --text-file path/to.txt     # прямой текст из файла

Адаптеры каналов:
  - VK    : токен VK_ACCESS_TOKEN в .env
  - TG    : токен TG_BOT_TOKEN + TG_CHANNEL_ID
  - OK    : токен OK_ACCESS_TOKEN + OK_GROUP_ID
  - ZEN   : без токена — только генерирует RSS, постит ручной добавкой в Дзен Studio

Если токен канала не задан — канал скипается с warning (не падает).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import ssl
import urllib.parse
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from xml.sax.saxutils import escape

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_ROOT / "templates" / "post-channels"
LAB_SITE_ROOT = Path("C:/Users/kfigh/lab_site")
TMP_DIR = SKILL_ROOT / "tmp"
TMP_DIR.mkdir(parents=True, exist_ok=True)

# === ENV ===
def load_env():
    env_path = SKILL_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.split("#", 1)[0].strip()  # отрезаем инлайн-комментарий «# ...»
        os.environ.setdefault(k.strip(), v)

load_env()

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent))
import pending_store  # noqa: E402

# MITM
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


# === Affiliate (AdvCake → Литрес) ===

# Подключаем модуль affiliate_links для генерации партнёрских URL.
# Если модуль не найден (например, при первом деплое до сборки) — фоллбек на None.
try:
    sys.path.insert(0, str(SKILL_ROOT.parent))
    from affiliate_links.advcake import (
        build_litres_url_with_label,
        make_book_affiliate,
    )
    _AFFILIATE_OK = True
except Exception as _e:
    _AFFILIATE_OK = False
    _AFFILIATE_IMPORT_ERR = _e

    def build_litres_url_with_label(*args, **kwargs):  # type: ignore
        raise RuntimeError(f"affiliate_links not available: {_AFFILIATE_IMPORT_ERR}")


_BOOKS_JSON = LAB_SITE_ROOT / "src" / "data" / "books.json"
_BOOKS_CACHE: dict[str, dict] | None = None


def _load_books_index() -> dict[str, dict]:
    """{slug → book dict}, с ленивой загрузкой и кешем."""
    global _BOOKS_CACHE
    if _BOOKS_CACHE is None:
        if not _BOOKS_JSON.exists():
            _BOOKS_CACHE = {}
        else:
            try:
                _BOOKS_CACHE = {
                    b["slug"]: b
                    for b in json.loads(_BOOKS_JSON.read_text(encoding="utf-8"))["books"]
                }
            except Exception:
                _BOOKS_CACHE = {}
    return _BOOKS_CACHE


def build_affiliate_link(
    slug: str,
    *,
    channel: str,
    post_id: str | int | None = None,
    date: str | None = None,
    fallback_to_book_url: bool = True,
) -> str | None:
    """Возвращает партнёрский URL Литреса для книги из books.json.

    Args:
        slug: slug книги (например, 'alhimik-koeluo').
        channel: канал постинга (vk/tg/ok/zen/site) — идёт в subid.
        post_id: id поста — идёт в subid.
        date: дата в формате YYYY-MM-DD — идёт в subid.
        fallback_to_book_url: если affiliate нет, вернуть book.litres_url или None.

    Returns:
        Полный URL с UTM + erid + subid, или None.
    """
    if not _AFFILIATE_OK:
        return None
    books = _load_books_index()
    book = books.get(slug)
    if not book:
        return None
    aff = book.get("affiliate") or {}
    book_path = aff.get("litres_url", "")
    if not book_path:
        if fallback_to_book_url:
            return None
        return None
    # Нормализуем litres_url → относительный path для build_litres_url_with_label
    # litres_url: "https://www.litres.ru/book/paulo-koelo/alhimik-122351/"
    from urllib.parse import urlparse
    parsed = urlparse(book_path)
    rel_path = parsed.path
    return build_litres_url_with_label(
        rel_path,
        channel=channel,
        post_id=post_id,
        slug=slug,
        date=date,
    )


# === Контент ===

def load_content(content: str) -> dict:
    """Возвращает dict с полями: {title, vk, tg, ok, zen, image, url, hashtags}."""
    if content == "detector":
        path = TEMPLATES_DIR / "detector.json"
        if not path.exists():
            sys.exit(f"❌ Шаблон не найден: {path}")
        return json.loads(path.read_text(encoding="utf-8"))
    if content.startswith("type:"):
        # type:custom — текст из --text-file
        return {
            "title": "Анонс",
            "vk": getattr(args, "text_file", None) and Path(args.text_file).read_text(encoding="utf-8") or "",
            "tg": "",
            "ok": "",
            "zen": "",
            "image": None,
            "url": "",
            "hashtags": [],
        }
    # Путь к JSON-файлу (relative или absolute). Используется image_skill Phase 3.
    path = Path(content)
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        # v1.6: safety-net — file:// в url/image никогда не должен уйти в ВК/ТГ/ОК/Дзен.
        # image_skill в announce_text.py уже фильтрует file:// в тексте,
        # здесь — последний рубеж на случай прямого вызова post_channels.py.
        for k in ("url", "image"):
            v = data.get(k, "")
            if isinstance(v, str) and v.startswith("file:"):
                print(f"  ⚠ {k}={v!r} начинается с file:// — заменяю на пустую строку", file=sys.stderr)
                data[k] = ""
        return data
    sys.exit(f"❌ Неизвестный content: {content}")


# === Адаптер VK ===

def post_vk(text: str, image_path: str | None, url: str, dry_run: bool) -> bool:
    token = os.environ.get("VK_ACCESS_TOKEN")
    group_id = os.environ.get("VK_GROUP_ID", "237295798")
    if not token:
        print("  ⚠ VK: токен VK_ACCESS_TOKEN не задан, скип")
        return False

    api = "https://api.vk.com/method"

    def vk_call(method: str, params: dict) -> dict:
        params.update({"access_token": token, "v": "5.199"})
        url_full = f"{api}/{method}?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url_full)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    # 1. Загрузка фото (если есть)
    photo_id = None
    if image_path:
        # image_path может быть локальным путём или http(s):// URL
        local_image_path = None
        if image_path.startswith(("http://", "https://")):
            # Скачать во временный файл
            import tempfile
            try:
                suffix = ".jpg" if ".jpg" in image_path.lower() or ".jpeg" in image_path.lower() else ".png"
                tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
                dl_req = urllib.request.Request(image_path, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(dl_req, context=ctx, timeout=60) as r:
                    tmp.write(r.read())
                tmp.close()
                local_image_path = tmp.name
            except Exception as e:
                print(f"  ⚠ VK: не удалось скачать {image_path[:60]}... ({e}), пост без картинки")
                local_image_path = None
        elif Path(image_path).exists():
            local_image_path = image_path
        else:
            print(f"  ⚠ VK: image_path не найден ({image_path[:80]}), пост без картинки")

        if local_image_path:
            try:
                upload_server = vk_call("photos.getWallUploadServer", {"group_id": group_id})
                if "response" not in upload_server:
                    raise RuntimeError(f"getWallUploadServer: {upload_server}")
                upload_url = upload_server["response"]["upload_url"]

                # POST multipart/form-data с файлом на upload_url
                with open(local_image_path, "rb") as f:
                    img_bytes = f.read()
                boundary = "----WebKitFormBoundary" + os.urandom(8).hex()
                content_type = "image/jpeg" if Path(local_image_path).suffix.lower() in (".jpg", ".jpeg") else "image/png"
                body = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="photo"; filename="{Path(local_image_path).name}"\r\n'
                    f"Content-Type: {content_type}\r\n\r\n"
                ).encode("utf-8") + img_bytes + f"\r\n--{boundary}--\r\n".encode("utf-8")
                upload_req = urllib.request.Request(
                    upload_url,
                    data=body,
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                )
                with urllib.request.urlopen(upload_req, context=ctx, timeout=60) as r:
                    upload_result = json.loads(r.read().decode("utf-8"))

                # 2. saveWallPhoto: сохранить в фотоальбоме группы
                if "error" in upload_result:
                    raise RuntimeError(f"upload: {upload_result}")
                save_result = vk_call("photos.saveWallPhoto", {
                    "group_id": group_id,
                    "photo": upload_result["photo"],
                    "server": upload_result["server"],
                    "hash": upload_result["hash"],
                })
                if "error" in save_result or "response" not in save_result:
                    raise RuntimeError(f"saveWallPhoto: {save_result}")
                saved = save_result["response"][0]
                photo_id = f"photo{saved['owner_id']}_{saved['id']}"
                print(f"  ✓ VK: фото загружено (photo_id={photo_id})")
            except Exception as e:
                print(f"  ⚠ VK: ошибка загрузки фото ({e}), пост без картинки")
                photo_id = None
            finally:
                # Удалить временный файл
                if local_image_path and local_image_path != image_path:
                    try:
                        os.unlink(local_image_path)
                    except Exception:
                        pass

    # 2. Публикация
    from_id = 0  # от группы
    if dry_run:
        print(f"  [DRY-RUN] VK: {text[:80]}...")
        return True

    params = {
        "owner_id": f"-{group_id}",
        "from_group": "1",
        "message": text,
    }
    # ВК не принимает просто ссылку в attachments — нужна photo+link или ничего.
    # Ссылка уже есть в тексте, поэтому attachments не прикладываем.
    if photo_id:
        params["attachments"] = photo_id

    result = vk_call("wall.post", params)
    if "error" in result:
        print(f"  ✗ VK: {result['error'].get('error_msg', result)}")
        return False
    post_id = result.get("response", {}).get("post_id", "?")
    print(f"  ✓ VK: опубликовано (post_id={post_id})")
    return True


# === Адаптер Telegram ===

def post_tg(text: str, image_path: str | None, url: str, dry_run: bool) -> bool:
    token = os.environ.get("TG_BOT_TOKEN")
    channel = os.environ.get("TG_CHANNEL_ID")
    if not token or not channel:
        print("  ⚠ TG: токен/канал не заданы (TG_BOT_TOKEN, TG_CHANNEL_ID), скип")
        return False

    api = f"https://api.telegram.org/bot{token}"
    if dry_run:
        print(f"  [DRY-RUN] TG: {text[:80]}...")
        return True

    if image_path and Path(image_path).exists():
        # sendPhoto с подписью
        boundary = "----formdata" + os.urandom(8).hex()
        with open(image_path, "rb") as f:
            img = f.read()
        body = (
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{channel}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="caption"\r\n\r\n{text[:1024]}\r\n'
            f"--{boundary}\r\n"
            f'Content-Disposition: form-data; name="photo"; filename="image.jpg"\r\n'
            f"Content-Type: image/jpeg\r\n\r\n"
        ).encode("utf-8") + img + f"\r\n--{boundary}--\r\n".encode("utf-8")
        req = urllib.request.Request(
            f"{api}/sendPhoto",
            data=body,
            headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        )
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            result = json.loads(r.read().decode("utf-8"))
    else:
        # sendMessage с inline-кнопкой
        reply_markup = {}
        if url:
            reply_markup = {
                "inline_keyboard": [[{"text": "👉 Пройти тест", "url": url}]]
            }
        data = urllib.parse.urlencode({
            "chat_id": channel,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": "false",
            "reply_markup": json.dumps(reply_markup),
        }).encode("utf-8")
        req = urllib.request.Request(f"{api}/sendMessage", data=data)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            result = json.loads(r.read().decode("utf-8"))

    if not result.get("ok"):
        print(f"  ✗ TG: {result.get('description', result)}")
        return False
    msg_id = result.get("result", {}).get("message_id", "?")
    print(f"  ✓ TG: опубликовано (message_id={msg_id})")
    return True


def post_tg_private(text: str, image_path: str | None, url: str, dry_run: bool) -> bool:
    """
    Не публикует напрямую, а отправляет превью в личку админу (@kednet) с inline-кнопками.
    Бот-модератор @WLPostingbot примет решение: ✅ Одобрить / ✏️ Редактировать / ❌ Отклонить.

    Требует:
      TG_BOT_TOKEN
      TG_CHANNEL_PRIVATE_ID  (id приватного канала)
      TG_ADMIN_CHAT_ID       (id админа для отправки превью)
    """
    token = os.environ.get("TG_BOT_TOKEN")
    admin_chat = os.environ.get("TG_ADMIN_CHAT_ID")
    if not token or not admin_chat:
        print("  ⚠ TG-private: токен/TG_ADMIN_CHAT_ID не заданы, скип")
        return False

    api = f"https://api.telegram.org/bot{token}"

    # Dry-run: показать, что ушло бы
    if dry_run:
        print(f"  [DRY-RUN] TG-private: превью {admin_chat} ← {text[:60]}...")
        return True

    # 1. Сохранить pending-пост
    source_title = ""
    # Попробуем достать заголовок из текста (первая непустая строка без разметки)
    for line in text.splitlines():
        s = re.sub(r"<[^>]+>", "", line).strip()
        if s:
            source_title = s[:100]
            break
    pending = pending_store.create(
        text=text,
        image_path=image_path if image_path and Path(image_path).exists() else None,
        url=url,
        source_title=source_title or "Пост",
    )

    # 2. Inline-кнопки модерации
    keyboard = {
        "inline_keyboard": [
            [
                {"text": "✅ Одобрить",  "callback_data": f"moderate:approve:{pending['id']}"},
                {"text": "✏️ Править",  "callback_data": f"moderate:edit:{pending['id']}"},
            ],
            [
                {"text": "❌ Отклонить", "callback_data": f"moderate:reject:{pending['id']}"},
            ],
        ]
    }

    # 3. Заголовок превью
    preview_header = (
        f"📋 <b>ПРЕВЬЮ ДЛЯ ЧАСТНОГО КАНАЛА</b>\n"
        f"<i>post_id: {pending['id']}</i>\n"
        f"{'━' * 30}\n\n"
    )

    # 4. Отправить превью (с картинкой или без)
    try:
        if pending["image_path"]:
            boundary = "----moderator" + os.urandom(8).hex()
            with open(pending["image_path"], "rb") as f:
                img = f.read()
            caption = (preview_header + text)[:1024]
            body = (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="chat_id"\r\n\r\n{admin_chat}\r\n'
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="caption"\r\n\r\n{caption}\r\n'
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="parse_mode"\r\n\r\nHTML\r\n'
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="reply_markup"\r\n\r\n{json.dumps(keyboard)}\r\n'
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="photo"; filename="image.jpg"\r\n'
                f"Content-Type: image/jpeg\r\n\r\n"
            ).encode("utf-8") + img + f"\r\n--{boundary}--\r\n".encode("utf-8")
            req = urllib.request.Request(
                f"{api}/sendPhoto",
                data=body,
                headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
            )
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                result = json.loads(r.read().decode("utf-8"))
        else:
            body_text = (preview_header + text)[:4096]
            data = urllib.parse.urlencode({
                "chat_id": admin_chat,
                "text": body_text,
                "parse_mode": "HTML",
                "reply_markup": json.dumps(keyboard),
                "disable_web_page_preview": "false",
            }).encode("utf-8")
            req = urllib.request.Request(f"{api}/sendMessage", data=data)
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                result = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # Telegram может вернуть 403 «bot was blocked by the user» или 400 «chat not found»
        body = e.read().decode("utf-8", errors="replace")
        print(f"  ✗ TG-private: HTTP {e.code} {e.reason}")
        print(f"    Ответ: {body[:300]}")
        if e.code == 403 and "blocked" in body.lower():
            print(f"    ⚠ Админ (chat_id={admin_chat}) ЗАБЛОКИРОВАЛ @WLPostingbot.")
            print(f"    Разблокируй: открой @WLPostingbot → нажми аватарку → «Разблокировать»")
        pending_store.delete(pending["id"])
        return False
    except urllib.error.URLError as e:
        print(f"  ✗ TG-private: сетевая ошибка: {e.reason}")
        pending_store.delete(pending["id"])
        return False

    if not result.get("ok"):
        print(f"  ✗ TG-private: не удалось отправить превью: {result.get('description', result)}")
        pending_store.delete(pending["id"])
        return False

    # 5. Сохранить ID сообщения бота в личке (для редактирования/удаления позже)
    msg_id = result.get("result", {}).get("message_id", "?")
    pending_store.update(pending["id"], moderated_message_id=msg_id)
    print(f"  ✓ TG-private: превью отправлено в личку (msg_id={msg_id}, post_id={pending['id']})")
    print(f"    Ждём модерации: ✅ Одобрить / ✏️ Править / ❌ Отклонить")
    return True


# === Адаптер OK ===

def post_ok(text: str, image_path: str | None, url: str, dry_run: bool) -> bool:
    token = os.environ.get("OK_ACCESS_TOKEN")
    group_id = os.environ.get("OK_GROUP_ID")
    if not token or not group_id:
        print("  ⚠ OK: токен/группа не заданы (OK_ACCESS_TOKEN, OK_GROUP_ID), скип")
        return False

    if dry_run:
        print(f"  [DRY-RUN] OK: {text[:80]}...")
        return True

    # OK API: apiok.ru
    # 1) Загрузить фото через photosV2.getUploadUrl → upload → commit
    # 2) Привязать к посту через mediatopic.post
    # Документация: https://apiok.ru/wiki/display/api/mediatopic.post
    # Реализация пока упрощённая — только текст с ссылкой
    params = {
        "application_key": os.environ.get("OK_APPLICATION_KEY", ""),
        "format": "json",
        "gid": group_id,
        "type": "GROUP_THEME",
        "text": text,
        "link": "",
        "attachment": json.dumps({"media": [{"type": "link", "url": url}]}) if url else "",
    }
    if image_path and Path(image_path).exists():
        # TODO: photosV2 — out of scope MVP
        print("  ⚠ OK: фото пока не загружается, пост с текстом+ссылкой")

    sig_params = sorted(params.keys())
    sig_str = "".join(f"{k}={params[k]}" for k in sig_params)
    import hmac, hashlib
    secret = os.environ.get("OK_APPLICATION_SECRET", "")
    sig = hmac.new(secret.encode("utf-8"), sig_str.encode("utf-8"), hashlib.md5).hexdigest()
    params["sig"] = sig
    params["access_token"] = token

    query = urllib.parse.urlencode(params)
    req = urllib.request.Request(
        f"https://api.ok.ru/fb.do?{query}",
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
            result = json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        result = {"error": e.read().decode("utf-8", errors="ignore")}

    if "error" in result or result.get("type") == "ERROR":
        print(f"  ✗ OK: {result.get('error_msg') or result.get('error', result)}")
        return False
    print(f"  ✓ OK: опубликовано (id={result.get('id', '?')})")
    return True


# === Адаптер Дзен (RSS) ===

#: Сколько последних материалов хранить в RSS-ленте Дзена.
ZEN_RSS_HISTORY_SIZE = 10


def _strip_html(text: str) -> str:
    """Удалить простые HTML-теги, оставить переносы строк."""
    text = re.sub(r"<br\s*/?>|</p>|</div>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = re.sub(r"&nbsp;", " ", text)
    text = re.sub(r"&(amp|lt|gt|quot|#\d+);", lambda m: {"amp": "&", "lt": "<", "gt": ">", "quot": '"'}.get(m.group(1), m.group(0)), text)
    return text.strip()


def _text_to_html(text: str) -> str:
    """Обернуть абзацы текста в <p>, ссылки в <a>."""
    lines = [_strip_html(line) for line in text.splitlines()]
    paragraphs = [line for line in lines if line]
    html_parts = []
    for p in paragraphs:
        p = re.sub(
            r'(https?://[^\s<]+)',
            r'<a href="\1">\1</a>',
            p,
        )
        html_parts.append(f"<p>{p}</p>")
    return "\n".join(html_parts)


def _local_to_public_url(path_or_url: str | None) -> str | None:
    """Превратить локальный путь к public-файлу сайта в абсолютный URL."""
    if not path_or_url:
        return None
    if path_or_url.startswith(("http://", "https://")):
        return path_or_url
    try:
        local = Path(path_or_url).resolve()
        site_root = LAB_SITE_ROOT / "public"
        if local.exists() and site_root in [local, *local.parents]:
            relative = local.relative_to(site_root).as_posix()
            return f"https://app.pulab.ru/{relative}"
    except Exception:
        pass
    return path_or_url


def _file_size_bytes(path_or_url: str) -> int | None:
    if not path_or_url:
        return None
    try:
        if path_or_url.startswith(("http://", "https://")):
            req = urllib.request.Request(path_or_url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, context=ctx, timeout=30) as r:
                return int(r.headers.get("Content-Length", 0)) or None
        else:
            p = Path(path_or_url)
            if p.exists():
                return p.stat().st_size
    except Exception:
        return None


def _image_mime_type(path_or_url: str | None) -> str:
    if not path_or_url:
        return "image/jpeg"
    ext = Path(path_or_url).suffix.lower()
    if ext in (".png",):
        return "image/png"
    if ext in (".webp",):
        return "image/webp"
    return "image/jpeg"


def _stable_guid(title: str, link: str) -> str:
    """Постоянный guid для статьи. Дзен использует его как идентификатор."""
    h = hashlib.sha1(f"{link}::{title}".encode("utf-8")).hexdigest()[:16]
    return f"{link.rstrip('/')}/?guid={h}"


def _parse_existing_items(rss_path: Path) -> list[dict]:
    """Прочитать уже существующие <item> из RSS, чтобы не потерять историю."""
    if not rss_path.exists():
        return []
    try:
        tree = ET.parse(rss_path)
        root = tree.getroot()
    except Exception:
        return []

    items = []
    for item in root.findall(".//item"):
        title_el = item.find("title")
        link_el = item.find("link")
        desc_el = item.find("description")
        pub_el = item.find("pubDate")
        guid_el = item.find("guid")
        # content:encoded — ищем по tag без namespace prefix, ElementTree даёт {uri}encoded
        content_el = None
        for child in item:
            if child.tag.endswith("encoded"):
                content_el = child
                break
        enclosure_el = item.find("enclosure")

        title = (title_el.text or "").strip() if title_el is not None else ""
        link = (link_el.text or "").strip() if link_el is not None else ""
        description = (desc_el.text or "").strip() if desc_el is not None else ""
        pub_date = (pub_el.text or "").strip() if pub_el is not None else ""
        guid = (guid_el.text or "").strip() if guid_el is not None else ""
        content_encoded = (content_el.text or "").strip() if content_el is not None else ""
        image_url = enclosure_el.get("url") if enclosure_el is not None else None

        if title and link:
            items.append({
                "title": title,
                "link": link,
                "description": description,
                "pub_date": pub_date,
                "guid": guid,
                "content_encoded": content_encoded,
                "image_url": image_url,
            })
    return items


def _render_item_xml(item: dict) -> str:
    """Отрисовать один <item> вручную, чтобы CDATA и namespace остались корректными."""
    lines = [
        "    <item>",
        f"      <title>{escape(item['title'])}</title>",
        f"      <link>{escape(item['link'])}</link>",
        f"      <description>{escape(item['description'])}</description>",
        f"      <pubDate>{escape(item['pub_date'])}</pubDate>",
        f"      <guid isPermaLink=\"false\">{escape(item['guid'])}</guid>",
    ]
    if item.get("content_encoded"):
        lines.append("      <content:encoded><![CDATA[")
        lines.append(item["content_encoded"])
        lines.append("      ]]></content:encoded>")
    if item.get("image_url"):
        mime = _image_mime_type(item["image_url"])
        size = _file_size_bytes(item["image_url"])
        length_attr = f' length="{size}"' if size else ""
        lines.append(
            f'      <enclosure url="{escape(item["image_url"])}" type="{mime}"{length_attr} />'
        )
        lines.append(f'      <media:thumbnail url="{escape(item["image_url"])}" />')
    lines.append("    </item>")
    return "\n".join(lines)


def post_zen(content: dict, dry_run: bool) -> bool:
    """Дзен не имеет открытого API — только RSS. Генерирует/обновляет RSS-фид lab_site/detector/feed.xml.

    Поведение:
      - добавляет новый <item> в начало ленты
      - сохраняет последние ZEN_RSS_HISTORY_SIZE записей
      - guid стабильный (на основе title+link) — не пересоздаёт дубли
      - включает <enclosure> для картинки и <content:encoded> для Дзен
      - лента доступна после деплоя по https://app.pulab.ru/detector/feed.xml
    """
    rss_path = LAB_SITE_ROOT / "public" / "detector" / "feed.xml"
    rss_path.parent.mkdir(parents=True, exist_ok=True)

    title = content.get("zen_title") or content.get("title", "Детектор желаний")
    description = _strip_html(content.get("zen", content.get("vk", "")))
    link = content.get("url", "https://app.pulab.ru/detector/").rstrip("/") + "/"
    pub_date = datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    image_path = content.get("image_local") or content.get("image")
    image_url = _local_to_public_url(image_path) or "https://app.pulab.ru/cover.jpg"

    content_html = _text_to_html(content.get("zen", content.get("vk", "")))
    # CDATA внутри: HTML-контент без экранирования
    content_encoded_body = content_html

    new_guid = _stable_guid(title, link)

    existing = _parse_existing_items(rss_path)
    # Удалить старую версию этой же статьи (по guid или title+link)
    existing = [
        it for it in existing
        if it.get("guid") != new_guid
        and not (it.get("title") == title and it.get("link") == link)
    ]

    new_item = {
        "title": title,
        "link": link,
        "description": description,
        "pub_date": pub_date,
        "guid": new_guid,
        "content_encoded": content_encoded_body,
        "image_url": image_url,
    }
    items = [new_item, *existing][:ZEN_RSS_HISTORY_SIZE]

    item_xml_blocks = "\n".join(_render_item_xml(it) for it in items)

    rss_xml = (
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<rss version="2.0" '
        'xmlns:content="http://purl.org/rss/1.0/modules/content/" '
        'xmlns:media="http://search.yahoo.com/mrss/">\n'
        "  <channel>\n"
        "    <title>ЛАБОРАТОРИЯ ЖЕЛАНИЙ — Детектор</title>\n"
        "    <link>https://app.pulab.ru/detector/</link>\n"
        "    <description>Бесплатный тест: твоё желание про «надо» или про «хочу»?</description>\n"
        "    <language>ru-RU</language>\n"
        f"    <lastBuildDate>{escape(pub_date)}</lastBuildDate>\n"
        "    <image>\n"
        "      <url>https://app.pulab.ru/cover.jpg</url>\n"
        "      <title>ЛАБОРАТОРИЯ ЖЕЛАНИЙ — Детектор</title>\n"
        "      <link>https://app.pulab.ru/detector/</link>\n"
        "    </image>\n"
        f"{item_xml_blocks}\n"
        "  </channel>\n"
        "</rss>\n"
    )

    rss_path.write_text(rss_xml, encoding="utf-8")

    if dry_run:
        print(f"  [DRY-RUN] ZEN: RSS-фид обновлён → {rss_path}")
    else:
        print(f"  ✓ ZEN: RSS-фид обновлён → {rss_path}")
    print(f"    Добавь в Дзен Studio → Каналы → Внешний RSS → https://app.pulab.ru/detector/feed.xml")
    return True


# === Main ===

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--content", required=True, help="Имя контента (detector, type:free) или путь к JSON")
    p.add_argument("--channels", default="vk,tg,ok,zen", help="Каналы через запятую: vk,tg,ok,zen,private")
    p.add_argument("--dry-run", action="store_true", help="Показать превью, не публиковать")
    p.add_argument("--text-file", help="Файл с текстом (для type:free)")
    args = p.parse_args()

    content = load_content(args.content)
    channels = [c.strip() for c in args.channels.split(",") if c.strip()]

    print(f"📤 Публикация: {content.get('title', args.content)}")
    print(f"   Каналы: {', '.join(channels)}")
    print(f"   Режим: {'DRY-RUN' if args.dry_run else 'LIVE'}")
    print()

    if "vk" in channels:
        print("→ VK:")
        # v1.4: приоритет image_local (уже скачан image_skill), затем image (URL)
        vk_image = content.get("image_local") or content.get("image")
        post_vk(content.get("vk", ""), vk_image, content.get("url", ""), args.dry_run)
    if "tg" in channels:
        print("→ TG:")
        tg_image = content.get("image_local") or content.get("image")
        post_tg(content.get("tg", ""), tg_image, content.get("url", ""), args.dry_run)
    if "private" in channels:
        print("→ TG-PRIVATE (модерация):")
        pr_image = content.get("image_local") or content.get("image")
        post_tg_private(content.get("tg", ""), pr_image, content.get("url", ""), args.dry_run)
    if "ok" in channels:
        print("→ OK:")
        ok_image = content.get("image_local") or content.get("image")
        post_ok(content.get("ok", ""), ok_image, content.get("url", ""), args.dry_run)
    if "zen" in channels:
        print("→ ZEN:")
        post_zen(content, args.dry_run)
        print("   Не забудь: если feed.xml изменился — npm run build в lab_site и деплой на VPS.")

    # Лог
    log_path = TMP_DIR / f"post-{datetime.now().strftime('%Y%m%d-%H%M%S')}.json"
    log_path.write_text(
        json.dumps(
            {
                "content": args.content,
                "channels": channels,
                "dry_run": args.dry_run,
                "ts": datetime.now().isoformat(),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n📝 Лог: {log_path}")


if __name__ == "__main__":
    main()
