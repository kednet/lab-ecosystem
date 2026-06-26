"""
Kednet-агент — persistent WebSocket-клиент между Kednet (ноут kfigh) и Chief Agent (VPS).

Держит один long-lived WS к ws://89.108.88.74:7070/ws, авто-reconnect 5/10/30/60 сек.
По команде Chief (type="run") — spawn'ит `.venv\\python.exe -u <script> [args]` в нужном cwd,
стримит stdout/stderr чанками, шлёт артефакты, шлёт exit с duration.

По команде Chief (type="scaffold") — создаёт папку, пишет agent.py + requirements.txt + README.md.

Конфиг: kednet_agent.config.json в этой же папке.
Зависимости: pip install websockets==12.0 (см. requirements.txt).
Запуск как сервис: см. nssm/install-kednet-agent.ps1.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import signal
import subprocess
import sys
import time
import uuid
from pathlib import Path
from typing import Any

try:
    import websockets
    from websockets.exceptions import ConnectionClosed
except ImportError:
    print("FATAL: pip install websockets==12.0", file=sys.stderr)
    raise

HERE = Path(__file__).resolve().parent

# ── Логирование ──────────────────────────────────────────────
LOG_FILE = HERE / "logs" / "kednet_agent.log"
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(sys.stdout)
    ]
)
log = logging.getLogger("kednet_agent")

HOSTNAME = os.environ.get("COMPUTERNAME", "unknown")
PLATFORM = sys.platform

# ── Subprocess-менеджер ─────────────────────────────────────
class JobManager:
    """Хранит запущенные jobs по jobId, умеет их cancel'ить."""

    def __init__(self) -> None:
        self._jobs: dict[str, dict[str, Any]] = {}

    def track(self, job_id: str, proc: subprocess.Popen, cwd: str) -> None:
        self._jobs[job_id] = {
            "proc": proc,
            "cwd": cwd,
            "started_at": time.time(),
        }
        log.info("job %s tracked (pid=%d, cwd=%s)", job_id, proc.pid, cwd)

    def cancel(self, job_id: str) -> bool:
        info = self._jobs.get(job_id)
        if not info:
            log.warning("cancel: jobId %s not found", job_id)
            return False
        proc: subprocess.Popen = info["proc"]
        if proc.poll() is not None:
            log.info("cancel: job %s already exited (rc=%s)", job_id, proc.returncode)
            return True
        log.info("cancel: SIGTERM → job %s (pid=%d)", job_id, proc.pid)
        try:
            proc.terminate()
            return True
        except Exception as e:
            log.error("cancel failed: %s", e)
            return False

    def cleanup(self, job_id: str) -> None:
        self._jobs.pop(job_id, None)


jobs = JobManager()


# ── Скаффолд (создание папки агента) ────────────────────────
TEMPLATES: dict[str, str] = {
    "subprocess": '''# {{AGENT_ID}} — agent.py
# Chief-managed agent skeleton (subprocess transport).
# Chief (VPS) spawns this script via .venv/bin/python -u agent.py <action> [args].

import argparse
import json
import sys


def cmd_hello(args):
    print(json.dumps({"status": "ok", "agent": "{{AGENT_ID}}", "version": "0.1.0"}))


def cmd_run(args):
    print(f"Running with: {vars(args)}")
    # TODO: implement
    return 0


def main():
    p = argparse.ArgumentParser(description="{{AGENT_DISPLAY_NAME}}")
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="action", required=True)

    s_hello = sub.add_parser("hello", help="ping agent")
    s_hello.set_defaults(func=cmd_hello)

    s_run = sub.add_parser("run", help="run main action")
    s_run.add_argument("--input", required=True)
    s_run.set_defaults(func=cmd_run)

    args = p.parse_args()
    rc = args.func(args) or 0
    sys.exit(rc)


if __name__ == "__main__":
    main()
''',
    "http": '''# {{AGENT_ID}} — agent.py
# Chief-managed agent skeleton (HTTP transport).
# Run as FastAPI server; Chief POSTs to /actions/<id>.

from fastapi import FastAPI
import uvicorn

app = FastAPI(title="{{AGENT_ID}}")


@app.get("/health")
def health():
    return {"status": "ok", "agent": "{{AGENT_ID}}", "version": "0.1.0"}


@app.post("/actions/{action_id}")
def run_action(action_id: str, body: dict):
    # TODO: dispatch by action_id
    return {"status": "received", "action": action_id, "body": body}


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8080)
''',
    "remote": '''# {{AGENT_ID}} — agent.py
# Chief-managed agent skeleton (remote transport, Kednet via WebSocket).
# Chief отправляет команду Kednet-агенту, Kednet-агент spawn'ит python -u agent.py.

import argparse
import json
import sys


def cmd_hello(args):
    print(json.dumps({"status": "ok", "agent": "{{AGENT_ID}}", "version": "0.1.0"}))


def cmd_run(args):
    print(f"Running with: {vars(args)}")
    # TODO: implement
    return 0


def main():
    p = argparse.ArgumentParser(description="{{AGENT_DISPLAY_NAME}}")
    p.add_argument("--dry-run", action="store_true")
    sub = p.add_subparsers(dest="action", required=True)

    s_hello = sub.add_parser("hello")
    s_hello.set_defaults(func=cmd_hello)

    s_run = sub.add_parser("run")
    s_run.add_argument("--input", required=True)
    s_run.set_defaults(func=cmd_run)

    args = p.parse_args()
    rc = args.func(args) or 0
    sys.exit(rc)


if __name__ == "__main__":
    main()
''',
}

