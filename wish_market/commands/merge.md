# /merge
Сливает черновик + правки пользователя в финальный JSON.

**Использование:** `/merge health` или `/merge-all`

**Что делает:**
1. Берёт `data/library/_draft-<sphere>.md`
2. Парсит таблицу + секцию «Правки»
3. Применяет правки:
   - «N: заменить на X» → обновляет text
   - «N: удалить» → удаляет
   - «добавить: Y» → добавляет
4. Сохраняет в `data/library/wishes_final.json` (дописывает к существующему)

**Структура `wishes_final.json`:**
```json
{
  "version": "0.1",
  "generated_at": "2026-06-13T...",
  "wishes": [
    {
      "id": "uuid",
      "text": "...",
      "sphere": "здоровье",
      "description": "...",
      "source_book_id": null,
      "source_chapter": null,
      "is_ai_generated": true,
      "created_by": "curator",
      "is_active": true
    }
  ]
}
```
