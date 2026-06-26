# YandexART API reference

См. `sub-skills/yandex-art-api.md` для полной документации.

**Краткая сводка:**

- **Endpoint:** `POST https://llm.api.cloud.yandex.net/foundationModels/v1/imageGeneration_async`
- **Auth:** `Authorization: Api-Key <YANDEX_API_KEY>` + `x-folder-id: <YANDEX_FOLDER_ID>`
- **modelUri:** `art://<folder_id>/yandex-art/latest`
- **Aspect ratio:** widthRatio/heightRatio — целые 1..8
- **Max size Phase 1:** 512×512 (8×8 = 64×64 base unit)
- **Стоимость:** ~0.05₽ за изображение, щедрый free-tier

## Response (sync)

```json
{"image": "<base64-png>"}
```

## Response (async)

```json
{"id": "<operation_id>", "done": false}
```

→ поллинг по `GET https://llm.api.cloud.yandex.net/operations/<id>`.

## Известные баги / фичи

- **YandexART любит EN-промпты.** На русском понимает хуже.
- **Текст на картинке получается криво.** negative_prompts блокирует.
- **Соотношения сторон фиксированные** (1..8 × 1..8). Для нестандартных — upscale (Phase 2).
- **Async-эндпоинт возвращает sync-ответ** в большинстве случаев.