REQUIREMENTS_TMPL = '''# {{AGENT_ID}} — Python deps
# .venv\\Scripts\\pip install -r requirements.txt
{{DEPS}}
'''

README_TMPL = '''# {{AGENT_ID}}

Chief-managed agent ({{AGENT_DISPLAY_NAME}}).

## Local run

```bash
.venv\\Scripts\\activate  # Windows
python -u agent.py hello
python -u agent.py run --input "test" --dry-run
```

## Chief connection

- Registered in Chief's registry (`/api/agents`).
- Kednet-агент запускает этот скрипт по команде Chief через WebSocket.
- Артефакты (картинки/аудио) появятся в TG @ChiefAgentbot для approve.
'''


def _render(tmpl: str, agent_id: str, display_name: str, **extra: str) -> str:
    out = tmpl.replace("{{AGENT_ID}}", agent_id).replace("{{AGENT_DISPLAY_NAME}}", display_name)
    for k, v in extra.items():
        out = out.replace("{{" + k + "}}", v)
    return out


def do_scaffold(data: dict, skills_dir: str) -> dict:
    """Синхронная работа с файлами (допустимо из async-контекста)."""
    agent_id = data["agentId"]
    cwd = data["cwd"]
    template_type = data.get("templateType", "subprocess")
    display_name = data.get("displayName", agent_id)
    scripts_entry = data.get("scriptsEntry")

    if template_type not in TEMPLATES:
        raise ValueError(f"unknown templateType: {template_type}")

    base = Path(cwd).resolve()
    base_root = Path(skills_dir).resolve()
    try:
        base.relative_to(base_root)
    except ValueError:
        raise ValueError(f"cwd {cwd} is outside skillsDir {skills_dir}")
    if base.exists():
        raise FileExistsError(f"cwd already exists: {cwd}")
    base.mkdir(parents=True)

    files: list[str] = []
    (base / "agent.py").write_text(
        _render(TEMPLATES[template_type], agent_id, display_name),
        encoding="utf-8"
    )
    files.append("agent.py")

    deps = data.get("requirements") or "# (no deps)"
    (base / "requirements.txt").write_text(
        _render(REQUIREMENTS_TMPL, agent_id, display_name, DEPS=deps),
        encoding="utf-8"
    )
    files.append("requirements.txt")

    (base / "README.md").write_text(
        _render(README_TMPL, agent_id, display_name),
        encoding="utf-8"
    )
    files.append("README.md")

    if scripts_entry:
        scripts_dir = base / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        entry_name = Path(scripts_entry).name
        (scripts_dir / entry_name).write_text(
            f"# Entry point for {agent_id}\n# Run via Kednet-агент: python -u {scripts_entry} <action> [args]\n",
            encoding="utf-8"
        )
        files.append(f"scripts/{entry_name}")

    log.info("scaffold done: %s → %s (files=%s)", agent_id, base, files)
    return {"agentId": agent_id, "files": files, "requirements": data.get("requirements") or []}


