"""
FastAPI-сервис для генерации книг.

Архитектура:
1. Worker POST /internal/jobs/{id}/enqueue с { userId, bookQuery, queryType }.
2. Worker пишет job в KV со статусом 'pending'.
3. python-service polling'ом каждые 2 сек берёт pending jobs (через Worker API).
4. Обрабатывает через WL, шлёт прогресс через callback.
5. По завершении — Worker кладёт результат в R2 и book:{slug} в KV.

Endpoints:
- GET  /health              — liveness
- POST /internal/heartbeat  — для cron-пинга (UptimeRobot)
- POST /internal/poll       — Worker дёргает, отдаёт pending jobs
- POST /internal/callback   — НЕ используется; Worker сам ходит по URL
"""
from __future__ import annotations

import asyncio
import json
import os
import tempfile
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, Header, HTTPException
from loguru import logger
from pydantic import BaseModel

from wishlibrarian_adapter import process_book
from copywriter import SocialCopywriter, copywrite_book_endpoint


def json_dumps(obj) -> str:
    """json.dumps with sensible defaults."""
    return json.dumps(obj, ensure_ascii=False, default=str)

load_dotenv()

WORKER_CALLBACK_URL = os.getenv("WORKER_CALLBACK_URL", "http://127.0.0.1:8787")
PYTHON_SERVICE_TOKEN = os.getenv("PYTHON_SERVICE_TOKEN", "dev-token-change-me")
WL_OUTPUT_DIR = Path(os.getenv("WL_OUTPUT_DIR", tempfile.gettempdir())) / "wl-output"
WL_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
MAX_CONCURRENT_JOBS = int(os.getenv("MAX_CONCURRENT_JOBS", "2"))
POLL_INTERVAL_SEC = float(os.getenv("POLL_INTERVAL_SEC", "2"))

# ────────────────────────────────────────────────
# Poller — фоновый таск, забирает jobs
# ────────────────────────────────────────────────
job_queue: asyncio.Queue = asyncio.Queue()
in_flight: set[str] = set()


class EnqueueRequest(BaseModel):
    jobId: str
    userId: str
    bookQuery: str
    queryType: str  # 'url' | 'title'


class ProgressUpdate(BaseModel):
    stage: str
    progress: int
    message: str = ""


async def send_progress(job_id: str, user_id: str, update: ProgressUpdate):
    """Шлёт прогресс в Worker через callback."""
    url = f"{WORKER_CALLBACK_URL.rstrip('/')}/internal/jobs/{job_id}/progress"
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.post(
                url,
                json={
                    "stage": update.stage,
                    "progress": update.progress,
                    "message": update.message,
                    "userId": user_id,
                },
                headers={"Authorization": f"Bearer {PYTHON_SERVICE_TOKEN}"},
            )
            if r.status_code >= 400:
                logger.warning(f"Worker callback {r.status_code}: {r.text[:200]}")
    except Exception as e:
        logger.warning(f"Worker callback failed for job {job_id}: {e}")


async def send_done(job_id: str, user_id: str, result: dict, files: dict):
    """Шлёт финальный callback с результатом и файлами (multipart/form-data).

    Worker распарсит multipart, положит файлы в R2, запишет book:{slug} в KV.
    """
    url = f"{WORKER_CALLBACK_URL.rstrip('/')}/internal/jobs/{job_id}/done"
    # Сопоставление kind -> поле multipart
    field_for_kind = {
        "summary": "files[summary]",
        "workbook": "files[workbook]",
        "tips": "files[tips]",
        "cover": "files[cover]",
    }
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            form = []
            form.append(("result", (None, json_dumps(result), "application/json")))
            for kind, path in files.items():
                p = Path(path)
                if not p.exists() or p.stat().st_size == 0:
                    continue
                # Грузим в память — файлы маленькие (md/jpg, до ~1 МБ)
                with open(p, "rb") as f:
                    data = f.read()
                form.append((field_for_kind.get(kind, f"files[{kind}]"), (p.name, data, "application/octet-stream")))
            r = await client.post(
                url,
                files=form,
                headers={"Authorization": f"Bearer {PYTHON_SERVICE_TOKEN}"},
            )
            if r.status_code >= 400:
                logger.error(f"Worker done callback {r.status_code}: {r.text[:200]}")
                raise RuntimeError(f"Worker rejected done: {r.status_code}")
    except Exception as e:
        logger.error(f"Worker done callback failed: {e}")
        raise


def _progress_factory(job_id: str, user_id: str):
    def cb(stage: str, progress: int, message: str = ""):
        # Синхронный callback — планируем async отправку
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                asyncio.create_task(send_progress(job_id, user_id, ProgressUpdate(
                    stage=stage, progress=progress, message=message,
                )))
        except RuntimeError:
            pass
    return cb


