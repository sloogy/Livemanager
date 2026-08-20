# Changelog

## 0.5.7 – FPM vollständig gethemt

- FPM 1.0.3: auch die Inline-Styles einzelner Widgets folgen dem zentralen Designprofil. Damit ist die Seite Darstellung für alle drei Module vollständig wirksam.
- Semantische Farben (Erfolg, Gefahr, Warnung, Kategorie) bleiben in FPM bewusst fest, damit eine Löschen-Schaltfläche nicht grün wird.
- Kompatibilitätsbasis auf FPM 1.0.3 angehoben.

## 0.5.6 – FPM 1.0.2

- FPM 1.0.2: der Releasejob von 1.0.1 brach an einem i18n-Gate ab, das eine Diagnosemeldung für sichtbaren UI-Text hielt. Funktional identisch, 1.0.1 wurde nie veröffentlicht.
- Kompatibilitätsbasis auf FPM 1.0.2 angehoben.

## 0.5.5 – FPM folgt der zentralen Darstellung

- FPM 1.0.1 übernimmt das zentral gewählte Designprofil für Hauptfenster, Seitenleiste, Toolbar, Tabellen, Eingabefelder, Karten und Dialoge; die Schriftgröße des Profils wirkt als Skalierungsfaktor.
- Damit folgen alle drei Module der Seite Darstellung. Inline-Styles einzelner FPM-Widgets führen weiterhin eigene Farben.
- Kompatibilitätsbasis auf FPM 1.0.1 angehoben.

## 0.5.4 – Zentrale Darstellung und Modulstart aus der Quelle

- **Modulstart repariert.** `build_command()` nutzte die in `module.json` deklarierte Programmdatei nur, wenn der Host selbst eingefroren lief. Aus der Quelle gestartet fiel er auf `source_entry` zurück und meldete `Moduleinstieg fehlt: .../main.py` — eine Datei, die ein installiertes Binärmodul gar nicht mitbringt. Betroffen waren alle Module gleichermaßen. Die Programmdatei wird jetzt verwendet, sobald sie vorhanden ist; `source_entry` bleibt der Weg für Entwicklungsquellen.
- Fehlt beides, nennt die Meldung beide geprüften Pfade statt nur den Quelleinstieg.
- **Neuer Bereich Darstellung.** 26 Designprofile, Vorschau vor dem Übernehmen und ein Häkchen, das Host und alle Module auf dasselbe Profil setzt. Ohne Häkchen lässt sich je Modul ein eigenes Profil wählen.
- Die Profile sind wertgleich mit denen des BudgetManagers, damit „überall dasselbe Theme" dieselben Farben bedeutet und nicht nur denselben Namen.
- **Ein Austauschformat statt zwei.** Der FreizeitManager hatte `lifeplanner.theme.v1` im Bridge-Ordner bereits festgelegt; der Host schreibt jetzt genau dieses Format und der FreizeitManager übernimmt das zentrale Theme ohne jede Änderung.
- `shared_theme.json` wird bewusst nur bei gesetztem Häkchen geschrieben — ein ungefragt veröffentlichter Eintrag würde die abweichende Wahl einzelner Module überstimmen. Für abweichende Profile bekommt jeder Modulprozess `LIFEPLANNER_THEME` und `LIFEPLANNER_THEME_FILE`.
- BudgetManager übernimmt das zentrale Profil beim Start im Host. Seine lokal gespeicherte Wahl bleibt unangetastet und gilt weiterhin im Standalone-Betrieb.
- Profile mit ungültigem Modus, ungültiger Schriftgröße oder defekter Farbe werden übersprungen und auf der Seite Darstellung als Fehler benannt, statt die Optik stillschweigend zu ersetzen.
- Kompatibilitätsbasis auf BudgetManager 2.2.63 angehoben.
- Dokumentation: `docs/THEMING.md`.

## 0.5.3 – Kontaktmanager als drittes Modul

- **FreizeitManager** (Repository `sloogy/Kontaktmanager`) als drittes Modul aufgenommen: Kontaktrotation, Beziehungsfrische und Freizeitplanung. Aufgenommen in Lockdatei, GitHub-Katalog und Releaseworkflow.
- Die Modul-ID lautet `freizeitmanager`; das Repository heißt `Kontaktmanager`. Assets erscheinen daher als `freizeitmanager_<Version>_<Plattform>.lpmodule`.
- `tools/build_release.py` und `tools/build_linux_release.py` hatten BudgetManager und FPM fest verdrahtet. Beide leiten Repository-Variablen, Buildaufrufe und Quellparameter jetzt aus `dependencies/modules.lock.json` ab; ein weiteres Modul wäre sonst lautlos aus Release und Installer gefallen.
- `tools/validate_release.py` prüft jetzt jedes Modul aus der Lockdatei statt fest zwei; fehlende Vertragstests werden übersprungen statt verlangt.
- Ein Regressionstest stellt sicher, dass jedes Modul der Lockdatei im Workflow ausgecheckt und mitgebaut wird und dass die Buildskripte keine Modul-ID mehr fest verdrahten.

