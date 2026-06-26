"""
Sanity-test для micro_cta: пропускает YAML-скрипт через adapt_yaml (без LLM)
и печатает результат. Используется для пилота — проверить, что блок micro_cta
реально встраивается в script перед outro.

Usage:
    python scripts/test_micro_cta.py data/library/<slug>.yaml
"""
from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import yaml

from scripts.llm_adapt import adapt_yaml  # noqa: E402


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python test_micro_cta.py <yaml>")
        return 1

    yaml_path = Path(sys.argv[1])
    if not yaml_path.exists():
        print(f"[!] Файл не найден: {yaml_path}")
        return 1

    draft = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    # Не требуем _draft — это финальный скрипт
    draft["_draft"] = True

    print(f"[*] Поля micro_cta в draft:")
    print(f"    micro_cta_question: {draft.get('micro_cta_question', '—')!r}")
    print(f"    micro_cta_url:      {draft.get('micro_cta_url', '—')!r}")

    final = adapt_yaml(
        draft,
        provider="stub",  # без LLM
        voice=draft.get("voice", "alena"),
        tone=draft.get("tone", "warm_mentor"),
        style="lively",
        remove_concrete=True,
        add_whisper=True,
        template="intro_outro",
    )

    print(f"\n[*] Финальный script ({len(final['script'])} chars):\n")
    print("=" * 60)
    print(final["script"])
    print("=" * 60)

    # Проверки
    script = final["script"]
    checks = [
        ("intro (Здравствуй)", "Здравствуй" in script),
        ("outro (Продолжай экспериментировать)", "Продолжай экспериментировать" in script),
        ("micro_cta (Мой вопрос к тебе)", "Мой вопрос к тебе" in script),
        ("micro_cta (URL)", "/my-experiment/" in script),
        ("micro_cta вставлен ПЕРЕД outro (вдхглуб)",
            script.find("Мой вопрос к тебе") < script.find("[ВДОХГЛУБ]")),
    ]
    print("\n[*] Проверки:")
    for name, ok in checks:
        print(f"    {'✅' if ok else '❌'} {name}")
    return 0 if all(ok for _, ok in checks) else 2


if __name__ == "__main__":
    sys.exit(main())
