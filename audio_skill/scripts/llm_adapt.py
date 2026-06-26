"""
LLM-адаптер: черновой YAML → финальный YAML для Audio Skill.

Берёт результат pdf_parse.py (или текст из чата), прогоняет через гибридный
конвейер «локальные правила + YandexGPT» с промптом prompts/affirm-adapt.md,
сохраняет финальный YAML в data/library/<slug>.yaml.

Использование:
    python scripts/llm_adapt.py data/library/_draft-zolotye-pravila.yaml \
        --provider=yandex \
        --voice=ermil \
        --style=lively \
        --tone=warm_mentor \
        --remove-concrete-examples \
        --add-whisper \
        --out=data/library/zolotye-pravila.yaml

В v0.2 — реальный LLM-вызов через YandexGPT (Foundation Models v1).
В v0.1 — был stub на regex. Сейчас regex-логика переехала в _local_normalize()
и вызывается ПЕРЕД LLM (как пре-нормализация).
"""

import argparse
import io
import os
import re
import sys
from pathlib import Path

# Принудительно UTF-8 для Windows-консоли (cp1252 не понимает кириллицу)
if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

try:
    import yaml
except ImportError:
    print("[!] pip install pyyaml", file=sys.stderr)
    sys.exit(1)

try:
    import requests
