"""
pending_store.py — хранилище pending-постов для модерации.

Посты, которые ждут одобрения в TG-админке, складываются в JSON-файлы
в tmp/private_pending/<uuid>.json. Когда бот-модератор берёт их в работу —
он читает, обновляет статус (pending/approved/rejected/edited) и удаляет.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

SKILL_ROOT = Path(__file__).resolve().parent.parent
PENDING_DIR = SKILL_ROOT / "tmp" / "private_pending"
PENDING_DIR.mkdir(parents=True, exist_ok=True)


def create(text: str, image_path: str | None, url: str, source_title: str) -> dict:
    """Создать pending-пост. Возвращает dict с uuid."""
    post_id = uuid.uuid4().hex[:12]
    payload = {
        "id": post_id,
        "status": "pending",          # pending | approved | rejected | edited
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_title": source_title,
        "text": text,
        "image_path": image_path,
        "url": url,
        "moderated_at": None,
        "moderated_message_id": None,  # ID сообщения бота с превью в личке
        "edited_text": None,           # если была правка
    }
    path = PENDING_DIR / f"{post_id}.json"
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def get(post_id: str) -> dict | None:
    p = PENDING_DIR / f"{post_id}.json"
    if not p.exists():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def update(post_id: str, **fields) -> dict | None:
    """Обновить поля в pending-посте."""
    p = PENDING_DIR / f"{post_id}.json"
    if not p.exists():
        return None
    payload = json.loads(p.read_text(encoding="utf-8"))
    payload.update(fields)
    payload["moderated_at"] = datetime.now(timezone.utc).isoformat()
    p.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return payload


def list_pending() -> list[dict]:
    out = []
    for p in sorted(PENDING_DIR.glob("*.json")):
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        if d.get("status") == "pending":
            out.append(d)
    return out


def delete(post_id: str) -> bool:
    p = PENDING_DIR / f"{post_id}.json"
    if p.exists():
        p.unlink()
        return True
    return False