"""Send Data: staged uploads, recipient directory, transfer creation, drafts and attachment downloads."""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from ..config import config
from ..database import get_db
from ..deps import Ctx, get_ctx, require
from ..models import Attachment, Device, Draft, Message, Transfer, TransferRecipient, User, utcnow
from ..realtime import hub
from ..services import delivery, search, storage
from ..services import settings as app_settings
from ..services.common import audit, html_to_text, iso, sanitise_html
from ..services.devices import device_status

router = APIRouter(prefix="/api", tags=["transfers"])


def _attachment_dict(a: Attachment) -> dict:
    return {"uid": a.uid, "name": a.original_name, "size": a.size, "extension": a.extension,
            "mime_type": a.mime_type, "sha256": a.sha256, "created_at": iso(a.created_at)}


def _storage_used_bytes() -> int:
    return storage.dir_size(config.storage_path)


# --------------------------------------------------------------------------- uploads
@router.post("/transfers/uploads")
async def upload_attachment(file: UploadFile = File(...), ctx: Ctx = Depends(require("send", write=True)),
                            db: Session = Depends(get_db)):
    s = app_settings.get_all(db)
    name = storage.clean_filename(file.filename or "file")
    ext = storage.check_extension(name, s["allowed_extensions"], bool(s.get("file_whitelist_enforced", True)))
    max_bytes = int(s["max_file_size_mb"]) * 1024 * 1024
    quota = float(s.get("storage_quota_gb") or 0) * 1024 ** 3
    if quota and _storage_used_bytes() >= quota:
        raise HTTPException(507, "Server storage quota reached. Contact the administrator.")
    rel, size, digest = await storage.save_upload(file, "transfers", max_bytes)
    a = Attachment(uploader_id=ctx.user.id, original_name=name, stored_path=rel, extension=ext,
                   mime_type=storage.guess_mime(name), size=size, sha256=digest)
    db.add(a)
    db.commit()
    return _attachment_dict(a)


@router.delete("/transfers/uploads/{uid}")
def delete_staged(uid: str, ctx: Ctx = Depends(require("send")), db: Session = Depends(get_db)):
    a = db.query(Attachment).filter_by(uid=uid).first()
    if not a or a.uploader_id != ctx.user.id or a.transfer_id is not None:
        raise HTTPException(404, "Staged attachment not found")
    storage.delete_stored(a.stored_path)
    db.delete(a)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- recipients
@router.get("/transfers/recipients")
def recipients(ctx: Ctx = Depends(require("send")), db: Session = Depends(get_db)):
    users = (db.query(User).filter(User.is_deleted.is_(False), User.status == "active")
             .order_by(User.full_name).all())
    browser_ids = hub.online_device_ids()
    online_users = hub.online_user_ids()
    out = []
    for u in users:
        dev: Optional[Device] = u.assigned_device
        st = device_status(db, dev, browser_ids) if dev else {"online": False, "browser_active": False,
                                                              "agent_online": False}
        out.append({"id": u.id, "full_name": u.full_name, "login_id": u.login_id,
                    "section_id": u.section_id, "section": u.section.name if u.section else "Unassigned",
                    "pc_name": dev.pc_name if dev else "", "ip_address": dev.ip_address if dev else "",
                    "connection_type": dev.connection_type if dev else "unknown",
                    "user_online": u.id in online_users, "pc_online": st["online"],
                    "is_self": u.id == ctx.user.id})
    return out


# --------------------------------------------------------------------------- send
class SendIn(BaseModel):
    subject: str = Field("", max_length=255)
    body_html: str = ""
    recipient_user_ids: list[int]
    attachment_uids: list[str] = []
    forward_attachment_uids: list[str] = []  # attachments of a transfer the sender can access
    reply_to_transfer_id: Optional[int] = None
    forwarded_from_transfer_id: Optional[int] = None
    priority: str = "normal"
    notify: bool = True
    delivery_confirmation: bool = True
    read_receipt: bool = False
    expires_at: Optional[datetime] = None
    draft_id: Optional[int] = None


