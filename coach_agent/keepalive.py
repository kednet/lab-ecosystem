"""
Keepalive-скрипт для Render Cron Job.

Пингует /health нашего Web Service, чтобы Free tier не засыпал.
Запускается каждые 14 минут (см. render.yaml → cron).

Использование:
    python keepalive.py
или с явным URL:
    RENDER_EXTERNAL_URL=https://wishcoach.onrender.com python keepalive.py
"""

from __future__ import annotations

import os
import sys

import httpx


def main() -> int:
    url = os.environ.get("RENDER_EXTERNAL_URL", "http://localhost:8000")
    target = f"{url.rstrip('/')}/health"
    try:
        r = httpx.get(target, timeout=15, verify=False)
    except httpx.HTTPError as e:
        print(f"keepalive: network error {e}", file=sys.stderr)
        return 1
    print(f"keepalive: {r.status_code} {target}")
    return 0 if r.status_code == 200 else 1


if __name__ == "__main__":
    raise SystemExit(main())
