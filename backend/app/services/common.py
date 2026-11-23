"""Shared helpers: audit logging, notifications, network checks, HTML sanitising, formatting."""
from __future__ import annotations

import html
import ipaddress
import json
import logging
import re
from datetime import datetime
from html.parser import HTMLParser
from typing import Any, Optional

from fastapi import Request
from sqlalchemy.orm import Session

from ..models import AuditLog, Notification, User

log = logging.getLogger("offline_share")


# --------------------------------------------------------------------------- audit
def audit(db: Session, action: str, *, user: Optional[User] = None, ip: str = "", entity_type: str = "",
          entity_id: Any = "", details: Any = None, commit: bool = False) -> None:
    db.add(AuditLog(user_id=user.id if user else None, user_name=user.full_name if user else "system",
                    ip_address=ip, action=action, entity_type=entity_type, entity_id=str(entity_id or ""),
                    details=json.dumps(details, default=str) if details is not None else ""))
    if commit:
        db.commit()


def notify(db: Session, user_id: int, type_: str, title: str, body: str = "", link: str = "") -> Notification:
    n = Notification(user_id=user_id, type=type_, title=title[:200], body=body[:500], link=link)
    db.add(n)
    return n


# --------------------------------------------------------------------------- network
def client_ip(request: Request) -> str:
    # The server is reached directly on the LAN (no reverse proxy), so the socket peer is authoritative.
    return request.client.host if request.client else ""


def ip_allowed(ip: str, subnets: list[str]) -> bool:
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return ip in ("testclient",)
    if addr.is_loopback:
        return True
    if getattr(addr, "ipv4_mapped", None):
        addr = addr.ipv4_mapped
    for s in subnets:
        try:
            if addr in ipaddress.ip_network(s, strict=False):
                return True
        except ValueError:
            continue
    return False


def ip_in_ranges(ip: str, ranges: list[str]) -> bool:
    """Ranges may be CIDR (10.0.0.0/24) or start-end (192.168.50.150-192.168.50.199)."""
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for r in ranges:
        r = r.strip()
        try:
            if "-" in r:
                a, b = (ipaddress.ip_address(x.strip()) for x in r.split("-", 1))
                if a <= addr <= b:
                    return True
            elif addr in ipaddress.ip_network(r, strict=False):
                return True
        except ValueError:
            continue
    return False


# --------------------------------------------------------------------------- html
_ALLOWED_TAGS = {"b", "strong", "i", "em", "u", "ul", "ol", "li", "p", "br", "div", "span"}
_VOID = {"br"}


class _Sanitiser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.out: list[str] = []
        self.stack: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # noqa: ANN001
        if tag in ("script", "style"):
            self.skip += 1
            return
        if tag in _ALLOWED_TAGS and not self.skip:
            self.out.append(f"<{tag}>")
            if tag not in _VOID:
                self.stack.append(tag)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
            return
        if tag in _ALLOWED_TAGS and tag not in _VOID and tag in self.stack and not self.skip:
            while self.stack:
                t = self.stack.pop()
                self.out.append(f"</{t}>")
                if t == tag:
                    break

    def handle_data(self, data: str) -> None:
        if not self.skip:
            self.out.append(html.escape(data, quote=False))

    def result(self) -> str:
        while self.stack:
            self.out.append(f"</{self.stack.pop()}>")
        return "".join(self.out)


def sanitise_html(raw: str) -> str:
    p = _Sanitiser()
    p.feed(raw or "")
    p.close()
    return p.result()


class _Text(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.ol_counters: list[int | None] = []

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag == "br":
            self.parts.append("\n")
        elif tag in ("p", "div"):
            if self.parts and not self.parts[-1].endswith("\n"):
                self.parts.append("\n")
        elif tag == "ul":
            self.ol_counters.append(None)
        elif tag == "ol":
            self.ol_counters.append(0)
        elif tag == "li":
            if self.parts and not self.parts[-1].endswith("\n"):
                self.parts.append("\n")
            if self.ol_counters and self.ol_counters[-1] is not None:
                self.ol_counters[-1] += 1
                self.parts.append(f"{self.ol_counters[-1]}. ")
            else:
                self.parts.append("• ")

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in ("ul", "ol") and self.ol_counters:
            self.ol_counters.pop()
        if tag in ("p", "div", "li", "ul", "ol"):
            self.parts.append("\n")

    def handle_data(self, data):  # noqa: ANN001
        self.parts.append(data)


def html_to_text(raw: str) -> str:
    p = _Text()
    p.feed(raw or "")
    p.close()
    txt = "".join(p.parts)
    return re.sub(r"\n{3,}", "\n\n", txt).strip()


def text_to_html(txt: str) -> str:
    return "<br>".join(html.escape(line) for line in (txt or "").split("\n"))


# --------------------------------------------------------------------------- misc
def iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() + "Z" if dt else None


def local_day_start_utc(d) -> datetime:
    """Start of calendar day ``d`` in the server's local time zone, as a naive UTC datetime.
    Timestamps are stored in UTC, but users pick dates in office (server) local time."""
    from datetime import time as _time, timezone as _tz
    return datetime.combine(d, _time.min).astimezone().astimezone(_tz.utc).replace(tzinfo=None)


def local_day_range_utc(date_from=None, date_to=None):
    """(start, end_exclusive) UTC bounds for an inclusive local date range; either may be None."""
    from datetime import timedelta as _td
    return (local_day_start_utc(date_from) if date_from else None,
            local_day_start_utc(date_to + _td(days=1)) if date_to else None)


def local_str(dt: Optional[datetime]) -> str:
    """Format a stored UTC timestamp in server local time for reports (dd/mm/yyyy HH:MM)."""
    if not dt:
        return ""
    from datetime import timezone as _tz
    return dt.replace(tzinfo=_tz.utc).astimezone().strftime("%d/%m/%Y %H:%M")


def human_size(n: int) -> str:
    size = float(n or 0)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.0f} {unit}" if unit == "B" else f"{size:.1f} {unit}"
        size /= 1024
    return f"{n} B"


def paginate(query, page: int, page_size: int):  # noqa: ANN001
    page = max(1, page)
    page_size = max(1, min(500, page_size))
    total = query.order_by(None).count()
    items = query.offset((page - 1) * page_size).limit(page_size).all()
    return items, total, page, page_size
