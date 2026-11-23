# PyInstaller spec for the OFFLINE SHARE server (run on Windows from the repository root):
#   pyinstaller deploy\windows\offline_share_server.spec --noconfirm
# Produces dist\OfflineShare\OfflineShare.exe (one-folder build: faster start, AV friendly).
import os
from PyInstaller.utils.hooks import collect_submodules

ROOT = os.path.abspath(os.getcwd())
BACKEND = os.path.join(ROOT, "backend")

hidden = (collect_submodules("uvicorn") + collect_submodules("app") +
          ["windows_service", "win32timezone", "sqlalchemy.dialects.sqlite", "multipart", "python_multipart"])

a = Analysis(
    [os.path.join(BACKEND, "offline_share.py")],
    pathex=[BACKEND],
    datas=[(os.path.join(ROOT, "frontend", "dist"), "frontend_dist")],
    hiddenimports=hidden,
    excludes=["tkinter", "pytest", "playwright"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="OfflineShare", console=True,
          icon=os.path.join(ROOT, "deploy", "windows", "offline_share.ico") if os.path.exists(
              os.path.join(ROOT, "deploy", "windows", "offline_share.ico")) else None,
          version=None, uac_admin=False)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="OfflineShare")
