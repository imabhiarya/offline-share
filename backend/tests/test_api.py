"""End-to-end API tests: auth, RBAC, CSRF, transfers, inbox, history, devices, users, files, settings, backup."""
import io
import time

import pytest
from openpyxl import Workbook, load_workbook

from conftest import Api


def mkuser(admin, login, role="user", section_id=None, device_id=None, password="User@12345"):
    r = admin.post("/api/users", json={"full_name": login.title(), "login_id": login, "password": password,
                                       "role": role, "section_id": section_id, "assigned_device_id": device_id})
    assert r.status_code == 200, r.text
    return r.json()


def first_login(login, ip, password="User@12345", new="Better@12345"):
    a = Api(ip)
    a.login(login, password)
    r = a.post("/api/auth/change-password", json={"current_password": password, "new_password": new})
    assert r.status_code == 200, r.text
    return a


# --------------------------------------------------------------------------- auth / security
def test_health_is_public():
    a = Api()
    r = a.get("/api/health")
    assert r.status_code == 200 and r.json()["database"] == "ok"
    assert "OFFLINE SHARE" in a.get("/health").text


def test_non_lan_client_is_refused():
    a = Api("10.20.30.40")
    assert a.get("/api/health").status_code == 403


def test_login_wrong_password_and_lockout(admin):
    mkuser(admin, "lockme")
    a = Api("192.168.50.120")
    for _ in range(5):
        a.login("lockme", "nope", expect=401)
    r = a.login("lockme", "User@12345", expect=423)
    assert "locked" in r.json()["detail"].lower()


def test_csrf_required_for_mutations(admin):
    r = admin.c.post("/api/notifications/read", json={"all": True})  # no header
    assert r.status_code == 403
    r = admin.post("/api/notifications/read", json={"all": True})
    assert r.status_code == 200


def test_unauthenticated_is_401():
    assert Api().get("/api/dashboard").status_code == 401


def test_password_policy_enforced(admin):
    r = admin.post("/api/users", json={"full_name": "Weak", "login_id": "weak", "password": "short", "role": "user"})
    assert r.status_code == 400 and "Password must contain" in r.json()["detail"]


def test_passwords_are_hashed(admin):
    import sqlite3
    from app.config import config
    con = sqlite3.connect(config.db_path)
    rows = con.execute("select password_hash from users").fetchall()
    assert rows and all(r[0].startswith("scrypt$") for r in rows)


def test_rbac_readonly_cannot_send_or_manage(admin):
    mkuser(admin, "viewer", role="readonly")
    v = first_login("viewer", "192.168.50.121")
    assert v.get("/api/users").status_code == 403
    assert v.get("/api/devices").status_code == 403
    assert v.get("/api/settings").status_code == 403
    r = v.post("/api/transfers", json={"recipient_user_ids": [1], "body_html": "hi"})
    assert r.status_code == 403
    assert v.get("/api/inbox").status_code == 200


def test_logout_ends_session(admin):
    mkuser(admin, "bye")
    b = first_login("bye", "192.168.50.122")
    assert b.post("/api/auth/logout").status_code == 200
    assert b.get("/api/auth/me").status_code == 401


# --------------------------------------------------------------------------- transfers
@pytest.fixture(scope="module")
def people(admin):
    sec = admin.get("/api/sections").json()
    acc = next(s for s in sec if s["name"] == "Accounts")
    d1 = admin.post("/api/devices", json={"pc_name": "ACC-PC-01", "ip_address": "192.168.50.131",
                                          "section_id": acc["id"], "connection_type": "lan"}).json()
    d2 = admin.post("/api/devices", json={"pc_name": "ACC-PC-02", "ip_address": "192.168.50.132",
                                          "section_id": acc["id"], "connection_type": "wifi"}).json()
    d3 = admin.post("/api/devices", json={"pc_name": "ENG-PC-01", "ip_address": "192.168.50.133",
                                          "connection_type": "lan"}).json()
    s = mkuser(admin, "sender1", section_id=acc["id"], device_id=d1["id"])
    r = mkuser(admin, "recv1", section_id=acc["id"], device_id=d2["id"])
    o = mkuser(admin, "offline1", device_id=d3["id"])
    return {"sender": (s, first_login("sender1", "192.168.50.131")),
            "recv": (r, first_login("recv1", "192.168.50.132")),
            "offline": (o, None), "devices": (d1, d2, d3)}


