#!/usr/bin/env python3
"""
wordstat_playwright.py — авторизованный сбор частотностей через Яндекс.Вордстат.

Использует Playwright (headless=False, чтобы было видно авторизацию).
Пользователь логинится в Яндекс ID в браузере Playwright, сессия сохраняется
в cookies. Повторные запуски используют ту же сессию.

Использование:
    python wordstat_playwright.py --input drafts/keywords-2026-06.md
    python wordstat_playwright.py --input drafts/keywords.md --limit 25 --rate-limit 5
    python wordstat_playwright.py --input drafts/keywords.md --anonymous
    python wordstat_playwright.py --input drafts/keywords.md --headless
"""

import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Зависимости Playwright (опциональны — нужны только при запуске)
try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False


WORDSTAT_URL = "https://wordstat.yandex.ru/"


# === ЧТЕНИЕ ЧЕРНОВИКА ===

def read_queries_from_draft(input_path):
    """
    Читает фразы из черновика. Поддерживает 2 формата:
    1) Markdown-таблица: | <число> | <фраза> | ... |
    2) Простой список: 1. <фраза> / - <фраза> / <фраза>

    Приоритет: секция `## ТОП-N для парсинга через Wordstat` —
    берём фразы оттуда (обычно 20-30 штук). Если её нет — берём
    все фразы из таблиц.
    """
    text = Path(input_path).read_text(encoding="utf-8")

    # 1) Ищем секцию "## ТОП-N для парсинга через Wordstat"
    top_section_match = re.search(
        r"##\s*ТОП[\-\d\s]*для парсинга через Wordstat\s*\n(.+?)(?=\n##|\Z)",
        text,
        re.DOTALL | re.IGNORECASE,
    )

    queries = []

    if top_section_match:
        # Берём фразы из нумерованного списка после этой секции
        top_section = top_section_match.group(1)
        for line in top_section.split("\n"):
            # Убираем нумерацию "1. " / "2. " / "- " / "* "
            cleaned = re.sub(r"^\s*(\d+[\.\)]\s*|[\-\*]\s*)+", "", line).strip()
            if cleaned and not cleaned.startswith("(") and not cleaned.startswith("Беру"):
                queries.append(cleaned)
    else:
        # 2) Fallback: парсим markdown-таблицы
        for row_match in re.finditer(
            r"\|\s*(\d+)\s*\|\s*([^|]+?)\s*\|", text
        ):
            phrase = row_match.group(2).strip()
            if phrase and not phrase.startswith("---") and "Фраза" not in phrase:
                queries.append(phrase)

    # Убираем дубли, сохраняя порядок
    seen = set()
    unique = []
    for q in queries:
        q_lower = q.lower().strip()
        if q_lower and q_lower not in seen:
            seen.add(q_lower)
            unique.append(q)

    return unique


# === ПАРСИНГ РЕЗУЛЬТАТОВ WORDSTAT ===