## 0.5.2 – FPM 1.0.0

- Kompatibilitätsbasis auf FPM 1.0.0 angehoben. Dieses Release behebt im FPM-Repository die Ursache dafür, dass das veröffentlichte Linux-`.lpmodule` die Programmdatei nur als `0644` speicherte.
- Mindestversion für FPM im GitHub-Katalog entsprechend auf 1.0.0 gesetzt.
- BudgetManager bleibt auf 2.2.62.

## 0.5.1 – Windows-Release, Modulstart und Modulkompatibilität

- Modulstart unter Linux repariert: `secure_extract_zip()` hat jede Datei mit Standardrechten geschrieben und das Execute-Bit aus dem Paket verworfen. Ein installiertes Modul scheiterte deshalb beim Start mit `[Errno 13] Keine Berechtigung`. Betroffen waren Modulinstallation und Update-Staging gleichermaßen.
- Das Execute-Bit wird jetzt aus dem Archiv übernommen, indem die Leserechte gespiegelt werden; die umask bleibt wirksam und setuid/setgid/sticky werden nie übernommen.
- Zusätzlich stellt der Modulinstaller die in `module.json` deklarierte Programmdatei unabhängig vom Archivinhalt ausführbar. Das fängt Pakete ab, die das Bit bereits beim Bauen verloren haben – aktuell das veröffentlichte `fpm_0.3.05_Linux_x86_64.lpmodule`.
- Der Modulstart repariert veraltete Installationen einmalig selbst und meldet sonst einen klaren Fehler statt eines rohen `Errno 13`.
- Der GitHub-Katalog kennt jetzt eine Mindestversion je Modul und bietet ältere Releases nicht mehr an, auch wenn sie ein passendes Asset mitbringen. BudgetManager ist auf 2.2.62 festgelegt, weil die Übersicht davor unter Fedora/Wayland in `CompactChart` abbrach; FPM auf 0.3.05.

- Windows-Release repariert: `_local_path()` im zentralen Updater hat einen Windows-Laufwerksbuchstaben (`C:\…`) als URL-Schema gelesen und lokale Update-Dateien deshalb als unsichere Remote-URLs abgelehnt.
- Zwei Testfälle verglichen Pfade mit hartkodiertem POSIX-Trennzeichen und schlugen unter Windows fehl; sie prüfen jetzt plattformneutral.
- Kompatibilitätsbasis auf BudgetManager 2.2.62 und FPM 0.3.05 (final statt `rc.1`) angehoben.
- `default_sibling` für BudgetManager auf die tatsächliche Ordnerschreibweise `../Budgetmanager` korrigiert; lokale Builds auf Linux fanden die Modulquelle vorher nicht.
- `LifePlanner_0.5.1_Windows_Setup.exe` wird jetzt als Release-Asset veröffentlicht statt nur als internes CI-Artefakt. Sie bleibt unsigniert; SmartScreen warnt entsprechend.
- Kanonische GitHub-Repositories integriert: `sloogy/Budgetmanager` und `sloogy/FPM`.
- Installer-/Releasegenerierung arbeitet mit den kanonischen Repository-Slugs ohne Repository-Owner-Variablen.
- Umgebungs-/Repositoryvariablen bleiben als ausdrückliche Overrides unterstützt.
- Transiente private GitHub-Token-Dateien und Kompatibilitätsdokumentation ergänzt.

## 0.5.0 – GitHub-Modulbootstrap im Windows-Installer
- Erster Release kann nur über den ausdrücklichen Schalter `--allow-unsigned` ohne Schlüssel gebaut werden.
- Unsignierte Windows-/Linux-`.lpmodule` behalten Payload-Hash-, Struktur-, Versions- und Plattformprüfung.
- Lokale Installation unsignierter Pakete verlangt eine manuelle Vertrauensbestätigung; Standardaktion ist Abbrechen.
- Automatischer GitHub-Bootstrap und Remote-Updates bleiben signaturpflichtig.
- Der Windows-Setup bleibt im ersten unsigned Release ein internes CI-Artefakt; öffentlich ausgeliefert werden Portable-Pakete und lokale `.lpmodule`-Assets.
- Linux multi-repository release with Fedora/Linux portable and local module assets.
- Hardened read-only GitHub token-file handling for private repositories.

