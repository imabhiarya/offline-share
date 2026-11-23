"""Background jobs: delivery retry, scheduled backups, retention cleanup, device presence."""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional

from . import database
from .models import Device, Transfer, TransferRecipient, UserSession, utcnow

log = logging.getLogger("offline_share.runtime")

_restart_cb: Optional[Callable[[], None]] = None
_tasks: list[asyncio.Task] = []


def set_restart_callback(cb: Callable[[], None]) -> None:
    global _restart_cb
    _restart_cb = cb


def request_restart() -> None:
    if _restart_cb:
        _restart_cb()
    else:
        log.warning("Restart requested but no restart handler is installed (development mode)")


def next_backup_time(s: dict, now: Optional[datetime] = None) -> Optional[str]:
    if not s.get("auto_backup"):
        return None
    now = now or datetime.now()
    hh, mm = (int(x) for x in str(s.get("backup_time") or "20:00").split(":"))
    cand = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if s.get("backup_schedule") == "weekly":
        wd = int(s.get("backup_weekday") or 6)
        cand += timedelta(days=(wd - cand.weekday()) % 7)
        if cand <= now:
            cand += timedelta(days=7)
    elif cand <= now:
        cand += timedelta(days=1)
    return cand.isoformat(timespec="minutes")


async def _loop(name: str, interval: float, fn) -> None:  # noqa: ANN001
    await asyncio.sleep(2)
    while True:
        try:
            await fn()
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Background job %s failed", name)
        await asyncio.sleep(interval)


async def delivery_job() -> None:
    from .services.delivery import worker_tick
    await worker_tick()


_last_backup_slot: Optional[str] = None


async def backup_job() -> None:
    global _last_backup_slot
    from .services import backup, settings as app_settings
    with database.SessionLocal() as db:
        s = app_settings.get_all(db)
        if not s.get("auto_backup"):
            return
        from .models import BackupHistory
        last = (db.query(BackupHistory).filter(BackupHistory.kind == "scheduled")
                .order_by(BackupHistory.created_at.desc()).first())
    now = datetime.now()
    hh, mm = (int(x) for x in str(s.get("backup_time") or "20:00").split(":"))
    due = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if now < due:
        return
    if s.get("backup_schedule") == "weekly" and now.weekday() != int(s.get("backup_weekday") or 6):
        return
    slot = due.isoformat()
    if _last_backup_slot == slot:
        return
    # skip if a scheduled backup already exists for this slot (e.g. after a restart)
    if last and (last.created_at + (datetime.now() - utcnow())) >= due:
        _last_backup_slot = slot
        return
    _last_backup_slot = slot
    log.info("Running scheduled backup")
    await asyncio.to_thread(backup.create_backup, "scheduled", bool(s.get("backup_include_files", True)))
    backup.prune(int(s.get("backup_keep_count") or 14))


async def retention_job() -> None:
    from .services import settings as app_settings
    from .services.storage import clear_tmp
    from .routers.history import hard_delete_transfer
    from .routers.transfers import cleanup_stale_uploads
    with database.SessionLocal() as db:
        s = app_settings.get_all(db)
        now = utcnow()
        rd, sd, hd = (int(s.get(k) or 0) for k in ("received_retention_days", "sent_retention_days",
                                                    "history_retention_days"))
        if rd:
            db.query(TransferRecipient).filter(
                TransferRecipient.created_at < now - timedelta(days=rd), TransferRecipient.purged.is_(False),
                TransferRecipient.status.in_(("delivered", "read"))).update(
                {"purged": True, "is_deleted": True}, synchronize_session=False)
        if sd:
            db.query(Transfer).filter(Transfer.created_at < now - timedelta(days=sd),
                                      Transfer.sender_deleted.is_(False)).update(
                {"sender_deleted": True}, synchronize_session=False)
        db.commit()
        if hd:
            old = db.query(Transfer).filter(Transfer.created_at < now - timedelta(days=hd)).limit(500).all()
            for t in old:
                hard_delete_transfer(db, t)
            db.commit()
        # Transfers whose every party has removed them: free the disk space (records stay unless history retention)
        db.query(UserSession).filter(UserSession.expires_at < now - timedelta(days=7)).delete()
        db.commit()
        cleanup_stale_uploads(db)
    clear_tmp_old()


def clear_tmp_old() -> None:
    import time
    from .config import config
    for p in config.tmp_path.glob("*"):
        try:
            if p.is_file() and time.time() - p.stat().st_mtime > 6 * 3600:
                p.unlink()
        except OSError:
            pass


_last_online: set[int] = set()


async def presence_job() -> None:
    """Broadcast device online/offline changes (agent heartbeat timeouts) to connected admins."""
    global _last_online
    from .realtime import hub
    from .services.devices import device_status
    with database.SessionLocal() as db:
        browser_ids = hub.online_device_ids()
        now_online = {d.id for d in db.query(Device).all() if device_status(db, d, browser_ids)["online"]}
    if now_online != _last_online:
        changed = now_online ^ _last_online
        _last_online = now_online
        hub.broadcast({"type": "devices.changed", "changed": sorted(changed)})


def start_background() -> None:
    loop = asyncio.get_running_loop()
    for name, interval, fn in (("delivery", 10, delivery_job), ("backup", 30, backup_job),
                               ("retention", 3600, retention_job), ("presence", 15, presence_job)):
        _tasks.append(loop.create_task(_loop(name, interval, fn)))


async def stop_background() -> None:
    for t in _tasks:
        t.cancel()
    for t in _tasks:
        try:
            await t
        except (asyncio.CancelledError, Exception):
            pass
    _tasks.clear()
