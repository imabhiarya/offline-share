"""Browser end-to-end test of the built frontend against a running server.

Usage: python tests/ui_e2e.py http://127.0.0.1:5050 <screenshot-dir>
Requires: pip install playwright (uses the locally installed Google Chrome, no download).
Expects demo data from tools/seed_demo.py and admin password Admin@12345.
"""
import sys
import time
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

BASE = sys.argv[1]
OUT = Path(sys.argv[2])
OUT.mkdir(parents=True, exist_ok=True)
errors: list[str] = []
results: list[tuple[str, bool, str]] = []
PAGES: dict = {}


def check(name, fn):
    try:
        fn()
        results.append((name, True, ""))
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        call = next((l.strip() for l in msg.splitlines() if "waiting for" in l), "")
        results.append((name, False, msg.splitlines()[0][:160] + " | " + call[:160]))
        for pg in list(PAGES):
            try:
                pg.screenshot(path=OUT / f"FAIL_{len(results)}_{PAGES[pg]}.png", full_page=True)
            except Exception:
                pass


def watch(page, who):
    PAGES[page] = who
    page.on("console", lambda m: m.type == "error" and errors.append(f"[{who}] console: {m.text}"))
    page.on("pageerror", lambda e: errors.append(f"[{who}] pageerror: {e}"))


def login(page, user, pwd):
    page.goto(f"{BASE}/login")
    page.get_by_label("Login ID").fill(user)
    page.get_by_label("Password", exact=True).fill(pwd)
    page.get_by_role("button", name="Sign in").click()


