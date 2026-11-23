"""Windows Service wrapper (pywin32). Installed as "OfflineShare", start type Automatic,
with recovery actions so Windows restarts it after a crash."""
from __future__ import annotations

import subprocess
import sys
import threading

import servicemanager  # type: ignore
import win32event  # type: ignore
import win32service  # type: ignore
import win32serviceutil  # type: ignore

SERVICE_NAME = "OfflineShare"


class OfflineShareService(win32serviceutil.ServiceFramework):
    _svc_name_ = SERVICE_NAME
    _svc_display_name_ = "OFFLINE SHARE – Local Data Transfer Server"
    _svc_description_ = "Serves the OFFLINE SHARE LAN data transfer application to office PCs (no internet required)."

    def __init__(self, args):  # noqa: ANN001
        super().__init__(args)
        self.stop_handle = win32event.CreateEvent(None, 0, 0, None)
        self.stop_event = threading.Event()

    def SvcStop(self):  # noqa: N802
        self.ReportServiceStatus(win32service.SERVICE_STOP_PENDING)
        self.stop_event.set()
        win32event.SetEvent(self.stop_handle)

    def SvcDoRun(self):  # noqa: N802
        servicemanager.LogMsg(servicemanager.EVENTLOG_INFORMATION_TYPE, servicemanager.PYS_SERVICE_STARTED,
                              (self._svc_name_, ""))
        from offline_share import serve
        try:
            serve(self.stop_event)
        except Exception as e:  # pragma: no cover
            servicemanager.LogErrorMsg(f"OFFLINE SHARE stopped with error: {e}")
            raise


def handle(action: str) -> int:
    if action == "install":
        exe = sys.executable
        win32serviceutil.InstallService(
            pythonClassString=f"{__name__}.OfflineShareService" if not getattr(sys, "frozen", False) else None,
            serviceName=SERVICE_NAME, displayName=OfflineShareService._svc_display_name_,
            description=OfflineShareService._svc_description_, startType=win32service.SERVICE_AUTO_START,
            exeName=exe if getattr(sys, "frozen", False) else None,
            exeArgs="service-run" if getattr(sys, "frozen", False) else None)
        subprocess.call(["sc", "failure", SERVICE_NAME, "reset=", "86400",
                         "actions=", "restart/5000/restart/10000/restart/30000"])
        subprocess.call(["sc", "config", SERVICE_NAME, "start=", "delayed-auto"])
        print("Service installed (automatic start, restarts on failure).")
        return 0
    if action == "remove":
        win32serviceutil.RemoveService(SERVICE_NAME)
        return 0
    if action == "start":
        win32serviceutil.StartService(SERVICE_NAME)
        return 0
    if action == "stop":
        win32serviceutil.StopService(SERVICE_NAME)
        return 0
    if action == "restart":
        win32serviceutil.RestartService(SERVICE_NAME)
        return 0
    if action == "debug":
        from offline_share import serve
        serve()
        return 0
    return 1


def run_as_service() -> None:
    """Entry used by the frozen EXE when started by the Service Control Manager."""
    servicemanager.Initialize()
    servicemanager.PrepareToHostSingle(OfflineShareService)
    servicemanager.StartServiceCtrlDispatcher()
