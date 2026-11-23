"""Dashboard statistics (all from the database) and notifications."""
from __future__ import annotations

import os
import platform
import shutil
import time
from datetime import datetime, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..models import utcnow as _utcnow
from ..config import APP_VERSION, config
from ..database import get_db
from ..deps import Ctx, get_ctx, require
from ..models import Device, Notification, RepoFile, Transfer, TransferRecipient, User
from ..realtime import hub
from ..services import settings as app_settings
from ..services import storage
from ..services.common import iso
from ..services.devices import serialise_device

router = APIRouter(prefix="/api", tags=["dashboard"])
STARTED = time.time()
_storage_cache: dict = {"at": 0.0, "used": 0}


def storage_used() -> int:
    if time.time() - _storage_cache["at"] > 60:
        _storage_cache.update(at=time.time(), used=storage.dir_size(config.storage_path))
    return _storage_cache["used"]


def server_health() -> dict:
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory().percent
    except Exception:
        cpu = mem = None
    disk = shutil.disk_usage(config.storage_path)
    db_size = sum(p.stat().st_size for p in config.db_path.parent.glob("offline_share.db*") if p.exists())
    return {"status": "online", "version": APP_VERSION, "uptime_seconds": int(time.time() - STARTED),
            "cpu_percent": cpu, "memory_percent": mem, "disk_total": disk.total, "disk_free": disk.free,
            "disk_percent": round((disk.total - disk.free) / disk.total * 100, 1), "db_size": db_size,
            "ws_connections": hub.connection_count(), "online_users": len(hub.online_user_ids()),
            "host": platform.node(), "platform": f"{platform.system()} {platform.release()}",
            "python": platform.python_version(), "pid": os.getpid(), "server_ip": config.public_ip,
            "port": config.port, "https": config.https}


