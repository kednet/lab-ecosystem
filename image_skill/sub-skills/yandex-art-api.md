---
name: yandex-art-api
description: "Документация Yandex Cloud YandexART API (imageGeneration_async)"
metadata:
  type: sub-skill
  phase: 1
---

# Yandex Cloud YandexART API

## Endpoint

```
POST https://llm.api.cloud.yandex.net/foundationModels/v1/imageGeneration_async
```

## Auth

```
Authorization: Api-Key <YANDEX_API_KEY>
x-folder-id: <YANDEX_FOLDER_ID>
```

Тот же ключ, что для YandexGPT (оплата по единому счёту).

## modelUri

```
art://<folder_id>/yandex-art/latest
```

Пример: `art://b1gmccf4hvud5vlkrdl3/yandex-art/latest`

`folder_id` берётся из ENV `YANDEX_FOLDER_ID` или `YANDEX_MODEL_ART` (полный URI).

## Request body

```json
{
  "modelUri": "art://<folder_id>/yandex-art/latest",
  "messages": [
    {"role": "user", "text": "<промпт на английском, 1-2 предложения>"}
  ],
  "generationOptions": {
    "mimeType": "image/png",
    "aspectRatio": {
      "widthRatio": 8,
      "heightRatio": 8
    },
    "seed": 271828
  }
}
```

### Параметры

| Поле | Тип | Описание | Диапазон |
|------|-----|----------|----------|
| `modelUri` | string | art://<folder>/yandex-art/latest | — |
| `messages[].role` | string | "user" | — |
| `messages[].text` | string | Промпт | до 1000 символов рекомендую |
| `mimeType` | string | "image/png" \| "image/jpeg" | — |
| `aspectRatio.widthRatio` | int | Пропорция ширины | 1..8 |
| `aspectRatio.heightRatio` | int | Пропорция высоты | 1..8 |
| `seed` | uint | Random seed | 0..2^32 (опц.) |

### Размеры

Базовая сетка: 8 × 64px = до 512×512px. С v2 модели возможны размеры до 1024×1024,
но для Phase 1 фиксируем сетку.

Примеры:
- 8:8 → 512×512
- 5:9 → 320×576
- 4:6 → 256×384
- 6:8 → 384×512
- 6:3 → 384×192

## Response (sync)

```json
{
  "image": "<base64-png>"
}
```

## Response (async — operation ID)

```json
{
  "id": "<operation_id>",
  "done": false
}
```

→ поллинг по `GET https://llm.api.cloud.yandex.net/operations/<id>` пока `done: true`,
затем `response.image` содержит base64 PNG.

## Пример (curl)

```bash
curl -X POST \
  https://llm.api.cloud.yandex.net/foundationModels/v1/imageGeneration_async \
  -H "Authorization: Api-Key $YANDEX_API_KEY" \
  -H "x-folder-id: $YANDEX_FOLDER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "modelUri": "art://b1gmccf4hvud5vlkrdl3/yandex-art/latest",
    "messages": [{"role": "user", "text": "a cute fox in watercolor style"}],
    "generationOptions": {
      "mimeType": "image/png",
      "aspectRatio": {"widthRatio": 8, "heightRatio": 8},
      "seed": 42
    }
  }'
```

## Пример (Python)

```python
import base64, json, urllib.request
from _image_common import mitm_bypass_ssl

req = urllib.request.Request(
    "https://llm.api.cloud.yandex.net/foundationModels/v1/imageGeneration_async",
    data=json.dumps({...}).encode(),
    headers={"Authorization": f"Api-Key {KEY}", "x-folder-id": FOLDER},
)
with urllib.request.urlopen(req, context=mitm_bypass_ssl()) as resp:
    result = json.loads(resp.read())
png = base64.b64decode(result["image"])
```

## Стоимость

~0.05₽ за 1 изображение (зависит от региона и текущих тарифов Yandex Cloud).
На момент 2026-06-17 действует щедрый free-tier.

## Квоты

Единая квота на YandexAPI (YandexGPT + YandexART + будущий SpeechKit):
- Default: 1000 RPS, 1M запросов/мес
- При превышении → HTTP 429

## Известные баги / фичи

- **YandexART любит EN-промпты.** На русском понимает хуже, особенно абстрактные концепты.
  Поэтому `cmd_generate.build_prompt` всегда переводит в EN через LLM.
- **Текст на картинке получается криво.** Поэтому negative_prompts = ["text on image"].
- **Соотношения сторон фиксированные** (1..8 × 1..8). Для нестандартных — upscale (Phase 2).
- **Async-эндпоинт возвращает sync-ответ** в большинстве случаев, polling нужен редко.
  Реализация polling есть в `yandex_art._poll_operation` (на всякий случай).

## Связано с

- [[image-skill-v1-phase1-built]]
- [[cmd-generate]] — где используется
- [[corporate-mitm-proxy]] — обход MITM
