"""
WishCoach — FastAPI app (Phase 1+: каркас + state machine + AI + детектор + онбординг).

Запуск локально:
    uvicorn agent.main:app --reload --port 8000
    AI_FAKE_MODE=true uvicorn agent.main:app --reload --port 8000  # без ключей

Запуск в проде (Render.com):
    uvicorn agent.main:app --host 0.0.0.0 --port $PORT

Эндпоинты:
    GET  /health          — liveness/readiness
    GET  /health/d1       — readiness (D1)
    POST /admin/migrate   — применить миграции (X-Admin-Token)
    GET  /                — корневой info
    POST /coach/message                — главный диалог
    POST /coach/onboarding/tone        — выбор тона
    POST /coach/onboarding/start       — выбор старта
    POST /coach/tone                   — смена тона
    POST /coach/end                    — завершить сессию (save/complete)
    GET  /coach/session                — текущее состояние
    POST /coach/desire                 — создать желание
    GET  /coach/desires                — список активных желаний
"""

from __future__ import annotations

import os
from contextlib import AsyncExitStack, asynccontextmanager
from datetime import UTC, datetime
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from agent.ai.factory import AIError, AIUnconfiguredError
from agent.ai.fake_client import FakeAIClient
from agent.api import chat as chat_api
from agent.api import desires as desires_api
from agent.api import onboarding as onboarding_api
from agent.api import sessions as sessions_api
from agent.api import tones as tones_api
from agent.api import workbook as workbook_api
from agent.api.middleware.ratelimit import RateLimitMiddleware
from agent.channels.router import ChannelRouter
from agent.config import apply_mitm_globals, settings
from agent.core.detector import DetectorService
from agent.core.idle import IdleTimer
from agent.core.message_bus import MessageBus
from agent.core.onboarding import OnboardingService
from agent.core.session import SessionService
from agent.core.state_machine import SessionStateMachine
from agent.core.states import InvalidTransitionError
from agent.services.crisis_followup import CrisisFollowup
from agent.storage.d1_client import D1Error
from agent.storage.d1_client_async import close_d1_async, get_d1_async
from agent.storage.migrations import (
    SCHEMA_VERSION,
    apply_migrations,
    get_current_version,
)
from agent.storage.repository import Repository
from agent.utils import get_logger, setup_logging

log = get_logger("main")

IDLE_TIMEOUT_SEC = int(os.getenv("IDLE_TIMEOUT_SEC", "900"))


# === Lifespan ===

