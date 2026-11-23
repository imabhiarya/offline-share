"""Excel (.xlsx) export/import helpers using openpyxl (fully offline)."""
from __future__ import annotations

import io
from datetime import datetime
from typing import Any, Iterable

from fastapi.responses import StreamingResponse
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

MAROON = "8B2E3C"


def xlsx_response(title: str, headers: list[str], rows: Iterable[list[Any]], filename: str) -> StreamingResponse:
    wb = Workbook(write_only=False)
    ws = wb.active
    ws.title = title[:31]
    ws.append([f"OFFLINE SHARE – {title}"])
    ws["A1"].font = Font(bold=True, size=14, color=MAROON)
    ws.append([f"Generated {datetime.now():%d/%m/%Y %H:%M}"])
    ws.append([])
    ws.append(headers)
    for i, _ in enumerate(headers, 1):
        c = ws.cell(row=4, column=i)
        c.font = Font(bold=True, color="FFFFFF")
        c.fill = PatternFill("solid", fgColor=MAROON)
        c.alignment = Alignment(vertical="center")
    widths = [len(h) + 2 for h in headers]
    for row in rows:
        clean = [("" if v is None else v) for v in row]
        ws.append(clean)
        for i, v in enumerate(clean):
            widths[i] = min(60, max(widths[i], len(str(v)) + 2))
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    ws.freeze_panes = "A5"
    buf = io.BytesIO()
    wb.save(buf)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                             headers={"Content-Disposition": f'attachment; filename="{filename}"'})


def read_rows(data: bytes) -> list[dict[str, Any]]:
    """Read the first sheet; the first row containing 'login' or 'name' headers is the header row."""
    wb = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    ws = wb.worksheets[0]
    rows = list(ws.iter_rows(values_only=True))
    header_idx = 0
    for i, r in enumerate(rows[:10]):
        cells = [str(c or "").strip().lower() for c in r]
        if any("login" in c for c in cells) or any(c in ("full name", "name", "pc name") for c in cells):
            header_idx = i
            break
    headers = [str(c or "").strip().lower().replace(" ", "_") for c in rows[header_idx]]
    out = []
    for r in rows[header_idx + 1:]:
        if not any(c not in (None, "") for c in r):
            continue
        out.append({headers[i]: (r[i] if i < len(r) else None) for i in range(len(headers)) if headers[i]})
    return out
