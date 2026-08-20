# LifePlanner 0.5.0 – Implementierungsbericht

## Umgesetzte Anforderung

Der Windows-Installer fragt die eigenständigen GitHub-Repositories nach verfügbaren LifePlanner-Modulpaketen ab. Der Benutzer wählt Programme per Kontrollkästchen aus; mindestens ein Programm ist obligatorisch. Die ausgewählten Programme werden heruntergeladen, kryptografisch geprüft und in den Core eingefügt.

## Neue Komponenten

- `lifeplanner_core/installer_catalog.py`: Quellenvalidierung, GitHub-Releaseabfrage und INI-Katalog.
- `lifeplanner_core/installer_bootstrap.py`: headless Download-, Prüf- und Installationslogik.
- `LifePlannerInstallerBootstrap.spec`: eigener PyInstaller-Onefile-Helfer ohne Qt.
- `installer-module-sources.json`: beim Release erzeugte Liste der vertrauenswürdigen Modul-Repositories.
- dynamische Inno-Setup-Seite „Programme auswählen“.
- eigene `.lpmodule`-Releaseworkflows in BudgetManager und FPM.

## Repositoryabfrage

Die abgefragten Repositories stammen aus der beim Core-Release erzeugten Vertrauensliste. Es findet keine unkontrollierte GitHub-Suche statt. Bis zu vier Repositories werden parallel abgefragt; Drafts und Pre-Releases werden standardmäßig ignoriert.

## Installationssemantik

Der Setup kopiert nur Coredateien. Anschließend installiert der Bootstrap alle ausgewählten Module in einer gemeinsamen Update-Transaktion. Eine teilweise erfolgreiche Installation wird dadurch vermieden. Vorhandene Modulprogrammdateien werden gesichert und bei Fehlern zurückgerollt; Profildaten werden nicht überschrieben.

## Grenzen

- Endbenutzer-Releases sollten öffentlich erreichbar sein. Private Repositories funktionieren nur mit einem bereits auf dem Zielcomputer gesetzten `GITHUB_TOKEN`; der Installer bettet keinen Token ein.
- Der eigentliche Inno-Setup-Build muss auf Windows erfolgen.
- Eine reine Core-Installation ist im Online-Setup absichtlich nicht erlaubt.
- Der Portable-Build bleibt für Offline-Szenarien separat.

## Zusätzliche BudgetManager-Korrektur

Die vollständige BudgetManager-Regression deckte fünf modale reine Informationsmeldungen in der LifePlanner-Import-Inbox und im Hinweis auf den zentralen Updater auf. Diese wurden auf den bereits vorhandenen nicht-modalen Benachrichtigungsdienst umgestellt. Sicherheitsfragen, irreversible Bestätigungen und echte Fehler bleiben modal.
