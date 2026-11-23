"""File Depository: central repository with folders, access permissions, versions and a recycle bin."""
from __future__ import annotations

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import Ctx, require
from ..models import AuditLog, FilePermission, FileVersion, Folder, RepoFile, User, utcnow
from ..services import search, storage
from ..services import settings as app_settings
from ..services.common import audit, iso, notify, paginate
from ..realtime import hub

router = APIRouter(prefix="/api/files", tags=["files"])


# --------------------------------------------------------------------------- access helpers
def _visible_filter(ctx: Ctx):
    if ctx.is_admin:
        return None
    me = ctx.user.id
    shared_ids = FilePermission.__table__.select().with_only_columns(FilePermission.file_id).where(
        FilePermission.user_id == me)
    conds = [RepoFile.access_scope == "all", RepoFile.uploaded_by == me, RepoFile.id.in_(shared_ids)]
    if ctx.user.section_id:
        conds.append((RepoFile.access_scope == "section") & (RepoFile.section_id == ctx.user.section_id))
    return or_(*conds)


def _can_view(ctx: Ctx, f: RepoFile) -> bool:
    if ctx.is_admin or f.uploaded_by == ctx.user.id or f.access_scope == "all":
        return True
    if f.access_scope == "section" and f.section_id and f.section_id == ctx.user.section_id:
        return True
    return any(p.user_id == ctx.user.id for p in f.allowed_users)


def _can_modify(ctx: Ctx, f: RepoFile) -> bool:
    return not ctx.read_only and (ctx.is_admin or f.uploaded_by == ctx.user.id)


def _get_file(db: Session, ctx: Ctx, file_id: int, include_deleted: bool = False) -> RepoFile:
    f = db.get(RepoFile, file_id)
    if not f or (f.deleted_at and not include_deleted) or not _can_view(ctx, f):
        raise HTTPException(404, "File not found")
    return f


def _file_dict(f: RepoFile, ctx: Optional[Ctx] = None) -> dict:
    return {
        "id": f.id, "uid": f.uid, "name": f.name, "extension": f.extension, "mime_type": f.mime_type, "size": f.size,
        "folder_id": f.folder_id, "folder": f.folder.name if f.folder else "", "description": f.description,
        "access_scope": f.access_scope, "section_id": f.section_id,
        "allowed_user_ids": [p.user_id for p in f.allowed_users], "uploaded_by": f.uploaded_by,
        "uploaded_by_name": f.uploaded_by_name, "created_at": iso(f.created_at), "updated_at": iso(f.updated_at),
        "version": f.current_version, "deleted_at": iso(f.deleted_at), "sha256": f.sha256,
        "storage_location": f"repository/{f.folder.name if f.folder else ''}/{f.name}",
        "can_modify": _can_modify(ctx, f) if ctx else False,
    }


def repository_usage(db: Session) -> int:
    return int(db.query(func.coalesce(func.sum(FileVersion.size), 0)).scalar() or 0)


def _check_quota(db: Session, incoming: int = 0) -> None:
    quota = float(app_settings.get(db, "repository_quota_gb") or 0) * 1024 ** 3
    if quota and repository_usage(db) + incoming > quota:
        raise HTTPException(507, "Repository storage quota exceeded. Ask the administrator to free space.")


def _log(db: Session, ctx: Ctx, action: str, f: RepoFile, details: Optional[dict] = None) -> None:
    audit(db, f"file.{action}", user=ctx.user, ip=ctx.ip, entity_type="file", entity_id=f.id,
          details={"name": f.name, **(details or {})})


# --------------------------------------------------------------------------- folders
@router.get("/folders")
def folders(ctx: Ctx = Depends(require("files")), db: Session = Depends(get_db)):
    vis = _visible_filter(ctx)
    q = db.query(RepoFile.folder_id, func.count(RepoFile.id)).filter(RepoFile.deleted_at.is_(None))
    if vis is not None:
        q = q.filter(vis)
    counts = dict(q.group_by(RepoFile.folder_id).all())
    fs = db.query(Folder).filter(Folder.deleted_at.is_(None)).order_by(Folder.is_system.desc(), Folder.id).all()
    total = sum(counts.values())
    shared = db.query(RepoFile).join(FilePermission).filter(FilePermission.user_id == ctx.user.id,
                                                            RepoFile.deleted_at.is_(None),
                                                            RepoFile.uploaded_by != ctx.user.id).count()
    rq = db.query(RepoFile).filter(RepoFile.deleted_at.is_not(None))
    if not ctx.is_admin:
        rq = rq.filter(or_(RepoFile.uploaded_by == ctx.user.id, RepoFile.deleted_by == ctx.user.id))
    return {"folders": [{"id": f.id, "name": f.name, "parent_id": f.parent_id, "is_system": f.is_system,
                         "system_key": f.system_key, "count": counts.get(f.id, 0)} for f in fs],
            "virtual": {"all": total, "shared": shared, "recycle": rq.count()}}


class FolderIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    parent_id: Optional[int] = None


@router.post("/folders")
def create_folder(body: FolderIn, ctx: Ctx = Depends(require("files", write=True)), db: Session = Depends(get_db)):
    name = storage.clean_filename(body.name)
    if body.parent_id and not db.get(Folder, body.parent_id):
        raise HTTPException(404, "Parent folder not found")
    if db.query(Folder).filter(Folder.parent_id.is_(body.parent_id) if body.parent_id is None else
                               Folder.parent_id == body.parent_id, Folder.name.ilike(name),
                               Folder.deleted_at.is_(None)).first():
        raise HTTPException(409, "A folder with this name already exists here")
    f = Folder(name=name, parent_id=body.parent_id, created_by=ctx.user.id)
    db.add(f)
    db.flush()
    audit(db, "folder.create", user=ctx.user, ip=ctx.ip, entity_type="folder", entity_id=f.id, details={"name": name})
    db.commit()
    return {"id": f.id, "name": f.name, "parent_id": f.parent_id}


@router.patch("/folders/{folder_id}")
def rename_folder(folder_id: int, body: FolderIn, ctx: Ctx = Depends(require("files", write=True)),
                  db: Session = Depends(get_db)):
    f = db.get(Folder, folder_id)
    if not f or f.deleted_at:
        raise HTTPException(404, "Folder not found")
    if f.is_system and not ctx.is_admin:
        raise HTTPException(403, "System folders can only be renamed by an administrator")
    if not ctx.is_admin and f.created_by != ctx.user.id:
        raise HTTPException(403, "Only the folder creator or an administrator can rename it")
    old = f.name
    f.name = storage.clean_filename(body.name)
    audit(db, "folder.rename", user=ctx.user, ip=ctx.ip, entity_type="folder", entity_id=f.id,
          details={"from": old, "to": f.name})
    db.commit()
    return {"id": f.id, "name": f.name}


@router.delete("/folders/{folder_id}")
def delete_folder(folder_id: int, ctx: Ctx = Depends(require("files", write=True)), db: Session = Depends(get_db)):
    f = db.get(Folder, folder_id)
    if not f or f.deleted_at:
        raise HTTPException(404, "Folder not found")
    if f.is_system:
        raise HTTPException(400, "System folders cannot be deleted")
    if not ctx.is_admin and f.created_by != ctx.user.id:
        raise HTTPException(403, "Only the folder creator or an administrator can delete it")
    if db.query(RepoFile).filter(RepoFile.folder_id == f.id, RepoFile.deleted_at.is_(None)).count() or \
            db.query(Folder).filter(Folder.parent_id == f.id, Folder.deleted_at.is_(None)).count():
        raise HTTPException(400, "Folder is not empty")
    f.deleted_at = utcnow()
    audit(db, "folder.delete", user=ctx.user, ip=ctx.ip, entity_type="folder", entity_id=f.id, details={"name": f.name})
    db.commit()
    return {"ok": True}


# --------------------------------------------------------------------------- listing
@router.get("")
def list_files(view: str = "all", folder_id: Optional[int] = None, q: str = "", file_type: str = "",
               sort: str = "date", page: int = 1, page_size: int = 50, ctx: Ctx = Depends(require("files")),
               db: Session = Depends(get_db)):
    query = db.query(RepoFile)
    if view == "recycle":
        query = query.filter(RepoFile.deleted_at.is_not(None))
        if not ctx.is_admin:
            query = query.filter(or_(RepoFile.uploaded_by == ctx.user.id, RepoFile.deleted_by == ctx.user.id))
    else:
        query = query.filter(RepoFile.deleted_at.is_(None))
        vis = _visible_filter(ctx)
        if vis is not None:
            query = query.filter(vis)
        if view == "shared":
            query = query.join(FilePermission).filter(FilePermission.user_id == ctx.user.id,
                                                      RepoFile.uploaded_by != ctx.user.id)
        elif view == "folder" and folder_id:
            query = query.filter(RepoFile.folder_id == folder_id)
    if q.strip():
        ids = search.search_file_ids(db, q) or []
        like = f"%{q.strip()}%"
        query = query.filter(or_(RepoFile.id.in_(ids), RepoFile.name.ilike(like)))
    if file_type:
        query = query.filter(RepoFile.extension == file_type.lower().lstrip("."))
    order = {"name": RepoFile.name.asc(), "size": RepoFile.size.desc(), "type": RepoFile.extension.asc()}.get(
        sort, RepoFile.updated_at.desc())
    rows, total, page, page_size = paginate(query.order_by(order), page, page_size)
    return {"items": [_file_dict(f, ctx) for f in rows], "total": total, "page": page, "page_size": page_size}