def can_access_transfer(db: Session, ctx: Ctx, t: Transfer) -> Optional[TransferRecipient]:
    """Returns the caller's recipient row if they are a recipient; raises 404 if no access at all."""
    row = next((r for r in t.recipients if r.recipient_user_id == ctx.user.id and not r.purged), None)
    if row is not None or t.sender_user_id == ctx.user.id or (ctx.is_admin and "history" in ctx.perms):
        return row
    raise HTTPException(404, "Transfer not found")


@router.post("/transfers")
def send_transfer(body: SendIn, ctx: Ctx = Depends(require("send", write=True)), db: Session = Depends(get_db)):
    s = app_settings.get_all(db)
    if body.priority not in ("normal", "high", "urgent"):
        raise HTTPException(400, "Invalid priority")
    body_html = sanitise_html(body.body_html)
    body_text = html_to_text(body_html)
    recips = list(dict.fromkeys(body.recipient_user_ids))
    if not recips:
        raise HTTPException(400, "Select at least one recipient")
    users = db.query(User).filter(User.id.in_(recips), User.is_deleted.is_(False)).all()
    if len(users) != len(recips):
        raise HTTPException(400, "One or more recipients no longer exist")
    inactive = [u.full_name for u in users if u.status != "active"]
    if inactive:
        raise HTTPException(400, f"Inactive recipient(s): {', '.join(inactive)}")

    staged = db.query(Attachment).filter(Attachment.uid.in_(body.attachment_uids)).all() if body.attachment_uids else []
    if len(staged) != len(set(body.attachment_uids)) or any(
            a.uploader_id != ctx.user.id or a.transfer_id is not None for a in staged):
        raise HTTPException(400, "Attachment list is invalid or already sent")
    forwarded: list[Attachment] = []
    if body.forward_attachment_uids:
        forwarded = db.query(Attachment).filter(Attachment.uid.in_(body.forward_attachment_uids)).all()
        for a in forwarded:
            if a.transfer is None:
                raise HTTPException(400, "Invalid forwarded attachment")
            can_access_transfer(db, ctx, a.transfer)
    total_files = len(staged) + len(forwarded)
    if total_files > int(s["max_files_per_transfer"]):
        raise HTTPException(400, f"Maximum {s['max_files_per_transfer']} files per transfer")
    if not body_text.strip() and total_files == 0:
        raise HTTPException(400, "Enter a message or attach at least one file")
    if body.expires_at and body.expires_at.replace(tzinfo=None) <= utcnow():
        raise HTTPException(400, "Expiry must be in the future")

    kind = "both" if (body_text.strip() and total_files) else ("file" if total_files else "text")
    sender_dev = db.get(Device, ctx.session.device_id) if ctx.session.device_id else None
    t = Transfer(transfer_uid=delivery.new_transfer_uid(), sender_user_id=ctx.user.id,
                 sender_device_id=sender_dev.id if sender_dev else None, sender_name=ctx.user.full_name,
                 sender_login=ctx.user.login_id, sender_pc=sender_dev.pc_name if sender_dev else "",
                 sender_ip=ctx.ip, subject=body.subject.strip() or (body_text[:60] if body_text else
                                                                     (staged or forwarded)[0].original_name),
                 kind=kind, priority=body.priority, notify=body.notify,
                 delivery_confirmation=body.delivery_confirmation, read_receipt=body.read_receipt,
                 expires_at=body.expires_at.replace(tzinfo=None) if body.expires_at else None,
                 reply_to_id=body.reply_to_transfer_id, forwarded_from_id=body.forwarded_from_transfer_id)
    db.add(t)
    db.flush()
    t.message = Message(transfer_id=t.id, body_html=body_html, body_text=body_text)
    for a in staged:
        a.transfer_id = t.id
    for src in forwarded:
        db.add(Attachment(transfer_id=t.id, uploader_id=ctx.user.id, original_name=src.original_name,
                          stored_path=storage.copy_stored(src.stored_path, "transfers"), extension=src.extension,
                          mime_type=src.mime_type, size=src.size, sha256=src.sha256))
    db.flush()
    db.refresh(t)
    t.file_count = len(t.attachments)
    t.total_size = sum(a.size for a in t.attachments)
    rows = []
    for u in users:
        dev = u.assigned_device
        r = TransferRecipient(transfer_id=t.id, recipient_user_id=u.id, recipient_device_id=dev.id if dev else None,
                              recipient_name=u.full_name, recipient_login=u.login_id,
                              recipient_pc=dev.pc_name if dev else "", recipient_ip=dev.ip_address if dev else "")
        db.add(r)
        rows.append(r)
    if body.draft_id:
        db.query(Draft).filter_by(id=body.draft_id, user_id=ctx.user.id).delete()
    db.flush()
    search.index_transfer(db, t)
    audit(db, "transfer.send", user=ctx.user, ip=ctx.ip, entity_type="transfer", entity_id=t.transfer_uid,
          details={"recipients": [u.login_id for u in users], "files": t.file_count, "size": t.total_size})
    db.commit()
    db.refresh(t)
    delivery.dispatch_now(db, rows)
    db.refresh(t)
    return {"transfer": delivery.transfer_summary(t), "recipients": [delivery.recipient_dict(r) for r in t.recipients],
            "aggregate": delivery.aggregate_status(t.recipients)}