def _ws_recv_until(ws, kind, limit=20):
    for _ in range(limit):
        m = ws.receive_json()
        if m["type"] == kind:
            return m
    raise AssertionError(f"no {kind} message")


def test_send_text_delivery_lifecycle(people):
    (s_user, sender), (r_user, recv) = people["sender"], people["recv"]
    with recv.ws() as ws:
        assert ws.receive_json()["type"] == "hello"
        r = sender.post("/api/transfers", json={
            "subject": "Budget", "body_html": "<p><b>Hello</b> <script>alert(1)</script>team</p>",
            "recipient_user_ids": [r_user["id"]], "read_receipt": True, "priority": "urgent"})
        assert r.status_code == 200, r.text
        data = r.json()
        tid = data["transfer"]["id"]
        assert data["transfer"]["transfer_uid"].startswith("TRF-")
        # never "delivered" just because the sender clicked send
        assert data["recipients"][0]["status"] in ("pending", "sent")
        msg = _ws_recv_until(ws, "transfer.new")
        rid = msg["transfer"]["recipient_id"]
        st = sender.get(f"/api/transfers/{tid}/status").json()
        assert st["recipients"][0]["status"] == "sent"
        ws.send_json({"type": "ack", "recipient_ids": [rid]})
        for _ in range(50):
            st = sender.get(f"/api/transfers/{tid}/status").json()
            if st["recipients"][0]["status"] == "delivered":
                break
            time.sleep(0.05)
        assert st["recipients"][0]["status"] == "delivered"
        assert st["recipients"][0]["delivered_at"]
    # open -> read + sanitised HTML
    m = recv.get(f"/api/inbox/{rid}").json()
    assert "<script>" not in m["body_html"] and "<b>Hello</b>" in m["body_html"]
    assert sender.get(f"/api/transfers/{tid}/status").json()["recipients"][0]["status"] == "read"
    notes = sender.get("/api/notifications").json()
    assert any(n["type"] == "read" for n in notes["items"])


def test_offline_queue_delivers_on_reconnect(admin, people):
    (s_user, sender), (o_user, _) = people["sender"], people["offline"]
    r = sender.post("/api/transfers", json={"body_html": "queued", "recipient_user_ids": [o_user["id"]]})
    tid = r.json()["transfer"]["id"]
    assert sender.get(f"/api/transfers/{tid}/status").json()["recipients"][0]["status"] == "pending"
    off = first_login("offline1", "192.168.50.133")
    with off.ws() as ws:
        ws.receive_json()
        msg = _ws_recv_until(ws, "transfer.new")
        assert msg["transfer"]["id"] == tid
    assert sender.get(f"/api/transfers/{tid}/status").json()["recipients"][0]["status"] == "sent"
    off.get("/api/inbox")  # fetching the inbox is an acknowledgement
    assert sender.get(f"/api/transfers/{tid}/status").json()["recipients"][0]["status"] == "delivered"


def test_file_transfer_upload_download_zip(people):
    (s_user, sender), (r_user, recv) = people["sender"], people["recv"]
    content = b"%PDF-1.4 test" * 1000
    up = sender.post("/api/transfers/uploads", files={"file": ("Report Q1.pdf", content, "application/pdf")})
    assert up.status_code == 200, up.text
    up2 = sender.post("/api/transfers/uploads", files={"file": ("data.xlsx", b"x" * 10, "application/octet-stream")})
    bad = sender.post("/api/transfers/uploads", files={"file": ("virus.exe", b"MZ", "application/octet-stream")})
    assert bad.status_code == 415
    r = sender.post("/api/transfers", json={"subject": "Files", "recipient_user_ids": [r_user["id"]],
                                            "attachment_uids": [up.json()["uid"], up2.json()["uid"]]})
    assert r.status_code == 200, r.text
    t = r.json()["transfer"]
    assert t["file_count"] == 2 and t["kind"] == "file"
    inbox = recv.get("/api/inbox?category=attachments").json()
    item = next(i for i in inbox["items"] if i["id"] == t["id"])
    detail = recv.get(f"/api/inbox/{item['recipient_id']}").json()
    pdf = next(a for a in detail["attachments"] if a["name"] == "Report Q1.pdf")
    dl = recv.get(f"/api/attachments/{pdf['uid']}")
    assert dl.status_code == 200 and dl.content == content
    z = recv.get(f"/api/transfers/{t['id']}/zip")
    assert z.status_code == 200 and z.content[:2] == b"PK"
    # an unrelated user cannot download it
    stranger = Api("192.168.50.140")
    stranger.login("admin", "Admin@12345")  # admin may (audit); use readonly viewer instead
    v = Api("192.168.50.121")
    v.login("viewer", "Better@12345")
    assert v.get(f"/api/attachments/{pdf['uid']}").status_code == 404