@router.get("/storage")
def storage_info(ctx: Ctx = Depends(require("files")), db: Session = Depends(get_db)):
    quota = float(app_settings.get(db, "repository_quota_gb") or 0) * 1024 ** 3
    used = repository_usage(db)
    month_start = utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    up = db.query(func.count(FileVersion.id), func.coalesce(func.sum(FileVersion.size), 0)).filter(
        FileVersion.created_at >= month_start).one()
    dl_ids = [int(e) for (e,) in db.query(AuditLog.entity_id).filter(
        AuditLog.action == "file.download", AuditLog.created_at >= month_start).all() if e.isdigit()]
    dl_bytes = 0
    if dl_ids:
        sizes = dict(db.query(RepoFile.id, RepoFile.size).filter(RepoFile.id.in_(set(dl_ids))).all())
        dl_bytes = sum(sizes.get(i, 0) for i in dl_ids)
    return {"used": used, "quota": int(quota), "percent": round(used / quota * 100, 1) if quota else 0,
            "files": db.query(RepoFile).filter(RepoFile.deleted_at.is_(None)).count(),
            "folders": db.query(Folder).filter(Folder.deleted_at.is_(None)).count(),
            "month_uploads": int(up[0]), "month_upload_bytes": int(up[1]),
            "month_downloads": len(dl_ids), "month_download_bytes": dl_bytes}


# --------------------------------------------------------------------------- upload
def _parse_ids(raw: str) -> list[int]:
    try:
        return [int(x) for x in json.loads(raw or "[]")]
    except (ValueError, TypeError):
        return [int(x) for x in (raw or "").split(",") if x.strip().isdigit()]


def _set_access(db: Session, f: RepoFile, scope: str, section_id: Optional[int], user_ids: list[int]) -> list[int]:
    if scope not in ("all", "section", "specific"):
        raise HTTPException(400, "Access must be all, section or specific")
    if scope == "section" and not section_id:
        raise HTTPException(400, "Choose a section for section-only access")
    f.access_scope = scope
    f.section_id = section_id if scope == "section" else None
    before = {p.user_id for p in f.allowed_users}
    f.allowed_users.clear()
    db.flush()
    if scope == "specific":
        valid = {u.id for u in db.query(User).filter(User.id.in_(user_ids), User.is_deleted.is_(False))}
        for uid in valid:
            f.allowed_users.append(FilePermission(file_id=f.id, user_id=uid))
        return sorted(valid - before)
    return []


