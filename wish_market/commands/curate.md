# /curate <sphere>
Генерирует черновик 15–20 желаний для указанной сферы через YandexGPT-lite.

**Использование:** `/curate health` или `/curate finance`

**Что делает:**
1. Загружает `data/spheres/<sphere>.yaml`
2. Формирует промпт с подсферами и привязанными книгами WL
3. Вызывает `python scripts/curate_wishes.py --sphere=<sphere>`
4. Сохраняет результат в `data/library/_draft-<sphere>.md`
5. Показывает таблицу в чате для ревью

**Алгоритм:** см. `SKILL.md` → «Алгоритм /curate»

**Следующие шаги:**
- Пользователь ревьюит markdown, оставляет правки
- `/merge` — слить правки в `wishes_final.json`