def test_max_file_size_enforced(admin, people):
    _, sender = people["sender"]
    admin.put("/api/settings", json={"values": {"max_file_size_mb": 1}})
    r = sender.post("/api/transfers/uploads", files={"file": ("big.zip", b"0" * (1024 * 1024 + 10), "application/zip")})
    assert r.status_code == 413
    admin.put("/api/settings", json={"values": {"max_file_size_mb": 200}})


def test_inbox_flags_search_and_categories(people):
    (s_user, sender), (r_user, recv) = people["sender"], people["recv"]
    sender.post("/api/transfers", json={"subject": "Quarterly circular zebra", "body_html": "find me",
                                        "recipient_user_ids": [r_user["id"]]})
    res = recv.get("/api/inbox?q=zebra").json()
    assert res["total"] == 1
    rid = res["items"][0]["recipient_id"]
    assert recv.patch(f"/api/inbox/{rid}", json={"is_flagged": True}).status_code == 200
    assert recv.get("/api/inbox?category=flagged").json()["total"] >= 1
    recv.post("/api/inbox/bulk", json={"recipient_ids": [rid], "action": "archive"})
    assert any(i["recipient_id"] == rid for i in recv.get("/api/inbox?category=archived").json()["items"])
    recv.post("/api/inbox/bulk", json={"recipient_ids": [rid], "action": "delete"})
    assert any(i["recipient_id"] == rid for i in recv.get("/api/inbox?category=deleted").json()["items"])
    counts = recv.get("/api/inbox/counts").json()
    assert set(counts) >= {"all", "unread", "read", "attachments", "text", "flagged", "important", "archived",
                           "deleted"}
    tid_search = recv.get(f"/api/inbox?q={res['items'][0]['transfer_uid']}").json()
    assert tid_search["total"] == 0 or tid_search["items"][0]["recipient_id"] == rid


def test_expiry_and_retry(admin, people):
    import asyncio
    from datetime import datetime, timedelta, timezone

    from app.database import SessionLocal
    from app.models import Transfer
    from app.services.delivery import worker_tick
    (s_user, sender), (o_user, _) = people["sender"], people["offline"]
    exp = (datetime.now(timezone.utc) + timedelta(minutes=5)).isoformat()
    r = sender.post("/api/transfers", json={"body_html": "short-lived", "recipient_user_ids": [o_user["id"]],
                                            "expires_at": exp})
    tid = r.json()["transfer"]["id"]
    with SessionLocal() as db:
        t = db.get(Transfer, tid)
        from app.models import utcnow
        t.expires_at = utcnow() - timedelta(seconds=1)
        db.commit()
    asyncio.run(worker_tick())
    st = sender.get(f"/api/transfers/{tid}/status").json()
    assert st["recipients"][0]["status"] == "failed"
    hist = sender.get("/api/history?tab=failed").json()
    row = next(i for i in hist["items"] if i["transfer_id"] == tid)
    assert row["can_retry"]
    assert sender.post("/api/history/retry", json={"recipient_ids": [row["id"]]}).json()["retried"] == 1
    assert sender.get(f"/api/transfers/{tid}/status").json()["recipients"][0]["status"] == "pending"


def test_history_filters_and_export(people):
    _, sender = people["sender"]
    h = sender.get("/api/history?tab=sent").json()
    assert h["total"] >= 3 and all(i["direction"] == "sent" for i in h["items"])
    assert sender.get("/api/history?file_type=pdf").json()["total"] >= 1
    assert sender.get("/api/history?user=recv1").json()["total"] >= 1
    uid = h["items"][0]["transfer_uid"]
    d = sender.get(f"/api/history/transfer/{uid}").json()
    assert d["recipients"] and d["sender"]["login"] == "sender1"
    x = sender.get("/api/history/export.xlsx")
    assert x.status_code == 200
    wb = load_workbook(io.BytesIO(x.content))
    assert wb.active.cell(row=4, column=2).value == "Transfer ID"


