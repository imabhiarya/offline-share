"""User Management with RBAC. Deleting a user is a soft delete so audit history is preserved."""
from __future__ import annotations

import secrets
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import ALL_PERMS, Ctx, effective_permissions, require
from ..models import Device, Permission, Role, Section, User, UserPermission, UserSession, utcnow
from ..realtime import hub
from ..security import check_password_policy, hash_password
from ..services import settings as app_settings
from ..services.common import audit, iso, paginate, local_str
from ..services.excel import read_rows, xlsx_response

router = APIRouter(prefix="/api/users", tags=["users"])


def _dict(db: Session, u: User) -> dict:
    return {
        "id": u.id, "full_name": u.full_name, "login_id": u.login_id, "section_id": u.section_id,
        "section": u.section.name if u.section else "", "assigned_device_id": u.assigned_device_id,
        "assigned_pc": u.assigned_device.pc_name if u.assigned_device else "",
        "mobile": u.mobile, "email": u.email, "role": u.role.code, "role_name": u.role.name, "status": u.status,
        "online": hub.is_online(u.id), "last_login_at": iso(u.last_login_at), "created_at": iso(u.created_at),
        "locked": bool(u.locked_until and u.locked_until > utcnow()),
        "permissions": sorted(effective_permissions(db, u)),
        "permission_overrides": {o.permission_id: o.granted for o in u.permission_overrides},
    }


def _guard_target(ctx: Ctx, target: User) -> None:
    """Only a Super Admin can manage Super Admin accounts; admins cannot manage peers above them."""
    if target.role.code == "super_admin" and not ctx.is_super:
        raise HTTPException(403, "Only a Super Admin can modify a Super Admin account")


@router.get("")
def list_users(q: str = "", role: str = "", section_id: Optional[int] = None, status: str = "", page: int = 1,
               page_size: int = 50, ctx: Ctx = Depends(require("users")), db: Session = Depends(get_db)):
    query = db.query(User).filter(User.is_deleted.is_(False))
    if q.strip():
        like = f"%{q.strip()}%"
        query = query.filter(or_(User.full_name.ilike(like), User.login_id.ilike(like), User.email.ilike(like),
                                 User.mobile.ilike(like)))
    if role:
        query = query.join(Role).filter(Role.code == role)
    if section_id:
        query = query.filter(User.section_id == section_id)
    if status in ("active", "inactive"):
        query = query.filter(User.status == status)
    rows, total, page, page_size = paginate(query.order_by(User.full_name), page, page_size)
    stats = {
        "total": db.query(User).filter(User.is_deleted.is_(False)).count(),
        "active": db.query(User).filter(User.is_deleted.is_(False), User.status == "active").count(),
        "inactive": db.query(User).filter(User.is_deleted.is_(False), User.status == "inactive").count(),
        "online": len(hub.online_user_ids()),
        "admins": db.query(User).join(Role).filter(User.is_deleted.is_(False),
                                                   Role.code.in_(("super_admin", "admin"))).count(),
        "normal": db.query(User).join(Role).filter(User.is_deleted.is_(False), Role.code == "user").count(),
        "readonly": db.query(User).join(Role).filter(User.is_deleted.is_(False), Role.code == "readonly").count(),
        "assigned_pcs": db.query(User).filter(User.is_deleted.is_(False), User.assigned_device_id.is_not(None)).count(),
    }
    return {"items": [_dict(db, u) for u in rows], "total": total, "page": page, "page_size": page_size,
            "stats": stats}


@router.get("/meta")
def meta(ctx: Ctx = Depends(require("users")), db: Session = Depends(get_db)):
    return {
        "roles": [{"code": r.code, "name": r.name, "description": r.description,
                   "permissions": [p.code for p in r.permissions]} for r in db.query(Role).order_by(Role.rank.desc())],
        "permissions": [{"id": p.id, "code": p.code, "name": p.name} for p in db.query(Permission).all()],
        "sections": [{"id": s.id, "name": s.name} for s in db.query(Section).order_by(Section.name)],
        "devices": [{"id": d.id, "pc_name": d.pc_name, "ip_address": d.ip_address}
                    for d in db.query(Device).filter(Device.status != "blocked").order_by(Device.pc_name)],
        "password_policy": app_settings.get(db, "password_policy"),
    }


