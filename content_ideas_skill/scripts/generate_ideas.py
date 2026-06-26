#!/usr/bin/env python3
"""
generate_ideas.py — главный оркестратор content-ideas-skill.

Генерирует идеи постов для VK/блога/Telegram на основе 4 источников:
  1. WL-книги (sources/books-from-wl.md)
  2. Coach-модули (sources/coach-modules.md)
  3. Боли ЦА (audience-mining/pain-language-bank.md)
  4. Сезонный календарь + тренды (sources/seasonal-calendar.md, trends-watchlist.md)

Фильтры:
  - profiles/lab-zhelanii-ca.md (ЦА)
  - profiles/tone-of-voice.md (тон)
  - profiles/rubrics.md (рубрикатор)
  - data/history.json (дедуп)

Выход:
  - data/ideas-bank.json (обновляется)
  - data/generated/<date>-<pack>.md (markdown-выгрузка)
  - data/history.json (обновляется после dedupe.py)

Использование:
  python generate_ideas.py --theme "навязанные желания" --count 10 --target vk
  python generate_ideas.py --source wl --count 5 --target blog
  python generate_ideas.py --source pains --count 8 --target vk --rubric "провокация"

Статус: v0.1 — CLI-скелет без LLM-вызовов. Логика генерации — в TODO.
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple  # noqa: F401

try:
    import yaml
except ImportError:
    yaml = None  # опционально — без yaml работаем на встроенных промптах

# Канонические рубрики (для нормализации LLM-вывода)
CANONICAL_RUBRICS = {
    "разбор-цитаты", "детектор", "история", "провокация",
    "практика", "миф-vs-правда", "подборка",
}


def normalize_rubric(r: str) -> str:
    """Нормализовать название рубрики к каноническому виду.

    LLM иногда пишет 'миф vs правда' вместо 'миф-vs-правда' — приводим к канону.
    """
    if not r:
        return "разбор-цитаты"
    norm = r.strip().lower().replace(" ", "-").replace("—", "-")
    # Простая защита от мусора: оставляем только [a-zа-я-]
    norm = "".join(c for c in norm if c.isalnum() or c == "-")
    if norm in CANONICAL_RUBRICS:
        return norm
    # Попробовать найти частичное совпадение
    for canon in CANONICAL_RUBRICS:
        # Если все слова канона есть в norm (без учёта дефисов)
        canon_words = canon.replace("-", "")
        norm_words = norm.replace("-", "")
        if canon_words and canon_words in norm_words:
            return canon
    return norm or "разбор-цитаты"

# Force UTF-8 output on Windows (cp1252 by default breaks Cyrillic)
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass

# Добавляем scripts/lib в sys.path для импорта llm_client
sys.path.insert(0, str(Path(__file__).parent / "lib"))

# Пути
SKILL_DIR = Path(__file__).parent.parent
DATA_DIR = SKILL_DIR / "data"
HISTORY_FILE = DATA_DIR / "history.json"
IDEAS_BANK = DATA_DIR / "ideas-bank.json"
GENERATED_DIR = DATA_DIR / "generated"
CONFIG_FILE = SKILL_DIR / "config.yaml"


def load_config() -> Dict[str, Any]:
    """Загрузить config.yaml. Если нет yaml или файла — пустой словарь."""
    if yaml is None:
        return {}
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"[warn] Не удалось прочитать config.yaml: {e}")
        return {}


def load_history() -> Dict[str, Any]:
    """Загрузить историю идей (для дедупа)."""
    if not HISTORY_FILE.exists():
        return {"version": "1.0", "ideas": []}
    return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))


def save_history(history: Dict[str, Any]) -> None:
    """Сохранить историю."""
    HISTORY_FILE.parent.mkdir(parents=True, exist_ok=True)
    HISTORY_FILE.write_text(
        json.dumps(history, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def load_ideas_bank() -> Dict[str, Any]:
    """Загрузить банк идей."""
    if not IDEAS_BANK.exists():
        return {"version": "1.0", "updated": None, "ideas": []}
    return json.loads(IDEAS_BANK.read_text(encoding="utf-8"))


def save_ideas_bank(bank: Dict[str, Any]) -> None:
    """Сохранить банк идей."""
    IDEAS_BANK.parent.mkdir(parents=True, exist_ok=True)
    bank["updated"] = datetime.now().isoformat()
    IDEAS_BANK.write_text(
        json.dumps(bank, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def make_idea_id() -> str:
    """Сгенерировать уникальный ID идеи."""
    import random
    # Используем timestamp + счётчик + случайное число для гарантии уникальности
    return f"idea-{datetime.now().strftime('%Y-%m-%d')}-{random.randint(100000, 999999)}"


def make_fingerprint(theme: str, rubric: str, hook_keywords: List[str]) -> str:
    """Хеш для дедупа."""
    import hashlib
    raw = f"{theme}|{rubric}|{'|'.join(sorted(hook_keywords))}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def is_duplicate(fingerprint: str, history: Dict[str, Any]) -> bool:
    """Проверить, есть ли уже такая идея в истории."""
    for idea in history.get("ideas", []):
        if idea.get("fingerprint") == fingerprint:
            return True
    return False


def load_profile(profile_name: str) -> str:
    """Загрузить профиль (markdown) по имени файла."""
    # Передаём короткие имена
    mapping = {
        "ca": "lab-zhelanii-ca.md",
        "ca-zhelanii": "lab-zhelanii-ca.md",
        "lab-zhelanii-ca": "lab-zhelanii-ca.md",
        "tone": "tone-of-voice.md",
        "tone-of-voice": "tone-of-voice.md",
        "rubrics": "rubrics.md",
    }
    fname = mapping.get(profile_name, profile_name)
    path = SKILL_DIR / "profiles" / fname
    if not path.exists():
        return f"[Profile not found: {path}]"
    return path.read_text(encoding="utf-8")


def load_pain_bank() -> str:
    """Загрузить pain-language-bank.md (если есть)."""
    path = SKILL_DIR / "audience-mining" / "pain-language-bank.md"
    if not path.exists():
        return "[Pain bank not yet collected]"
    return path.read_text(encoding="utf-8")


def build_prompt(
    theme: str = None,
    source: str = None,
    target: str = "vk",
    count: int = 5,
    rubric: str = None,
    audience_profile: str = "",
    tone_guide: str = "",
    rubrics_guide: str = "",
    pain_bank: str = "",
    config: Optional[Dict[str, Any]] = None,
) -> Tuple[str, str]:
    """Собрать system + user промпт для LLM.

    Если в config.yaml есть prompts.system / prompts.user — используем их
    (с подстановкой плейсхолдеров). Иначе — встроенный фолбэк.
    """
    config = config or {}
    llm_cfg = config.get("llm", {}) or {}
    prompts_cfg = llm_cfg.get("prompts", {}) or {}
    # target_mapping может лежать либо под llm., либо на верхнем уровне
    target_map = llm_cfg.get("target_mapping") or config.get("target_mapping") or {}

    # === target_label и length_hint из target_mapping (или фолбэк) ===
    tgt = target_map.get(target) or {}
    target_label = tgt.get("label") or {
        "vk": "сообщества ВКонтакте",
        "blog": "блога на сайте",
        "telegram": "Telegram-канала",
    }.get(target, "соцсетей")
    length_hint = tgt.get("length") or {
        "vk": "800-1500 знаков",
        "blog": "2500-4000 знаков",
        "telegram": "400-800 знаков",
    }.get(target, "800-1500 знаков")

    # === source / rubric placeholder ===
    rubric_value = rubric or "любая из списка рубрик (минимум 3 разных)"
    pains_section = ""
    if pain_bank and "not yet collected" not in pain_bank and "Заглушка" not in pain_bank:
        pains_section = f"**БОЛИ ЦА (реальные формулировки из комментов — используй как язык, а не копируй):**\n{pain_bank[:1500]}"

    # === System промпт ===
    if prompts_cfg.get("system"):
        try:
            system = prompts_cfg["system"].format(
                audience_profile=audience_profile[:3000],
                tone_guide=tone_guide[:2000],
                rubrics_guide=rubrics_guide[:2000],
            )
        except KeyError as e:
            print(f"[warn] В system-промпте не хватает плейсхолдера: {e}")
            system = _fallback_system(audience_profile, tone_guide, rubrics_guide)
    else:
        system = _fallback_system(audience_profile, tone_guide, rubrics_guide)

    # === User промпт ===
    if prompts_cfg.get("user"):
        try:
            user = prompts_cfg["user"].format(
                count=count,
                target_label=target_label,
                theme=theme or "(на твой выбор, но в духе ЛЖ)",
                source=source or "(свободный — опирайся на боли ЦА и тон)",
                rubric=rubric_value,
                length_hint=length_hint,
                pains_section=pains_section,
            )
        except KeyError as e:
            print(f"[warn] В user-промпте не хватает плейсхолдера: {e}")
            user = _fallback_user(theme, source, count, rubric, target, target_label, length_hint, pains_section)
    else:
        user = _fallback_user(theme, source, count, rubric, target, target_label, length_hint, pains_section)

    return system, user


def _fallback_system(audience_profile: str, tone_guide: str, rubrics_guide: str) -> str:
    """Запасной system-промпт, если в config.yaml нет prompts.system."""
    return f"""Ты — контент-стратег Лаборатории желаний (ЛЖ) — психологического сообщества для женщин 25-45 лет.

