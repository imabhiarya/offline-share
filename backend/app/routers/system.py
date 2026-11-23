"""Settings, network configuration, backup/restore, maintenance, logs and health check."""
from __future__ import annotations

import ipaddress
import socket
import sqlite3
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from sqlalchemy import or_
from sqlalchemy.orm import Session

from .. import runtime
from ..models import utcnow as _utcnow
from ..config import APP_VERSION, config, save_config
from ..database import get_db
from ..deps import Ctx, require, require_super
from ..models import AuditLog, BackupHistory
from ..realtime import hub
from ..services import backup as backup_svc
from ..services import search, storage
from ..services import settings as app_settings
from ..services.common import audit, client_ip, human_size, ip_allowed, iso, local_day_range_utc, local_str, paginate
from ..services.excel import xlsx_response
from .dashboard import server_health

router = APIRouter(prefix="/api", tags=["system"])

SUPER_ONLY_GROUPS = {"security", "backup"}


def _admin_settings(ctx: Ctx) -> None:
    if not ctx.is_admin:
        raise HTTPException(403, "Administrator access required")


@router.get("/settings")
def get_settings(ctx: Ctx = Depends(require("settings")), db: Session = Depends(get_db)):
    return {"settings": app_settings.grouped(db),
            "network": {"public_ip": config.public_ip, "port": config.port, "subnet": config.subnet,
                        "allowed_subnets": config.allowed_subnets, "https": config.https,
                        "host": config.host},
            "paths": {"data": str(config.home), "database": str(config.db_path), "storage": str(config.storage_path),
                      "backups": str(config.backup_path), "logs": str(config.log_path)},
            "defaults": {k: v[0] for k, v in app_settings.DEFAULTS.items()},
            "can_edit": ctx.is_admin, "is_super": ctx.is_super}


def _validate_setting(key: str, value: Any) -> Any:
    default = app_settings.DEFAULTS[key][0]
    if isinstance(default, bool):
        if not isinstance(value, bool):
            raise HTTPException(400, f"{key} must be true/false")
    elif isinstance(default, int):
        try:
            value = int(value)
        except (TypeError, ValueError):
            raise HTTPException(400, f"{key} must be a number")
        if value < 0:
            raise HTTPException(400, f"{key} cannot be negative")
    elif isinstance(default, list):
        if isinstance(value, str):
            value = [v.strip() for v in value.split(",") if v.strip()]
        if not isinstance(value, list):
            raise HTTPException(400, f"{key} must be a list")
        value = [str(v).strip() for v in value if str(v).strip()]
    elif isinstance(default, dict):
        if not isinstance(value, dict):
            raise HTTPException(400, f"{key} must be an object")
    elif isinstance(default, str):
        value = str(value)
    return value


class SettingsIn(BaseModel):
    values: dict[str, Any]


