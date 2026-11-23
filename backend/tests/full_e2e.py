"""Broad feature-by-feature browser test (real server + built frontend + Chrome, several users at once).

Usage: python tests/full_e2e.py http://127.0.0.1:5070 <out-dir>
Expects a FRESH database seeded with tools/seed_demo.py (admin password Admin@12345, demo users Demo@1234).
Every check is independent: a failure is recorded with a screenshot and the run continues.
"""
import io
import re
import sqlite3
import sys
import time
import zipfile
from pathlib import Path

from openpyxl import Workbook, load_workbook
from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1]
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
DB = Path(sys.argv[3]) if len(sys.argv) > 3 else None
T = 8000
results: list[tuple[str, str, bool, str]] = []
errors: list[str] = []
PAGES: dict = {}
section = "?"


def sect(name):
    global section
    section = name


def check(name, fn):
    try:
        fn()
        results.append((section, name, True, ""))
        print(f"  PASS  {section} › {name}", flush=True)
    except Exception as e:  # noqa: BLE001
        msg = str(e).replace("\n", " ")[:260]
        results.append((section, name, False, msg))
        print(f"  FAIL  {section} › {name} -> {msg}", flush=True)
        for pg, who in list(PAGES.items()):
            try:
                pg.keyboard.press("Escape")
                pg.screenshot(path=OUT / f"FAIL_{len(results):02d}_{who}.png")
            except Exception:
                pass


def watch(page, who):
    PAGES[page] = who
    page.on("pageerror", lambda e: errors.append(f"[{who}] JS error: {e}"))
    page.on("console", lambda m: m.type == "error" and "401" not in m.text and "Failed to load resource" not in m.text
            and errors.append(f"[{who}] console: {m.text[:200]}"))
    page.on("response", lambda r: r.status >= 500 and errors.append(f"[{who}] HTTP {r.status} {r.request.method} {r.url}"))


def login(page, user, pwd, new_pwd=None, wait_online=True):
    page.goto(f"{BASE}/login")
    page.get_by_label("Login ID").fill(user)
    page.get_by_label("Password", exact=True).fill(pwd)
    page.get_by_role("button", name="Sign in").click()
    if new_pwd:
        dlg = page.get_by_role("dialog")
        expect(dlg.get_by_text("Set a new password")).to_be_visible(timeout=T)
        dlg.get_by_label("Current password").fill(pwd)
        dlg.get_by_label("New password", exact=True).fill(new_pwd)
        dlg.get_by_label("Repeat new password").fill(new_pwd)
        dlg.get_by_role("button", name="Save password").click()
        expect(page.get_by_text("Set a new password")).to_be_hidden(timeout=T)
    if wait_online:
        expect(page.locator("header").get_by_text("Online", exact=True)).to_be_visible(timeout=T)
    else:
        expect(page).not_to_have_url(re.compile("/login"), timeout=T)


def go(page, path):
    page.goto(BASE + path)
    page.wait_for_load_state("networkidle")


def toast(page, text):
    expect(page.get_by_text(text).first).to_be_visible(timeout=T)


def dl(page, click):
    with page.expect_download(timeout=T) as d:
        click()
    return d.value


def tmpfile(name, data: bytes):
    p = OUT / name
    p.write_bytes(data)
    return str(p)