def test_drafts(people):
    _, sender = people["sender"]
    d = sender.post("/api/drafts", json={"subject": "draft", "body_html": "wip", "recipient_user_ids": [1]}).json()
    assert sender.get("/api/drafts").json()[0]["id"] == d["id"]
    sender.put(f"/api/drafts/{d['id']}", json={"subject": "draft2"})
    assert sender.get("/api/drafts").json()[0]["subject"] == "draft2"
    assert sender.delete(f"/api/drafts/{d['id']}").status_code == 200


# --------------------------------------------------------------------------- devices
def test_unknown_device_detection_and_block(admin):
    mkuser(admin, "roamer")
    a = Api("192.168.50.177")
    a.login("roamer", "User@12345")
    devs = admin.get("/api/devices?q=192.168.50.177").json()["items"]
    assert devs and devs[0]["is_unknown"] and devs[0]["status"] == "pending"
    assert devs[0]["connection_type"] == "wifi"  # inside the default Wi-Fi range
    admin.post(f"/api/devices/{devs[0]['id']}/status", json={"status": "blocked"})
    assert a.get("/api/auth/me").status_code == 401  # session ended
    a.login("roamer", "User@12345", expect=403)
    admin.post(f"/api/devices/{devs[0]['id']}/status", json={"status": "approved"})
    a.login("roamer", "User@12345")


def test_registered_pc_restriction(admin):
    admin.put("/api/settings", json={"values": {"registered_pc_restriction": True}})
    mkuser(admin, "strict1")
    Api("192.168.50.188").login("strict1", "User@12345", expect=403)
    admin.put("/api/settings", json={"values": {"registered_pc_restriction": False}})


def test_agent_register_and_heartbeat(admin):
    key = admin.get("/api/devices/agent-key").json()["enrolment_key"]
    ag = Api("192.168.50.160")
    assert ag.c.post("/api/agent/register", json={"enrolment_key": "bad", "pc_name": "X"}).status_code == 403
    r = ag.c.post("/api/agent/register", json={"enrolment_key": key, "pc_name": "store-pc-07", "mac_address": "aa:bb",
                                               "os_info": "Windows 11", "connection_type": "lan"})
    assert r.status_code == 200
    tok = r.json()["token"]
    hb = ag.c.post("/api/agent/heartbeat", json={"connection_type": "lan"}, headers={"X-Agent-Token": tok})
    assert hb.status_code == 200
    d = next(i for i in admin.get("/api/devices?q=STORE-PC-07").json()["items"])
    assert d["agent_online"] and d["online"] and not d["browser_active"]
    assert admin.get("/api/devices/network-map").status_code == 200
    assert admin.get("/api/devices/export.xlsx").status_code == 200


def test_device_duplicate_ip_rejected(admin):
    r = admin.post("/api/devices", json={"pc_name": "DUP", "ip_address": "192.168.50.131"})
    assert r.status_code == 409


# --------------------------------------------------------------------------- users
def test_user_crud_and_soft_delete_preserves_history(admin, people):
    u = mkuser(admin, "temp1")
    r = admin.put(f"/api/users/{u['id']}", json={"full_name": "Temp One", "login_id": "temp1", "role": "readonly",
                                                 "permission_overrides": {"send": True}})
    assert r.status_code == 200 and "send" in r.json()["permissions"]
    rp = admin.post(f"/api/users/{u['id']}/reset-password", json={}).json()
    assert rp["temporary_password"]
    assert admin.post(f"/api/users/{u['id']}/status", json={"status": "inactive"}).json()["status"] == "inactive"
    Api("192.168.50.150").login("temp1", rp["temporary_password"], expect=403)
    # delete the receiver of earlier transfers: history keeps the name snapshot
    r_user, _ = people["recv"]
    s_user, sender = people["sender"]
    assert admin.delete(f"/api/users/{r_user['id']}").status_code == 200
    h = sender.get("/api/history?tab=sent").json()
    assert any(i["recipient_name"] == "Recv1" for i in h["items"])
    assert admin.delete(f"/api/users/{admin.get('/api/auth/me').json()['user']['id']}").status_code == 400