@router.put("/settings")
def put_settings(body: SettingsIn, ctx: Ctx = Depends(require("settings", write=True)), db: Session = Depends(get_db)):
    _admin_settings(ctx)
    clean: dict[str, Any] = {}
    for k, v in body.values.items():
        if k not in app_settings.DEFAULTS:
            raise HTTPException(400, f"Unknown setting: {k}")
        if app_settings.DEFAULTS[k][1] in SUPER_ONLY_GROUPS and not ctx.is_super:
            raise HTTPException(403, "Security and backup settings require a Super Admin")
        clean[k] = _validate_setting(k, v)
    if "allowed_extensions" in clean:
        clean["allowed_extensions"] = sorted({e.lower().lstrip(".") for e in clean["allowed_extensions"]})
        dangerous = {"exe", "bat", "cmd", "com", "msi", "ps1", "vbs", "js", "scr", "dll", "hta", "jar"}
        bad = dangerous & set(clean["allowed_extensions"])
        if bad and not ctx.is_super:
            raise HTTPException(400, f"Executable types ({', '.join(sorted(bad))}) can only be allowed by a Super Admin")
    if "max_file_size_mb" in clean and not (1 <= clean["max_file_size_mb"] <= 20480):
        raise HTTPException(400, "Maximum file size must be between 1 MB and 20 GB")
    if "heartbeat_interval_seconds" in clean and not (10 <= clean["heartbeat_interval_seconds"] <= 600):
        raise HTTPException(400, "Heartbeat interval must be 10–600 seconds")
    if "session_timeout_minutes" in clean and not (5 <= clean["session_timeout_minutes"] <= 1440):
        raise HTTPException(400, "Session timeout must be 5–1440 minutes")
    if "logo_data_url" in clean and clean["logo_data_url"]:
        if not clean["logo_data_url"].startswith("data:image/") or len(clean["logo_data_url"]) > 400_000:
            raise HTTPException(400, "Logo must be a PNG/JPG image under 300 KB")
    for k, limit in (("organisation_name", 120), ("organisation_slogan", 150), ("app_name", 60), ("app_subtitle", 120)):
        if k in clean:
            clean[k] = " ".join(str(clean[k]).split())
            if len(clean[k]) > limit:
                raise HTTPException(400, f"{k.replace('_', ' ').title()} must be at most {limit} characters")
    if "layout_style" in clean and clean["layout_style"] not in ("classic", "modern", "compact"):
        raise HTTPException(400, "Page design must be classic, modern or compact")
    if "theme" in clean and clean["theme"] not in ("maroon", "blue", "green", "navy", "purple"):
        raise HTTPException(400, "Unknown colour theme")
    if "backup_time" in clean:
        try:
            datetime.strptime(clean["backup_time"], "%H:%M")
        except ValueError:
            raise HTTPException(400, "Backup time must be HH:MM")
    changed = app_settings.set_many(db, clean, ctx.user.id)
    audit(db, "settings.update", user=ctx.user, ip=ctx.ip, entity_type="settings",
          details={k: ("<image>" if k == "logo_data_url" else v) for k, v in changed.items()}, commit=True)
    hub.broadcast({"type": "settings.changed"})
    return {"settings": app_settings.grouped(db)}


class NetworkIn(BaseModel):
    public_ip: str
    port: int
    subnet: str
    allowed_subnets: list[str]
    https: bool = False


@router.put("/settings/network")
def put_network(body: NetworkIn, ctx: Ctx = Depends(require_super)):
    try:
        ipaddress.ip_address(body.public_ip)
        net = ipaddress.ip_network(body.subnet, strict=False)
        for s in body.allowed_subnets:
            ipaddress.ip_network(s, strict=False)
    except ValueError as e:
        raise HTTPException(400, f"Invalid address: {e}")
    if not (1 <= body.port <= 65535):
        raise HTTPException(400, "Invalid port")
    if ipaddress.ip_address(body.public_ip) not in net:
        raise HTTPException(400, "Server IP must be inside the LAN subnet")
    if not body.allowed_subnets:
        raise HTTPException(400, "At least one allowed subnet is required")
    if body.https and not (config.ssl_certfile and Path(config.ssl_certfile).exists()):
        raise HTTPException(400, "HTTPS needs a certificate. Run the certificate tool first (see Installation Guide).")
    config.public_ip, config.port, config.subnet = body.public_ip, body.port, str(net)
    config.allowed_subnets, config.https = body.allowed_subnets, body.https
    save_config(config)
    from ..database import SessionLocal
    with SessionLocal() as db:
        audit(db, "settings.network", user=ctx.user, ip=ctx.ip, details=body.model_dump(), commit=True)
    return {"ok": True, "restart_required": True,
            "message": "Saved. Restart the service and update the Windows Firewall rule for the new port/subnet."}


# --------------------------------------------------------------------------- backups
def _backup_dict(b: BackupHistory) -> dict:
    return {"id": b.id, "filename": b.filename, "size": b.size, "kind": b.kind, "includes_files": b.includes_files,
            "status": b.status, "message": b.message, "created_at": iso(b.created_at),
            "exists": Path(b.path).exists()}


@router.get("/system/backups")
def list_backups(ctx: Ctx = Depends(require("settings")), db: Session = Depends(get_db)):
    _admin_settings(ctx)
    rows = db.query(BackupHistory).order_by(BackupHistory.created_at.desc()).limit(200).all()
    s = app_settings.get_all(db)
    return {"items": [_backup_dict(b) for b in rows], "location": str(config.backup_path),
            "next_run": runtime.next_backup_time(s)}


class BackupIn(BaseModel):
    include_files: bool = True