# ── Запуск subprocess по команде run ─────────────────────────
def _resolve_python(cwd: Path) -> str:
    """Ищет .venv\\python.exe; иначе системный python.exe."""
    venv_py = cwd / ".venv" / "Scripts" / "python.exe"
    if venv_py.exists():
        return str(venv_py)
    return sys.executable


def _resolve_interpreter(cwd: Path, declared: str | None) -> str:
    if not declared:
        return _resolve_python(cwd)
    if declared.lower().startswith("python"):
        return _resolve_python(cwd)
    return declared


def _detect_artifact(path: Path) -> dict:
    ext = path.suffix.lower().lstrip(".")
    kind_map = {
        "jpg": "image", "jpeg": "image", "png": "image", "webp": "image", "gif": "image",
        "mp3": "audio", "wav": "audio", "ogg": "audio", "m4a": "audio",
        "mp4": "video", "mov": "video", "webm": "video",
        "json": "json", "txt": "text", "md": "text", "csv": "text",
    }
    kind = kind_map.get(ext, "file")
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    return {"path": str(path), "kind": kind, "sizeBytes": size}


def _build_env(cwd: Path, declared_env: dict, env_keys: list | None) -> dict:
    """Собрать окружение для subprocess."""
    env = os.environ.copy()
    if env_keys is not None:
        env = {k: env[k] for k in env_keys if k in env}
    env.update(declared_env)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUNBUFFERED"] = "1"
    env["LC_ALL"] = "C.UTF-8"
    return env


async def _safe_send(ws: Any, payload: dict) -> None:
    """Awaitable wrapper, единая точка обработки ошибок отправки."""
    try:
        await ws.send(json.dumps(payload, ensure_ascii=False))
    except Exception as e:
        log.warning("ws.send failed: %s", e)


async def _read_stream_to_chief(stream: Any, ws: Any, job_id: str, kind: str) -> None:
    """Читает subprocess.Popen-стрим построчно, шлёт в Chief. Блокирующий read — в executor."""
    loop = asyncio.get_event_loop()
    try:
        while True:
            line = await loop.run_in_executor(None, stream.readline)
            if not line:
                return
            await _safe_send(ws, {"type": kind, "jobId": job_id, "data": {"chunk": line}})
    except Exception as e:
        log.warning("job %s stream %s error: %s", job_id, kind, e)


async def _watch_subprocess(ws: Any, job_id: str, proc: subprocess.Popen, cwd: Path, start_ts: float, timeout_ms: int) -> None:
    """Стрим stdout/stderr параллельно, ждёт exit, шлёт artifact+exit."""
    loop = asyncio.get_event_loop()

    stdout_task = asyncio.create_task(_read_stream_to_chief(proc.stdout, ws, job_id, "stdout"))
    stderr_task = asyncio.create_task(_read_stream_to_chief(proc.stderr, ws, job_id, "stderr"))

    try:
        if timeout_ms > 0:
            try:
                rc = await asyncio.wait_for(
                    loop.run_in_executor(None, proc.wait),
                    timeout=timeout_ms / 1000
                )
            except asyncio.TimeoutError:
                log.warning("job %s timeout after %dms, SIGTERM", job_id, timeout_ms)
                try:
                    proc.terminate()
                except Exception:
                    pass
                rc = await loop.run_in_executor(None, proc.wait)
        else:
            rc = await loop.run_in_executor(None, proc.wait)
    finally:
        # Дать стрим-таскам дослать последние строки
        try:
            await asyncio.wait_for(asyncio.gather(stdout_task, stderr_task), timeout=5)
        except asyncio.TimeoutError:
            stdout_task.cancel()
            stderr_task.cancel()

    duration_ms = int((time.time() - start_ts) * 1000)

    # Сканируем артефакты
    artifacts: list[dict] = []
    try:
        for p in cwd.rglob("*"):
            if not p.is_file():
                continue
            if p.name in {"agent.py", "requirements.txt", "README.md"}:
                continue
            if p.stat().st_mtime >= start_ts - 1:
                artifacts.append(_detect_artifact(p))
    except Exception as e:
        log.warning("job %s artifact scan: %s", job_id, e)

    for art in artifacts:
        await _safe_send(ws, {"type": "artifact", "jobId": job_id, "data": art})

    err_msg = None
    if rc != 0 and timeout_ms and duration_ms >= timeout_ms:
        err_msg = f"timeout after {timeout_ms}ms"

    await _safe_send(ws, {
        "type": "exit", "jobId": job_id,
        "data": {"exitCode": rc, "durationMs": duration_ms, "errorMessage": err_msg}
    })
    jobs.cleanup(job_id)
    log.info("job %s exit rc=%d duration=%dms artifacts=%d",
             job_id, rc, duration_ms, len(artifacts))