def test_user_import_export(admin):
    wb = Workbook()
    ws = wb.active
    ws.append(["Full Name", "Login ID", "Password", "Section", "Assigned PC", "Mobile", "Email", "Role", "Status"])
    ws.append(["Imported One", "imp1", "Import@123", "Store", "", "9999999999", "imp1@office.local", "Normal User",
               "Active"])
    ws.append(["Bad Row", "", "", "", "", "", "", "", ""])
    buf = io.BytesIO()
    wb.save(buf)
    r = admin.post("/api/users/import", files={"file": ("u.xlsx", buf.getvalue(),
                                                        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, r.text
    assert r.json()["created"] == 1 and len(r.json()["errors"]) == 1
    assert admin.get("/api/users?q=imp1").json()["total"] == 1
    assert admin.get("/api/users/export.xlsx").status_code == 200


def test_admin_cannot_edit_super_admin(admin):
    mkuser(admin, "admin2", role="admin")
    a2 = first_login("admin2", "192.168.50.170")
    sa = admin.get("/api/auth/me").json()["user"]
    r = a2.post(f"/api/users/{sa['id']}/reset-password", json={})
    assert r.status_code == 403
    r = a2.put("/api/settings", json={"values": {"max_login_attempts": 3}})
    assert r.status_code == 403  # security group is super-admin only


# --------------------------------------------------------------------------- files
def test_repository_flow(admin, people):
    _, sender = people["sender"]
    folders = sender.get("/api/files/folders").json()
    names = {f["name"] for f in folders["folders"]}
    assert {"Administration", "Accounts", "Circulars", "Archive", "Policies & Orders"} <= names
    circ = next(f for f in folders["folders"] if f["name"] == "Circulars")
    arch = next(f for f in folders["folders"] if f["name"] == "Archive")
    up = sender.post("/api/files/upload", data={"folder_id": circ["id"], "access_scope": "all"},
                     files={"file": ("Circular 12.pdf", b"v1", "application/pdf")})
    assert up.status_code == 200, up.text
    fid = up.json()["file"]["id"]
    dup = sender.post("/api/files/upload", data={"folder_id": circ["id"]},
                      files={"file": ("Circular 12.pdf", b"v2", "application/pdf")})
    assert dup.status_code == 409 and dup.json()["duplicate"] == "name"
    v2 = sender.post("/api/files/upload", data={"folder_id": circ["id"], "on_duplicate": "version"},
                     files={"file": ("Circular 12.pdf", b"v2", "application/pdf")})
    assert v2.json()["file"]["version"] == 2
    assert sender.get(f"/api/files/{fid}/download?version=1").content == b"v1"
    assert sender.get(f"/api/files/{fid}/download").content == b"v2"
    det = sender.get(f"/api/files/{fid}").json()
    assert len(det["versions"]) == 2 and any(a["action"] == "upload" for a in det["activity"])
    assert sender.patch(f"/api/files/{fid}", json={"name": "Circular 12 final"}).json()["name"] == "Circular 12 final.pdf"
    cp = sender.post(f"/api/files/{fid}/copy", json={"folder_id": arch["id"]}).json()
    assert cp["folder_id"] == arch["id"]
    mv = sender.post(f"/api/files/{cp['id']}/move", json={"folder_id": circ["id"]})
    assert mv.status_code == 409  # name clash in target
    assert sender.get("/api/files?q=Circular").json()["total"] >= 2
    sender.delete(f"/api/files/{fid}")
    assert sender.get("/api/files?view=recycle").json()["total"] >= 1
    sender.post(f"/api/files/{fid}/restore")
    assert sender.get(f"/api/files/{fid}").json()["deleted_at"] is None
    sender.delete(f"/api/files/{cp['id']}")
    assert sender.delete(f"/api/files/{cp['id']}/permanent").status_code == 200
    nf = sender.post("/api/files/folders", json={"name": "Project X"})
    assert nf.status_code == 200
    assert sender.delete(f"/api/files/folders/{nf.json()['id']}").status_code == 200


def test_repository_access_permissions(admin):
    mkuser(admin, "owner1")
    mkuser(admin, "friend1")
    mkuser(admin, "other1")
    owner = first_login("owner1", "192.168.50.181")
    friend = first_login("friend1", "192.168.50.182")
    other = first_login("other1", "192.168.50.183")
    fid_friend = friend.get("/api/auth/me").json()["user"]["id"]
    folder = owner.get("/api/files/folders").json()["folders"][0]
    r = owner.post("/api/files/upload", data={"folder_id": folder["id"], "access_scope": "specific",
                                              "user_ids": f"[{fid_friend}]"},
                   files={"file": ("secret.txt", b"s", "text/plain")})
    fid = r.json()["file"]["id"]
    assert friend.get(f"/api/files/{fid}/download").status_code == 200
    assert friend.get("/api/files?view=shared").json()["total"] == 1
    assert other.get(f"/api/files/{fid}/download").status_code == 404
    assert friend.delete(f"/api/files/{fid}").status_code == 403


# --------------------------------------------------------------------------- dashboard, settings, maintenance, backup
def test_dashboard_real_numbers(admin, people):
    _, sender = people["sender"]
    d = sender.get("/api/dashboard").json()
    assert d["stats"]["total_sent"] >= 3
    assert len(d["activity"]) == 7 and sum(x["sent"] for x in d["activity"]) >= 3
    g = admin.get("/api/dashboard").json()
    assert g["scope"] == "global" and g["health"]["status"] == "online"


def test_settings_update_and_validation(admin):
    s = admin.get("/api/settings").json()
    assert "transfer" in s["settings"] and s["network"]["port"]
    r = admin.put("/api/settings", json={"values": {"allowed_extensions": "pdf, DOCX, .png"}})
    assert r.json()["settings"]["transfer"]["allowed_extensions"] == ["docx", "pdf", "png"]
    assert admin.put("/api/settings", json={"values": {"nope": 1}}).status_code == 400
    admin.put("/api/settings", json={"values": {"allowed_extensions":
              ["pdf", "doc", "docx", "xls", "xlsx", "ppt", "pptx", "txt", "jpg", "jpeg", "png", "zip"]}})


def test_maintenance_tasks(admin):
    for task in ("integrity-check", "rebuild-index", "clear-temp", "optimise"):
        r = admin.post(f"/api/system/maintenance/{task}")
        assert r.status_code == 200, (task, r.text)
    assert admin.post("/api/system/maintenance/integrity-check").json()["ok"]
    assert admin.get("/api/system/audit").json()["total"] > 0
    assert admin.get("/api/system/network-test").status_code == 200


def test_backup_and_restore(admin, people):
    _, sender = people["sender"]
    b = admin.post("/api/system/backups", json={"include_files": True})
    assert b.status_code == 200, b.text
    bid = b.json()["id"]
    before = admin.get("/api/users").json()["total"]
    mkuser(admin, "after_backup")
    assert admin.get("/api/users").json()["total"] == before + 1
    r = admin.post("/api/system/restore", json={"backup_id": bid, "restore_files": True})
    assert r.status_code == 200, r.text
    # sessions are restored with the database, so the admin session is still valid
    assert admin.get("/api/users").json()["total"] == before
    assert admin.get("/api/system/backups").json()["items"]


def test_date_filters_use_local_calendar_day(admin, people):
    """Regression: date filters must use the server's local day, not the UTC day (e.g. 00:10 IST = 18:40 UTC)."""
    from datetime import date, datetime, timedelta

    from app.services.common import local_day_range_utc
    today = date.today()
    start, end = local_day_range_utc(today, today)
    assert end - start == timedelta(days=1)
    local_midnight = datetime.combine(today, datetime.min.time()).astimezone()
    assert start == local_midnight.astimezone().replace(tzinfo=None) - local_midnight.utcoffset()
    _, sender = people["sender"]
    admin_id = admin.get("/api/auth/me").json()["user"]["id"]
    sent = sender.post("/api/transfers", json={"subject": "tz check", "body_html": "x", "recipient_user_ids": [admin_id]})
    assert sent.status_code == 200, sent.text
    t = today.isoformat()
    assert sender.get(f"/api/history?q=tz&date_from={t}&date_to={t}").json()["total"] >= 1
    y = (today - timedelta(days=1)).isoformat()
    assert sender.get(f"/api/history?q=tz&date_from={y}&date_to={y}").json()["total"] == 0
