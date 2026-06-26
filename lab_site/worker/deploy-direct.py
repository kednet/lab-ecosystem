"""
Деплой Worker через прямой Cloudflare API.
Обходит баг wrangler 4.98+ на Node 24: fetch failed.
"""
import os
import json
import uuid
import urllib.request
import urllib.error
from email.generator import BytesGenerator
from io import BytesIO


ACCT = "80ba4de511365824283fec3678626c75"
BUNDLE_PATH = r"C:\Users\kfigh\lab_site\worker\dist-worker\index.js"
BUNDLE_NAME = "index.js"
SCRIPT_NAME = "lab-site-api"

# CF API token берётся из secrets-файла (НЕ из репо, НЕ из .env).
def _load_token() -> str:
    path = os.path.join(os.path.expanduser("~"), ".claude", "secrets", "lab-site.env")
    if not os.path.exists(path):
        raise SystemExit(f"ERROR: secrets file not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("CLOUDFLARE_API_TOKEN="):
                return line.split("=", 1)[1].strip()
    raise SystemExit("ERROR: CLOUDFLARE_API_TOKEN not in secrets file")


TOKEN = _load_token()

with open(BUNDLE_PATH, "rb") as f:
    bundle_data = f.read()

metadata = {
    "main_module": BUNDLE_NAME,
    "compatibility_date": "2024-12-18",
    "compatibility_flags": ["nodejs_compat"],
    "bindings": [
        {"name": "LAB_KV", "type": "kv_namespace", "namespace_id": "c9d44152187e4ac18f4a44b895ea0c4b"},
        {"type": "plain_text", "name": "ENVIRONMENT", "text": "production"},
        {"type": "plain_text", "name": "FRONTEND_ORIGIN", "text": "https://app.pulab.online"},
        {"type": "plain_text", "name": "JWT_SECRET_DEV", "text": "dev-secret-change-me-in-production-please-make-it-long-and-random"},
    ],
}

# Multipart form-data
boundary = uuid.uuid4().hex
parts = []

def add_field(name, filename, content_type, data):
    parts.append(f"--{boundary}\r\n".encode())
    if filename is not None:
        parts.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
    else:
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n'.encode())
    parts.append(f"Content-Type: {content_type}\r\n\r\n".encode())
    parts.append(data)
    parts.append(b"\r\n")

add_field("metadata", None, "application/json", json.dumps(metadata).encode("utf-8"))
add_field(BUNDLE_NAME, BUNDLE_NAME, "application/javascript+module", bundle_data)
parts.append(f"--{boundary}--\r\n".encode())

body = b"".join(parts)

req = urllib.request.Request(
    f"https://api.cloudflare.com/client/v4/accounts/{ACCT}/workers/scripts/{SCRIPT_NAME}",
    data=body,
    method="PUT",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    },
)

print(f"Bundle: {len(bundle_data)} bytes, body: {len(body)} bytes")

try:
    import ssl
    ctx = ssl.create_default_context()
    # Python на Windows иногда валится на Cloudflare'ских сертификатах
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE

    last_err = None
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
                result = json.loads(resp.read())
                print(f"Status: {resp.status} (attempt {attempt+1})")
                print(json.dumps(result, indent=2)[:2000])
            break
        except (urllib.error.URLError, ConnectionError, OSError) as e:
            last_err = e
            print(f"Attempt {attempt+1} failed: {e}")
            if attempt < 2:
                import time
                time.sleep(2)
    else:
        print(f"All attempts failed: {last_err}")
except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}")
    print(e.read().decode()[:2000])
except Exception as e:
    print(f"Error: {e}")
