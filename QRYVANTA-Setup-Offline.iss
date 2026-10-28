; QRYVANTA 1.1.0 — Offline Windows installer
; Build the PyInstaller onedir bundle first with build_windows.bat.
; This installer copies the complete local bundle; the target PC does not need Python,
; pip, or an internet connection to run QRYVANTA's offline learning/quiz features.
; Live database connections still require the relevant database service, and Oracle's
; SQL*Plus console requires a compatible SQL*Plus installation.

#define MyAppName "QRYVANTA — Query Intelligence Studio"
#define MyAppVersion "1.1.0"
#define MyAppPublisher "QRYVANTA"
#define MyAppExeName "QRYVANTA.exe"
#define MyAppId "{1AE6BE0B-782C-4D16-BA62-5D58DDEB9FF1}"

[Setup]
AppId={#MyAppId}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\QRYVANTA
DefaultGroupName=QRYVANTA
DisableProgramGroupPage=yes
UninstallDisplayName={#MyAppName}
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile=assets\qryvanta_icon.ico
OutputDir=installer-output
OutputBaseFilename=QRYVANTA-Setup-{#MyAppVersion}-Offline-x64
VersionInfoVersion=1.1.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription=QRYVANTA offline desktop installer
VersionInfoProductName={#MyAppName}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64
CloseApplications=no
RestartApplications=no
DisableWelcomePage=no
Uninstallable=yes

[Tasks]
Name: "desktopicon"; Description: "Create a desktop shortcut"; GroupDescription: "Additional shortcuts:"; Flags: unchecked

[Dirs]
Name: "{app}\docs"

[Files]
; Ship the full PyInstaller onedir bundle. Never include environment files, secrets, logs,
; local databases, or temporary files even if one was accidentally copied into dist.
Source: "dist\QRYVANTA\*"; DestDir: "{app}"; Excludes: ".env,*.env,.env.*,*.env.*,*.pem,*.key,*.p12,*.pfx,*.sqlite,*.sqlite3,*.db,*.log,*.tmp,*.bak"; Flags: ignoreversion recursesubdirs createallsubdirs
; Include the source-distributed offline study documents for convenient access after install.
Source: "docs\*"; DestDir: "{app}\docs"; Excludes: ".env,*.env,.env.*,*.env.*,*.pem,*.key,*.p12,*.pfx,*.sqlite,*.sqlite3,*.db,*.log,*.tmp,*.bak"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "README.txt"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\QRYVANTA"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\QRYVANTA"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch QRYVANTA"; WorkingDir: "{app}"; Flags: postinstall nowait skipifsilent
