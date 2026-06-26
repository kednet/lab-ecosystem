"""
State manager для audio_skill.

Идемпотентность через state/<slug>.json:
- Поля: status, created_at, ssml_path, voice_path, mixed_path, r2_url, page_path,
  deployed_at, live_url, channels_posted, channels_failed, error.
- CLI: list / show <slug> / reset <slug> / mark <slug> <field> <value>

Делегирует хранение в publisher_skill/scripts/state.py, чтобы схема была
единой по всем скиллам.

Использование:
    python scripts/state.py list
    python scripts/state.py show zolotye-pravila
    python scripts/state.py reset zolotye-pravila --force
    python scripts/state.py mark zolotye-pravila status published
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Пытаемся импортировать общий state manager
PUBLISHER_ROOT = Path(__file__).parent.parent.parent / "publisher_skill"
if PUBLISHER_ROOT.exists() and str(PUBLISHER_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PUBLISHER_ROOT / "scripts"))

try:
    # Если у publisher_skill есть универсальный state, используем его
    from state import StateManager, StateError  # type: ignore
    _USE_PUBLISHER = True
except ImportError:
    _USE_PUBLISHER = False

    class StateError(Exception):
        pass

    class StateManager:
        """Локальный state manager (fallback)."""

        def __init__(self, state_dir: Path):
            self.state_dir = Path(state_dir)
            self.state_dir.mkdir(parents=True, exist_ok=True)

        def _path(self, slug: str) -> Path:
            return self.state_dir / f"{slug}.json"

        def get(self, slug: str) -> dict:
            p = self._path(slug)
            if not p.exists():
                return {"slug": slug, "status": "draft"}
            return json.loads(p.read_text(encoding="utf-8"))

        def set(self, slug: str, **fields):
            current = self.get(slug)
            current.update(fields)
            current.setdefault("slug", slug)
            self._path(slug).write_text(
                json.dumps(current, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

        def reset(self, slug: str) -> None:
            p = self._path(slug)
            if p.exists():
                p.unlink()

        def list_all(self) -> list[dict]:
            return [
                json.loads(p.read_text(encoding="utf-8"))
                for p in self.state_dir.glob("*.json")
            ]


def _get_manager() -> StateManager:
    state_dir = Path(__file__).parent.parent / "state"
    return StateManager(state_dir)


def cmd_list() -> int:
    mgr = _get_manager()
    states = mgr.list_all()
    if not states:
        print("[*] Нет записей в state/")
        return 0
    print(f"[*] Найдено {len(states)} аудио:")
    for s in states:
        slug = s.get("slug", "?")
        status = s.get("status", "draft")
        title = s.get("title", "")
        duration = s.get("final_duration_sec", s.get("voice_duration_sec", ""))
        live = s.get("live_url", "")
        print(f"  {slug:30s}  {status:12s}  {title[:40]:40s}  "
              f"{duration if duration else '—':>5}с  {live}")
    return 0


def cmd_show(slug: str) -> int:
    mgr = _get_manager()
    s = mgr.get(slug)
    print(json.dumps(s, ensure_ascii=False, indent=2))
    return 0


def cmd_reset(slug: str, force: bool = False) -> int:
    if not force:
        confirm = input(f"Точно сбросить state для '{slug}'? [y/N]: ")
        if confirm.lower() != "y":
            print("[*] Отменено")
            return 0
    mgr = _get_manager()
    mgr.reset(slug)
    print(f"[+] state/{slug}.json удалён")
    return 0


def cmd_mark(slug: str, field: str, value: str) -> int:
    mgr = _get_manager()
    # Автоматически парсим JSON, если возможно
    try:
        parsed = json.loads(value)
    except (json.JSONDecodeError, TypeError):
        parsed = value
    mgr.set(slug, **{field: parsed})
    print(f"[+] {slug}.{field} = {parsed}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description="State manager для audio_skill")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("list", help="Показать все slug и статусы")

    p_show = sub.add_parser("show", help="Подробно по slug")
    p_show.add_argument("slug")

    p_reset = sub.add_parser("reset", help="Сбросить state slug")
    p_reset.add_argument("slug")
    p_reset.add_argument("--force", action="store_true", help="Без подтверждения")

    p_mark = sub.add_parser("mark", help="Установить поле в state")
    p_mark.add_argument("slug")
    p_mark.add_argument("field")
    p_mark.add_argument("value")

    args = ap.parse_args()

    if args.cmd == "list":
        return cmd_list()
    elif args.cmd == "show":
        return cmd_show(args.slug)
    elif args.cmd == "reset":
        return cmd_reset(args.slug, args.force)
    elif args.cmd == "mark":
        return cmd_mark(args.slug, args.field, args.value)
    return 0


if __name__ == "__main__":
    sys.exit(main())
