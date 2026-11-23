"""Connected Devices: registry, approval, blocking, live status, network map and client agent API."""
from __future__ import annotations

import hmac
import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..config import config
from ..database import get_db
from ..deps import Ctx, require
from ..models import AppSetting, Device, Section, User, utcnow
from ..realtime import hub
from ..security import token_digest
from ..services import settings as app_settings
from ..services.common import audit, client_ip, iso, local_str
from ..services.devices import device_status, infer_connection, serialise_device
from ..services.excel import xlsx_response

router = APIRouter(prefix="/api/devices", tags=["devices"])
agent_router = APIRouter(prefix="/api/agent", tags=["agent"])


def _users_by_device(db: Session) -> dict[int, list[User]]:
    out: dict[int, list[User]] = {}
    for u in db.query(User).filter(User.is_deleted.is_(False), User.assigned_device_id.is_not(None)).all():
        out.setdefault(u.assigned_device_id, []).append(u)
    return out


def _all(db: Session, section_id: Optional[int] = None, status: str = "", conn: str = "", q: str = ""):
    query = db.query(Device)
    if section_id:
        query = query.filter(Device.section_id == section_id)
    if status in ("pending", "approved", "blocked"):
        query = query.filter(Device.status == status)
    if conn in ("lan", "wifi", "unknown"):
        query = query.filter(Device.connection_type == conn)
    if q.strip():
        like = f"%{q.strip()}%"
        uids = db.query(User.assigned_device_id).filter(or_(User.full_name.ilike(like), User.login_id.ilike(like)))
        query = query.filter(or_(Device.pc_name.ilike(like), Device.ip_address.ilike(like),
                                 Device.mac_address.ilike(like), Device.id.in_(uids)))
    return query.order_by(Device.pc_name).all()


@router.get("")
def list_devices(section_id: Optional[int] = None, status: str = "", connection: str = "", online: str = "",
                 q: str = "", ctx: Ctx = Depends(require("devices")), db: Session = Depends(get_db)):
    browser_ids = hub.online_device_ids()
    ubd = _users_by_device(db)
    items = [serialise_device(db, d, browser_ids, ubd) for d in _all(db, section_id, status, connection, q)]
    if online == "online":
        items = [i for i in items if i["online"]]
    elif online == "offline":
        items = [i for i in items if not i["online"]]
    every = [serialise_device(db, d, browser_ids, ubd) for d in db.query(Device).all()]
    stats = {
        "total": len(every), "online": sum(1 for d in every if d["online"]),
        "offline": sum(1 for d in every if not d["online"]),
        "lan": sum(1 for d in every if d["connection_type"] == "lan"),
        "wifi": sum(1 for d in every if d["connection_type"] == "wifi"),
        "active_users": len(hub.online_user_ids()),
        "pending": sum(1 for d in every if d["status"] == "pending"),
        "blocked": sum(1 for d in every if d["status"] == "blocked"),
        "unknown": sum(1 for d in every if d["is_unknown"]),
    }
    return {"items": items, "stats": stats}


@router.get("/network-map")
def network_map(ctx: Ctx = Depends(require("devices")), db: Session = Depends(get_db)):
    browser_ids = hub.online_device_ids()
    ubd = _users_by_device(db)
    devs = [serialise_device(db, d, browser_ids, ubd) for d in db.query(Device).filter(Device.status != "blocked")
            .order_by(Device.pc_name).all()]
    return {"server": {"ip": config.public_ip, "port": config.port, "subnet": config.subnet},
            "wired": [d for d in devs if d["connection_type"] != "wifi"],
            "wireless": [d for d in devs if d["connection_type"] == "wifi"]}


class DeviceIn(BaseModel):
    pc_name: str = Field(..., min_length=1, max_length=64)
    ip_address: str = ""
    mac_address: str = ""
    section_id: Optional[int] = None
    connection_type: str = "lan"
    status: str = "approved"
    notes: str = ""