@router.get("/dashboard")
def dashboard(scope: str = "auto", ctx: Ctx = Depends(require("dashboard")), db: Session = Depends(get_db)):
    glob = ctx.is_admin and scope != "mine"
    me = ctx.user.id
    T, TR = Transfer, TransferRecipient
    sent_q = db.query(T) if glob else db.query(T).filter(T.sender_user_id == me)
    recv_q = db.query(TR) if glob else db.query(TR).filter(TR.recipient_user_id == me)
    out_q = db.query(TR) if glob else db.query(TR).join(T).filter(T.sender_user_id == me)

    def count_status(*sts: str) -> int:
        return out_q.filter(TR.status.in_(sts)).count()

    if glob:
        data_total = db.query(func.coalesce(func.sum(T.total_size), 0)).scalar()
    else:
        sent_bytes = db.query(func.coalesce(func.sum(T.total_size), 0)).filter(T.sender_user_id == me).scalar()
        recv_bytes = (db.query(func.coalesce(func.sum(T.total_size), 0)).join(TR, TR.transfer_id == T.id)
                      .filter(TR.recipient_user_id == me).scalar())
        data_total = (sent_bytes or 0) + (recv_bytes or 0)
    stats = {"total_sent": sent_q.count(), "total_received": recv_q.count(),
             "delivered": count_status("delivered", "read"), "pending": count_status("pending", "sent"),
             "failed": count_status("failed"), "total_data": int(data_total or 0),
             "unread": db.query(TR).filter(TR.recipient_user_id == me, TR.status != "read", TR.status != "failed",
                                           TR.is_deleted.is_(False), TR.purged.is_(False)).count()}

    # 7-day activity
    today = datetime.now().date()
    days = [today - timedelta(days=i) for i in range(6, -1, -1)]
    start = datetime.combine(days[0], datetime.min.time())
    # stored timestamps are UTC; shift into server local time for the day buckets
    offset = datetime.now() - _utcnow()
    sent_rows = sent_q.filter(T.created_at >= start - timedelta(days=1)).with_entities(T.created_at, T.total_size).all()
    recv_rows = (recv_q.join(T, T.id == TR.transfer_id) if not glob else recv_q.join(T, T.id == TR.transfer_id)) \
        .filter(T.created_at >= start - timedelta(days=1)).with_entities(T.created_at).all()
    by_day = {d: {"date": d.isoformat(), "sent": 0, "received": 0, "bytes": 0} for d in days}
    for created, size in sent_rows:
        d = (created + offset).date()
        if d in by_day:
            by_day[d]["sent"] += 1
            by_day[d]["bytes"] += size or 0
    for (created,) in recv_rows:
        d = (created + offset).date()
        if d in by_day:
            by_day[d]["received"] += 1

    # recent transfers
    rq = db.query(TR).join(T, T.id == TR.transfer_id)
    if not glob:
        rq = rq.filter(or_(T.sender_user_id == me, TR.recipient_user_id == me))
    recent = []
    for r in rq.order_by(T.created_at.desc()).limit(8).all():
        t = r.transfer
        recent.append({"id": r.id, "transfer_uid": t.transfer_uid, "subject": t.subject, "kind": t.kind,
                       "direction": "sent" if t.sender_user_id == me else ("received" if r.recipient_user_id == me
                                                                         else "network"),
                       "sender": t.sender_name, "sender_pc": t.sender_pc, "recipient": r.recipient_name,
                       "recipient_pc": r.recipient_pc, "size": t.total_size, "status": r.status,
                       "created_at": iso(t.created_at)})

    browser_ids = hub.online_device_ids()
    devices = [serialise_device(db, d, browser_ids) for d in db.query(Device).filter(Device.status == "approved")
               .order_by(Device.last_seen_at.desc().nullslast()).limit(500).all()]
    online = sum(1 for d in devices if d["online"])
    notes = (db.query(Notification).filter(Notification.user_id == me)
             .order_by(Notification.created_at.desc()).limit(6).all())
    quota = float(app_settings.get(db, "storage_quota_gb") or 0) * 1024 ** 3
    repo_used = int(db.query(func.coalesce(func.sum(RepoFile.size), 0)).filter(RepoFile.deleted_at.is_(None)).scalar())
    used = storage_used()
    return {
        "scope": "global" if glob else "mine", "stats": stats, "activity": list(by_day.values()), "recent": recent,
        "devices": {"total": len(devices), "online": online, "offline": len(devices) - online,
                    "items": sorted(devices, key=lambda d: (not d["online"], d["pc_name"]))[:10]},
        "health": server_health(),
        "storage": {"used": used, "quota": int(quota), "repository_used": repo_used,
                    "transfers_used": max(0, used - repo_used),
                    "percent": round(used / quota * 100, 1) if quota else 0},
        "notifications": [_note(n) for n in notes],
        "users": {"total": db.query(User).filter(User.is_deleted.is_(False)).count(),
                  "online": len(hub.online_user_ids())},
    }


def _note(n: Notification) -> dict:
    return {"id": n.id, "type": n.type, "title": n.title, "body": n.body, "link": n.link, "is_read": n.is_read,
            "created_at": iso(n.created_at)}


@router.get("/notifications")
def notifications(limit: int = 30, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    q = db.query(Notification).filter(Notification.user_id == ctx.user.id)
    items = q.order_by(Notification.created_at.desc()).limit(min(limit, 200)).all()
    return {"items": [_note(n) for n in items],
            "unread": q.filter(Notification.is_read.is_(False)).count()}


class NoteIds(BaseModel):
    ids: list[int] = []
    all: bool = False


@router.post("/notifications/read")
def mark_notifications(body: NoteIds, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    q = db.query(Notification).filter(Notification.user_id == ctx.user.id, Notification.is_read.is_(False))
    if not body.all:
        q = q.filter(Notification.id.in_(body.ids))
    n = q.update({"is_read": True}, synchronize_session=False)
    db.commit()
    return {"updated": n}


@router.post("/notifications/clear")
def clear_notifications(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    n = db.query(Notification).filter(Notification.user_id == ctx.user.id).delete()
    db.commit()
    return {"deleted": n}
