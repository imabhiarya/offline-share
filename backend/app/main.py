"""FastAPI application: API routers, WebSocket hub, LAN restriction, static frontend."""
from __future__ import annotations

import asyncio
import json
import logging
import logging.handlers
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from urllib.parse import urlparse

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from . import database, runtime
from .config import APP_NAME, APP_VERSION, config
from .deps import SESSION_COOKIE, load_session
from .migrations import init_database
from .models import Device, utcnow
from .realtime import Conn, hub
from .routers import auth, dashboard, devices, files, history, inbox, system, transfers, users
from .services import delivery
from .services.common import ip_allowed

log = logging.getLogger("offline_share")


def setup_logging() -> None:
    config.log_path.mkdir(parents=True, exist_ok=True)
    root = logging.getLogger()
    if any(getattr(h, "_offline_share", False) for h in root.handlers):
        return
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    fh = logging.handlers.RotatingFileHandler(config.log_path / "offline_share.log", maxBytes=10 * 1024 * 1024,
                                              backupCount=10, encoding="utf-8")
    fh.setFormatter(fmt)
    fh._offline_share = True  # type: ignore[attr-defined]
    root.addHandler(fh)
    if sys.stderr and sys.stderr.isatty():
        sh = logging.StreamHandler()
        sh.setFormatter(fmt)
        root.addHandler(sh)
    root.setLevel(logging.INFO)


def frontend_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)) / "frontend_dist"
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging()
    init_database()
    import time as _time
    dashboard.STARTED = _time.time()
    hub.loop = asyncio.get_running_loop()
    runtime.start_background()
    log.info("%s %s started on %s:%s (data: %s)", APP_NAME, APP_VERSION, config.host, config.port, config.home)
    yield
    await runtime.stop_background()
    log.info("%s stopped", APP_NAME)


app = FastAPI(title=APP_NAME, version=APP_VERSION, lifespan=lifespan, docs_url="/api/docs", redoc_url=None,
              openapi_url="/api/openapi.json")

CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
       "connect-src 'self' ws: wss:; font-src 'self' data:; frame-src 'self' blob:; object-src 'self' blob:; "
       "base-uri 'self'; form-action 'self'; frame-ancestors 'self'")


@app.middleware("http")
async def lan_guard(request: Request, call_next):
    ip = request.client.host if request.client else ""
    if not ip_allowed(ip, config.allowed_subnets):
        log.warning("Rejected request from non-LAN address %s %s", ip, request.url.path)
        return PlainTextResponse("Access denied: this server only accepts connections from the office LAN.", 403)
    response = await call_next(request)
    h = response.headers
    h.setdefault("X-Content-Type-Options", "nosniff")
    h.setdefault("X-Frame-Options", "SAMEORIGIN")
    h.setdefault("Referrer-Policy", "no-referrer")
    h.setdefault("Content-Security-Policy", CSP)
    if request.url.path.startswith("/api/"):
        h.setdefault("Cache-Control", "no-store")
    if config.https:
        h.setdefault("Strict-Transport-Security", "max-age=31536000")
    return response


for r in (auth.router, dashboard.router, transfers.router, inbox.router, history.router, devices.router,
          devices.agent_router, devices.section_router, users.router, files.router, system.router,
          system.health_page_router):
    app.include_router(r)


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception):
    log.exception("Unhandled error on %s %s", request.method, request.url.path)
    return JSONResponse({"detail": "Internal server error. The error has been logged."}, status_code=500)


# --------------------------------------------------------------------------- websocket
@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket):
    ip = ws.client.host if ws.client else ""
    if not ip_allowed(ip, config.allowed_subnets):
        await ws.close(code=4403)
        return
    origin = ws.headers.get("origin")
    if origin and urlparse(origin).netloc != ws.headers.get("host"):
        await ws.close(code=4403)  # cross-site WebSocket hijacking protection
        return
    with database.SessionLocal() as db:
        found = load_session(db, ws.cookies.get(SESSION_COOKIE))
        if not found:
            await ws.close(code=4401)
            return
        user, sess = found
        user_id, session_id, device_id = user.id, sess.id, sess.device_id
        _touch_device(db, device_id, user_id)
    await ws.accept()
    conn = Conn(ws=ws, user_id=user_id, session_id=session_id, device_id=device_id, ip=ip)
    hub.add(conn)
    hub.broadcast({"type": "presence", "user_id": user_id, "online": True})
    await ws.send_text(json.dumps({"type": "hello", "user_id": user_id}))
    await delivery.deliver_queue_for_user(user_id)
    try:
        while True:
            raw = await ws.receive_text()
            try:
                msg = json.loads(raw)
            except ValueError:
                continue
            kind = msg.get("type")
            if kind == "ping":
                conn.last_ping = utcnow()
                with database.SessionLocal() as db:
                    if not load_session(db, ws.cookies.get(SESSION_COOKIE)):
                        await ws.close(code=4401)
                        break
                    _touch_device(db, device_id, user_id)
                await ws.send_text(json.dumps({"type": "pong"}))
            elif kind == "ack":
                ids = [int(i) for i in msg.get("recipient_ids", [])][:200]
                if ids:
                    await asyncio.to_thread(_ack, user_id, ids, ip)
    except WebSocketDisconnect:
        pass
    except Exception:
        log.exception("WebSocket error")
    finally:
        hub.remove(conn)
        if not hub.is_online(user_id):
            hub.broadcast({"type": "presence", "user_id": user_id, "online": False})


def _touch_device(db, device_id, user_id) -> None:  # noqa: ANN001
    if not device_id:
        return
    d = db.get(Device, device_id)
    if d:
        d.last_browser_at = d.last_seen_at = utcnow()
        d.last_user_id = user_id
        db.commit()


def _ack(user_id: int, ids: list[int], ip: str) -> None:
    from .models import TransferRecipient
    with database.SessionLocal() as db:
        rows = db.query(TransferRecipient).filter(TransferRecipient.id.in_(ids),
                                                  TransferRecipient.recipient_user_id == user_id).all()
        delivery.acknowledge(db, rows, ip)


# --------------------------------------------------------------------------- frontend (SPA)
_dist = frontend_dir()
if (_dist / "assets").exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")


@app.get("/{full_path:path}", include_in_schema=False)
async def spa(full_path: str):
    if full_path.startswith(("api/", "ws")):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    candidate = (_dist / full_path).resolve()
    if full_path and candidate.is_file() and _dist.resolve() in candidate.parents:
        return FileResponse(candidate)
    index = _dist / "index.html"
    if index.exists():
        return FileResponse(index, headers={"Cache-Control": "no-cache"})
    return PlainTextResponse("OFFLINE SHARE API is running. Frontend build not found – run `npm run build` in "
                             "frontend/.", 200)