@router.post("/system/backups")
def make_backup(body: BackupIn, ctx: Ctx = Depends(require_super), db: Session = Depends(get_db)):
    try:
        rec = backup_svc.create_backup("manual", body.include_files, ctx.user.id)
    except Exception as e:
        audit(db, "backup.failed", user=ctx.user, ip=ctx.ip, details={"error": str(e)}, commit=True)
        raise HTTPException(500, f"Backup failed: {e}")
    audit(db, "backup.create", user=ctx.user, ip=ctx.ip, details={"file": rec.filename}, commit=True)
    return _backup_dict(rec)


@router.get("/system/backups/{backup_id}/download")
def download_backup(backup_id: int, ctx: Ctx = Depends(require_super), db: Session = Depends(get_db)):
    b = db.get(BackupHistory, backup_id)
    if not b or not Path(b.path).exists():
        raise HTTPException(404, "Backup file not found")
    audit(db, "backup.download", user=ctx.user, ip=ctx.ip, details={"file": b.filename}, commit=True)
    return FileResponse(b.path, media_type="application/zip", filename=b.filename)


@router.delete("/system/backups/{backup_id}")
def delete_backup(backup_id: int, ctx: Ctx = Depends(require_super), db: Session = Depends(get_db)):
    b = db.get(BackupHistory, backup_id)
    if not b:
        raise HTTPException(404, "Backup not found")
    Path(b.path).unlink(missing_ok=True)
    audit(db, "backup.delete", user=ctx.user, ip=ctx.ip, details={"file": b.filename})
    db.delete(b)
    db.commit()
    return {"ok": True}


class RestoreIn(BaseModel):
    backup_id: int
    restore_files: bool = True


