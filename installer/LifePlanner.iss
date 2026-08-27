#define MyAppName "LifePlanner"
#define MyAppVersion "0.6.4"
#define MyAppExeName "LifePlanner.exe"
; Erzeugt von tools/generate_icons.py aus dem unskalierten Quellbild, mit
; allen Aufloesungen bis 256 in einer Datei. Ohne SetupIconFile traegt der
; Setup das Standardsymbol von Inno Setup - dasselbe wie jedes andere Setup.
#define MyAppIcon "..\lifeplanner_core\resources\icons\lifeplanner.ico"

[Setup]
SetupIconFile={#MyAppIcon}
AppId={{4DF6574B-6A23-4B55-8D2C-7B71A84CC1AC}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\LifePlanner
DefaultGroupName=LifePlanner
OutputDir=..\release
OutputBaseFilename=LifePlanner_0.6.4_Windows_Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesEnvironment=no
DisableProgramGroupPage=yes

[Files]
; Der Setup enthält ausschließlich den LifePlanner-Core. Module werden erst nach
; der Auswahl aus ihren eigenständigen GitHub-Releases geladen und geprüft.
Source: "..\release\LifePlanner_Installer_Source\*"; DestDir: "{app}"; Excludes: "modules\*,installer-module-sources.json"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\release\LifePlannerInstallerBootstrap.exe"; Flags: dontcopy
Source: "..\release\LifePlanner_Installer_Source\installer-module-sources.json"; Flags: dontcopy

[Dirs]
Name: "{app}\modules"

[Icons]
Name: "{group}\LifePlanner"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\LifePlanner"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Desktop-Verknüpfung erstellen"; GroupDescription: "Zusätzliche Aufgaben:"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "LifePlanner starten"; Flags: nowait postinstall skipifsilent

[Registry]
Root: HKCU; Subkey: "Software\Classes\.lpmodule"; ValueType: string; ValueName: ""; ValueData: "LifePlanner.ModulePackage"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\LifePlanner.ModulePackage"; ValueType: string; ValueName: ""; ValueData: "LifePlanner-Modulpaket"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\LifePlanner.ModulePackage\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\LifePlanner.ModulePackage\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#MyAppExeName}"" --install-module ""%1"""

[Code]
var
  ModulePage: TWizardPage;
  StatusLabel: TNewStaticText;
  RefreshButton: TNewButton;
  ModulePanel: TPanel;
  ModuleList: TNewCheckListBox;
  ModuleIds: array of String;
  ModuleAvailable: array of Boolean;
  CatalogLoaded: Boolean;
  CatalogPath: String;
  SourcesPath: String;
  BootstrapPath: String;
  SelectedModules: String;
  InstallResultPath: String;

procedure RecreateModulePanel;
begin
  if ModulePanel <> nil then
    ModulePanel.Free;
  ModulePanel := TPanel.Create(ModulePage);
  ModulePanel.Parent := ModulePage.Surface;
  ModulePanel.Left := 0;
  ModulePanel.Top := ScaleY(68);
  ModulePanel.Width := ModulePage.SurfaceWidth;
  ModulePanel.Height := ModulePage.SurfaceHeight - ScaleY(68);
  ModulePanel.BevelOuter := bvNone;
  SetArrayLength(ModuleIds, 0);
  SetArrayLength(ModuleAvailable, 0);
  ModuleList := TNewCheckListBox.Create(ModulePanel);
  ModuleList.Parent := ModulePanel;
  ModuleList.Left := 0;
  ModuleList.Top := 0;
  ModuleList.Width := ModulePanel.ClientWidth;
  ModuleList.Height := ModulePanel.ClientHeight;
  ModuleList.Anchors := [akLeft, akTop, akRight, akBottom];
  ModuleList.Flat := True;
  ModuleList.ShowLines := False;
  ModuleList.MinItemHeight := ScaleY(42);
end;

function CheckedModuleCount: Integer;
var
  I: Integer;
begin
  Result := 0;
  for I := 0 to GetArrayLength(ModuleIds) - 1 do
    if ModuleAvailable[I] and ModuleList.Checked[I] then
      Result := Result + 1;
end;

function BuildSelectedModuleList: String;
var
  I: Integer;
begin
  Result := '';
  for I := 0 to GetArrayLength(ModuleIds) - 1 do
    if ModuleAvailable[I] and ModuleList.Checked[I] then
    begin
      if Result <> '' then
        Result := Result + ',';
      Result := Result + ModuleIds[I];
    end;
end;

procedure LoadCatalogControls;
var
  Count, AvailableCount, I, ItemIndex: Integer;
  Section, ModuleId, ModuleName, Version, Repository, Description, ErrorText, CaptionText, DetailText: String;
  IsAvailable: Boolean;
begin
  RecreateModulePanel;
  Count := GetIniInt('catalog', 'count', 0, 0, 100, CatalogPath);
  AvailableCount := GetIniInt('catalog', 'available', 0, 0, 100, CatalogPath);
  SetArrayLength(ModuleIds, Count);
  SetArrayLength(ModuleAvailable, Count);

  for I := 0 to Count - 1 do
  begin
    Section := 'module' + IntToStr(I);
    ModuleId := GetIniString(Section, 'id', '', CatalogPath);
    ModuleName := GetIniString(Section, 'name', ModuleId, CatalogPath);
    Version := GetIniString(Section, 'version', '', CatalogPath);
    Repository := GetIniString(Section, 'repository', '', CatalogPath);
    Description := GetIniString(Section, 'description', '', CatalogPath);
    ErrorText := GetIniString(Section, 'error', '', CatalogPath);
    IsAvailable := GetIniBool(Section, 'available', False, CatalogPath);

    if IsAvailable then
    begin
      CaptionText := ModuleName + '  ' + Version;
      DetailText := Description + '  Quelle: github.com/' + Repository;
    end
    else
    begin
      CaptionText := ModuleName + '  (nicht verfügbar)';
      DetailText := ErrorText + '  Quelle: github.com/' + Repository;
    end;
    ItemIndex := ModuleList.AddCheckBox(
      CaptionText, DetailText, 0, IsAvailable, IsAvailable, False, False, nil
    );
    ModuleList.ItemFontStyle[ItemIndex] := [fsBold];
    ModuleIds[I] := ModuleId;
    ModuleAvailable[I] := IsAvailable;
  end;

  if AvailableCount > 0 then
    StatusLabel.Caption := IntToStr(AvailableCount) + ' Programm(e) verfügbar. Mindestens eines muss ausgewählt bleiben.'
  else
    StatusLabel.Caption := 'Kein installierbares Programm gefunden. Internetverbindung und GitHub-Releases prüfen.';
end;

procedure RefreshCatalog(Sender: TObject);
var
  ResultCode: Integer;
  Params: String;
begin
  StatusLabel.Caption := 'GitHub-Repositories werden abgefragt ...';
  WizardForm.NextButton.Enabled := False;
  CatalogLoaded := False;
  DeleteFile(CatalogPath);
  Params := 'catalog --sources ' + AddQuotes(SourcesPath) +
    ' --output ' + AddQuotes(CatalogPath) + ' --timeout 20';
  if not Exec(BootstrapPath, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
  begin
    StatusLabel.Caption := 'GitHub-Abfrage konnte nicht gestartet werden.';
    WizardForm.NextButton.Enabled := True;
    exit;
  end;
  if FileExists(CatalogPath) then
  begin
    LoadCatalogControls;
    CatalogLoaded := True;
  end
  else
    StatusLabel.Caption := 'GitHub-Abfrage fehlgeschlagen. Bitte Internetverbindung prüfen und erneut versuchen.';
  WizardForm.NextButton.Enabled := True;
end;

procedure InitializeWizard;
begin
  ExtractTemporaryFile('LifePlannerInstallerBootstrap.exe');
  ExtractTemporaryFile('installer-module-sources.json');
  BootstrapPath := ExpandConstant('{tmp}\LifePlannerInstallerBootstrap.exe');
  SourcesPath := ExpandConstant('{tmp}\installer-module-sources.json');
  CatalogPath := ExpandConstant('{tmp}\lifeplanner-installer-catalog.ini');
  InstallResultPath := ExpandConstant('{tmp}\lifeplanner-installer-result.ini');

  ModulePage := CreateCustomPage(
    wpSelectDir,
    'Programme auswählen',
    'Der Installer fragt die eigenständigen GitHub-Repositories ab. Mindestens ein Programm ist erforderlich.'
  );
  StatusLabel := TNewStaticText.Create(ModulePage);
  StatusLabel.Parent := ModulePage.Surface;
  StatusLabel.Left := 0;
  StatusLabel.Top := 0;
  StatusLabel.Width := ModulePage.SurfaceWidth - ScaleX(130);
  StatusLabel.Height := ScaleY(54);
  StatusLabel.AutoSize := False;
  StatusLabel.WordWrap := True;
  StatusLabel.Caption := 'Die verfügbaren Programme werden beim Öffnen dieser Seite geladen.';

  RefreshButton := TNewButton.Create(ModulePage);
  RefreshButton.Parent := ModulePage.Surface;
  RefreshButton.Left := ModulePage.SurfaceWidth - ScaleX(120);
  RefreshButton.Top := 0;
  RefreshButton.Width := ScaleX(120);
  RefreshButton.Height := ScaleY(28);
  RefreshButton.Caption := 'Neu abfragen';
  RefreshButton.OnClick := @RefreshCatalog;
  RecreateModulePanel;
end;

procedure CurPageChanged(CurPageID: Integer);
begin
  if (CurPageID = ModulePage.ID) and not CatalogLoaded then
    RefreshCatalog(nil);
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = ModulePage.ID then
  begin
    if not CatalogLoaded then
    begin
      MsgBox('Die GitHub-Modulliste wurde noch nicht erfolgreich geladen.', mbError, MB_OK);
      Result := False;
      exit;
    end;
    if CheckedModuleCount < 1 then
    begin
      MsgBox('Mindestens ein Programm muss ausgewählt sein, zum Beispiel BudgetManager oder FPM.', mbError, MB_OK);
      Result := False;
      exit;
    end;
    SelectedModules := BuildSelectedModuleList;
  end;
end;

procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Params, CachePath: String;
begin
  if CurStep = ssPostInstall then
  begin
    if SelectedModules = '' then
      SelectedModules := BuildSelectedModuleList;
    if SelectedModules = '' then
      RaiseException('Mindestens ein Programm muss installiert werden.');
    CachePath := ExpandConstant('{tmp}\LifePlannerModuleCache');
    DeleteFile(InstallResultPath);
    Params := 'install --catalog ' + AddQuotes(CatalogPath) +
      ' --selected ' + AddQuotes(SelectedModules) +
      ' --app-root ' + AddQuotes(ExpandConstant('{app}')) +
      ' --cache ' + AddQuotes(CachePath) +
      ' --result ' + AddQuotes(InstallResultPath);
    if not Exec(BootstrapPath, Params, '', SW_HIDE, ewWaitUntilTerminated, ResultCode) then
      RaiseException('Der zentrale Modul-Installer konnte nicht gestartet werden.');
    if ResultCode <> 0 then
      RaiseException(
        'Mindestens ein ausgewähltes Programm konnte nicht sicher aus GitHub geladen oder installiert werden.' + #13#10 +
        GetIniString('result', 'message', 'Unbekannter Fehler', InstallResultPath) + #13#10 +
        'Der Setup wird abgebrochen; bereits ausgetauschte Moduldateien werden durch den Transaktionsschutz zurückgerollt.'
      );
  end;
end;