except ImportError:
    print("[!] pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass


PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "affirm-adapt.md"
SYSTEM_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "system-vivify.md"
TEMPLATES_DIR = Path(__file__).parent.parent / "data" / "templates"
PROMPTS_DIR = Path(__file__).parent.parent / "prompts"


# =============================================================================
# ЛОКАЛЬНЫЕ ПРАВИЛА (детерминированная пре-нормализация)
# =============================================================================

# Поддерживаем: ключ (regex) → замена. Регистр учитывается.
# ВАЖНО: порядок имеет значение — длинные/специфичные правила идут раньше.
LOCAL_RULES: list[tuple[str, str]] = [
    # 1. Канцеляризмы и книжные обороты
    (r"\bосуществлять\b", "делать"),
    (r"\bосуществляет\b", "делает"),
    (r"\bосуществляешь\b", "делаешь"),
    (r"\bосуществлял[аи]?\b", "делал"),
    (r"\bосуществляться\b", "делаться"),
    (r"\bосуществляется\b", "делается"),
    (r"\bпроизводить\b", "делать"),
    (r"\bпроизводит\b", "делает"),
    (r"\bпредставляет собой\b", "это"),
    (r"\bявляется\b", "это"),
    (r"\bявляются\b", "это"),
    (r"\bв настоящее время\b", "сейчас"),
    (r"\bв настоящий момент\b", "сейчас"),
    (r"\bв данный момент\b", "сейчас"),
    (r"\bна сегодняшний день\b", "сейчас"),
    (r"\bна данный момент\b", "сейчас"),
    (r"\bблагодаря чему\b", "поэтому"),
    (r"\bв связи с этим\b", "поэтому"),
    (r"\bв связи с чем\b", "поэтому"),
    (r"\bтаким образом,?\s*", ""),
    (r"\bоднако,?\s*", "но "),
    (r"\bтем не менее,?\s*", "но "),
    (r"\bвместе с тем,?\s*", "и "),
    (r"\bв конечном итоге,?\s*", "в итоге, "),
    (r"\bв конечном счёте,?\s*", "в итоге, "),
    (r"\bв первую очередь,?\s*", "сначала "),
    (r"\bпрежде всего,?\s*", "сначала "),
    (r"\bследует отметить,?\s*что\s*", ""),
    (r"\bследует подчеркнуть,?\s*что\s*", ""),
    (r"\bстоит отметить,?\s*что\s*", ""),
    (r"\bнеобходимо отметить,?\s*что\s*", ""),
    (r"\bнеобходимо\b", "нужно"),
    (r"\bжелательно\b", "лучше"),
    (r"\bцелесообразно\b", "лучше"),
    (r"\bкак известно,?\s*", ""),
    (r"\bтак сказать,?\s*", ""),
    (r"\bв общем-то,?\s*", ""),
    (r"\bв принципе,?\s*", ""),
    (r"\bпо большому счёту,?\s*", ""),
    (r"\bбезусловно,?\s*", ""),
    (r"\bразумеется,?\s*", ""),
    # 2. Двойные пробелы после удаления
    (r"  +", " "),
    # 3. Лишние переносы строк (3+ подряд → 2)
    (r"\n{3,}", "\n\n"),
]


def _local_normalize(script: str) -> str:
    """Применяет локальные правила к тексту скрипта."""
    for pattern, replacement in LOCAL_RULES:
        script = re.sub(pattern, replacement, script, flags=re.IGNORECASE)
    return script


def _strip_llm_intro_outro(script: str) -> str:
    """Удаляет LLM-вставленные приветствия и прощания, если они появились
    после шаблона (YandexGPT иногда игнорирует инструкцию «не пиши своё»).

    Стратегия:
    - intro: удаляет «Здравствуй.», «Привет!», «Добро пожаловать», «Дорогой друг»
      если они идут сразу после [ПАУЗА:2s] (т.е. после шаблона).
    - outro: удаляет «Благодарю тебя...До встречи», «До новых встреч»,
      «До скорой встречи» в конце скрипта.
    """
    # 1. Удаляем LLM-приветствие ПОСЛЕ шаблона
    # Шаблон заканчивается на [ПАУЗА:2s], после неё идёт LLM-блок.
    # Паттерн: [ПАУЗА:2s]\n...до 2-3 строк...\n[ПАУЗА:0.5s] или новый [ВДОХ] или контент
    intro_patterns = [
        # «Здравствуй. Сегодня ...»
        r"(\[ПАУЗА:2s\]\s*\[ПАУЗА:2s\]\s*)\[?ШЁПОТ[^\]]*\]?\s*Здравствуй[^\n]*\n?(\[?ШЁПОТ[^\]]*\]?\s*)?",
        r"(\[ПАУЗА:2s\]\s*\[ПАУЗА:2s\]\s*)Здравствуй[^\n]*\n?(\[?ШЁПОТ[^\]]*\]?\s*)?",
        r"(\[ПАУЗА:2s\]\s*\[ПАУЗА:2s\]\s*)\[?ШЁПОТ[^\]]*\]?\s*Привет[^\n]*\n?(\[?ШЁПОТ[^\]]*\]?\s*)?",
        r"(\[ПАУЗА:2s\]\s*\[ПАУЗА:2s\]\s*)\[?ШЁПОТ[^\]]*\]?\s*Дорогой друг[^\n]*\n?(\[?ШЁПОТ[^\]]*\]?\s*)?",
        r"(\[ПАУЗА:2s\]\s*\[ПАУЗА:2s\]\s*)Привет[^\n]*\n?(\[?ШЁПОТ[^\]]*\]?\s*)?",
    ]
    for pat in intro_patterns:
        script = re.sub(pat, r"\1", script, flags=re.MULTILINE)

    # 2. Удаляем LLM-прощание в конце (перед ``` или [Музыка становится])
    # Паттерн: ... «Благодарю тебя...» «До встречи» / «До скорой» / «До новых встреч»
    outro_patterns = [
        r"\n\[?ВДОХГЛУБ\]?\s*\[?ШЁПОТ[^\]]*\]?\s*Благодарю[^[]*?\[?ШЁПОТ[^\]]*\]?\s*До[^[]*?",
        r"\n\[?ВДОХГЛУБ\]?\s*\[?ШЁПОТ[^\]]*\]?\s*Благодарю[^[]*?\[?ШЁПОТ[^\]]*\]?\s*",
        r"\n\[?ВДОХГЛУБ\]?\s*\[?ШЁПОТ[^\]]*\]?\s*Продолжай[^[]*?\[?ШЁПОТ[^\]]*\]?\s*",
    ]
    # НЕ удаляем, если это наш шаблон. Проверяем: если в outro уже есть «Продолжай экспериментировать» — оставляем.
    if "Продолжай экспериментировать" not in script:
        for pat in outro_patterns:
            script = re.sub(pat, "\n", script, flags=re.MULTILINE | re.DOTALL)

    return script


def _apply_micro_cta_template(question: str, url: str = "") -> str:
    """Собирает micro_cta блок из data/templates/micro_cta.yaml с подстановкой.

    Возвращает пустую строку, если шаблон не найден или вопрос пустой.
    """
    if not question or not question.strip():
        return ""
    tpl_path = TEMPLATES_DIR / "micro_cta.yaml"
    if not tpl_path.exists():
        print(f"[!] Шаблон 'micro_cta' не найден: {tpl_path}", file=sys.stderr)
        return ""
    tpl = yaml.safe_load(tpl_path.read_text(encoding="utf-8"))
    block = tpl.get("micro_cta", "").rstrip()
    # Защита от «?» в конце вопроса (мы добавляем свой знак вопроса для TTS-паузы)
    q = question.strip().rstrip("?.!")
    if not q.endswith("?"):
        q = q + "?"
    block = block.replace("{question}", q).replace("{url}", url)
    return block


def _insert_block_before_outro(script: str, block: str) -> str:
    """Вставляет block перед outro (последний [ВДОХГЛУБ] или конец script)."""
    if not block:
        return script
    # Стратегия: вставляем перед последним [ВДОХГЛУБ] (начало outro)
    m = list(re.finditer(r"\[ВДОХГЛУБ\]", script))
    if m:
        # Вставляем перед [ВДОХГЛУБ] + 2 переноса до
        last = m[-1]
        return script[:last.start()].rstrip() + "\n\n" + block + "\n\n" + script[last.start():]
    # Fallback: в конец script (до Markdown-обвязки)
    return script.rstrip() + "\n\n" + block + "\n"


def _apply_intro_outro_template(script: str, template: str, micro_cta_block: str = "", setting_line: str = "") -> str:
    """Заменяет приветствие и прощание в script на шаблонные блоки.

    Стратегия:
    - intro: заменяет ВСЁ от начала до первого [ПАУЗА:2s] (или до первого «Правило»/«Сегодня»)
    - {setting_line}: LLM-сгенерированная фраза 8-15 слов про книгу.
      Если пустая — берётся дефолт «Сегодня у нас новая практика».
    - micro_cta (опционально): вставляется между body и outro
    - outro: добавляет шаблонный блок в конец (если его ещё нет)
    """
    template_path = TEMPLATES_DIR / f"{template}.yaml"
    if not template_path.exists():
        print(f"[!] Шаблон '{template}' не найден: {template_path}", file=sys.stderr)
        return script

    tpl = yaml.safe_load(template_path.read_text(encoding="utf-8"))
    intro = tpl.get("intro", "").rstrip()
    outro = tpl.get("outro", "").rstrip()

    # Подставляем setting_line в intro (по плейсхолдеру {setting_line})
    if not setting_line:
        setting_line = "Сегодня у нас новая практика — тихо послушай себя."
    intro = intro.replace("{setting_line}", setting_line)

    # 1. Убираем старое интро (от ``` в начале до первого [ПАУЗА:2s] или [Правило / Сегодня)
    # В шаблонах мы знаем точку разделения: первое [ПАУЗА:2s] после шёпота
    # Стратегия: ищем первый абзац (от ``` до первого [ПАУЗА:2s] или [Правило ...)
    m = re.search(
        r"\[ПАУЗА:2s\]|\[Правило\s|\[Сегодня\s|\[Шаг\s",
        script,
    )
    if m:
        body = script[m.start():].lstrip("\n")
    else:
        # Fallback: ищем "Правило первое" / "Сегодня" в тексте
        m2 = re.search(
            r"(Правило\s+(?:первое|второе|1\.|2\.)|Сегодня\s+(?:я|мы|ты|попробуй|поговорим)|Шаг\s+1)",
            script,
        )
        if m2:
            body = script[:m2.start()] + script[m2.start():]
            # Заново ищем
            m3 = re.search(
                r"\[ПАУЗА:2s\]|\[Правило\s|\[Сегодня\s|\[Шаг\s",
                script,
            )
            body = script[m3.start():].lstrip("\n") if m3 else script
        else:
            body = script

    # 2. Убираем Markdown-обвязку и финальную музыкальную ремарку
    body = re.sub(r"^```\w*\n?", "", body)
    body = re.sub(r"\n?```\s*$", "", body)
    body = re.sub(r"\[Музыка[^]]*\]", "", body, flags=re.IGNORECASE)
    body = body.rstrip()

    # 3. Убираем старое аутро (последние 2-3 предложения перед музыкой)
    outro_markers = [
        r"Благодарю[^.]+\.\s*До встречи\.",
        r"Благодарю[^.]+\.\s*До скорой встречи\.",
        r"До встречи\.",
        r"До новых встреч\.",
        r"До скорой встречи\.",
        r"Продолжай[^.]+\.\s*",
    ]
    for marker in outro_markers:
        body = re.sub(marker, "", body, flags=re.IGNORECASE | re.DOTALL)

    # 4. Собираем финальный script (outro всегда в конце, micro_cta — между body и outro)
    if micro_cta_block:
        new_script = (
            f"```\n{intro}\n\n{body}\n\n{micro_cta_block}\n\n{outro}\n```\n"
        )
    else:
        new_script = (
            f"```\n{intro}\n\n{body}\n\n{outro}\n```\n"
        )
    return new_script


def _remove_concrete_examples(script: str) -> str:
    """Убирает конкретику: числа, города, имена."""
    # Числа + валюта + период + дата
    script = re.sub(
        r"\d+\s*(тысяч|миллионов)?\s*(рублей|долларов|евро|₽|\$|€)?\s*"
        r"(в месяц|в год|в неделю)?\s*к\s+\w+\s+\d{4}\s*года?",
        "столько-то в месяц к такой-то дате",
        script,
    )
    # «лечу/еду в [Город] на [период]»
    script = re.sub(
        r"(?:лечу|еду|поеду|отправлюсь) в [А-ЯЁ][а-яё]+"
        r" на [а-яё]+ ?(?:праздники|каникулы|выходные|новый год|рождество)",
        "лечу в конкретное место на конкретные даты",
        script,
    )
    # «лечу/еду в [Город]» (без периода)
    script = re.sub(
        r"(?:лечу|еду|поеду|отправлюсь) в [А-ЯЁ][а-яё]+",
        "отправляюсь в конкретное место",
        script,
    )
    # ФИО
    script = re.sub(
        r"\b[А-ЯЁ][а-яё]+\s+[А-ЯЁ][а-яё]+(?![\.,])",
        "человек, о котором я думаю",
        script,
    )
    return script


def _add_whisper(script: str) -> str:
    """Оборачивает интро/аутро в шёпот-теги, если их ещё нет."""
    if "[ШЁПОТ:" not in script:
        # Найти первое приветствие
        m = re.search(
            r"(Здравствуй[^.]+\.|Привет[^.]+\.|Дорогой друг[^.]+\.)",
            script,
        )
        if m:
            script = (
                script[:m.start()] + "[ШЁПОТ:30%]\n" + m.group(0)
                + "\n[ШЁПОТ:off]\n" + script[m.end():]
            )
    if script.count("[ШЁПОТ:") == 1:
        m = re.search(r"(Благодарю[^.]+\.|До встречи\.|До скорой встречи\.)", script)
        if m and "[ШЁПОТ:" not in script[max(0, m.start()-20):m.start()]:
            script = (
                script[:m.start()] + "[ШЁПОТ:30%]\n" + m.group(0)
                + "\n[ШЁПОТ:off]\n" + script[m.end():]
            )
    return script


# =============================================================================
# YANDEXGPT (Foundation Models v1)
# =============================================================================

def _load_yandex_prompt() -> str:
    """Грузит текст промпта для YandexGPT (берется из affirm-adapt.md секция «Промпт для YandexGPT»)."""
    full = PROMPT_PATH.read_text(encoding="utf-8")
    # Извлечь блок между «```» после «# Промпт для YandexGPT» и следующим «```»
    m = re.search(r"# Промпт для YandexGPT\s*```\n(.*?)\n```", full, re.DOTALL)
    if not m:
        # Fallback: вся секция «Промпт для YandexGPT»
        m = re.search(r"# Промпт для YandexGPT\s*(.+?)(?:\n## |\Z)", full, re.DOTALL)
    if not m:
        raise RuntimeError("Не найден промпт для YandexGPT в affirm-adapt.md")
    return m.group(1).strip()


def _yandexgpt_call(script: str, style: str, voice: str, tone: str) -> str:
    """Вызов YandexGPT для «оживления» script. Возвращает новый script."""
    api_key = os.getenv("YANDEX_GPT_API_KEY")
    folder_id = os.getenv("YANDEX_GPT_FOLDER_ID")
    model = os.getenv("YANDEX_GPT_MODEL", "yandexgpt-lite")
    verify_ssl = os.getenv("LLM_VERIFY_SSL", "false").lower() not in ("0", "false", "no", "")

    if not api_key or not folder_id:
        raise RuntimeError(
            "YANDEX_GPT_API_KEY и YANDEX_GPT_FOLDER_ID должны быть в .env"
        )

    system_prompt = _load_yandex_prompt()
    user_prompt = (
        f"СТИЛЬ: {style}\n"
        f"ГОЛОС: {voice} (учти это при разбивке фраз)\n"
        f"ТОН: {tone}\n\n"
        f"ИСХОДНЫЙ SCRIPT:\n{script}\n\n"
        f"Верни ТОЛЬКО изменённый script (с тегами), без пояснений."
    )

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "x-folder-id": folder_id,
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": f"gpt://{folder_id}/{model}",
        "completionOptions": {
            "stream": False,
            "temperature": float(os.getenv("YANDEX_GPT_TEMPERATURE", "0.6")),
            "maxTokens": "2000",
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_prompt},
        ],
    }

    r = requests.post(url, headers=headers, json=payload, verify=verify_ssl, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"YandexGPT HTTP {r.status_code}: {r.text[:500]}")

    data = r.json()
    try:
        text = data["result"]["alternatives"][0]["message"]["text"]
    except (KeyError, IndexError, TypeError) as e:
        raise RuntimeError(f"Неожиданный ответ YandexGPT: {data}") from e
    text = text.strip()
    # YandexGPT иногда возвращает литературные "\n" / "\t" вместо реальных
    # переносов строк (когда модель экранирует переносы в своём JSON-ответе).
    # Разворачиваем их в настоящие символы.
    text = text.replace("\\n", "\n").replace("\\t", "\t").replace('\\"', '"')
    return text


