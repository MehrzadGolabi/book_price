; Inno Setup script. Build the exe first:
;   .venv\Scripts\python.exe -m PyInstaller BookCostCalculator.spec
; Source paths are relative to this .iss file (repo root).

#define MyAppName "برنامه برآورد قیمت کتاب انتشارات شهرقلم"
#define MyAppVersion "0.1"
#define MyAppPublisher "انتشارات شهرقلم"
#define MyAppURL "https://www.shghalam.ir"
#define MyAppExeName "BookCostCalculator.exe"

[Setup]
; NOTE: The value of AppId uniquely identifies this application. Do not use the same AppId value in installers for other applications.
AppId={{78E3E971-86A9-4B5D-98A7-CC839D0DEE29}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\PriceEstimatorShghalam
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
PrivilegesRequiredOverridesAllowed=dialog
OutputBaseFilename=mysetup
; Optional installer icon — drop an .ico at the repo root and uncomment:
;SetupIconFile=shghalam.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "config.ini"; DestDir: "{app}"; Flags: ignoreversion
; Fonts/stylesheet/logo are bundled inside the exe by BookCostCalculator.spec;
; copies next to the exe would also be found (bookcost/resources.py fallback).

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
