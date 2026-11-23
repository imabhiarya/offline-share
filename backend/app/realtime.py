"""In-process WebSocket hub used for live notifications and delivery.

The server runs as a single process (one uvicorn worker), which comfortably serves
50 PCs; all live connections are therefore held here.
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional

from fastapi import WebSocket

from datetime import timezone as _tz


def _utcnow() -> datetime:
    return datetime.now(_tz.utc).replace(tzinfo=None)

log = logging.getLogger("offline_share.realtime")


@dataclass(eq=False)
class Conn:
    ws: WebSocket
    user_id: int
    session_id: str
    device_id: Optional[int]
    ip: str
    connected_at: datetime = field(default_factory=_utcnow)
    last_ping: datetime = field(default_factory=_utcnow)


class Hub:
    def __init__(self) -> None:
        self._conns: dict[int, set[Conn]] = {}
        self._lock = threading.Lock()
        self.loop: Optional[asyncio.AbstractEventLoop] = None

    # ---- registry -------------------------------------------------------
    def add(self, conn: Conn) -> None:
        with self._lock:
            self._conns.setdefault(conn.user_id, set()).add(conn)

    def remove(self, conn: Conn) -> None:
        with self._lock:
            s = self._conns.get(conn.user_id)
            if s:
                s.discard(conn)
                if not s:
                    self._conns.pop(conn.user_id, None)

    def is_online(self, user_id: int) -> bool:
        with self._lock:
            return bool(self._conns.get(user_id))

    def online_user_ids(self) -> set[int]:
        with self._lock:
            return set(self._conns)

    def online_device_ids(self) -> set[int]:
        with self._lock:
            return {c.device_id for s in self._conns.values() for c in s if c.device_id}

    def connection_count(self) -> int:
        with self._lock:
            return sum(len(s) for s in self._conns.values())

    def close_session(self, session_id: str) -> None:
        with self._lock:
            targets = [c for s in self._conns.values() for c in s if c.session_id == session_id]
        for c in targets:
            self._schedule(self._close(c))

    def close_user(self, user_id: int) -> None:
        with self._lock:
            targets = list(self._conns.get(user_id, ()))
        for c in targets:
            self._schedule(self._close(c))

    async def _close(self, c: Conn) -> None:
        try:
            await c.ws.close(code=4401)
        except Exception:
            pass

    # ---- sending ----------------------------------------------------------
    async def send_user_async(self, user_id: int, message: dict[str, Any]) -> int:
        with self._lock:
            targets = list(self._conns.get(user_id, ()))
        data = json.dumps(message, default=str)
        sent = 0
        for c in targets:
            try:
                await c.ws.send_text(data)
                sent += 1
            except Exception:
                self.remove(c)
        return sent

    def _schedule(self, coro) -> None:  # noqa: ANN001
        loop = self.loop
        if loop is None or loop.is_closed():
            coro.close()
            return
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None
        if running is loop:
            loop.create_task(coro)
        else:
            asyncio.run_coroutine_threadsafe(coro, loop)

    def send_user(self, user_id: int, message: dict[str, Any]) -> None:
        """Thread-safe fire-and-forget send (usable from sync request handlers)."""
        self._schedule(self.send_user_async(user_id, message))

    def broadcast(self, message: dict[str, Any], user_ids: Optional[set[int]] = None) -> None:
        for uid in (user_ids if user_ids is not None else self.online_user_ids()):
            self.send_user(uid, message)


hub = Hub()
