"""
send_email.py — Stage 3c: email-дайджест подписчикам.

Использование:
  python send_email.py <slug>
  python send_email.py <slug> --dry-run            # в tmp/, не отправлять
  python send_email.py <slug> --to=me@example.com  # отправить одному

Требует (.env):
  SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD
  EMAIL_FROM  (default: "Лаборатория желаний <noreply@pulab.online>")
  EMAIL_LIST  (файл с 1 email на строку, default: data/email_list.txt)
"""
from __future__ import annotations

import argparse
import os
import smtplib
import ssl
import sys
import time
from datetime import datetime
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import formataddr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import state  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
LAB_SITE_ROOT = Path("C:/Users/kfigh/lab_site")
TEMPLATE_HTML = SKILL_ROOT / "templates" / "announcement-email.html"
EMAIL_LIST = SKILL_ROOT / "data" / "email_list.txt"
TMP_DIR = SKILL_ROOT / "tmp"

try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass


def _load_env():
    env_path = SKILL_ROOT / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())


_load_env()


def load_metadata(slug: str) -> dict:
    p = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "metadata.json"
    if not p.exists():
        p = Path("C:/Users/kfigh/wish_librarian/output/library") / slug / "metadata.json"
    import json
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def _markdown_bold_to_html(text: str) -> str:
    """Превратить **текст** в <b>текст</b> для email HTML."""
    return re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)


def extract_bullets(slug: str, limit: int = 7) -> list[str]:
    """Достать 5-7 тезисов из summary.md."""
    p = LAB_SITE_ROOT / "src" / "data" / "books" / slug / "summary.md"
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith(("- ", "* ", "• ")) and len(line) > 8:
            out.append(_markdown_bold_to_html(line[2:].strip()[:200]))
            if len(out) >= limit:
                break
    return out


def extract_quote(slug: str) -> str | None:
    """Первая цитата из scientific.md или summary.md (если есть blockquote)."""
    for fname in ("scientific.md", "summary.md"):
        p = LAB_SITE_ROOT / "src" / "data" / "books" / slug / fname
        if not p.exists():
            continue
        for line in p.read_text(encoding="utf-8").splitlines():
            s = line.strip()
            if s.startswith(">") and len(s) > 5:
                return s.lstrip(">").strip()
    return None


def _resolve_cover_url(slug: str) -> str:
    """Найти обложку книги в public/books или вернуть fallback."""
    books_dir = LAB_SITE_ROOT / "public" / "books"
    exact = books_dir / f"{slug}.jpg"
    if exact.exists():
        return f"https://app.pulab.ru/books/{slug}.jpg"
    # fuzzy match по началу slug
    for f in books_dir.glob("*.jpg"):
        if f.stem.startswith(slug):
            return f"https://app.pulab.ru/books/{f.name}"
    return "https://app.pulab.ru/cover.jpg"


def build_html(slug: str, meta: dict, live_url: str) -> str:
    template = TEMPLATE_HTML.read_text(encoding="utf-8")
    title = meta.get("title", "")
    author = meta.get("author", "")
    year = meta.get("year", "")
    cover_url = _resolve_cover_url(slug)

    bullets = extract_bullets(slug)
    if not bullets:
        bullets = ["(идеи появятся после наполнения конспекта)"]
    bullets_html = "<ul>" + "".join(f"<li style='margin-bottom:6px;'>{b}</li>" for b in bullets) + "</ul>"

    quote = extract_quote(slug)
    quote_block = ""
    if quote:
        quote_block = (
            f'<tr><td style="padding:8px 32px 16px 32px;">'
            f'<blockquote style="margin:0;padding:16px 20px;border-left:4px solid #7c3aed;'
            f'background:#f8f7ff;font-style:italic;color:#444;font-size:15px;line-height:1.5;">'
            f'«{quote}»</blockquote></td></tr>'
        )

    lead = (
        f"В библиотеке «Лаборатории желаний» — новая книга. "
        f"Мы сделали по ней конспект, практические советы, упражнения и подборку отзывов. "
        f"Внутри — самое ценное из идей {author}."
    )

    html = template
    html = html.replace("{title}", title)
    html = html.replace("{author}", author)
    html = html.replace("{year}", f", {year}" if year else "")
    html = html.replace("{cover_url}", cover_url)
    html = html.replace("{live_url}", live_url)
    html = html.replace("{lead}", lead)
    html = html.replace("{bullets_html}", bullets_html)
    html = html.replace("{unsubscribe_url}", f"https://app.pulab.ru/unsubscribe?book={slug}")
    # Quote block: либо вставляем готовый <tr>, либо вырезаем плейсхолдер
    if quote_block:
        html = html.replace("<!-- {quote_block} -->", quote_block)
    else:
        # убрать плейсхолдер-комментарий
        html = html.replace("<!-- {quote_block} -->", "")
    return html


