import os
import shutil
import sys
import tempfile
from pathlib import Path

import pytest

HOME = Path(tempfile.mkdtemp(prefix="offline_share_test_"))
os.environ["OFFLINE_SHARE_HOME"] = str(HOME)
os.environ["OFFLINE_SHARE_ADMIN_PASSWORD"] = "Admin@12345"
os.environ["OFFLINE_SHARE_ALLOWED"] = "192.168.50.0/24"
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402

LAN = ("192.168.50.101", 50000)


class Api:
    """Small helper around TestClient that tracks the CSRF token."""

    def __init__(self, ip: str = "192.168.50.101"):
        self.c = TestClient(app, client=(ip, 50000), base_url="http://192.168.50.10:5000")
        self.csrf = ""

    def __enter__(self):
        self.c.__enter__()
        return self

    def __exit__(self, *a):
        self.c.__exit__(*a)

    def login(self, login_id: str, password: str, expect: int = 200):
        r = self.c.post("/api/auth/login", json={"login_id": login_id, "password": password})
        assert r.status_code == expect, r.text
        if r.status_code == 200:
            self.csrf = r.json()["csrf_token"]
        return r

    def ws(self):
        cookie = "; ".join(f"{k}={v}" for k, v in self.c.cookies.items())
        return self.c.websocket_connect("/ws", headers={"cookie": cookie})

    def _h(self, kw):
        h = kw.pop("headers", {}) or {}
        if self.csrf:
            h["X-CSRF-Token"] = self.csrf
        return h

    def get(self, url, **kw):
        return self.c.get(url, **kw)

    def post(self, url, **kw):
        return self.c.post(url, headers=self._h(kw), **kw)

    def put(self, url, **kw):
        return self.c.put(url, headers=self._h(kw), **kw)

    def patch(self, url, **kw):
        return self.c.patch(url, headers=self._h(kw), **kw)

    def delete(self, url, **kw):
        return self.c.delete(url, headers=self._h(kw), **kw)


@pytest.fixture(scope="session", autouse=True)
def server():
    """Run the application lifespan (DB init, background jobs) once for the whole test session."""
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def admin(server):
    a = Api("192.168.50.100")
    a.login("admin", "Admin@12345")
    yield a


def pytest_sessionfinish(session, exitstatus):
    shutil.rmtree(HOME, ignore_errors=True)
