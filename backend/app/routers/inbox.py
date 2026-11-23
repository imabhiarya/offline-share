"""Receive Data: the recipient's inbox."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, require
from ..models import Attachment, Transfer, TransferRecipient, utcnow
from ..services import delivery, search
from ..services.common import audit, iso, local_day_range_utc, paginate

router = APIRouter(prefix="/api/inbox", tags=["inbox"])

CATEGORIES = ["all", "unread", "read", "attachments", "text", "flagged", "important", "archived", "deleted"]


def _visible(db: Session, user_id: int):
    now = utcnow()
    return (db.query(TransferRecipient).join(Transfer, Transfer.id == TransferRecipient.transfer_id)
            .filter(TransferRecipient.recipient_user_id == user_id, TransferRecipient.purged.is_(False),
                    TransferRecipient.status != "failed",
                    # an expired transfer that was never delivered is not shown
                    or_(Transfer.expires_at.is_(None), Transfer.expires_at > now,
                        TransferRecipient.status.in_(("delivered", "read")))))


def _apply_category(q, category: str):  # noqa: ANN001
    TR = TransferRecipient
    live = and_(TR.is_archived.is_(False), TR.is_deleted.is_(False))
    if category == "all":
        return q.filter(live)
    if category == "unread":
        return q.filter(live, TR.status != "read")
    if category == "read":
        return q.filter(live, TR.status == "read")
    if category == "attachments":
        return q.filter(live, Transfer.file_count > 0)
    if category == "text":
        return q.filter(live, Transfer.file_count == 0)
    if category == "flagged":
        return q.filter(TR.is_flagged.is_(True), TR.is_deleted.is_(False))
    if category == "important":
        return q.filter(or_(TR.is_important.is_(True), Transfer.priority.in_(("high", "urgent"))),
                        TR.is_deleted.is_(False))
    if category == "archived":
        return q.filter(TR.is_archived.is_(True), TR.is_deleted.is_(False))
    if category == "deleted":
        return q.filter(TR.is_deleted.is_(True))
    raise HTTPException(400, "Unknown category")


@router.get("")
def list_inbox(category: str = "all", q: str = "", sender: str = "", page: int = 1, page_size: int = 25,
               date_from: Optional[date] = None, date_to: Optional[date] = None,
               ctx: Ctx = Depends(require("receive")), db: Session = Depends(get_db)):
    query = _apply_category(_visible(db, ctx.user.id), category)
    start, end = local_day_range_utc(date_from, date_to)
    if start:
        query = query.filter(Transfer.created_at >= start)
    if end:
        query = query.filter(Transfer.created_at < end)
    if q.strip():
        term = q.strip()
        ids = search.search_transfer_ids(db, term) or []
        like = f"%{term}%"
        query = query.filter(or_(Transfer.id.in_(ids), Transfer.transfer_uid.ilike(like),
                                 Transfer.sender_name.ilike(like), Transfer.sender_pc.ilike(like),
                                 Transfer.subject.ilike(like),
                                 Transfer.id.in_(db.query(Attachment.transfer_id)
                                                 .filter(Attachment.original_name.ilike(like)))))
    if sender.strip():
        like = f"%{sender.strip()}%"
        query = query.filter(or_(Transfer.sender_name.ilike(like), Transfer.sender_login.ilike(like),
                                 Transfer.sender_pc.ilike(like)))
    query = query.order_by(Transfer.created_at.desc())
    rows, total, page, page_size = paginate(query, page, page_size)
    # The client fetched these rows, which proves receipt: acknowledge undelivered ones.
    undelivered = [r for r in rows if r.status in ("pending", "sent")]
    if undelivered:
        delivery.acknowledge(db, undelivered, ctx.ip)
    return {"items": [delivery.transfer_summary(r.transfer, r) for r in rows], "total": total,
            "page": page, "page_size": page_size}


@router.get("/counts")
def counts(ctx: Ctx = Depends(require("receive")), db: Session = Depends(get_db)):
    out = {}
    for c in CATEGORIES:
        out[c] = _apply_category(_visible(db, ctx.user.id), c).order_by(None).count()
    from ..services import settings as app_settings
    inbox_bytes = (db.query(func.coalesce(func.sum(Attachment.size), 0))
                   .join(TransferRecipient, TransferRecipient.transfer_id == Attachment.transfer_id)
                   .filter(TransferRecipient.recipient_user_id == ctx.user.id, TransferRecipient.purged.is_(False))
                   .scalar())
    out["storage"] = {"inbox_bytes": int(inbox_bytes or 0),
                      "quota": int(float(app_settings.get(db, "storage_quota_gb") or 0) * 1024 ** 3)}
    return out


class AckIn(BaseModel):
    recipient_ids: list[int]


@router.post("/ack")
def ack(body: AckIn, ctx: Ctx = Depends(require("receive")), db: Session = Depends(get_db)):
    rows = (db.query(TransferRecipient)
            .filter(TransferRecipient.id.in_(body.recipient_ids[:500]),
                    TransferRecipient.recipient_user_id == ctx.user.id).all())
    return {"acknowledged": delivery.acknowledge(db, rows, ctx.ip)}


def _own_row(db: Session, ctx: Ctx, rid: int) -> TransferRecipient:
    r = db.get(TransferRecipient, rid)
    if not r or r.recipient_user_id != ctx.user.id or r.purged:
        raise HTTPException(404, "Message not found")
    return r


@router.get("/{rid}")
def open_message(rid: int, mark_read: bool = True, ctx: Ctx = Depends(require("receive")),
                 db: Session = Depends(get_db)):
    r = _own_row(db, ctx, rid)
    t = r.transfer
    if t.expires_at and t.expires_at < utcnow() and r.status not in ("delivered", "read"):
        raise HTTPException(410, "This transfer expired before it was delivered")
    if mark_read:
        delivery.acknowledge(db, [r], ctx.ip, read=True)
    elif r.status in ("pending", "sent"):
        delivery.acknowledge(db, [r], ctx.ip)
    db.refresh(r)
    data = delivery.transfer_summary(t, r)
    data.update({"body_html": t.message.body_html if t.message else "",
                 "body_text": t.message.body_text if t.message else "",
                 "attachments": [{"uid": a.uid, "name": a.original_name, "size": a.size, "extension": a.extension,
                                  "mime_type": a.mime_type} for a in t.attachments],
                 "reply_to_id": t.reply_to_id, "forwarded_from_id": t.forwarded_from_id})
    return data


class FlagsIn(BaseModel):
    is_flagged: Optional[bool] = None
    is_important: Optional[bool] = None
    is_archived: Optional[bool] = None
    is_deleted: Optional[bool] = None
    is_read: Optional[bool] = None


def _apply_flags(db: Session, ctx: Ctx, r: TransferRecipient, body: FlagsIn) -> None:
    for f in ("is_flagged", "is_important", "is_archived"):
        v = getattr(body, f)
        if v is not None:
            setattr(r, f, v)
    if body.is_deleted is not None:
        r.is_deleted = body.is_deleted
        r.deleted_at = utcnow() if body.is_deleted else None
    if body.is_read:
        delivery.acknowledge(db, [r], ctx.ip, read=True)


@router.patch("/{rid}")
def update_flags(rid: int, body: FlagsIn, ctx: Ctx = Depends(require("receive")), db: Session = Depends(get_db)):
    r = _own_row(db, ctx, rid)
    _apply_flags(db, ctx, r, body)
    db.commit()
    return delivery.transfer_summary(r.transfer, r)


class BulkIn(BaseModel):
    recipient_ids: list[int]
    action: str  # read / flag / unflag / important / unimportant / archive / unarchive / delete / restore / purge


@router.post("/bulk")
def bulk(body: BulkIn, ctx: Ctx = Depends(require("receive")), db: Session = Depends(get_db)):
    mapping = {"flag": FlagsIn(is_flagged=True), "unflag": FlagsIn(is_flagged=False),
               "important": FlagsIn(is_important=True), "unimportant": FlagsIn(is_important=False),
               "archive": FlagsIn(is_archived=True), "unarchive": FlagsIn(is_archived=False),
               "delete": FlagsIn(is_deleted=True), "restore": FlagsIn(is_deleted=False),
               "read": FlagsIn(is_read=True)}
    if body.action not in mapping and body.action != "purge":
        raise HTTPException(400, "Unknown action")
    rows = (db.query(TransferRecipient).filter(TransferRecipient.id.in_(body.recipient_ids[:1000]),
                                               TransferRecipient.recipient_user_id == ctx.user.id).all())
    for r in rows:
        if body.action == "purge":
            if not r.is_deleted:
                continue
            r.purged = True
        else:
            _apply_flags(db, ctx, r, mapping[body.action])
    if body.action == "purge":
        audit(db, "inbox.purge", user=ctx.user, ip=ctx.ip, details={"count": len(rows)})
    db.commit()
    return {"updated": len(rows)}


@router.get("/unread/count")
def unread_count(ctx: Ctx = Depends(require("receive")), db: Session = Depends(get_db)):
    n = _apply_category(_visible(db, ctx.user.id), "unread").order_by(None).with_entities(func.count()).scalar()
    return {"unread": n}