def _load_setting_line_prompt() -> tuple[str, float, int]:
    """Грузит system_prompt + параметры для setting_line из prompts/setting-line.md.

    Возвращает кортеж (system_prompt, temperature, max_tokens).

    Формат файла:
    ---
    name: setting_line
    temperature: 0.7
    max_tokens: 100
    ---

    # комментарии...

    # SYSTEM PROMPT
    {текст промпта}
    # END SYSTEM PROMPT

    Если frontmatter битый / маркеров нет — RuntimeError (адаптер
    использует дефолт «Сегодня у нас новая практика — тихо послушай себя.»).
    """
    path = PROMPTS_DIR / "setting-line.md"
    if not path.exists():
        raise RuntimeError(f"Промпт для setting_line не найден: {path}")
    full = path.read_text(encoding="utf-8")

    # Парсим frontmatter (YAML между --- маркерами)
    fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)$", full, re.DOTALL)
    if not fm_match:
        raise RuntimeError(
            f"В {path.name} нет frontmatter (нужны маркеры '---' в начале файла)"
        )
    try:
        fm = yaml.safe_load(fm_match.group(1)) or {}
    except yaml.YAMLError as e:
        raise RuntimeError(f"Битый YAML в frontmatter {path.name}: {e}")
    temperature = float(fm.get("temperature", 0.7))
    max_tokens = int(fm.get("max_tokens", 100))

    body = fm_match.group(2)
    pm_match = re.search(
        r"# SYSTEM PROMPT\s*\n(.*?)\n\s*# END SYSTEM PROMPT",
        body, re.DOTALL,
    )
    if not pm_match:
        raise RuntimeError(
            f"В {path.name} не найдены маркеры '# SYSTEM PROMPT' / '# END SYSTEM PROMPT'"
        )
    return pm_match.group(1).strip(), temperature, max_tokens


