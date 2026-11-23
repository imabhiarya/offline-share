# OFFLINE SHARE – Testing Report

Date: 23/11/2026 · Version 1.0.0 · Test environment: macOS development machine, Python 3.12, Chrome (headless, via Playwright). **The Windows-specific parts (service, installers, firewall) were not executed in this environment** – see section 5.

## 1. Automated backend tests – `backend/tests/test_api.py`

`pytest -q backend/tests` → **30 passed**

| Area | What is verified |
|---|---|
| Health | `/api/health` and `/health` page work without sign-in |
| LAN restriction | A request from `10.20.30.40` (outside `192.168.50.0/24`) gets HTTP 403 |
| Authentication | Wrong password ×5 locks the account (HTTP 423); logout ends the session; unauthenticated requests get 401 |
| CSRF | Mutating request without `X-CSRF-Token` is refused (403) |
| Password storage | All stored hashes are `scrypt$…`; password policy rejects weak passwords |
| RBAC | Read Only user is refused Users/Devices/Settings and sending; Admin cannot modify a Super Admin or security settings |
| Delivery lifecycle | Send → recipient row `sent` (never `delivered`) → WebSocket ack → `delivered` → open → `read`; read-receipt notification created |
| Offline queue | Transfer to an offline user stays `pending`; on WebSocket connect it is pushed; inbox fetch acknowledges → `delivered` |
| Files in transfers | Upload, extension whitelist (`.exe` → 415), size limit (413), download integrity, ZIP download, non-recipient gets 404 |
| HTML safety | `<script>` removed from messages; allowed formatting kept |
| Inbox | Search (FTS + Transfer ID), flag, archive, delete, category counts |
| Expiry & retry | Expired transfer → `failed`; manual retry → `pending` |
| History | Sent tab, file type/user filters, per-recipient detail, Excel export |
| Drafts | Create, list, update, delete |
| Devices | Unknown device detection (pending, Wi-Fi by IP range), block ends sessions and refuses sign-in, registered-PC restriction, duplicate IP rejected, agent register + heartbeat, network map, Excel export |
| Users | Create/edit with permission override, reset password, deactivate (sign-in refused), soft delete keeps history snapshot, cannot delete self, Excel import (1 created, 1 row error reported) and export |
| Depository | System folders, upload, duplicate warning (409), new version, download specific version, rename, copy, move clash, search, recycle/restore, permanent delete, folder create/delete, specific-user access (shared user can read, others 404, cannot delete) |
| Dashboard | Values come from the database (sent count, 7-day activity) |
| Settings | Validation, extension normalisation, unknown key rejected |
| Maintenance | Integrity check, rebuild index, clear temp, optimise, audit log, network test |
| Backup/restore | Backup with files; data added afterwards disappears after restore |

## 2. Browser end-to-end – `backend/tests/ui_e2e.py`

Real server + built frontend + Chrome, two separate browser sessions (admin and a receiver). **18 / 18 passed** on a fresh database:

admin sign-in and live connection · all 8 pages render · network map · receiver forced password change · compose with bold text + file + High priority + receiver search · **Delivered appears only after the receiver's browser acknowledges** · receiver pop-up, preview, formatted text, attachment, *Copy Message* · sender sees **Read** · history detail with per-PC status · depository upload · manual backup · integrity check · logout confirmation.

Defects found and fixed during this testing:

1. Clicking inside the message editor moved focus to the Bold button (form label wrapped several controls) – users could not type a message. Fixed with a non-label field group; also applied to Priority, Logo, Extensions and Access fields.
2. Field hints were part of the input's accessible name. Moved outside the label.
3. The forced password-change dialog showed a close button that did nothing. Removed for the forced case.
4. Sign-ins on the server itself were recorded as an "unknown device". Loopback is now excluded.
5. In-app service restart could wait on idle keep-alive connections; a 5-second graceful-shutdown limit was added. Restart verified (stopped → started in 13 ms).

The script is not re-runnable against the same database (it changes a demo user's password); reset the demo data first.

## 3. Load and performance – `backend/tests/load_test.py`

| Scenario | Result |
|---|---|
| 50 PCs signed in with open WebSockets | Server RSS 129 MB |
| One transfer to all 50 recipients | All received in **0.03 s**; all acknowledged **Delivered in 0.53 s** |
| 10 concurrent 50 MB uploads (500 MB) | 1.0 s on loopback; **peak server RSS 172 MB** (files streamed to disk, not held in memory) |
| 50 MB streamed download | 0.12 s, byte count verified |
| Errors in server log | 0 |

Loopback figures show server overhead only; on a real network, throughput is limited by the LAN (≈ 110 MB/s on gigabit, less on Wi-Fi).

## 4. Other verifications

- **HTTPS**: `make-certs` creates the internal CA and server certificate; TLS verified against the root CA; session cookies are `Secure; HttpOnly; SameSite=Strict`.
- **Client agent** (run mode): registers with the enrolment key, appears as *pending*, heartbeat sets PC Online with Browser Session = None.
- **PyInstaller spec**: built on macOS from `deploy/windows/offline_share_server.spec`; the frozen binary initialised the database, served the bundled frontend and ran a CLI backup. (The Windows build uses the same spec.)
- **Frontend**: `tsc` strict type-check and production build pass; no runtime console errors besides the expected 401 from the session check on the sign-in page.

## 5. Not yet tested – to be done on Windows before go-live

| Item | Why not tested here | How to test |
|---|---|---|
| Building the `.exe` installers | Needs Windows + Inno Setup | `deploy\windows\build_windows.bat` |
| Windows Service install / automatic start at boot / recovery | Needs Windows (pywin32) | Install, reboot, check `services.msc`; kill the process and confirm Windows restarts it |
| Firewall rule | Needs Windows | `wf.msc`; connect from a PC outside the subnet |
| Agent as a Windows service, Wi-Fi adapter detection | Needs Windows client | Install the agent on a laptop on Wi-Fi |
| Installing the root CA on clients, clipboard/desktop notifications over HTTPS in Edge and Chrome | Needs Windows clients | Follow the Network Guide §5 |
| 20–50 real PCs on LAN + Wi-Fi | Simulated with 50 connections on one machine | Pilot with one section first |

Recommended acceptance test: install on the server, connect two wired and one Wi-Fi PC, run the scenarios in section 2 manually, restore last night's backup onto a spare PC.
