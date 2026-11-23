"""Device identification, status computation and serialisation."""
from __future__ import annotations

from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from ..models import Device, User, utcnow
from ..realtime import hub
from . import settings as app_settings
from .common import ip_in_ranges, iso


def infer_connection(db: Session, ip: str) -> str:
    ranges = app_settings.get(db, "wifi_ip_ranges") or []
    return "wifi" if ranges and ip_in_ranges(ip, ranges) else "lan"


def device_for_ip(db: Session, ip: str, create: bool = True) -> Optional[Device]:
    """Find the registered device using this IP; optionally record an unknown device."""
    if not ip or ip in ("127.0.0.1", "::1", "testclient"):
        return None  # the server itself is not a client PC
    dev = (db.query(Device).filter(Device.ip_address == ip)
           .order_by(Device.status == "approved", Device.last_seen_at).all())
    if dev:
        return dev[-1]
    if not create or not app_settings.get(db, "device_discovery"):
        return None
    approval = app_settings.get(db, "device_approval_required")
    d = Device(pc_name=f"UNKNOWN-{ip.replace('.', '-').replace(':', '-')}", ip_address=ip,
               connection_type=infer_connection(db, ip), status="pending" if approval else "approved",
               is_unknown=True, notes="Auto-detected from browser sign-in")
    db.add(d)
    db.flush()
    return d


def agent_online(db: Session, d: Device) -> bool:
    hb = int(app_settings.get(db, "heartbeat_interval_seconds") or 30)
    return bool(d.last_agent_at and d.last_agent_at > utcnow() - timedelta(seconds=hb * 3))


def device_status(db: Session, d: Device, browser_ids: Optional[set[int]] = None) -> dict:
    browser_ids = hub.online_device_ids() if browser_ids is None else browser_ids
    browser = d.id in browser_ids
    agent = agent_online(db, d)
    return {"online": browser or agent, "browser_active": browser, "agent_online": agent}


def serialise_device(db: Session, d: Device, browser_ids: Optional[set[int]] = None,
                     users_by_device: Optional[dict[int, list[User]]] = None) -> dict:
    st = device_status(db, d, browser_ids)
    users = (users_by_device or {}).get(d.id, [])
    return {
        "id": d.id, "uid": d.uid, "pc_name": d.pc_name, "ip_address": d.ip_address, "mac_address": d.mac_address,
        "section_id": d.section_id, "section": d.section.name if d.section else "",
        "connection_type": d.connection_type, "status": d.status, "is_unknown": d.is_unknown,
        "os_info": d.os_info, "notes": d.notes, "agent_installed": bool(d.agent_token_hash),
        "agent_version": d.agent_version,
        "last_seen_at": iso(d.last_seen_at), "last_browser_at": iso(d.last_browser_at),
        "last_agent_at": iso(d.last_agent_at), "created_at": iso(d.created_at),
        "users": [{"id": u.id, "full_name": u.full_name, "login_id": u.login_id} for u in users],
        **st,
    }
