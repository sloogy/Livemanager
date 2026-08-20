# GitHub-Modulbootstrap im Windows-Installer

## Ziel

Der LifePlanner-Setup installiert den Core und mindestens ein ausgewähltes Fachprogramm. BudgetManager, FPM und spätere Module werden nicht in den Installer kopiert. Der Setup fragt stattdessen die freigegebenen Releases der jeweiligen eigenständigen GitHub-Repositories ab.

## Ablauf

1. Der Setup entpackt temporär `LifePlannerInstallerBootstrap.exe` und `installer-module-sources.json`.
2. Der Bootstrap ruft die GitHub-Releases-API für bis zu vier konfigurierte Repositories parallel auf.
3. Er durchsucht je Repository bis zu 20 stabile Releases nach einem passenden `Windows_x86_64.lpmodule`-Asset.
4. Der Setup zeigt Name, Version, Releasebeschreibung, Repository und Fehlerstatus an.
5. Mindestens ein verfügbares Programm muss ausgewählt bleiben.
6. Nach Installation des Core lädt der Bootstrap die ausgewählten Pakete herunter.
7. Jedes Paket wird vollständig geprüft und danach gemeinsam transaktional in `modules/<id>` eingesetzt.
8. Schlägt ein Modul fehl, wird der gesamte Modulaustausch zurückgerollt.

## Vertrauensmodell

Der Installer durchsucht nicht beliebige GitHub-Projekte. Die vertrauenswürdigen Repositorynamen werden beim Core-Release aus der Lockdatei erzeugt. Der Repositoryname allein ist trotzdem kein Vertrauensbeweis. Ein Remote-Paket wird nur akzeptiert, wenn:

- der Download über HTTPS von GitHub beziehungsweise einem erlaubten GitHub-Assethost erfolgt,
- die von GitHub gemeldete Dateigröße stimmt,
- das Archiv keine Pfadtraversierung oder symbolischen Links enthält,
- `component.json` und `payload/module.json` zusammenpassen,
- der vollständige Payload-Hash stimmt,
- die Ed25519-Signatur gültig ist,
- Modul-ID und Version mit der ausgewählten GitHub-Veröffentlichung übereinstimmen,
- Plattform und `requires_host` zum installierten LifePlanner passen,
- die erwartete Windows-Programmdatei enthalten ist.

Unsignierte Remote-Pakete werden ohne Ausnahme abgelehnt.

Der bewusst unsignierte erste LifePlanner-Release ändert diese Grenze nicht: Seine `.lpmodule`-Assets werden vom LifePlanner-Release heruntergeladen und lokal in der Modulverwaltung geöffnet. Dort ist eine sichtbare manuelle Vertrauensbestätigung erforderlich. `--allow-unsigned` ist ein Build-Schalter und kein stilles Vertrauens-Override für den GitHub-Bootstrap.

## Modulquellen

Beim Windows-Release erzeugt `tools/build_release.py` aus `dependencies/modules.lock.json` die Datei:

```text
release/LifePlanner_Installer_Source/installer-module-sources.json
```

Standardmäßig werden folgende Repositories verwendet:

```text
<GITHUB_REPOSITORY_OWNER>/BudgetManager
<GITHUB_REPOSITORY_OWNER>/FPM
```

Abweichende Namen werden über Repository-Variablen gesetzt:

```text
BUDGETMANAGER_REPOSITORY=sloogy/Budgetmanager
FPM_REPOSITORY=sloogy/FPM
```

## Verpflichtung der Modul-Repositories

Für spätere vollautomatische Online-Installationen veröffentlicht jedes Modulrepository ein signiertes Asset nach folgendem Namensvertrag:

```text
<module-id>_<version>_Windows_x86_64.lpmodule
```

Beispiele:

```text
budgetmanager_2.2.56_Windows_x86_64.lpmodule
fpm_0.3.04_Windows_x86_64.lpmodule
```

Alle Repositories müssen dafür dasselbe Secret `LIFEPLANNER_UPDATE_PRIVATE_KEY_B64` verwenden. Der zugehörige Public Key wird beim LifePlanner-Build in Core und Bootstrap eingebettet. Für den ersten Release fehlen diese Secrets bewusst; dessen zentrale Releaseworkflows erzeugen die lokalen `.lpmodule`-Assets mit `--allow-unsigned`.

## Öffentliche und private Repositories

Für einen normalen Endbenutzer-Installer müssen die Release-Seiten und `.lpmodule`-Assets öffentlich abrufbar sein. Ein privates Modulrepository kann technisch nur abgefragt werden, wenn auf dem Zielcomputer bereits ein geeigneter `GITHUB_TOKEN` gesetzt ist. Der Installer enthält absichtlich keinen eingebetteten Zugriffstoken.

## Fehlerverhalten

Der Bootstrap schreibt ein maschinenlesbares INI-Ergebnis. Dadurch zeigt der Setup-Assistent bei einem Fehlschlag nicht nur eine Sammelmeldung, sondern beispielsweise eine ungültige Signatur, eine unpassende Modul-ID, eine falsche Version oder ein inkompatibles Paket an. Mehrere ausgewählte Module werden erst nach vollständiger Prüfung gemeinsam installiert.

## Offline-Verhalten

Da mindestens ein Programm erforderlich ist, kann der Online-Installer ohne erreichbares, gültiges Modulrelease nicht abgeschlossen werden. Für Offline-Verteilung bleibt das Portable-Paket beziehungsweise die spätere Installation lokaler `.lpmodule`-Dateien im LifePlanner-Modulmanager vorgesehen.