def load_email_list(single_to: str | None) -> list[str]:
    if single_to:
        return [single_to]
    if not EMAIL_LIST.exists():
        return []
    out = []
    for line in EMAIL_LIST.read_text(encoding="utf-8").splitlines():
        s = line.strip()
        if s and "@" in s and not s.startswith("#"):
            out.append(s)
    return out


def send_one(smtp: smtplib.SMTP, msg: MIMEMultipart, to: str) -> tuple[bool, str]:
    try:
        smtp.sendmail(msg["From"], [to], msg.as_string())
        return True, "ok"
    except Exception as e:
        return False, str(e)


def main():
    ap = argparse.ArgumentParser(description="Send email announcement")
    ap.add_argument("slug")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--to", default=None, help="Один получатель вместо списка")
    args = ap.parse_args()

    slug = args.slug
    print(f"[email] {slug}")

    if not args.dry_run and not state.channel_pending(slug, "email"):
        print(f"[email] ✓ уже отправлено ранее. Пропуск.")
        return

    data = state.load(slug)
    live_url = data.get("live_url") or f"https://pulab.online/books/{slug}"
    meta = load_metadata(slug)
    html = build_html(slug, meta, live_url)

    # Список получателей
    recipients = load_email_list(args.to)
    if not recipients and not args.dry_run:
        print(f"[email] ✗ нет получателей (создай {EMAIL_LIST} или --to=...)", file=sys.stderr)
        sys.exit(1)
    print(f"[email] получателей: {len(recipients)}")

    if args.dry_run:
        out = TMP_DIR / f"{slug}-email-draft.html"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(html, encoding="utf-8")
        print(f"[email] DRY-RUN. HTML в {out}")
        return

    # SMTP
    host = os.environ.get("SMTP_HOST")
    port = int(os.environ.get("SMTP_PORT", "587"))
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASSWORD")
    from_addr = os.environ.get("EMAIL_FROM", "Лаборатория желаний <noreply@pulab.online>")

    if not all([host, user, password]):
        print(f"[email] ✗ SMTP_HOST/SMTP_USER/SMTP_PASSWORD не заданы", file=sys.stderr)
        sys.exit(1)

    # MIME
    msg = MIMEMultipart("alternative")
    msg["Subject"] = Header(f"📚 Новая книга: {meta.get('title', slug)}", "utf-8")
    msg["From"] = from_addr.split("<")[-1].rstrip(">").strip()
    msg["To"] = ", ".join(recipients[:3]) + (f" и ещё {len(recipients) - 3}" if len(recipients) > 3 else "")
    # Plain-text fallback
    plain = (
        f"Новая книга: {meta.get('title')}\n"
        f"Автор: {meta.get('author')}, {meta.get('year', '')}\n\n"
        f"Читать на сайте: {live_url}\n"
    )
    msg.attach(MIMEText(plain, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    # Подключение + STARTTLS
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # корпоративный MITM

    print(f"[email] подключаюсь к {host}:{port} как {user}…")
    sent_ok = 0
    sent_failed = []
    try:
        with smtplib.SMTP(host, port, timeout=30) as smtp:
            smtp.starttls(context=ctx)
            smtp.login(user, password)
            for i, to in enumerate(recipients):
                # Per-recipient To header
                m = MIMEMultipart("alternative")
                m["Subject"] = Header(f"📚 Новая книга: {meta.get('title', slug)}", "utf-8")
                m["From"] = from_addr.split("<")[-1].rstrip(">").strip()
                m["To"] = to
                m.attach(MIMEText(plain, "plain", "utf-8"))
                m.attach(MIMEText(html, "html", "utf-8"))
                ok, err = send_one(smtp, m, to)
                if ok:
                    sent_ok += 1
                else:
                    sent_failed.append((to, err))
                # Rate-limit (SMTP обычно 30/min, держим запас)
                if (i + 1) % 25 == 0:
                    time.sleep(2)
    except Exception as e:
        print(f"[email] ✗ SMTP-ошибка: {e}", file=sys.stderr)
        state.mark_channel_failed(slug, "email", f"SMTP: {e}")
        sys.exit(1)

    print(f"[email] ✓ отправлено: {sent_ok}/{len(recipients)}")
    if sent_failed:
        print(f"[email] ✗ ошибок: {len(sent_failed)}")
        for to, err in sent_failed[:5]:
            print(f"  - {to}: {err[:120]}")
        state.mark_channel_failed(slug, "email", f"{len(sent_failed)} failed of {len(recipients)}")
    else:
        state.mark_channel_posted(slug, "email")


if __name__ == "__main__":
    main()
