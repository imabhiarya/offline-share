# OFFLINE SHARE – Installation Guide

Local Data Transfer System (LAN) · Version 1.0.0

This guide installs OFFLINE SHARE on one dedicated **Windows Server PC** and connects 20–50 **client PCs** that use Chrome or Microsoft Edge. No internet connection is needed at any point after the installer has been copied to the server.

---

## 1. Requirements

| Item | Server PC | Client PCs |
|---|---|---|
| Operating system | Windows 10/11 (64-bit) or Windows Server 2019/2022 | Windows 10/11 |
| CPU / RAM | 4 cores, 8 GB RAM recommended (tested: ~170 MB RAM with 50 PCs connected) | any |
| Disk | SSD; size for your files + backups (e.g. 500 GB) | – |
| Network | Wired LAN, **static IP** (default `192.168.50.10`) | LAN or Wi-Fi in `192.168.50.0/24` |
| Software | Nothing else – the installer contains everything | Chrome or Edge (current version) |

Keep the database and stored files on the server's **local disk**. Do not place the data folder on a network share.

---

## 2. Set a static IP on the server

1. Open **Settings → Network & Internet → Ethernet → (your adapter) → IP assignment → Edit**.
2. Choose **Manual**, enable **IPv4**:
    - IP address: `192.168.50.10`
    - Subnet mask: `255.255.255.0` (prefix length 24)
    - Gateway: `192.168.50.1`
    - Preferred DNS: `192.168.50.1` (or leave blank)
3. Save, then check with `ipconfig` in a Command Prompt.

Alternatively, reserve `192.168.50.10` for the server's MAC address in the router's DHCP settings. See the *Network Configuration Guide* for the full network plan.

---

## 3. Install the server (recommended: Setup EXE)

1. Copy `OFFLINE_SHARE_Server_Setup.exe` to the server (USB drive).
2. Right-click → **Run as administrator**.
3. On the **Network configuration** page enter the server IP, port (default `5000`) and the allowed subnet (`192.168.50.0/24`).
4. Finish. The installer automatically:
    - installs the application to `C:\Program Files\OfflineShare`
    - creates the data folders in `C:\ProgramData\OfflineShare` (`db`, `storage`, `backups`, `logs`, `certs`)
    - initialises the SQLite database (WAL mode) and runs migrations
    - creates the Windows Firewall rule allowing the port **only from the LAN subnet**
    - installs the **OfflineShare** Windows Service (automatic, delayed start; restarts itself on failure)
    - starts the service and opens the initial administrator password

### Manual installation (alternative)

If you were given the `OfflineShare` folder instead of the Setup EXE, copy it to `C:\Program Files\OfflineShare` and run **`Install.bat` as administrator**. It performs the same six steps and finishes with a health check.

### Data locations

| Path | Contents |
|---|---|
| `C:\ProgramData\OfflineShare\config.json` | IP, port, subnet, allowed subnets, HTTPS files |
| `C:\ProgramData\OfflineShare\db\offline_share.db` | SQLite database (+ `-wal`, `-shm` files) |
| `C:\ProgramData\OfflineShare\storage\` | Transfer attachments and depository files (random names) |
| `C:\ProgramData\OfflineShare\backups\` | Backup ZIP files |
| `C:\ProgramData\OfflineShare\logs\offline_share.log` | Rotating log (10 × 10 MB) |

---

## 4. Administrator credentials setup

On first start the server creates one **Super Admin** account:

- Login ID: `admin`
- Password: random, written to `C:\ProgramData\OfflineShare\INITIAL_ADMIN_PASSWORD.txt`

Sign in at `http://192.168.50.10:5000`, set a new password (you are forced to), then **delete the text file**.

Other useful commands (Command Prompt as administrator, in `C:\Program Files\OfflineShare`):

```bat
OfflineShare.exe create-admin itadmin --name "IT Administrator"   :: prompts for a password
OfflineShare.exe reset-password admin                              :: prints a temporary password
```

---

## 5. First configuration in the web application