- Windows-Setup enthält nur den LifePlanner-Core und fragt die eigenständigen Modul-Repositories zur Laufzeit ab.
- Dynamische Auswahlliste mit Version, Releasebeschreibung, Repository und Verfügbarkeitsstatus ergänzt.
- Mindestens ein Programm muss ausgewählt sein; eine reine Core-Installation wird im Setup verhindert.
- Ausgewählte `.lpmodule`-Assets werden direkt aus den jeweiligen GitHub-Releases geladen.
- Nur signierte Pakete mit gültigem Payload-Hash, passender Modul-ID, Version, Plattform und Core-Anforderung werden installiert.
- Mehrere Module werden in einer gemeinsamen Transaktion installiert und bei Fehlern zurückgerollt.
- Separater headless `LifePlannerInstallerBootstrap.exe` für Repositoryabfrage, Download und Installation ergänzt.
- Der erste LifePlanner-Release veröffentlicht BudgetManager- und FPM-`.lpmodule` bewusst unsigned für lokale Installation.

## 0.4.1 – Getrennte Git-Repositories

- BudgetManager- und FPM-Quellcode vollständig aus dem LifePlanner-Repository entfernt.
- Versionierte `dependencies/modules.lock.json` für Modulversionen und Buildverträge ergänzt.
- Lokale Modulquellen über Geschwisterordner, Umgebungsvariablen oder ignorierte Konfiguration auflösbar.
- Entwicklungsverknüpfung über Symlink, Windows-Junction oder ignorierte Kopie ergänzt.
- Windows-Releasepipeline checkt LifePlanner, BudgetManager und FPM als drei getrennte Repositories aus.
- Build prüft Modul-ID und Version gegen die Lockdatei.
- Release erzeugt `module-source-provenance.json` mit Git-Commit, Tag/Branch und Dirty-Status.
- Core-Validierung funktioniert ohne vorhandene Modulquellen; `--with-modules` prüft zusätzlich beide externen Repositories.
- Installer und zentraler Updater behalten fertige Modulbinärpakete, ohne Sourcecode zu vermischen.

## 0.4.0 – Modul-Installer

- Neuer Bereich **Module** für lokale Installation, Neuinstallation, Downgrade und Deinstallation.
- Neues ZIP-kompatibles Paketformat `.lpmodule`.
- Ed25519-Paketsignatur mit kryptografisch gebundenem Payload-SHA-256.
- Sicherheitsvorschau für Version, Herkunft, Plattform, Core-Abhängigkeit und Berechtigungen.
- Explizites Vertrauens-Gate für unsignierte Entwicklungspakete.
- Transaktionale Modulinstallation und -deinstallation über den externen Helfer.
- Profildaten bleiben bei der Deinstallation erhalten; Programm- und Profilbackup werden erstellt.
- Windows-Dateizuordnung für `.lpmodule` und direkter Aufruf über `--install-module`.
- Windows-Setup mit optional auswählbarem BudgetManager und FPM.
- Releasepipeline veröffentlicht Module als installierbare, signierte `.lpmodule`-Assets.
- Zentrales Manifest kennzeichnet nicht installierte Module als installierbar.

## 0.3.0 – Zentraler Core-/Modul-Updater

- Gemeinsamer Update-Bereich für LifePlanner-Core, BudgetManager, FPM und künftige Module.
- Signiertes `lifeplanner.update.v1`-Manifest mit Ed25519-Vertrauensanker.
- Komponentenarchive mit SHA-256, exakter Größenprüfung und sicherer ZIP-Extraktion.
- Externer Windows-Update-Helfer für gesperrte EXE-/DLL-Dateien.
- Transaktionaler Dateitausch, Profil-Sicherungen und automatisches Rollback.
- Host-Abhängigkeiten über `requires_host`; Core-Update wird bei Bedarf erzwungen.
- Modulinterne Updater bleiben standalone verfügbar, werden im LifePlanner-Host aber deaktiviert.
- Windows-Releasepipeline veröffentlicht signierte Komponentenassets im GitHub Release.

## 0.2.0 – FPM/BudgetManager Review Integration

- FPM auf 0.3.04 aktualisiert.
- Profilbezogenen LifePlanner-Bridge-Pfad im FPM aktiviert.
- Atomare FPM-JSONL-Snapshots ergänzt.
- BudgetManager Import-Inbox mit Vorschau, Bearbeiten, Übernehmen und Ablehnen ergänzt.
- Externe-ID-/Payload-Hash-Duplikatschutz und kontrolliertes Upsert ergänzt.
- Fremdwährungsbestätigung, Kategorieauflösung und Auditpersistenz ergänzt.
- Windows-Paketierung auf 0.2.0 aktualisiert.
