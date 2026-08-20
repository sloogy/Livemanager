# LifePlanner 0.3.0 – Implementierungsbericht

## Auftrag

Ein zentraler Updater sollte LifePlanner-Core, BudgetManager, FPM und künftige Module gemeinsam aktualisieren und unter Windows zuverlässig funktionieren.

## Umgesetzte Komponenten

### Zentrale Oberfläche

Der LifePlanner besitzt eine neue Navigationsseite **Updates** mit:

- konfigurierbarer Manifest-URL
- optionaler automatischer Prüfung beim Start
- Übersicht über installierte und verfügbare Versionen
- Auswahl einzelner oder aller Komponenten
- Status für Kompatibilität und fehlende Plattformassets
- Anzeige des letzten Update- oder Rollbackergebnisses

### Update-Service

Der Service ermittelt die installierten Versionen aus:

- `lifeplanner_core.APP_VERSION`
- den dynamisch entdeckten `module.json`-Dateien

Ein unbekanntes Modul im zentralen Manifest wird als noch nicht installiert behandelt und kann über denselben Mechanismus ergänzt werden.

### Vertrauenskette

- Ed25519-signiertes Manifest
- eingebetteter öffentlicher Schlüssel
- privater Schlüssel ausschließlich als Release-Secret
- HTTPS-Pflicht für Remote-Quellen
- SHA-256 und exakte Downloadgröße je Komponente
- sichere ZIP-Extraktion

### Windows-Dateisperren

Ein separat gebauter `LifePlannerUpdater.exe` wird vor dem Update in den Datenordner kopiert. Er wartet auf das Ende des LifePlanner-Prozesses und kann danach sämtliche EXE-/DLL-Dateien im Programmordner ersetzen.

### Transaktion und Rollback

- Vorab-Sicherung aller Profile
- Rollback-ZIP der bisherigen Programmkomponente
- Kopieren der neuen Payload auf das Ziel-Dateisystem
- Rename-basierter Dateitausch mit Wiederholungen bei kurzzeitigen Windows-Sperren
- Rückwärts-Rollback aller bereits angewendeten Operationen bei einem späteren Fehler
- Neustart der bisherigen Version nach einem zurückgerollten Fehler

### Modulverhalten

`ModuleProcessManager` setzt beim Host-Start:

```text
LIFEPLANNER_CENTRAL_UPDATER=1
```

BudgetManager unterdrückt damit die automatische eigene Update-Prüfung und verweist beim manuellen Aufruf auf LifePlanner. FPM zeigt im Einstellungsbereich denselben zentralen Hinweis. Standalone bleibt das bisherige Updateverhalten erhalten.

### Releasepipeline

Die Windows-Pipeline:

1. materialisiert den öffentlichen Schlüssel
2. führt Releaseprüfungen aus
3. baut BudgetManager, FPM, LifePlanner und den externen Updater
4. erzeugt Portable ZIP und Inno-Setup-Quelle
5. erzeugt ein Core-Komponentenarchiv
6. erzeugt automatisch ein Archiv für jedes gebaute Modul
7. erzeugt und signiert `lifeplanner-latest.json`
8. baut den Installer
9. veröffentlicht die Assets am GitHub-Tag

## Bewusste Grenzen

- Ohne konfigurierte Manifest-URL erfolgt keine Netzwerkverbindung.
- Ohne eingebetteten Public Key werden Remote-Updates fail-closed abgelehnt.
- Die aktuelle Pipeline erzeugt Windows-x86_64-Komponenten. Das Manifestformat und der Update-Service unterstützen zusätzliche Linux-Assets, sobald ein Linux-Build ergänzt wird.
- Ein erfolgreich installiertes Programm-Rollback wird aufbewahrt, aber nicht über eine grafische Downgrade-Schaltfläche zurückgespielt. Fehler während der Installation werden automatisch zurückgerollt.
