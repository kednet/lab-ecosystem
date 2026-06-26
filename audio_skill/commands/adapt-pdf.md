# /adapt-pdf <path>

Импорт скриптов из PDF в Audio Skill.

## Использование

```bash
# Только посмотреть, какие скрипты в PDF:
/adapt-pdf "C:/Users/kfigh/Downloads/Скрипты для аудио.pdf" --list

# Адаптировать все 10 скриптов (долго, ~5 мин через LLM):
/adapt-pdf "C:/Users/kfigh/Downloads/Скрипты для аудио.pdf" --all

# Один скрипт (быстро, ~30 сек):
/adapt-pdf "C:/Users/kfigh/Downloads/Скрипты для аудио.pdf" --script-id=1
# → data/library/_draft-zolotye-pravila.yaml
# → LLM-адаптер (через prompts/affirm-adapt.md)
# → data/library/zolotye-pravila.yaml
```

## Флаги

- `--script-id=N` — только один скрипт
- `--all` — все скрипты
- `--list` — только список без парсинга
- `--provider=claude|yandex|gigachat` — LLM-провайдер (по умолчанию claude)
- `--tone=warm_mentor|i_affirmation|we_journey|instructor` — тон (по умолчанию warm_mentor)
- `--remove-concrete-examples` — убрать «100 тысяч к марту 2027», «в Париж на майские»
- `--add-whisper` — обернуть интро/аутро в шёпот

## Алгоритм

1. **PDF parse** — `python scripts/pdf_parse.py <path> --script-id=N --out-dir=data/library`.
   Создаёт `data/library/_draft-<slug>.yaml` (черновик).
2. **LLM adapt** — `python scripts/llm_adapt.py data/library/_draft-<slug>.yaml --provider=claude --remove-concrete-examples --add-whisper --out=data/library/<slug>.yaml`.
3. **Validate** — `python scripts/llm_adapt.py` валидирует финальный YAML (обязательные поля, slug, длительность).
4. **Show summary** — вывести карточку: title, voice, background, duration, шёпот да/нет, конкретные примеры удалены да/нет.

## Следующий шаг

```bash
/preview-audio zolotye-pravila    # SSML + dry-run TTS (Phase 2)
/publish-audio zolotye-pravila    # полный цикл
```

## Известные ограничения (Phase 1)

- LLM-адаптер пока работает как **заглушка** (простые регулярки). Реальный LLM-вызов в Phase 2.
- Парсер ожидает формат «### Скрипт №N. „Название" (N минут)» + строку «Зона: ... | Жанр: ...» после заголовка.
- Если в PDF другая структура заголовков — нужно править `SCRIPT_HEADER_RE` и `META_LINE_RE` в `pdf_parse.py`.
