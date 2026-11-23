"""Relational schema for OFFLINE SHARE."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def new_uid() -> str:
    return uuid.uuid4().hex


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, nullable=False, index=True)


# --------------------------------------------------------------------------- RBAC
class Role(Base):
    __tablename__ = "roles"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)  # super_admin/admin/user/readonly
    name: Mapped[str] = mapped_column(String(64), unique=True)
    description: Mapped[str] = mapped_column(String(255), default="")
    rank: Mapped[int] = mapped_column(Integer, default=0)  # higher = more privileged
    permissions: Mapped[list["Permission"]] = relationship(secondary="role_permissions", lazy="selectin")


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class UserPermission(Base):
    """Per-user override of the role defaults (granted True/False)."""
    __tablename__ = "user_permissions"
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[int] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)
    granted: Mapped[bool] = mapped_column(Boolean, default=True)


class Section(Base, TimestampMixin):
    __tablename__ = "sections"
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True)
    code: Mapped[str] = mapped_column(String(20), default="")
    description: Mapped[str] = mapped_column(String(255), default="")


# --------------------------------------------------------------------------- users / devices
class User(Base, TimestampMixin):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    full_name: Mapped[str] = mapped_column(String(120))
    login_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    section_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"), index=True)
    assigned_device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"), index=True)
    mobile: Mapped[str] = mapped_column(String(20), default="")
    email: Mapped[str] = mapped_column(String(120), default="")
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id"), index=True)
    status: Mapped[str] = mapped_column(String(16), default="active", index=True)  # active / inactive
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[Optional[datetime]] = mapped_column(DateTime)
    must_change_password: Mapped[bool] = mapped_column(Boolean, default=False)
    password_changed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)

    role: Mapped[Role] = relationship(lazy="joined")
    section: Mapped[Optional[Section]] = relationship(lazy="joined")
    assigned_device: Mapped[Optional["Device"]] = relationship(foreign_keys=[assigned_device_id], lazy="joined")
    permission_overrides: Mapped[list[UserPermission]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class Device(Base, TimestampMixin):
    __tablename__ = "devices"
    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(32), unique=True, default=new_uid)
    pc_name: Mapped[str] = mapped_column(String(64), index=True)
    ip_address: Mapped[str] = mapped_column(String(45), default="", index=True)
    mac_address: Mapped[str] = mapped_column(String(32), default="")
    section_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"), index=True)
    connection_type: Mapped[str] = mapped_column(String(16), default="unknown")  # lan / wifi / unknown
    status: Mapped[str] = mapped_column(String(16), default="pending", index=True)  # pending/approved/blocked
    is_unknown: Mapped[bool] = mapped_column(Boolean, default=False)  # auto-detected, not registered by admin
    os_info: Mapped[str] = mapped_column(String(120), default="")
    notes: Mapped[str] = mapped_column(String(255), default="")
    agent_token_hash: Mapped[str] = mapped_column(String(128), default="")
    agent_version: Mapped[str] = mapped_column(String(32), default="")
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_browser_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_agent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    section: Mapped[Optional[Section]] = relationship(lazy="joined")


class UserSession(Base, TimestampMixin):
    __tablename__ = "sessions"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # sha256 of the cookie token
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    user_agent: Mapped[str] = mapped_column(String(255), default="")
    csrf_token: Mapped[str] = mapped_column(String(64))
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime)
    revoked_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


# --------------------------------------------------------------------------- transfers
class Transfer(Base, TimestampMixin):
    __tablename__ = "transfers"
    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_uid: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    sender_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    sender_device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    sender_name: Mapped[str] = mapped_column(String(120), default="")
    sender_login: Mapped[str] = mapped_column(String(64), default="")
    sender_pc: Mapped[str] = mapped_column(String(64), default="")
    sender_ip: Mapped[str] = mapped_column(String(45), default="")
    subject: Mapped[str] = mapped_column(String(255), default="")
    kind: Mapped[str] = mapped_column(String(8), default="text")  # text / file / both
    priority: Mapped[str] = mapped_column(String(8), default="normal")  # normal / high / urgent
    notify: Mapped[bool] = mapped_column(Boolean, default=True)
    delivery_confirmation: Mapped[bool] = mapped_column(Boolean, default=True)
    read_receipt: Mapped[bool] = mapped_column(Boolean, default=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    total_size: Mapped[int] = mapped_column(BigInteger, default=0)
    file_count: Mapped[int] = mapped_column(Integer, default=0)
    reply_to_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transfers.id", ondelete="SET NULL"))
    forwarded_from_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transfers.id", ondelete="SET NULL"))
    sender_deleted: Mapped[bool] = mapped_column(Boolean, default=False)

    message: Mapped[Optional["Message"]] = relationship(lazy="joined", uselist=False, cascade="all, delete-orphan")
    attachments: Mapped[list["Attachment"]] = relationship(lazy="selectin", back_populates="transfer")
    recipients: Mapped[list["TransferRecipient"]] = relationship(lazy="selectin", back_populates="transfer",
                                                                 cascade="all, delete-orphan")


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("transfers.id", ondelete="CASCADE"), unique=True)
    body_html: Mapped[str] = mapped_column(Text, default="")
    body_text: Mapped[str] = mapped_column(Text, default="")


class Attachment(Base, TimestampMixin):
    __tablename__ = "attachments"
    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(32), unique=True, default=new_uid)
    transfer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("transfers.id", ondelete="CASCADE"), index=True)
    uploader_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    original_name: Mapped[str] = mapped_column(String(255))
    stored_path: Mapped[str] = mapped_column(String(400))  # relative to storage root
    extension: Mapped[str] = mapped_column(String(16), default="")
    mime_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")

    transfer: Mapped[Optional[Transfer]] = relationship(back_populates="attachments")


class TransferRecipient(Base, TimestampMixin):
    __tablename__ = "transfer_recipients"
    __table_args__ = (
        UniqueConstraint("transfer_id", "recipient_user_id", name="uq_transfer_recipient"),
        Index("ix_tr_user_status", "recipient_user_id", "status"),
    )
    id: Mapped[int] = mapped_column(primary_key=True)
    transfer_id: Mapped[int] = mapped_column(ForeignKey("transfers.id", ondelete="CASCADE"), index=True)
    recipient_user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    recipient_device_id: Mapped[Optional[int]] = mapped_column(ForeignKey("devices.id", ondelete="SET NULL"))
    recipient_name: Mapped[str] = mapped_column(String(120), default="")
    recipient_login: Mapped[str] = mapped_column(String(64), default="")
    recipient_pc: Mapped[str] = mapped_column(String(64), default="")
    recipient_ip: Mapped[str] = mapped_column(String(45), default="")
    # pending -> sent (pushed to an open session) -> delivered (client ack) -> read ; or failed
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    last_attempt_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    delivered_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    failed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    failed_reason: Mapped[str] = mapped_column(String(255), default="")
    delivered_ip: Mapped[str] = mapped_column(String(45), default="")
    # inbox state (recipient side)
    is_flagged: Mapped[bool] = mapped_column(Boolean, default=False)
    is_important: Mapped[bool] = mapped_column(Boolean, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    purged: Mapped[bool] = mapped_column(Boolean, default=False)  # removed from inbox permanently

    transfer: Mapped[Transfer] = relationship(back_populates="recipients", lazy="joined")


class Draft(Base, TimestampMixin):
    __tablename__ = "drafts"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    subject: Mapped[str] = mapped_column(String(255), default="")
    body_html: Mapped[str] = mapped_column(Text, default="")
    recipient_ids: Mapped[str] = mapped_column(Text, default="[]")  # json
    attachment_ids: Mapped[str] = mapped_column(Text, default="[]")  # json (attachment uids)
    options: Mapped[str] = mapped_column(Text, default="{}")  # json
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)


class Notification(Base, TimestampMixin):
    __tablename__ = "notifications"
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(32))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(String(500), default="")
    link: Mapped[str] = mapped_column(String(200), default="")
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, index=True)


# --------------------------------------------------------------------------- repository
class Folder(Base, TimestampMixin):
    __tablename__ = "folders"
    __table_args__ = (UniqueConstraint("parent_id", "name", name="uq_folder_name"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    parent_id: Mapped[Optional[int]] = mapped_column(ForeignKey("folders.id", ondelete="CASCADE"), index=True)
    section_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"))
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    system_key: Mapped[str] = mapped_column(String(32), default="")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime)


class RepoFile(Base, TimestampMixin):
    __tablename__ = "file_repository"
    id: Mapped[int] = mapped_column(primary_key=True)
    uid: Mapped[str] = mapped_column(String(32), unique=True, default=new_uid)
    folder_id: Mapped[int] = mapped_column(ForeignKey("folders.id"), index=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    extension: Mapped[str] = mapped_column(String(16), default="")
    mime_type: Mapped[str] = mapped_column(String(120), default="application/octet-stream")
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="", index=True)
    stored_path: Mapped[str] = mapped_column(String(400))
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    description: Mapped[str] = mapped_column(String(500), default="")
    access_scope: Mapped[str] = mapped_column(String(16), default="all")  # all / section / specific
    section_id: Mapped[Optional[int]] = mapped_column(ForeignKey("sections.id", ondelete="SET NULL"))
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    uploaded_by_name: Mapped[str] = mapped_column(String(120), default="")
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
    deleted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))

    folder: Mapped[Folder] = relationship(lazy="joined")
    allowed_users: Mapped[list["FilePermission"]] = relationship(lazy="selectin", cascade="all, delete-orphan")


class FilePermission(Base):
    __tablename__ = "file_permissions"
    __table_args__ = (UniqueConstraint("file_id", "user_id", name="uq_file_user"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("file_repository.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class FileVersion(Base, TimestampMixin):
    __tablename__ = "file_versions"
    __table_args__ = (UniqueConstraint("file_id", "version", name="uq_file_version"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    file_id: Mapped[int] = mapped_column(ForeignKey("file_repository.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    stored_path: Mapped[str] = mapped_column(String(400))
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    sha256: Mapped[str] = mapped_column(String(64), default="")
    uploaded_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    uploaded_by_name: Mapped[str] = mapped_column(String(120), default="")
    note: Mapped[str] = mapped_column(String(255), default="")


# --------------------------------------------------------------------------- system
class AuditLog(Base, TimestampMixin):
    __tablename__ = "audit_logs"
    __table_args__ = (Index("ix_audit_entity", "entity_type", "entity_id"),)
    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"), index=True)
    user_name: Mapped[str] = mapped_column(String(120), default="")
    ip_address: Mapped[str] = mapped_column(String(45), default="")
    action: Mapped[str] = mapped_column(String(64), index=True)
    entity_type: Mapped[str] = mapped_column(String(32), default="")
    entity_id: Mapped[str] = mapped_column(String(64), default="")
    details: Mapped[str] = mapped_column(Text, default="")


class AppSetting(Base):
    __tablename__ = "application_settings"
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)  # json encoded
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow, onupdate=utcnow)
    updated_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))


class BackupHistory(Base, TimestampMixin):
    __tablename__ = "backup_history"
    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    path: Mapped[str] = mapped_column(String(500))
    size: Mapped[int] = mapped_column(BigInteger, default=0)
    kind: Mapped[str] = mapped_column(String(16), default="manual")  # manual / scheduled / pre-restore
    includes_files: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(16), default="success")
    message: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