async def process_one(req: EnqueueRequest):
    """Запускает WL, шлёт прогресс, по завершении — done callback."""
    job_id = req.jobId
    user_id = req.userId
    query = req.bookQuery

    logger.info(f"[{job_id}] start: {req.queryType}={query}")
    await send_progress(job_id, user_id, ProgressUpdate("starting", 0, "Приняли в работу"))

    # Папка для артефактов (Worker потом их прочитает и положит в R2)
    work_dir = WL_OUTPUT_DIR / job_id
    work_dir.mkdir(parents=True, exist_ok=True)

    loop = asyncio.get_event_loop()

    try:
        # Определяем URL
        if req.queryType == "url":
            url = query
        else:
            # Если пользователь дал название — пробуем koob.ru поиск
            # TODO: в будущем — нормальный парсинг koob.ru search
            # Сейчас для простоты — берём как есть и пусть WL упадёт если не URL
            url = f"https://www.koob.ru/search?q={query}"

        # Запускаем WL в executor'е (он синхронный и блокирующий — до 3 мин)
        progress_cb = _progress_factory(job_id, user_id)
        result = await loop.run_in_executor(
            None,
            lambda: process_book(url, work_dir, progress_cb=progress_cb),
        )

        logger.info(f"[{job_id}] WL done: {result.title} ({len(result.files)} files)")

        # Отправляем done + файлы
        await send_done(
            job_id,
            user_id,
            {
                "slug": result.slug,
                "title": result.title,
                "author": result.author,
                "year": result.year,
                "description": result.description,
            },
            result.files,
        )

    except Exception as e:
        logger.exception(f"[{job_id}] failed: {e}")
        await send_progress(job_id, user_id, ProgressUpdate("error", 0, str(e)[:200]))


async def poll_loop():
    """Каждые POLL_INTERVAL_SEC дёргает Worker, забирает pending jobs."""
    while True:
        try:
            url = f"{WORKER_CALLBACK_URL.rstrip('/')}/internal/jobs/pending"
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {PYTHON_SERVICE_TOKEN}"},
                )
                if r.status_code == 200:
                    jobs = r.json().get("jobs", [])
                    for j in jobs:
                        if j["jobId"] not in in_flight:
                            in_flight.add(j["jobId"])
                            req = EnqueueRequest(**j)
                            asyncio.create_task(_safe_process(req))
        except Exception as e:
            logger.debug(f"poll error: {e}")
        await asyncio.sleep(POLL_INTERVAL_SEC)


async def _safe_process(req: EnqueueRequest):
    try:
        await process_one(req)
    finally:
        in_flight.discard(req.jobId)


# ────────────────────────────────────────────────
# FastAPI app
# ────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Запускаем polling
    task = asyncio.create_task(poll_loop())
    logger.info("python-service started, polling Worker")
    yield
    task.cancel()


app = FastAPI(title="lab-site-python", version="0.1.0", lifespan=lifespan)


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "lab-site-python",
        "wl_output_dir": str(WL_OUTPUT_DIR),
        "in_flight": list(in_flight),
        "timestamp": time.time(),
    }


@app.post("/internal/heartbeat")
async def heartbeat():
    """Endpoint для UptimeRobot (просто чтобы сервис не засыпал)."""
    return {"ok": True, "ts": time.time()}


# Для дебага — ручной запуск процесса (минуя очередь)
@app.post("/internal/process-now")
async def process_now(req: EnqueueRequest, authorization: str = Header(None)):
    if authorization != f"Bearer {PYTHON_SERVICE_TOKEN}":
        raise HTTPException(401, "Bad token")
    asyncio.create_task(_safe_process(req))
    return {"accepted": True, "jobId": req.jobId}


# ────────────────────────────────────────────────
# Publisher (Фаза 5): AI-копирайтер для анонсов
# ────────────────────────────────────────────────
class CopywriteRequest(BaseModel):
    bookSlug: str
    """ Если не задан — будет найден в WL output по slug. """
    summaryPath: Optional[str] = None
    """ Если true — пропустить AI и сразу вернуть fallback. """
    fallbackOnly: bool = False


@app.post("/internal/copywrite")
async def copywrite(req: CopywriteRequest, authorization: str = Header(None)):
    """
    Эндпоинт для Worker'а: генерирует VK/TG/meta тексты по книге.
    Использует wish_librarian/agent/ai/factory.py если AI_PROVIDER задан.
    """
    if authorization != f"Bearer {PYTHON_SERVICE_TOKEN}":
        raise HTTPException(401, "Bad token")

    result = await copywrite_book_endpoint(book_slug=req.bookSlug)
    return result
