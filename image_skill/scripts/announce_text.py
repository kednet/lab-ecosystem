"""
announce_text.py — генерация 4 адаптаций поста через YandexGPT (Phase 3, hardened v1.3).

Используется в `cmd_publish.py` для генерации текстов под VK/TG/OK/Zen.

Стратегия (v1.3):
1. LLM-вызов с жёстким промптом (длина/формат/тон для каждого канала)
2. JSON-парсинг с 3 fallback-уровнями (json.loads → regex {...} → None)
3. Per-channel валидация: длина, теги, кодировка
4. Если LLM ответил невалидно — повторный вызов с упрощённым промптом (max 1 retry)
5. Если всё упало — per-channel fallback шаблон на title + hashtags

Per-channel требования (v1.3):
- VK:  100-1000 chars, RU, 2-5 строк, эмодзи уместны, hashtags в конце
- TG:  100-1024 chars, HTML (<b>, <i>, <a>), короткий, CTA-кнопка
- OK:  100-1000 chars, RU, нейтральный, без овер-эмодзи
- Zen: 300-3000 chars, без hashtag (Дзен их не любит), SEO-friendly
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Optional


PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"

# === Per-channel constraints (v1.3) ===
VK_MIN, VK_MAX = 100, 1000
TG_MIN, TG_MAX = 100, 1024
OK_MIN, OK_MAX = 100, 1000
ZEN_MIN, ZEN_MAX = 300, 3000


def _hashtags_str(hashtags: list[str]) -> str:
    """['#a', '#b'] → '#a #b'. Фильтрует пустые/не-строковые."""
    if not hashtags:
        return ""
    safe = [str(h).strip() for h in hashtags if h and str(h).strip()]
    return " ".join(safe)


def _strip_code_fence(text: str) -> str:
    """Убрать ```json ... ``` обёртку если есть."""
    text = text.strip()
    if text.startswith("```"):
        m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
        if m:
            return m.group(1)
    return text


def _parse_json_safely(raw: str) -> Optional[dict]:
    """Парсит JSON из ответа LLM. 3 fallback уровня: full, regex, ничего."""
    raw = _strip_code_fence(raw)
    if not raw:
        return None
    # 1) Весь текст
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    # 2) Greedy regex первого {...} (DOTALL)
    m = re.search(r"\{.*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    # 3) Non-greedy
    m = re.search(r"\{[^{}]*\}", raw, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass
    return None


def _validate_text(text: str, channel: str) -> bool:
    """Per-channel валидация длины и базового формата."""
    if not isinstance(text, str):
        return False
    t = text.strip()
    if not t:
        return False
    if channel == "vk":
        ok = VK_MIN <= len(t) <= VK_MAX
    elif channel == "tg":
        # TG: 100-1024 + должен содержать <b>/<i> или просто текст
        ok = TG_MIN <= len(t) <= TG_MAX
    elif channel == "ok":
        ok = OK_MIN <= len(t) <= OK_MAX
    elif channel == "zen":
        # Zen: 300-3000, БЕЗ '#' (хэштеги Дзен не любит)
        ok = ZEN_MIN <= len(t) <= ZEN_MAX and "#" not in t
    else:
        ok = False
    return ok


def _has_link(text: str, live_url: str) -> bool:
    """Проверяет, что в тексте есть ссылка на сайт (live_url или его хост).

    Учитывает:
    - прямую вставку URL (https://app.pulab.ru/...)
    - HTML-обёртку в TG (<a href="...">...</a>)
    - канонический хост без www
    - file:// НЕ считается валидной ссылкой (v1.6: защита от мусора в ВК)
    """
    if not text or not live_url:
        return False
    # v1.6: file:/// и пустые протоколы — НЕ валидная ссылка
    if not live_url.startswith(("http://", "https://")):
        return False
    t = text.lower()
    url = live_url.lower().rstrip("/")
    if url in t:
        return True
    # Хост без протокола и слэша
    host = re.sub(r"^https?://(www\.)?", "", url).rstrip("/")
    if host and host in t:
        return True
    return False


def _ensure_link(text: str, channel: str, live_url: str) -> str:
    """Если в тексте нет ссылки на live_url — добавить каноническую строку перед хэштегами/в конец.

    Per-channel формат:
    - VK/OK: `👉 {live_url}` в конец (перед хэштегами — но они обычно тоже в конце,
      потому что пост короткий, добавим просто в самый конец)
    - TG: `<a href="{live_url}">👉 Подробнее</a>` в конец
    - Zen: `Подробнее: {live_url}` в конец

    v1.6: file:/// и невалидные URL не добавляются (защита от мусора в ВК).
    """
    # v1.6: защита от file:/// и пустого протокола
    if not live_url or not live_url.startswith(("http://", "https://")):
        return text
    if _has_link(text, live_url):
        return text
    t = text.rstrip()
    if channel == "tg":
        addition = f'<a href="{live_url}">👉 Подробнее</a>'
    elif channel == "zen":
        addition = f"Подробнее: {live_url}"
    else:  # vk, ok
        addition = f"👉 {live_url}"
    # Разделитель: пустая строка перед ссылкой, если в тексте есть переносы
    sep = "\n\n" if "\n" in t else "\n"
    return t + sep + addition


def _fix_length(text: str, channel: str) -> str:
    """Обрезать до max, добавить многоточие если обрезали."""
    if not isinstance(text, str):
        return ""
    t = text.strip()
    if channel == "vk":
        if len(t) > VK_MAX:
            t = t[: VK_MAX - 1].rstrip() + "…"
    elif channel == "tg":
        if len(t) > TG_MAX:
            t = t[: TG_MAX - 1].rstrip() + "…"
    elif channel == "ok":
        if len(t) > OK_MAX:
            t = t[: OK_MAX - 1].rstrip() + "…"
    elif channel == "zen":
        if len(t) > ZEN_MAX:
            t = t[: ZEN_MAX - 1].rstrip() + "…"
        # Zen: убрать '#' если прокрались
        t = re.sub(r"#[А-Яа-яA-Za-z0-9_]+", "", t).strip()
    return t


def _fallback_announce(state: dict, profile: dict, image_url: str = "", live_url: str = "") -> dict:
    """Per-channel ручной шаблон когда LLM не сработал. v1.3: top-level hashtags + per-channel тон. v1.8: per-book."""
    title = state.get("title", "Анонс")
    # FIX v1.3: hashtags_base на верхнем уровне профиля (не в branding)
    base_ht = profile.get("hashtags_base", profile.get("branding", {}).get("hashtags_base", []))
    book_ht = state.get("book_tags") or []
    seen = set()
    hashtags = []
    for h in base_ht + book_ht:
        h_norm = h.lower().strip()
        if h_norm and h_norm not in seen:
            hashtags.append(h)
            seen.add(h_norm)
    ht = _hashtags_str(hashtags)
    display_name = profile.get("display_name", "Лаборатория желаний")
    has_url = bool(live_url or image_url)
    url = live_url or image_url or ""
    url_block = f"\n\n👉 {url}" if url else ""

    return {
        "vk": (
            f"{title}\n\n"
            f"Узнаёте себя? Напишите в комментариях 🙌\n\n"
            f"{ht}"
        ).strip(),
        "tg": (
            f"<b>{title}</b>\n\n"
            f"Узнаёте себя? Напишите в комментариях 🙌"
            f"{url_block}"
        ).strip(),
        "ok": (
            f"{title}\n\n"
            f"Узнаёте себя? Напишите в комментариях.\n\n"
            f"{ht}"
        ).strip(),
        "zen": (
            f"{title}\n\n"
            f"Эта картинка из сообщества «{display_name}». "
            f"Здесь мы разбираем книги о желаниях, делаем практики "
            f"и учимся отличать «надо» от «хочу».\n\n"
            f"Подробнее: {url}" if url else
            f"{title}\n\n"
            f"Эта картинка из сообщества «{display_name}». "
            f"Здесь мы разбираем книги о желаниях, делаем практики "
            f"и учимся отличать «надо» от «хочу»."
        ).strip(),
    }


def _coerce_announce(parsed: dict, state: dict, profile: dict, image_url: str, live_url: str) -> dict:
    """Принять dict от LLM, валидировать и дочинить до контракта. v1.3: per-channel.
    v1.5: гарантируем ссылку на сайт для каждого канала, даже если LLM её не добавил.
    """
    out = {}
    for ch in ("vk", "tg", "ok", "zen"):
        raw = parsed.get(ch, "")
        if _validate_text(raw, ch):
            text = raw.strip()
        else:
            # Достаём из fallback и мерджим
            fb = _fallback_announce(state, profile, image_url, live_url)
            text = _fix_length(fb.get(ch, ""), ch)
        # v1.5: гарантируем ссылку на сайт
        out[ch] = _ensure_link(text, ch, live_url)
    return out


def generate_announce(
    state: dict,
    profile: dict,
    format_meta: dict,
    image_url: str = "",
    live_url: str = "",
) -> dict:
    """
    Сгенерировать 4 адаптации поста (vk/tg/ok/zen) с retry и per-channel валидацией (v1.3).

    Returns:
        dict с ключами vk, tg, ok, zen. Гарантированно валидный по длинам.
    """
    title = state.get("title", "Анонс")
    fmt_label = format_meta.get("label", "Картинка")
    display_name = profile.get("display_name", "Лаборатория желаний")

    style = state.get("style", "watercolor")
    mood = state.get("mood", "soft")
    style_hint = profile.get("prompt_styles", {}).get(style, "")
    mood_hint = profile.get("prompt_moods", {}).get(mood, "")
    palette = profile.get("branding", {}).get("palette", {})
    accent = profile.get("branding", {}).get("accent_color", "")
    # FIX v1.3: top-level hashtags + v1.8: per-book tags
    base_ht = profile.get("hashtags_base", profile.get("branding", {}).get("hashtags_base", []))
    book_ht = state.get("book_tags") or []
    seen = set()
    hashtags = []
    for h in base_ht + book_ht:
        h_norm = h.lower().strip()
        if h_norm and h_norm not in seen:
            hashtags.append(h)
            seen.add(h_norm)

    # v1.7: book_type для разных шаблонов промпта (fiction-reflective и др.)
    book_type = state.get("book_type", "nonfiction") or "nonfiction"
    book_types = profile.get("book_types", {}) or {}
    book_type_note = book_types.get(book_type, {}).get("prompt_note", "") or ""
    book_type_section = book_types.get(book_type, {}).get("prompt_section", "") or ""

    palette_str = ", ".join(f"{k}={v}" for k, v in palette.items()) if palette else "(none)"

    # === Попытка LLM (основная) ===
    parsed = _try_llm(
        title=title,
        fmt_label=fmt_label,
        aspect=format_meta.get("aspect", ""),
        display_name=display_name,
        style=style, style_hint=style_hint,
        mood=mood, mood_hint=mood_hint,
        palette=palette_str, accent=accent,
        hashtags=hashtags, image_url=image_url, live_url=live_url,
        book_type=book_type,
        book_type_note=book_type_note,
        book_type_section=book_type_section,
        strict=True,
    )
    if parsed and all(_validate_text(parsed.get(ch, ""), ch) for ch in ("vk", "tg", "ok", "zen")):
        print(f"  → LLM сгенерировал 4 валидные адаптации", file=sys.stderr)
        return _coerce_announce(parsed, state, profile, image_url, live_url)

    # === Retry (упрощённый промпт) ===
    if parsed is None:
        print(f"  ⚠ LLM JSON невалидный, retry с упрощённым промптом", file=sys.stderr)
        parsed2 = _try_llm(
            title=title,
            fmt_label=fmt_label,
            aspect=format_meta.get("aspect", ""),
            display_name=display_name,
            style=style, style_hint=style_hint,
            mood=mood, mood_hint=mood_hint,
            palette=palette_str, accent=accent,
            hashtags=hashtags, image_url=image_url, live_url=live_url,
            book_type=book_type,
            book_type_note=book_type_note,
            book_type_section=book_type_section,
            strict=False,
        )
        if parsed2 and all(_validate_text(parsed2.get(ch, ""), ch) for ch in ("vk", "tg", "ok", "zen")):
            print(f"  → LLM сгенерировал 4 адаптации со 2-й попытки", file=sys.stderr)
            return _coerce_announce(parsed2, state, profile, image_url, live_url)

    # === Fallback (per-channel шаблон) ===
    print(f"  ⚠ LLM не сработал, fallback на per-channel шаблон", file=sys.stderr)
    fb = _fallback_announce(state, profile, image_url, live_url)
    return {ch: _ensure_link(_fix_length(fb.get(ch, ""), ch), ch, live_url)
            for ch in ("vk", "tg", "ok", "zen")}


def _try_llm(
    title: str, fmt_label: str, aspect: str, display_name: str,
    style: str, style_hint: str, mood: str, mood_hint: str,
    palette: str, accent: str, hashtags: list, image_url: str, live_url: str,
    book_type: str = "nonfiction",
    book_type_note: str = "",
    book_type_section: str = "",
    strict: bool = True,
) -> Optional[dict]:
    """Один вызов LLM. strict=True — основной промпт с per-channel правилами, False — упрощённый."""
    try:
        from llm_factory import get_llm_client
        client = get_llm_client()
        template_name = "announce-text.md" if strict else "announce-text-simple.md"
        template_path = PROMPTS_DIR / template_name
        if not template_path.exists():
            # Если упрощённого нет — используем основной
            template_path = PROMPTS_DIR / "announce-text.md"
        template = template_path.read_text(encoding="utf-8")
        user_msg = template.format(
            title=title,
            format_label=fmt_label,
            aspect=aspect,
            display_name=display_name,
            style=style,
            style_hint=style_hint,
            mood=mood,
            mood_hint=mood_hint,
            palette=palette,
            accent_color=accent,
            hashtags=", ".join(hashtags) if hashtags else "",
            image_url=image_url,
            live_url=live_url,
            book_type=book_type,
            book_type_note=book_type_note,
            book_type_section=book_type_section,
            vk_min=VK_MIN, vk_max=VK_MAX,
            tg_min=TG_MIN, tg_max=TG_MAX,
            ok_min=OK_MIN, ok_max=OK_MAX,
            zen_min=ZEN_MIN, zen_max=ZEN_MAX,
        )
        system_msg = (
            "Ты — SMM-копирайтер для сообщества «Лаборатория желаний». "
            "Генерируешь 4 адаптации одного поста: VK, Telegram, OK, Дзен. "
            "Возвращай ТОЛЬКО валидный JSON без markdown-обёрток и пояснений."
        )
        llm_raw = client.generate(
            system=system_msg,
            user=user_msg,
            max_tokens=2000,
            temperature=0.7,
        ).strip()
        return _parse_json_safely(llm_raw)
    except Exception as e:
        print(f"  ⚠ LLM вызов упал ({type(e).__name__}: {e})", file=sys.stderr)
        return None


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="Генерация 4 адаптаций поста")
    p.add_argument("--slug-id", required=True)
    p.add_argument("--profile", default="lab")
    p.add_argument("--image-url", default="")
    p.add_argument("--live-url", default="")
    args = p.parse_args()

    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from _image_common import get_format
    from state import load as load_state
    from cmd_profile import load_profile

    state = load_state(args.slug_id)
    profile = load_profile(args.profile)
    fmt = get_format(state.get("format") or "vk_post")
    announce = generate_announce(state, profile, fmt, args.image_url, args.live_url)
    print(json.dumps(announce, ensure_ascii=False, indent=2))
