; Inno Setup Script for Silent Employee Monitor Agent
[Setup]
AppName=Employee Monitor Agent
AppVersion=1.0
DefaultDirName={userappdata}\EmployeeMonitorAgent
DefaultGroupName=Employee Monitor
OutputBaseFilename=EmployeeMonitor_Setup
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
CreateUninstallRegKey=no
ArchitecturesInstallIn64BitMode=x64

[Files]
Source: "dist\EmployeeMonitor_Installer_Package\EmployeeMonitorSilent.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\EmployeeMonitor_Installer_Package\config.json"; DestDir: "{app}"; Flags: ignoreversion

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "EmployeeMonitorAgent"; ValueData: """{app}\EmployeeMonitorSilent.exe"""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\EmployeeMonitorSilent.exe"; Flags: nowait postinstall skipifsilent
