; OFFLINE SHARE - Server installer (NSIS 3). Built by deploy/windows/build_portable.sh (works on macOS/Linux/Windows):
;   makensis -DAPPVER=1.0.0 -DSRC=build/OfflineShare -DOUTFILE=build/installer/OFFLINE_SHARE_Server_Setup.exe OFFLINE_SHARE_Server_Setup.nsi
Unicode true
!include "MUI2.nsh"
!include "x64.nsh"

!ifndef APPVER
  !define APPVER "1.0.0"
!endif
!define APPNAME "OFFLINE SHARE"
!define UNKEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\OfflineShare"

Name "${APPNAME} ${APPVER}"
OutFile "${OUTFILE}"
InstallDir "$PROGRAMFILES64\OfflineShare"
InstallDirRegKey HKLM "${UNKEY}" "InstallLocation"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
BrandingText "OFFLINE SHARE - Local Data Transfer System (LAN)"
VIProductVersion "${APPVER}.0"
VIAddVersionKey "ProductName" "${APPNAME}"
VIAddVersionKey "FileDescription" "OFFLINE SHARE Server Setup"
VIAddVersionKey "FileVersion" "${APPVER}"
VIAddVersionKey "LegalCopyright" "OFFLINE SHARE"

!define MUI_ABORTWARNING
!define MUI_WELCOMEPAGE_TITLE "OFFLINE SHARE ${APPVER} - Server Setup"
!define MUI_WELCOMEPAGE_TEXT "This installs the OFFLINE SHARE server on this PC.$\r$\n$\r$\nEverything needed is included - no internet and no Python installation are required.$\r$\n$\r$\nAfter the files are copied, a setup window asks for this PC's IP address, the port (default 5000) and the allowed LAN network. Press Enter to accept the detected values.$\r$\n$\r$\nThe server then starts automatically with Windows."
!define MUI_FINISHPAGE_TITLE "OFFLINE SHARE is installed"
!define MUI_FINISHPAGE_TEXT "Open OFFLINE SHARE from the desktop shortcut or the Start menu.$\r$\n$\r$\nOther PCs on the network open http://<this PC's IP>:<port> in Chrome or Edge.$\r$\n$\r$\nThe initial administrator password was shown in the setup window and is saved in C:\ProgramData\OfflineShare\INITIAL_ADMIN_PASSWORD.txt."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "OFFLINE SHARE requires 64-bit Windows 10/11 or Windows Server 2016+."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

Section "OFFLINE SHARE Server" SecMain
  SectionIn RO
  ; upgrade in place: stop a running server first
  nsExec::Exec 'powershell -NoProfile -Command "Stop-ScheduledTask -TaskName OfflineShare -ErrorAction SilentlyContinue"'
  Sleep 1500
  SetOutPath "$INSTDIR"
  File /r "${SRC}\*.*"
  WriteUninstaller "$INSTDIR\Uninstall OFFLINE SHARE.exe"

  WriteRegStr HKLM "${UNKEY}" "DisplayName" "${APPNAME} Server"
  WriteRegStr HKLM "${UNKEY}" "DisplayVersion" "${APPVER}"
  WriteRegStr HKLM "${UNKEY}" "Publisher" "OFFLINE SHARE"
  WriteRegStr HKLM "${UNKEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNKEY}" "UninstallString" '"$INSTDIR\Uninstall OFFLINE SHARE.exe"'
  WriteRegDWORD HKLM "${UNKEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNKEY}" "NoRepair" 1

  SetShellVarContext all
  CreateDirectory "$SMPROGRAMS\OFFLINE SHARE"
  CreateShortcut "$SMPROGRAMS\OFFLINE SHARE\Start Server.lnk" "$INSTDIR\Start_Server.bat"
  CreateShortcut "$SMPROGRAMS\OFFLINE SHARE\Stop Server.lnk" "$INSTDIR\Stop_Server.bat"
  CreateShortcut "$SMPROGRAMS\OFFLINE SHARE\Backup Now.lnk" "$INSTDIR\Backup.bat"
  CreateShortcut "$SMPROGRAMS\OFFLINE SHARE\Reset Admin Password.lnk" "$INSTDIR\Reset_Admin_Password.bat"
  CreateShortcut "$SMPROGRAMS\OFFLINE SHARE\Re-run Network Setup.lnk" "$INSTDIR\Install.bat"
  CreateShortcut "$SMPROGRAMS\OFFLINE SHARE\Documentation.lnk" "$INSTDIR\docs"
  CreateShortcut "$SMPROGRAMS\OFFLINE SHARE\Uninstall OFFLINE SHARE.lnk" "$INSTDIR\Uninstall OFFLINE SHARE.exe"

  ; interactive network setup in a console window (IP / port / subnet, firewall, startup task, health check)
  DetailPrint "Running network setup..."
  ExecWait '"$SYSDIR\cmd.exe" /c ""$INSTDIR\Install.bat""' $0
  ${If} $0 != 0
    MessageBox MB_ICONEXCLAMATION "Network setup did not finish (code $0).$\r$\nYou can run it again from Start menu > OFFLINE SHARE > Re-run Network Setup."
  ${EndIf}
  WriteINIStr "$INSTDIR\Open OFFLINE SHARE.url" "InternetShortcut" "URL" "http://127.0.0.1:5000/"
  IfFileExists "$DESKTOP\OFFLINE SHARE.url" +2 0
    CopyFiles /SILENT "$INSTDIR\Open OFFLINE SHARE.url" "$DESKTOP\OFFLINE SHARE.url"
  CreateShortcut "$SMPROGRAMS\OFFLINE SHARE\Open OFFLINE SHARE.lnk" "$DESKTOP\OFFLINE SHARE.url"
SectionEnd

Section "Uninstall"
  SetRegView 64
  SetShellVarContext all
  ; removes startup task + firewall rule; the data in C:\ProgramData\OfflineShare is kept
  ExecWait '"$SYSDIR\cmd.exe" /c ""$INSTDIR\Uninstall.bat" /keep /nopause"'
  RMDir /r "$SMPROGRAMS\OFFLINE SHARE"
  Delete "$DESKTOP\OFFLINE SHARE.url"
  RMDir /r "$INSTDIR\python"
  RMDir /r "$INSTDIR\backend"
  RMDir /r "$INSTDIR\frontend"
  RMDir /r "$INSTDIR\docs"
  Delete "$INSTDIR\*.*"
  RMDir "$INSTDIR"
  DeleteRegKey HKLM "${UNKEY}"
  MessageBox MB_ICONINFORMATION "OFFLINE SHARE was removed.$\r$\nYour data (database, files, backups) is kept in C:\ProgramData\OfflineShare.$\r$\nDelete that folder manually if you no longer need it."
SectionEnd
