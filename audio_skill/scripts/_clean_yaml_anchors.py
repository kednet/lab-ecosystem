"""Чистим мусорные YAML-якоря ('script: |', 'script:', просто '|' в начале строки)
из блока script: у всех финальных YAML-файлов.

Также чистим пустые теги [ПАУЗА] без параметра.
"""
import re
import yaml
from pathlib import Path

SLUGS = [
    "zolotye-pravila-ispolneniya-zhelaniy",
    "chuvstvo-ispolnennogo-zhelaniya",
    "detskie-ustanovki-pro-dengi",
    "malenkie-shagi",
    "razreshenie-sebe",
    "tehnika-100-zhelaniy",
    "proschenie-sebya",
    "tehnika-zachem",
    "utrennee-namerenie",
    "rabota-s-vnutrennim-kritikom",
]


def clean(s: str) -> str:
    # 1. Вырезаем мусорный "script: |" / "script:" (YandexGPT иногда их вставляет в середину)
    s = re.sub(r"^\s*script:\s*\|\s*\n", "", s, flags=re.MULTILINE)
    s = re.sub(r"\n\s*script:\s*\|\s*\n", "\n", s)
    s = re.sub(r"\n\s*script:\s*\n", "\n", s)
    # 2. [ПАУЗА] без параметра → [ПАУЗА:0.5s]
    s = re.sub(r"\[ПАУЗА\](?![\d:])", "[ПАУЗА:0.5s]", s)
    # 3. Одиночный '|' в начале строки (видимо как разделитель)
    s = re.sub(r"^\|\s*\n", "", s, flags=re.MULTILINE)
    # 4. Литеральные backslash-n (на всякий случай)
    s = s.replace(chr(92) + "n", "\n")
    return s.strip()


def main() -> int:
    import io
    for slug in SLUGS:
        p = Path(f"data/library/{slug}.yaml")
        with open(p, "r", encoding="utf-8") as fh:
            d = yaml.safe_load(fh)
        s = d.get("script", "")
        n_pipes = s.count("|")
        n_anchor = s.count("script:")
        if n_pipes == 0 and n_anchor <= 1:  # 1 = само поле script: в yaml
            print(f"[=] {slug}: clean")
            continue
        s2 = clean(s)
        d["script"] = s2
        buf = io.StringIO()
        yaml.dump(d, buf, allow_unicode=True, sort_keys=False, default_flow_style=False, width=10000)
        p.write_text(buf.getvalue(), encoding="utf-8")
        print(f"[+] {slug}: pipes {n_pipes}→{s2.count('|')}, anchor {n_anchor}→{s2.count('script:')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
