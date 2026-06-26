"""
ffmpeg mix для Audio Skill.

Миксует голосовую дорожку с фоновой музыкой:
1. Подмешивает фон к голосу с указанной громкостью
2. Делает fade-in фона (music_intro сек)
3. Делает fade-out фона (music_outro сек)
4. Нормализует громкость в -14 LUFS (стандарт для подкастов/аудиокниг)

Использование:
    python scripts/mix_audio.py tmp/<slug>-voice.mp3 \
        --background=bowls_warm \
        --music-intro=5s --music-outro=6s \
        --out=tmp/<slug>-full.mp3
"""

import argparse
import io
import os
import re
import subprocess
import sys
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

try:
    import yaml
except ImportError:
    print("[!] pip install pyyaml", file=sys.stderr)
    sys.exit(1)


def find_ffmpeg() -> str:
    """Ищет ffmpeg в PATH или в известных местах winget."""
    # 1. Пробуем просто ffmpeg (если в PATH)
    try:
        r = subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        if r.returncode == 0:
            return "ffmpeg"
    except FileNotFoundError:
        pass

    # 2. Ищем в WinGet packages
    winget_root = Path("C:/Users/kfigh/AppData/Local/Microsoft/WinGet/Packages")
    if winget_root.exists():
        for p in winget_root.glob("Gyan.FFmpeg*"):
            for ffmpeg in p.rglob("ffmpeg.exe"):
                return str(ffmpeg)

    raise RuntimeError("ffmpeg не найден. Установи: winget install Gyan.FFmpeg")


def parse_seconds(s: str) -> float:
    """'5s' → 5.0, '500ms' → 0.5"""
    s = s.strip()
    m = re.match(r"^(\d+(?:\.\d+)?)(s|ms)?$", s)
    if not m:
        return 1.0
    val = float(m.group(1))
    unit = m.group(2) or "s"
    return val if unit == "s" else val / 1000


def load_background(bg_slug: str) -> dict:
    """Загружает описание фона из data/backgrounds.yaml."""
    yaml_path = Path(__file__).parent.parent / "data" / "backgrounds.yaml"
    data = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    bg = data.get("backgrounds", {}).get(bg_slug)
    if not bg:
        raise ValueError(f"Фон '{bg_slug}' не найден в backgrounds.yaml")
    return bg


