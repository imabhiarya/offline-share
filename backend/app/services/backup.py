"""Backup and restore.

A backup is a single .zip containing:
  * ``database/offline_share.db`` – a consistent snapshot taken with SQLite's online backup API
  * ``storage/...``               – the stored files (optional)
  * ``config.json`` and ``manifest.json``
Restore copies the snapshot back into the live database through the same backup API,
so the server does not need to be stopped.
"""
from __future__ import annotations

import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Optional

from .. import database
from ..config import APP_VERSION, config, config_file
from ..models import BackupHistory

log = logging.getLogger("offline_share.backup")


def _snapshot_db(dest: Path) -> None:
    src = sqlite3.connect(str(config.db_path))
    dst = sqlite3.connect(str(dest))
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()


def create_backup(kind: str = "manual", include_files: bool = True, user_id: Optional[int] = None,
                  target_dir: Optional[Path] = None) -> BackupHistory:
    target_dir = Path(target_dir or config.backup_path)
    target_dir.mkdir(parents=True, exist_ok=True)
    name = f"offline_share_{kind}_{datetime.now():%Y%m%d_%H%M%S}.zip"
    final = target_dir / name
    part = target_dir / (name + ".part")
    with tempfile.TemporaryDirectory(dir=config.tmp_path) as td:
        snap = Path(td) / "offline_share.db"
        _snapshot_db(snap)
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
            zf.write(snap, "database/offline_share.db")
            if config_file().exists():
                zf.write(config_file(), "config.json")
            nfiles = 0
            if include_files:
                root = config.storage_path
                for dirpath, dirnames, filenames in os.walk(root):
                    rel_dir = Path(dirpath).relative_to(root)
                    if rel_dir.parts and rel_dir.parts[0] == "_tmp":
                        dirnames[:] = []
                        continue
                    for fn in filenames:
                        p = Path(dirpath) / fn
                        zf.write(p, f"storage/{(rel_dir / fn).as_posix()}", compress_type=zipfile.ZIP_STORED)
                        nfiles += 1
            zf.writestr("manifest.json", json.dumps({
                "app": "OFFLINE SHARE", "version": APP_VERSION, "created": datetime.now().isoformat(),
                "kind": kind, "include_files": include_files, "file_count": nfiles}, indent=2))
    os.replace(part, final)
    with database.db_session() as db:
        rec = BackupHistory(filename=name, path=str(final), size=final.stat().st_size, kind=kind,
                            includes_files=include_files, status="success", created_by=user_id,
                            message=f"{'Database + files' if include_files else 'Database only'}")
        db.add(rec)
        db.flush()
        db.expunge(rec)
    log.info("Backup created: %s", final)
    return rec


def prune(keep: int) -> int:
    if keep <= 0:
        return 0
    files = sorted(config.backup_path.glob("offline_share_scheduled_*.zip"), key=lambda p: p.stat().st_mtime,
                   reverse=True)
    removed = 0
    for p in files[keep:]:
        p.unlink(missing_ok=True)
        removed += 1
    return removed


def validate_backup(path: Path) -> dict:
    with zipfile.ZipFile(path) as zf:
        names = set(zf.namelist())
        if "database/offline_share.db" not in names or "manifest.json" not in names:
            raise ValueError("Not an OFFLINE SHARE backup (manifest or database missing)")
        for n in names:
            if n.startswith("/") or ".." in Path(n).parts:
                raise ValueError("Backup contains unsafe paths")
        return json.loads(zf.read("manifest.json"))


def restore_backup(path: Path, restore_files: bool = True, user_id: Optional[int] = None) -> dict:
    manifest = validate_backup(path)
    # safety net: snapshot the current state first
    pre = create_backup("pre-restore", include_files=False, user_id=user_id)
    with tempfile.TemporaryDirectory(dir=config.tmp_path) as td:
        with zipfile.ZipFile(path) as zf:
            zf.extract("database/offline_share.db", td)
            db_src = Path(td) / "database" / "offline_share.db"
            chk = sqlite3.connect(str(db_src))
            ok = chk.execute("PRAGMA integrity_check").fetchone()[0]
            chk.close()
            if ok != "ok":
                raise ValueError(f"Backup database failed integrity check: {ok}")
            database.engine.dispose()
            src = sqlite3.connect(str(db_src))
            dst = sqlite3.connect(str(config.db_path))
            try:
                src.backup(dst)
            finally:
                dst.close()
                src.close()
            restored_files = 0
            if restore_files and manifest.get("include_files"):
                root = config.storage_path.resolve()
                for info in zf.infolist():
                    if not info.filename.startswith("storage/") or info.is_dir():
                        continue
                    rel = info.filename[len("storage/"):]
                    dest = (root / rel).resolve()
                    if root not in dest.parents:
                        continue
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    with zf.open(info) as s, open(dest, "wb") as d:
                        shutil.copyfileobj(s, d, 1024 * 1024)
                    restored_files += 1
    database.reset_engine()
    from . import settings as app_settings
    app_settings.invalidate()
    from ..migrations import migrate
    migrate()  # bring an older backup up to the current schema
    with database.db_session() as db:
        db.add(BackupHistory(filename=path.name, path=str(path), size=path.stat().st_size, kind="restore",
                             includes_files=restore_files, status="success", created_by=None,
                             message=f"Restored ({restored_files} files). Safety copy: {pre.filename}"))
    return {"manifest": manifest, "restored_files": restored_files, "safety_backup": pre.filename}
