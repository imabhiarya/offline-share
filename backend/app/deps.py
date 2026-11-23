"""Authentication, session, CSRF and role-based access control dependencies."""
from __future__ import annotations

import hmac
from dataclasses import dataclass
from datetime import timedelta
from typing import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from .models import Permission, User, UserSession, utcnow
from .security import token_digest
from .services import settings as app_settings
from .services.common import client_ip

SESSION_COOKIE = "os_session"
CSRF_COOKIE = "os_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
ALL_PERMS = ["dashboard", "send", "receive", "history", "devices", "users", "files", "settings"]


@dataclass
class Ctx:
    user: User
    session: UserSession
    ip: str
    perms: set[str]

    @property
    def role(self) -> str:
        return self.user.role.code

    @property
    def is_admin(self) -> bool:
        return self.role in ("super_admin", "admin")

    @property
    def is_super(self) -> bool:
        return self.role == "super_admin"

    @property
    def read_only(self) -> bool:
        return self.role == "readonly"


def effective_permissions(db: Session, user: User) -> set[str]:
    if user.role.code == "super_admin":
        return set(ALL_PERMS)
    perms = {p.code for p in user.role.permissions}
    if user.permission_overrides:
        id_to_code = {p.id: p.code for p in db.query(Permission).all()}
        for o in user.permission_overrides:
            code = id_to_code.get(o.permission_id)
            if not code:
                continue
            if o.granted:
                perms.add(code)
            else:
                perms.discard(code)
    return perms


def load_session(db: Session, token: str | None, touch: bool = True) -> tuple[User, UserSession] | None:
    if not token:
        return None
    sess = db.get(UserSession, token_digest(token))
    now = utcnow()
    if sess is None or sess.revoked_at is not None or sess.expires_at < now:
        return None
    timeout = int(app_settings.get(db, "session_timeout_minutes") or 480)
    if sess.last_seen_at + timedelta(minutes=timeout) < now:
        sess.revoked_at = now
        db.commit()
        return None
    user = db.get(User, sess.user_id)
    if user is None or user.is_deleted or user.status != "active":
        return None
    if touch and (now - sess.last_seen_at).total_seconds() > 30:
        sess.last_seen_at = now
        db.commit()
    return user, sess


def get_ctx(request: Request, db: Session = Depends(get_db)) -> Ctx:
    found = load_session(db, request.cookies.get(SESSION_COOKIE))
    if not found:
        raise HTTPException(401, "Not signed in or session expired")
    user, sess = found
    if request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not hmac.compare_digest(sent, sess.csrf_token):
            raise HTTPException(403, "CSRF token missing or invalid")
    return Ctx(user=user, session=sess, ip=client_ip(request), perms=effective_permissions(db, user))


def require(*perms: str, write: bool = False) -> Callable[[Ctx], Ctx]:
    """Dependency factory: the user must hold every listed permission.
    ``write=True`` additionally refuses Read Only users."""

    def dep(ctx: Ctx = Depends(get_ctx)) -> Ctx:
        missing = [p for p in perms if p not in ctx.perms]
        if missing:
            raise HTTPException(403, f"Permission denied ({', '.join(missing)})")
        if write and ctx.read_only:
            raise HTTPException(403, "Read Only users cannot perform this action")
        return ctx

    return dep


def require_admin(ctx: Ctx = Depends(get_ctx)) -> Ctx:
    if not ctx.is_admin:
        raise HTTPException(403, "Administrator access required")
    return ctx


def require_super(ctx: Ctx = Depends(get_ctx)) -> Ctx:
    if not ctx.is_super:
        raise HTTPException(403, "Super Admin access required")
    return ctx