@router.post("/upload")
async def upload(file: UploadFile = File(...), folder_id: int = Form(...), access_scope: str = Form("all"),
                 section_id: Optional[int] = Form(None), user_ids: str = Form("[]"), description: str = Form(""),
                 on_duplicate: str = Form("ask"), ctx: Ctx = Depends(require("files", write=True)),
                 db: Session = Depends(get_db)):
    folder = db.get(Folder, folder_id)
    if not folder or folder.deleted_at:
        raise HTTPException(404, "Folder not found")
    s = app_settings.get_all(db)
    name = storage.clean_filename(file.filename or "file")
    ext = storage.check_extension(name, s["allowed_extensions"], bool(s.get("file_whitelist_enforced", True)))
    existing = db.query(RepoFile).filter(RepoFile.folder_id == folder.id, RepoFile.name.ilike(name),
                                         RepoFile.deleted_at.is_(None)).first()
    if existing and on_duplicate == "ask":
        return JSONResponse(status_code=409, content={
            "detail": f"'{name}' already exists in {folder.name}", "duplicate": "name",
            "existing": _file_dict(existing, ctx)})
    if existing and on_duplicate == "version" and not _can_modify(ctx, existing):
        raise HTTPException(403, "You cannot add a version to a file you do not own")
    if existing and on_duplicate == "skip":
        return {"skipped": True, "file": _file_dict(existing, ctx)}
    _check_quota(db)
    rel, size, digest = await storage.save_upload(file, "repository", int(s["max_file_size_mb"]) * 1024 * 1024)
    try:
        _check_quota(db, 0)
    except HTTPException:
        storage.delete_stored(rel)
        raise
    same_hash = (db.query(RepoFile).filter(RepoFile.sha256 == digest, RepoFile.deleted_at.is_(None)).first()
                 if not existing else None)
    if existing and on_duplicate == "version":
        f = existing
        f.current_version += 1
        f.stored_path, f.size, f.sha256 = rel, size, digest
        f.updated_at = utcnow()
        db.add(FileVersion(file_id=f.id, version=f.current_version, stored_path=rel, size=size, sha256=digest,
                           uploaded_by=ctx.user.id, uploaded_by_name=ctx.user.full_name, note=description[:255]))
        _log(db, ctx, "new_version", f, {"version": f.current_version})
    else:
        if existing:  # rename
            stem, dot, ext2 = name.rpartition(".")
            n = 2
            while db.query(RepoFile).filter(RepoFile.folder_id == folder.id, RepoFile.name.ilike(name),
                                            RepoFile.deleted_at.is_(None)).first():
                name = f"{stem or ext2} ({n}){dot}{ext2 if stem else ''}"
                n += 1
        f = RepoFile(folder_id=folder.id, name=name, extension=ext, mime_type=storage.guess_mime(name), size=size,
                     sha256=digest, stored_path=rel, description=description[:500], uploaded_by=ctx.user.id,
                     uploaded_by_name=ctx.user.full_name)
        db.add(f)
        db.flush()
        db.add(FileVersion(file_id=f.id, version=1, stored_path=rel, size=size, sha256=digest,
                           uploaded_by=ctx.user.id, uploaded_by_name=ctx.user.full_name, note="Initial upload"))
        newly = _set_access(db, f, access_scope, section_id, _parse_ids(user_ids))
        _notify_shared(db, ctx, f, newly)
        _log(db, ctx, "upload", f, {"folder": folder.name, "size": size})
    search.index_file(db, f)
    db.commit()
    db.refresh(f)
    out = {"file": _file_dict(f, ctx)}
    if same_hash:
        out["warning"] = f"Identical content already exists as '{same_hash.name}' in {same_hash.folder.name}"
    return out


def _notify_shared(db: Session, ctx: Ctx, f: RepoFile, user_ids: list[int]) -> None:
    for uid in user_ids:
        if uid != ctx.user.id:
            notify(db, uid, "file_shared", f"File shared: {f.name}", f"{ctx.user.full_name} shared a file with you",
                   "/files?view=shared")
            hub.send_user(uid, {"type": "notification"})


# --------------------------------------------------------------------------- single file
@router.get("/{file_id}")
def file_detail(file_id: int, ctx: Ctx = Depends(require("files")), db: Session = Depends(get_db)):
    f = _get_file(db, ctx, file_id, include_deleted=True)
    versions = db.query(FileVersion).filter_by(file_id=f.id).order_by(FileVersion.version.desc()).all()
    logs = (db.query(AuditLog).filter(AuditLog.entity_type == "file", AuditLog.entity_id == str(f.id))
            .order_by(AuditLog.created_at.desc()).limit(100).all())
    users = db.query(User).filter(User.id.in_([p.user_id for p in f.allowed_users])).all()
    return {**_file_dict(f, ctx),
            "allowed_users": [{"id": u.id, "full_name": u.full_name} for u in users],
            "versions": [{"version": v.version, "size": v.size, "sha256": v.sha256, "uploaded_by": v.uploaded_by_name,
                          "created_at": iso(v.created_at), "note": v.note, "current": v.version == f.current_version}
                         for v in versions],
            "activity": [{"action": a.action.replace("file.", ""), "user": a.user_name, "ip": a.ip_address,
                          "at": iso(a.created_at), "details": a.details} for a in logs]}


