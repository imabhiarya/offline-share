"""Transfer History: one row per (transfer, recipient) with full delivery tracking."""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, require
from ..models import Attachment, Transfer, TransferRecipient
from ..services import delivery, search, storage
from ..services.common import audit, human_size, iso, local_day_range_utc, local_str, paginate
from ..services.excel import xlsx_response

router = APIRouter(prefix="/api/history", tags=["history"])


class Filters(BaseModel):
    tab: str = "all"
    scope: str = "mine"  # mine / all (admins)
    date_from: Optional[date] = None
    date_to: Optional[date] = None
    direction: str = ""
    status: str = ""
    file_type: str = ""
    pc: str = ""
    user: str = ""
    transfer_uid: str = ""
    q: str = ""


def _filters(tab: str = "all", scope: str = "mine", date_from: Optional[date] = None, date_to: Optional[date] = None,
             direction: str = "", status: str = "", file_type: str = "", pc: str = "", user: str = "",
             transfer_uid: str = "", q: str = "") -> Filters:
    return Filters(tab=tab, scope=scope, date_from=date_from, date_to=date_to, direction=direction, status=status,
                   file_type=file_type, pc=pc, user=user, transfer_uid=transfer_uid, q=q)


def _query(db: Session, ctx: Ctx, f: Filters):
    TR, T = TransferRecipient, Transfer
    q = db.query(TR).join(T, T.id == TR.transfer_id)
    me = ctx.user.id
    mine_sent = (T.sender_user_id == me) & (T.sender_deleted.is_(False))
    mine_recv = (TR.recipient_user_id == me) & (TR.purged.is_(False))
    all_scope = f.scope == "all" and ctx.is_admin
    if not all_scope:
        q = q.filter(or_(mine_sent, mine_recv))
    tab = f.tab
    direction = f.direction or ({"sent": "sent", "received": "received"}.get(tab, ""))
    if direction == "sent":
        q = q.filter(T.sender_user_id == me) if not all_scope else q
        if not all_scope:
            q = q.filter(T.sender_deleted.is_(False))
    elif direction == "received":
        q = q.filter(TR.recipient_user_id == me, TR.purged.is_(False))
    if tab == "pending":
        q = q.filter(TR.status.in_(("pending", "sent")))
    elif tab == "failed":
        q = q.filter(TR.status == "failed")
    if f.status:
        q = q.filter(TR.status == f.status)
    start, end = local_day_range_utc(f.date_from, f.date_to)
    if start:
        q = q.filter(T.created_at >= start)
    if end:
        q = q.filter(T.created_at < end)
    if f.file_type:
        ft = f.file_type.lower().lstrip(".")
        if ft == "text":
            q = q.filter(T.file_count == 0)
        else:
            q = q.filter(T.id.in_(db.query(Attachment.transfer_id).filter(Attachment.extension == ft)))
    if f.pc:
        like = f"%{f.pc}%"
        q = q.filter(or_(T.sender_pc.ilike(like), TR.recipient_pc.ilike(like), T.sender_ip.ilike(like),
                         TR.recipient_ip.ilike(like)))
    if f.user:
        like = f"%{f.user}%"
        q = q.filter(or_(T.sender_name.ilike(like), T.sender_login.ilike(like), TR.recipient_name.ilike(like),
                         TR.recipient_login.ilike(like)))
    if f.transfer_uid:
        q = q.filter(T.transfer_uid.ilike(f"%{f.transfer_uid.strip()}%"))
    if f.q.strip():
        ids = search.search_transfer_ids(db, f.q) or []
        like = f"%{f.q.strip()}%"
        q = q.filter(or_(T.id.in_(ids), T.subject.ilike(like), T.transfer_uid.ilike(like)))
    return q.order_by(T.created_at.desc(), TR.id)


