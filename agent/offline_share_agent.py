"""OFFLINE SHARE – optional Windows client agent.

Reports this PC's presence to the OFFLINE SHARE server every heartbeat interval so the
Connected Devices page shows the PC as online even when no browser is open. It transfers
no files, reads no user data and only talks to the configured LAN server.

Usage (run as Administrator):
  OfflineShareAgent.exe install --server http://192.168.50.10:5000 --key <enrolment-key>
  OfflineShareAgent.exe remove | start | stop | status | run
"""
from __future__ import annotations

import argparse
import json
import logging
import logging.handlers
import os
import platform
import socket
import ssl
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from pathlib import Path
from urllib.parse import urlparse

VERSION = "1.0.0"
SERVICE_NAME = "OfflineShareAgent"
HOME = Path(os.environ.get("PROGRAMDATA", str(Path.home()))) / "OfflineShareAgent"
CONFIG = HOME / "agent.json"
log = logging.getLogger("offline_share_agent")


def setup_logging() -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    h = logging.handlers.RotatingFileHandler(HOME / "agent.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    h.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.addHandler(h)
    log.setLevel(logging.INFO)


def load() -> dict:
    return json.loads(CONFIG.read_text(encoding="utf-8")) if CONFIG.exists() else {}


def save(cfg: dict) -> None:
    HOME.mkdir(parents=True, exist_ok=True)
    CONFIG.write_text(json.dumps(cfg, indent=2), encoding="utf-8")


def _ssl_ctx(cfg: dict):
    if not cfg.get("server", "").startswith("https"):
        return None
    ctx = ssl.create_default_context()
    ca = cfg.get("ca_file")
    if ca and Path(ca).exists():
        ctx.load_verify_locations(ca)
    return ctx


def post(cfg: dict, path: str, body: dict, token: str = "") -> dict:
    req = urllib.request.Request(cfg["server"].rstrip("/") + path, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "User-Agent": f"OfflineShareAgent/{VERSION}",
                                          **({"X-Agent-Token": token} if token else {})})
    with urllib.request.urlopen(req, timeout=10, context=_ssl_ctx(cfg)) as r:
        return json.loads(r.read().decode())


def local_ip_for(server: str) -> str:
    host = urlparse(server).hostname or "127.0.0.1"
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect((host, 9))  # no packet is sent for UDP connect
        return s.getsockname()[0]
    finally:
        s.close()


def connection_type(server: str) -> str:
    """'wifi' if the interface used to reach the server is wireless, else 'lan'."""
    try:
        import psutil
        ip = local_ip_for(server)
        for name, addrs in psutil.net_if_addrs().items():
            if any(a.address == ip for a in addrs):
                n = name.lower()
                return "wifi" if any(k in n for k in ("wi-fi", "wifi", "wireless", "wlan", "802.11")) else "lan"
    except Exception:
        pass
    return ""


def mac_address() -> str:
    m = uuid.getnode()
    return ":".join(f"{(m >> s) & 0xff:02X}" for s in range(40, -1, -8))


def register(cfg: dict) -> dict:
    res = post(cfg, "/api/agent/register", {
        "enrolment_key": cfg["key"], "pc_name": platform.node(), "mac_address": mac_address(),
        "os_info": f"{platform.system()} {platform.release()} ({platform.version()})"[:120],
        "agent_version": VERSION, "connection_type": connection_type(cfg["server"])})
    cfg["token"], cfg["device_uid"] = res["token"], res["device_uid"]
    cfg["interval"] = int(res.get("heartbeat_interval") or 30)
    save(cfg)
    log.info("Registered with %s as %s (status %s)", cfg["server"], platform.node(), res.get("status"))
    return cfg