@router.post("/system/restore")
def restore(body: RestoreIn, ctx: Ctx = Depends(require_super), db: Session = Depends(get_db)):
    b = db.get(BackupHistory, body.backup_id)
    if not b or not Path(b.path).exists():
        raise HTTPException(404, "Backup file not found")
    user, ip = ctx.user, ctx.ip
    db.close()
    try:
        result = backup_svc.restore_backup(Path(b.path), body.restore_files, user.id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    from ..database import SessionLocal
    with SessionLocal() as s2:
        audit(s2, "backup.restore", ip=ip, details={"file": b.path, "by": user.login_id}, commit=True)
    hub.broadcast({"type": "system.restored"})
    return {"ok": True, **result}


@router.post("/system/restore/upload")
async def restore_upload(file: UploadFile = File(...), restore_files: bool = True, ctx: Ctx = Depends(require_super)):
    name = storage.clean_filename(file.filename or "uploaded_backup.zip")
    if not name.lower().endswith(".zip"):
        raise HTTPException(400, "Upload a .zip backup created by OFFLINE SHARE")
    dest = config.backup_path / f"uploaded_{datetime.now():%Y%m%d_%H%M%S}_{name}"
    with open(dest, "wb") as out:
        while chunk := await file.read(1024 * 1024):
            out.write(chunk)
    try:
        backup_svc.validate_backup(dest)
        result = backup_svc.restore_backup(dest, restore_files, ctx.user.id)
    except (ValueError, Exception) as e:  # noqa: B014
        raise HTTPException(400, f"Restore failed: {e}")
    hub.broadcast({"type": "system.restored"})
    return {"ok": True, **result}


# --------------------------------------------------------------------------- maintenance
@router.post("/system/maintenance/{task}")
def maintenance(task: str, ctx: Ctx = Depends(require("settings")), db: Session = Depends(get_db)):
    _admin_settings(ctx)
    if task == "clear-temp":
        from .transfers import cleanup_stale_uploads
        n = storage.clear_tmp()
        m = cleanup_stale_uploads(db)
        result = {"message": f"Removed {n} temporary item(s) and {m} abandoned upload(s)"}
    elif task == "integrity-check":
        con = sqlite3.connect(str(config.db_path))
        try:
            res = [r[0] for r in con.execute("PRAGMA integrity_check").fetchall()]
            fk = con.execute("PRAGMA foreign_key_check").fetchall()
        finally:
            con.close()
        from ..models import Attachment, FileVersion
        missing = 0
        for (p,) in db.query(Attachment.stored_path).filter(Attachment.transfer_id.is_not(None)):
            if not storage.resolve(p).exists():
                missing += 1
        for (p,) in db.query(FileVersion.stored_path):
            if not storage.resolve(p).exists():
                missing += 1
        ok = res == ["ok"] and not fk
        result = {"ok": ok, "integrity": res[:20], "foreign_key_issues": len(fk), "missing_files": missing,
                  "message": ("Database integrity OK" if ok else "Problems found") +
                             (f"; {missing} stored file(s) missing" if missing else "")}
    elif task == "rebuild-index":
        r = search.rebuild(db)
        result = {"message": f"Search index rebuilt: {r['transfers']} transfers, {r['files']} files"}
    elif task == "optimise":
        con = sqlite3.connect(str(config.db_path))
        try:
            con.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            con.execute("PRAGMA optimize")
        finally:
            con.close()
        result = {"message": "Database checkpoint and optimise complete"}
    elif task == "restart":
        if not ctx.is_super:
            raise HTTPException(403, "Super Admin access required")
        audit(db, "system.restart", user=ctx.user, ip=ctx.ip, commit=True)
        runtime.request_restart()
        return {"message": "Service restart requested. The page will reconnect automatically."}
    else:
        raise HTTPException(404, "Unknown maintenance task")
    audit(db, f"maintenance.{task}", user=ctx.user, ip=ctx.ip, details=result, commit=True)
    return result


@router.get("/system/logs")
def system_logs(lines: int = 300, level: str = "", ctx: Ctx = Depends(require("settings"))):
    _admin_settings(ctx)
    path = config.log_path / "offline_share.log"
    if not path.exists():
        return {"lines": [], "path": str(path)}
    with open(path, "rb") as f:
        f.seek(0, 2)
        size = f.tell()
        f.seek(max(0, size - 512 * 1024))
        data = f.read().decode("utf-8", "replace").splitlines()
    if level:
        data = [l for l in data if f" {level.upper()} " in l]
    return {"lines": data[-min(lines, 5000):], "path": str(path)}


@router.get("/system/audit")
def audit_logs(q: str = "", action: str = "", date_from: Optional[date] = None, date_to: Optional[date] = None,
               page: int = 1, page_size: int = 50, ctx: Ctx = Depends(require("settings")),
               db: Session = Depends(get_db)):
    _admin_settings(ctx)
    query = db.query(AuditLog)
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(AuditLog.user_name.ilike(like), AuditLog.ip_address.ilike(like),
                                 AuditLog.details.ilike(like), AuditLog.entity_id.ilike(like)))
    if action:
        query = query.filter(AuditLog.action.ilike(f"{action}%"))
    start, end = local_day_range_utc(date_from, date_to)
    if start:
        query = query.filter(AuditLog.created_at >= start)
    if end:
        query = query.filter(AuditLog.created_at < end)
    rows, total, page, page_size = paginate(query.order_by(AuditLog.created_at.desc()), page, page_size)
    return {"items": [{"id": a.id, "at": iso(a.created_at), "user": a.user_name, "ip": a.ip_address,
                       "action": a.action, "entity_type": a.entity_type, "entity_id": a.entity_id,
                       "details": a.details} for a in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/system/audit/export.xlsx")
def export_audit(ctx: Ctx = Depends(require("settings")), db: Session = Depends(get_db)):
    _admin_settings(ctx)
    rows = [[i, local_str(a.created_at), a.user_name, a.ip_address, a.action, a.entity_type, a.entity_id, a.details]
            for i, a in enumerate(db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(100000), 1)]
    return xlsx_response("Audit Log", ["S.No", "Time", "User", "IP", "Action", "Entity", "Entity ID", "Details"],
                         rows, f"audit_log_{datetime.now():%Y%m%d}.xlsx")


@router.get("/system/network-test")
def network_test(request: Request, ctx: Ctx = Depends(require("dashboard"))):
    ip = client_ip(request)
    addrs: list[dict] = []
    try:
        import psutil
        for name, lst in psutil.net_if_addrs().items():
            for a in lst:
                if a.family == socket.AF_INET:
                    addrs.append({"interface": name, "ip": a.address, "netmask": a.netmask})
        stats = psutil.net_if_stats()
        for a in addrs:
            st = stats.get(a["interface"])
            a["up"] = bool(st and st.isup)
            a["speed_mbps"] = st.speed if st else 0
    except Exception:
        pass
    bound = any(a["ip"] == config.public_ip for a in addrs)
    checks = [
        {"name": "Server reachable from this PC", "ok": True, "detail": f"Request arrived from {ip}"},
        {"name": "This PC is inside an allowed subnet", "ok": ip_allowed(ip, config.allowed_subnets),
         "detail": ", ".join(config.allowed_subnets)},
        {"name": f"Configured server IP {config.public_ip} present on server", "ok": bound,
         "detail": "Static IP is assigned" if bound else "Configured IP not found on any interface – check static IP"},
        {"name": "Encrypted connection (HTTPS)", "ok": config.https,
         "detail": "Enabled" if config.https else "HTTP only – clipboard/notifications limited on client PCs"},
        {"name": "Live notification channel", "ok": True, "detail": f"{hub.connection_count()} open connection(s)"},
    ]
    return {"client_ip": ip, "server_ip": config.public_ip, "port": config.port, "interfaces": addrs,
            "checks": checks, "server_time": iso(_utcnow())}


# --------------------------------------------------------------------------- health (no auth)
@router.get("/health")
def health():
    t0 = time.perf_counter()
    db_ok = True
    try:
        con = sqlite3.connect(str(config.db_path), timeout=5)
        con.execute("SELECT 1").fetchone()
        con.close()
    except Exception:
        db_ok = False
    disk = server_health()
    return {"status": "ok" if db_ok else "degraded", "database": "ok" if db_ok else "error",
            "version": APP_VERSION, "uptime_seconds": disk["uptime_seconds"], "disk_free": disk["disk_free"],
            "connections": hub.connection_count(), "response_ms": round((time.perf_counter() - t0) * 1000, 2),
            "time": iso(_utcnow())}


health_page_router = APIRouter()


@health_page_router.get("/health", response_class=HTMLResponse, include_in_schema=False)
def health_page():
    h = health()
    s = server_health()
    ok = h["status"] == "ok"
    rows = [("Status", "ONLINE" if ok else "DEGRADED"), ("Database", h["database"]), ("Version", APP_VERSION),
            ("Server", f"{config.public_ip}:{config.port}"), ("Uptime", str(timedelta(seconds=h["uptime_seconds"]))),
            ("CPU", f"{s['cpu_percent']}%"), ("Memory", f"{s['memory_percent']}%"),
            ("Disk free", human_size(s["disk_free"])), ("Database size", human_size(s["db_size"])),
            ("Live connections", str(s["ws_connections"])), ("Checked", datetime.now().strftime("%d/%m/%Y %H:%M:%S"))]
    body = "".join(f"<tr><th>{k}</th><td>{v}</td></tr>" for k, v in rows)
    colour = "#1f7a4d" if ok else "#b3261e"
    return f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta http-equiv="refresh" content="15">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>OFFLINE SHARE – Health</title>
<style>body{{font-family:Segoe UI,system-ui,sans-serif;background:#faf6f6;color:#2b1d20;margin:0;padding:32px}}
.card{{max-width:560px;margin:auto;background:#fff;border-radius:16px;box-shadow:0 4px 20px rgba(122,30,48,.08);padding:28px}}
h1{{color:#7a1e30;margin:0 0 4px;font-size:22px}}.badge{{display:inline-block;padding:4px 12px;border-radius:999px;
background:{colour};color:#fff;font-weight:600;font-size:13px}}table{{width:100%;border-collapse:collapse;margin-top:18px}}
th,td{{text-align:left;padding:8px 4px;border-bottom:1px solid #f0e4e6;font-size:14px}}th{{color:#6b5a5e;font-weight:500;width:45%}}
a{{color:#7a1e30}}</style></head><body><div class="card"><h1>OFFLINE SHARE</h1>
<p>Local Data Transfer System (LAN) – server health <span class="badge">{'ONLINE' if ok else 'DEGRADED'}</span></p>
<table>{body}</table><p style="font-size:13px;color:#6b5a5e">Auto-refreshes every 15 seconds. JSON: <a href="/api/health">/api/health</a> · <a href="/">Open application</a></p>
</div></body></html>"""
