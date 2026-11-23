"""Transfer delivery engine.

Recipient status lifecycle::

    pending  - queued; the recipient has no open session yet
    sent     - pushed over WebSocket to an open session, awaiting acknowledgement
    delivered- the recipient's browser acknowledged receipt (ack API or inbox fetch)
    read     - the recipient opened the message
    failed   - expired, or no acknowledgement after the configured retry attempts

A transfer is never marked delivered by the sender; only the receiving client can do that.
"""
from __future__ import annotations

import logging
import secrets
from datetime import datetime, timedelta
from typing import Iterable, Optional

from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import database
from ..models import Transfer, TransferRecipient, User, utcnow
from ..realtime import hub
from . import settings as app_settings
from .common import audit, iso, notify

log = logging.getLogger("offline_share.delivery")

ACTIVE = ("pending", "sent")


def new_transfer_uid() -> str:
    return f"TRF-{datetime.now():%Y%m%d}-{secrets.token_hex(3).upper()}"


def aggregate_status(recipients: Iterable[TransferRecipient]) -> str:
    sts = [r.status for r in recipients]
    if not sts:
        return "draft"
    if all(s == "read" for s in sts):
        return "read"
    if all(s in ("delivered", "read") for s in sts):
        return "delivered"
    if any(s in ACTIVE for s in sts):
        return "pending" if all(s in ACTIVE for s in sts) else "partial"
    if all(s == "failed" for s in sts):
        return "failed"
    return "partial"


def transfer_summary(t: Transfer, r: Optional[TransferRecipient] = None) -> dict:
    body_text = t.message.body_text if t.message else ""
    d = {
        "id": t.id, "transfer_uid": t.transfer_uid, "subject": t.subject, "kind": t.kind, "priority": t.priority,
        "sender_user_id": t.sender_user_id, "sender_name": t.sender_name, "sender_login": t.sender_login,
        "sender_pc": t.sender_pc, "sender_ip": t.sender_ip,
        "preview": body_text[:160], "file_count": t.file_count, "total_size": t.total_size,
        "file_types": sorted({a.extension for a in t.attachments if a.extension}),
        "file_names": [a.original_name for a in t.attachments],
        "created_at": iso(t.created_at), "expires_at": iso(t.expires_at),
        "read_receipt": t.read_receipt, "delivery_confirmation": t.delivery_confirmation,
    }
    if r is not None:
        d.update({"recipient_id": r.id, "status": r.status, "is_read": r.status == "read",
                  "is_flagged": r.is_flagged, "is_important": r.is_important, "is_archived": r.is_archived,
                  "is_deleted": r.is_deleted, "delivered_at": iso(r.delivered_at), "read_at": iso(r.read_at)})
    return d


def recipient_dict(r: TransferRecipient) -> dict:
    return {"id": r.id, "user_id": r.recipient_user_id, "name": r.recipient_name, "login": r.recipient_login,
            "pc": r.recipient_pc, "ip": r.recipient_ip, "status": r.status, "attempts": r.attempts,
            "sent_at": iso(r.sent_at), "delivered_at": iso(r.delivered_at), "read_at": iso(r.read_at),
            "failed_at": iso(r.failed_at), "failed_reason": r.failed_reason, "delivered_ip": r.delivered_ip}


def _status_event(r: TransferRecipient) -> dict:
    return {"type": "transfer.status", "transfer_id": r.transfer_id, "transfer_uid": r.transfer.transfer_uid,
            "recipient": recipient_dict(r), "aggregate": aggregate_status(r.transfer.recipients)}


def _push_rows(db: Session, rows: list[TransferRecipient]) -> list[tuple[int, dict]]:
    """Mark rows as sent and return (user_id, message) pairs to deliver."""
    now = utcnow()
    out = []
    for r in rows:
        t = r.transfer
        if t.expires_at and t.expires_at < now:
            continue
        r.status = "sent"
        r.attempts += 1
        r.last_attempt_at = now
        r.sent_at = r.sent_at or now
        out.append((r.recipient_user_id, {"type": "transfer.new", "notify": t.notify,
                                          "transfer": transfer_summary(t, r)}))
        if t.sender_user_id:
            out.append((t.sender_user_id, _status_event(r)))
    db.commit()
    return out


def dispatch_now(db: Session, recipient_rows: list[TransferRecipient]) -> None:
    """Called right after a transfer is created: push to recipients currently online."""
    online = hub.online_user_ids()
    rows = [r for r in recipient_rows if r.recipient_user_id in online and r.status == "pending"]
    for uid, msg in _push_rows(db, rows):
        hub.send_user(uid, msg)


async def deliver_queue_for_user(user_id: int) -> None:
    """Flush the pending queue for a user who just connected."""
    with database.SessionLocal() as db:
        rows = (db.query(TransferRecipient)
                .filter(TransferRecipient.recipient_user_id == user_id, TransferRecipient.status == "pending")
                .order_by(TransferRecipient.id).limit(500).all())
        msgs = _push_rows(db, rows)
    for uid, msg in msgs:
        await hub.send_user_async(uid, msg)


