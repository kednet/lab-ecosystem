"""
cmd_auto.py — подкоманда `video.py auto` (A-режим, Phase 2+).

Phase 1: ЗАГЛУШКА. Печатает что не реализовано.
Phase 2: Pexels+Pixabay+ffmpeg+TTS+subs+BGM+watermark → mp4.
"""
from __future__ import annotations

import sys


def run(args) -> int:
    print("⚠  auto (A-режим) — Phase 2, не реализовано в Phase 1.")
    print("   Требует: PEXELS_API_KEY, PIXABAY_API_KEY, YANDEX_SPEECHKIT_API_KEY, FFMPEG_BIN")
    print("   План: C:/Users/kfigh/.claude/plans/video-skill-universal-2026-06-17.md (секция 4)")
    return 1


if __name__ == "__main__":
    sys.exit(run(None))
