# OFFLINE SHARE – User Manual

OFFLINE SHARE lets office PCs exchange messages and files over the office network without the internet. Open Chrome or Edge and go to the address given by your administrator, e.g. `http://192.168.50.10:5000`.

## Signing in and out

- Enter your **Login ID** and **Password**. On first sign-in you must choose a new password.
- After several wrong passwords the account is locked for a short time.
- The header shows **LAN Only · No Internet**, the server address and **Server Online/Offline** (live connection).
- **Logout** (last item in the sidebar) asks for confirmation. Logging out ends only your session; the server keeps running and messages sent to you are queued until you sign in again.
- Change your password from the profile menu (top right).

## Dashboard

Your totals (sent, received, delivered, pending, failed, data transferred), quick-access cards, a seven-day activity chart (with a *Show table* option), recent transfers, PC status, server health, storage use and latest notifications. Administrators can switch between *All users* and *Only mine*.

## Send Data

1. Choose **Text / Message**, **File / Document** or **Text + File**.
2. Enter a subject and type or paste the message. Use the toolbar for **bold**, *italic*, underline, bullets and numbering; *Clear* empties the message.
3. Attach files by dragging them onto the box or clicking *browse*. Each file shows its size and upload progress; remove any file with the bin icon. Allowed types and size limits are set by the administrator.
4. Choose receivers on the right: search by PC name, user name or IP, filter by section or *Online only*, tick *Select all*, or *Select section*. Each receiver shows Online (signed in, or PC on via agent) or queued.
5. Options: *Notification* (pop-up for the receiver), *Delivery confirmation*, *Read receipt*, priority (Normal/High/Urgent) and an optional expiry.
6. **Send**, or **Save as Draft** to finish later (*Drafts* button).

After sending you see the **Transfer ID** (e.g. `TRF-20261123-A1B2C3`) and a live status for every receiver:

| Status | Meaning |
|---|---|
| Pending | Queued – the receiver is not connected. Delivered automatically when they connect. |
| Sent | Pushed to the receiver's open session, waiting for acknowledgement |
| Delivered | The receiver's PC confirmed it received the transfer |
| Read | The receiver opened it |
| Failed | Expired, or not acknowledged after the retry limit – use *Retry* in Transfer History |

## Receive Data

Folders on the left: All Received, Unread, Read, With Attachment, Text Only, Flagged, Important, Archived, Deleted. Search by sender, PC, subject, file name or Transfer ID.

Click a message to preview it. From the preview you can:

- **Copy Message** – copies the text to this PC's clipboard (rich formatting on HTTPS; plain text otherwise)
- **Copy file** – images and text files are copied to the clipboard; for other documents browsers cannot place the file itself on the Windows clipboard, so use **Download**
- **Download** one file or **Download All** as a ZIP; **Preview** PDFs, images and text files
- **Reply**, **Forward** (attachments included), **Flag**, **Important**, **Archive**, **Delete**

Tick several messages to mark read, flag, archive or delete them together. Items in *Deleted* can be restored or deleted forever (history is kept for audit).

## Transfer History

Tabs: All, Sent, Received, Pending, Failed. Filters: date range, direction, status, file type, PC, user, Transfer ID. Click a Transfer ID for full details – sender, every receiver PC with its own status, delivery and read times, attachments and SHA-256 checksums.

- **Retry** failed transfers (row button or select several)
- **Export Excel**, **Download Records** (CSV), **Print Report**
- **Delete Selected** – hides records from your view (administrators delete them permanently; this is audit-logged)

## File Depository

Shared office folders (Administration, Accounts, Store, Engineering, Technical, Audit Reports, Policies & Orders, Forms & Templates, Circulars, Archive) plus *All Files*, *Shared with Me* and *Recycle Bin*.

- **Upload Files** – choose the folder, an optional description and who may see the files: *All Users*, *Section Only* or *Specific Users*. If a file with the same name exists you can save it as a **new version**, keep both, or skip. You are warned when identical content already exists elsewhere.
- Row actions: preview, download, share (change access), move, copy, rename, file history (details, versions, activity log), delete.
- Deleted files go to the **Recycle Bin** and can be restored; *Delete permanently* erases all versions.
- **Create Folder** adds your own folders.

Only the uploader or an administrator can change or delete a file. Read Only users can view and download but not upload.

## Notifications

The bell shows delivery failures, read receipts and files shared with you. New transfers also pop up in the corner; with HTTPS and your permission, Windows desktop notifications appear when the tab is in the background.

---

# Administrator section

## Connected Devices

Statistics, a searchable device list and a **Network Map** (server → switch → wired PCs and Wi-Fi access point → wireless PCs).

- **Add Device** / **Edit** – PC name, IP, MAC, section, LAN/Wi-Fi, approval
- **Approve** new PCs, **Block/Unblock** (blocking signs out users on that PC at once), **Remove**
- *PC Status* (online via browser or agent) is shown separately from *Browser Session* (someone has OFFLINE SHARE open)
- Unknown PCs that sign in are recorded as **Unknown / Pending**
- **Client agent** shows the server URL and enrolment key for the optional agent
- **Export Excel**, **Print**

## User Management

Add, edit, activate/deactivate, delete, reset password, assign role, section and PC, and adjust page permissions per user. Roles:

| Role | Can do |
|---|---|
| Super Admin | Everything, including security, backup/restore, network and service restart |
| Administrator | Users, devices, transfers, settings (except security/backup) |
| Normal User | Dashboard, Send, Receive, History, File Depository |
| Read Only User | View and receive only – cannot send, upload or modify |

Only a Super Admin can manage Super Admin accounts. Deleting a user keeps all their transfers and audit entries. **Import Excel** (download the template first) and **Export Excel** are available.

## Settings

| Section | Contents |
|---|---|
| A. General | Name, organisation, logo, language, date/time format, theme |
| B. Transfer | Max file size, files per transfer, allowed extensions, delivery/read defaults, automatic retry and attempts |
| C. Storage | Paths, storage and depository quotas, retention for received/sent data and history |
| D. Security | Password policy, login attempts and lockout, session timeout, registered PC restriction, device approval, file whitelist |
| E. Network | Server IP/port/subnet/allowed subnets/HTTPS, heartbeat, Wi-Fi ranges, device discovery, connectivity test |
| F. Notifications | New message/file alerts, failed transfer alerts, desktop notifications |
| G. Backup & Restore | Schedule, manual backup, restore, backup list |
| H. Maintenance | Clear temporary files, integrity check, rebuild search index, optimise, restart service, system logs, audit log |