def parse_frequency_from_page(page, query=None):
    """
    Извлекает из открытой страницы Вордстата:
    - общее число запросов/мес
    - топ-3 связанных запросов

    Актуальная вёрстка wordstat.yandex.ru (13.06.2026) — после ввода фразы +
    Enter страница показывает блок "Общее число запросов" с фразой и числом,
    далее таблицу "Запросы со словами / Число запросов" с топ-связями.

    Пример реального inner_text:
        Общее число запросов
        медитации онлайн
        за 13.05.2026 – 11.06.2026: 14 556
        ...
        Запросы со  Число
        словами    запросов
        медитации онлайн    14 556
        медитации слушать онлайн    12 246
        медитации онлайн бесплатно    8 679
    """
    result = {
        "frequency": None,
        "related": [],
        "raw_text": None,
    }

    try:
        # Ждём загрузки результатов: сначала пробуем networkidle (быстро),
        # но он часто не срабатывает на wordstat — не критично.
        try:
            page.wait_for_load_state("networkidle", timeout=4000)
        except PlaywrightTimeout:
            pass

        # Доп. пауза, чтобы динамический контент отрисовался
        time.sleep(2)

        # Получаем весь видимый текст страницы
        body_text = page.inner_text("body")
        result["raw_text"] = body_text[:5000]

        # === СТРАТЕГИЯ 1 (точная): ищем строку вида
        #     "за ДД.ММ.ГГГГ – ДД.ММ.ГГГГ: 14 556"
        #     Это число стоит прямо под нашей фразой в блоке "Общее число запросов".
        m = re.search(
            r"за\s+\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}\s*[–\-—]\s*\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}[:\s]+(\d{1,3}(?:\s\d{3})+|\d{1,7})",
            body_text,
        )
        if m:
            result["frequency"] = int(re.sub(r"\s+", "", m.group(1)))

        # === СТРАТЕГИЯ 2: ищем паттерн "<фраза> ... <число>" в первых 2к символов
        #     (где как раз лежит блок "Общее число запросов")
        if not result["frequency"] and query:
            head = body_text[:2500]
            esc = re.escape(query)
            m2 = re.search(
                esc + r"\s*\n+\s*за\s+\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}\s*[–\-—]\s*\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}[:\s]+(\d{1,3}(?:\s\d{3})+|\d{1,7})",
                head,
                flags=re.IGNORECASE,
            )
            if m2:
                result["frequency"] = int(re.sub(r"\s+", "", m2.group(1)))

        # === СТРАТЕГИЯ 3 (fallback): первое "большое" число в первых 2к символов
        #     (где точно лежит результат для текущей фразы).
        if not result["frequency"]:
            head = body_text[:2500]
            for num_str in re.findall(r"(\d{1,3}(?:\s\d{3})+|\d{4,7})", head):
                num = int(re.sub(r"\s+", "", num_str))
                if 10 <= num <= 10_000_000:
                    result["frequency"] = num
                    break

        # === СВЯЗАННЫЕ: ищем таблицу "Запросы со словами / Число запросов"
        #     Это секция ПОСЛЕ первой строки с числом. Парсим пары: "фраза\tчисло".
        if result["frequency"]:
            # Берём текст ПОСЛЕ первой строки вида "фраза\tчисло" (это наш запрос,
            # от него идёт список связанных).
            anchor_pattern = re.compile(
                r"за\s+\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}\s*[–\-—]\s*\d{1,2}[.\-]\d{1,2}[.\-]\d{2,4}[:\s]+\d",
            )
            anchor = anchor_pattern.search(body_text)
            tail = body_text[anchor.end():] if anchor else body_text

            # Ищем строки вида "фраза\t14 556" или "фраза\n14 556"
            # Фраза — это текст до цифр, число — 1+ группа цифр с разделителями.
            row_pattern = re.compile(
                r"([а-яёa-z][а-яёa-z0-9 \-\.]{2,80}?)\s+(\d{1,3}(?:\s\d{3})+|\d{1,7})\b",
                re.IGNORECASE,
            )
            seen_queries = {query.lower().strip()} if query else set()
            for m3 in row_pattern.finditer(tail):
                phrase = re.sub(r"\s+", " ", m3.group(1)).strip()
                if not phrase or len(phrase) < 3:
                    continue
                # Отсеиваем заголовки таблиц и служебные слова
                if any(skip in phrase.lower() for skip in [
                    "запросы со", "число запросов", "история запросов",
                    "регионы", "сайты по", "похожие", "общее число",
                ]):
                    continue
                try:
                    num = int(re.sub(r"\s+", "", m3.group(2)))
                except ValueError:
                    continue
                if num < 1:
                    continue
                key = phrase.lower()
                if key in seen_queries:
                    continue
                seen_queries.add(key)
                result["related"].append({"query": phrase, "frequency": num})
                if len(result["related"]) >= 3:
                    break

    except PlaywrightTimeout:
        print(f"   ⚠️ Таймаут при парсинге страницы", flush=True)
    except Exception as e:
        print(f"   ⚠️ Ошибка парсинга: {e}", flush=True)

    return result


# === ГЛАВНАЯ ЛОГИКА СБОРА ===