def _validate(db: Session, body: DeviceIn, exclude_id: Optional[int] = None) -> None:
    if body.connection_type not in ("lan", "wifi", "unknown"):
        raise HTTPException(400, "Connection type must be lan, wifi or unknown")
    if body.status not in ("pending", "approved", "blocked"):
        raise HTTPException(400, "Invalid status")
    q = db.query(Device).filter(Device.pc_name.ilike(body.pc_name.strip()))
    if exclude_id:
        q = q.filter(Device.id != exclude_id)
    if q.first():
        raise HTTPException(409, f"A device named {body.pc_name} already exists")
    if body.ip_address:
        import ipaddress
        try:
            ipaddress.ip_address(body.ip_address.strip())
        except ValueError:
            raise HTTPException(400, "Invalid IP address")
        q = db.query(Device).filter(Device.ip_address == body.ip_address.strip(), Device.status != "blocked")
        if exclude_id:
            q = q.filter(Device.id != exclude_id)
        dup = q.first()
        if dup:
            raise HTTPException(409, f"IP {body.ip_address} is already assigned to {dup.pc_name}")


@router.post("")
def add_device(body: DeviceIn, ctx: Ctx = Depends(require("devices", write=True)), db: Session = Depends(get_db)):
    if not ctx.is_admin:
        raise HTTPException(403, "Administrator access required")
    _validate(db, body)
    d = Device(pc_name=body.pc_name.strip().upper(), ip_address=body.ip_address.strip(),
               mac_address=body.mac_address.strip().upper(), section_id=body.section_id,
               connection_type=body.connection_type, status=body.status, notes=body.notes)
    if body.status == "approved":
        d.approved_at, d.approved_by = utcnow(), ctx.user.id
    db.add(d)
    db.flush()
    audit(db, "device.add", user=ctx.user, ip=ctx.ip, entity_type="device", entity_id=d.id, details=body.model_dump())
    db.commit()
    return serialise_device(db, d)


@router.put("/{device_id}")
def edit_device(device_id: int, body: DeviceIn, ctx: Ctx = Depends(require("devices", write=True)),
                db: Session = Depends(get_db)):
    if not ctx.is_admin:
        raise HTTPException(403, "Administrator access required")
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(404, "Device not found")
    _validate(db, body, exclude_id=d.id)
    d.pc_name, d.ip_address = body.pc_name.strip().upper(), body.ip_address.strip()
    d.mac_address, d.section_id = body.mac_address.strip().upper(), body.section_id
    d.connection_type, d.notes = body.connection_type, body.notes
    if body.status != d.status:
        _set_status(db, ctx, d, body.status)
    d.is_unknown = False
    audit(db, "device.edit", user=ctx.user, ip=ctx.ip, entity_type="device", entity_id=d.id, details=body.model_dump())
    db.commit()
    return serialise_device(db, d)


def _set_status(db: Session, ctx: Ctx, d: Device, status: str) -> None:
    d.status = status
    if status == "approved":
        d.approved_at, d.approved_by, d.is_unknown = utcnow(), ctx.user.id, False
    if status == "blocked":
        # end active browser sessions from this PC
        from ..models import UserSession
        sess = db.query(UserSession).filter(UserSession.device_id == d.id, UserSession.revoked_at.is_(None)).all()
        for s in sess:
            s.revoked_at = utcnow()
            hub.close_session(s.id)


class StatusIn(BaseModel):
    status: str


@router.post("/{device_id}/status")
def change_status(device_id: int, body: StatusIn, ctx: Ctx = Depends(require("devices", write=True)),
                  db: Session = Depends(get_db)):
    if not ctx.is_admin:
        raise HTTPException(403, "Administrator access required")
    if body.status not in ("pending", "approved", "blocked"):
        raise HTTPException(400, "Invalid status")
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(404, "Device not found")
    _set_status(db, ctx, d, body.status)
    audit(db, f"device.{ {'approved': 'approve', 'blocked': 'block', 'pending': 'unblock'}[body.status]}",
          user=ctx.user, ip=ctx.ip, entity_type="device", entity_id=d.id, details={"pc": d.pc_name})
    db.commit()
    return serialise_device(db, d)


