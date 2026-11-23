; Inno Setup 6 script -> build\installer\OFFLINE_SHARE_Server_Setup.exe
; Build: "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" deploy\windows\OFFLINE_SHARE_Server_Setup.iss
#define AppName "OFFLINE SHARE Server"
#define AppVersion "1.0.0"
#define Root "..\.."

[Setup]
AppId={{6C1C3E9B-8C51-4E5B-9E07-0F5A1D2B7A10}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher=OFFLINE SHARE
DefaultDirName={autopf}\OfflineShare
DefaultGroupName=OFFLINE SHARE
OutputDir={#Root}\build\installer
OutputBaseFilename=OFFLINE_SHARE_Server_Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
WizardStyle=modern
UninstallDisplayName={#AppName}
MinVersion=10.0

[Files]
Source: "{#Root}\build\dist\OfflineShare\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "Install.bat"; DestDir: "{app}"
Source: "Start_Server.bat"; DestDir: "{app}"
Source: "Stop_Server.bat"; DestDir: "{app}"
Source: "Backup.bat"; DestDir: "{app}"
Source: "Restore.bat"; DestDir: "{app}"
Source: "Uninstall.bat"; DestDir: "{app}"
Source: "Make_Certificates.bat"; DestDir: "{app}"
Source: "Install_Client_Certificate.bat"; DestDir: "{app}\client"
Source: "configure_firewall.ps1"; DestDir: "{app}"
Source: "{#Root}\build\dist\OfflineShareAgent.exe"; DestDir: "{app}\client"; Flags: skipifsourcedoesntexist
Source: "{#Root}\docs\*.pdf"; DestDir: "{app}\docs"; Flags: skipifsourcedoesntexist
Source: "{#Root}\docs\*.md"; DestDir: "{app}\docs"

[Icons]
Name: "{group}\Open OFFLINE SHARE"; Filename: "http://127.0.0.1:{code:GetPort}/"
Name: "{group}\Server health"; Filename: "http://127.0.0.1:{code:GetPort}/health"
Name: "{group}\Backup now"; Filename: "{app}\Backup.bat"
Name: "{group}\Documentation"; Filename: "{app}\docs"
Name: "{group}\Uninstall OFFLINE SHARE"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\OfflineShare.exe"; Parameters: "configure --ip {code:GetIP} --port {code:GetPort} --subnet {code:GetSubnet}"; Flags: runhidden waituntilterminated; StatusMsg: "Writing configuration..."
Filename: "{app}\OfflineShare.exe"; Parameters: "init"; Flags: runhidden waituntilterminated; StatusMsg: "Creating database..."
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\configure_firewall.ps1"" -Port {code:GetPort} -Subnet {code:GetSubnet}"; Flags: runhidden waituntilterminated; StatusMsg: "Configuring Windows Firewall..."
Filename: "{app}\OfflineShare.exe"; Parameters: "service install"; Flags: runhidden waituntilterminated; StatusMsg: "Installing Windows Service..."
Filename: "{app}\OfflineShare.exe"; Parameters: "service start"; Flags: runhidden waituntilterminated; StatusMsg: "Starting service..."
Filename: "notepad.exe"; Parameters: "{commonappdata}\OfflineShare\INITIAL_ADMIN_PASSWORD.txt"; Description: "Show the initial administrator password"; Flags: postinstall nowait skipifsilent; Check: AdminFileExists
Filename: "http://127.0.0.1:{code:GetPort}/"; Description: "Open OFFLINE SHARE"; Flags: postinstall shellexec nowait skipifsilent unchecked

[UninstallRun]
Filename: "sc.exe"; Parameters: "stop OfflineShare"; Flags: runhidden; RunOnceId: "StopSvc"
Filename: "{app}\OfflineShare.exe"; Parameters: "service remove"; Flags: runhidden; RunOnceId: "RemoveSvc"
Filename: "powershell.exe"; Parameters: "-NoProfile -Command ""Get-NetFirewallRule -DisplayName 'OFFLINE SHARE*' -ErrorAction SilentlyContinue | Remove-NetFirewallRule"""; Flags: runhidden; RunOnceId: "RemoveFw"

[Code]
var NetPage: TInputQueryWizardPage;

procedure InitializeWizard;
begin
  NetPage := CreateInputQueryPage(wpSelectDir, 'Network configuration',
    'The server must have a static IP address on the office LAN.',
    'Enter the static IP of THIS server PC, the port, and the LAN subnet allowed to connect. ' +
    'Clients will open http://<IP>:<port> in Chrome or Edge.');
  NetPage.Add('Server static IP:', False);
  NetPage.Add('Port:', False);
  NetPage.Add('Allowed LAN subnet (CIDR):', False);
  NetPage.Values[0] := '192.168.50.10';
  NetPage.Values[1] := '5000';
  NetPage.Values[2] := '192.168.50.0/24';
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = NetPage.ID) and ((Trim(NetPage.Values[0]) = '') or (StrToIntDef(NetPage.Values[1], 0) <= 0) or (Pos('/', NetPage.Values[2]) = 0)) then
  begin
    MsgBox('Enter a valid IP, port and subnet (e.g. 192.168.50.0/24).', mbError, MB_OK);
    Result := False;
  end;
end;

function GetIP(Param: String): String; begin Result := Trim(NetPage.Values[0]); end;
function GetPort(Param: String): String; begin Result := Trim(NetPage.Values[1]); end;
function GetSubnet(Param: String): String; begin Result := Trim(NetPage.Values[2]); end;
function AdminFileExists: Boolean; begin Result := FileExists(ExpandConstant('{commonappdata}\OfflineShare\INITIAL_ADMIN_PASSWORD.txt')); end;

procedure CurStepChanged(CurStep: TSetupStep);
var Code: Integer;
begin
  if CurStep = ssInstall then
    Exec('sc.exe', 'stop OfflineShare', '', SW_HIDE, ewWaitUntilTerminated, Code);  { upgrade in place }
end;