def heartbeat_loop(stop: threading.Event) -> None:
    cfg = load()
    if not cfg.get("server") or not cfg.get("key"):
        log.error("Agent not configured. Run: OfflineShareAgent.exe install --server URL --key KEY")
        return
    backoff = 5
    while not stop.is_set():
        try:
            if not cfg.get("token"):
                cfg = register(cfg)
            res = post(cfg, "/api/agent/heartbeat", {
                "connection_type": connection_type(cfg["server"]), "agent_version": VERSION,
                "logged_in_user": os.environ.get("USERNAME", ""),
                "os_info": f"{platform.system()} {platform.release()}"}, cfg["token"])
            cfg["interval"] = int(res.get("heartbeat_interval") or cfg.get("interval") or 30)
            backoff = 5
            stop.wait(cfg["interval"])
        except urllib.error.HTTPError as e:
            if e.code == 401:
                log.warning("Server no longer recognises this agent; re-registering")
                cfg.pop("token", None)
            elif e.code == 403:
                log.warning("This PC is blocked or the enrolment key is wrong (HTTP 403)")
                stop.wait(300)
                continue
            else:
                log.warning("Heartbeat failed: HTTP %s", e.code)
            stop.wait(backoff)
        except Exception as e:  # server down / network unplugged
            log.info("Server unreachable (%s); retrying in %ss", e, backoff)
            stop.wait(backoff)
            backoff = min(backoff * 2, 120)


# --------------------------------------------------------------------------- Windows service
if sys.platform == "win32":
    import servicemanager  # type: ignore
    import win32event  # type: ignore
    import win32service  # type: ignore
    import win32serviceutil  # type: ignore

    class AgentService(win32serviceutil.ServiceFramework):
        _svc_name_ = SERVICE_NAME
        _svc_display_name_ = "OFFLINE SHARE Client Agent"
        _svc_description_ = "Reports PC presence to the OFFLINE SHARE LAN server (no internet required)."

        def __init__(self, args):  # noqa: ANN001
            super().__init__(args)
            self.stop = threading.Event()

        def SvcStop(self):  # noqa: N802
            self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
            self.stop.set()

        def SvcDoRun(self):  # noqa: N802
            setup_logging()
            log.info("Agent service started (v%s)", VERSION)
            heartbeat_loop(self.stop)


def main() -> int:
    if sys.argv[1:2] == ["service-run"] and sys.platform == "win32":
        servicemanager.Initialize()
        servicemanager.PrepareToHostSingle(AgentService)
        servicemanager.StartServiceCtrlDispatcher()
        return 0
    ap = argparse.ArgumentParser(prog="OfflineShareAgent")
    ap.add_argument("action", choices=["install", "remove", "start", "stop", "status", "run"])
    ap.add_argument("--server")
    ap.add_argument("--key")
    ap.add_argument("--ca-file", help="Root CA certificate when the server uses HTTPS")
    a = ap.parse_args()
    setup_logging()
    if a.action == "run":
        logging.getLogger().addHandler(logging.StreamHandler())
        try:
            heartbeat_loop(threading.Event())
        except KeyboardInterrupt:
            pass
        return 0
    if a.action == "status":
        cfg = load()
        print(json.dumps({k: v for k, v in cfg.items() if k not in ("token", "key")}, indent=2))
        return 0
    if sys.platform != "win32":
        print("Service actions are only available on Windows; use 'run' to test.")
        return 1
    import subprocess
    if a.action == "install":
        if not a.server or not a.key:
            print("--server and --key are required")
            return 1
        cfg = {"server": a.server.rstrip("/"), "key": a.key}
        if a.ca_file:
            cfg["ca_file"] = a.ca_file
        save(cfg)
        try:
            register(cfg)
            print("Registered with the server. Ask the administrator to approve this PC.")
        except Exception as e:
            print(f"Warning: could not reach the server now ({e}). The agent will keep retrying.")
        frozen = getattr(sys, "frozen", False)
        win32serviceutil.InstallService(
            pythonClassString=None if frozen else f"{__name__}.AgentService", serviceName=SERVICE_NAME,
            displayName=AgentService._svc_display_name_, description=AgentService._svc_description_,
            startType=win32service.SERVICE_AUTO_START, exeName=sys.executable if frozen else None,
            exeArgs="service-run" if frozen else None)
        subprocess.call(["sc", "failure", SERVICE_NAME, "reset=", "86400", "actions=", "restart/10000/restart/30000/restart/60000"])
        win32serviceutil.StartService(SERVICE_NAME)
        print("Agent service installed and started.")
    elif a.action == "remove":
        try:
            win32serviceutil.StopService(SERVICE_NAME)
        except Exception:
            pass
        win32serviceutil.RemoveService(SERVICE_NAME)
    elif a.action == "start":
        win32serviceutil.StartService(SERVICE_NAME)
    elif a.action == "stop":
        win32serviceutil.StopService(SERVICE_NAME)
    return 0


if __name__ == "__main__":
    sys.exit(main())