@router.delete("/{device_id}")
def delete_device(device_id: int, ctx: Ctx = Depends(require("devices", write=True)), db: Session = Depends(get_db)):
    if not ctx.is_admin:
        raise HTTPException(403, "Administrator access required")
    d = db.get(Device, device_id)
    if not d:
        raise HTTPException(404, "Device not found")
    audit(db, "device.delete", user=ctx.user, ip=ctx.ip, entity_type="device", entity_id=d.id,
          details={"pc": d.pc_name, "ip": d.ip_address})
    db.delete(d)
    db.commit()
    return {"ok": True}


@router.get("/export.xlsx")
def export_devices(ctx: Ctx = Depends(require("devices")), db: Session = Depends(get_db)):
    browser_ids = hub.online_device_ids()
    ubd = _users_by_device(db)
    rows = []
    for i, d in enumerate(db.query(Device).order_by(Device.pc_name).all(), 1):
        s = serialise_device(db, d, browser_ids, ubd)
        rows.append([i, s["pc_name"], s["ip_address"], s["mac_address"], ", ".join(u["full_name"] for u in s["users"]),
                     s["section"], s["connection_type"].upper(), "Online" if s["online"] else "Offline",
                     "Yes" if s["browser_active"] else "No", "Yes" if s["agent_installed"] else "No",
                     s["status"].title(), local_str(d.last_seen_at)])
    return xlsx_response("Connected Devices", ["S.No", "PC Name", "IP Address", "MAC", "User", "Section",
                                               "Connection", "PC Status", "Browser Session", "Agent", "Approval",
                                               "Last Active"], rows, f"devices_{datetime.now():%Y%m%d}.xlsx")


@router.get("/agent-key")
def agent_key(ctx: Ctx = Depends(require("devices")), db: Session = Depends(get_db)):
    if not ctx.is_admin:
        raise HTTPException(403, "Administrator access required")
    return {"enrolment_key": get_enrolment_key(db), "server_url": f"{'https' if config.https else 'http'}://"
                                                                   f"{config.public_ip}:{config.port}"}


def get_enrolment_key(db: Session) -> str:
    row = db.get(AppSetting, "_agent_enrolment_key")
    if row is None:
        import json
        row = AppSetting(key="_agent_enrolment_key", value=json.dumps(secrets.token_urlsafe(18)))
        db.add(row)
        db.commit()
    import json
    return json.loads(row.value)


# --------------------------------------------------------------------------- client agent API
class AgentRegisterIn(BaseModel):
    enrolment_key: str
    pc_name: str
    mac_address: str = ""
    os_info: str = ""
    agent_version: str = ""
    connection_type: str = ""


@agent_router.post("/register")
def agent_register(body: AgentRegisterIn, request: Request, db: Session = Depends(get_db)):
    ip = client_ip(request)
    if not hmac.compare_digest(body.enrolment_key, get_enrolment_key(db)):
        audit(db, "agent.register_denied", ip=ip, details={"pc": body.pc_name}, commit=True)
        raise HTTPException(403, "Invalid enrolment key")
    name = body.pc_name.strip().upper()[:64]
    d = db.query(Device).filter(Device.pc_name.ilike(name)).first()
    if d is None:
        approval = app_settings.get(db, "device_approval_required")
        d = Device(pc_name=name, status="pending" if approval else "approved", is_unknown=True,
                   notes="Registered by client agent")
        db.add(d)
    if d.status == "blocked":
        raise HTTPException(403, "This PC is blocked")
    token = secrets.token_urlsafe(32)
    d.agent_token_hash = token_digest(token)
    d.ip_address = ip
    d.mac_address = body.mac_address.upper()[:32]
    d.os_info = body.os_info[:120]
    d.agent_version = body.agent_version[:32]
    d.connection_type = body.connection_type if body.connection_type in ("lan", "wifi") else infer_connection(db, ip)
    d.last_agent_at = d.last_seen_at = utcnow()
    db.flush()
    audit(db, "agent.register", ip=ip, entity_type="device", entity_id=d.id, details={"pc": name})
    db.commit()
    return {"device_uid": d.uid, "token": token, "status": d.status,
            "heartbeat_interval": app_settings.get(db, "heartbeat_interval_seconds")}


