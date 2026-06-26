"""FastAPI сервер для AI-консьержа."""

import logging
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from ..shared.config import settings
from ..shared.db import init_db
from .bot import get_bot
from .schemas import ChatRequest, ChatResponse, HealthResponse

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup/shutdown."""
    await init_db()
    bot = get_bot()
    # Прогрев RAG
    await bot.rag.load()
    logger.info("Concierge server started")
    yield
    logger.info("Concierge server stopped")


app = FastAPI(
    title="Whitewill AI Concierge",
    version="0.1.0-demo",
    description="AI-консьерж для элитной недвижимости (RU + EN)",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    from datetime import datetime

    return HealthResponse(
        status="ok",
        version="0.1.0-demo",
        llm_mode="mock" if settings.use_mock_llm else "yandexgpt",
        database="sqlite" if "sqlite" in settings.database_url else "postgresql",
        timestamp=datetime.utcnow(),
    )


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest) -> ChatResponse:
    bot = get_bot()
    try:
        return await bot.handle(req)
    except Exception as e:
        logger.exception("Chat handler error")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket) -> None:
    await websocket.accept()
    bot = get_bot()
    session_id = websocket.query_params.get("session_id", "demo-session")

    try:
        while True:
            data = await websocket.receive_json()
            req = ChatRequest(
                session_id=data.get("session_id", session_id),
                message=data.get("message", ""),
                lang=data.get("lang"),
                source="web",
            )
            response = await bot.handle(req)
            await websocket.send_json(response.model_dump())
    except WebSocketDisconnect:
        logger.info(f"Client {session_id} disconnected")


@app.get("/")
async def root() -> HTMLResponse:
    """Простая HTML-страница для тестирования."""

    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Whitewill AI Concierge — Demo</title>
        <style>
            body { font-family: 'Inter', system-ui; max-width: 600px; margin: 40px auto; padding: 20px; }
            #chat { border: 1px solid #ddd; border-radius: 8px; padding: 16px; height: 400px; overflow-y: auto; background: #fafafa; }
            .msg { margin: 8px 0; padding: 8px 12px; border-radius: 8px; max-width: 80%; white-space: pre-wrap; }
            .user { background: #2c3e50; color: white; margin-left: auto; }
            .bot { background: white; border: 1px solid #eee; }
            .meta { font-size: 11px; color: #888; margin-top: 4px; }
            .msg.bot code { background: #f4ecd8; padding: 2px 6px; border-radius: 4px; font-family: ui-monospace, monospace; color: #6b4f1d; }
            .msg.bot b { color: #2c3e50; }
            .msg.bot div { margin-top: 2px; }
            #input { display: flex; gap: 8px; margin-top: 12px; }
            input { flex: 1; padding: 10px; border: 1px solid #ddd; border-radius: 6px; }
            button { padding: 10px 20px; background: #c9a96e; color: white; border: none; border-radius: 6px; cursor: pointer; }
            button:hover { background: #b8954f; }
            h1 { color: #2c3e50; }
            .lang-toggle { display: flex; gap: 4px; margin-bottom: 8px; }
            .lang-toggle button { padding: 4px 10px; font-size: 12px; background: #eee; color: #333; }
            .lang-toggle button.active { background: #c9a96e; color: white; }
        </style>
    </head>
    <body>
        <h1>🏛 Whitewill AI Concierge</h1>
        <p style="color: #666;">Demo MVP • RAG • Bitrix24 integration</p>
        <div class="lang-toggle">
            <button id="lang-ru" class="active" onclick="setLang('ru')">RU</button>
            <button id="lang-en" onclick="setLang('en')">EN</button>
        </div>
        <div id="chat"></div>
        <div id="input">
            <input id="msg" placeholder="Напишите сообщение..." onkeypress="if(event.key==='Enter')send()">
            <button onclick="send()">Send</button>
        </div>
        <script>
            const sessionId = 'demo-' + Math.random().toString(36).slice(2, 11);
            let currentLang = 'ru';

            const i18n = {
                ru: {
                    placeholder: 'Напишите сообщение...',
                    greeting: 'Здравствуйте! Я AI-ассистент Whitewill. Помогу подобрать элитную недвижимость. Какая цель покупки?',
                    matchedLabel: '📍 Подобрано',
                    crmLabel: '✅ Передан в CRM',
                },
                en: {
                    placeholder: 'Type a message...',
                    greeting: "Hello! I'm Whitewill's AI assistant. I'll help you find luxury real estate. What's the purpose of your purchase?",
                    matchedLabel: '📍 Matched',
                    crmLabel: '✅ Sent to CRM',
                },
            };

            function setLang(lang) {
                currentLang = lang;
                document.getElementById('lang-ru').classList.toggle('active', lang === 'ru');
                document.getElementById('lang-en').classList.toggle('active', lang === 'en');
                document.getElementById('msg').placeholder = i18n[lang].placeholder;
                document.getElementById('chat').innerHTML = '<div class="msg bot">' + i18n[lang].greeting + '<div class="meta">session_id: ' + sessionId + '</div></div>';
            }

            setLang('ru');

            async function send() {
                const input = document.getElementById('msg');
                const chat = document.getElementById('chat');
                const text = input.value.trim();
                if (!text) return;

                chat.innerHTML += '<div class="msg user">' + escapeHtml(text) + '</div>';
                input.value = '';

                const res = await fetch('/api/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ session_id: sessionId, message: text, lang: currentLang })
                });
                const data = await res.json();

                const t = i18n[currentLang];
                const meta = 'state: ' + data.state + ' • score: ' + data.score.toFixed(2) + ' • ' + data.latency_ms + 'ms';
                chat.innerHTML += '<div class="msg bot">' + md(data.reply) + '<div class="meta">' + meta + '</div></div>';
                if (data.matched_properties && data.matched_properties.length > 0) {
                    chat.innerHTML += '<div class="msg bot" style="background: #f0f0e0;">' + t.matchedLabel + ': ' +
                        data.matched_properties.map(p => escapeHtml(p.title)).join(', ') + '</div>';
                }
                if (data.crm_lead_id) {
                    chat.innerHTML += '<div class="msg bot" style="background: #d4f4dd;">' + t.crmLabel + ': ' + escapeHtml(data.crm_lead_id) + '</div>';
                }
                chat.scrollTop = chat.scrollHeight;
            }

            function escapeHtml(s) {
                return String(s).replace(/[&<>"']/g, c => ({
                    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
                }[c]));
            }

            // Минимальный markdown: **жирный**, `код`, переносы строк
            function md(s) {
                return escapeHtml(s)
                    .replace(/`([^`]+)`/g, '<code>$1</code>')
                    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
                    .replace(/\n/g, '<br>');
            }
        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html)


def run() -> None:
    """Запуск через python -m."""
    uvicorn.run(
        "src.concierge.server:app",
        host="0.0.0.0",
        port=8001,
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    run()
