# LifePlanner 0.5.0 – Release-Validierung

## Automatisiert geprüft

- vollständige Python-Kompilierung des Core und des neuen Bootstrap-Helfers,
- Quellenformat und Repositoryvalidierung,
- GitHub-Releaseauswahl über mehrere Releases,
- parallele Repositoryabfrage sowie Katalog-INI-Schreib- und Leselogik,
- Mindestwahl von einem Programm im Installervertrag,
- signierter End-to-End-Moduldownload mit transaktionaler Installation und lesbarer Fehlerdatei,
- expliziter `--allow-unsigned`-Buildmodus mit Abbruch bei fehlendem Opt-in oder widersprüchlich gesetzten Schlüsseln,
- lokale Prüfung unsignierter `.lpmodule` mit manueller Vertrauenswarnung und **Abbrechen** als Standard,
- bestehende Core-, Updater-, Backup-, Modul- und Packagingtests,
- zentrale Windows-/Linux-Paketbuilder für die ausdrücklich unsignierten Erst-Release-Assets,
- statische Prüfung der drei GitHub-Actions-Workflows.

## Nicht lokal ausgeführt

- Kompilierung von `LifePlanner_0.5.0_Windows_Setup.exe` mit Inno Setup,
- realer GitHub-API-Aufruf gegen die noch nicht veröffentlichten Benutzerrepositories,
- Windows-SmartScreen- und Code-Signing-Prüfung.

Diese Schritte werden durch die enthaltene `windows-latest`-Pipeline beziehungsweise nach Veröffentlichung der Repository-Releases ausgeführt.

## Tatsächliche Testläufe dieser Quellversion

- LifePlanner-Core: **55 bestanden**.
- BudgetManager: alle 119 Testdateien in vier Batches ausgeführt, **766 bestanden, 12 übersprungen**. Ein dabei entdeckter älterer LifePlanner-Inbox-Verstoß gegen die nicht-modale Informationspolicy wurde auf `show_info` umgestellt und anschließend vollständig grün geprüft.
- FPM: **355 bestanden** in der vollständigen Qt-freien Suite. Fünf zusätzliche GUI-Testdateien konnten in der Linux-Prüfumgebung nicht gesammelt werden, weil PySide6 dort nicht installiert ist.
- Multi-Repository-Vertragsvalidierung: Core, BudgetManager und FPM gemeinsam erfolgreich.
- YAML der drei GitHub-Actions-Workflows erfolgreich geparst.

Der Inno-Setup-Quelltext wurde statisch geprüft. Eine echte Kompilierung des Windows-Setups bleibt dem enthaltenen `windows-latest`-Workflow vorbehalten.

Der erste Release wird bewusst ohne Signaturschlüssel gebaut. Deshalb sind automatische Remote-Updates und der headless GitHub-Bootstrap für diese Pakete nicht freigeschaltet; die veröffentlichten `.lpmodule` werden lokal mit sichtbarer Vertrauensbestätigung installiert.
Der Windows-Setup bleibt bis zur Einführung signierter Modul-Releases ein internes Actions-Artefakt und wird nicht an Endnutzer veröffentlicht.
