"""OFFLINE SHARE server command-line entry point (also the PyInstaller entry point).

Usage:
  offline_share serve                     Run the server in the foreground
  offline_share init                      Create data folders and database, print admin setup
  offline_share create-admin LOGIN [--name NAME] [--password PWD]
  offline_share reset-password LOGIN [--password PWD]
  offline_share configure --ip 192.168.50.10 --port 5000 --subnet 192.168.50.0/24 [--https on|off]
  offline_share make-certs [--ip IP]      Create internal CA + server certificate and enable HTTPS
  offline_share backup [--no-files] [--dir DIR]
  offline_share restore FILE [--no-files]
  offline_share check                     Database integrity check
  offline_share service install|remove|start|stop   (Windows only)
"""
from __future__ import annotations

import argparse
import getpass
import os
import secrets
import sys
import threading
from pathlib import Path

# Make "import app" work when frozen or run from another directory
sys.path.insert(0, str(Path(__file__).resolve().parent))


def serve(stop_event: threading.Event | None = None) -> None:
    import uvicorn

    from app import runtime
    from app.config import load_config
    from app.main import app

    while True:
        cfg = load_config()
        kwargs = dict(host=cfg.host, port=cfg.port, log_level="info", proxy_headers=False, ws_ping_interval=20,
                      ws_ping_timeout=30, timeout_keep_alive=30, timeout_graceful_shutdown=5, access_log=False, log_config=None)
        if cfg.https and cfg.ssl_certfile and cfg.ssl_keyfile:
            kwargs.update(ssl_certfile=cfg.ssl_certfile, ssl_keyfile=cfg.ssl_keyfile)
        server = uvicorn.Server(uvicorn.Config(app, **kwargs))
        restart = {"flag": False}

        def do_restart() -> None:
            restart["flag"] = True
            server.should_exit = True

        runtime.set_restart_callback(do_restart)
        if stop_event is not None:
            def watcher() -> None:
                stop_event.wait()
                server.should_exit = True
            threading.Thread(target=watcher, daemon=True).start()
        server.run()
        if not restart["flag"] or (stop_event is not None and stop_event.is_set()):
            break
        # reload configuration (port/IP/HTTPS) on restart
        import importlib
        import app.config as appcfg
        newcfg = appcfg.load_config()
        for k, v in newcfg.to_json().items():
            setattr(appcfg.config, k, v)
        importlib.invalidate_caches()


