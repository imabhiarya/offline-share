"""Typed application settings stored in the ``application_settings`` table."""
from __future__ import annotations

import json
import threading
from typing import Any

from sqlalchemy.orm import Session

from ..models import AppSetting

DEFAULT_EXTENSIONS = ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "jpg", "jpeg", "png", "zip"]

# key -> (default, group)
DEFAULTS: dict[str, tuple[Any, str]] = {
    # A. General
    "app_name": ("OFFLINE SHARE", "general"),
    "app_subtitle": ("Local Data Transfer System (LAN)", "general"),
    "organisation_name": ("", "general"),
    "organisation_slogan": ("", "general"),  # shown in small text under the office name
    "logo_data_url": ("", "general"),
    "language": ("en-GB", "general"),
    "date_format": ("DD/MM/YYYY", "general"),
    "time_format": ("24h", "general"),
    "theme": ("maroon", "general"),
    "layout_style": ("classic", "general"),  # classic / modern / compact  # maroon / blue / green / navy / purple
    # B. Transfer
    "max_file_size_mb": (200, "transfer"),
    "max_files_per_transfer": (20, "transfer"),
    "allowed_extensions": (DEFAULT_EXTENSIONS, "transfer"),
    "delivery_confirmation_default": (True, "transfer"),
    "read_receipt_default": (True, "transfer"),
    "auto_retry": (True, "transfer"),
    "retry_attempts": (5, "transfer"),
    "retry_interval_seconds": (60, "transfer"),
    # C. Storage
    "storage_quota_gb": (100, "storage"),
    "repository_quota_gb": (50, "storage"),
    "received_retention_days": (0, "storage"),   # 0 = keep forever
    "sent_retention_days": (0, "storage"),
    "history_retention_days": (0, "storage"),
    # D. Security
    "password_policy": ({"min_length": 8, "require_upper": True, "require_lower": True,
                         "require_digit": True, "require_symbol": False}, "security"),
    "max_login_attempts": (5, "security"),
    "lockout_minutes": (15, "security"),
    "session_timeout_minutes": (480, "security"),
    "registered_pc_restriction": (False, "security"),
    "device_approval_required": (True, "security"),
    "file_whitelist_enforced": (True, "security"),
    # E. Network (bind values live in config.json; these are mirrors + runtime values)
    "network_mode": ("lan+wifi", "network"),
    "heartbeat_interval_seconds": (30, "network"),
    "device_discovery": (True, "network"),
    "wifi_ip_ranges": (["192.168.50.150-192.168.50.199"], "network"),
    # F. Notifications
    "notify_new_message": (True, "notifications"),
    "notify_new_file": (True, "notifications"),
    "notify_failed_transfer": (True, "notifications"),
    "desktop_notifications": (True, "notifications"),
    "sound_notifications": (True, "notifications"),
    # G. Backup
    "auto_backup": (True, "backup"),
    "backup_schedule": ("daily", "backup"),  # daily / weekly
    "backup_time": ("20:00", "backup"),
    "backup_weekday": (6, "backup"),  # 0=Monday
    "backup_include_files": (True, "backup"),
    "backup_keep_count": (14, "backup"),
}

_cache: dict[str, Any] = {}
_lock = threading.Lock()


def _load(db: Session) -> None:
    rows = db.query(AppSetting).all()
    data = {k: v[0] for k, v in DEFAULTS.items()}
    for r in rows:
        try:
            data[r.key] = json.loads(r.value)
        except ValueError:
            pass
    with _lock:
        _cache.clear()
        _cache.update(data)


def invalidate() -> None:
    with _lock:
        _cache.clear()


def get_all(db: Session) -> dict[str, Any]:
    if not _cache:
        _load(db)
    with _lock:
        return dict(_cache)


def get(db: Session, key: str) -> Any:
    return get_all(db).get(key, DEFAULTS.get(key, (None,))[0])


def set_many(db: Session, values: dict[str, Any], user_id: int | None = None) -> dict[str, Any]:
    changed = {}
    for key, value in values.items():
        if key not in DEFAULTS:
            continue
        row = db.get(AppSetting, key)
        enc = json.dumps(value)
        if row is None:
            db.add(AppSetting(key=key, value=enc, updated_by=user_id))
        else:
            row.value = enc
            row.updated_by = user_id
        changed[key] = value
    db.commit()
    invalidate()
    return changed


def grouped(db: Session) -> dict[str, dict[str, Any]]:
    data = get_all(db)
    out: dict[str, dict[str, Any]] = {}
    for key, (_d, group) in DEFAULTS.items():
        out.setdefault(group, {})[key] = data.get(key)
    return out