with sync_playwright() as p:
    browser = p.chromium.launch(channel="chrome", headless=True)
    admin_ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    admin = admin_ctx.new_page()
    watch(admin, "admin")

    def admin_login():
        login(admin, "admin", "Admin@12345")
        expect(admin.get_by_text("Welcome,")).to_be_visible(timeout=10000)
        expect(admin.locator("header").get_by_text("Online", exact=True)).to_be_visible(timeout=10000)
        admin.screenshot(path=OUT / "01_dashboard.png", full_page=True)
    check("admin login + dashboard + live connection", admin_login)

    pages = [("/send", "Send Data"), ("/receive", "Receive Data (Inbox)"), ("/history", "Transfer History"),
             ("/devices", "Connected Devices"), ("/users", "User Management"),
             ("/files", "File Depository (Central Repository)"), ("/settings", "Settings – System Configuration")]
    for i, (path, title) in enumerate(pages, 2):
        def visit(path=path, title=title, i=i):
            admin.goto(BASE + path)
            expect(admin.get_by_role("heading", name=title, exact=True)).to_be_visible(timeout=10000)
            admin.wait_for_timeout(600)
            admin.screenshot(path=OUT / f"{i:02d}_{path.strip('/')}.png", full_page=True)
        check(f"page renders: {title}", visit)

    def network_map():
        admin.goto(BASE + "/devices")
        admin.get_by_role("tab", name="Network Map").click()
        expect(admin.get_by_text("Wi-Fi Access Point")).to_be_visible()
        admin.screenshot(path=OUT / "09_network_map.png", full_page=True)
    check("network map", network_map)

    # ---- receiver logs in on a second "PC" and must change the password first
    rctx = browser.new_context(viewport={"width": 1366, "height": 850})
    recv = rctx.new_page()
    watch(recv, "rahul")

    def recv_login():
        login(recv, "rahul", "Demo@1234")
        expect(recv.get_by_text("Set a new password")).to_be_visible(timeout=10000)
        recv.screenshot(path=OUT / "10_forced_password_change.png")
        dlg = recv.get_by_role("dialog")
        dlg.get_by_label("Current password").fill("Demo@1234")
        dlg.get_by_label("New password", exact=True).fill("Rahul@2026")
        dlg.get_by_label("Repeat new password").fill("Rahul@2026")
        dlg.get_by_role("button", name="Save password").click()
        expect(recv.get_by_text("Set a new password")).to_be_hidden(timeout=10000)
        recv.goto(BASE + "/receive")
        expect(recv.locator("header").get_by_text("Online", exact=True)).to_be_visible(timeout=10000)
    check("receiver first login with forced password change", recv_login)

    # ---- admin sends a formatted message with a file to Rahul
    sample = OUT / "Budget_Q3.txt"
    sample.write_text("Line 1 of the budget\nLine 2\n")

    def send():
        admin.goto(BASE + "/send")
        admin.get_by_label("Subject").fill("Q3 budget review")
        ed = admin.locator(".editor")
        ed.click()
        admin.keyboard.type("Please review the ")
        admin.keyboard.press("Meta+b")
        admin.keyboard.type("attached")
        admin.keyboard.press("Meta+b")
        admin.keyboard.type(" budget before Friday.")
        admin.locator("input[type=file]").first.set_input_files(str(sample))
        expect(admin.locator('[aria-label="ready"]')).to_be_visible(timeout=10000)
        admin.get_by_placeholder("Search by Name, PC Name, Section or IP…").fill("rahul")
        admin.get_by_text("Rahul Mehta").first.click()
        admin.get_by_label("Priority").select_option("high")
        admin.screenshot(path=OUT / "11_send_compose.png", full_page=True)
        admin.get_by_role("button", name="Send Data", exact=True).click()
        expect(admin.get_by_text("live delivery status")).to_be_visible(timeout=10000)
    check("send text + file via UI", send)

    def delivered():
        # receiver's open browser acknowledges over WebSocket -> Delivered
        expect(admin.get_by_text("Delivered").first).to_be_visible(timeout=15000)
        admin.screenshot(path=OUT / "12_send_delivered.png", full_page=True)
    check("status becomes Delivered only after receiver ack", delivered)

    def receive_and_read():
        expect(recv.get_by_text("New file from System Administrator")).to_be_visible(timeout=10000)
        recv.screenshot(path=OUT / "13_receiver_toast.png")
        recv.reload()
        recv.get_by_text("Q3 budget review").first.click()
        expect(recv.get_by_text("Message Preview")).to_be_visible()
        expect(recv.locator(".rich b").first).to_have_text("attached")
        expect(recv.get_by_text("Budget_Q3.txt").first).to_be_visible()
        recv.screenshot(path=OUT / "14_receiver_message.png")
        recv.get_by_role("button", name="Copy Message").click()
        expect(recv.get_by_text("copied to this PC")).to_be_visible(timeout=5000)
    check("receiver inbox, preview, rich text, copy message", receive_and_read)

    def read_status():
        expect(admin.get_by_text("Read").first).to_be_visible(timeout=10000)
    check("sender sees Read status (read receipt)", read_status)

    def history():
        admin.goto(BASE + "/history?tab=sent")
        expect(admin.get_by_text("Q3 budget review").first).to_be_visible(timeout=10000)
        admin.get_by_text("Q3 budget review").first.click()
        expect(admin.get_by_text("Transfer Details")).to_be_visible()
        expect(admin.get_by_text("Budget_Q3.txt").first).to_be_visible()
        admin.screenshot(path=OUT / "15_history_detail.png", full_page=True)
    check("history + per-PC detail", history)

    def repo_upload():
        admin.goto(BASE + "/files")
        admin.get_by_role("button", name="Upload File(s)").click()
        dlg = admin.get_by_role("dialog")
        dlg.locator("input[type=file]").set_input_files(str(sample))
        dlg.get_by_role("button", name="Upload 1").click()
        expect(dlg.get_by_text("done")).to_be_visible(timeout=10000)
        dlg.get_by_role("button", name="Close").last.click()
        expect(admin.get_by_text("Budget_Q3.txt").first).to_be_visible(timeout=10000)
        admin.screenshot(path=OUT / "16_files.png", full_page=True)
    check("file depository upload", repo_upload)

    def settings_backup():
        admin.goto(BASE + "/settings")
        admin.get_by_role("button", name="Backup", exact=True).click()
        admin.get_by_role("button", name="Create Backup Now").click()
        expect(admin.get_by_text("Backup created")).to_be_visible(timeout=20000)
        admin.screenshot(path=OUT / "17_backup.png", full_page=True)
        admin.get_by_role("button", name="Maintenance", exact=True).click()
        admin.get_by_role("button", name="Check Now").click()
        expect(admin.get_by_text("Database integrity OK").first).to_be_visible(timeout=10000)
        admin.screenshot(path=OUT / "18_maintenance.png", full_page=True)
    check("manual backup + integrity check", settings_backup)

    def logout():
        recv.get_by_role("button", name="Logout").first.click()
        recv.get_by_role("button", name="Yes, Logout").click()
        expect(recv.get_by_role("heading", name="Sign in")).to_be_visible(timeout=10000)
        recv.screenshot(path=OUT / "19_login.png")
    check("logout confirmation", logout)

    browser.close()

for name, ok, msg in results:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{'  -> ' + msg if msg else ''}")
print("\nBrowser errors:" if errors else "\nNo browser console errors.")
for e in errors:
    print("  ", e)
sys.exit(0 if all(ok for _, ok, _ in results) else 1)