## ПОРТРЕТ ЦЕЛЕВОЙ АУДИТОРИИ
{audience_profile[:3000]}

## ТОН ГОЛОСА
{tone_guide[:2000]}

## РУБРИКАТОР (обязательно используй разные рубрики)
{rubrics_guide[:2000]}

## ТВОИ ПРАВИЛА
1. Одна идея = одна тема, один ракурс. Не размывай.
2. Хук — это первая фраза поста. Острая, провокационная или узнаваемая. Не "продающая", а честная.
3. Язык ЦА, не маркетинга. Никаких "узнайте", "попробуйте", "упустите".
4. Без эзотерики (вселенная, энергия, карма).
5. Без "успешного успеха" (10 правил, 5 шагов к успеху).
6. Без нравоучения — делись наблюдением, не учи жить.
7. CTA — открытый вопрос или мягкое действие.
8. Если задана рубрика — она у КАЖДОЙ идеи. Иначе — чередуй рубрики.
9. Верни ТОЛЬКО валидный JSON-массив. Никаких ```json, никаких пояснений."""


def _fallback_user(theme, source, count, rubric, target, target_label, length_hint, pains_section) -> str:
    """Запасной user-промпт."""
    parts = [f"Сгенерируй РОВНО {count} идей постов для {target_label}."]
    if theme:
        parts.append(f"\n**Тема:** {theme}.")
    if source:
        parts.append(f"\n**Источник вдохновения:** {source}.")
    if rubric:
        parts.append(f"\n**Рубрика (ОБЯЗАТЕЛЬНО у всех идей):** {rubric}.")
    else:
        rubrics = ["разбор-цитаты", "детектор", "история", "провокация", "практика", "миф-vs-правда", "подборка"]
        parts.append(f"\n**Рубрики:** используй минимум 3 разных из: {', '.join(rubrics)}.")
    parts.append(f"\n**Длина текста:** {length_hint}.")
    if pains_section:
        parts.append(f"\n{pains_section}")
    parts.append("\nВерни ТОЛЬКО JSON-массив объектов с полями: title, hook, key_idea, structure_hint, rubric, cta, target_metric, priority, reasoning, notes.")
    return "\n".join(parts)


def parse_llm_json(response: str) -> List[Dict[str, Any]]:
    """Распарсить JSON из ответа LLM. Терпимо к ```json обёрткам и пр.

    Поддерживает:
      - [...] (голый массив)
      - {"ideas": [...]} (dict с массивом)
      - ```json ... ``` обёрнутый в markdown
    """
    import re

    text = response.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```\s*$", "", text)
    text = text.strip()

    # Сначала пытаемся распарсить целиком
    try:
        data = json.loads(text)
        if isinstance(data, list):
            return data
        if isinstance(data, dict) and "ideas" in data and isinstance(data["ideas"], list):
            return data["ideas"]
    except json.JSONDecodeError:
        pass

    # Не вышло — ищем первый [ или { через баланс скобок
    def find_balanced(s: str, open_ch: str, close_ch: str) -> Optional[str]:
        start = s.find(open_ch)
        if start == -1:
            return None
        depth = 0
        for i in range(start, len(s)):
            if s[i] == open_ch:
                depth += 1
            elif s[i] == close_ch:
                depth -= 1
                if depth == 0:
                    return s[start:i + 1]
        return None

    for open_ch, close_ch, key in [("[", "]", None), ("{", "}", "ideas")]:
        candidate = find_balanced(text, open_ch, close_ch)
        if candidate is None:
            continue
        try:
            data = json.loads(candidate)
            if isinstance(data, list):
                return data
            if isinstance(data, dict) and key in data and isinstance(data[key], list):
                return data[key]
        except json.JSONDecodeError:
            continue

    return []


def generate_ideas_with_llm(
    theme: str = None,
    source: str = None,
    target: str = "vk",
    count: int = 5,
    rubric: str = None,
    audience: str = "ca-zhelanii",
    tone: str = "B3",
    use_llm: bool = True,
    config: Optional[Dict[str, Any]] = None,
) -> List[Dict[str, Any]]:
    """Генерация идей через LLM (или заглушка, если LLM недоступен)."""

    # Загружаем профили и config
    if config is None:
        config = load_config()
    audience_profile = load_profile("ca-zhelanii")
    tone_guide = load_profile("tone-of-voice")
    rubrics_guide = load_profile("rubrics")
    pain_bank = load_pain_bank()

    ideas: List[Dict[str, Any]] = []
    used_titles: set = set()

    if use_llm:
        try:
            from lib.llm_client import LLMClient
            client = LLMClient()
            if not client.is_available():
                print(f"[warn] LLM недоступен (provider={client.provider}), fallback на заглушки")
                use_llm = False
        except Exception as e:
            print(f"[warn] Не удалось инициализировать LLM: {e}")
            use_llm = False

    if use_llm:
        # Множитель из конфига (сколько просить у LLM с запасом)
        llm_cfg = config.get("llm", {}) or {}
        multiplier = llm_cfg.get("request_multiplier", 2) or 2
        request_count = max(count + 2, int(count * multiplier))
        system, user = build_prompt(
            theme=theme, source=source, target=target, count=request_count,
            rubric=rubric, audience_profile=audience_profile,
            tone_guide=tone_guide, rubrics_guide=rubrics_guide, pain_bank=pain_bank,
            config=config,
        )
        try:
            print(f"[llm] Запрашиваю {request_count} идей (provider={client.provider}, model={client.model})...")
            response = client.generate(user, system=system, max_tokens=4000, temperature=0.8)
            print(f"[llm] Получен ответ ({len(response)} символов)")
            parsed = parse_llm_json(response)
            print(f"[llm] Распарсено идей: {len(parsed)}")
        except Exception as e:
            print(f"[error] LLM ошибка: {e}")
            parsed = []

        # Превращаем в карточки
        for i, item in enumerate(parsed):
            if len(ideas) >= count:
                break

            title = item.get("title", "").strip()
            if not title or title in used_titles:
                continue
            used_titles.add(title)

            r = normalize_rubric(rubric or item.get("rubric") or "разбор-цитаты")
            idea = {
                "id": make_idea_id(),
                "created": datetime.now().isoformat(),
                "version": "1.0",
                "target": target,
                "rubric": r,
                "priority": item.get("priority", "medium"),
                "title": title,
                "hook": item.get("hook", "").strip(),
                "key_idea": item.get("key_idea", "").strip(),
                "structure_hint": item.get("structure_hint", "storytelling"),
                "source": {
                    "type": source or "llm",
                    "ref": None,
                    "reason": f"Сгенерировано LLM ({client.provider}/{client.model}) на тему '{theme or source}'",
                },
                "audience": audience,
                "tone": tone,
                "cta": item.get("cta", "").strip(),
                "target_metric": item.get("target_metric", "комменты"),
                "reasoning": item.get("reasoning", "").strip(),
                "notes": item.get("notes", "").strip(),
                "llm_provider": client.provider,
                "llm_model": client.model,
                "fingerprint": make_fingerprint(
                    theme or "general",
                    r,
                    (item.get("hook", "") + " " + title).split()[:5],
                ),
            }
            ideas.append(idea)

    # Если LLM не дал нужного количества — дополняем заглушками
    if len(ideas) < count:
        rubrics_default = [
            "разбор-цитаты", "детектор", "история",
            "провокация", "практика", "миф-vs-правда", "подборка",
        ]
        for i in range(count - len(ideas)):
            r = rubric or rubrics_default[(len(ideas) + i) % len(rubrics_default)]
            stub_num = len(ideas) + i + 1
            ideas.append({
                "id": make_idea_id(),
                "created": datetime.now().isoformat(),
                "version": "1.0",
                "target": target,
                "rubric": r,
                "priority": "low",
                "title": f"[LLM не хватило] Идея #{stub_num} на тему {theme or source or 'general'}",
                "hook": "[Заглушка — LLM не вернул достаточно идей]",
                "key_idea": "[Заглушка — дописать вручную]",
                "structure_hint": "storytelling",
                "source": {
                    "type": "fallback",
                    "ref": None,
                    "reason": f"Дозаполнение после нехватки от LLM (получено {len(ideas) - i})",
                },
                "audience": audience,
                "tone": tone,
                "cta": "[Заглушка]",
                "target_metric": "комменты",
                "reasoning": "[Заглушка]",
                "notes": "v0.2 — дописать вручную, увеличить request_count или починить парсинг",
                "fingerprint": make_fingerprint(
                    theme or "general", r, [f"fallback-{stub_num}"]
                ),
            })

    return ideas


def write_markdown_report(ideas: List[Dict[str, Any]], args: argparse.Namespace) -> Path:
    """Сохранить markdown-отчёт по пачке идей."""
    GENERATED_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    theme_part = f"-{args.theme[:20]}" if args.theme else ""
    filepath = GENERATED_DIR / f"{stamp}{theme_part}-pack.md"

    lines = [
        f"# Пачка идей: {args.theme or args.source or 'general'}",
        "",
        f"**Дата:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Запрос:** `python generate_ideas.py --theme \"{args.theme}\" --source {args.source} --count {args.count} --target {args.target}`",
        f"**Скил:** content-ideas-skill v0.1",
        "",
        "---",
        "",
        "## Сводка",
        "",
        f"- **Всего идей:** {len(ideas)}",
        f"- **Target:** {args.target}",
        f"- **Рубрика (если задана):** {args.rubric or '—'}",
        "",
        "**⚠️ v0.1 — это заглушки.** Тексты идей (title, hook, key_idea, cta) нужно дописать вручную или сгенерировать через LLM после реализации v0.2.",
        "",
        "---",
        "",
    ]

    for i, idea in enumerate(ideas, 1):
        lines.extend([
            f"## Идея #{i}: {idea['title']}",
            "",
            f"**ID:** `{idea['id']}`",
            f"**Рубрика:** {idea['rubric']}",
            f"**Приоритет:** {idea['priority']}",
            f"**Источник:** {idea['source']['type']}",
            f"**Tone:** {idea['tone']}",
            "",
            "### Хук",
            f"> {idea['hook']}",
            "",
            "### Ключевая идея",
            f"{idea['key_idea']}",
            "",
            "### CTA",
            f"{idea['cta']}",
            "",
            "### Почему сработает",
            f"{idea['reasoning']}",
            "",
            "### Ограничения",
            f"{idea['notes']}",
            "",
            "---",
            "",
        ])

    filepath.write_text("\n".join(lines), encoding="utf-8")
    return filepath


def main() -> int:
    """Главная точка входа."""
    parser = argparse.ArgumentParser(
        description="Генератор идей постов для Лаборатории желаний"
    )
    parser.add_argument(
        "--theme", type=str, default=None,
        help="Тема (например, 'навязанные желания')",
    )
    parser.add_argument(
        "--source", type=str, default=None,
        choices=["wl", "coach", "pains", "competitors", "seasonal", "trends", "manual"],
        help="Источник идей",
    )
    parser.add_argument(
        "--count", type=int, default=10,
        help="Сколько идей сгенерировать (default: 10)",
    )
    parser.add_argument(
        "--target", type=str, default="vk",
        choices=["vk", "blog", "telegram"],
        help="Площадка (default: vk)",
    )
    parser.add_argument(
        "--rubric", type=str, default=None,
        choices=["разбор-цитаты", "детектор", "история", "провокация", "практика", "миф-vs-правда", "подборка"],
        help="Рубрика (если не задана — микс)",
    )
    parser.add_argument(
        "--audience", type=str, default="ca-zhelanii",
        help="ID профиля ЦА",
    )
    parser.add_argument(
        "--tone", type=str, default="B3",
        help="Тон (например, A2, B3, D1)",
    )
    parser.add_argument(
        "--no-dedupe", action="store_true",
        help="Не проверять дедуп (по умолчанию проверяем)",
    )
    parser.add_argument(
        "--no-llm", action="store_true",
        help="Не вызывать LLM (использовать заглушки — для отладки)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Не сохранять в банк, только показать",
    )

    args = parser.parse_args()

    # Загружаем config один раз
    config = load_config()
    if config:
        print(f"[config] Загружен config.yaml (промпты: {'да' if config.get('llm', {}).get('prompts', {}).get('system') else 'нет, fallback'})")
    else:
        print(f"[config] config.yaml не найден или pyyaml не установлен — используем встроенные промпты")

    print(f"[generate_ideas] Тема: {args.theme or '(не задана)'}")
    print(f"[generate_ideas] Источник: {args.source or '(любой)'}")
    print(f"[generate_ideas] Кол-во: {args.count}")
    print(f"[generate_ideas] Target: {args.target}")
    print(f"[generate_ideas] Рубрика: {args.rubric or '(микс)'}")
    print(f"[generate_ideas] LLM: {'выкл' if args.no_llm else 'авто'}")
    print()

    # Генерируем идеи (через LLM, если доступен)
    ideas = generate_ideas_with_llm(
        theme=args.theme,
        source=args.source,
        target=args.target,
        count=args.count,
        rubric=args.rubric,
        audience=args.audience,
        tone=args.tone,
        use_llm=not args.no_llm,
        config=config,
    )

    # Дедуп
    if not args.no_dedupe:
        history = load_history()
        before = len(ideas)
        ideas = [
            i for i in ideas
            if not is_duplicate(i["fingerprint"], history)
        ]
        after = len(ideas)
        if before != after:
            print(f"[dedupe] Отфильтровано {before - after} дублей")

    # Сохраняем
    if not args.dry_run:
        bank = load_ideas_bank()
        bank["ideas"].extend(ideas)
        save_ideas_bank(bank)
        print(f"[save] Добавлено {len(ideas)} идей в data/ideas-bank.json")

        # Синхронизируем с history.json (для дедупа)
        history = load_history()
        for idea in ideas:
            history_entry = {
                "id": idea["id"],
                "created": idea["created"],
                "title": idea["title"],
                "rubric": idea["rubric"],
                "theme": args.theme or "general",
                "hook_keywords": idea.get("hook", "").split()[:5] if idea.get("hook") else [],
                "source_type": idea.get("source", {}).get("type", "manual"),
                "source_ref": idea.get("source", {}).get("ref"),
                "fingerprint": idea["fingerprint"],
                "target": idea["target"],
            }
            history["ideas"].append(history_entry)
        save_history(history)
        print(f"[save] Добавлено {len(ideas)} записей в data/history.json")

        # Markdown отчёт
        md_path = write_markdown_report(ideas, args)
        print(f"[save] Markdown отчёт: {md_path}")

    # Показываем
    print()
    print("=" * 60)
    print(f"Сгенерировано идей: {len(ideas)}")
    print("=" * 60)
    for i, idea in enumerate(ideas, 1):
        print(f"\n--- Идея #{i} ---")
        print(f"ID:        {idea['id']}")
        print(f"Рубрика:   {idea['rubric']}")
        print(f"Title:     {idea['title']}")
        print(f"Hook:      {idea['hook']}")
        print(f"FP:        {idea['fingerprint']}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
