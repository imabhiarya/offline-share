"""Load test against a running server: 50 simultaneous PCs, broadcast delivery, concurrent large uploads.

Usage: python tests/load_test.py http://127.0.0.1:5050 Admin@12345 [server-pid]
"""
import asyncio
import json
import os
import sys
import time

import httpx
import websockets

BASE, ADMIN_PWD = sys.argv[1], sys.argv[2]
PID = int(sys.argv[3]) if len(sys.argv) > 3 else None
N = 50
WS = BASE.replace("http", "ws") + "/ws"


def rss_mb():
    if not PID:
        return None
    import psutil
    return round(psutil.Process(PID).memory_info().rss / 1024 / 1024, 1)


async def login(c: httpx.AsyncClient, user, pwd):
    r = await c.post("/api/auth/login", json={"login_id": user, "password": pwd})
    r.raise_for_status()
    return {"X-CSRF-Token": r.json()["csrf_token"]}


async def main():
    admin = httpx.AsyncClient(base_url=BASE, timeout=120)
    h = await login(admin, "admin", ADMIN_PWD)
    # create N users
    t0 = time.perf_counter()
    for i in range(N):
        await admin.post("/api/users", headers=h, json={"full_name": f"Load User {i:02d}", "login_id": f"load{i:02d}",
                                                        "password": "Load@1234", "role": "user"})
    print(f"created {N} users in {time.perf_counter() - t0:.1f}s (scrypt hashing)")

    clients, sockets = [], []
    for i in range(N):
        c = httpx.AsyncClient(base_url=BASE, timeout=60)
        await login(c, f"load{i:02d}", "Load@1234")
        cookie = "; ".join(f"{k}={v}" for k, v in c.cookies.items())
        ws = await websockets.connect(WS, additional_headers={"Cookie": cookie})
        json.loads(await ws.recv())  # hello
        clients.append(c)
        sockets.append(ws)
    print(f"{N} PCs connected over WebSocket; server RSS {rss_mb()} MB")

    users = (await admin.get("/api/users?q=load&page_size=100")).json()["items"]
    ids = [u["id"] for u in users]
    received = 0

    async def listen(ws):
        nonlocal received
        while True:
            m = json.loads(await ws.recv())
            if m["type"] == "transfer.new":
                await ws.send(json.dumps({"type": "ack", "recipient_ids": [m["transfer"]["recipient_id"]]}))
                received += 1
                return

    t0 = time.perf_counter()
    listeners = [asyncio.create_task(listen(ws)) for ws in sockets]
    r = await admin.post("/api/transfers", headers=h, json={"subject": "Broadcast to all PCs", "body_html": "<p>Hello all</p>",
                                                             "recipient_user_ids": ids})
    tid = r.json()["transfer"]["id"]
    await asyncio.wait_for(asyncio.gather(*listeners), 30)
    t_recv = time.perf_counter() - t0
    for _ in range(50):
        st = (await admin.get(f"/api/transfers/{tid}/status")).json()
        if all(x["status"] == "delivered" for x in st["recipients"]):
            break
        await asyncio.sleep(0.1)
    t_all = time.perf_counter() - t0
    print(f"broadcast to {N}: all received in {t_recv:.2f}s; all Delivered (acked) in {t_all:.2f}s -> {st['aggregate']}")

    # concurrent uploads: 10 x 50 MB streamed
    size = 50 * 1024 * 1024
    path = os.path.join(os.environ.get("TMPDIR", "/tmp"), "os_load_50mb.zip")
    with open(path, "wb") as f:
        f.write(os.urandom(1024 * 1024) * 50)
    peak = rss_mb()

    async def up(i):
        nonlocal peak
        c = clients[i]
        hh = {"X-CSRF-Token": c.cookies.get("os_csrf")}
        with open(path, "rb") as f:
            r = await c.post("/api/transfers/uploads", headers=hh, files={"file": (f"big{i}.zip", f, "application/zip")})
        r.raise_for_status()
        return r.json()

    async def sample():
        nonlocal peak
        while True:
            m = rss_mb()
            if m and (peak is None or m > peak):
                peak = m
            await asyncio.sleep(0.2)

    s = asyncio.create_task(sample())
    t0 = time.perf_counter()
    res = await asyncio.gather(*[up(i) for i in range(10)])
    dt = time.perf_counter() - t0
    s.cancel()
    assert all(x["size"] == size for x in res)
    print(f"10 concurrent 50 MB uploads ({500} MB) in {dt:.1f}s = {500 / dt:.0f} MB/s; peak server RSS {peak} MB")

    # streamed download
    t0 = time.perf_counter()
    c = clients[0]
    hh = {"X-CSRF-Token": c.cookies.get("os_csrf")}
    tr = await c.post("/api/transfers", headers=hh, json={"subject": "big", "recipient_user_ids": [ids[1]],
                                                          "attachment_uids": [res[0]["uid"]]})
    tr.raise_for_status()
    inbox = (await clients[1].get("/api/inbox?category=attachments")).json()["items"]
    item = next(i for i in inbox if i["subject"] == "big")
    det = (await clients[1].get(f"/api/inbox/{item['recipient_id']}")).json()
    n = 0
    async with clients[1].stream("GET", f"/api/attachments/{det['attachments'][0]['uid']}") as r:
        async for chunk in r.aiter_bytes():
            n += len(chunk)
    print(f"streamed 50 MB download in {time.perf_counter() - t0:.2f}s ({n == size}); server RSS {rss_mb()} MB")
    os.remove(path)
    for ws in sockets:
        await ws.close()


asyncio.run(main())
