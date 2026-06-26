# /video manual ... --timestamps="..."

**Phase 3 — ЗАГЛУШКА. Реализация в следующей сессии.**

Будет: скачать длинный фильм/видео через `yt-dlp` и нарезать highlights по таймстампам + склеить в короткое видео.

## Требования для реализации

- `pip install yt-dlp` — загрузчик видео
- Источник: YouTube-ссылка, локальный mp4, или VK-видео

## План реализации (Phase 3)

1. Скачать исходник через `yt-dlp` (или скопировать локальный)
2. Парсить таймстампы из `--timestamps="00:01:23-00:01:45,00:05:00-00:05:30"`
3. Нарезать через ffmpeg `trim` фильтр
4. Склеить через ffmpeg `concat` (или filter complex)
5. Экспорт: 9:16 / 1:1 H.264 + AAC

## Алгоритм (после реализации)

```
1. resolve manual args (--source, --timestamps, --title)
2. download via yt-dlp → tmp/sources/<id>.mp4
3. parse_timestamps("00:01:23-00:01:45,...") → [(start, end), ...]
4. for each (start, end):
   - ffmpeg -ss <start> -to <end> -i source -c copy tmp/slices/<n>.mp4
5. concat slices → ffmpeg -f concat -i list.txt -c copy tmp/highlights/<slug>.mp4
6. save to tmp/renders/<profile>/<slug>-highlights.mp4
7. state.update(status=rendered, video_path=..., source_url=...)
```

## Связано с

- `sub-skills/manual-mode.md` — детали B-режима
- `sub-skills/ffmpeg-pipeline.md` — ffmpeg cheatsheet
- `expert-reviews-hub` — вход `auto --from-review=<slug>` (Phase 4.5)
- `coach_agent` — модули → темы для подбора таймстампов