class HeartbeatIn(BaseModel):
    connection_type: str = ""
    logged_in_user: str = ""
    os_info: str = ""
    agent_version: str = ""


@agent_router.post("/heartbeat")
def agent_heartbeat(body: HeartbeatIn, request: Request, x_agent_token: str = Header(""),
                    db: Session = Depends(get_db)):
    if not x_agent_token:
        raise HTTPException(401, "Missing agent token")
    d = db.query(Device).filter(Device.agent_token_hash == token_digest(x_agent_token)).first()
    if d is None:
        raise HTTPException(401, "Unknown agent token; re-register")
    if d.status == "blocked":
        raise HTTPException(403, "This PC is blocked")
    was_online = device_status(db, d)["online"]
    now = utcnow()
    d.last_agent_at = d.last_seen_at = now
    d.ip_address = client_ip(request)
    if body.connection_type in ("lan", "wifi"):
        d.connection_type = body.connection_type
    if body.os_info:
        d.os_info = body.os_info[:120]
    if body.agent_version:
        d.agent_version = body.agent_version[:32]
    db.commit()
    if not was_online:
        hub.broadcast({"type": "device.status", "device_id": d.id, "online": True})
    unread = 0
    users = db.query(User).filter(User.assigned_device_id == d.id, User.is_deleted.is_(False)).all()
    if users:
        from ..models import TransferRecipient
        unread = db.query(TransferRecipient).filter(
            TransferRecipient.recipient_user_id.in_([u.id for u in users]),
            TransferRecipient.status.in_(("pending", "sent"))).count()
    return {"status": d.status, "heartbeat_interval": app_settings.get(db, "heartbeat_interval_seconds"),
            "pending_for_pc": unread, "server_time": iso(now)}


# Sections are shared by devices and users
section_router = APIRouter(prefix="/api/sections", tags=["sections"])


class SectionIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    code: str = ""
    description: str = ""


@section_router.get("")
def list_sections(db: Session = Depends(get_db), ctx: Ctx = Depends(require("dashboard"))):
    return [{"id": s.id, "name": s.name, "code": s.code, "description": s.description}
            for s in db.query(Section).order_by(Section.name).all()]


@section_router.post("")
def add_section(body: SectionIn, ctx: Ctx = Depends(require("users", write=True)), db: Session = Depends(get_db)):
    if db.query(Section).filter(Section.name.ilike(body.name.strip())).first():
        raise HTTPException(409, "Section already exists")
    s = Section(name=body.name.strip(), code=body.code.strip().upper(), description=body.description)
    db.add(s)
    audit(db, "section.add", user=ctx.user, ip=ctx.ip, details=body.model_dump())
    db.commit()
    return {"id": s.id, "name": s.name, "code": s.code, "description": s.description}


@section_router.delete("/{section_id}")
def delete_section(section_id: int, ctx: Ctx = Depends(require("users", write=True)), db: Session = Depends(get_db)):
    s = db.get(Section, section_id)
    if not s:
        raise HTTPException(404, "Section not found")
    audit(db, "section.delete", user=ctx.user, ip=ctx.ip, details={"name": s.name})
    db.delete(s)
    db.commit()
    return {"ok": True}
