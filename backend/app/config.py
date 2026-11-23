"""Server bootstrap configuration.

Bootstrap values (bind address, port, data locations, TLS files, allowed subnets)
live in ``config.json`` inside the data directory because they are needed before
the database is opened. Everything else is stored in the ``application_settings``
table and edited from the Settings page.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "OFFLINE SHARE"
APP_VERSION = "1.0.0"


def _default_home() -> Path:
    env = os.environ.get("OFFLINE_SHARE_HOME")
    if env:
        return Path(env)
    if sys.platform == "win32":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "OfflineShare"
    return Path(__file__).resolve().parents[2] / "data"


@dataclass
class ServerConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    public_ip: str = "192.168.50.10"
    subnet: str = "192.168.50.0/24"
    # Clients outside these networks are refused (loopback is always allowed).
    allowed_subnets: list[str] = field(default_factory=lambda: ["192.168.50.0/24"])
    data_dir: str = ""
    storage_dir: str = ""
    backup_dir: str = ""
    log_dir: str = ""
    ssl_certfile: str = ""
    ssl_keyfile: str = ""
    https: bool = False

    # ---- derived paths -------------------------------------------------
    @property
    def home(self) -> Path:
        return Path(self.data_dir) if self.data_dir else _default_home()

    @property
    def db_path(self) -> Path:
        return self.home / "db" / "offline_share.db"

    @property
    def storage_path(self) -> Path:
        return Path(self.storage_dir) if self.storage_dir else self.home / "storage"

    @property
    def backup_path(self) -> Path:
        return Path(self.backup_dir) if self.backup_dir else self.home / "backups"

    @property
    def log_path(self) -> Path:
        return Path(self.log_dir) if self.log_dir else self.home / "logs"

    @property
    def tmp_path(self) -> Path:
        return self.storage_path / "_tmp"

    def ensure_dirs(self) -> None:
        for p in (self.db_path.parent, self.storage_path, self.backup_path, self.log_path,
                  self.tmp_path, self.storage_path / "transfers", self.storage_path / "repository",
                  self.home / "certs"):
            p.mkdir(parents=True, exist_ok=True)

    def to_json(self) -> dict:
        return asdict(self)


def config_file() -> Path:
    return _default_home() / "config.json"


def load_config() -> ServerConfig:
    path = config_file()
    cfg = ServerConfig()
    if path.exists():
        data = json.loads(path.read_text(encoding="utf-8"))
        for k, v in data.items():
            if hasattr(cfg, k) and not k.startswith("_"):
                setattr(cfg, k, v)
    # Environment overrides (useful for tests / dev)
    if os.environ.get("OFFLINE_SHARE_PORT"):
        cfg.port = int(os.environ["OFFLINE_SHARE_PORT"])
    if os.environ.get("OFFLINE_SHARE_ALLOWED"):
        cfg.allowed_subnets = [s.strip() for s in os.environ["OFFLINE_SHARE_ALLOWED"].split(",") if s.strip()]
    return cfg


def save_config(cfg: ServerConfig) -> None:
    path = config_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(cfg.to_json(), indent=2), encoding="utf-8")
    tmp.replace(path)


config = load_config()
