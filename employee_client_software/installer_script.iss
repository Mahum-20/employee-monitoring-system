; Inno Setup Script for Silent UltraMonitor
[Setup]
AppName=UltraMonitor
AppVersion=1.0
DefaultDirName={userappdata}\UltraMonitor
DefaultGroupName=UltraMonitor
OutputBaseFilename=UltraMonitor_Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
CreateUninstallRegKey=no
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\UltraMonitor_Installer_Package\UltraMonitorSilent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\UltraMonitor_Installer_Package\config.json"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "UltraMonitorAgent"; ValueData: """{app}\UltraMonitorSilent.exe"""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\UltraMonitorSilent.exe"; Flags: nowait postinstall skipifsilent
