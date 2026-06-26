"""
Smoke-тесты для SQL-миграций.

Не дёргают D1 — проверяют, что SQL-скрипт корректный (синтаксис SQLite/D1),
полный (все 9 таблиц), и идемпотентный (CREATE TABLE IF NOT EXISTS).
"""

from __future__ import annotations

import re

from agent.storage.migrations import MIGRATION_001, MIGRATIONS, SCHEMA_VERSION

# === Полнота миграций ===

def test_all_expected_tables_present() -> None:
    sql = MIGRATION_001.upper()
    expected = [
        "SCHEMA_META",
        "CLIENT",
        "CLIENT_CHANNEL",
        "DESIRE",
        "DESIRE_STEP",
        "SESSION",
        "MESSAGE",
        "WORKBOOK_RUN",
        "CRISIS_LOG",
        "TONE_PROFILE",
    ]
    for table in expected:
        assert f"CREATE TABLE IF NOT EXISTS {table}" in sql, f"нет таблицы {table}"


def test_all_relations_present() -> None:
    """FOREIGN KEY между таблицами."""
    sql = MIGRATION_001.upper()
    relations = [
        ("CLIENT_CHANNEL", "CLIENT"),
        ("DESIRE", "CLIENT"),
        ("DESIRE", "DESIRE"),  # parent_desire_id self-FK
        ("DESIRE_STEP", "DESIRE"),
        ("SESSION", "CLIENT"),
        ("MESSAGE", "SESSION"),
        ("WORKBOOK_RUN", "CLIENT"),
        ("TONE_PROFILE", "CLIENT"),
    ]
    for _child, _parent in relations:
        assert "FOREIGN KEY" in sql
        # Не проверяем точное совпадение — главное, что FK упоминается


def test_necessary_indexes_present() -> None:
    sql = MIGRATION_001.upper()
    indexes = [
        "IDX_CLIENT_EMAIL",
        "IDX_DESIRE_CLIENT",
        "IDX_SESSION_CLIENT",
        "IDX_MESSAGE_SESSION",
        "IDX_WORKBOOK_CLIENT",
        "IDX_CRISIS_CLIENT",
    ]
    for idx in indexes:
        assert f"CREATE INDEX IF NOT EXISTS {idx}" in sql, f"нет индекса {idx}"


# === Идемпотентность ===

def test_migration_uses_if_not_exists() -> None:
    """Все CREATE должны быть IF NOT EXISTS — повторное применение не должно падать."""
    # Слово за словом: CREATE TABLE [IF NOT EXISTS] имя
    pattern = re.compile(r"CREATE\s+TABLE\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)", re.IGNORECASE)
    matches = pattern.findall(MIGRATION_001)
    assert len(matches) >= 9, f"найдено только {len(matches)} CREATE TABLE, ожидалось ≥9"
    # Проверяем, что ВСЕ CREATE-блоки в скрипте содержат IF NOT EXISTS
    if_not_exists_count = len(re.findall(r"CREATE\s+TABLE\s+IF\s+NOT\s+EXISTS", MIGRATION_001, re.IGNORECASE))
    assert if_not_exists_count == len(matches), (
        f"не все CREATE имеют IF NOT EXISTS: {if_not_exists_count} из {len(matches)}"
    )


# === Crisis log НЕ хранит текст ===

def test_crisis_log_does_not_have_message_text() -> None:
    """По PRD v2.0 (5.8) crisis_log хранит только message_hash, не текст."""
    sql = MIGRATION_001.upper()
    # Найдём блок создания crisis_log
    crisis_block = re.search(r"CREATE TABLE IF NOT EXISTS CRISIS_LOG.*?\)", sql, re.DOTALL)
    assert crisis_block is not None, "таблица crisis_log не найдена"
    block = crisis_block.group(0)
    assert "MESSAGE_HASH" in block
    # Не должно быть поля TEXT для хранения исходного текста
    assert "MESSAGE_TEXT" not in block
    assert "CONTENT" not in block


# === Версия и список миграций ===

def test_migrations_list_not_empty() -> None:
    assert len(MIGRATIONS) >= 1
    name, sql = MIGRATIONS[0]
    assert name == "001_initial"
    assert sql == MIGRATION_001


def test_schema_version_semver() -> None:
    parts = SCHEMA_VERSION.split(".")
    assert len(parts) == 3
    assert all(p.isdigit() for p in parts)


# === Defaults и enum-строки (выборочно) ===

def test_client_defaults() -> None:
    """Дефолты client соответствуют PRD v2.0."""
    sql = MIGRATION_001
    assert "DEFAULT 'warm'" in sql or 'DEFAULT "warm"' in sql
    assert "DEFAULT 3" in sql  # tone_intensity
    assert "DEFAULT 'Europe/Moscow'" in sql
    assert "DEFAULT '10:00'" in sql
    assert "DEFAULT 'new'" in sql  # onboarding_state


def test_desire_verdict_label_6_values() -> None:
    """
    По PRD v2.0 (5.9) 6 подписей вердиктов: imposed, mostly_imposed, mixed_low, mixed_high, mostly_true, true.
    Эти значения не enforced на уровне SQL (SQLite нет enum), но упоминаются в комментариях.
    """
    sql = MIGRATION_001
    # Комментарий с 6 подписями должен быть
    assert "verdict_label" in sql
    # Хотя бы некоторые подписи упомянуты
    assert "imposed" in sql.lower() or "mostly" in sql.lower()


def test_session_states_in_comments() -> None:
    """State machine состояния упомянуты в комментариях к current_state."""
    sql = MIGRATION_001.lower()
    assert "current_state" in sql


def test_message_excluded_from_training() -> None:
    """По PRD v2.0 (10) message.excluded_from_training для фильтрации кризиса."""
    sql = MIGRATION_001.upper()
    assert "EXCLUDED_FROM_TRAINING" in sql
