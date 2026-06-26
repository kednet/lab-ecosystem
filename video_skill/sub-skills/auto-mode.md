# A-режим (auto) — Video Creator Skill v1.0 (Phase 2 STUB)

Phase 1: ЗАГЛУШКА. Phase 2: реализация.

## Что будет в Phase 2
Полный pipeline авто-сборки mp4 9:16 из стокового видео + озвучка + субтитры + BGM + watermark + CTA.

## Алгоритм (план)

1. **fetch_clips** — Pexels API `GET /videos/search?query=<kw>&orientation=portrait&per_page=5` (4-6 клипов)
2. **tts_pipeline** — Yandex SpeechKit `POST /speech/v1/tts:synthesize` (1 mp3 на сценарий)
3. **burn_subs** — SRT → burned-in subs через ffmpeg `subtitles=`
4. **mix_video** — ffmpeg pipeline:
   - scale+pad 1080:1920
   - subtitles=
   - drawtext watermark (из profile.branding.watermark)
   - amix (VO + BGM)
   - export preset 9x16-h264
5. **validate** — ffprobe width=1080, height=1920, codec=h264, fps=30/1

## Команды Phase 2
```bash
python scripts/video.py auto reels engagement soulful 30 \
    --from-script=lab/5-oshibok-karty-zhelaniy --profile=lab

# Override голоса
python scripts/video.py auto ... --voice=filipp

# Без BGM
python scripts/video.py auto ... --no-bgm

# Только стадия
python scripts/video.py auto ... --only=fetch|tts|subs|mix|export
```

## Требует от kfigh
- PEXELS_API_KEY (https://www.pexels.com/api/) — 2 мин
- PIXABAY_API_KEY (https://pixabay.com/service/about/api/) — 2 мин
- YANDEX_SPEECHKIT_API_KEY (переиспользовать от audio_skill) — 0 мин
- FFMPEG_BIN в PATH (уже есть `ffmpeg 8.1.1-full_build`)

## Связано с
- `prompts/clip-keywords.md` — план LLM-перевода shot.vo_text → EN keywords
- `data/presets/9x16-h264.json` — export preset
- `data/bgm_catalog.yaml` — Pixabay Music URLs
- План: `C:/Users/kfigh/.claude/plans/video-skill-universal-2026-06-17.md` (секция 4)
