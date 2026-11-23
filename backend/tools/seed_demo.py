"""DEMO / TEST DATA ONLY – never run on a production server.

Creates sample devices and users through the real HTTP API of a running server so the
UI can be evaluated. Usage:
    python tools/seed_demo.py http://127.0.0.1:5000 admin <admin-password>
"""
import sys

import httpx

BASE, LOGIN, PWD = sys.argv[1], sys.argv[2], sys.argv[3]
c = httpx.Client(base_url=BASE)
r = c.post("/api/auth/login", json={"login_id": LOGIN, "password": PWD})
r.raise_for_status()
H = {"X-CSRF-Token": r.json()["csrf_token"]}
sections = {s["name"]: s["id"] for s in c.get("/api/sections").json()}
devices = [
    ("ADM-PC-01", "192.168.50.101", "Administration", "lan"), ("ACC-PC-01", "192.168.50.111", "Accounts", "lan"),
    ("ACC-PC-02", "192.168.50.112", "Accounts", "lan"), ("STR-PC-01", "192.168.50.121", "Store", "lan"),
    ("ENG-PC-01", "192.168.50.131", "Engineering", "lan"), ("ENG-LT-02", "192.168.50.161", "Engineering", "wifi"),
    ("TEC-LT-01", "192.168.50.171", "Technical", "wifi"), ("AUD-PC-01", "192.168.50.141", "Audit", "lan"),
]
ids = {}
for name, ip, sec, conn in devices:
    d = c.post("/api/devices", headers=H, json={"pc_name": name, "ip_address": ip, "section_id": sections[sec],
                                                "connection_type": conn, "status": "approved"})
    ids[name] = d.json().get("id")
people = [
    ("Priya Sharma", "priya", "Administration", "ADM-PC-01", "admin"), ("Rahul Mehta", "rahul", "Accounts", "ACC-PC-01", "user"),
    ("Anita Desai", "anita", "Accounts", "ACC-PC-02", "user"), ("Vikram Singh", "vikram", "Store", "STR-PC-01", "user"),
    ("Neha Kapoor", "neha", "Engineering", "ENG-PC-01", "user"), ("Arjun Rao", "arjun", "Engineering", "ENG-LT-02", "user"),
    ("Sunita Iyer", "sunita", "Technical", "TEC-LT-01", "user"), ("Karan Joshi", "karan", "Audit", "AUD-PC-01", "readonly"),
]
for full, login, sec, pc, role in people:
    c.post("/api/users", headers=H, json={"full_name": full, "login_id": login, "password": "Demo@1234",
                                          "section_id": sections[sec], "assigned_device_id": ids.get(pc), "role": role})
print("Demo data created. Demo users' password: Demo@1234 (must be changed at first sign-in)")
