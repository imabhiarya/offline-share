"""SQLite FTS5 search index for transfers and repository files."""
from __future__ import annotations

import re

from sqlalchemy import text
from sqlalchemy.orm import Session

from ..models import RepoFile, Transfer


def fts_query(q: str) -> str:
    tokens = re.findall(r"[\w\-.@]+", q or "", flags=re.UNICODE)
    return " AND ".join('"' + t.replace('"', '""') + '"*' for t in tokens[:8])


def index_transfer(db: Session, t: Transfer) -> None:
    db.execute(text("DELETE FROM search_messages WHERE transfer_id = :id"), {"id": t.id})
    db.execute(text("INSERT INTO search_messages(transfer_id, transfer_uid, subject, body, filenames, sender) "
                    "VALUES (:id, :uid, :s, :b, :f, :snd)"),
               {"id": t.id, "uid": t.transfer_uid, "s": t.subject or "",
                "b": t.message.body_text if t.message else "",
                "f": " ".join(a.original_name for a in t.attachments),
                "snd": f"{t.sender_name} {t.sender_login} {t.sender_pc} {t.sender_ip}"})


def unindex_transfer(db: Session, transfer_id: int) -> None:
    db.execute(text("DELETE FROM search_messages WHERE transfer_id = :id"), {"id": transfer_id})


def search_transfer_ids(db: Session, q: str) -> list[int] | None:
    fq = fts_query(q)
    if not fq:
        return None
    rows = db.execute(text("SELECT transfer_id FROM search_messages WHERE search_messages MATCH :q LIMIT 5000"),
                      {"q": fq}).all()
    return [int(r[0]) for r in rows]


def index_file(db: Session, f: RepoFile) -> None:
    db.execute(text("DELETE FROM search_files WHERE file_id = :id"), {"id": f.id})
    db.execute(text("INSERT INTO search_files(file_id, name, description, uploader) VALUES (:id, :n, :d, :u)"),
               {"id": f.id, "n": f.name, "d": f.description or "", "u": f.uploaded_by_name or ""})


def unindex_file(db: Session, file_id: int) -> None:
    db.execute(text("DELETE FROM search_files WHERE file_id = :id"), {"id": file_id})


def search_file_ids(db: Session, q: str) -> list[int] | None:
    fq = fts_query(q)
    if not fq:
        return None
    rows = db.execute(text("SELECT file_id FROM search_files WHERE search_files MATCH :q LIMIT 5000"),
                      {"q": fq}).all()
    return [int(r[0]) for r in rows]


def rebuild(db: Session) -> dict:
    db.execute(text("DELETE FROM search_messages"))
    db.execute(text("DELETE FROM search_files"))
    nt = nf = 0
    for t in db.query(Transfer).yield_per(200):
        index_transfer(db, t)
        nt += 1
    for f in db.query(RepoFile).yield_per(200):
        index_file(db, f)
        nf += 1
    db.execute(text("INSERT INTO search_messages(search_messages) VALUES ('optimize')"))
    db.execute(text("INSERT INTO search_files(search_files) VALUES ('optimize')"))
    db.commit()
    return {"transfers": nt, "files": nf}