def mix(voice_path: Path, bg_path: Path = None,
        volume_db: float = -22.0, fade_in: float = 5.0, fade_out: float = 6.0,
        out_path: Path = None, normalize: bool = True) -> None:
    """Миксует голос + фон через ffmpeg."""
    ffmpeg = find_ffmpeg()
    voice_duration = get_duration(voice_path)

    # Если фона нет — нормализуем голос
    if bg_path is None or not bg_path.exists():
        print(f"[*] Фон не указан, нормализую только голос")
        cmd = [ffmpeg, "-y", "-i", str(voice_path)]
        if normalize:
            cmd += ["-af", "loudnorm=I=-14:TP=-1.5:LRA=11"]
        cmd += ["-ar", "48000", "-ac", "2", "-b:a", "192k", str(out_path)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {r.stderr[-500:]}")
        return

    # Фон короче голоса — зацикливаем
    bg_duration = get_duration(bg_path)
    loop_count = max(1, int(voice_duration / bg_duration) + 1)
    print(f"[*] Voice: {voice_duration:.1f}s, BG: {bg_duration:.1f}s → loop {loop_count}x")

    # 1) Зацикливаем фон
    loop_bg = out_path.with_suffix(".looped.mp3")
    cmd_loop = [ffmpeg, "-y", "-stream_loop", str(loop_count), "-i", str(bg_path),
                "-t", str(voice_duration + fade_in + fade_out + 2),  # запас
                "-ar", "48000", "-ac", "2", str(loop_bg)]
    r = subprocess.run(cmd_loop, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg loop failed: {r.stderr[-500:]}")

    # 2) Микс: голос + фон с громкостью + fade in/out фона
    # amix с weights: голос 1.0, фон по громкости
    # fade in/out применяется к фону
    fade_in_ms = int(fade_in * 1000)
    fade_out_ms = int(fade_out * 1000)
    bg_vol_linear = 10 ** (volume_db / 20)  # дБ → линейный множитель

    filter_complex = (
        f"[1:a]afade=t=in:st=0:d={fade_in},"
        f"afade=t=out:st={voice_duration + fade_in - fade_out}:d={fade_out},"
        f"volume={bg_vol_linear:.4f}[bg];"
        f"[0:a][bg]amix=inputs=2:duration=first:dropout_transition=0[mix]"
    )
    if normalize:
        filter_complex += ";[mix]loudnorm=I=-14:TP=-1.5:LRA=11[out]"

    cmd_mix = [
        ffmpeg, "-y",
        "-i", str(voice_path),
        "-i", str(loop_bg),
        "-filter_complex", filter_complex,
        "-map", "[out]" if normalize else "[mix]",
        "-ar", "48000", "-ac", "2", "-b:a", "192k",
        str(out_path),
    ]
    r = subprocess.run(cmd_mix, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffmpeg mix failed: {r.stderr[-500:]}")

    # Чистим loop
    loop_bg.unlink(missing_ok=True)


def get_duration(p: Path) -> float:
    """Возвращает длительность mp3 в секундах через ffprobe."""
    ff = find_ffmpeg()
    # ffprobe лежит рядом с ffmpeg: ffmpeg.exe → ffprobe.exe, или просто ffprobe
    if ff.endswith("ffmpeg.exe"):
        ffprobe = ff.replace("ffmpeg.exe", "ffprobe.exe")
    elif ff.endswith("ffmpeg"):
        ffprobe = ff.replace("ffmpeg", "ffprobe")
    else:
        ffprobe = "ffprobe"
    r = subprocess.run([ffprobe, "-v", "error", "-show_entries", "format=duration",
                        "-of", "default=noprint_wrappers=1:nokey=1", str(p)],
                       capture_output=True, text=True)
    try:
        return float(r.stdout.strip())
    except ValueError:
        return 0.0


def main() -> int:
    ap = argparse.ArgumentParser(description="ffmpeg mix voice + background")
    ap.add_argument("voice", help="Путь к голосовой mp3 дорожке")
    ap.add_argument("--background", help="Slug фона из backgrounds.yaml")
    ap.add_argument("--music-intro", default="5s", help="Длительность fade-in фона")
    ap.add_argument("--music-outro", default="6s", help="Длительность fade-out фона")
    ap.add_argument("--no-normalize", action="store_true", help="Без нормализации loudnorm")
    ap.add_argument("--out", required=True, help="Путь к финальному mp3")
    args = ap.parse_args()

    voice_path = Path(args.voice)
    if not voice_path.exists():
        print(f"[!] Голос не найден: {voice_path}", file=sys.stderr)
        return 1

    bg_path = None
    volume_db = -22.0
    fade_in = parse_seconds(args.music_intro)
    fade_out = parse_seconds(args.music_outro)

    if args.background and args.background != "silence":
        bg = load_background(args.background)
        bg_path = Path(__file__).parent.parent / bg["file"]
        volume_db = bg.get("volume_db", -22.0)
        if bg.get("fade_in"):
            fade_in = parse_seconds(bg["fade_in"])
        if bg.get("fade_out"):
            fade_out = parse_seconds(bg["fade_out"])
        print(f"[*] Фон: {args.background} ({bg['file']})")
        print(f"    volume_db={volume_db}, fade_in={fade_in}s, fade_out={fade_out}s")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    mix(voice_path, bg_path, volume_db, fade_in, fade_out, out_path,
        normalize=not args.no_normalize)

    size_kb = out_path.stat().st_size / 1024
    duration = get_duration(out_path)
    print(f"[+] {out_path}  ({size_kb:.0f} КБ, {duration:.1f} сек)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
