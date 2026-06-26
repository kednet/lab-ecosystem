"""
Деплой Worker через POST /accounts/{id}/workers/scripts/{name}/versions
с multipart/form-data. /versions не режется нашим edge (в отличие от PUT /scripts).
"""
import os
import json
import uuid
import urllib.request
import urllib.error
import ssl


ACCT = "80ba4de511365824283fec3678626c75"
BUNDLE_PATH = r"C:\Users\kfigh\lab_site\worker\dist-worker\index.js"
BUNDLE_NAME = "index.js"
SCRIPT_NAME = "lab-site-api"

# CF API token берётся из secrets-файла (НЕ из репо, НЕ из .env).
# Положить: Set-Content "$HOME\.claude\secrets\lab-site.env" "CLOUDFLARE_API_TOKEN=..." (UTF-8)
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

# /versions принимает: metadata + каждый файл как поле формы
add_field("metadata", None, "application/json", json.dumps(metadata).encode("utf-8"))
add_field(BUNDLE_NAME, BUNDLE_NAME, "application/javascript+module", bundle_data)
parts.append(f"--{boundary}--\r\n".encode())

body = b"".join(parts)

# Сначала зальём version, потом promote через /deployments
# По docs wrangler 4.99+: POST /versions возвращает { id, number, metadata }
# Затем: POST /deployments с { script, strategy: "percentage", versions: [{ percentage: 100, version_id: ... }] }
# Но самый простой путь — POST /deployments с { script, strategy: "percentage", versions: [{ percentage: 100, version_id: NEW }] }
# Однако это 2 запроса. Сначала сделаем upload + promote через /versions?deploy=true (если поддерживается)

url = f"https://api.cloudflare.com/client/v4/accounts/{ACCT}/workers/scripts/{SCRIPT_NAME}/versions"
print(f"POST {url}")
print(f"Bundle: {len(bundle_data)} bytes, body: {len(body)} bytes")

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

req = urllib.request.Request(
    url,
    data=body,
    method="POST",
    headers={
        "Authorization": f"Bearer {TOKEN}",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Content-Length": str(len(body)),
    },
)

try:
    with urllib.request.urlopen(req, timeout=120, context=ctx) as resp:
        result = json.loads(resp.read())
        print(f"Status: {resp.status}")
        print(json.dumps(result, indent=2)[:3000])

    # Если успех — promote to deploy
    if result.get("success") and result.get("result", {}).get("id"):
        version_id = result["result"]["id"]
        print(f"\n=== Promote version {version_id} to 100% ===")
        promote_body = json.dumps({
            "script": SCRIPT_NAME,
            "strategy": "percentage",
            "versions": [{"percentage": 100, "version_id": version_id}],
        }).encode("utf-8")
        promote_req = urllib.request.Request(
            f"https://api.cloudflare.com/client/v4/accounts/{ACCT}/workers/scripts/{SCRIPT_NAME}/deployments",
            data=promote_body,
            method="POST",
            headers={
                "Authorization": f"Bearer {TOKEN}",
                "Content-Type": "application/json",
                "Content-Length": str(len(promote_body)),
            },
        )
        with urllib.request.urlopen(promote_req, timeout=60, context=ctx) as pr:
            presult = json.loads(pr.read())
            print(f"Status: {pr.status}")
            print(json.dumps(presult, indent=2)[:2000])

except urllib.error.HTTPError as e:
    print(f"HTTP {e.code}")
    print(e.read().decode()[:2000])
except Exception as e:
    print(f"Error: {e}")
