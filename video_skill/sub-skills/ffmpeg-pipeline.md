# ffmpeg pipeline — Video Creator Skill v1.0 (Phase 2+)

Phase 1: ЗАГЛУШКА. Phase 2: справочник по ffmpeg-командам.

## Ключевые ffmpeg-фильтры

### scale+pad (приведение к 9:16)
```bash
ffmpeg -i in.mp4 -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1" out.mp4
```

### subtitles (burned-in subs из SRT)
```bash
ffmpeg -i in.mp4 -vf "subtitles=subs.srt:force_style='FontName=Arial,FontSize=28,PrimaryColour=&HFFFFFF,Outline=2,Alignment=2,MarginV=80'" out.mp4
```

### drawtext (watermark)
```bash
# Windows: абсолютный путь к шрифту с экранированием
ffmpeg -i in.mp4 -vf "drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='@pulab_ru':fontcolor=white:fontsize=36:box=1:boxcolor=black@0.5:x=(w-tw)/2:y=h-th-60:enable='gte(t,2)'" out.mp4
```

### amix (VO + BGM)
```bash
ffmpeg -i vo.mp3 -i bgm.mp3 -filter_complex "
  [0:a]volume=1.0,aresample=48000[vo];
  [1:a]volume=0.18,afade=t=in:st=0:d=2,afade=t=out:st=<total-3>:d=3[bgm];
  [vo][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0
" -c:a aac -b:a 128k out.m4a
```

### Полный pipeline (A-режим)
```bash
ffmpeg -y -i source.mp4 -i voiceover.mp3 -i bgm.mp3 \
  -filter_complex "
    [0:v]scale=1080:1920:force_original_aspect_ratio=decrease,
         pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1,
         subtitles=subs.srt:force_style='FontName=Arial,FontSize=28,PrimaryColour=&HFFFFFF,Outline=2,Alignment=2,MarginV=80',
         drawtext=fontfile='C\\:/Windows/Fonts/arialbd.ttf':text='@pulab_ru':fontcolor=white:fontsize=36:box=1:boxcolor=black@0.5:x=(w-tw)/2:y=h-th-60:enable='gte(t,2)'[v];
    [1:a]volume=1.0,aresample=48000[vo];
    [2:a]volume=0.18,afade=t=in:st=0:d=2,afade=t=out:st=<total-3>:d=3[bgm];
    [vo][bgm]amix=inputs=2:duration=first:dropout_transition=0:normalize=0[a]
  " -map "[v]" -map "[a]" \
  -c:v libx264 -profile:v high -level 4.0 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -ar 48000 \
  -r 30 -s 1080x1920 -movflags +faststart \
  out/<slug>.mp4
```

## Export preset (data/presets/9x16-h264.json)
```json
{
  "width": 1080, "height": 1920, "fps": 30,
  "vcodec": "libx264", "crf": 23, "preset": "medium",
  "acodec": "aac", "ab": "128k",
  "pix_fmt": "yuv420p", "faststart": true
}
```

## Pitfalls
- **Windows paths**: `C\\:/Windows/Fonts/arialbd.ttf` (двойной escape)
- **VFR-видео в стоке**: принудительно `fps=30` через `-vf fps=30`
- **Клип короче shot**: loop с `-stream_loop -1` + `-t shot_dur`
- **TikTok safe-zone**: `pad=1080:1920:200:400:black` (увеличить top/bottom)
- **yuv420p обязателен** для совместимости с QuickTime/iOS

## Валидация (ffprobe)
```bash
ffprobe -v error -select_streams v:0 -show_entries stream=width,height,codec_name,r_frame_rate,pix_fmt -of default out.mp4
# Ожидаем: width=1080, height=1920, codec_name=h264, r_frame_rate=30/1, pix_fmt=yuv420p
```

## Связано с
- `data/presets/9x16-h264.json` — export preset
- `data/platforms.yaml` — safe_zones для каждой платформы
- `references/ffmpeg-cheatsheet.md` — расширенная шпаргалка (Phase 2+)