def _ask_password(given: str | None) -> str:
    if given:
        return given
    while True:
        p1 = getpass.getpass("New password: ")
        p2 = getpass.getpass("Repeat password: ")
        if p1 == p2 and p1:
            return p1
        print("Passwords do not match, try again.")


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    if argv[:1] == ["service-run"] and sys.platform == "win32":
        import windows_service
        windows_service.run_as_service()
        return 0
    ap = argparse.ArgumentParser(prog="offline_share", description="OFFLINE SHARE server")
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("serve")
    sub.add_parser("init")
    sub.add_parser("check")
    ca = sub.add_parser("create-admin")
    ca.add_argument("login")
    ca.add_argument("--name", default="System Administrator")
    ca.add_argument("--password")
    rp = sub.add_parser("reset-password")
    rp.add_argument("login")
    rp.add_argument("--password")
    cf = sub.add_parser("configure")
    cf.add_argument("--ip")
    cf.add_argument("--port", type=int)
    cf.add_argument("--subnet")
    cf.add_argument("--allowed", help="comma separated list of allowed subnets")
    cf.add_argument("--https", choices=["on", "off"])
    cf.add_argument("--data-dir")
    mc = sub.add_parser("make-certs")
    mc.add_argument("--ip")
    mc.add_argument("--org", default="Office")
    bk = sub.add_parser("backup")
    bk.add_argument("--no-files", action="store_true")
    bk.add_argument("--dir")
    rs = sub.add_parser("restore")
    rs.add_argument("file")
    rs.add_argument("--no-files", action="store_true")
    sv = sub.add_parser("service")
    sv.add_argument("action", choices=["install", "remove", "start", "stop", "restart", "debug"])
    args = ap.parse_args(argv)
    cmd = args.cmd or "serve"

    if cmd == "service":
        if sys.platform != "win32":
            print("Windows service management is only available on Windows.")
            return 1
        try:
            import windows_service
        except ImportError:
            print("This package runs OFFLINE SHARE as a Windows startup task (Task Scheduler), not a service.\n"
                  "Use Start_Server.bat / Stop_Server.bat, or re-run Install.bat to register it.")
            return 1
        return windows_service.handle(args.action)

    if cmd == "serve":
        serve()
        return 0

    if cmd == "configure":
        from app.config import load_config, save_config
        cfg = load_config()
        if args.ip:
            cfg.public_ip = args.ip
        if args.port:
            cfg.port = args.port
        if args.subnet:
            cfg.subnet = args.subnet
            if not args.allowed:
                cfg.allowed_subnets = [args.subnet]
        if args.allowed:
            cfg.allowed_subnets = [s.strip() for s in args.allowed.split(",") if s.strip()]
        if args.https:
            cfg.https = args.https == "on"
        if args.data_dir:
            cfg.data_dir = args.data_dir
        save_config(cfg)
        print(f"Saved configuration: {cfg.public_ip}:{cfg.port} subnet {cfg.subnet} allowed {cfg.allowed_subnets} "
              f"https={cfg.https}")
        return 0

    if cmd == "make-certs":
        from app.certs import make_certs
        from app.config import load_config, save_config
        cfg = load_config()
        cfg.ensure_dirs()
        res = make_certs(cfg.home / "certs", args.ip or cfg.public_ip, args.org)
        cfg.ssl_certfile, cfg.ssl_keyfile, cfg.https = res["cert"], res["key"], True
        save_config(cfg)
        print("Certificates created and HTTPS enabled.")
        print(f"  Root CA to install on every client PC: {res['ca_der']}")
        print(f"  Server certificate: {res['cert']}")
        print("Restart the OFFLINE SHARE service to apply.")
        return 0

    from app.migrations import init_database
    init_database()

    if cmd == "init":
        from app.config import config
        note = config.home / "INITIAL_ADMIN_PASSWORD.txt"
        print(f"Data directory : {config.home}")
        print(f"Database       : {config.db_path}")
        if note.exists():
            print(note.read_text(encoding="utf-8"))
        return 0

    if cmd == "check":
        import sqlite3
        from app.config import config
        con = sqlite3.connect(str(config.db_path))
        res = con.execute("PRAGMA integrity_check").fetchall()
        print("Integrity:", ", ".join(r[0] for r in res))
        return 0 if res == [("ok",)] else 2

    from app.database import db_session
    from app.models import Role, User
    from app.security import check_password_policy, hash_password
    from app.services import settings as app_settings

    if cmd == "create-admin":
        pwd = _ask_password(args.password)
        with db_session() as db:
            problems = check_password_policy(pwd, app_settings.get(db, "password_policy") or {})
            if problems:
                print("Password must contain " + ", ".join(problems))
                return 1
            role = db.query(Role).filter_by(code="super_admin").one()
            u = db.query(User).filter_by(login_id=args.login).first()
            if u:
                u.password_hash, u.role_id, u.status, u.is_deleted = hash_password(pwd), role.id, "active", False
                u.locked_until, u.failed_logins, u.must_change_password = None, 0, False
                print(f"Updated existing account '{args.login}' as Super Admin.")
            else:
                db.add(User(full_name=args.name, login_id=args.login, password_hash=hash_password(pwd),
                            role_id=role.id))
                print(f"Created Super Admin '{args.login}'.")
        return 0

    if cmd == "reset-password":
        pwd = args.password or ("Os-" + secrets.token_urlsafe(8) + "9a")
        with db_session() as db:
            u = db.query(User).filter_by(login_id=args.login).first()
            if not u:
                print("User not found")
                return 1
            u.password_hash, u.must_change_password = hash_password(pwd), True
            u.locked_until, u.failed_logins, u.status = None, 0, "active"
        print(f"Password for '{args.login}' reset to: {pwd}  (must be changed at next login)")
        return 0

    if cmd == "backup":
        from app.services.backup import create_backup
        rec = create_backup("manual", include_files=not args.no_files, target_dir=Path(args.dir) if args.dir else None)
        print(f"Backup written: {rec.path} ({rec.size:,} bytes)")
        return 0

    if cmd == "restore":
        from app.services.backup import restore_backup
        res = restore_backup(Path(args.file), restore_files=not args.no_files)
        print(f"Restored. Files restored: {res['restored_files']}. Safety backup: {res['safety_backup']}")
        return 0

    ap.print_help()
    return 1


if __name__ == "__main__":
    os.environ.setdefault("PYTHONUTF8", "1")
    sys.exit(main())