def _yandexgpt_setting_line(title: str, author: str, tone: str, voice: str) -> str:
    """Генерит «живую» фразу-сеттинг для intro (8-15 слов).

    Используется вместо шаблонного «Сегодня мы хотим предложить тебе новый
    интересный опыт». LLM получает title/author/tone и возвращает 1 фразу,
    которая встанет между «Здравствуй. Лаборатория желаний.» и телом аудио.

    System prompt берётся из prompts/setting-line.md (редактируется без
    правки Python). Если LLM упал / вернул мусор — возвращается дефолт
    «Сегодня у нас новая практика — тихо послушай себя.» (без обращения к сети).
    """
    api_key = os.getenv("YANDEX_GPT_API_KEY")
    folder_id = os.getenv("YANDEX_GPT_FOLDER_ID")
    model = os.getenv("YANDEX_GPT_MODEL", "yandexgpt-lite")
    verify_ssl = os.getenv("LLM_VERIFY_SSL", "false").lower() not in ("0", "false", "no", "")

    if not api_key or not folder_id:
        return ""  # вызывающий код подставит дефолт

    try:
        system_prompt, temperature, max_tokens = _load_setting_line_prompt()
    except RuntimeError as e:
        print(f"[!] {e}. Использую встроенный дефолт.")
        return ""

    user_prompt = (
        f"КНИГА: {title}\n"
        f"АВТОР: {author}\n"
        f"ТОН ТРЕКА: {tone}\n"
        f"ГОЛОС: {voice}\n"
    )

    url = "https://llm.api.cloud.yandex.net/foundationModels/v1/completion"
    headers = {
        "Authorization": f"Api-Key {api_key}",
        "x-folder-id": folder_id,
        "Content-Type": "application/json",
    }
    payload = {
        "modelUri": f"gpt://{folder_id}/{model}",
        "completionOptions": {
            "stream": False,
            "temperature": temperature,
            "maxTokens": str(max_tokens),
        },
        "messages": [
            {"role": "system", "text": system_prompt},
            {"role": "user", "text": user_prompt},
        ],
    }

    try:
        r = requests.post(url, headers=headers, json=payload, verify=verify_ssl, timeout=30)
        if r.status_code != 200:
            print(f"[!] setting_line HTTP {r.status_code}: {r.text[:200]}", file=sys.stderr)
            return ""
        data = r.json()
        text = data["result"]["alternatives"][0]["message"]["text"].strip()
        text = text.replace("\\n", " ").replace("\\t", " ").replace('\\"', '"')
        # Берём только первое предложение (защита от многословия)
        text = re.split(r"[.!?]\s", text, maxsplit=1)[0].strip()
        # Если нет точки — добавим
        if not text.endswith((".", "!", "?")):
            text = text + "."
        # Если короче 4 слов — мусор, не используем
        if len(text.split()) < 4:
            return ""
        return text
    except Exception as e:
        print(f"[!] setting_line упал: {e}", file=sys.stderr)
        return ""


