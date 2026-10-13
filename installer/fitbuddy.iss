; FitBuddy Windows installer (Section 38).
; Build with Inno Setup 6 (https://jrsoftware.org/isinfo.php):
;   1. Run build.py first so dist\FitBuddy\FitBuddy.exe exists.
;   2. Open this file in the Inno Setup Compiler (or run ISCC.exe fitbuddy.iss)
;      from installer\build_installer.bat.
; Produces: installer\Output\FitBuddy Setup.exe

#define MyAppName "FitBuddy"
#define MyAppVersion "0.1.0"
#define MyAppPublisher "FitBuddy"
#define MyAppExeName "FitBuddy.exe"

[Setup]
AppId={{6F2B1D2E-6E6F-4C1B-9C10-FITBUDDY0001}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
; No administrator privileges required for normal operation (Section 37).
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=FitBuddy Setup
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"
Name: "startupentry"; Description: "Start FitBuddy automatically when Windows starts"; GroupDescription: "Startup:"; Flags: checkedonce

[Files]
; Pulls in everything PyInstaller produced (--onedir build).
Source: "..\dist\FitBuddy\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Registry]
; Per-user Run-key startup entry, matching app/windows/startup.py's own
; registration mechanism - both write to the same key so the in-app
; "Start with Windows" checkbox and this installer option stay in sync.
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; \
    ValueType: string; ValueName: "FitBuddy"; ValueData: """{app}\{#MyAppExeName}"""; \
    Tasks: startupentry

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch FitBuddy"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Application files only. The user's activity database and logs live under
; %LOCALAPPDATA%\FitBuddy\ (see app/config.py) and are intentionally left
; alone here - see the optional prompt below.
Type: filesandordirs; Name: "{app}"

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
var
  DataDir: string;
  ResultCode: Integer;
begin
  if CurUninstallStep = usPostUninstall then
  begin
    DataDir := ExpandConstant('{localappdata}\FitBuddy');
    if DirExists(DataDir) then
    begin
      if MsgBox('Also delete your FitBuddy activity history and settings ' + #13#10 +
                '(' + DataDir + ')?', mbConfirmation, MB_YESNO) = IDYES then
        DelTree(DataDir, True, True, True);
    end;
  end;
end;