async def run_subprocess(ws: Any, job_id: str, data: dict, skills_dir: str) -> None:
    """Spawn subprocess, стримит stdout/stderr/artifact/exit в Chief."""
    cwd_raw = data["cwd"]
    cwd = Path(cwd_raw).resolve()
    base_root = Path(skills_dir).resolve()
    try:
        cwd.relative_to(base_root)
    except ValueError:
        log.error("job %s: cwd outside skillsDir (%s)", job_id, cwd)
        await _safe_send(ws, {
            "type": "exit", "jobId": job_id,
            "data": {"exitCode": -1, "durationMs": 0,
                     "errorMessage": f"cwd outside skillsDir: {cwd}"}
        })
        return

    if not cwd.exists():
        await _safe_send(ws, {
            "type": "exit", "jobId": job_id,
            "data": {"exitCode": -1, "durationMs": 0,
                     "errorMessage": f"cwd not found: {cwd}"}
        })
        return

    command = _resolve_interpreter(cwd, data.get("command"))
    args = data.get("args") or []
    declared_env = data.get("env") or {}
    env_keys = data.get("envKeys")
    timeout_ms = int(data.get("timeoutMs") or 0)
    env = _build_env(cwd, declared_env, env_keys)

    log.info("job %s spawn: %s %s (cwd=%s)", job_id, command, args, cwd)
    start_ts = time.time()

    try:
        proc = subprocess.Popen(
            [command, *args],
            cwd=str(cwd),
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    except Exception as e:
        log.error("job %s: spawn failed: %s", job_id, e)
        await _safe_send(ws, {
            "type": "exit", "jobId": job_id,
            "data": {"exitCode": -1,
                     "durationMs": int((time.time() - start_ts) * 1000),
                     "errorMessage": f"spawn failed: {e}"}
        })
        return

    jobs.track(job_id, proc, str(cwd))
    await _safe_send(ws, {
        "type": "started", "jobId": job_id,
        "data": {"pid": proc.pid, "startedAt": start_ts}
    })

    # Не await'им — пусть идёт параллельно, обработчик сообщений остаётся свободным
    asyncio.create_task(_watch_subprocess(ws, job_id, proc, cwd, start_ts, timeout_ms))


# ── Главный WS-цикл ─────────────────────────────────────────
BACKOFFS = [5, 10, 30, 60]


def _scan_skills(skills_dir: str) -> list[dict]:
    base = Path(skills_dir)
    if not base.exists():
        return []
    out: list[dict] = []
    for entry in base.iterdir():
        if not entry.is_dir():
            continue
        if not (entry / "agent.py").exists():
            continue
        has_venv = (entry / ".venv" / "Scripts" / "python.exe").exists()
        out.append({
            "id": entry.name,
            "path": str(entry),
            "hasVenv": has_venv,
        })
    return out


def load_config() -> dict:
    cfg_path = HERE / "kednet_agent.config.json"
    if not cfg_path.exists():
        log.error("Config not found: %s", cfg_path)
        sys.exit(1)
    cfg = json.loads(cfg_path.read_text("utf-8"))
    if "chiefUrl" not in cfg or "token" not in cfg:
        log.error("chiefUrl/token missing in config")
        sys.exit(1)
    return cfg


async def _handle_message(ws: Any, msg: dict, skills_dir: str) -> None:
    typ = msg.get("type")
    job_id = msg.get("jobId")
    data = msg.get("data") or {}

    if typ == "welcome":
        log.info("welcome received (serverTime=%s)", data.get("serverTime"))
        return

    if typ == "ping":
        await _safe_send(ws, {"type": "pong"})
        return

    if typ == "cancel":
        if job_id and jobs.cancel(job_id):
            log.info("cancel ack: %s", job_id)
        return

    if typ == "run":
        if not job_id:
            log.error("run without jobId")
            return
        await run_subprocess(ws, job_id, data, skills_dir)
        return

    if typ == "scaffold":
        # sync fs work — выполним в executor, чтобы не блокировать loop
        loop = asyncio.get_event_loop()
        try:
            result = await loop.run_in_executor(None, do_scaffold, data, skills_dir)
        except Exception as e:
            log.error("scaffold failed: %s", e)
            result = {"agentId": data.get("agentId"), "error": str(e), "files": []}
        await _safe_send(ws, {
            "type": "scaffold.done",
            "jobId": job_id or str(uuid.uuid4()),
            "data": result
        })
        return

    if typ == "open":
        path = data.get("path")
        if path and Path(path).exists():
            try:
                subprocess.Popen(["explorer", "/select,", path])
                log.info("explorer /select %s", path)
            except Exception as e:
                log.warning("explorer failed: %s", e)
        return

    log.warning("unknown message type: %r", typ)


async def run(cfg: dict) -> None:
    chief_url = cfg["chiefUrl"]
    token = cfg["token"]
    skills_dir = cfg.get("skillsDir") or str(Path("C:/Users/kfigh").resolve())
    ws_path = cfg.get("wsPath", "/ws")
    full_url = chief_url.rstrip("/") + ws_path

    skills_detected = _scan_skills(skills_dir)
    log.info("skills detected: %d", len(skills_detected))

    backoff_idx = 0
    while True:
        try:
            log.info("connecting → %s", full_url)
            async with websockets.connect(full_url, max_size=16 * 1024 * 1024) as ws:
                backoff_idx = 0
                await _safe_send(ws, {
                    "type": "hello",
                    "data": {
                        "version": "1.0.0",
                        "hostname": HOSTNAME,
                        "os": "Windows",
                        "platform": PLATFORM,
                        "skillsDetected": skills_detected,
                        "token": token,
                    }
                })
                log.info("hello sent (hostname=%s)", HOSTNAME)

                async def ping_loop() -> None:
                    while True:
                        await asyncio.sleep(30)
                        try:
                            await ws.send(json.dumps({"type": "pong"}, ensure_ascii=False))
                        except Exception:
                            return

                ping_task = asyncio.create_task(ping_loop())

                try:
                    async for raw in ws:
                        try:
                            msg = json.loads(raw)
                        except json.JSONDecodeError:
                            log.warning("bad JSON from chief: %s", str(raw)[:200])
                            continue
                        await _handle_message(ws, msg, skills_dir)
                finally:
                    ping_task.cancel()
                    try:
                        await ping_task
                    except Exception:
                        pass
        except (ConnectionClosed, OSError, asyncio.IncompleteReadError) as e:
            delay = BACKOFFS[min(backoff_idx, len(BACKOFFS) - 1)]
            log.warning("WS disconnect (%s): reconnect in %ds", e, delay)
            backoff_idx += 1
            await asyncio.sleep(delay)
        except Exception as e:
            log.exception("WS loop crashed: %s", e)
            await asyncio.sleep(30)


def main() -> None:
    parser = argparse.ArgumentParser(description="Kednet-agent: WS-bridge Kednet ↔ Chief")
    parser.add_argument("--once", action="store_true",
                        help="для smoke-test: вывести hello и завершить")
    args = parser.parse_args()

    cfg = load_config()
    log.info("config loaded: chiefUrl=%s skillsDir=%s",
             cfg["chiefUrl"], cfg.get("skillsDir", "<default>"))

    if args.once:
        print(json.dumps({
            "type": "hello",
            "data": {
                "version": "1.0.0",
                "hostname": HOSTNAME,
                "os": "Windows",
                "skillsDetected": _scan_skills(cfg.get("skillsDir", "C:/Users/kfigh"))
            }
        }, ensure_ascii=False))
        return

    if sys.platform != "win32":
        def _stop(*_a: Any) -> None:
            log.info("signal received, exiting")
            sys.exit(0)
        for s in (signal.SIGTERM, signal.SIGINT):
            signal.signal(s, _stop)

    try:
        asyncio.run(run(cfg))
    except KeyboardInterrupt:
        log.info("interrupted, exiting")


if __name__ == "__main__":
    main()