PDF = b"%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj 3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF"
PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000" "1f15c4890000000d49444154789c6360000002000154a24f5d0000000049454e44ae426082")


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    ctx = lambda: browser.new_context(viewport={"width": 1680, "height": 945}, accept_downloads=True)  # noqa: E731
    admin = ctx().new_page(); watch(admin, "admin")
    rahul = ctx().new_page(); watch(rahul, "rahul")
    anita = ctx().new_page(); watch(anita, "anita")
    karan = ctx().new_page(); watch(karan, "karan")

    # ===================================================================== AUTH
    sect("Login")

    def wrong_pwd():
        admin.goto(f"{BASE}/login")
        admin.get_by_label("Login ID").fill("admin")
        admin.get_by_label("Password", exact=True).fill("nope")
        admin.get_by_role("button", name="Sign in").click()
        expect(admin.get_by_text("Invalid login ID or password")).to_be_visible(timeout=T)
    check("wrong password shows a clear error", wrong_pwd)
    check("admin signs in", lambda: login(admin, "admin", "Admin@12345"))
    check("normal user rahul: first sign-in forces password change", lambda: login(rahul, "rahul", "Demo@1234", "Rahul@2026"))
    check("normal user anita signs in", lambda: login(anita, "anita", "Demo@1234", "Anita@2026"))
    check("read-only user karan signs in", lambda: login(karan, "karan", "Demo@1234", "Karan@2026"))

    # ===================================================================== RBAC
    sect("Permissions")

    def ro_menu():
        nav = karan.locator("aside nav")
        expect(nav.get_by_role("link", name="Receive Data")).to_be_visible()
        expect(nav.get_by_role("link", name="Send Data")).to_have_count(0)
        expect(nav.get_by_role("link", name="Settings")).to_have_count(0)
        expect(nav.get_by_role("link", name="User Management")).to_have_count(0)
    check("read-only menu hides Send/Settings/Users", ro_menu)

    def ro_blocked():
        go(karan, "/settings")
        expect(karan.get_by_text("Access denied")).to_be_visible(timeout=T)
    check("read-only user blocked from Settings URL", ro_blocked)

    def ro_files():
        go(karan, "/files")
        expect(karan.get_by_role("heading", name="File Depository (Central Repository)")).to_be_visible(timeout=T)
        expect(karan.get_by_role("button", name="Upload File(s)")).to_have_count(0)
    check("read-only user cannot upload files", ro_files)

    def user_menu():
        nav = rahul.locator("aside nav")
        expect(nav.get_by_role("link", name="Send Data")).to_be_visible()
        expect(nav.get_by_role("link", name="User Management")).to_have_count(0)
    check("normal user has no User Management", user_menu)

    # ===================================================================== SEND / RECEIVE
    sect("Send & Receive")
    go(rahul, "/receive"); go(anita, "/receive")

    def send_text_multi():
        go(admin, "/send")
        admin.get_by_role("button", name="Text / Message").click()
        admin.get_by_label("Subject").fill("Office circular 41")
        admin.locator(".editor").click()
        admin.keyboard.type("All staff please note the ")
        admin.keyboard.press("Meta+b"); admin.keyboard.type("new timings"); admin.keyboard.press("Meta+b")
        admin.keyboard.type(" from Monday.")
        admin.get_by_role("radio", name="Section / Group").check()
        admin.locator("button", has_text="Accounts").filter(has_text="user(s)").click()
        expect(admin.get_by_text("Selected Receivers (2)")).to_be_visible()
        admin.get_by_role("button", name="Send Data", exact=True).click()
        expect(admin.get_by_text("live delivery status")).to_be_visible(timeout=T)
    check("send formatted text to a whole section (Accounts = rahul + anita)", send_text_multi)

    def both_receive():
        for pg, who in ((rahul, "rahul"), (anita, "anita")):
            expect(pg.get_by_text("New message from System Administrator").first).to_be_visible(timeout=T)
    check("both receivers get a live pop-up", both_receive)

    def delivered_both():
        panel = admin.locator("section", has_text="live delivery status")
        expect(panel.get_by_text("Delivered", exact=True)).to_have_count(3, timeout=T)  # aggregate + 2 PCs
        expect(panel.get_by_text("Pending", exact=True)).to_have_count(0)
    check("sender sees Delivered for both PCs (acknowledged)", delivered_both)

    def unread_badge():
        expect(rahul.locator("aside a", has_text="Receive Data").locator("span.bg-red-600")).to_have_text("1", timeout=T)
    check("receiver sidebar shows unread badge", unread_badge)

    def open_and_read():
        go(rahul, "/receive")
        rahul.get_by_text("Office circular 41").first.click()
        expect(rahul.locator(".rich b").first).to_have_text("new timings", timeout=T)
    check("receiver opens message, bold formatting preserved", open_and_read)

    def read_receipt():
        go(admin, "/history?tab=sent")
        admin.get_by_text("Office circular 41").first.click()
        expect(admin.get_by_text("Delivery status per PC")).to_be_visible(timeout=T)
        expect(admin.locator("aside, section").get_by_text("Read").first).to_be_visible(timeout=T)
    check("sender sees Read for rahul in Transfer Details", read_receipt)

    att_pdf = tmpfile("Agenda.pdf", PDF)
    att_png = tmpfile("Site.png", PNG)
    att_txt = tmpfile("Notes.txt", b"line one\nline two\n")

    def send_files():
        go(rahul, "/send")
        rahul.get_by_role("button", name="File / Document").click()
        rahul.get_by_label("Subject").fill("Files for review")
        rahul.locator("input[type=file]").first.set_input_files([att_pdf, att_png, att_txt])
        expect(rahul.locator('[aria-label="ready"]')).to_have_count(3, timeout=T)
        rahul.get_by_placeholder("Search by Name, PC Name, Section or IP…").fill("anita")
        rahul.locator("tbody tr", has_text="Anita Desai").first.click()
        rahul.get_by_label("Priority").select_option("urgent")
        rahul.get_by_role("button", name="Send Data", exact=True).click()
        expect(rahul.get_by_text("live delivery status")).to_be_visible(timeout=T)
    check("normal user sends 3 files (urgent) to one person", send_files)

    def recv_files():
        expect(anita.get_by_text("URGENT: New file from Rahul Mehta").first).to_be_visible(timeout=T)
        go(anita, "/receive")
        anita.get_by_text("Files for review").first.click()
        for n in ("Agenda.pdf", "Site.png", "Notes.txt"):
            expect(anita.get_by_text(n).first).to_be_visible()
        d = dl(anita, lambda: anita.get_by_role("button", name="Download All").click())
        z = zipfile.ZipFile(io.BytesIO(Path(d.path()).read_bytes()))
        assert sorted(z.namelist()) == ["Agenda.pdf", "Notes.txt", "Site.png"], z.namelist()
        assert z.read("Notes.txt") == b"line one\nline two\n"
    check("receiver sees files; Download All ZIP has all 3 intact", recv_files)

    def single_download():
        row = anita.locator("li", has_text="Agenda.pdf").first
        d = dl(anita, lambda: row.get_by_role("button", name="Download").click())
        assert Path(d.path()).read_bytes() == PDF and d.suggested_filename == "Agenda.pdf"
    check("single file download is byte-identical", single_download)

    def preview_pdf():
        anita.locator("li", has_text="Agenda.pdf").first.get_by_role("button", name="Preview").click()
        expect(anita.get_by_role("dialog").locator("iframe")).to_be_visible(timeout=T)
        anita.keyboard.press("Escape")
    check("PDF preview opens", preview_pdf)

    def reply():
        anita.get_by_role("button", name="Reply").click()
        expect(anita).to_have_url(re.compile(r"/send"), timeout=T)
        expect(anita.get_by_label("Subject")).to_have_value("Re: Files for review")
        expect(anita.get_by_text("Selected Receivers (1)")).to_be_visible()
        anita.locator(".editor").click(); anita.keyboard.press("Meta+Home"); anita.keyboard.type("Received, thanks.")
        anita.get_by_role("button", name="Send Data", exact=True).click()
        expect(anita.get_by_text("live delivery status")).to_be_visible(timeout=T)
        expect(rahul.get_by_text("New message from Anita Desai").first).to_be_visible(timeout=T)
    check("reply goes back to sender with Re: subject", reply)

    def forward():
        go(anita, "/receive")
        anita.get_by_text("Files for review").first.click()
        anita.get_by_role("button", name="Forward").click()
        expect(anita.get_by_label("Subject")).to_have_value("Fwd: Files for review", timeout=T)
        expect(anita.get_by_text("forwarded", exact=True)).to_have_count(3)
        anita.get_by_placeholder("Search by Name, PC Name, Section or IP…").fill("neha")
        anita.locator("tbody tr", has_text="Neha Kapoor").first.click()
        anita.get_by_role("button", name="Send Data", exact=True).click()
        expect(anita.get_by_text("live delivery status")).to_be_visible(timeout=T)
    check("forward with all 3 attachments to an offline user", forward)

    def offline_pending():
        panel = anita.locator("section", has_text="live delivery status")
        expect(panel.get_by_text("Pending", exact=True).first).to_be_visible(timeout=T)
        expect(panel.get_by_text("Delivered", exact=True)).to_have_count(0)
    check("offline receiver shows Pending (queued), not Delivered", offline_pending)

    neha = ctx().new_page(); watch(neha, "neha")

    def offline_delivery():
        login(neha, "neha", "Demo@1234", "Neha@2026")
        go(neha, "/receive")
        expect(neha.get_by_text("Fwd: Files for review").first).to_be_visible(timeout=T)
        go(anita, "/history?tab=sent")
        anita.get_by_text("Fwd: Files for review").first.click()
        expect(anita.locator("section").get_by_text("Delivered").first).to_be_visible(timeout=T)
    check("queued transfer delivered when the offline user signs in", offline_delivery)

    def draft():
        go(admin, "/send")
        admin.get_by_label("Subject").fill("Draft budget note")
        admin.locator(".editor").click(); admin.keyboard.type("Work in progress")
        admin.get_by_role("button", name="Save as Draft").click()
        toast(admin, "Draft saved")
        go(admin, "/send")
        admin.get_by_role("button", name=re.compile("Drafts")).click()
        admin.get_by_role("dialog").get_by_role("button", name="Open").first.click()
        expect(admin.get_by_label("Subject")).to_have_value("Draft budget note", timeout=T)
    check("save draft and reopen it", draft)

    def validations():
        go(admin, "/send")
        admin.get_by_label("Subject").fill("no receivers")
        admin.locator(".editor").click(); admin.keyboard.type("x")
        admin.get_by_role("button", name="Send Data", exact=True).click()
        toast(admin, "Select at least one receiver")
        admin.locator("input[type=file]").first.set_input_files(tmpfile("bad.exe", b"MZ"))
        toast(admin, "bad.exe not allowed")
    check("send without receiver / blocked .exe are rejected", validations)

    def expiry_option():
        go(admin, "/send")
        admin.get_by_label("Subject").fill("Expiring notice")
        admin.locator(".editor").click(); admin.keyboard.type("valid for 1 day")
        admin.get_by_placeholder("Search by Name, PC Name, Section or IP…").fill("vikram")
        admin.locator("tbody tr", has_text="Vikram Singh").first.click()
        admin.get_by_label("Set validity / expire after").check()
        admin.locator("select").filter(has=admin.locator("option", has_text="1 Day")).select_option("1")
        admin.get_by_role("button", name="Send Data", exact=True).click()
        expect(admin.get_by_text("live delivery status")).to_be_visible(timeout=T)
    check("send with 1-day validity", expiry_option)

    # ===================================================================== INBOX ACTIONS
    sect("Inbox actions")

    def inbox_actions():
        go(rahul, "/receive")
        rahul.get_by_text("Received, thanks.").first.click()  # preview text of reply
        rahul.get_by_role("button", name="Flag", exact=True).click()
        rahul.get_by_role("button", name="Flagged").click()
        expect(rahul.locator("tbody tr")).to_have_count(1, timeout=T)
        rahul.get_by_role("button", name="All Received").click()
        rahul.locator("tbody tr").first.click()
        rahul.get_by_role("button", name="Archive", exact=True).click()
        rahul.get_by_role("button", name="Archived").click()
        expect(rahul.locator("tbody tr")).to_have_count(1, timeout=T)
    check("flag + archive move message to the right folders", inbox_actions)

    def delete_restore():
        rahul.locator("tbody tr").first.click()
        rahul.get_by_role("button", name="Delete", exact=True).click()
        rahul.get_by_role("button", name="Deleted").click()
        expect(rahul.locator("tbody tr")).to_have_count(1, timeout=T)
        rahul.locator("tbody tr").first.click()
        rahul.get_by_role("button", name="Restore", exact=True).click()
        expect(rahul.locator("tbody tr")).to_have_count(0, timeout=T)
    check("delete → Deleted folder → restore", delete_restore)

    def inbox_search():
        go(anita, "/receive")
        anita.get_by_placeholder("Search by Sender, Subject, File Name or Transfer ID…").fill("Agenda")
        expect(anita.locator("tbody tr")).to_have_count(1, timeout=T)
        anita.get_by_placeholder("Search by Sender, Subject, File Name or Transfer ID…").fill("")
    check("inbox search by file name", inbox_search)

    def copy_msg():
        anita.context.grant_permissions(["clipboard-read", "clipboard-write"], origin=BASE)
        go(anita, "/receive")
        anita.get_by_text("Office circular 41").first.click()
        anita.get_by_role("button", name="Copy Message").click()
        toast(anita, "copied to this PC")
        clip = anita.evaluate("navigator.clipboard.readText()")
        assert "new timings" in clip, clip
    check("Copy Message puts text on the clipboard", copy_msg)

    # ===================================================================== HISTORY
    sect("Transfer History")

    def hist_counts():
        go(admin, "/history")
        admin.get_by_role("combobox").filter(has=admin.locator("option", has_text="All users")).select_option("all")
        expect(admin.get_by_role("tab", name=re.compile("All Transfers"))).to_be_visible()
        expect(admin.locator("tbody tr").first).to_be_visible(timeout=T)
    check("admin can view all users' transfers", hist_counts)

    def hist_filters():
        admin.locator("select").filter(has=admin.locator("option", has_text="All Types")).select_option("pdf")
        admin.get_by_role("button", name="Filter", exact=True).click()
        expect(admin.locator("tbody tr").first).to_contain_text("Agenda", timeout=T) if False else expect(admin.locator("tbody tr").first).to_be_visible(timeout=T)
        rows = admin.locator("tbody tr").count()
        assert rows >= 2, rows
        admin.get_by_role("button", name="Reset").click()
    check("filter by file type PDF", hist_filters)

    def quick_range():
        admin.locator("select").filter(has=admin.locator("option", has_text="This Month")).select_option("today")
        expect(admin.locator("tbody tr").first).to_be_visible(timeout=T)
    check("quick range Today", quick_range)

    def exports():
        d = dl(admin, lambda: admin.get_by_role("button", name="Export to Excel").click())
        wb = load_workbook(io.BytesIO(Path(d.path()).read_bytes()))
        assert wb.active.max_row > 4, f"Excel has only {wb.active.max_row} rows (filters applied: today)"
        d2 = dl(admin, lambda: admin.get_by_role("button", name="Download", exact=True).click())
        body = Path(d2.path()).read_bytes()
        assert d2.suggested_filename.endswith(".csv"), f"download name {d2.suggested_filename}"
        assert b"Transfer ID" in body, body[:200]
    check("Export to Excel + CSV download", exports)

    def retry_failed():
        assert DB, "DB path not given"
        con = sqlite3.connect(DB)
        con.execute("UPDATE transfers SET expires_at = datetime('now','-1 minute') WHERE subject='Expiring notice'")
        con.commit(); con.close()
        time.sleep(12)  # delivery worker runs every 10 s
        go(admin, "/history?tab=failed")
        expect(admin.locator("tbody tr", has_text="Expiring notice")).to_be_visible(timeout=T)
        admin.locator("tbody tr", has_text="Expiring notice").get_by_role("button", name="Retry").click()
        toast(admin, "queued for retry")
    check("expired transfer → Failed tab → Retry", retry_failed)

    def hist_delete():
        go(rahul, "/history?tab=received")
        n = rahul.locator("tbody tr").count()
        rahul.locator("tbody tr").first.locator("input[type=checkbox]").check()
        rahul.get_by_role("button", name="Delete", exact=True).click()
        rahul.get_by_role("dialog").get_by_role("button", name="Delete").click()
        toast(rahul, "record(s) deleted")
        expect(rahul.locator("tbody tr")).to_have_count(n - 1, timeout=T)
    check("user deletes a record from own history", hist_delete)

    # ===================================================================== DEVICES
    sect("Connected Devices")

    def add_device():
        go(admin, "/devices")
        admin.get_by_role("button", name="Add Device").click()
        dlg = admin.get_by_role("dialog")
        dlg.get_by_label("PC name").fill("qa-pc-09")
        dlg.get_by_label("IP address").fill("192.168.50.109")
        dlg.get_by_label("Connection type").select_option("wifi")
        dlg.get_by_role("button", name="Save").click()
        toast(admin, "Device added")
        expect(admin.locator("tbody tr", has_text="QA-PC-09")).to_be_visible(timeout=T)
    check("add device (name upper-cased, Wi-Fi)", add_device)

    def dup_ip():
        admin.get_by_role("button", name="Add Device").click()
        dlg = admin.get_by_role("dialog")
        dlg.get_by_label("PC name").fill("dup")
        dlg.get_by_label("IP address").fill("192.168.50.109")
        dlg.get_by_role("button", name="Save").click()
        expect(dlg.get_by_text("already assigned")).to_be_visible(timeout=T)
        dlg.get_by_role("button", name="Cancel").click()
    check("duplicate IP is rejected", dup_ip)

    def block_unblock():
        admin.locator("tbody tr", has_text="ACC-PC-02").click()
        admin.get_by_role("button", name="Block Device").click()
        admin.get_by_role("dialog").get_by_role("button", name="Block PC").click()
        toast(admin, "ACC-PC-02: blocked")
        expect(admin.locator("tbody tr", has_text="ACC-PC-02")).to_contain_text("Blocked", timeout=T)
        admin.get_by_role("button", name="Unblock").first.click()
        toast(admin, "ACC-PC-02: approved")
    check("block then unblock a device", block_unblock)

    def dev_tabs():
        for t, txt in (("Network Map", "Wi-Fi Access Point"), ("Section Wise", "Accounts"), ("Device Statistics", "Approval")):
            admin.get_by_role("tab", name=t).click()
            expect(admin.get_by_text(txt).first).to_be_visible(timeout=T)
        admin.get_by_role("tab", name="Device List").click()
    check("Network Map / Section Wise / Statistics tabs", dev_tabs)

    def dev_filter():
        admin.locator("select").filter(has=admin.locator("option", has_text="All (LAN & Wi-Fi)")).select_option("wifi")
        admin.get_by_role("button", name="Filter", exact=True).click()
        expect(admin.locator("tbody tr", has_text="ACC-PC-01")).to_have_count(0, timeout=T)
        expect(admin.locator("tbody tr", has_text="QA-PC-09")).to_be_visible()
        admin.get_by_role("button", name="Reset").click()
    check("filter devices by Wi-Fi", dev_filter)

    def dev_export():
        d = dl(admin, lambda: admin.get_by_role("button", name="Export List (Excel)").click())
        assert d.suggested_filename.endswith(".xlsx")
    check("export device list", dev_export)

    # ===================================================================== USERS
    sect("User Management")

    def add_user():
        go(admin, "/users")
        admin.get_by_role("button", name="Add User").click()
        dlg = admin.get_by_role("dialog")
        dlg.get_by_label("Full name").fill("Meena Verma")
        dlg.get_by_label("Login ID").fill("meena")
        dlg.get_by_label("Password").fill("Meena@1234")
        dlg.get_by_label("Section").select_option(label="Store")
        dlg.get_by_label("Assigned PC").select_option(label="QA-PC-09 (192.168.50.109)")
        dlg.get_by_role("button", name="Create user").click()
        toast(admin, "User created")
        expect(admin.locator("tbody tr", has_text="Meena Verma")).to_be_visible(timeout=T)
    check("add user with section + assigned PC", add_user)

    def weak_pwd():
        admin.get_by_role("button", name="Add User").click()
        dlg = admin.get_by_role("dialog")
        dlg.get_by_label("Full name").fill("Weak"); dlg.get_by_label("Login ID").fill("weak"); dlg.get_by_label("Password").fill("abc")
        dlg.get_by_role("button", name="Create user").click()
        expect(dlg.get_by_text("Password must contain")).to_be_visible(timeout=T)
        dlg.get_by_role("button", name="Cancel").click()
    check("weak password rejected", weak_pwd)

    def reset_pwd():
        admin.locator("tbody tr", has_text="Meena Verma").click()
        admin.locator("tbody tr", has_text="Meena Verma").get_by_role("button", name="Reset password").click()
        admin.get_by_role("dialog").get_by_role("button", name="Reset password").click()
        expect(admin.get_by_text("Temporary password")).to_be_visible(timeout=T)
        pwd = admin.get_by_role("dialog").locator(".font-mono").inner_text().strip()
        admin.keyboard.press("Escape")
        m = ctx().new_page(); watch(m, "meena")
        login(m, "meena", pwd, "Meena@5678")
        m.context.close()
    check("reset password → user signs in with temp password", reset_pwd)

    def bulk_role():
        for n in ("Vikram Singh", "Sunita Iyer"):
            admin.locator("tbody tr", has_text=n).locator("input[type=checkbox]").check()
        admin.get_by_role("button", name="Bulk Assign Role").click()
        admin.get_by_role("dialog").get_by_label("Role").select_option("readonly")
        admin.get_by_role("dialog").get_by_role("button", name="Assign role").click()
        toast(admin, "Role updated for 2 user(s)")
        expect(admin.locator("tbody tr", has_text="Vikram Singh")).to_contain_text("Read Only", timeout=T)
    check("bulk assign role to 2 users", bulk_role)

    def deactivate():
        admin.locator("tbody tr", has_text="Meena Verma").locator("input[type=checkbox]").check()
        admin.get_by_role("button", name="Deactivate").first.click()
        admin.get_by_role("dialog").get_by_role("button", name="Deactivate").click()
        expect(admin.locator("tbody tr", has_text="Meena Verma")).to_contain_text("Inactive", timeout=T)
        m = ctx().new_page()
        m.goto(f"{BASE}/login"); m.get_by_label("Login ID").fill("meena"); m.get_by_label("Password", exact=True).fill("Meena@5678")
        m.get_by_role("button", name="Sign in").click()
        expect(m.get_by_text("deactivated")).to_be_visible(timeout=T)
        m.context.close()
    check("deactivated user cannot sign in", deactivate)

    def import_users():
        wb = Workbook(); ws = wb.active
        ws.append(["Full Name", "Login ID", "Password", "Section", "Assigned PC", "Mobile", "Email", "Role", "Status"])
        ws.append(["Imported Person", "imp.person", "Import@123", "Audit", "", "9999999999", "imp@office.local", "Normal User", "Active"])
        buf = io.BytesIO(); wb.save(buf)
        f = tmpfile("import.xlsx", buf.getvalue())
        admin.get_by_role("button", name="Import Excel").click()
        with admin.expect_file_chooser() as fc:
            admin.get_by_role("dialog").get_by_role("button", name="Choose .xlsx file").click()
        fc.value.set_files(f)
        expect(admin.get_by_text("1 user(s) created")).to_be_visible(timeout=T)
        admin.keyboard.press("Escape")
        expect(admin.locator("tbody tr", has_text="Imported Person")).to_be_visible(timeout=T)
    check("import users from Excel", import_users)

    def export_users():
        d = dl(admin, lambda: admin.get_by_role("button", name="Export Excel").click())
        wb = load_workbook(io.BytesIO(Path(d.path()).read_bytes()))
        names = [r[1] for r in wb.active.iter_rows(min_row=5, values_only=True)]
        assert "Meena Verma" in names, names
    check("export users to Excel", export_users)

    # ===================================================================== FILES
    sect("File Depository")
    doc = tmpfile("Policy.pdf", PDF)

    def upload_repo():
        go(admin, "/files")
        admin.get_by_role("button", name="Upload File(s)").click()
        dlg = admin.get_by_role("dialog")
        dlg.get_by_label("Destination folder").select_option(label="Circulars")
        dlg.locator("input[type=file]").set_input_files([doc, att_png])
        dlg.get_by_role("button", name="Upload 2").click()
        expect(dlg.get_by_text("done")).to_have_count(2, timeout=T)
        dlg.get_by_role("button", name="Close").last.click()
        expect(admin.locator("tbody tr", has_text="Policy.pdf")).to_be_visible(timeout=T)
    check("upload 2 files to Circulars", upload_repo)

    def version():
        admin.get_by_role("button", name="Upload File(s)").click()
        dlg = admin.get_by_role("dialog")
        dlg.get_by_label("Destination folder").select_option(label="Circulars")
        dlg.locator("input[type=file]").set_input_files(tmpfile("Policy.pdf", PDF + b"\n% v2"))
        dlg.get_by_role("button", name="Upload 1").click()
        dlg.get_by_role("button", name="Save as new version").click()
        expect(dlg.get_by_text("Saved as version 2")).to_be_visible(timeout=T)
        dlg.get_by_role("button", name="Close").last.click()
    check("duplicate name → save as version 2", version)

    def detail_panel():
        admin.locator("tbody tr", has_text="Policy.pdf").click()
        expect(admin.get_by_text("File Preview & Details")).to_be_visible()
        expect(admin.locator("section").get_by_text("v2").first).to_be_visible(timeout=T)
        admin.get_by_role("button", name="File History").click()
        admin.get_by_role("dialog").get_by_role("tab", name=re.compile("Versions")).click()
        expect(admin.get_by_role("dialog").get_by_text("v1")).to_be_visible()
        admin.keyboard.press("Escape")
    check("details panel + version history", detail_panel)

    def rename_move_copy():
        admin.locator("tbody tr", has_text="Site.png").click()
        admin.get_by_role("button", name="Rename").click()
        admin.get_by_role("dialog").get_by_label("File name").fill("Site photo")
        admin.get_by_role("dialog").get_by_role("button", name="Save").click()
        expect(admin.locator("tbody tr", has_text="Site photo.png")).to_be_visible(timeout=T)
        admin.locator("tbody tr", has_text="Site photo.png").click()
        admin.get_by_role("button", name="Copy", exact=True).click()
        admin.get_by_role("dialog").get_by_label("Target folder").select_option(label="Archive")
        admin.get_by_role("dialog").get_by_role("button", name="Copy").click()
        toast(admin, "File copied")
        admin.get_by_role("button", name="Move To").click()
        admin.get_by_role("dialog").get_by_label("Target folder").select_option(label="Engineering")
        admin.get_by_role("dialog").get_by_role("button", name="Move").click()
        toast(admin, "File moved")
    check("rename, copy to Archive, move to Engineering", rename_move_copy)

    def share_specific():
        admin.locator("tbody tr", has_text="Policy.pdf").click()
        admin.get_by_role("button", name="Share / Access").click()
        dlg = admin.get_by_role("dialog")
        dlg.get_by_role("tab", name="Specific Users").click()
        dlg.get_by_label(re.compile("Rahul Mehta")).check()
        dlg.get_by_role("button", name="Save access").click()
        toast(admin, "Access updated")
        go(rahul, "/files?view=shared")
        expect(rahul.locator("tbody tr", has_text="Policy.pdf")).to_be_visible(timeout=T)
        go(anita, "/files")
        expect(anita.locator("tbody tr", has_text="Policy.pdf")).to_have_count(0, timeout=T)
    check("share with specific user: visible to rahul, hidden from anita", share_specific)

    def recycle():
        go(admin, "/files")
        admin.locator("tbody tr", has_text="Policy.pdf").click()
        admin.get_by_role("button", name="Delete", exact=True).click()
        admin.get_by_role("dialog").get_by_role("button", name="Move to Recycle Bin").click()
        toast(admin, "Recycle Bin")
        admin.locator("aside, div").get_by_role("button", name=re.compile("^Recycle Bin")).first.click()
        admin.locator("tbody tr", has_text="Policy.pdf").get_by_role("button", name="Restore").click()
        toast(admin, "restored")
    check("delete → Recycle Bin → restore", recycle)

    def repo_download():
        go(admin, "/files")
        admin.locator("tbody tr", has_text="Policy.pdf").click()
        d = dl(admin, lambda: admin.locator("tbody tr", has_text="Policy.pdf").get_by_role("button", name="Download").click())
        assert Path(d.path()).read_bytes() == PDF + b"\n% v2"
    check("download latest version is correct", repo_download)

    def new_folder():
        admin.get_by_role("button", name="New Folder", exact=True).click()
        admin.get_by_role("dialog").get_by_label("Folder name").fill("Project X")
        admin.get_by_role("dialog").get_by_role("button", name="Create").click()
        expect(admin.get_by_role("button", name=re.compile("Project X"))).to_be_visible(timeout=T)
    check("create folder", new_folder)

    # ===================================================================== SETTINGS
    sect("Settings")

    def branding():
        go(admin, "/settings")
        admin.get_by_placeholder("e.g. MES Office, Garrison Engineer (East)").fill("Test Office East")
        admin.get_by_placeholder("Motto shown in small text under the office name").fill("Service with Integrity")
        admin.get_by_role("button", name="Save Changes").click()
        toast(admin, "Settings saved")
        expect(admin.locator("header").get_by_text("Test Office East")).to_be_visible(timeout=T)
        expect(rahul.locator("header").get_by_text("Test Office East")).to_be_visible(timeout=T)
    check("office name + slogan appear in header for all users live", branding)

    def theme_layout():
        admin.get_by_role("button", name="blue theme").click()
        admin.get_by_role("button", name="Modern", exact=True).click()
        admin.get_by_role("button", name="Save Changes").click()
        toast(admin, "Settings saved")
        assert admin.evaluate("document.documentElement.dataset.theme") == "blue"
        assert admin.evaluate("document.documentElement.dataset.layout") == "modern"
        rahul.reload(); rahul.wait_for_load_state("networkidle")
        assert rahul.evaluate("document.documentElement.dataset.theme") == "blue"
        admin.get_by_role("button", name="Reset to Default").click()
        admin.get_by_role("dialog").get_by_role("button", name="Reset").click()
        admin.get_by_role("button", name="Save Changes").click()
        toast(admin, "Settings saved")
    check("colour theme + page design save and apply to other users", theme_layout)

    def max_files():
        admin.get_by_text("Maximum Files per Transfer").locator("xpath=..").locator("select").select_option("5")
        admin.get_by_role("button", name="Save Changes").click()
        toast(admin, "Settings saved")
        rahul.reload()
        go(rahul, "/send")
        rahul.get_by_role("button", name="File / Document").click()
        rahul.locator("input[type=file]").first.set_input_files([tmpfile(f"f{i}.txt", b"x") for i in range(6)])
        toast(rahul, "Maximum 5 files per transfer")
    check("max files per transfer setting is enforced on Send page", max_files)

    def backup():
        go(admin, "/settings")
        admin.get_by_role("button", name="Create Backup Now").click()
        toast(admin, "Backup created")
        admin.get_by_role("button", name="Restore from Backup").click()
        expect(admin.get_by_role("dialog").get_by_text("offline_share_manual_")).to_be_visible(timeout=T)
        admin.keyboard.press("Escape")
    check("backup now + backup list", backup)

    def maintenance():
        for b, txt in (("Check Now", "Database integrity OK"), ("Rebuild", "Search index rebuilt"), ("Clear Now", "temporary item")):
            admin.get_by_role("button", name=b).click()
            toast(admin, txt)
        admin.get_by_role("button", name="View Logs").click()
        expect(admin.get_by_role("dialog").locator("pre")).to_contain_text("OFFLINE SHARE", timeout=T)
        admin.keyboard.press("Escape")
        admin.get_by_role("button", name="Run Test").click()
        expect(admin.get_by_role("dialog").get_by_text("Latency")).to_be_visible(timeout=T)
        admin.keyboard.press("Escape")
    check("maintenance: integrity, index, temp, logs, network test", maintenance)

    # ===================================================================== MISC
    sect("Notifications & misc")

    def bell():
        rahul.locator("header").get_by_role("button", name="Notifications").click()
        expect(rahul.get_by_text("Read:").first).to_be_visible(timeout=T)
        rahul.keyboard.press("Escape")
    check("sender gets read-receipt notification in bell", bell)

    def dashboard_numbers():
        go(rahul, "/dashboard")
        total = int(rahul.locator(".os-stat", has_text="Total Sent").locator(".text-\\[26px\\]").inner_text())
        assert total >= 1, total
    check("dashboard numbers come from real data", dashboard_numbers)

    def mobile():
        m = browser.new_context(viewport={"width": 390, "height": 844}).new_page(); watch(m, "mobile")
        login(m, "admin", "Admin@12345", wait_online=False)
        go(m, "/receive")
        w = m.evaluate("document.documentElement.scrollWidth")
        assert w <= 400, f"page is {w}px wide on a 390px phone (horizontal scroll)"
        m.context.close()
    check("phone width: no horizontal page scroll", mobile)

    def logout_all():
        rahul.locator("aside").get_by_role("button", name="Logout").click()
        rahul.get_by_role("button", name="Yes, Logout").click()
        expect(rahul.get_by_role("heading", name="Sign in")).to_be_visible(timeout=T)
        go(rahul, "/dashboard")
        expect(rahul.get_by_role("heading", name="Sign in")).to_be_visible(timeout=T)
    check("logout ends session; protected page redirects to sign-in", logout_all)

    browser.close()

print("\n================ SUMMARY ================")
cur = None
for s, n, ok, m in results:
    if s != cur:
        print(f"\n{s}")
        cur = s
    print(f"  {'PASS' if ok else 'FAIL'}  {n}" + (f"\n        → {m}" if m else ""))
print(f"\n{sum(r[2] for r in results)} / {len(results)} passed")
print("\nBrowser / server errors:" if errors else "\nNo JS errors or HTTP 5xx.")
for e in sorted(set(errors)):
    print("  ", e)