class UserIn(BaseModel):
    full_name: str = Field(..., min_length=1, max_length=120)
    login_id: str = Field(..., min_length=3, max_length=64, pattern=r"^[A-Za-z0-9._\-]+$")
    password: Optional[str] = None
    section_id: Optional[int] = None
    assigned_device_id: Optional[int] = None
    mobile: str = Field("", max_length=20)
    email: str = Field("", max_length=120)
    role: str = "user"
    status: str = "active"
    permission_overrides: dict[str, bool] = {}  # permission code -> granted


def _apply(db: Session, ctx: Ctx, u: User, body: UserIn) -> None:
    role = db.query(Role).filter_by(code=body.role).first()
    if not role:
        raise HTTPException(400, "Unknown role")
    if role.code == "super_admin" and not ctx.is_super:
        raise HTTPException(403, "Only a Super Admin can assign the Super Admin role")
    if body.status not in ("active", "inactive"):
        raise HTTPException(400, "Invalid status")
    if body.email and "@" not in body.email:
        raise HTTPException(400, "Invalid email address")
    if body.mobile and not body.mobile.replace("+", "").replace(" ", "").replace("-", "").isdigit():
        raise HTTPException(400, "Mobile number may contain digits, spaces, + and - only")
    if body.section_id and not db.get(Section, body.section_id):
        raise HTTPException(400, "Unknown section")
    if body.assigned_device_id and not db.get(Device, body.assigned_device_id):
        raise HTTPException(400, "Unknown device")
    if u.id == ctx.user.id and (body.status != "active" or role.code != u.role.code):
        raise HTTPException(400, "You cannot change your own role or deactivate yourself")
    u.full_name, u.section_id, u.assigned_device_id = body.full_name.strip(), body.section_id, body.assigned_device_id
    u.mobile, u.email, u.role_id, u.status = body.mobile.strip(), body.email.strip(), role.id, body.status
    perms = {p.code: p for p in db.query(Permission).all()}
    if u.id is None:
        db.flush()
    else:
        db.query(UserPermission).filter_by(user_id=u.id).delete()
        db.flush()
        db.expire(u, ["permission_overrides"])
    role_perms = {p.code for p in role.permissions}
    for code, granted in body.permission_overrides.items():
        if code in perms and code in ALL_PERMS and (granted != (code in role_perms)):
            db.add(UserPermission(user_id=u.id, permission_id=perms[code].id, granted=granted))


@router.post("")
def add_user(body: UserIn, ctx: Ctx = Depends(require("users", write=True)), db: Session = Depends(get_db)):
    if db.query(User).filter(User.login_id.ilike(body.login_id)).first():
        raise HTTPException(409, "Login ID already exists")
    if not body.password:
        raise HTTPException(400, "Password is required")
    problems = check_password_policy(body.password, app_settings.get(db, "password_policy") or {})
    if problems:
        raise HTTPException(400, "Password must contain " + ", ".join(problems))
    u = User(full_name="", login_id=body.login_id.strip(), password_hash=hash_password(body.password),
             role_id=0, must_change_password=True)
    db.add(u)
    _apply(db, ctx, u, body)
    audit(db, "user.add", user=ctx.user, ip=ctx.ip, entity_type="user", entity_id=u.id,
          details={"login_id": u.login_id, "role": body.role})
    db.commit()
    db.refresh(u)
    return _dict(db, u)


