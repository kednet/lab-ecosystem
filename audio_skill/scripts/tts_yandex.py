"""
Yandex SpeechKit TTS для Audio Skill.

Берёт SSML файл (или YAML), синтезирует mp3 через Yandex SpeechKit REST API.

Использование:
    python scripts/tts_yandex.py tmp/<slug>.ssml --voice=jane --out=tmp/<slug>-voice.mp3
    python scripts/tts_yandex.py data/library/<slug>.yaml --voice=jane --out=tmp/<slug>-voice.mp3
"""

import argparse
import io
import os
import subprocess
import sys
from pathlib import Path

if sys.platform.startswith("win"):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

try:
    import requests
except ImportError:
    print("[!] pip install requests", file=sys.stderr)
    sys.exit(1)

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent.parent / ".env")
except ImportError:
    pass


def synthesize(ssml_text: str, voice: str = "jane",
               folder_id: str = None, api_key: str = None,
               sample_rate: int = 48000,
               speed: float = None, role: str = None) -> bytes:
    folder_id = folder_id or os.getenv("YC_FOLDER_ID")
    api_key = api_key or os.getenv("YC_API_KEY")

    if not folder_id or not api_key:
        raise RuntimeError("YC_FOLDER_ID и YC_API_KEY должны быть в .env")

    url = "https://tts.api.cloud.yandex.net/speech/v1/tts:synthesize"
    headers = {"Authorization": f"Api-Key {api_key}"}
    data = {
        "ssml": ssml_text,
        "lang": "ru-RU",
        "voice": voice,
        "format": "mp3",
        "folderId": folder_id,
        "sampleRateHertz": str(sample_rate),
    }
    # speed: 0.1..3.0 (1.0 = normal). role: эмоция (good/neutral/...).
    # Премиум-голоса (anton, mikhail, lea…) НЕ поддерживают pitch в API —
    # pitch_shift нужно делать через ffmpeg asetrate после синтеза.
    if speed is not None:
        data["speed"] = str(speed)
    if role is not None:
        data["role"] = role

    r = requests.post(url, headers=headers, data=data, timeout=120)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:500]}")
    return r.content


def main() -> int:
    ap = argparse.ArgumentParser(description="TTS через Yandex SpeechKit")
    ap.add_argument("input", help="SSML файл или YAML (если YAML — будет сначала собран SSML)")
    ap.add_argument("--voice", default="jane", help="Голос (jane, alena, anton, filipp, ermil, mikhail, lea)")
    ap.add_argument("--out", required=True, help="Путь к выходному mp3")
    ap.add_argument("--sample-rate", type=int, default=48000)
    ap.add_argument("--speed", type=float, default=None, help="Скорость (0.1..3.0)")
    ap.add_argument("--role", type=str, default=None, help="Эмоция (neutral, good, evil, angry, sad, funny, serious, surprised)")
    ap.add_argument("--pitch-shift", type=int, default=None, help="Сдвиг тона в %% (через ffmpeg asetrate, например -10)")
    args = ap.parse_args()

    inp = Path(args.input)
    if not inp.exists():
        print(f"[!] Файл не найден: {inp}", file=sys.stderr)
        return 1

    # Если вход — YAML, читаем prosody (speed, role, pitch_shift) из YAML
    pitch_shift = args.pitch_shift
    speed = args.speed
    role = args.role
    if inp.suffix in (".yaml", ".yml"):
        sys.path.insert(0, str(Path(__file__).parent))
        from ssml_build import build_ssml
        ssml = build_ssml(inp)
        # Сохраняем SSML рядом с mp3 для отладки
        ssml_path = Path(args.out).with_suffix(".ssml")
        ssml_path.write_text(ssml, encoding="utf-8")
        print(f"[+] SSML saved: {ssml_path} ({len(ssml)} chars)")
        # Подхватываем prosody из YAML, если не передан флагом
        try:
            import yaml as _yaml
            meta = _yaml.safe_load(inp.read_text(encoding="utf-8"))
            prosody = meta.get("prosody", {}) or {}
            if speed is None and prosody.get("rate") is not None:
                speed = float(prosody["rate"])
            if pitch_shift is None and prosody.get("pitch") is not None:
                pitch_shift = int(prosody["pitch"])
            if role is None and prosody.get("role") is not None:
                role = str(prosody["role"])
        except Exception:
            pass
    else:
        ssml = inp.read_text(encoding="utf-8")

    print(f"[*] Synth voice='{args.voice}' speed={speed} role={role} pitch_shift={pitch_shift}%")
    raw_bytes = synthesize(ssml, voice=args.voice, sample_rate=args.sample_rate,
                           speed=speed, role=role)

    # Если нужен сдвиг тона, делаем через ffmpeg rubberband (сохраняет темп).
    # pitch ratio: 0.9 = на 10% ниже по частоте, длительность не меняется.
    if pitch_shift is not None and pitch_shift != 0:
        from mix_audio import find_ffmpeg
        ffmpeg = find_ffmpeg()
        factor = 1.0 + pitch_shift / 100.0  # -10% → 0.9
        raw_in = Path(args.out).with_suffix(".raw.mp3")
        raw_in.write_bytes(raw_bytes)
        cmd = [
            ffmpeg, "-y", "-i", str(raw_in),
            "-af", f"rubberband=pitch={factor:.4f}:tempo=1.0",
            "-ar", str(args.sample_rate), "-ac", "2", "-b:a", "192k",
            str(args.out),
        ]
        r = subprocess.run(cmd, capture_output=True, text=True)
        raw_in.unlink(missing_ok=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg pitch shift failed: {r.stderr[-500:]}")
        audio_bytes = Path(args.out).read_bytes()
    else:
        audio_bytes = raw_bytes

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(audio_bytes)
    size_kb = len(audio_bytes) / 1024
    # Оценка длительности: ~8 КБ/сек при 48 kHz mp3
    duration_est = size_kb / 8
    print(f"[+] mp3 saved: {out} ({size_kb:.0f} KB, ~{duration_est:.0f} sec)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
