# /video auto ... --from-script=<slug>

**Phase 2 — ЗАГЛУШКА. Реализация в следующей сессии.**

Будет: собрать mp4 из сценария через стоки (Pexels+Pixabay) + ffmpeg + TTS (Yandex) + субтитры + BGM + watermark.

## Требования для реализации

- `PEXELS_API_KEY` — https://www.pexels.com/api/ (2 мин)
- `PIXABAY_API_KEY` — https://pixabay.com/service/about/api/ (2 мин)
- `YANDEX_SPEECHKIT_API_KEY` — переиспользовать от `audio_skill` (0 мин)
- `FFMPEG_BIN` — путь к `ffmpeg.exe` (Phase 2+)

## План реализации (Phase 2)

1. Прочитать `tmp/scripts/<profile>/<slug>.md` (из `script_ready`)
2. Сгенерировать `clip_keywords` через LLM (`prompts/clip-keywords.md`)
3. Скачать клипы через `pexels_client.search(keyword)` и `pixabay_client.search(keyword)`
4. Озвучить через `tts_yandex.synthesize(ssml, voice, speed)` (по одному TTS на шот или один общий)
5. Собрать субтитры через `burn_subs.py` (libass или PIL+ffmpeg drawtext)
6. Подмешать BGM из `data/bgm_catalog.yaml` (по `music_mood`)
7. Наложить watermark через ffmpeg drawtext (`@pulab_ru` в правом нижнем углу)
8. Экспорт: `ffmpeg -preset slow -crf 23 -movflags +faststart` → 9:16, H.264, AAC
9. Сохранить в `tmp/renders/<profile>/<slug>.mp4`
10. Обновить `state/<profile>/<slug>.json` → `status="rendered"`, `video_path`, `rendered_at`

## Алгоритм (после реализации)

```
1. resolve auto args (--from-script, --voice, --bgm)
2. load state/<profile>/<slug>.json — должен быть script_ready
3. for each shot:
   - clip = fetch_clip(keyword, pexels_or_pixabay)
   - audio = synthesize(shot.vo_text, voice, speed)
4. concat clips + overlay audio
5. burn subs (libass)
6. mix BGM (volume 0.15–0.20)
7. overlay watermark
8. export 9:16 H.264
9. save to tmp/renders/<profile>/<slug>.mp4
10. state.update(status=rendered, video_path=...)
```

## Связано с

- `sub-skills/auto-mode.md` — детали A-режима
- `sub-skills/ffmpeg-pipeline.md` — ffmpeg cheatsheet
- `prompts/clip-keywords.md` — генерация ключевых слов для поиска
- `audio_skill/scripts/tts_yandex.py` — TTS
