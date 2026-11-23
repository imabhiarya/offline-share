; Inno Setup 6 script -> build\installer\OFFLINE_SHARE_Client_Agent_Setup.exe  (OPTIONAL, per client PC)
#define Root "..\.."

[Setup]
AppId={{9A4E2D11-3B7C-4C8E-A0F2-5D6E7F8091AB}
AppName=OFFLINE SHARE Client Agent
AppVersion=1.0.0
DefaultDirName={autopf}\OfflineShareAgent
OutputDir={#Root}\build\installer
OutputBaseFilename=OFFLINE_SHARE_Client_Agent_Setup
Compression=lzma2
SolidCompression=yes
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
WizardStyle=modern
DisableProgramGroupPage=yes

[Files]
Source: "{#Root}\build\dist\OfflineShareAgent.exe"; DestDir: "{app}"; Flags: ignoreversion

[Run]
Filename: "{app}\OfflineShareAgent.exe"; Parameters: "install --server {code:GetServer} --key {code:GetKey}"; Flags: runhidden waituntilterminated; StatusMsg: "Registering this PC with the server..."

[UninstallRun]
Filename: "{app}\OfflineShareAgent.exe"; Parameters: "remove"; Flags: runhidden; RunOnceId: "RemoveAgent"

[Code]
var P: TInputQueryWizardPage;
procedure InitializeWizard;
begin
  P := CreateInputQueryPage(wpSelectDir, 'Server connection', 'Connect this PC to the OFFLINE SHARE server',
    'The administrator can find the server URL and enrolment key under Connected Devices > Client agent. ' +
    'Silent install: OFFLINE_SHARE_Client_Agent_Setup.exe /VERYSILENT /SERVER=http://192.168.50.10:5000 /KEY=xxxx');
  P.Add('Server URL:', False);
  P.Add('Enrolment key:', False);
  P.Values[0] := ExpandConstant('{param:SERVER|http://192.168.50.10:5000}');
  P.Values[1] := ExpandConstant('{param:KEY|}');
end;
function GetServer(Param: String): String; begin Result := Trim(P.Values[0]); end;
function GetKey(Param: String): String; begin Result := Trim(P.Values[1]); end;
