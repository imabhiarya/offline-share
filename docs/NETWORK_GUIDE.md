# OFFLINE SHARE – Network Configuration Guide

## 1. Network plan

| Device | Address | Notes |
|---|---|---|
| Network | `192.168.50.0/24` | Private LAN, **no WAN/internet link required** |
| Router / gateway | `192.168.50.1` | DHCP server for clients |
| Wi-Fi access point | `192.168.50.2` | Bridged into the same LAN (same subnet, no separate NAT) |
| **OFFLINE SHARE server** | `192.168.50.10`, TCP port `5000` | Static IP, wired connection |
| Client DHCP range | `192.168.50.100 – 192.168.50.199` | Use reservations for each PC |
| Subnet mask | `255.255.255.0` | |

```
                 ┌──────────────────────┐
                 │ OFFLINE SHARE Server │ 192.168.50.10:5000
                 └──────────┬───────────┘
                            │ wired
                 ┌──────────┴───────────┐
                 │ LAN Switch / Router  │ 192.168.50.1 (DHCP .100–.199)
                 └───┬──────────────┬───┘
            wired    │              │ wired
     ┌───────────────┴───┐   ┌──────┴──────────────┐
     │ Wired PCs          │   │ Wi-Fi Access Point  │ 192.168.50.2
     │ 192.168.50.100-149 │   └──────┬──────────────┘
     └────────────────────┘          │ wireless
                              ┌──────┴─────────────┐
                              │ Wireless PCs        │
                              │ 192.168.50.150-199  │
                              └────────────────────┘
```

The Connected Devices page labels browser-only PCs as Wi-Fi when their IP falls in **Settings → E. Network → Wi-Fi IP ranges** (default `192.168.50.150-192.168.50.199`). Arrange your DHCP reservations to match, or set the connection type per device. PCs running the client agent report their real adapter type.

## 2. Router and access point settings

1. Disable or unplug any WAN/internet uplink if the network must be fully offline.
2. Set the LAN to `192.168.50.1/24` with DHCP range `.100–.199`.
3. **DHCP reservations**: reserve one IP per client PC (by MAC address). OFFLINE SHARE identifies PCs by IP.
4. Configure the access point in **bridge/AP mode** (not router mode) so wireless PCs get addresses from the same DHCP server and can reach `192.168.50.10` directly.
5. Disable *client/AP isolation* on the Wi-Fi network – it blocks wireless PCs from reaching the server.
6. Use WPA2/WPA3 with a strong passphrase.

## 3. Server firewall

The installer creates an inbound rule equivalent to:

```powershell
New-NetFirewallRule -DisplayName "OFFLINE SHARE (TCP 5000, LAN only)" -Direction Inbound -Action Allow `
  -Protocol TCP -LocalPort 5000 -RemoteAddress 192.168.50.0/24 -Profile Any
```

Re-run `configure_firewall.ps1 -Port <port> -Subnet <cidr>` after changing the port or subnet. In addition, the application itself refuses any request whose source address is outside **Allowed subnets** (Settings → E. Network), and the server's own loopback address.

## 4. Changing IP, port or subnet

Super Admin → **Settings → E. Network → Server address**, then *Save network*, update the firewall rule, and restart the service. Command-line equivalent:

```bat
OfflineShare.exe configure --ip 192.168.50.10 --port 5000 --subnet 192.168.50.0/24 --allowed 192.168.50.0/24
powershell -ExecutionPolicy Bypass -File configure_firewall.ps1 -Port 5000 -Subnet 192.168.50.0/24
sc stop OfflineShare & sc start OfflineShare
```

## 5. HTTPS with an internal certificate

Browsers allow the secure clipboard API and desktop notifications only on HTTPS (or `localhost`). OFFLINE SHARE ships its own small certificate authority so no internet or public CA is needed.

1. Server: `Make_Certificates.bat` (as administrator). Output in `C:\ProgramData\OfflineShare\certs\`:
    - `OfflineShare-RootCA.cer` – **install on clients**
    - `server.crt`, `server.key` – used by the server (key never leaves the server)
    - `rootCA.key` – keep private; back it up offline
2. Each client: copy `OfflineShare-RootCA.cer` and run `Install_Client_Certificate.bat` as administrator, which runs:
    ```bat
    certutil -addstore -f Root OfflineShare-RootCA.cer
    ```
    For many PCs use Group Policy (Trusted Root Certification Authorities).
3. Open `https://192.168.50.10:5000`. The padlock should show without warnings.

The server certificate is valid for 825 days and covers the server IP, `localhost` and the server's host name. Re-run `Make_Certificates.bat` to renew (the root CA is reused, so clients need nothing new).

## 6. Connectivity testing

- **In the application**: Settings → E. Network → *Network connectivity test* runs from the current PC: reachability, subnet authorisation, static IP present on the server, HTTPS status, live channel, and five-ping latency.
- **Health page**: `http://192.168.50.10:5000/health` – status, database, uptime, CPU, memory, disk, live connections.
- **From a client**: `ping 192.168.50.10` and `powershell Test-NetConnection 192.168.50.10 -Port 5000`.

## 7. Presence and heartbeats

- An open browser keeps a WebSocket to the server and pings every *Heartbeat interval* (default 30 s). This drives **Browser Session: Active**.
- The optional client agent posts a heartbeat at the same interval. A PC is **Online** if either source has been seen within three intervals. The two are shown separately so a powered-on PC with no browser open is not confused with an active user.
- Transfers to a user with no open session are **queued** and delivered automatically when they next connect.