@router.get("/transfers/{transfer_id}/status")
def transfer_status(transfer_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    t = db.get(Transfer, transfer_id)
    if not t:
        raise HTTPException(404, "Transfer not found")
    can_access_transfer(db, ctx, t)
    if t.sender_user_id != ctx.user.id and not ctx.is_admin:
        raise HTTPException(403, "Only the sender can view delivery status")
    return {"transfer": delivery.transfer_summary(t), "aggregate": delivery.aggregate_status(t.recipients),
            "recipients": [delivery.recipient_dict(r) for r in t.recipients]}


# --------------------------------------------------------------------------- drafts
class DraftIn(BaseModel):
    subject: str = ""
    body_html: str = ""
    recipient_user_ids: list[int] = []
    attachment_uids: list[str] = []
    options: dict = {}


def _draft_dict(db: Session, d: Draft) -> dict:
    uids = json.loads(d.attachment_ids or "[]")
    atts = db.query(Attachment).filter(Attachment.uid.in_(uids), Attachment.transfer_id.is_(None)).all() if uids else []
    return {"id": d.id, "subject": d.subject, "body_html": d.body_html,
            "recipient_user_ids": json.loads(d.recipient_ids or "[]"),
            "attachments": [_attachment_dict(a) for a in atts], "options": json.loads(d.options or "{}"),
            "updated_at": iso(d.updated_at), "created_at": iso(d.created_at)}


@router.get("/drafts")
def list_drafts(ctx: Ctx = Depends(require("send")), db: Session = Depends(get_db)):
    ds = db.query(Draft).filter_by(user_id=ctx.user.id).order_by(Draft.updated_at.desc()).all()
    return [_draft_dict(db, d) for d in ds]


@router.post("/drafts")
def create_draft(body: DraftIn, ctx: Ctx = Depends(require("send", write=True)), db: Session = Depends(get_db)):
    d = Draft(user_id=ctx.user.id)
    db.add(d)
    _fill_draft(d, body)
    db.commit()
    return _draft_dict(db, d)


@router.put("/drafts/{draft_id}")
def update_draft(draft_id: int, body: DraftIn, ctx: Ctx = Depends(require("send", write=True)),
                 db: Session = Depends(get_db)):
    d = db.query(Draft).filter_by(id=draft_id, user_id=ctx.user.id).first()
    if not d:
        raise HTTPException(404, "Draft not found")
    _fill_draft(d, body)
    db.commit()
    return _draft_dict(db, d)


def _fill_draft(d: Draft, body: DraftIn) -> None:
    d.subject = body.subject[:255]
    d.body_html = sanitise_html(body.body_html)
    d.recipient_ids = json.dumps(body.recipient_user_ids)
    d.attachment_ids = json.dumps(body.attachment_uids)
    d.options = json.dumps(body.options)
    d.updated_at = utcnow()


@router.delete("/drafts/{draft_id}")
def delete_draft(draft_id: int, ctx: Ctx = Depends(require("send")), db: Session = Depends(get_db)):
    d = db.query(Draft).filter_by(id=draft_id, user_id=ctx.user.id).first()
    if not d:
        raise HTTPException(404, "Draft not found")
    db.delete(d)
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- downloads
@router.get("/attachments/{uid}")
def download_attachment(uid: str, inline: bool = Query(False), ctx: Ctx = Depends(get_ctx),
                        db: Session = Depends(get_db)):
    a = db.query(Attachment).filter_by(uid=uid).first()
    if not a:
        raise HTTPException(404, "File not found")
    if a.transfer is None:
        if a.uploader_id != ctx.user.id:
            raise HTTPException(404, "File not found")
    else:
        row = can_access_transfer(db, ctx, a.transfer)
        if row is not None:
            if a.transfer.expires_at and a.transfer.expires_at < utcnow() and row.status in ("pending", "sent", "failed"):
                raise HTTPException(410, "This transfer has expired")
            delivery.acknowledge(db, [row], ctx.ip, read=False)
    path = storage.resolve(a.stored_path)
    if not path.exists():
        raise HTTPException(410, "The stored file is missing on the server")
    audit(db, "attachment.download", user=ctx.user, ip=ctx.ip, entity_type="attachment", entity_id=a.uid,
          details={"name": a.original_name}, commit=True)
    return FileResponse(path, media_type=a.mime_type, filename=a.original_name,
                        content_disposition_type="inline" if inline else "attachment")


@router.get("/transfers/{transfer_id}/zip")
def download_zip(transfer_id: int, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    t = db.get(Transfer, transfer_id)
    if not t:
        raise HTTPException(404, "Transfer not found")
    row = can_access_transfer(db, ctx, t)
    if not t.attachments:
        raise HTTPException(404, "This transfer has no attachments")
    if row is not None:
        delivery.acknowledge(db, [row], ctx.ip)
    fd, tmp = tempfile.mkstemp(suffix=".zip", dir=config.tmp_path)
    os.close(fd)
    used: set[str] = set()
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for a in t.attachments:
            p = storage.resolve(a.stored_path)
            if not p.exists():
                continue
            name, n = a.original_name, 1
            while name.lower() in used:
                stem, dot, ext = a.original_name.rpartition(".")
                name = f"{stem or ext} ({n}){dot}{ext if stem else ''}"
                n += 1
            used.add(name.lower())
            zf.write(p, arcname=name)
    audit(db, "attachment.download_all", user=ctx.user, ip=ctx.ip, entity_type="transfer",
          entity_id=t.transfer_uid, commit=True)
    return FileResponse(tmp, media_type="application/zip", filename=f"{t.transfer_uid}.zip",
                        background=BackgroundTask(lambda: os.path.exists(tmp) and os.remove(tmp)))


def cleanup_stale_uploads(db: Session) -> int:
    """Remove staged uploads older than 24h that are not referenced by a draft."""
    cutoff = utcnow() - timedelta(hours=24)
    referenced: set[str] = set()
    for (uids,) in db.query(Draft.attachment_ids).all():
        referenced.update(json.loads(uids or "[]"))
    stale = db.query(Attachment).filter(Attachment.transfer_id.is_(None), Attachment.created_at < cutoff).all()
    n = 0
    for a in stale:
        if a.uid in referenced:
            continue
        storage.delete_stored(a.stored_path)
        db.delete(a)
        n += 1
    db.commit()
    return n