def is_login_page(page):
    """Проверяет, не на странице ли логина Yandex ID."""
    try:
        url = page.url.lower()
        if "passport.yandex" in url or "sso.passport" in url or "auth.yandex" in url:
            return True
        # Проверяем по содержимому
        try:
            body = page.inner_text("body", timeout=2000)
            login_markers = ["Введите ваш телефон", "Войти с Яндекс ID", "Yandex ID", "войдите в аккаунт"]
            if any(m.lower() in body.lower() for m in login_markers):
                return True
        except Exception:
            pass
        return False
    except Exception:
        return False


def collect_queries(page, queries, rate_limit, output_path, period_days=30, region="Россия"):
    """
    Поочерёдно вводит каждый запрос в Вордстат, парсит результат.
    Возвращает список dict с полями query, frequency, related, timestamp.
    """
    results = []
    total = len(queries)
    output_path = Path(output_path)
    reauth_flag = output_path / "REAUTH_NEEDED"  # файл для запроса повторной авторизации

    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/{total}] 🔍 Запрос: «{query}»", flush=True)

        try:
            # === ПРОВЕРКА: не на странице ли логина? ===
            if is_login_page(page):
                print(f"   🔐 Обнаружена страница логина. Жду файл {reauth_flag.name}...", flush=True)
                if reauth_flag.exists():
                    reauth_flag.unlink()
                waited = 0
                while is_login_page(page):
                    if reauth_flag.exists():
                        print(f"   ✅ Авторизация подтверждена. Продолжаю...", flush=True)
                        reauth_flag.unlink()
                        break
                    time.sleep(2)
                    waited += 2
                    if waited % 30 == 0:
                        print(f"   ...всё ещё жду авторизацию ({waited // 60} мин)", flush=True)

            # НЕ переходим на wordstat через goto, если уже там залогинены —
            # это часто сбрасывает сессию (SSO редирект). Вместо этого
            # чистим поле ввода и вводим новый запрос.
            url_lower = page.url.lower()
            already_on_wordstat = "wordstat.yandex" in url_lower
            if not already_on_wordstat:
                # Возможно Яндекс ещё дореливает нас после авторизации. Подождём.
                for _wait in range(5):
                    if "wordstat.yandex" in page.url.lower():
                        already_on_wordstat = True
                        break
                    time.sleep(1)
                if not already_on_wordstat:
                    # Пробуем аккуратный goto через "commit" (не ждём domcontentloaded,
                    # который провоцирует конфликт навигации при активном SSO).
                    try:
                        page.goto(WORDSTAT_URL, wait_until="commit", timeout=20000)
                        time.sleep(2)
                    except Exception as e:
                        # Если всё равно interrupted — пробуем сразу парсить
                        # (на случай если на странице уже нужные данные).
                        print(f"   ⚠️ goto конфликтует с SSO: {e}", flush=True)
                        time.sleep(2)

            # === ЕЩЁ РАЗ ПРОВЕРКА после goto (если goto был) ===
            if is_login_page(page):
                print(f"   🔐 После перехода — снова логин. Пропускаю фразу, жду авторизацию...", flush=True)
                if reauth_flag.exists():
                    reauth_flag.unlink()
                # Записываем фразу как no_data, продолжаем
                results.append({
                    "query": query,
                    "frequency": None,
                    "related": [],
                    "no_data": True,
                    "error": "auth_required",
                    "period": f"{period_days} дней",
                    "region": region,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                continue

            # Находим поле ввода. Несколько вариантов селекторов (Яндекс меняет разметку).
            # Актуальный селектор (13.06.2026): input.textinput__control с placeholder
            # "Введите слово или словосочетание". Оставляем fallback-варианты.
            input_selectors = [
                "input.textinput__control",                              # актуальный
                "input[placeholder*='Введите слово']",                   # по placeholder
                "input[placeholder*='Введите слова']",                   # вариант
                "input[name='text']",                                    # legacy
                "input[placeholder*='запрос']",
                "input[placeholder*='Запрос']",
                "input.input__control",
                "input[type='search']",
                "textarea[name='text']",
            ]
            input_box = None
            for selector in input_selectors:
                try:
                    loc = page.locator(selector)
                    if loc.count() > 0 and loc.first.is_visible():
                        input_box = loc.first
                        break
                except Exception:
                    continue

            if not input_box or input_box.count() == 0:
                print(f"   ⚠️ Не нашли поле ввода. Пробуем Ctrl+A → type...")
                page.keyboard.press("Control+a")
                page.keyboard.type(query, delay=20)
            else:
                input_box.click()
                input_box.fill("")
                input_box.fill(query)
                page.keyboard.press("Enter")

            # Ждём загрузки результатов (мягко — wordstat часто не достигает networkidle)
            try:
                page.wait_for_load_state("networkidle", timeout=4000)
            except PlaywrightTimeout:
                pass
            time.sleep(1)

            # Парсим
            parsed = parse_frequency_from_page(page, query=query)

            # Проверяем на капчу
            if "captcha" in (parsed.get("raw_text") or "").lower() or "робот" in (parsed.get("raw_text") or "").lower():
                print(f"   🚨 КАПЧА! Пауза 30 сек...")
                time.sleep(30)
                # Повторная попытка
                parsed = parse_frequency_from_page(page, query=query)

            # Если всё ещё нет результата — флаг no_data
            if not parsed["frequency"]:
                parsed["no_data"] = True
                print(f"   ⚠️ Не удалось извлечь частотность")
            else:
                print(f"   ✅ {parsed['frequency']:,} показов/мес")
                if parsed["related"]:
                    for r in parsed["related"]:
                        print(f"      → «{r['query']}» {r['frequency']:,}")

            result = {
                "query": query,
                "frequency": parsed["frequency"],
                "related": parsed["related"],
                "no_data": parsed.get("no_data", False),
                "period": f"{period_days} дней",
                "region": region,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
            results.append(result)

        except Exception as e:
            print(f"   ❌ Ошибка: {e}")
            results.append({
                "query": query,
                "frequency": None,
                "related": [],
                "no_data": True,
                "error": str(e),
                "period": f"{period_days} дней",
                "region": region,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

        # Rate limit между запросами
        if i < total:
            sleep_time = rate_limit + (i % 3)  # 5-7 сек с разбросом
            print(f"   ⏳ Пауза {sleep_time} сек...")
            time.sleep(sleep_time)

    return results


# === СОХРАНЕНИЕ ===

def save_results(results, output_path, input_path):
    """Сохраняет результаты в JSON + промежуточный лог."""
    output_path = Path(output_path)
    output_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    json_path = output_path / f"raw_{timestamp}.json"
    latest_path = output_path / "raw_latest.json"

    payload = {
        "source": "wordstat.yandex.ru",
        "collected_at": datetime.now(timezone.utc).isoformat(),
        "input_file": str(input_path),
        "queries_count": len(results),
        "queries_with_data": sum(1 for r in results if r.get("frequency") is not None),
        "queries_no_data": sum(1 for r in results if r.get("no_data")),
        "results": results,
    }

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    # Копия с фиксированным именем для удобства
    with open(latest_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"\n💾 Сохранено: {json_path}")
    print(f"💾 Копия:     {latest_path}")
    return json_path


# === MAIN ===

def main():
    # Windows-консоль по умолчанию использует cp1251/cp1252 — переключаем stdout/stderr на UTF-8,
    # иначе любой эмодзи (📖 ✅ ❌ и т.п.) роняет скрипт при записи в файл лога.
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is not None and hasattr(stream, "reconfigure"):
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except Exception:
                pass

    parser = argparse.ArgumentParser(
        description="Авторизованный сбор частотностей через Яндекс.Вордстат (Playwright)"
    )
    parser.add_argument(
        "--input", "-i", required=True,
        help="Путь к черновику (markdown) со списком фраз"
    )
    parser.add_argument(
        "--output", "-o", default="data/wordstat-output",
        help="Папка для сохранения результатов (по умолчанию data/wordstat-output)"
    )
    parser.add_argument(
        "--limit", "-l", type=int, default=None,
        help="Максимум фраз для парсинга (по умолчанию — все из черновика)"
    )
    parser.add_argument(
        "--rate-limit", type=int, default=5,
        help="Пауза между запросами в секундах (по умолчанию 5)"
    )
    parser.add_argument(
        "--period", type=int, default=30,
        help="Период в днях для истории (по умолчанию 30)"
    )
    parser.add_argument(
        "--region", default="Россия",
        help="Регион для фильтра (по умолчанию Россия)"
    )
    parser.add_argument(
        "--headless", action="store_true",
        help="Запустить браузер в headless-режиме. ⚠️ Работает ТОЛЬКО с --anonymous. "
             "Для авторизованного сбора нужен обычный режим (по умолчанию)."
    )
    parser.add_argument(
        "--anonymous", action="store_true",
        help="Парсить без авторизации. ⚠️ Вордстат редиректит на логин — данных не будет! "
             "Только для отладки селекторов. По умолчанию — авторизованный сбор."
    )
    parser.add_argument(
        "--debug-one", metavar="QUERY",
        help="Отладочный режим: ввести ОДНУ фразу, сохранить inner_text + HTML "
             "в output/debug-*.txt, сделать скриншот, НЕ продолжать сбор."
    )

    args = parser.parse_args()

    # Проверки
    if not PLAYWRIGHT_AVAILABLE:
        print("❌ Playwright не установлен.")
        print("   Установи: pip install playwright && playwright install chromium")
        sys.exit(1)

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"❌ Файл не найден: {input_path}")
        sys.exit(1)

    # Читаем фразы
    print(f"📖 Читаю черновик: {input_path}")
    queries = read_queries_from_draft(input_path)
    print(f"   Найдено фраз: {len(queries)}")

    if args.limit and args.limit < len(queries):
        queries = queries[:args.limit]
        print(f"   Ограничено до: {len(queries)} (--limit)")

    if not queries:
        print("❌ В черновике не найдено фраз для парсинга.")
        sys.exit(1)

    # Запускаем Playwright
    print(f"\n🚀 Запускаю Playwright (headless={args.headless})...")

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=args.headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 800},
        )
        page = context.new_page()

        # Открываем Вордстат для возможной авторизации
        print(f"🌐 Открываю {WORDSTAT_URL}")
        page.goto(WORDSTAT_URL, wait_until="domcontentloaded")

        if not args.anonymous and not args.headless:
            print("\n" + "="*60)
            print("🔐 АВТОРИЗАЦИЯ")
            print("="*60)
            print("Вордстат требует логин в Яндекс ID для выдачи данных.")
            print("Сейчас откроется окно браузера — залогинься под своим аккаунтом,")
            print("дождись загрузки wordstat.yandex.ru.")
            print("(Логин не сохраняется на диск — сессия живёт в cookies браузера Playwright)")
            print("="*60)
            ready_flag = Path(args.output) / "READY_TO_GO"
            ready_flag.parent.mkdir(parents=True, exist_ok=True)
            # Если файл уже есть (повторный запуск) — удаляем
            if ready_flag.exists():
                ready_flag.unlink()
            print(f"\n👉 Когда залогинишься и увидишь Вордстат — создай файл-флаг:")
            print(f"   {ready_flag}")
            print(f"   Например: touch \"{ready_flag}\" (в Git Bash)")
            print(f"   Или просто создай пустой файл в этой папке.")
            print(f"\n⏳ Скрипт ждёт появления файла (проверка каждые 2 сек)...")
            waited = 0
            while not ready_flag.exists():
                time.sleep(2)
                waited += 2
                if waited % 30 == 0:
                    print(f"   ...всё ещё жду ({waited // 60} мин {waited % 60} сек)")
            print(f"✅ Файл найден! Начинаю сбор...")
            try:
                ready_flag.unlink()  # убираем на следующий запуск
            except Exception:
                pass

            # Даём странице устаканиться после клика «Готово».
            # Если сессия в cookies, Яндекс автоматически перенаправит нас
            # обратно на wordstat.yandex.ru — никаких goto не нужно.
            print(f"⏳ Жду 3 сек, пока страница устаканится...")
            time.sleep(3)
            print(f"   Текущий URL: {page.url}")
        elif not args.anonymous and args.headless:
            print("❌ Headless-режим несовместим с авторизацией (не видно окна для логина).")
            print("   Запусти БЕЗ --headless (или используй --anonymous для отладки).")
            browser.close()
            sys.exit(1)
        elif args.anonymous:
            print("⚠️ АНОНИМНЫЙ РЕЖИМ")
            print("   Вордстат редиректит на passport.yandex.ru без сессии.")
            print("   Данных не будет — этот режим только для отладки селекторов.")
            print("   Для реального сбора запусти БЕЗ --anonymous и БЕЗ --headless.")
            time.sleep(3)  # даём время прочитать

        # Собираем данные
        print(f"\n🔄 Начинаю сбор {len(queries)} запросов...")
        print(f"   Период: {args.period} дней, регион: {args.region}")
        print(f"   Rate limit: {args.rate_limit} сек между запросами")
        print(f"   Ожидаемое время: ~{len(queries) * args.rate_limit // 60} мин")

        # === Отладочный режим: одна фраза, максимум логов ===
        if args.debug_one:
            dbg_query = args.debug_one
            out_dir = Path(args.output)
            out_dir.mkdir(parents=True, exist_ok=True)
            print(f"\n🪛 DEBUG-ONE: ввожу «{dbg_query}» и сохраняю всё подряд...")

            # Проверяем, что мы на wordstat
            if "wordstat.yandex" not in page.url.lower():
                print(f"   Текущий URL не wordstat: {page.url}")
                print(f"   Пробую goto через commit...")
                try:
                    page.goto(WORDSTAT_URL, wait_until="commit", timeout=20000)
                    time.sleep(3)
                except Exception as e:
                    print(f"   goto interrupted: {e}")
                    time.sleep(3)
            print(f"   URL перед вводом: {page.url}")

            # Находим поле ввода
            input_box = None
            for selector in [
                "input.textinput__control",
                "input[placeholder*='Введите слово']",
                "input[placeholder*='Введите слова']",
                "input[name='text']",
            ]:
                try:
                    loc = page.locator(selector)
                    if loc.count() > 0 and loc.first.is_visible():
                        input_box = loc.first
                        print(f"   Нашли поле ввода по селектору: {selector}")
                        break
                except Exception:
                    continue
            if not input_box:
                print("   ❌ Поле ввода НЕ найдено. Селектор устарел?")
                page.screenshot(path=str(out_dir / "debug-no-input.png"))
                browser.close()
                sys.exit(1)

            input_box.click()
            input_box.fill("")
            input_box.fill(dbg_query)
            print(f"   Ввёл «{dbg_query}», нажимаю Enter...")
            page.keyboard.press("Enter")
            time.sleep(5)  # ждём результат подольше

            # Сохраняем inner_text и HTML
            try:
                txt = page.inner_text("body")
                (out_dir / "debug-inner_text.txt").write_text(txt, encoding="utf-8")
                print(f"   inner_text: {len(txt)} символов → {out_dir/'debug-inner_text.txt'}")
                print(f"   --- первые 800 символов ---")
                print(txt[:800])
                print(f"   --- конец превью ---")
            except Exception as e:
                print(f"   ⚠️ inner_text: {e}")

            try:
                html = page.content()
                (out_dir / "debug-page.html").write_text(html, encoding="utf-8")
                print(f"   HTML: {len(html)} символов → {out_dir/'debug-page.html'}")
            except Exception as e:
                print(f"   ⚠️ page.content: {e}")

            try:
                page.screenshot(path=str(out_dir / "debug-screenshot.png"), full_page=True)
                print(f"   Скриншот → {out_dir/'debug-screenshot.png'}")
            except Exception as e:
                print(f"   ⚠️ screenshot: {e}")

            print(f"\n   URL после ввода: {page.url}")
            print("   Готово. Открой файлы debug-* в папке output.")
            browser.close()
            sys.exit(0)

        # === Обычный сбор ===
        results = collect_queries(
            page, queries,
            rate_limit=args.rate_limit,
            output_path=args.output,
            period_days=args.period,
            region=args.region,
        )

        # Сохраняем
        json_path = save_results(results, args.output, input_path)

        browser.close()

    # Итоги
    with_data = sum(1 for r in results if r.get("frequency") is not None)
    no_data = sum(1 for r in results if r.get("no_data"))
    print(f"\n{'='*60}")
    print(f"📊 ИТОГО")
    print(f"   Всего запросов: {len(results)}")
    print(f"   С данными: {with_data}")
    print(f"   Без данных: {no_data}")
    print(f"   JSON: {json_path}")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