# =============================================================================
# ОСНОВНОЙ КОНВЕЙЕР
# =============================================================================

def adapt_yaml(draft: dict, *, provider: str, voice: str, tone: str, style: str,
               remove_concrete: bool, add_whisper: bool, template: str = "") -> dict:
    """Прогоняет черновой YAML через конвейер и возвращает финальный.

    Поля draft для micro_cta (опционально):
      - micro_cta_question: открытый вопрос (7-15 слов, без «?» в конце)
      - micro_cta_url: deprecated — URL сайта в аудио не проговаривается.
    Если micro_cta_question не задан, micro_cta блок НЕ вставляется — обратная совместимость.
    """
    out = dict(draft)

    # 1. Локальные правила (детерминированная нормализация)
    if "script" in out and isinstance(out["script"], str):
        script = out["script"]
        if remove_concrete:
            script = _remove_concrete_examples(script)
        script = _local_normalize(script)
        if add_whisper:
            script = _add_whisper(script)
        out["script"] = script
        out["remove_concrete_examples"] = bool(remove_concrete)

    # 2. LLM-вызов (если provider != stub)
    if provider != "stub" and "script" in out:
        original_chars = len(out["script"])
        print(f"[*] YandexGPT: оживление (style={style}, voice={voice})...")
        try:
            new_script = _yandexgpt_call(out["script"], style, voice, tone)
            new_chars = len(new_script)
            ratio = original_chars / max(new_chars, 1)
            # Если YandexGPT сжал более чем в 1.5 раза — откатываемся.
            # Это может случиться, если модель решила, что часть текста — «инструкция».
            if ratio > 1.5:
                print(f"[!] YandexGPT сжал в {ratio:.2f}x ({original_chars} → {new_chars} chars). "
                      f"Откатываюсь к локальной нормализации.")
            else:
                out["script"] = new_script
                print(f"[+] YandexGPT: OK, {new_chars} chars (ratio {ratio:.2f}x)")
        except Exception as e:
            print(f"[!] YandexGPT упал: {e}. Использую результат локальных правил.")

    # 3. Применение шаблона intro/outro + опционально micro_cta (один вызов)
    if template and "script" in out:
        # Сначала убираем LLM-интро/аутро (если он их добавил)
        out["script"] = _strip_llm_intro_outro(out["script"])
        # Готовим micro_cta заранее, чтобы один раз собрать финал
        micro_cta_question = (out.get("micro_cta_question") or "").strip()
        micro_cta_block = ""
        if micro_cta_question:
            micro_cta_url = (out.get("micro_cta_url") or "/my-experiment/").strip()
            micro_cta_block = _apply_micro_cta_template(micro_cta_question, micro_cta_url)
            if micro_cta_block:
                print(f"[*] Шаблон {template} + micro_cta ({len(micro_cta_block)} chars)")
            else:
                print(f"[*] Шаблон {template} (micro_cta шаблон пуст, пропускаю)")
        else:
            print(f"[*] Шаблон {template} (без micro_cta)")
        # Генерим «живую» фразу-сеттинг для intro (если провайдер не stub)
        setting_line = ""
        if provider != "stub":
            try:
                setting_line = _yandexgpt_setting_line(
                    title=out.get("title", ""),
                    author=out.get("author", ""),
                    tone=tone,
                    voice=voice,
                )
                if setting_line:
                    print(f"[+] setting_line: «{setting_line}»")
                else:
                    print("[*] setting_line: пусто, использую дефолт")
            except Exception as e:
                print(f"[!] setting_line упал: {e}. Использую дефолт.")
        # Затем применяем шаблон (один раз)
        out["script"] = _apply_intro_outro_template(
            out["script"], template, micro_cta_block=micro_cta_block, setting_line=setting_line,
        )
    elif "script" in out and out.get("micro_cta_question"):
        # Шаблон intro/outro не указан, но micro_cta есть — вставляем перед outro
        micro_cta_question = (out["micro_cta_question"] or "").strip()
        micro_cta_url = (out.get("micro_cta_url") or "/my-experiment/").strip()
        micro_cta_block = _apply_micro_cta_template(micro_cta_question, micro_cta_url)
        if micro_cta_block:
            print(f"[*] Micro CTA: добавляю блок ({len(micro_cta_block)} chars) перед outro")
            out["script"] = _insert_block_before_outro(out["script"], micro_cta_block)

    # 3. Мета
    out.setdefault("tone", tone)
    out.setdefault("pov", "second_person")
    out.setdefault("language", "ru-RU")
    out.setdefault("preserve_structure", True)
    out.setdefault("music_intro", "5s")
    out.setdefault("music_outro", "6s")

    # 4. Голос и фон (по жанру/категории/voice)
    genre = (out.get("genre") or "").lower()
    category = (out.get("meta", {}).get("category") or "").lower()
    out["voice"] = voice if voice != "auto" else _pick_voice(genre, category)
    out["background"] = _pick_background(genre, category)

    # 5. SSML
    out.setdefault("ssml", {})
    out["ssml"].setdefault("prosody", {"rate": 0.9, "pitch": 0, "volume": "medium"})
    out["ssml"].setdefault("whisper", {"enabled_in": [], "strength": 30})
    if add_whisper:
        out["ssml"]["whisper"]["enabled_in"] = ["intro_greeting", "outro_farewell"]

    # 6. Meta.category
    if not out.get("meta", {}).get("category"):
        out.setdefault("meta", {})["category"] = category or "аффирмация"

    # 7. Удаляем черновые поля
    out.pop("_draft", None)
    out.pop("_source", None)
    out.pop("duration_str", None)

    return out