@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    log.info(
        "app.startup",
        env=settings.app_env,
        schema_version=SCHEMA_VERSION,
        verify_ssl=settings.verify_ssl,
        socks5=bool(settings.socks5_proxy),
        fake_ai=os.getenv("AI_FAKE_MODE", "").lower() in ("1", "true", "yes"),
    )
    apply_mitm_globals()

    # Phase 8: логируем MITM-дефолт на каждом старте (корпоративная среда)
    if not settings.verify_ssl or settings.socks5_proxy:
        log.warning(
            "app.mitm_enabled",
            verify_ssl=settings.verify_ssl,
            socks5=bool(settings.socks5_proxy),
            note="корпоративный MITM — SSL verify отключён. См. RUNBOOK.md#known-weaknesses",
        )
    # Phase 8: admin token fallback на service_name — слабая аутентификация в проде
    if settings.app_env == "production" and not os.environ.get("ADMIN_TOKEN"):
        log.warning(
            "app.admin_token_weak",
            fallback=settings.render_service_name,
            note="ADMIN_TOKEN не задан — /admin/* защищён именем сервиса. См. RUNBOOK.md#known-weaknesses",
        )

    async with AsyncExitStack():
        # Async storage (D1 или SQLite локальный)
        d1 = get_d1_async()
        # Для SQLite: применяем миграции (sync, один раз при старте)
        if settings.storage_backend == "sqlite_local":
            from agent.storage.d1_client import get_d1 as _get_d1_sync

            _sync_d1 = _get_d1_sync()
            current = get_current_version(client=_sync_d1)
            if current != SCHEMA_VERSION:
                log.info(
                    "app.migrations_needed",
                    current=current,
                    target=SCHEMA_VERSION,
                )
                apply_migrations(client=_sync_d1)
            else:
                log.info("app.migrations_current", version=current)
        # Repository
        repo = Repository(d1)
        # FSM
        fsm = SessionStateMachine(repo)
        # Detector
        detector = DetectorService()
        # Idle timer
        idle = IdleTimer(timeout_sec=IDLE_TIMEOUT_SEC)
        # AI client (или Fake)
        if os.getenv("AI_FAKE_MODE", "").lower() in ("1", "true", "yes"):
            ai_client: Any = FakeAIClient()
            log.info("app.ai_fake_mode_enabled")
        else:
            from agent.ai.factory import get_ai_client
            try:
                ai_client = get_ai_client(prefer="claude")
            except AIUnconfiguredError:
                ai_client = None
                log.warning("app.ai_unconfigured")
        # Workbook service (Phase 4) — shared between Onboarding и Session
        from agent.core.workbook import WorkbookService
        workbook_service = WorkbookService(repo, ai_client)
        # Onboarding
        onboarding = OnboardingService(repo, fsm, workbook_service)
        # Session
        session_service = SessionService(
            repository=repo,
            state_machine=fsm,
            onboarding=onboarding,
            detector=detector,
            idle_timer=idle,
            ai_client=ai_client,
        )
        # Message bus
        bus = MessageBus(session_service, repo)
        # Channel router
        router = ChannelRouter(bus)

        # Phase 8: crisis follow-up background-сервис (24ч soft follow-up)
        crisis_followup = CrisisFollowup(repo)
        crisis_followup.start()

        # Сохраняем в app.state
        app.state.repository = repo
        app.state.session_service = session_service
        app.state.message_bus = bus
        app.state.channel_router = router
        app.state.fsm = fsm
        app.state.idle = idle
        app.state.ai_client = ai_client
        app.state.crisis_followup = crisis_followup

        # VK Long Poll runner (Phase 7) — стартует ТОЛЬКО если задан токен.
        # Регистрируем VKAdapter в роутере (всегда — чтобы ручки могли
        # работать в тестах без реального Long Poll).
        from agent.channels.vk import VKAdapter, VKLongPollRunner
        vk_adapter = VKAdapter()
        router.register(vk_adapter)

        vk_runner: VKLongPollRunner | None = None
        if settings.has_vk and os.getenv("DISABLE_VK_POLL", "").lower() not in ("1", "true"):
            try:
                import asyncio as _asyncio
                main_loop = _asyncio.get_event_loop()
                if main_loop.is_closed():
                    main_loop = _asyncio.new_event_loop()
                    _asyncio.set_event_loop(main_loop)
                vk_runner = VKLongPollRunner(
                    token=settings.vk_group_token,
                    group_id=settings.vk_group_id,
                    message_bus=bus,
                    repository=repo,
                    loop=main_loop,
                )
                vk_runner.start()
                app.state.vk_runner = vk_runner
                log.info("app.vk_longpoll_started", group_id=settings.vk_group_id)
            except Exception:
                log.exception("app.vk_longpoll_failed")
        else:
            log.info("app.vk_longpoll_disabled", has_vk=settings.has_vk)

        log.info(
            "app.config",
            anthropic=settings.has_anthropic,
            telegram=settings.has_telegram,
            vk=settings.has_vk,
            d1=bool(settings.cf_account_id and settings.cf_d1_database_id and settings.cf_api_token),
        )

        try:
            yield
        finally:
            log.info("app.shutdown")
            await crisis_followup.stop()
            if vk_runner is not None:
                vk_runner.stop()
            await idle.shutdown()
            await close_d1_async()


# === FastAPI app ===

