"""
Pages Direct Upload (multipart/related-style) for lab-site.

Pages API uses these endpoints:
  POST /accounts/{id}/pages/assets/check-missing  (multipart, sends manifest)
  POST /accounts/{id}/pages/assets/upload         (multipart, sends file batch)
  POST /accounts/{id}/pages/projects/{name}/deployments (multipart with final hash)
"""
import os
import json
import hashlib
import urllib.request
import urllib.error
import ssl
import uuid
import time


TOKEN = "CF_API_TOKEN_REDACTED"
ACCT = "80ba4de511365824283fec3678626c75"
PROJECT = "lab-site"
DIST = r"C:\Users\kfigh\lab_site\dist"


ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def collect_manifest(dist_dir):
    """Walk dist/, return {relpath: sha256}."""
    manifest = {}
    for root, dirs, files in os.walk(dist_dir):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, dist_dir).replace(os.sep, '/')
            with open(full, 'rb') as fp:
                data = fp.read()
            manifest[rel] = hashlib.sha256(data).hexdigest()
    return manifest


def post_multipart(url, fields, files=None, raw=False):
    """fields: dict of name->str, files: dict of name->(filename, bytes)"""
    boundary = uuid.uuid4().hex
    parts = []
    for name, val in fields.items():
        parts.append(f"--{boundary}\r\n".encode())
        parts.append(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        parts.append(val.encode("utf-8") if isinstance(val, str) else val)
        parts.append(b"\r\n")
    for name, (filename, data) in (files or {}).items():
        parts.append(f"--{boundary}\r\n".encode())
        ctype = "application/octet-stream"
        if filename.endswith(".html"): ctype = "text/html"
        elif filename.endswith(".css"): ctype = "text/css"
        elif filename.endswith(".js"): ctype = "application/javascript"
        elif filename.endswith(".svg"): ctype = "image/svg+xml"
        elif filename.endswith(".json"): ctype = "application/json"
        parts.append(f'Content-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'.encode())
        parts.append(f"Content-Type: {ctype}\r\n\r\n".encode())
        parts.append(data)
        parts.append(b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    body = b"".join(parts)
    req = urllib.request.Request(
        url, data=body, method="POST",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        }
    )
    try:
        resp = urllib.request.urlopen(req, timeout=600, context=ctx)
        return resp.status, json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def main():
    print("=== Collecting manifest ===")
    manifest = collect_manifest(DIST)
    print(f"Total files: {len(manifest)}")
    total_size = 0
    for root, dirs, files in os.walk(DIST):
        for f in files:
            total_size += os.path.getsize(os.path.join(root, f))
    print(f"Total size: {total_size // 1024} KB")

    # Step 1: check-missing
    print("\n=== /pages/assets/check-missing ===")
    status, data = post_multipart(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCT}/pages/assets/check-missing",
        {"manifest": json.dumps(manifest)},
    )
    print(f"Status: {status}")
    if not data.get("success"):
        print("Error:", json.dumps(data, indent=2)[:1000])
        return
    print("Response keys:", list(data.get("result", {}).keys()))
    print(json.dumps(data["result"], indent=2)[:500])

    # Step 2: upload missing files
    print("\n=== /pages/assets/upload ===")
    # Upload in batches
    files_to_upload = []
    for root, dirs, files in os.walk(DIST):
        for f in files:
            full = os.path.join(root, f)
            rel = os.path.relpath(full, DIST).replace(os.sep, '/')
            with open(full, 'rb') as fp:
                data = fp.read()
            files_to_upload.append((rel, data))
    print(f"Files to upload: {len(files_to_upload)}")

    # Pages upload endpoint accepts a single file at a time
    # Use the JWT in headers
    upload_url = f"https://api.cloudflare.com/client/v4/accounts/{ACCT}/pages/assets/upload"
    uploaded = 0
    for relpath, data in files_to_upload:
        # Pages uses 'hash' = SHA256 of the file content as filename
        file_hash = hashlib.sha256(data).hexdigest()
        fields = {
            "hash": file_hash,
        }
        # Send file as 'file' field
        status, resp = post_multipart(
            upload_url,
            fields,
            files={"file": (relpath, data)},
        )
        if status != 200:
            print(f"  Upload FAILED {relpath}: {status} {resp}")
            return
        uploaded += 1
        if uploaded % 20 == 0 or uploaded == len(files_to_upload):
            print(f"  Uploaded {uploaded}/{len(files_to_upload)}")
    print(f"All uploaded: {uploaded}")

    # Step 3: create deployment
    print("\n=== /pages/projects/lab-site/deployments ===")
    # The final hash of all uploaded = sha256 of concatenated file hashes, sorted
    all_hashes = sorted(manifest.values())
    final_hash = hashlib.sha256("".join(all_hashes).encode("utf-8")).hexdigest()
    status, data = post_multipart(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCT}/pages/projects/{PROJECT}/deployments",
        {
            "manifest": json.dumps(manifest),
            "deployment-trigger": json.dumps({"type": "api"}),
        },
    )
    print(f"Status: {status}")
    print(json.dumps(data, indent=2)[:2000])


if __name__ == "__main__":
    main()
