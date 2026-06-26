"""
SSML builder для Audio Skill.

Превращает data/library/<slug>.yaml в SSML для Yandex SpeechKit.
- [ПАУЗА:Xs] / [Пауза] → <break time="Xs"/>
- [ШЁПОТ:X%] → <break time="200ms"/>, (визуальный маркер; prosody не поддержан)
- [МУЗЫКА: ...] → пустая строка (не отправляется в TTS)
- [ВДОХ] / [ВЫДОХ] → <break time="300ms"/>
- [ТИШИНА:Xs] → <break time="Xs"/>

Дополнительно:
- Чистит «голые» подсказки вроде [Мягкая, спокойная музыка на фоне] —
  любой [...] без известной метки удаляется из озвучки.
- Расставляет ударения знаком «+» по словарю ACCENTS (ё явно, остальные через +).
- Убирает «хвост» Markdown: \n```, \n---.

Использование:
    python scripts/ssml_build.py data/library/<slug>.yaml --out=tmp/<slug>.ssml
"""

import argparse
import io
import re
import sys
from pathlib import Path

# Примечание: не оборачиваем stdout/stderr здесь — это library-модуль,
# импортируемый из tts_yandex.py. Иначе закроем родительский stdout.
# НО: для main() ниже — оборачиваем, чтобы print с кириллицей не падал на cp1252.

try:
    import yaml
except ImportError:
    print("[!] pip install pyyaml", file=sys.stderr)
    sys.exit(1)


# Словарь ударений: левая часть (без учёта регистра) → с расставленным «+»
# (ё уже указывает ударную гласную; остальные — через + перед гласной).
ACCENTS: dict[str, str] = {
    "здра+вствуй": "здра+вствуй",
    "здра+вствуйте": "здра+вствуйте",
    "лаборато+рия": "лаборато+рия",
    "жела+ний": "жела+ний",
    "жела+ния": "жела+ния",
    "жела+ние": "жела+ние",
    "золо+тые": "золо+тые",
    "пра+вила": "пра+вила",
    "исполне+ния": "исполне+ния",
    "исполне+ние": "исполне+ние",
    "превраща+ют": "превраща+ют",
    "мечты+": "мечты+",  # ё форма
    "ме+чты": "ме+чты",
    "свобо+ду": "свобо+ду",
    "напра+влено": "напра+влено",
    "зага+дывать": "зага+дывать",
    "му+жа": "му+жа",
    "дете+й": "дете+й",
    "роди+телей": "роди+телей",
    "формули+руй": "формули+руй",
    "вре+мени": "вре+мени",
    "подсо+знание": "подсо+знание",
    "подсо+знания": "подсо+знания",
    "при+знаёт": "при+знаёт",
    "боле+ть": "боле+ть",
    "здоро+вым": "здоро+вым",
    "одно+й": "одно+й",
    "счастли+вых": "счастли+вых",
    "отноше+ниях": "отноше+ниях",
    "отноше+ния": "отноше+ния",
    "конкре+тика": "конкре+тика",
    "де+нег": "де+нег",
    "ме+сяц": "ме+сяц",
    "путеше+ствовать": "путеше+ствовать",
    "ма+йские": "ма+йские",
    "пра+здники": "пра+здники",
    "вызыва+ть": "вызыва+ть",
    "мура+шки": "мура+шки",
    "мар+кер": "мар+кер",
    "и+стинности": "и+стинности",
    "равноду+шной": "равноду+шной",
    "благода+рность": "благода+рность",
    "благода+рю": "благода+рю",
    "топ+ливо": "топ+ливо",
    "повод+ов": "повод+ов",
    "спаси+бо": "спаси+бо",
    "ме+лочи": "ме+лочи",
    "попро+буй": "попро+буй",
    "прожи+ть": "прожи+ть",
    "пого+ворим": "пого+ворим",
}

# Известные метки — только они превращаются в SSML. Остальные [...] в тексте
# считаются служебными подсказками и удаляются беззвучно.
KNOWN_LABELS = (
    "МУЗЫКА", "ПАУЗА", "ТИШИНА", "ШЁПОТ", "ВДОХ", "ВЫДОХ",
    "ВДОХГЛУБ", "ФОНОМ",
)


def apply_accents(text: str) -> str:
    """Расставляет «+» по словарю. Регистр и границы слова."""
    out = text
    for word, fixed in ACCENTS.items():
        # Игнорируем регистр, но сохраняем регистр оригинала через re.sub
        pattern = re.compile(re.escape(word), re.IGNORECASE)
        # Заменяем без потери регистра первой буквы
        def _repl(m: re.Match) -> str:
            return m.group(0)[0] + fixed[1:] if m.group(0)[0].isupper() else fixed
        out = pattern.sub(_repl, out)
    return out