def _set_status(db: Session, r: TransferRecipient, status: str, ip: str = "") -> bool:
    order = {"pending": 0, "sent": 1, "delivered": 2, "read": 3}
    now = utcnow()
    if r.status == "failed" and status in ("delivered", "read"):
        # a late acknowledgement still proves receipt
        r.failed_at = None
        r.failed_reason = ""
    elif order.get(status, -1) <= order.get(r.status, -1):
        return False
    if status in ("delivered", "read") and not r.delivered_at:
        r.delivered_at = now
        r.delivered_ip = ip
    if status == "read":
        r.read_at = now
    r.status = status
    return True


def acknowledge(db: Session, rows: list[TransferRecipient], ip: str, read: bool = False) -> int:
    """Recipient-side acknowledgement. Notifies senders (delivery confirmation / read receipt)."""
    changed = []
    for r in rows:
        if _set_status(db, r, "read" if read else "delivered", ip):
            changed.append(r)
    if not changed:
        return 0
    for r in changed:
        t = r.transfer
        if read and t.read_receipt and t.sender_user_id:
            notify(db, t.sender_user_id, "read", f"Read: {t.subject or t.transfer_uid}",
                   f"{r.recipient_name} ({r.recipient_pc or r.recipient_ip}) opened {t.transfer_uid}",
                   f"/history?transfer={t.transfer_uid}")
    db.commit()
    for r in changed:
        t = r.transfer
        if t.sender_user_id and (t.delivery_confirmation or (read and t.read_receipt)):
            hub.send_user(t.sender_user_id, _status_event(r))
            if read and t.read_receipt:
                hub.send_user(t.sender_user_id, {"type": "notification"})
    return len(changed)


def fail(db: Session, r: TransferRecipient, reason: str) -> None:
    r.status = "failed"
    r.failed_at = utcnow()
    r.failed_reason = reason[:255]
    t = r.transfer
    if t.sender_user_id and app_settings.get(db, "notify_failed_transfer"):
        notify(db, t.sender_user_id, "failed", f"Delivery failed: {t.subject or t.transfer_uid}",
               f"To {r.recipient_name}: {reason}", f"/history?transfer={t.transfer_uid}")


def retry(db: Session, rows: list[TransferRecipient], actor: Optional[User] = None, ip: str = "") -> int:
    n = 0
    for r in rows:
        if r.status != "failed":
            continue
        t = r.transfer
        if t.expires_at and t.expires_at < utcnow():
            t.expires_at = None  # a manual retry re-opens an expired transfer
        r.status, r.attempts, r.failed_at, r.failed_reason = "pending", 0, None, ""
        n += 1
        audit(db, "transfer.retry", user=actor, ip=ip, entity_type="transfer", entity_id=t.transfer_uid,
              details={"recipient": r.recipient_login})
    db.commit()
    if n:
        dispatch_now(db, rows)
    return n


async def worker_tick() -> None:
    """Periodic: expire transfers, re-push unacknowledged ones, fail after retry limit."""
    msgs: list[tuple[int, dict]] = []
    with database.SessionLocal() as db:
        now = utcnow()
        s = app_settings.get_all(db)
        # 1. expiry
        expired = (db.query(TransferRecipient).join(Transfer)
                   .filter(TransferRecipient.status.in_(ACTIVE), Transfer.expires_at.is_not(None),
                           Transfer.expires_at < now).limit(500).all())
        for r in expired:
            fail(db, r, "Expired before delivery")
            if r.transfer.sender_user_id:
                msgs.append((r.transfer.sender_user_id, _status_event(r)))
                msgs.append((r.transfer.sender_user_id, {"type": "notification"}))
        db.commit()
        # 2. unacknowledged pushes
        interval = int(s.get("retry_interval_seconds") or 60)
        attempts = int(s.get("retry_attempts") or 5)
        stale = (db.query(TransferRecipient)
                 .filter(TransferRecipient.status == "sent",
                         TransferRecipient.last_attempt_at < now - timedelta(seconds=interval))
                 .limit(500).all())
        online = hub.online_user_ids()
        to_push = []
        for r in stale:
            if r.recipient_user_id not in online:
                r.status = "pending"  # back to the offline queue; delivered on reconnect
            elif not s.get("auto_retry"):
                continue
            elif r.attempts >= attempts:
                fail(db, r, f"No acknowledgement after {r.attempts} attempts")
                if r.transfer.sender_user_id:
                    msgs.append((r.transfer.sender_user_id, _status_event(r)))
            else:
                to_push.append(r)
        db.commit()
        msgs.extend(_push_rows(db, to_push))
        # 3. pending rows for users who are online (e.g. queued while a socket was reconnecting)
        if online:
            pend = (db.query(TransferRecipient)
                    .filter(TransferRecipient.status == "pending",
                            TransferRecipient.recipient_user_id.in_(online),
                            or_(TransferRecipient.last_attempt_at.is_(None),
                                TransferRecipient.last_attempt_at < now - timedelta(seconds=10)))
                    .limit(500).all())
            msgs.extend(_push_rows(db, pend))
    for uid, msg in msgs:
        await hub.send_user_async(uid, msg)
