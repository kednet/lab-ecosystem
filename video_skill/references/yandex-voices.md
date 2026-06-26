# Yandex SpeechKit Voices (Phase 2+)

Карта голосов Yandex SpeechKit, используемых в `data/voice_map.yaml`.

| yandex_id | Описание | Пол | Премиум | Подходит для |
|---|---|---|---|---|
| `alena` | Спокойный женский, тёплый | Ж | нет | soulful, calm, tender |
| `jane` | Энергичный женский, яркий | Ж | да | bold, energetic, playful |
| `filipp` | Уверенный мужской, баритон | М | нет | inspiring, confident, educational |
| `ermil` | Нейтральный мужской, мягкий | М | нет | educational, calm, reflective |
| `marina` | Молодой женский, лёгкий | Ж | нет | playful, energetic, tender |
| `madirus` | Глубокий мужской, dramatic | М | да | bold, confident, inspiring |
| `zahar` | Низкий мужской, задумчивый | М | нет | reflective, calm, tender |

## ⚠️ НЕ использовать

- `lea` — обрезает длинный текст
- `nigora` — обрезает длинный текст

## Маппинг тон → голос (в `data/voice_map.yaml`)

```yaml
soulful:     { yandex_id: alena,   speed: 0.90 }
bold:        { yandex_id: madirus, speed: 1.05 }
inspiring:   { yandex_id: filipp,  speed: 1.00 }
educational: { yandex_id: ermil,   speed: 1.00 }
playful:     { yandex_id: marina,  speed: 1.10 }
calm:        { yandex_id: alena,   speed: 0.85 }
confident:   { yandex_id: filipp,  speed: 1.05 }
tender:      { yandex_id: jane,    speed: 0.90 }
energetic:   { yandex_id: jane,    speed: 1.10 }
reflective:  { yandex_id: zahar,   speed: 0.85 }
```

## Скорость (speed)

- `0.85` — медленно (для рефлексии, спокойствия)
- `0.90` — слегка замедленно (soulful)
- `1.00` — норма (default)
- `1.05` — слегка быстрее (confident)
- `1.10` — быстро (playful, energetic)

## Связано с

- `data/voice_map.yaml` — маппинг
- `audio_skill/data/voices.yaml` — канонический список
- `audio_skill/scripts/tts_yandex.py` — TTS-клиент
- `audio-skill-built.md` (memory) — preview 8 голосов + что работает
