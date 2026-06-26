"""Собирает все 10 финальных текстов в один md-файл для просмотра."""
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


def humanize(s: str) -> str:
    """Превращаем технические теги в человеческое описание."""
    s = re.sub(r"\[ВДОХГЛУБ\]", "\n  [ВДОХ] (глубокий)\n", s)
    s = re.sub(r"\[ВДОХ\]", "\n  [ВДОХ]\n", s)
    s = re.sub(r"\[ШЁПОТ:(\d+)%\]", r"\n  [шёпот \1%]\n", s)
    s = re.sub(r"\[ШЁПОТ:off\]", "\n  [обычный голос]\n", s)
    s = re.sub(r"\[ПАУЗА:([\d.]+)s\]", r"\n  [пауза \1s]\n", s)
    s = re.sub(r"\[ПАУЗА:(\d+)ms\]", r"\n  [пауза \1ms]\n", s)
    s = re.sub(r"\[МУЗЫКА:([^\]]+)\]", r"\n  [музыка: \1]\n", s)
    s = re.sub(r"\[ТИШИНА:([^\]]+)\]", r"\n  [тишина: \1]\n", s)
    # Схлопываем множественные пустые строки
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


def main() -> int:
    lines = [
        "# Все 10 текстов для озвучки (финальная версия)",
        "",
        "Файл собран из `data/library/*.yaml` — это то, что отдаётся в TTS",
        "после шаблона `intro_outro` + YandexGPT (lively).",
        "",
        "Условные обозначения:",
        "- `[ВДОХ]` — техническая вставка вдоха (для естественности)",
        "- `[пауза 1s]` — пауза 1 секунда (для ритма)",
        "- `[шёпот 30%]` — тихий голос, доверительно",
        "- `[обычный голос]` — выход из шёпота",
        "",
        "---",
        "",
    ]

    for i, slug in enumerate(SLUGS, 1):
        p = Path(f"data/library/{slug}.yaml")
        if not p.exists():
            continue
        with open(p, "r", encoding="utf-8") as f:
            doc = yaml.safe_load(f)
        title = doc.get("title", slug)
        body = humanize(doc.get("script", ""))
        chars = len(doc.get("script", ""))

        lines.append(f"## Трек #{i}. {title}")
        lines.append(f"**slug:** `{slug}` · **{chars} символов** · ~{chars // 14} сек")
        lines.append("")
        lines.append(body)
        lines.append("")
        lines.append("---")
        lines.append("")

    out = Path("tmp/library/ALL_TEXTS.md")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines), encoding="utf-8")

    print(f"[+] {out}  ({out.stat().st_size:,} байт, {len(lines):,} строк)")
    print(f"[*] Файлов: {len(SLUGS)}")
    for i, slug in enumerate(SLUGS, 1):
        p = Path(f"data/library/{slug}.yaml")
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                doc = yaml.safe_load(f)
            chars = len(doc.get("script", ""))
            print(f"  #{i:2d}  {slug:48s}  {chars:5d} chars  ~{chars // 14} сек")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