@router.put("/{user_id}")
def edit_user(user_id: int, body: UserIn, ctx: Ctx = Depends(require("users", write=True)),
              db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.is_deleted:
        raise HTTPException(404, "User not found")
    _guard_target(ctx, u)
    if body.login_id != u.login_id:
        if db.query(User).filter(User.login_id.ilike(body.login_id), User.id != u.id).first():
            raise HTTPException(409, "Login ID already exists")
        u.login_id = body.login_id.strip()
    was_active = u.status == "active"
    _apply(db, ctx, u, body)
    if body.password:
        problems = check_password_policy(body.password, app_settings.get(db, "password_policy") or {})
        if problems:
            raise HTTPException(400, "Password must contain " + ", ".join(problems))
        u.password_hash = hash_password(body.password)
        u.must_change_password = True
    if was_active and u.status != "active":
        _end_sessions(db, u)
    audit(db, "user.edit", user=ctx.user, ip=ctx.ip, entity_type="user", entity_id=u.id,
          details={"login_id": u.login_id, "role": body.role, "status": body.status})
    db.commit()
    db.refresh(u)
    return _dict(db, u)


def _end_sessions(db: Session, u: User) -> None:
    db.query(UserSession).filter(UserSession.user_id == u.id, UserSession.revoked_at.is_(None)).update(
        {"revoked_at": utcnow()})
    hub.close_user(u.id)


class StatusIn(BaseModel):
    status: str


@router.post("/{user_id}/status")
def set_status(user_id: int, body: StatusIn, ctx: Ctx = Depends(require("users", write=True)),
               db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.is_deleted:
        raise HTTPException(404, "User not found")
    _guard_target(ctx, u)
    if u.id == ctx.user.id:
        raise HTTPException(400, "You cannot deactivate yourself")
    if body.status not in ("active", "inactive"):
        raise HTTPException(400, "Invalid status")
    u.status = body.status
    if body.status == "inactive":
        _end_sessions(db, u)
    else:
        u.locked_until, u.failed_logins = None, 0
    audit(db, f"user.{'activate' if body.status == 'active' else 'deactivate'}", user=ctx.user, ip=ctx.ip,
          entity_type="user", entity_id=u.id, details={"login_id": u.login_id})
    db.commit()
    return _dict(db, u)


class ResetIn(BaseModel):
    new_password: Optional[str] = None


@router.post("/{user_id}/reset-password")
def reset_password(user_id: int, body: ResetIn, ctx: Ctx = Depends(require("users", write=True)),
                   db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.is_deleted:
        raise HTTPException(404, "User not found")
    _guard_target(ctx, u)
    pwd = body.new_password or ("Os-" + secrets.token_urlsafe(8) + "9a")
    problems = check_password_policy(pwd, app_settings.get(db, "password_policy") or {})
    if problems:
        raise HTTPException(400, "Password must contain " + ", ".join(problems))
    u.password_hash = hash_password(pwd)
    u.must_change_password = True
    u.locked_until, u.failed_logins = None, 0
    _end_sessions(db, u)
    audit(db, "user.reset_password", user=ctx.user, ip=ctx.ip, entity_type="user", entity_id=u.id,
          details={"login_id": u.login_id})
    db.commit()
    return {"temporary_password": pwd if not body.new_password else None, "ok": True}


@router.delete("/{user_id}")
def delete_user(user_id: int, ctx: Ctx = Depends(require("users", write=True)), db: Session = Depends(get_db)):
    u = db.get(User, user_id)
    if not u or u.is_deleted:
        raise HTTPException(404, "User not found")
    _guard_target(ctx, u)
    if u.id == ctx.user.id:
        raise HTTPException(400, "You cannot delete your own account")
    if u.role.code == "super_admin":
        others = db.query(User).join(Role).filter(Role.code == "super_admin", User.is_deleted.is_(False),
                                                  User.id != u.id).count()
        if not others:
            raise HTTPException(400, "Cannot delete the last Super Admin")
    _end_sessions(db, u)
    old_login = u.login_id
    u.is_deleted, u.deleted_at, u.status = True, utcnow(), "inactive"
    u.login_id = f"{old_login}~deleted~{u.id}"[:64]  # frees the login ID; transfers keep name snapshots
    u.assigned_device_id = None
    audit(db, "user.delete", user=ctx.user, ip=ctx.ip, entity_type="user", entity_id=u.id,
          details={"login_id": old_login, "full_name": u.full_name})
    db.commit()
    return {"ok": True}


USER_HEADERS = ["S.No", "Full Name", "Login ID", "Section", "Assigned PC", "Mobile", "Email", "Role", "Status",
                "Last Login"]


@router.get("/export.xlsx")
def export_users(ctx: Ctx = Depends(require("users")), db: Session = Depends(get_db)):
    rows = []
    for i, u in enumerate(db.query(User).filter(User.is_deleted.is_(False)).order_by(User.full_name), 1):
        rows.append([i, u.full_name, u.login_id, u.section.name if u.section else "",
                     u.assigned_device.pc_name if u.assigned_device else "", u.mobile, u.email, u.role.name,
                     u.status.title(), local_str(u.last_login_at)])
    return xlsx_response("Users", USER_HEADERS, rows, f"users_{datetime.now():%Y%m%d}.xlsx")


@router.get("/import-template.xlsx")
def import_template(ctx: Ctx = Depends(require("users"))):
    return xlsx_response("User Import", ["Full Name", "Login ID", "Password", "Section", "Assigned PC", "Mobile",
                                         "Email", "Role", "Status"],
                         [["Asha Verma", "asha.verma", "Welcome@123", "Accounts", "ACC-PC-01", "9876543210",
                           "asha@office.local", "Normal User", "Active"]], "user_import_template.xlsx")


@router.post("/import")
async def import_users(file: UploadFile = File(...), ctx: Ctx = Depends(require("users", write=True)),
                       db: Session = Depends(get_db)):
    data = await file.read(10 * 1024 * 1024 + 1)
    if len(data) > 10 * 1024 * 1024:
        raise HTTPException(413, "Import file too large")
    try:
        rows = read_rows(data)
    except Exception:
        raise HTTPException(400, "Could not read the Excel file (.xlsx expected)")
    roles = {r.name.lower(): r.code for r in db.query(Role).all()} | {r.code: r.code for r in db.query(Role).all()}
    sections = {s.name.lower(): s.id for s in db.query(Section).all()}
    devices = {d.pc_name.lower(): d.id for d in db.query(Device).all()}
    created, errors = 0, []
    policy = app_settings.get(db, "password_policy") or {}
    for n, r in enumerate(rows, 1):
        login = str(r.get("login_id") or r.get("login") or "").strip()
        name = str(r.get("full_name") or r.get("name") or "").strip()
        if not login or not name:
            errors.append(f"Row {n}: Full Name and Login ID are required")
            continue
        if db.query(User).filter(User.login_id.ilike(login)).first():
            errors.append(f"Row {n}: login '{login}' already exists")
            continue
        pwd = str(r.get("password") or "").strip() or ("Os-" + secrets.token_urlsafe(8) + "9a")
        if check_password_policy(pwd, policy):
            errors.append(f"Row {n}: password for '{login}' does not meet the policy")
            continue
        role_code = roles.get(str(r.get("role") or "Normal User").strip().lower(), "user")
        if role_code == "super_admin" and not ctx.is_super:
            role_code = "admin"
        sp = db.begin_nested()
        try:
            body = UserIn(full_name=name, login_id=login, password=pwd,
                          section_id=sections.get(str(r.get("section") or "").strip().lower()),
                          assigned_device_id=devices.get(str(r.get("assigned_pc") or "").strip().lower()),
                          mobile=str(r.get("mobile") or "").strip(), email=str(r.get("email") or "").strip(),
                          role=role_code,
                          status="inactive" if str(r.get("status") or "").strip().lower() == "inactive" else "active")
            u = User(full_name=name, login_id=login, password_hash=hash_password(pwd), role_id=0,
                     must_change_password=True)
            db.add(u)
            _apply(db, ctx, u, body)
            db.flush()
            sp.commit()
            created += 1
        except HTTPException as e:
            sp.rollback()
            errors.append(f"Row {n}: {e.detail}")
        except Exception as e:  # validation errors
            sp.rollback()
            errors.append(f"Row {n}: {str(e).splitlines()[0]}")
    audit(db, "user.import", user=ctx.user, ip=ctx.ip, details={"created": created, "errors": len(errors)})
    db.commit()
    return {"created": created, "errors": errors}
