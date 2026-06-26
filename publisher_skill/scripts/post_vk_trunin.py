"""
post_vk_trunin.py — разовый пост ВК по Трунину «От мечты до успеха».
Берёт текст из .message.txt, прикрепляет обложку книги, отправляет на стену pulabru (237295798).
"""
import os
import sys
import json
import ssl
import urllib.request
import urllib.parse

# UTF-8 в stdout
for _s in (sys.stdout, sys.stderr):
    try: _s.reconfigure(encoding="utf-8")
    except Exception: pass

# MITM
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

TOKEN = os.environ["VK_ACCESS_TOKEN"]
GROUP_ID = int(os.environ.get("VK_GROUP_ID", "237295798"))
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
SKILL_DIR = os.path.dirname(SCRIPT_DIR)
MESSAGE_FILE = os.path.join(SKILL_DIR, "tmp", "vk_trunin.message.txt")
COVER_PATH = "C:/Users/kfigh/lab_site/public/books/ot-mechty-do-uspeha-trunin-r-a.jpg"


def vk_api(method, params):
    params["access_token"] = TOKEN
    params["v"] = "5.199"
    url = f"https://api.vk.com/method/{method}?" + urllib.parse.urlencode(params)
    try:
        with urllib.request.urlopen(url, timeout=30, context=ctx) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"error": {"error_msg": str(e)}}


def upload_cover():
    """Загрузить обложку на стену. Возвращает attachment 'photo123_456' или None."""
    if not os.path.exists(COVER_PATH):
        print(f"[vk] WARN: cover не найден: {COVER_PATH}")
        return None

    # 1. photos.getWallUploadServer
    r = vk_api("photos.getWallUploadServer", {"group_id": GROUP_ID})
    if "error" in r:
        print(f"[vk] ✗ getWallUploadServer: {r['error']}", file=sys.stderr)
        return None
    upload_url = r["response"]["upload_url"]

    # 2. multipart upload
    boundary = "----VKPubSkill"
    with open(COVER_PATH, "rb") as f:
        photo_data = f.read()
    body = (
        f"--{boundary}\r\nContent-Disposition: form-data; name=\"photo\"; filename=\"cover.jpg\"\r\nContent-Type: application/octet-stream\r\n\r\n"
    ).encode("utf-8") + photo_data + f"\r\n--{boundary}--\r\n".encode("utf-8")
    req = urllib.request.Request(upload_url, data=body, headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    try:
        with urllib.request.urlopen(req, timeout=60, context=ctx) as r:
            upload_resp = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        print(f"[vk] ✗ upload: {e}", file=sys.stderr)
        return None

    # 3. photos.saveWallPhoto
    r = vk_api("photos.saveWallPhoto", {
        "group_id": GROUP_ID,
        "photo": upload_resp["photo"],
        "server": upload_resp["server"],
        "hash": upload_resp["hash"],
    })
    if "error" in r:
        print(f"[vk] ✗ saveWallPhoto: {r['error']}", file=sys.stderr)
        return None
    photo = r["response"][0]
    return f"photo{photo['owner_id']}_{photo['id']}"


def main():
    if not os.path.exists(MESSAGE_FILE):
        print(f"[ERR] no message file: {MESSAGE_FILE}")
        return 1
    text = open(MESSAGE_FILE, encoding="utf-8").read().strip()
    print(f"[vk] post length: {len(text)} chars")
    print("---")
    print(text)
    print("---")

    # Загружаем обложку
    attachment = upload_cover()
    if attachment:
        print(f"[vk] cover attached: {attachment}")
    else:
        print("[vk] пост пойдёт без картинки (обложка не загружена)")

    params = {
        "owner_id": -GROUP_ID,
        "from_group": 1,
        "message": text,
    }
    if attachment:
        params["attachments"] = attachment

    r = vk_api("wall.post", params)
    if "error" in r:
        print(f"[ERR] VK: {r['error']}")
        return 2
    post_id = r.get("response", {}).get("post_id")
    print(f"[OK] posted: post_id={post_id}, group=vk.com/pulabru (id={GROUP_ID})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