def parse_meta(m: re.Match) -> str:
    """Превращаем [МЕТКА:параметр] в SSML или пропускаем."""
    label = m.group(1).upper()
    value = m.group(2).strip()

    if label in ("МУЗЫКА", "ФОНОМ"):
        return ""
    if label in ("ПАУЗА", "ТИШИНА"):
        # Yandex SpeechKit НЕ принимает дробные секунды (0.5s → HTTP 400).
        # Поддерживаются только целые секунды (1s, 2s) или миллисекунды (500ms).
        # Конвертируем «0.5s» → «500ms», «1.5s» → «1500ms», «2s» → «2s».
        sec = value.replace("секунд", "").replace("секунды", "").replace("секунда", "").replace("сек", "").strip()
        if not sec:
            sec = "1s"  # голый [Пауза] → 1 секунда
        elif sec.endswith("ms"):
            pass  # уже миллисекунды
        elif sec.endswith("s"):
            num_str = sec[:-1]
            try:
                ms = int(float(num_str) * 1000)
                # Yandex API: max break time = 5s. Клэмпим.
                ms = min(ms, 5000)
                # Если делится на 1000 ровно — оставляем секунды (читаемее)
                if ms % 1000 == 0:
                    sec = f"{ms // 1000}s"
                else:
                    sec = f"{ms}ms"
            except ValueError:
                sec = "1s"
        elif sec.isdigit():
            n = int(sec)
            n = min(n, 5)  # Yandex API: max break time = 5s. Клэмпим.
            sec = f"{n}s"
        elif " " in sec:
            num = re.search(r"\d+", sec)
            n = min(int(num.group()), 5) if num else 1
            sec = f"{n}s"
        else:
            sec = "1s"
        return f'<break time="{sec}"/>'
    if label == "ШЁПОТ":
        # Yandex не поддерживает <prosody> — ставим короткую паузу-маркер.
        if value in ("off", "OFF"):
            return '<break time="200ms"/>. '
        return '<break time="200ms"/>, '
    if label == "ВДОХ":
        return '<break time="300ms"/>'
    if label == "ВЫДОХ":
        return '<break time="300ms"/>'
    if label == "ВДОХГЛУБ":
        return '<break time="800ms"/>'
    return ""


META_RE = re.compile(
    r"\[(" + "|".join(KNOWN_LABELS) + r")\s*[:\s]\s*([^\]]*)\]",
    re.IGNORECASE,
)

# Любые [...] в тексте, которые НЕ являются известной меткой — мусор.
# Например: [Мягкая, спокойная музыка на фоне, 5 секунд, затем затихает]
ANY_BRACKETS_RE = re.compile(r"\[[^\]]*\]")


def clean_unknown_brackets(script: str) -> tuple[str, int]:
    """Удаляет из скрипта все [...]-подсказки, не являющиеся известными метками.
    Возвращает (чистый_текст, кол-во_удалённых).
    """
    known_spans = [(m.start(), m.end()) for m in META_RE.finditer(script)]
    known_set = set(known_spans)

    def _is_known(span_start: int, span_end: int) -> bool:
        for ks, ke in known_spans:
            if ks <= span_start and span_end <= ke:
                return True
        return False

    parts: list[str] = []
    last = 0
    removed = 0
    for m in ANY_BRACKETS_RE.finditer(script):
        if m.start() < last:
            continue
        if _is_known(m.start(), m.end()):
            continue
        # Неизвестная подсказка — вырезаем.
        parts.append(script[last:m.start()])
        last = m.end()
        removed += 1
    parts.append(script[last:])
    return "".join(parts), removed


def build_ssml(yaml_path: Path) -> str:
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    script: str = data.get("script", "")
    voice = data.get("voice", "jane")
    rate = data.get("ssml", {}).get("prosody", {}).get("rate", 0.9)
    pitch = data.get("ssml", {}).get("prosody", {}).get("pitch", 0)
    volume = data.get("ssml", {}).get("prosody", {}).get("volume", "medium")

    # Markdown-обвязка
    script = re.sub(r"^```\w*\n?", "", script)
    script = re.sub(r"\n?```\s*$", "", script)
    script = re.sub(r"\n---\s*$", "", script)

    # 1) Удаляем неизвестные [...] (музыкальные ремарки и т.п.)
    script, n_removed = clean_unknown_brackets(script)

    # 1.5) Кавычки-ёлочки «…» тормозят TTS на предлогах → заменяем на «…»
    # с пробелами, чтобы SpeechKit не «зажёвывал» соседние слова.
    n_quotes = script.count("«") + script.count("»")
    script = re.sub(r"«\s*", '"', script)
    script = re.sub(r"\s*»", '"', script)
    # Тире «–» (en-dash между словами) → короткая пауза-точка
    # для естественной интонации. Дефис «-» оставляем как есть.
    script = re.sub(r"\s–\s", " . ", script)
    if n_quotes:
        pass  # silenced for cp1252 stdout compatibility

    # 2) Расставляем ударения
    script = apply_accents(script)

    # 3) Заменяем известные метки на SSML
    parts: list[str] = []
    last_end = 0
    for m in META_RE.finditer(script):
        text = script[last_end:m.start()].strip()
        if text:
            parts.append(text)
        ssml = parse_meta(m)
        if ssml:
            parts.append(ssml)
        last_end = m.end()
    tail = script[last_end:].strip()
    if tail:
        parts.append(tail)

    body = "\n".join(parts)
    ssml_doc = f"""<speak>
{body}
</speak>"""
    return ssml_doc


def main() -> int:
    # Принудительно UTF-8 для Windows-консоли
    if sys.platform.startswith("win"):
        try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")
        except Exception:
            pass

    ap = argparse.ArgumentParser(description="YAML → SSML для Yandex SpeechKit")
    ap.add_argument("yaml", help="Путь к YAML-скрипту")
    ap.add_argument("--out", required=True, help="Путь к выходному SSML")
    args = ap.parse_args()

    yaml_path = Path(args.yaml)
    if not yaml_path.exists():
        print(f"[!] Файл не найден: {yaml_path}", file=sys.stderr)
        return 1

    ssml = build_ssml(yaml_path)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(ssml, encoding="utf-8")
    print(f"[+] SSML сохранён в {out} ({len(ssml)} символов)")
    print("\n--- SSML preview (первые 800 символов) ---")
    print(ssml[:800])
    return 0


if __name__ == "__main__":
    sys.exit(main())
