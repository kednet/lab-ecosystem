"""
Установка секретов Worker'а через Cloudflare API.
Обход wrangler 4.98+ на Node 24 (fetch failed).
"""
import os
import json
import urllib.request
import urllib.error


TOKEN = "CF_API_TOKEN_REDACTED"
ACCT = "80ba4de511365824283fec3678626c75"
SCRIPT = "lab-site-api"

with open(r"C:\Users\kfigh\lab_site\worker\.jwt_secret.txt") as f:
    JWT_SECRET = f.read().strip()
with open(r"C:\Users\kfigh\lab_site\worker\.python_token.txt") as f:
    PYTHON_TOKEN = f.read().strip()

secrets = {
    "JWT_SECRET": JWT_SECRET,
    "PYTHON_SERVICE_TOKEN": PYTHON_TOKEN,
}

# 1) Перезатираем bindings (заодно сменим ENVIRONMENT → production, обновим FRONTEND_ORIGIN)
# На самом деле секреты в bindings и так не попадают — они отдельно через /secrets

for name, value in secrets.items():
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCT}/workers/scripts/{SCRIPT}/secrets/{name}",
        data=value.encode("utf-8"),
        method="PUT",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "text/plain",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            body = r.read()
            print(f"[{name}] HTTP {r.status}: {body[:200].decode()}")
    except urllib.error.HTTPError as e:
        print(f"[{name}] HTTP {e.code}: {e.read().decode()[:300]}")
    except Exception as e:
        print(f"[{name}] Error: {e}")
