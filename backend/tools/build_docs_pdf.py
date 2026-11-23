"""Render docs/*.md to styled PDFs with the locally installed Chrome (no internet needed).
Usage: python tools/build_docs_pdf.py   (requires: pip install markdown playwright)"""
from pathlib import Path

import markdown
from playwright.sync_api import sync_playwright

DOCS = Path(__file__).resolve().parents[2] / "docs"
CSS = """
body{font-family:'Segoe UI',Inter,Arial,sans-serif;color:#2b1d20;font-size:10.5pt;line-height:1.5;margin:0}
h1{color:#7e2a3d;font-size:22pt;border-bottom:3px solid #7e2a3d;padding-bottom:6px}
h2{color:#7e2a3d;font-size:14pt;margin-top:22px;border-bottom:1px solid #edccd2;padding-bottom:3px}
h3{color:#5a2231;font-size:12pt}
table{border-collapse:collapse;width:100%;margin:8px 0;font-size:9.5pt}
th{background:#7e2a3d;color:#fff;text-align:left;padding:5px 7px}
td{border-bottom:1px solid #efeced;padding:5px 7px;vertical-align:top}
code{background:#fbf4f5;padding:1px 4px;border-radius:3px;font-family:Consolas,monospace;font-size:9pt}
pre{background:#211b1d;color:#f8f7f7;padding:10px;border-radius:6px;overflow:hidden;white-space:pre-wrap}
pre code{background:none;color:inherit}
hr{border:none;border-top:1px solid #edccd2}
.cover{background:#7e2a3d;color:#fff;padding:18px 22px;border-radius:10px;margin-bottom:18px}
.cover b{font-size:18pt;letter-spacing:1px}
"""
FILES = {"INSTALLATION_GUIDE.md": "OFFLINE_SHARE_Installation_Guide.pdf", "NETWORK_GUIDE.md": "OFFLINE_SHARE_Network_Configuration_Guide.pdf",
         "USER_MANUAL.md": "OFFLINE_SHARE_User_Manual.pdf", "BACKUP_RESTORE.md": "OFFLINE_SHARE_Backup_and_Restore.pdf"}

with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome")
    page = b.new_page()
    for src, out in FILES.items():
        body = markdown.markdown((DOCS / src).read_text(encoding="utf-8"), extensions=["tables", "fenced_code"])
        html = (f"<!doctype html><html lang='en-GB'><meta charset='utf-8'><style>{CSS}</style><body>"
                f"<div class='cover'><b>OFFLINE SHARE</b><br>Local Data Transfer System (LAN) · v1.0.0</div>{body}</body></html>")
        page.set_content(html)
        page.pdf(path=str(DOCS / out), format="A4", print_background=True, margin={"top": "16mm", "bottom": "16mm", "left": "14mm", "right": "14mm"},
                 display_header_footer=True, header_template="<span></span>",
                 footer_template="<div style='font-size:8px;width:100%;text-align:center;color:#7a6e72'>OFFLINE SHARE · page <span class='pageNumber'></span> of <span class='totalPages'></span></div>")
        print("wrote", out)
    b.close()
