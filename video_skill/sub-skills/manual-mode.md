# B-режим (manual) — Video Creator Skill v1.0 (Phase 3 STUB)

Phase 1: ЗАГЛУШКА. Phase 3: реализация.

## Что будет в Phase 3
Нарезка отрезков из локального видео или YouTube-URL по таймкодам → highlights mp4.

## Команды Phase 3
```bash
# Локальный файл
python scripts/video.py manual youtube subscribe inspiring 30 \
    --from-file="C:/Users/kfigh/films/sekret.mp4" \
    --timestamps="0:12:30-0:12:45, 0:45:10-0:45:22, 1:02:05-1:02:18" \
    --subs-file=tmp/notes/sekret-subs.srt \
    --profile=lab \
    --out=tmp/out/sekret-highlight.mp4

# URL (через yt-dlp)
python scripts/video.py manual youtube subscribe inspiring 30 \
    --from-url="https://www.youtube.com/watch?v=xxx" \
    --timestamps="1:23-1:35, 5:40-5:55"
```

## Алгоритм (план)
1. **parse_timestamps** — regex `H:MM:SS-H:MM:SS` + валидация (end > start, no overlap)
2. **source_loader** — локальный файл ИЛИ `yt-dlp URL → mp4`
3. **concat_clips** — multi-trim → concat
4. **mix_video** — scale+pad 9:16 + (опц.) burned-in subs + watermark → export

## Edge-cases
| Edge | Решение |
|---|---|
| VFR-источник | `ffmpeg -filter:v fps=30` |
| Таймкод вне длительности | `ffprobe_duration` до старта → ValueError |
| URL приватный | yt-dlp exit 1 → state.status=failed |
| 16:9 → 9:16 | по умолчанию letterbox (pad=), `--crop` для zoom-in |

## Требует от kfigh
- yt-dlp (`pip install yt-dlp`) — 30 сек

## Связано с
- `scripts/parse_timestamps.py` — план
- План: `C:/Users/kfigh/.claude/plans/video-skill-universal-2026-06-17.md` (секция 5)
