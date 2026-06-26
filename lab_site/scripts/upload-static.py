"""
Upload Astro dist/ to Cloudflare KV (static:{path-with-leading-slash} = base64 value).

Использование: cd C:/Users/kfigh/lab_site && python scripts/upload-static.py
"""
import os
import sys
import json
import base64
import urllib.request
import urllib.error
import ssl

ACCT = '80ba4de511365824283fec3678626c75'
NS = 'c9d44152187e4ac18f4a44b895ea0c4b'
TOKEN = 'CF_API_TOKEN_REDACTED'
DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'dist')

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE


def upload():
    files = []
    for root, _, fnames in os.walk(DIST):
        for f in fnames:
            full = os.path.join(root, f)
            rel = '/' + os.path.relpath(full, DIST).replace(os.sep, '/')
            with open(full, 'rb') as fp:
                data = fp.read()
            files.append((rel, data))
    print(f'{len(files)} files, {sum(len(d) for _, d in files) // 1024} KB')

    keys = [
        {'key': f'static:{rel}', 'value': base64.b64encode(data).decode(), 'base64': True}
        for rel, data in files
    ]
    req = urllib.request.Request(
        f'https://api.cloudflare.com/client/v4/accounts/{ACCT}/storage/kv/namespaces/{NS}/bulk',
        data=json.dumps(keys).encode(),
        method='PUT',
        headers={'Authorization': f'Bearer {TOKEN}', 'Content-Type': 'application/json'},
    )
    try:
        resp = urllib.request.urlopen(req, timeout=300, context=ctx)
        print('OK:', resp.status, resp.read().decode()[:200])
        # Show first few written keys for sanity
        print('Written keys (first 5):')
        for k in keys[:5]:
            print(' ', k['key'], f'({len(k["value"])} b64 chars)')
    except urllib.error.HTTPError as e:
        print('Err:', e.code, e.read().decode()[:500])
        sys.exit(1)


if __name__ == '__main__':
    upload()
