"""
cmd_publish.py — Phase 3 pipeline: R2 upload + post_channels.py (Phase 3).

Использование:
    python scripts/image.py publish lab/5-oshibok-karty-zhelanii --profile=lab
    python scripts/image.py publish lab/... --channels vk,tg
    python scripts/image.py publish lab/... --dry-run
    python scripts/image.py publish lab/... --force

Pipeline:
1. Загрузить state, проверить status in (upscaled, published)
2. Загрузить upscaled JPEG в R2 (или fallback на file://)
3. Сгенерировать JSON-контент (через YandexGPT или fallback)
4. Вызвать publisher_skill/scripts/post_channels.py --content <json> --channels vk,tg,ok,zen
5. Update state → status=published, published_url, published_at, channels_posted

State transition: upscaled → published.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from _image_common import SKILL_ROOT, get_env, now_iso  # noqa: E402
from build_post_content import build_post_json  # noqa: E402
from state import load as load_state, update as update_state  # noqa: E402
from upload_storage import upload_to_storage  # noqa: E402

PUBLISHER_SKILL_ROOT = Path("C:/Users/kfigh/publisher_skill")
POST_CHANNELS_SCRIPT = PUBLISHER_SKILL_ROOT / "scripts" / "post_channels.py"


def _resolve_publisher_skill() -> Path:
    """Найти post_channels.py. Если нет — ошибка."""
    if not POST_CHANNELS_SCRIPT.exists():
        raise FileNotFoundError(
            f"publisher_skill не найден: {POST_CHANNELS_SCRIPT}\n"
            "Phase 3 требует publisher_skill. Клонируй в C:/Users/kfigh/publisher_skill/"
        )
    return POST_CHANNELS_SCRIPT


def _load_book_tags(book_slug: str) -> list[str]:
    """v1.8: подтянуть tags из lab_site/src/data/books.json для расширения хэштегов.

    Если книга найдена → вернуть tags как список hashtag'ов с '#'.
    Иначе → [].
    """
    if not book_slug:
        return []
    books_json = Path("C:/Users/kfigh/lab_site/src/data/books.json")
    if not books_json.exists():
        return []
    try:
        import json as _json
        data = _json.loads(books_json.read_text(encoding="utf-8"))
        for b in data.get("books", []):
            if b.get("slug") == book_slug:
                raw_tags = b.get("tags") or []
                return [f"#{t}" if not t.startswith("#") else t for t in raw_tags]
    except Exception as e:
        print(f"  ⚠ _load_book_tags: {e}", file=sys.stderr)
    return []


def run(args) -> int:
    """CLI: image.py publish <slug_id> --profile=lab [--channels vk,tg] [--dry-run] [--force]"""
    slug_id = args.slug_id
    profile_name = args.profile

    # 1. State check
    state = load_state(slug_id)
    status = state.get("status")
    if status not in ("upscaled", "published"):
        print(f"❌ status={status!r}, нужен upscaled. Сначала: image.py auto")
        return 1

    if status == "published" and not args.force:
        print(f"⏭ Уже published. --force для повтора")
        return 0

    # 2. R2 upload
    upscaled_rel = state.get("upscaled_path")
    if not upscaled_rel:
        print(f"❌ state.upscaled_path пустой")
        return 1
    upscaled_abs = (SKILL_ROOT / upscaled_rel).resolve()
    if not upscaled_abs.exists():
        print(f"❌ Файл не найден: {upscaled_abs}")
        return 1

    r2_key = f"images/{profile_name}/{upscaled_abs.name}"
    print(f"🔧 Phase 3: storage upload {upscaled_abs.name} → {r2_key}")
    provider = getattr(args, "storage", "") or ""
    image_url = upload_to_storage(upscaled_abs, r2_key, provider=provider)

    # 3. Live URL (v1.6: сначала --live-url, потом profile.site_url, иначе FAIL)
    # Раньше фоллбэк шёл на image_url (URL картинки) — это приводило к мусору в ВК
    # (например, для контента «карта желаний» live_url становился file:///C:/...).
    cli_live_url = getattr(args, "live_url", "") or ""
    profile_live_url = ""
    try:
        from cmd_profile import load_profile
        prof = load_profile(profile_name)
        profile_live_url = prof.get("site_url", "") or ""
    except Exception:
        pass

    if cli_live_url:
        live_url = cli_live_url
        live_url_src = "--live-url"
    elif profile_live_url:
        live_url = profile_live_url
        live_url_src = f"profile.site_url"
        print(f"  ℹ live_url из профиля: {live_url}")
    else:
        print(f"❌ live_url пуст и в профиле не задан site_url.")
        print(f"   Передай --live-url=https://... или добавь site_url в data/profiles/{profile_name}.yaml")
        print(f"   Без ссылки на сайт пост в ВК/ОК/Дзен бесполезен — читатель не перейдёт.")
        return 2

    # v1.6: защита от file:///
    if live_url.startswith("file:") or not live_url.startswith(("http://", "https://")):
        print(f"❌ live_url={live_url!r} невалидный (file:// или пустой протокол).")
        print(f"   Передай --live-url=https://...")
        return 2
    if live_url == image_url:
        print(f"⚠ live_url совпадает с image_url ({live_url}) — это URL картинки, не страницы.")
        print(f"   Пост уйдёт со ссылкой на картинку. Если так и задумано — игнор.")
        print(f"   Иначе передай --live-url=https://... на страницу сайта.")

    # 4. JSON-контент для post_channels.py
    print(f"🔧 Phase 3: генерация 4 адаптаций поста (vk/tg/ok/zen)")
    # v1.8: --book-slug → подтянуть tags книги в хэштеги
    book_tags = _load_book_tags(getattr(args, "book_slug", "") or "")
    if book_tags:
        print(f"  ℹ Теги книги: {book_tags}")
    content_json = build_post_json(slug_id, profile_name, image_url, live_url,
                                   book_type=getattr(args, "book_type", "") or "",
                                   book_tags=book_tags)

    # 5. Вызов post_channels.py
    channels = [c.strip() for c in args.channels.split(",") if c.strip()]
    if not channels:
        print(f"❌ --channels пустой. Укажи хотя бы один: vk,tg,ok,zen")
        return 1

    post_script = _resolve_publisher_skill()
    cmd = [
        sys.executable,
        str(post_script),
        "--content", str(content_json),
        "--channels", ",".join(channels),
    ]
    if args.dry_run:
        cmd.append("--dry-run")

    print(f"🔧 Phase 3: post_channels.py --content {content_json.name} --channels {','.join(channels)}"
          + (" [DRY-RUN]" if args.dry_run else " [LIVE]"))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",       # post_channels.py может печатать RU текст
            errors="replace",        # Windows cp1252 не выдержит — заменяем на ?
            timeout=180,
        )
    except subprocess.TimeoutExpired:
        print(f"❌ post_channels.py timeout (180 сек)", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ post_channels.py failed: {e}", file=sys.stderr)
        return 1

    # Печатаем stdout (для логов), и stderr
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)

    if result.returncode != 0:
        print(f"❌ post_channels.py exit code={result.returncode}")
        # Не обновляем state — failure
        return result.returncode

    # 6. Update state → status=published
    rel_content = str(content_json.relative_to(SKILL_ROOT))
    update_state(
        slug_id,
        status="published",
        published_url=image_url,
        published_at=now_iso(),
        channels_requested=channels,
        channels_posted=channels,  # post_channels.py сам решил что скипнуть; для idempotency считаем все requested
        post_content_json=rel_content,
        dry_run=bool(args.dry_run),
    )

    print(f"\n✅ Phase 3 done!")
    print(f"   📁 {upscaled_abs}")
    print(f"   🌐 {image_url}")
    print(f"   📤 Каналы: {', '.join(channels)}")
    print(f"   📋 state: {slug_id} → status=published")
    return 0


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Phase 3 publish: storage upload + post_channels.py")
    p.add_argument("slug_id", help="profile/slug или просто slug")
    p.add_argument("--profile", default="lab")
    p.add_argument("--channels", default="vk", help="vk,tg,ok,zen через запятую")
    p.add_argument("--live-url", default="", help="URL статьи/страницы (если есть)")
    p.add_argument("--book-type", default="", help="Тип книги: nonfiction | fiction-reflective (для спец. тона поста)")
    p.add_argument("--book-slug", default="", help="v1.8: slug книги (напр. alhimik-koeluo) — подтянет tags в хэштеги")
    p.add_argument("--storage", default="", help="Storage provider: auto|r2|yandex (default: STORAGE_PROVIDER env или auto)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--force", action="store_true")
    args = p.parse_args()
    sys.exit(run(args))