def _row(ctx: Ctx, r: TransferRecipient) -> dict:
    t = r.transfer
    me = ctx.user.id
    direction = "sent" if t.sender_user_id == me else ("received" if r.recipient_user_id == me else "network")
    return {
        "id": r.id, "transfer_id": t.id, "transfer_uid": t.transfer_uid, "direction": direction,
        "sender_name": t.sender_name, "sender_login": t.sender_login, "sender_pc": t.sender_pc, "sender_ip": t.sender_ip,
        "recipient_name": r.recipient_name, "recipient_login": r.recipient_login, "recipient_pc": r.recipient_pc,
        "recipient_ip": r.recipient_ip, "subject": t.subject, "file_names": [a.original_name for a in t.attachments],
        "file_types": sorted({a.extension for a in t.attachments}), "size": t.total_size, "kind": t.kind,
        "priority": t.priority, "created_at": iso(t.created_at), "status": r.status,
        "delivered_at": iso(r.delivered_at), "read_at": iso(r.read_at), "failed_reason": r.failed_reason,
        "attempts": r.attempts, "can_retry": r.status == "failed" and (t.sender_user_id == me or ctx.is_admin),
    }


@router.get("")
def list_history(page: int = 1, page_size: int = 25, f: Filters = Depends(_filters),
                 ctx: Ctx = Depends(require("history")), db: Session = Depends(get_db)):
    rows, total, page, page_size = paginate(_query(db, ctx, f), page, page_size)
    return {"items": [_row(ctx, r) for r in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/counts")
def history_counts(scope: str = "mine", ctx: Ctx = Depends(require("history")), db: Session = Depends(get_db)):
    out = {tab: _query(db, ctx, Filters(tab=tab, scope=scope)).order_by(None).count()
           for tab in ("all", "sent", "received", "pending", "failed")}
    from sqlalchemy import func
    T, TR = Transfer, TransferRecipient
    glob = scope == "all" and ctx.is_admin
    me = ctx.user.id
    outgoing = db.query(TR).join(T, T.id == TR.transfer_id)
    if not glob:
        outgoing = outgoing.filter(T.sender_user_id == me)
    sent_q = db.query(T) if glob else db.query(T).filter(T.sender_user_id == me)
    recv_q = db.query(TR) if glob else db.query(TR).filter(TR.recipient_user_id == me)
    if glob:
        data = db.query(func.coalesce(func.sum(T.total_size), 0)).scalar()
    else:
        data = (db.query(func.coalesce(func.sum(T.total_size), 0)).filter(T.sender_user_id == me).scalar() or 0) + \
               (db.query(func.coalesce(func.sum(T.total_size), 0)).join(TR, TR.transfer_id == T.id)
                .filter(TR.recipient_user_id == me).scalar() or 0)
    out["stats"] = {"total_sent": sent_q.count(), "total_received": recv_q.count(),
                    "delivered": outgoing.filter(TR.status.in_(("delivered", "read"))).count(),
                    "pending": outgoing.filter(TR.status.in_(("pending", "sent"))).count(),
                    "failed": outgoing.filter(TR.status == "failed").count(), "total_data": int(data or 0)}
    return out


@router.get("/transfer/{uid}")
def transfer_detail(uid: str, ctx: Ctx = Depends(require("history")), db: Session = Depends(get_db)):
    t = db.query(Transfer).filter_by(transfer_uid=uid).first()
    if not t:
        raise HTTPException(404, "Transfer not found")
    is_sender = t.sender_user_id == ctx.user.id
    mine = [r for r in t.recipients if r.recipient_user_id == ctx.user.id]
    if not (is_sender or mine or ctx.is_admin):
        raise HTTPException(404, "Transfer not found")
    recips = t.recipients if (is_sender or ctx.is_admin) else mine
    return {
        "transfer": delivery.transfer_summary(t),
        "aggregate": delivery.aggregate_status(t.recipients),
        "sender": {"name": t.sender_name, "login": t.sender_login, "pc": t.sender_pc, "ip": t.sender_ip},
        "body_html": t.message.body_html if t.message else "",
        "attachments": [{"uid": a.uid, "name": a.original_name, "size": a.size, "extension": a.extension,
                         "sha256": a.sha256} for a in t.attachments],
        "recipients": [delivery.recipient_dict(r) for r in recips],
        "options": {"priority": t.priority, "notify": t.notify, "delivery_confirmation": t.delivery_confirmation,
                    "read_receipt": t.read_receipt, "expires_at": iso(t.expires_at)},
    }


class IdsIn(BaseModel):
    recipient_ids: list[int]


@router.post("/retry")
def retry_failed(body: IdsIn, ctx: Ctx = Depends(require("history", write=True)), db: Session = Depends(get_db)):
    rows = db.query(TransferRecipient).filter(TransferRecipient.id.in_(body.recipient_ids[:500])).all()
    allowed = [r for r in rows if r.transfer.sender_user_id == ctx.user.id or ctx.is_admin]
    return {"retried": delivery.retry(db, allowed, ctx.user, ctx.ip)}


def hard_delete_transfer(db: Session, t: Transfer) -> None:
    for a in t.attachments:
        storage.delete_stored(a.stored_path)
    search.unindex_transfer(db, t.id)
    db.delete(t)


@router.post("/delete")
def delete_records(body: IdsIn, ctx: Ctx = Depends(require("history")), db: Session = Depends(get_db)):
    rows = db.query(TransferRecipient).filter(TransferRecipient.id.in_(body.recipient_ids[:1000])).all()
    n = 0
    touched: set[int] = set()
    for r in rows:
        t = r.transfer
        if ctx.is_admin and "history" in ctx.perms:
            touched.add(t.id)
            db.delete(r)
            n += 1
        elif t.sender_user_id == ctx.user.id:
            t.sender_deleted = True
            n += 1
        elif r.recipient_user_id == ctx.user.id:
            r.purged = True
            r.is_deleted = True
            n += 1
    db.flush()
    for tid in touched:
        t = db.get(Transfer, tid)
        if t is not None:
            db.refresh(t)
            if not t.recipients:
                hard_delete_transfer(db, t)
    audit(db, "history.delete", user=ctx.user, ip=ctx.ip, details={"rows": n, "admin": ctx.is_admin})
    db.commit()
    return {"deleted": n}


@router.get("/export.xlsx")
def export_history(f: Filters = Depends(_filters), ctx: Ctx = Depends(require("history")),
                   db: Session = Depends(get_db)):
    rows = _query(db, ctx, f).limit(50000).all()
    headers = ["S.No", "Transfer ID", "Direction", "Sender", "Sender PC", "Sender IP", "Receiver", "Receiver PC",
               "Receiver IP", "Subject", "Files", "File Type", "Size", "Date & Time", "Status", "Delivered At",
               "Read At", "Failure Reason"]
    data = []
    for i, r in enumerate(rows, 1):
        d = _row(ctx, r)
        data.append([i, d["transfer_uid"], d["direction"].title(), d["sender_name"], d["sender_pc"], d["sender_ip"],
                     d["recipient_name"], d["recipient_pc"], d["recipient_ip"], d["subject"],
                     ", ".join(d["file_names"]), ", ".join(d["file_types"]) or "text", human_size(d["size"]),
                     local_str(r.transfer.created_at), d["status"].title(), local_str(r.delivered_at), local_str(r.read_at),
                     d["failed_reason"]])
    audit(db, "history.export", user=ctx.user, ip=ctx.ip, details={"rows": len(data)}, commit=True)
    return xlsx_response("Transfer History", headers, data, f"transfer_history_{datetime.now():%Y%m%d_%H%M}.xlsx")


@router.get("/export.csv")
def export_history_csv(f: Filters = Depends(_filters), ctx: Ctx = Depends(require("history")),
                       db: Session = Depends(get_db)):
    import csv
    import io

    from fastapi.responses import Response
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["S.No", "Transfer ID", "Direction", "Sender", "Sender PC", "Receiver", "Receiver PC", "Subject",
                "Files", "Size (bytes)", "Date & Time", "Status", "Delivered At", "Read At"])
    for i, r in enumerate(_query(db, ctx, f).limit(50000).all(), 1):
        d = _row(ctx, r)
        w.writerow([i, d["transfer_uid"], d["direction"], d["sender_name"], d["sender_pc"], d["recipient_name"],
                    d["recipient_pc"], d["subject"], "; ".join(d["file_names"]), d["size"], local_str(r.transfer.created_at),
                    d["status"], local_str(r.delivered_at), local_str(r.read_at)])
    audit(db, "history.export_csv", user=ctx.user, ip=ctx.ip, commit=True)
    return Response("﻿" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="transfer_records_{datetime.now():%Y%m%d_%H%M}.csv"'})
