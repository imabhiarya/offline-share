# OFFLINE SHARE – Backup and Restore

## What a backup contains

Each backup is one ZIP file:

| Entry | Contents |
|---|---|
| `database/offline_share.db` | Consistent snapshot taken with SQLite's online backup API (safe while users are working) |
| `storage/…` | All transfer attachments and depository files, including old versions (optional) |
| `config.json` | Server IP, port, subnets, HTTPS settings |
| `manifest.json` | Version, date, type, file count |

Backups are written to `C:\ProgramData\OfflineShare\backups` unless `backup_dir` is set in `config.json`. Copy them regularly to an external disk kept in a different room.

## Automatic backups

Settings → **G. Backup & Restore** (Super Admin):

- Automatic backup on/off, **daily** or **weekly** (choose the day), time of day (default 20:00)
- Include stored files (on) or database only
- Keep the last *N* scheduled backups (older scheduled backups are removed; manual ones are never removed automatically)

If the server was off at the scheduled time, the backup runs shortly after the service next starts.

## Manual backup

- Web: Settings → G → **Manual backup** (tick *with files* if required) → *Download* to save a copy on another PC.
- Server: `Backup.bat` (default folder) or `Backup.bat D:\OfflineShareBackups` or `Backup.bat D:\OfflineShareBackups --no-files`.

## Restore

A restore replaces **all** current data. Before restoring, OFFLINE SHARE automatically takes a database-only *pre-restore* safety backup.

- Web (Super Admin): Settings → G → choose a backup → **Restore**, or **Restore from file** to upload a ZIP. The database is restored live; the page reloads and users may need to sign in again.
- Server: `Restore.bat "D:\OfflineShareBackups\offline_share_manual_20261123_200000.zip"` (stops the service, restores, starts it again).

The restore validates the archive (manifest present, no unsafe paths) and runs an SQLite integrity check on the snapshot before applying it. An older backup is migrated to the current schema automatically.

## Disaster recovery (new server PC)

1. Install OFFLINE SHARE with the same IP/port (Installation Guide).
2. Copy the latest backup ZIP to the new server.
3. Run `Restore.bat <zip>`.
4. If HTTPS was used, also restore `C:\ProgramData\OfflineShare\certs` from your offline copy (otherwise run `Make_Certificates.bat` and re-install the root certificate on clients).

## Verifying backups

Monthly: restore the latest backup on a spare PC and sign in; check Settings → H → *Database integrity check* reports **OK** with no missing files.