@router.get("/{file_id}/download")
def download(file_id: int, inline: bool = Query(False), version: Optional[int] = None,
             ctx: Ctx = Depends(require("files")), db: Session = Depends(get_db)):
    f = _get_file(db, ctx, file_id)
    rel = f.stored_path
    if version and version != f.current_version:
        v = db.query(FileVersion).filter_by(file_id=f.id, version=version).first()
        if not v:
            raise HTTPException(404, "Version not found")
        rel = v.stored_path
    path = storage.resolve(rel)
    if not path.exists():
        raise HTTPException(410, "Stored file is missing on the server")
    if not inline:
        _log(db, ctx, "download", f, {"version": version or f.current_version})
        db.commit()
    fname = f.name if not version or version == f.current_version else f"v{version}_{f.name}"
    return FileResponse(path, media_type=f.mime_type, filename=fname,
                        content_disposition_type="inline" if inline else "attachment")


class FileUpdateIn(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    access_scope: Optional[str] = None
    section_id: Optional[int] = None
    user_ids: Optional[list[int]] = None


@router.patch("/{file_id}")
def update_file(file_id: int, body: FileUpdateIn, ctx: Ctx = Depends(require("files", write=True)),
                db: Session = Depends(get_db)):
    f = _get_file(db, ctx, file_id)
    if not _can_modify(ctx, f):
        raise HTTPException(403, "Only the uploader or an administrator can change this file")
    if body.name is not None:
        new = storage.clean_filename(body.name)
        if storage.extension_of(new) != f.extension:
            new = f"{new}.{f.extension}" if f.extension else new
        if db.query(RepoFile).filter(RepoFile.folder_id == f.folder_id, RepoFile.name.ilike(new), RepoFile.id != f.id,
                                     RepoFile.deleted_at.is_(None)).first():
            raise HTTPException(409, "A file with this name already exists in the folder")
        _log(db, ctx, "rename", f, {"from": f.name, "to": new})
        f.name = new
    if body.description is not None:
        f.description = body.description[:500]
    if body.access_scope is not None:
        newly = _set_access(db, f, body.access_scope, body.section_id, body.user_ids or [])
        _notify_shared(db, ctx, f, newly)
        _log(db, ctx, "share", f, {"scope": body.access_scope, "users": body.user_ids or [],
                                   "section_id": body.section_id})
    search.index_file(db, f)
    db.commit()
    db.refresh(f)
    return _file_dict(f, ctx)


class TargetIn(BaseModel):
    folder_id: int


@router.post("/{file_id}/move")
def move_file(file_id: int, body: TargetIn, ctx: Ctx = Depends(require("files", write=True)),
              db: Session = Depends(get_db)):
    f = _get_file(db, ctx, file_id)
    if not _can_modify(ctx, f):
        raise HTTPException(403, "Only the uploader or an administrator can move this file")
    target = db.get(Folder, body.folder_id)
    if not target or target.deleted_at:
        raise HTTPException(404, "Target folder not found")
    if db.query(RepoFile).filter(RepoFile.folder_id == target.id, RepoFile.name.ilike(f.name),
                                 RepoFile.deleted_at.is_(None)).first():
        raise HTTPException(409, f"'{f.name}' already exists in {target.name}")
    _log(db, ctx, "move", f, {"from": f.folder.name, "to": target.name})
    f.folder_id = target.id
    db.commit()
    db.refresh(f)
    return _file_dict(f, ctx)


@router.post("/{file_id}/copy")
def copy_file(file_id: int, body: TargetIn, ctx: Ctx = Depends(require("files", write=True)),
              db: Session = Depends(get_db)):
    f = _get_file(db, ctx, file_id)
    target = db.get(Folder, body.folder_id)
    if not target or target.deleted_at:
        raise HTTPException(404, "Target folder not found")
    _check_quota(db, f.size)
    name = f.name
    stem, dot, ext = name.rpartition(".")
    n = 1
    while db.query(RepoFile).filter(RepoFile.folder_id == target.id, RepoFile.name.ilike(name),
                                    RepoFile.deleted_at.is_(None)).first():
        name = f"{stem or ext} - Copy{'' if n == 1 else f' ({n})'}{dot}{ext if stem else ''}"
        n += 1
    rel = storage.copy_stored(f.stored_path, "repository")
    c = RepoFile(folder_id=target.id, name=name, extension=f.extension, mime_type=f.mime_type, size=f.size,
                 sha256=f.sha256, stored_path=rel, description=f.description, uploaded_by=ctx.user.id,
                 uploaded_by_name=ctx.user.full_name, access_scope=f.access_scope, section_id=f.section_id)
    db.add(c)
    db.flush()
    for p in f.allowed_users:
        c.allowed_users.append(FilePermission(file_id=c.id, user_id=p.user_id))
    db.add(FileVersion(file_id=c.id, version=1, stored_path=rel, size=c.size, sha256=c.sha256,
                       uploaded_by=ctx.user.id, uploaded_by_name=ctx.user.full_name, note=f"Copied from {f.name}"))
    _log(db, ctx, "copy", f, {"to": target.name, "new_id": c.id})
    search.index_file(db, c)
    db.commit()
    db.refresh(c)
    return _file_dict(c, ctx)


@router.post("/{file_id}/versions/{version}/restore")
def restore_version(file_id: int, version: int, ctx: Ctx = Depends(require("files", write=True)),
                    db: Session = Depends(get_db)):
    f = _get_file(db, ctx, file_id)
    if not _can_modify(ctx, f):
        raise HTTPException(403, "Only the uploader or an administrator can restore versions")
    v = db.query(FileVersion).filter_by(file_id=f.id, version=version).first()
    if not v:
        raise HTTPException(404, "Version not found")
    rel = storage.copy_stored(v.stored_path, "repository")
    f.current_version += 1
    f.stored_path, f.size, f.sha256 = rel, v.size, v.sha256
    db.add(FileVersion(file_id=f.id, version=f.current_version, stored_path=rel, size=v.size, sha256=v.sha256,
                       uploaded_by=ctx.user.id, uploaded_by_name=ctx.user.full_name,
                       note=f"Restored from version {version}"))
    _log(db, ctx, "restore_version", f, {"from_version": version})
    db.commit()
    return _file_dict(f, ctx)


@router.delete("/{file_id}")
def recycle(file_id: int, ctx: Ctx = Depends(require("files", write=True)), db: Session = Depends(get_db)):
    f = _get_file(db, ctx, file_id)
    if not _can_modify(ctx, f):
        raise HTTPException(403, "Only the uploader or an administrator can delete this file")
    f.deleted_at, f.deleted_by = utcnow(), ctx.user.id
    _log(db, ctx, "delete", f)
    db.commit()
    return {"ok": True}


@router.post("/{file_id}/restore")
def restore(file_id: int, ctx: Ctx = Depends(require("files", write=True)), db: Session = Depends(get_db)):
    f = _get_file(db, ctx, file_id, include_deleted=True)
    if not f.deleted_at:
        raise HTTPException(400, "File is not in the Recycle Bin")
    if not _can_modify(ctx, f) and f.deleted_by != ctx.user.id:
        raise HTTPException(403, "Not allowed")
    folder = db.get(Folder, f.folder_id)
    if not folder or folder.deleted_at:
        f.folder_id = db.query(Folder).filter_by(system_key="archive").one().id
    if db.query(RepoFile).filter(RepoFile.folder_id == f.folder_id, RepoFile.name.ilike(f.name),
                                 RepoFile.deleted_at.is_(None), RepoFile.id != f.id).first():
        stem, dot, ext = f.name.rpartition(".")
        f.name = f"{stem or ext} (restored){dot}{ext if stem else ''}"
    f.deleted_at, f.deleted_by = None, None
    _log(db, ctx, "restore", f)
    search.index_file(db, f)
    db.commit()
    return _file_dict(f, ctx)


def _purge(db: Session, f: RepoFile) -> None:
    for v in db.query(FileVersion).filter_by(file_id=f.id).all():
        storage.delete_stored(v.stored_path)
    storage.delete_stored(f.stored_path)
    search.unindex_file(db, f.id)
    db.delete(f)


@router.delete("/{file_id}/permanent")
def delete_permanently(file_id: int, ctx: Ctx = Depends(require("files", write=True)), db: Session = Depends(get_db)):
    f = _get_file(db, ctx, file_id, include_deleted=True)
    if not f.deleted_at:
        raise HTTPException(400, "Move the file to the Recycle Bin first")
    if not _can_modify(ctx, f):
        raise HTTPException(403, "Not allowed")
    _log(db, ctx, "purge", f)
    _purge(db, f)
    db.commit()
    return {"ok": True}


@router.post("/recycle/empty")
def empty_recycle(ctx: Ctx = Depends(require("files", write=True)), db: Session = Depends(get_db)):
    q = db.query(RepoFile).filter(RepoFile.deleted_at.is_not(None))
    if not ctx.is_admin:
        q = q.filter(RepoFile.uploaded_by == ctx.user.id)
    n = 0
    for f in q.all():
        _purge(db, f)
        n += 1
    audit(db, "file.recycle_empty", user=ctx.user, ip=ctx.ip, details={"count": n})
    db.commit()
    return {"purged": n}