def _pick_voice(genre: str, category: str) -> str:
    """Выбирает голос по жанру/категории. Ermil/Alena — основная пара для всех."""
    if "медитац" in genre or "медитац" in category or "визуализац" in genre:
        return "alena"
    if "объясня" in genre or "обуча" in genre or "урок" in category or "инструкц" in genre:
        return "ermil"
    if "аффирм" in category or "аффирм" in genre or "правила" in category:
        return "ermil"  # нейтральный наставник
    if "ритуал" in category or "утренн" in category:
        return "alena"  # тёплый женский
    return "ermil"  # по умолчанию — нейтральный мужской


def _pick_background(genre: str, category: str) -> str:
    """Выбирает фон по жанру/категории."""
    if "объясня" in genre or "обуча" in genre or "урок" in category or "техника" in genre:
        return "silence"
    if "медитац" in category or "визуализац" in genre:
        return "tide_calm"
    if "ритуал" in category and "утренн" in category:
        return "sea_mantra"
    if "ритуал" in category:
        return "candle_glow"
    return "ambient_drone"  # универсальный


def main() -> int:
    ap = argparse.ArgumentParser(description="LLM-адаптер чернового YAML → финальный")
    ap.add_argument("input", help="Путь к черновому YAML (после pdf_parse.py)")
    ap.add_argument("--provider", default="yandex", choices=["yandex", "stub"],
                    help="Провайдер LLM (yandex — реальный вызов, stub — без LLM)")
    ap.add_argument("--voice", default="auto",
                    choices=["auto", "ermil", "alena", "jane", "filipp", "madirus"],
                    help="Голос (auto = выбор по жанру)")
    ap.add_argument("--tone", default="warm_mentor",
                    choices=["warm_mentor", "i_affirmation", "we_journey", "instructor"],
                    help="Тон повествования")
    ap.add_argument("--style", default="lively",
                    choices=["lively", "gentle", "neutral"],
                    help="Стиль оживления (lively=короткие фразы+дыхание, gentle=мягче, neutral=минимум)")
    ap.add_argument("--remove-concrete-examples", action="store_true",
                    help="Убрать конкретные цифры/даты/имена")
    ap.add_argument("--keep-concrete-examples", action="store_true",
                    help="Оставить примеры (по умолчанию)")
    ap.add_argument("--add-whisper", action="store_true",
                    help="Обернуть интро/аутро в шёпот")
    ap.add_argument("--no-whisper", action="store_true",
                    help="Без шёпота (по умолчанию)")
    ap.add_argument("--template", default="",
                    help="Шаблон intro/outro из data/templates/<name>.yaml (например, intro_outro)")
    ap.add_argument("--out", required=True, help="Путь к финальному YAML")
    args = ap.parse_args()

    in_path = Path(args.input)
    if not in_path.exists():
        print(f"[!] Входной файл не найден: {in_path}", file=sys.stderr)
        return 1

    draft = yaml.safe_load(in_path.read_text(encoding="utf-8"))
    if draft.get("_draft") is not True:
        print(f"[!] Файл не помечен как _draft. Добавь `_draft: true` в шапку.",
              file=sys.stderr)
        return 1

    remove_concrete = args.remove_concrete_examples
    add_whisper = args.add_whisper

    print(f"[*] Адаптирую (provider={args.provider}, voice={args.voice}, "
          f"style={args.style}, tone={args.tone}, "
          f"remove_concrete={remove_concrete}, whisper={add_whisper})...")

    final = adapt_yaml(
        draft,
        provider=args.provider,
        voice=args.voice,
        tone=args.tone,
        style=args.style,
        remove_concrete=remove_concrete,
        add_whisper=add_whisper,
        template=args.template,
    )

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        yaml.dump(final, allow_unicode=True, sort_keys=False, default_flow_style=False),
        encoding="utf-8",
    )
    print(f"[+] {out_path}")
    print(f"\n[*] Следующий шаг:")
    print(f"    python scripts/ssml_build.py {out_path} --out=tmp/{final['slug']}.ssml")
    print(f"    python scripts/tts_yandex.py {out_path} --voice={final['voice']} --out=tmp/{final['slug']}-voice.mp3")
    return 0


if __name__ == "__main__":
    sys.exit(main())
