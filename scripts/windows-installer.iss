#ifndef AppVersion
  #error AppVersion must be provided
#endif
[Setup]
AppId={{A3E84F52-8756-4237-9454-213B1C0A9D51}
AppName=Shiguang Capture
AppVersion={#AppVersion}
AppPublisher=asoming
AppPublisherURL=https://github.com/asoming/shiguang-capture
DefaultDirName={localappdata}\Programs\ShiguangCapture
DefaultGroupName=Shiguang Capture
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=ShiguangCapture-v{#AppVersion}-Windows-x86_64-Setup
SetupIconFile=..\docs\assets\icon.ico
UninstallDisplayIcon={app}\ShiguangCapture.exe
Compression=lzma2/fast
SolidCompression=yes
WizardStyle=modern
CloseApplications=yes
RestartApplications=no

[Tasks]
Name: desktopicon; Description: "Create a desktop shortcut"; GroupDescription: "Shortcuts:"

[Files]
Source: "{#BundleDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Shiguang Capture"; Filename: "{app}\ShiguangCapture.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\Shiguang Capture"; Filename: "{app}\ShiguangCapture.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\ShiguangCapture.exe"; Description: "Launch Shiguang Capture"; Flags: nowait postinstall skipifsilent
