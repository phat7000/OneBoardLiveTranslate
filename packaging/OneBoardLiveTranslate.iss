; Inno Setup 6.3+; all product values are supplied from branding.py/version.py.
; Per-user installation requires no administrator rights. Runtime data remains
; outside {app} and is intentionally preserved by both upgrade and uninstall.
#ifndef StageDir
  #error StageDir must point at the verified portable distribution
#endif
#ifndef OutputDir
  #error OutputDir is required
#endif

[Setup]
AppId={{44BCB381-3942-4FC7-8D9A-5210F1B743D2}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#CompanyName}
VersionInfoVersion={#WindowsVersion}
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
DefaultDirName={localappdata}\Programs\{#AppIdName}
DefaultGroupName={#AppName}
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
OutputDir={#OutputDir}
OutputBaseFilename={#AppIdName}-Setup-{#AppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
UninstallDisplayIcon={app}\{#AppIdName}.exe
LicenseFile={#StageDir}\LICENSE
CloseApplications=yes
RestartApplications=no
#ifdef IconFile
SetupIconFile={#IconFile}
#endif

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Files]
Source: "{#StageDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppIdName}.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppIdName}.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppIdName}.exe"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent
