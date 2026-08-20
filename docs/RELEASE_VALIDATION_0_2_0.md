# LifePlanner 0.2.0 – Release-Validierung

Stand: 30. Juli 2026

## Ergebnis

**Source-/Integrationsstatus: GRÜN**  
**Native Windows-Binärprüfung: AUSSTEHEND**

## Erfolgreich geprüft

- vollständige Syntaxkompilierung der geänderten Core-, BudgetManager- und FPM-Dateien
- Modul-Discovery: BudgetManager 2.2.49 und FPM 0.3.04
- 12 LifePlanner-Core-/Packaging-/Host-Vertragstests
- 7 BudgetManager-LifePlanner-Importtests
- 10 FPM-Bridge-/Collection-Health-/Host-Vertragstests
- 43 zusätzliche BudgetManager-Core-, Datenpfad-, Main-Window- und Tracking-Regressionstests
- 54 zusätzliche FPM-0.3.04-Enterprise-, Cross-Platform-, Updater-, Packaging- und Wishlist-Regressionstests
- atomarer Bridge-Snapshot
- Neu-/Geändert-/Abgelehnt-/Orphan-Zustände
- idempotenter Import und Update derselben Tracking-Buchung
- Fremdwährungs-Gate
- Beibehaltung einer vom Benutzer gewählten Kategorie bei späteren FPM-Änderungen
- DE/EN/FR-JSON-Dateien syntaktisch gültig
- Windows-Build-, Installer- und Portable-Paketnamen statisch konsistent auf 0.2.0

## Nicht in dieser Linux-Laufzeit ausführbar

- interaktiver Qt-GUI-Smoke-Test, da PySide6 in der Prüf-Laufzeit nicht installiert war
- Erzeugung und Start einer echten Windows-EXE
- realer Inno-Setup-Installations-/Deinstallationslauf

Die Projektabhängigkeiten enthalten PySide6 6.10.3. Der GitHub-Actions-Workflow baut auf `windows-latest` und führt vor dem Build `tools/validate_release.py` aus.

## Zusätzlicher Hinweis

Ein Versuch, die gesamte sehr große BudgetManager-Testmenge in einem einzelnen Lauf auszuführen, wurde nach 37 % durch das Laufzeitlimit der Umgebung beendet; bis dahin trat kein Fehler auf. Die integrationsnahen und releasekritischen Tests wurden anschließend vollständig und erfolgreich in getrennten Batches ausgeführt.
