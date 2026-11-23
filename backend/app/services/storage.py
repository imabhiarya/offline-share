"""Server-side file storage. Files are stored under random names inside the storage root;
original names are kept only in the database. Client-supplied paths are never used."""
from __future__ import annotations

import hashlib
import mimetypes
import os
import re
import shutil
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, UploadFile

from ..config import config

CHUNK = 1024 * 1024
_BAD_CHARS = re.compile(r'[\x00-\x1f<>:"/\\|?*]')
_RESERVED = {"con", "prn", "aux", "nul", *(f"com{i}" for i in range(1, 10)), *(f"lpt{i}" for i in range(1, 10))}

mimetypes.add_type("application/vnd.openxmlformats-officedocument.wordprocessingml.document", ".docx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", ".xlsx")
mimetypes.add_type("application/vnd.openxmlformats-officedocument.presentationml.presentation", ".pptx")


def clean_filename(name: str) -> str:
    name = os.path.basename((name or "").replace("\\", "/"))
    name = _BAD_CHARS.sub("_", name).strip(" .")
    stem = name.split(".")[0].lower()
    if not name or stem in _RESERVED:
        name = f"file_{uuid.uuid4().hex[:8]}" + (Path(name).suffix if name else "")
    return name[:200]


def extension_of(name: str) -> str:
    return Path(name).suffix.lower().lstrip(".")


def guess_mime(name: str) -> str:
    return mimetypes.guess_type(name)[0] or "application/octet-stream"


def check_extension(name: str, allowed: list[str], enforced: bool = True) -> str:
    ext = extension_of(name)
    if enforced and ext not in {a.lower().lstrip(".") for a in allowed}:
        raise HTTPException(415, f"File type '.{ext or '?'}' is not permitted. Allowed: {', '.join(allowed)}")
    return ext


def resolve(rel_path: str) -> Path:
    """Map a stored relative path to an absolute path, refusing anything outside the root."""
    root = config.storage_path.resolve()
    p = (root / rel_path).resolve()
    if root not in p.parents and p != root:
        raise HTTPException(400, "Invalid storage path")
    return p


async def save_upload(upload: UploadFile, area: str, max_bytes: int) -> tuple[str, int, str]:
    """Stream an upload to ``<storage>/<area>/YYYY/MM/<uuid>``. Returns (rel_path, size, sha256)."""
    now = datetime.now()
    rel_dir = Path(area) / f"{now:%Y}" / f"{now:%m}"
    abs_dir = config.storage_path / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)
    fname = uuid.uuid4().hex + ".bin"
    tmp = config.tmp_path / (fname + ".part")
    tmp.parent.mkdir(parents=True, exist_ok=True)
    h = hashlib.sha256()
    size = 0
    try:
        with open(tmp, "wb") as out:
            while True:
                chunk = await upload.read(CHUNK)
                if not chunk:
                    break
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(413, f"File exceeds the maximum size of {max_bytes // (1024 * 1024)} MB")
                h.update(chunk)
                out.write(chunk)
        final = abs_dir / fname
        os.replace(tmp, final)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)
    return str((rel_dir / fname).as_posix()), size, h.hexdigest()


def copy_stored(rel_path: str, area: str) -> str:
    src = resolve(rel_path)
    now = datetime.now()
    rel_dir = Path(area) / f"{now:%Y}" / f"{now:%m}"
    (config.storage_path / rel_dir).mkdir(parents=True, exist_ok=True)
    rel = (rel_dir / (uuid.uuid4().hex + ".bin")).as_posix()
    shutil.copyfile(src, config.storage_path / rel)
    return rel


def delete_stored(rel_path: str) -> None:
    try:
        resolve(rel_path).unlink(missing_ok=True)
    except HTTPException:
        pass


def dir_size(path: Path) -> int:
    total = 0
    if not path.exists():
        return 0
    for root, _dirs, files in os.walk(path):
        for f in files:
            try:
                total += (Path(root) / f).stat().st_size
            except OSError:
                pass
    return total


def clear_tmp() -> int:
    removed = 0
    for p in config.tmp_path.glob("*"):
        try:
            if p.is_file():
                p.unlink()
            else:
                shutil.rmtree(p)
            removed += 1
        except OSError:
            pass
    return removed
