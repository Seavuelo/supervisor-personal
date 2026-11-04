; Script de Inno Setup para seeU - Supervisor Personal
; Genera un instalador profesional con asistente grafico (.exe) para Windows

#define MyAppName "seeU"
#define MyAppVersion "1.0.5"
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
function GetPreviousInstallDir(): String;
var
  PrevDir: String;
begin
  PrevDir := '';
  if not RegQueryStringValue(HKCU, 'Software\{#MyAppName}', 'InstallPath', PrevDir) then
  begin
    if not RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1', 'InstallLocation', PrevDir) then
    begin
      RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1', 'InstallLocation', PrevDir);
    end;
  end;
  Result := PrevDir;
end;

function GetPreviousVersion(): String;
var
  PrevVer: String;
begin
  PrevVer := '';
  if not RegQueryStringValue(HKCU, 'Software\{#MyAppName}', 'Version', PrevVer) then
  begin
    if not RegQueryStringValue(HKCU, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1', 'DisplayVersion', PrevVer) then
    begin
      RegQueryStringValue(HKLM, 'Software\Microsoft\Windows\CurrentVersion\Uninstall\{#SetupSetting("AppId")}_is1', 'DisplayVersion', PrevVer);
    end;
  end;
  Result := PrevVer;
end;

function InitializeSetup(): Boolean;
var
  PrevDir: String;
  PrevVer: String;
  UninstallerPath: String;
  ResultCode: Integer;
  MsgPrompt: String;
begin
  Result := True;
  PrevDir := GetPreviousInstallDir();
  PrevVer := GetPreviousVersion();

  if (PrevDir <> '') and FileExists(PrevDir + '\{#MyAppExeName}') then
  begin
    if PrevVer <> '' then
      MsgPrompt := 'Se ha detectado una version anterior de seeU (' + PrevVer + ') instalada en tu equipo.' + #13#10 + #13#10 +
                   'Deseas actualizar a la version {#MyAppVersion} manteniendo todas tus tareas y datos a salvo?' + #13#10 + #13#10 +
                   '[Si] Actualizar directamente conservando mis datos (Recomendado).' + #13#10 +
                   '[No] Reinstalar desde cero.'
    else
      MsgPrompt := 'Se ha detectado una instalacion existente de seeU.' + #13#10 + #13#10 +
                   'Deseas actualizar manteniendo todos tus datos personales a salvo?' + #13#10 + #13#10 +
                   '[Si] Actualizar directamente conservando mis datos.' + #13#10 +
                   '[No] Reinstalar desde cero.';

    if MsgBox(MsgPrompt, mbConfirmation, MB_YESNO) = IDYES then
    begin
      Result := True;
    end
    else
    begin
      if MsgBox('Deseas desinstalar la version anterior ahora antes de continuar con la instalacion limpia?', mbConfirmation, MB_YESNO) = IDYES then
      begin
        UninstallerPath := PrevDir + '\unins000.exe';
        if FileExists(UninstallerPath) then
        begin
          Exec(UninstallerPath, '/SILENT /NORESTART', '', SW_SHOW, ewWaitUntilTerminated, ResultCode);
        end;
      end;
      Result := True;
    end;
  end;
end;
