# PyInstaller spec for the optional client agent:
#   pyinstaller deploy\windows\offline_share_agent.spec --noconfirm
import os
ROOT = os.path.abspath(os.getcwd())
a = Analysis([os.path.join(ROOT, "agent", "offline_share_agent.py")], pathex=[os.path.join(ROOT, "agent")],
             hiddenimports=["win32timezone", "psutil"], excludes=["tkinter"])
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, a.binaries, a.datas, name="OfflineShareAgent", console=True, upx=False)
