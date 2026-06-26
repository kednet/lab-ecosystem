# FFmpeg Cheatsheet (Phase 2+)

Справка по ffmpeg-командам для сборки коротких видео. Файл пустой — наполняется в Phase 2.

## Базовые операции

### Получить информацию о видео
```bash
ffprobe -v error -show_format -show_streams input.mp4
```

### Конвертировать в 9:16 (1080×1920)
```bash
ffmpeg -i input.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black" -c:v libx264 -preset slow -crf 23 -c:a aac -b:a 128k -movflags +faststart output.mp4
```

### H.264 preset для shorts/reels
```bash
ffmpeg -i input.mp4 \
  -c:v libx264 \
  -preset slow \
  -crf 23 \
  -profile:v high \
  -level 4.0 \
  -pix_fmt yuv420p \
  -c:a aac \
  -b:a 128k \
  -movflags +faststart \
  output.mp4
```

## Нарезка и склейка

### Вырезать фрагмент (по таймстампам, fast)
```bash
ffmpeg -ss 00:00:05 -to 00:00:15 -i source.mp4 -c copy slice.mp4
```

### Вырезать фрагмент (точный, re-encode)
```bash
ffmpeg -ss 00:00:05 -to 00:00:15 -i source.mp4 -c:v libx264 -crf 23 -c:a aac slice.mp4
```

### Склеить список клипов
```bash
# 1. Создать list.txt:
# file 'slice1.mp4'
# file 'slice2.mp4'
# file 'slice3.mp4'

ffmpeg -f concat -safe 0 -i list.txt -c copy output.mp4
```

## Оверлеи

### Watermark (текст в правом нижнем углу)
```bash
ffmpeg -i input.mp4 \
  -vf "drawtext=text='@pulab_ru':fontfile=Inter-Bold.ttf:fontsize=42:fontcolor=white:shadowcolor=black:shadowx=2:shadowy=2:x=w-tw-40:y=h-th-40" \
  -c:a copy \
  output.mp4
```

### Watermark (логотип PNG)
```bash
ffmpeg -i input.mp4 -i watermark.png \
  -filter_complex "overlay=W-w-40:H-h-40" \
  -c:a copy \
  output.mp4
```

### Субтитры (ASS-файл из subtitle render)
```bash
ffmpeg -i input.mp4 \
  -vf "ass=subs.ass" \
  -c:a copy \
  output.mp4
```

## Аудио

### Подмешать BGM (тихо, 15–20% от голоса)
```bash
ffmpeg -i video.mp4 -i bgm.mp3 \
  -filter_complex "[1:a]volume=0.18[bgm];[0:a][bgm]amix=inputs=2:duration=first" \
  -c:v copy \
  output.mp4
```

### Заменить аудиодорожку
```bash
ffmpeg -i video.mp4 -i voice.mp3 \
  -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 128k \
  output.mp4
```

### Fade in/out
```bash
ffmpeg -i input.mp3 -af "afade=t=in:st=0:d=1,afade=t=out:st=29:d=1" output.mp3
```

## Полезные флаги

- `-movflags +faststart` — переносит `moov` атом в начало (для веб-плееров)
- `-pix_fmt yuv420p` — совместимость с iOS/Quicktime
- `-crf 23` — visual quality (lower = better, 18–28 разумный диапазон)
- `-preset slow` — медленнее кодирование, меньше файл (veryslow/slow/medium/fast/ultrafast)
- `-ss before -i` vs `-ss after -i` — fast vs accurate seek

## Связано с

- `sub-skills/auto-mode.md` — Phase 2
- `sub-skills/manual-mode.md` — Phase 3
- `sub-skills/publish-flow.md` — Phase 4
- `data/presets/9x16-h264.json` — ffmpeg-пресет (Phase 2 stub)