app = FastAPI(
    title="WishCoach",
    version="0.2.0",
    description="ИИ-коуч для подписчиков Лаборатории желаний (Phase 1+ — диалог + state machine + детектор)",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Phase 8: rate-limit ДО CORS (чтобы 429 отдавался до preflight-логики)
app.add_middleware(RateLimitMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://app.pulab.online",
        "https://pulab.online",
        "http://localhost:4321",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Exception handlers ===

@app.exception_handler(D1Error)
async def d1_error_handler(request: Request, exc: D1Error):
    log.error("d1.error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=503,
        content={"detail": "database unavailable", "error": str(exc)[:200]},
    )


@app.exception_handler(AIUnconfiguredError)
async def ai_unconfigured_handler(request: Request, exc: AIUnconfiguredError):
    log.error("ai.unconfigured", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=503,
        content={"detail": "AI provider not configured", "error": str(exc)[:200]},
    )


@app.exception_handler(AIError)
async def ai_error_handler(request: Request, exc: AIError):
    log.error("ai.error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=503,
        content={"detail": "AI temporarily unavailable", "error": str(exc)[:200]},
    )


@app.exception_handler(InvalidTransitionError)
async def invalid_transition_handler(request: Request, exc: InvalidTransitionError):
    log.error("state.invalid_transition", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"detail": "internal state machine error", "error": str(exc)[:200]},
    )


# === /health ===

class HealthResponse(BaseModel):
    status: str
    service: str
    version: str
    schema_version: str
    env: str
    time: str
    d1: dict[str, Any] | None = None
    ai: str = "unconfigured"
    phase: int = 1


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health(request: Request) -> HealthResponse:
    # Phase 8: 503 если AI не сконфигурирован И не fake_mode (k8s/Render unhealthy)
    ai_obj = getattr(request.app.state, "ai_client", None)
    fake_mode = os.getenv("AI_FAKE_MODE", "").lower() in ("1", "true", "yes")
    if ai_obj is None and not fake_mode:
        log.warning("health.ai_unconfigured_503")
        # Возвращаем JSON 503 (liveness-проверка Render увидит fail)
        return JSONResponse(
            status_code=503,
            content={
                "status": "ai_unconfigured",
                "service": settings.render_service_name,
                "version": "0.2.0",
                "schema_version": SCHEMA_VERSION,
                "env": settings.app_env,
                "time": datetime.now(UTC).isoformat(),
                "ai": "unconfigured",
                "phase": 1,
            },
        )

    d1_status: dict[str, Any] = None
    try:
        d1 = get_d1_async()
        await d1.fetch_one("SELECT 1 AS ok")
        d1_status = {"ok": True}
    except D1Error as e:
        log.warning("health.d1_error", error=str(e))
        d1_status = {"ok": False, "error": str(e)[:200]}
    except Exception:
        log.exception("health.d1_unexpected")
        d1_status = {"ok": False, "error": "unexpected"}

    # Определяем тип AI-клиента
    ai_label = "unconfigured"
    if ai_obj is not None:
        cls_name = type(ai_obj).__name__
        if "Fake" in cls_name:
            ai_label = "fake"
        elif "Claude" in cls_name:
            ai_label = "claude"
        elif "Yandex" in cls_name:
            ai_label = "yandex"
        else:
            ai_label = cls_name.lower()

    return HealthResponse(
        status="ok",
        service=settings.render_service_name,
        version="0.2.0",
        schema_version=SCHEMA_VERSION,
        env=settings.app_env,
        time=datetime.now(UTC).isoformat(),
        d1=d1_status,
        ai=ai_label,
        phase=1,
    )


@app.get("/health/ai", tags=["health"])
async def health_ai(request: Request) -> JSONResponse:
    """Всегда 200: показывает тип AI клиента. Для мониторинга (без 503)."""
    ai_obj = getattr(request.app.state, "ai_client", None)
    fake_mode = os.getenv("AI_FAKE_MODE", "").lower() in ("1", "true", "yes")
    if ai_obj is None and not fake_mode:
        return JSONResponse({"ai": "unconfigured", "ok": False})
    if fake_mode:
        return JSONResponse({"ai": "fake", "ok": True})
    cls_name = type(ai_obj).__name__ if ai_obj else ""
    if "Claude" in cls_name:
        return JSONResponse({"ai": "claude", "ok": True})
    if "Yandex" in cls_name:
        return JSONResponse({"ai": "yandex", "ok": True})
    return JSONResponse({"ai": "unknown", "ok": ai_obj is not None})


@app.get("/health/d1", tags=["health"])
async def health_d1() -> JSONResponse:
    try:
        d1 = get_d1_async()
        await d1.fetch_one("SELECT 1 AS ok")
        return JSONResponse({"status": "ready", "d1": "ok"})
    except Exception as e:
        log.exception("readiness.d1_failed")
        return JSONResponse(
            {"status": "not_ready", "d1": "fail", "error": str(e)[:200]},
            status_code=503,
        )


# === /admin/migrate ===

async def require_admin_token(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    expected = os.environ.get("ADMIN_TOKEN") or settings.render_service_name
    if not x_admin_token or x_admin_token != expected:
        raise HTTPException(status_code=401, detail="invalid admin token")


class MigrateRequest(BaseModel):
    force: bool = False


class MigrateResponse(BaseModel):
    applied: dict[str, str]
    schema_version: str
    current_version: str | None


@app.post(
    "/admin/migrate",
    response_model=MigrateResponse,
    tags=["admin"],
    dependencies=[Depends(require_admin_token)],
)
async def migrate(req: MigrateRequest) -> MigrateResponse:
    current = get_current_version()
    if current == SCHEMA_VERSION and not req.force:
        log.info("migrate.noop", current=current, target=SCHEMA_VERSION)
        return MigrateResponse(applied={}, schema_version=SCHEMA_VERSION, current_version=current)
    log.info("migrate.start", current=current, target=SCHEMA_VERSION, force=req.force)
    result = apply_migrations()
    new_current = get_current_version()
    log.info("migrate.done", applied=list(result.keys()), new_current=new_current)
    return MigrateResponse(applied=result, schema_version=SCHEMA_VERSION, current_version=new_current)


# === Coach API (роутеры) ===

app.include_router(chat_api.router, prefix="/coach", tags=["coach"])
app.include_router(onboarding_api.router, prefix="/coach", tags=["coach"])
app.include_router(tones_api.router, prefix="/coach", tags=["coach"])
app.include_router(sessions_api.router, prefix="/coach", tags=["coach"])
app.include_router(desires_api.router, prefix="/coach", tags=["coach"])
app.include_router(workbook_api.router, prefix="/coach", tags=["coach"])


# === Корневой ===

@app.get("/", tags=["root"])
async def root() -> dict[str, Any]:
    return {
        "service": "wishcoach",
        "version": "0.2.0",
        "schema_version": SCHEMA_VERSION,
        "phase": 1,
        "description": "ИИ-коуч для подписчиков Лаборатории желаний. Phase 1+ готов.",
        "endpoints": {
            "health": "/health",
            "health_ai": "/health/ai",
            "d1_health": "/health/d1",
            "docs": "/docs",
            "migrate": "POST /admin/migrate (X-Admin-Token)",
            "coach_message": "POST /coach/message (X-Client-Id)",
            "coach_onboarding_tone": "POST /coach/onboarding/tone",
            "coach_onboarding_start": "POST /coach/onboarding/start",
            "coach_tone": "POST /coach/tone",
            "coach_end": "POST /coach/end",
            "coach_session": "GET /coach/session",
            "coach_desire": "POST /coach/desire",
            "coach_desires": "GET /coach/desires",
            "coach_workbook_list": "GET /coach/workbook/list",
            "coach_workbook_start": "POST /coach/workbook/start",
            "coach_workbook_answer": "POST /coach/workbook/answer",
            "coach_workbook_progress": "GET /coach/workbook/progress",
        },
    }


__all__ = ["app"]
