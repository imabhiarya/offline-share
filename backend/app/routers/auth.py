from __future__ import annotations

from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..config import APP_VERSION, config
from ..database import get_db
from ..deps import CSRF_COOKIE, SESSION_COOKIE, Ctx, effective_permissions, get_ctx
from ..models import User, UserSession, utcnow
from ..realtime import hub
from ..security import check_password_policy, hash_password, new_token, token_digest, verify_password
from ..services import settings as app_settings
from ..services.common import audit, client_ip, iso
from ..services.devices import device_for_ip

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    login_id: str
    password: str


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str


def public_branding(db: Session) -> dict:
    s = app_settings.get_all(db)
    return {k: s.get(k) for k in ("app_name", "app_subtitle", "organisation_name", "organisation_slogan", "logo_data_url", "language",
                                  "date_format", "time_format", "theme", "layout_style", "desktop_notifications", "sound_notifications",
                                  "notify_new_message", "notify_new_file",
                                  "heartbeat_interval_seconds", "max_file_size_mb", "max_files_per_transfer",
                                  "allowed_extensions", "delivery_confirmation_default", "read_receipt_default",
                                  "file_whitelist_enforced")}


def user_profile(db: Session, user: User) -> dict:
    return {
        "id": user.id, "full_name": user.full_name, "login_id": user.login_id, "role": user.role.code,
        "role_name": user.role.name, "section_id": user.section_id,
        "section": user.section.name if user.section else "", "email": user.email, "mobile": user.mobile,
        "assigned_device": user.assigned_device.pc_name if user.assigned_device else "",
        "must_change_password": user.must_change_password,
        "permissions": sorted(effective_permissions(db, user)),
        "last_login_at": iso(user.last_login_at),
    }


@router.get("/config")
def public_config(request: Request, db: Session = Depends(get_db)):
    return {"branding": public_branding(db), "server_ip": config.public_ip, "port": config.port,
            "https": config.https, "version": APP_VERSION, "client_ip": client_ip(request),
            "password_policy": app_settings.get(db, "password_policy")}


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    ip = client_ip(request)
    s = app_settings.get_all(db)
    user: Optional[User] = db.query(User).filter(User.login_id == body.login_id.strip(), User.is_deleted.is_(False)).first()
    now = utcnow()
    generic = HTTPException(401, "Invalid login ID or password")
    if user is None:
        verify_password(body.password, "scrypt$16384$8$1$AAAA$AAAA")  # equalise timing
        audit(db, "auth.login_failed", ip=ip, details={"login_id": body.login_id[:64]}, commit=True)
        raise generic
    if user.locked_until and user.locked_until > now:
        mins = int((user.locked_until - now).total_seconds() // 60) + 1
        raise HTTPException(423, f"Account locked after repeated failed attempts. Try again in {mins} minute(s).")
    if not verify_password(body.password, user.password_hash):
        user.failed_logins += 1
        max_attempts = int(s.get("max_login_attempts") or 5)
        if user.failed_logins >= max_attempts:
            user.locked_until = now + timedelta(minutes=int(s.get("lockout_minutes") or 15))
            user.failed_logins = 0
            audit(db, "auth.locked", user=user, ip=ip, entity_type="user", entity_id=user.id)
        audit(db, "auth.login_failed", user=user, ip=ip, entity_type="user", entity_id=user.id, commit=True)
        raise generic
    if user.status != "active":
        raise HTTPException(403, "This account is deactivated. Contact the administrator.")

    loopback = ip in ("127.0.0.1", "::1", "testclient")
    device = device_for_ip(db, ip)
    if device is not None and device.status == "blocked" and not loopback:
        audit(db, "auth.blocked_device", user=user, ip=ip, entity_type="device", entity_id=device.id, commit=True)
        raise HTTPException(403, f"This PC ({device.pc_name}) is blocked by the administrator.")
    if s.get("registered_pc_restriction") and not loopback:
        if device is None or device.status != "approved":
            db.commit()
            audit(db, "auth.unregistered_device", user=user, ip=ip, commit=True)
            raise HTTPException(403, "Sign-in is only allowed from registered and approved PCs. "
                                     "Ask the administrator to approve this PC.")
    if device is not None:
        device.last_seen_at = device.last_browser_at = now
        device.last_user_id = user.id

    token = new_token()
    csrf = new_token(24)
    timeout = int(s.get("session_timeout_minutes") or 480)
    sess = UserSession(id=token_digest(token), user_id=user.id, device_id=device.id if device else None,
                       ip_address=ip, user_agent=(request.headers.get("user-agent") or "")[:255],
                       csrf_token=csrf, expires_at=now + timedelta(hours=24), last_seen_at=now)
    db.add(sess)
    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    audit(db, "auth.login", user=user, ip=ip, entity_type="user", entity_id=user.id,
          details={"device": device.pc_name if device else None})
    db.commit()
    secure = config.https
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="strict", secure=secure,
                        max_age=24 * 3600, path="/")
    response.set_cookie(CSRF_COOKIE, csrf, httponly=False, samesite="strict", secure=secure,
                        max_age=24 * 3600, path="/")
    return {"user": user_profile(db, user), "csrf_token": csrf, "session_timeout_minutes": timeout,
            "device": {"id": device.id, "pc_name": device.pc_name, "status": device.status} if device else None}


@router.post("/logout")
def logout(response: Response, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    sess = db.get(UserSession, ctx.session.id)
    if sess:
        sess.revoked_at = utcnow()
    audit(db, "auth.logout", user=ctx.user, ip=ctx.ip, entity_type="user", entity_id=ctx.user.id)
    db.commit()
    hub.close_session(ctx.session.id)
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    from ..models import Device
    dev = db.get(Device, ctx.session.device_id) if ctx.session.device_id else None
    return {"user": user_profile(db, ctx.user), "csrf_token": ctx.session.csrf_token,
            "branding": public_branding(db), "server_ip": config.public_ip, "port": config.port,
            "https": config.https, "version": APP_VERSION, "client_ip": ctx.ip,
            "session_timeout_minutes": app_settings.get(db, "session_timeout_minutes"),
            "device": {"id": dev.id, "pc_name": dev.pc_name, "status": dev.status} if dev else None}


@router.post("/change-password")
def change_password(body: ChangePasswordIn, ctx: Ctx = Depends(get_ctx), db: Session = Depends(get_db)):
    user = db.get(User, ctx.user.id)
    if not verify_password(body.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    problems = check_password_policy(body.new_password, app_settings.get(db, "password_policy") or {})
    if problems:
        raise HTTPException(400, "Password must contain " + ", ".join(problems))
    if body.new_password == body.current_password:
        raise HTTPException(400, "New password must differ from the current password")
    user.password_hash = hash_password(body.new_password)
    user.must_change_password = False
    user.password_changed_at = utcnow()
    # revoke other sessions of this user
    db.query(UserSession).filter(UserSession.user_id == user.id, UserSession.id != ctx.session.id,
                                 UserSession.revoked_at.is_(None)).update({"revoked_at": utcnow()})
    audit(db, "auth.password_changed", user=user, ip=ctx.ip, entity_type="user", entity_id=user.id)
    db.commit()
    return {"ok": True}
