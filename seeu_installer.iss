; Script de Inno Setup para seeU - Supervisor Personal
; Genera un instalador profesional con asistente grafico (.exe) para Windows

#define MyAppName "seeU"
#define MyAppVersion "1.1.2"
#define MyAppPublisher "Seavuelo"
#define MyAppURL "https://github.com/Seavuelo/supervisor-personal"
#define MyAppExeName "seeU.exe"
#define MyAppMutex "seeU_Personal_Supervisor_Mutex"

[Setup]
AppId={{D37E8864-7546-4E83-9973-1F42B9A18DF1}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DisableProgramGroupPage=yes
; Deteccion y gestion de instancias en ejecucion
AppMutex={#MyAppMutex}
CloseApplications=yes
CloseApplicationsFilter=*.exe
RestartApplications=no
; Deteccion automatica del directorio de instalacion previo
UsePreviousAppDir=yes
DirExistsWarning=no
EnableDirDoesntExistWarning=no
; Permite instalar sin privilegios de administrador si el usuario no tiene permisos elevados
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
OutputDir=dist-installer
OutputBaseFilename=seeU-Setup-x64
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSmallImageFile=assets\icon.png
DisableWelcomePage=no

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "startupicon"; Description: "Iniciar seeU automaticamente al encender el computador"; GroupDescription: "Preferencias de inicio:"; Flags: unchecked

[Files]
; Archivos compilados por PyInstaller en dist\seeU
Source: "dist\seeU\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\icon.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: desktopicon
Name: "{userstartup}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"; Tasks: startupicon

[Registry]
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\{#MyAppName}"; ValueType: string; ValueName: "ExePath"; ValueData: "{app}\{#MyAppExeName}"; Flags: uninsdeletekey

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
var
  PreviousExe, PreviousVersion: String;
begin
  Result := True;
  if WizardSilent then
    Exit;
  if RegQueryStringValue(HKCU, 'Software\{#MyAppName}', 'ExePath', PreviousExe) and
     FileExists(PreviousExe) and
     RegQueryStringValue(HKCU, 'Software\{#MyAppName}', 'Version', PreviousVersion) then
  begin
    Result := MsgBox('seeU ' + PreviousVersion + ' ya esta instalado.' + #13#10 +
      'Deseas instalar seeU {#MyAppVersion} conservando tus tareas y preferencias?',
      mbConfirmation, MB_YESNO) = IDYES;
  end;
end;
