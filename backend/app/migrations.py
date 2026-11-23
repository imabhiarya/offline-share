"""Versioned schema migrations and initial seed data.

Each migration runs inside a transaction and is recorded in ``schema_migrations``.
Add new migrations to ``MIGRATIONS`` with an increasing version number; never edit
a migration that has already shipped.
"""
from __future__ import annotations

import logging
import os
import secrets
from typing import Callable

from sqlalchemy import text
from sqlalchemy.engine import Connection

from . import database
from .config import config
from .database import Base
from . import models  # noqa: F401  (register tables)

log = logging.getLogger("offline_share.migrations")


def _m001_initial(conn: Connection) -> None:
    Base.metadata.create_all(conn)
    conn.execute(text(
        "CREATE VIRTUAL TABLE IF NOT EXISTS search_messages USING fts5("
        "transfer_id UNINDEXED, transfer_uid, subject, body, filenames, sender, tokenize='unicode61')"))
    conn.execute(text(
        "CREATE VIRTUAL TABLE IF NOT EXISTS search_files USING fts5("
        "file_id UNINDEXED, name, description, uploader, tokenize='unicode61')"))


def _m002_extra_indexes(conn: Connection) -> None:
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_tr_status_attempt ON transfer_recipients(status, last_attempt_at)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_transfers_sender_created ON transfers(sender_user_id, created_at)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_notifications_user_read ON notifications(user_id, is_read)"))


MIGRATIONS: list[tuple[int, str, Callable[[Connection], None]]] = [
    (1, "initial schema", _m001_initial),
    (2, "performance indexes", _m002_extra_indexes),
]


def current_version(conn: Connection) -> int:
    conn.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations ("
                      "version INTEGER PRIMARY KEY, description TEXT, applied_at TEXT DEFAULT CURRENT_TIMESTAMP)"))
    v = conn.execute(text("SELECT MAX(version) FROM schema_migrations")).scalar()
    return int(v or 0)


def migrate() -> int:
    with database.engine.begin() as conn:
        ver = current_version(conn)
    for version, desc, fn in MIGRATIONS:
        if version <= ver:
            continue
        with database.engine.begin() as conn:
            log.info("Applying migration %s: %s", version, desc)
            fn(conn)
            conn.execute(text("INSERT INTO schema_migrations(version, description) VALUES (:v, :d)"),
                         {"v": version, "d": desc})
        ver = version
    return ver


# --------------------------------------------------------------------------- seed data
PERMISSIONS = [
    ("dashboard", "Dashboard"), ("send", "Send Data"), ("receive", "Receive Data"),
    ("history", "Transfer History"), ("devices", "Connected Devices"), ("users", "User Management"),
    ("files", "File Depository"), ("settings", "Settings"),
]
ROLES = [
    ("super_admin", "Super Admin", "Full control including security, backup and restore", 100,
     [p for p, _ in PERMISSIONS]),
    ("admin", "Administrator", "Manages users, devices and transfers", 50, [p for p, _ in PERMISSIONS]),
    ("user", "Normal User", "Sends and receives data, uses the file depository", 10,
     ["dashboard", "send", "receive", "history", "files"]),
    ("readonly", "Read Only User", "Can receive and view but cannot send or upload", 1,
     ["dashboard", "receive", "history", "files"]),
]
SECTIONS = [("Administration", "ADM"), ("Accounts", "ACC"), ("Store", "STR"), ("Engineering", "ENG"),
            ("Technical", "TEC"), ("Audit", "AUD")]
SYSTEM_FOLDERS = [
    ("Administration", "administration"), ("Accounts", "accounts"), ("Store", "store"),
    ("Engineering", "engineering"), ("Technical", "technical"), ("Audit Reports", "audit_reports"),
    ("Policies & Orders", "policies"), ("Forms & Templates", "forms"), ("Circulars", "circulars"),
    ("Archive", "archive"),
]


def seed() -> str | None:
    """Insert reference data. Returns a generated admin password if one was created."""
    from .models import Folder, Permission, Role, RolePermission, Section, User
    from .security import hash_password

    generated = None
    with database.db_session() as db:
        perms = {p.code: p for p in db.query(Permission).all()}
        for code, name in PERMISSIONS:
            if code not in perms:
                perms[code] = Permission(code=code, name=name)
                db.add(perms[code])
        db.flush()
        for code, name, desc, rank, plist in ROLES:
            role = db.query(Role).filter_by(code=code).first()
            if role is None:
                role = Role(code=code, name=name, description=desc, rank=rank)
                db.add(role)
                db.flush()
                for p in plist:
                    db.add(RolePermission(role_id=role.id, permission_id=perms[p].id))
        for name, code in SECTIONS:
            if not db.query(Section).filter_by(name=name).first():
                db.add(Section(name=name, code=code))
        for name, key in SYSTEM_FOLDERS:
            if not db.query(Folder).filter_by(system_key=key).first():
                db.add(Folder(name=name, parent_id=None, is_system=True, system_key=key))
        db.flush()
        if not db.query(User).join(Role).filter(Role.code == "super_admin", User.is_deleted.is_(False)).first():
            pwd = os.environ.get("OFFLINE_SHARE_ADMIN_PASSWORD") or ("Adm-" + secrets.token_urlsafe(9))
            sa = db.query(Role).filter_by(code="super_admin").one()
            adm_section = db.query(Section).filter_by(name="Administration").first()
            existing = db.query(User).filter_by(login_id="admin").first()
            if existing is None:
                db.add(User(full_name="System Administrator", login_id="admin", password_hash=hash_password(pwd),
                            role_id=sa.id, section_id=adm_section.id if adm_section else None,
                            must_change_password=not os.environ.get("OFFLINE_SHARE_ADMIN_PASSWORD")))
                generated = pwd
                if not os.environ.get("OFFLINE_SHARE_ADMIN_PASSWORD"):
                    note = config.home / "INITIAL_ADMIN_PASSWORD.txt"
                    note.write_text(
                        "OFFLINE SHARE initial administrator account\n"
                        f"Login ID : admin\nPassword : {pwd}\n\n"
                        "You will be asked to change this password at first login.\n"
                        "Delete this file after signing in.\n", encoding="utf-8")
                    log.warning("Created initial admin account; password written to %s", note)
    return generated


def init_database() -> None:
    config.ensure_dirs()
    migrate()
    seed()
