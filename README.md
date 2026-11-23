# OFFLINE SHARE – Local Data Transfer System (LAN)

A self-hosted, fully offline web application for exchanging messages and files between 20–50 Windows PCs on an office LAN/Wi-Fi, with a central file depository. One Windows server PC runs the application; client PCs only need Chrome or Edge.

- **Backend**: Python 3.12, FastAPI, SQLAlchemy 2, SQLite (WAL), WebSockets, streaming uploads/downloads
- **Frontend**: React 18, TypeScript, Tailwind CSS, Lucide icons – fonts and all assets bundled, no CDN
- **Windows**: Windows Service (pywin32), PyInstaller, Inno Setup installers, firewall script, optional client agent
- **Security**: scrypt password hashing, server-side sessions, CSRF tokens, RBAC with per-user overrides, LAN-subnet restriction, device approval/blocking, file whitelist, safe storage paths, audit log, optional HTTPS with an internal CA

## Repository layout

```
backend/
  offline_share.py        CLI + entry point (serve, init, configure, create-admin, backup, restore, make-certs, service)
  windows_service.py      Windows Service wrapper
  app/
    main.py               FastAPI app, LAN guard, WebSocket hub endpoint, SPA serving
    models.py             Relational schema (21 tables + FTS5 search tables)
    migrations.py         Versioned migrations + seed data (roles, permissions, sections, folders, admin)
    deps.py, security.py  Sessions, CSRF, RBAC, scrypt hashing
    realtime.py, runtime.py  WebSocket hub; background jobs (delivery retry, backups, retention, presence)
    routers/              auth, dashboard, transfers, inbox, history, devices, users, files, system
    services/             delivery engine, storage, search, backup, settings, excel, devices
  tests/                  test_api.py (pytest), ui_e2e.py (browser), load_test.py
  tools/seed_demo.py      DEMO data only
frontend/                 React app (npm run build -> frontend/dist, bundled into the EXE)
agent/                    Optional Windows client agent
deploy/windows/           PyInstaller specs, Inno Setup scripts, Install/Start/Stop/Backup/Restore/Uninstall .bat, firewall, certificates
docs/                     Installation Guide (MD + PDF), Network Guide, Backup & Restore, User Manual, Testing Report, database_schema.sql
```

## Development

```bash
# backend
cd backend
python3.12 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt
OFFLINE_SHARE_HOME=./data-dev OFFLINE_SHARE_ADMIN_PASSWORD='Admin@12345' .venv/bin/python offline_share.py serve
.venv/bin/python -m pytest -q tests

# frontend (separate terminal) – dev server proxies /api and /ws to port 5000
cd frontend && npm install && npm run dev
npm run build   # production build served by the backend
```

`OFFLINE_SHARE_HOME` sets the data directory (default `C:\ProgramData\OfflineShare` on Windows). `OFFLINE_SHARE_PORT` overrides the port (on macOS port 5000 is taken by AirPlay Receiver – use 5050).

## Building the Windows installers

On Windows with Python 3.12 x64, Node.js 20+ and Inno Setup 6: `deploy\windows\build_windows.bat` → `build\installer\OFFLINE_SHARE_Server_Setup.exe` and `OFFLINE_SHARE_Client_Agent_Setup.exe`. See `docs/INSTALLATION_GUIDE.md`.

## Key design decisions

- **Delivery is acknowledgement-based.** A recipient row moves `pending → sent → delivered → read`. *Delivered* is only set when the receiving browser acknowledges over the WebSocket, fetches its inbox or downloads the file – never because the sender clicked Send. Offline recipients stay queued and receive the transfer when they reconnect; unacknowledged pushes are retried and fail after the configured attempts; expiry fails undelivered transfers.
- **Single server process.** One uvicorn worker holds all WebSocket connections in memory; load-tested with 50 concurrent PCs.
- **Recipients are users; PCs are tracked alongside.** Each user has an assigned PC; transfer rows store name/PC/IP snapshots so history survives user deletion.
- **PC presence vs. browser session** are reported separately (agent heartbeat vs. open WebSocket).
- **Files live on disk under random names**; metadata (original name, SHA-256, versions, permissions) lives in SQLite. Client-supplied paths are never used.
- **Backups** use SQLite's online backup API, so they are consistent while the server runs; restore is applied live.

See `docs/TESTING_REPORT.md` for what has been tested and what still needs verification on Windows.