1. **Settings → A. General**: organisation name, logo, date/time format.
2. **Settings → B. Transfer**: maximum file size, files per transfer, allowed extensions.
3. **Connected Devices → Add Device**: register each PC (name, IP, section, LAN/Wi-Fi). Give client PCs **DHCP reservations** so their IPs stay fixed – devices are recognised by IP.
4. **User Management → Add User / Import Excel**: create accounts, assign section, PC and role. New users must change their password at first sign-in.
5. **Settings → G. Backup & Restore**: confirm the daily backup time.
6. Optional: **Settings → D. Security → Registered PC restriction** to allow sign-in only from approved PCs.

---

## 6. Client PCs

No installation is required.

1. Open Chrome or Edge.
2. Go to `http://192.168.50.10:5000` (or `https://…` once HTTPS is enabled).
3. Sign in with the credentials from the administrator.
4. Optional: bookmark the page and allow notifications when asked.

### Optional client agent

`OFFLINE_SHARE_Client_Agent_Setup.exe` installs a small Windows service that reports the PC as online even when no browser is open. On each PC: run it as administrator and enter the server URL and the enrolment key shown in **Connected Devices → Client agent**. Silent deployment:

```bat
OFFLINE_SHARE_Client_Agent_Setup.exe /VERYSILENT /SERVER=http://192.168.50.10:5000 /KEY=<enrolment-key>
```

Approve the PC afterwards in Connected Devices.

---

## 7. HTTPS (recommended)

HTTPS encrypts traffic and allows the browser's secure clipboard API and desktop notifications on client PCs.

1. On the server run **`Make_Certificates.bat`** as administrator. It creates an internal root CA and a server certificate for the server IP, enables HTTPS and restarts the service.
2. Copy `C:\ProgramData\OfflineShare\certs\OfflineShare-RootCA.cer` and `client\Install_Client_Certificate.bat` to each client PC (or deploy the certificate with Group Policy: *Computer Configuration → Windows Settings → Security Settings → Public Key Policies → Trusted Root Certification Authorities*).
3. Run `Install_Client_Certificate.bat` as administrator on each client, restart the browser, and use `https://192.168.50.10:5000`.

Never copy `rootCA.key` off the server.

---

## 8. Service control

| Action | How |
|---|---|
| Start / stop | `Start_Server.bat` / `Stop_Server.bat` (as administrator) or `services.msc` → *OFFLINE SHARE* |
| Restart | Settings → H. Maintenance → Restart service (Super Admin) |
| Health | `http://192.168.50.10:5000/health` (page, auto-refreshes) or `/api/health` (JSON) |
| Logs | Settings → H. Maintenance → System logs, or the log file |
| Uninstall | Control Panel → Programs, or `Uninstall.bat` (data is kept; `Uninstall.bat /purge` deletes it) |

The service starts automatically with Windows (delayed start) and Windows restarts it if it stops unexpectedly.

---

## 9. Building the installers from source

On a Windows build PC with Python 3.12 (x64), Node.js 20+ and Inno Setup 6, run from the repository root:

```bat
deploy\windows\build_windows.bat
```

This builds the frontend, runs the backend tests, packages `OfflineShare.exe` and `OfflineShareAgent.exe` with PyInstaller, and produces `build\installer\OFFLINE_SHARE_Server_Setup.exe` and `build\installer\OFFLINE_SHARE_Client_Agent_Setup.exe`. Copy the installers to the offline network by USB.

---

## 10. Troubleshooting

| Symptom | Check |
|---|---|
| Client cannot open the page | `ping 192.168.50.10`; firewall rule exists (`wf.msc`); client IP inside the allowed subnet; Settings → E. Network → *Run test* |
| "Access denied: this server only accepts connections from the office LAN" | The client's subnet is not in *Allowed subnets* |
| "This PC is blocked" / "only approved PCs" | Approve the PC in Connected Devices |
| Account locked | Wait for the lockout period or *Activate* the user in User Management |
| Copy Message copies plain text only | Enable HTTPS (secure context) |
| Port already in use | Change the port in Settings → E. Network (or `OfflineShare.exe configure --port 5050`), update the firewall rule, restart |
