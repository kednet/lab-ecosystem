"""
cmd_manual.py — подкоманда `video.py manual` (B-режим, Phase 3).

Phase 1: ЗАГЛУШКА.
Phase 3: yt-dlp URL → mp4, multi-trim + concat → highlights mp4.
"""
from __future__ import annotations

import sys


def run(args) -> int:
    print("⚠  manual (B-режим) — Phase 3, не реализовано в Phase 1.")
    print("   Требует: yt-dlp (pip install yt-dlp)")
    print("   План: C:/Users/kfigh/.claude/plans/video-skill-universal-2026-06-17.md (секция 5)")
    return 1


if __name__ == "__main__":
    sys.exit(run(None))
