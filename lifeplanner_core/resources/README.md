# Mitgelieferte Dateien des Hosts

## Update-Vertrauensanker

Für produktive Remote-Updates muss hier beim Build `lifeplanner_update_public_key.b64` liegen.
Die Datei enthält ausschließlich den öffentlichen Ed25519-Schlüssel. Der private Schlüssel darf
niemals in das Repository oder ein Release-Artefakt gelangen.

## Programmbilder (`icons/`)

Das Symbol des Hosts, sein Logo-Banner und die Symbole der Module. Anders als der
Vertrauensanker gehören sie in die Versionierung: Sie sind Programmbestandteil, kein
Bauartefakt.

Erzeugt werden sie aus den unskalierten Quellbildern unter `icons/original` durch
`python3 tools/generate_icons.py`. Wer eine Kante nachzieht, ändert die Quelle und lässt den
Lauf erneut durch — von Hand skalierte Dateien lassen sich später nicht mehr nachvollziehen.
Pillow braucht nur dieses Werkzeug; im Betrieb liest der Host fertige PNG-Dateien.

Die Zuordnung Modul zu Bild geschieht ausschließlich über den Dateinamen:
`icons/modules/<modul-id>.png`, mit der Kennung aus `dependencies/modules.lock.json`. Ein
viertes Modul braucht damit eine Bilddatei und keine Zeile Code. Fehlt sie oder lässt sie sich
nicht lesen, setzt die Oberfläche ein neutrales Symbol ein — die Modulliste bleibt vollständig.

`icons/original` bleibt aus den Paketen draußen. `LifePlanner.spec` nimmt nur die abgeleiteten
Dateien mit, in einen Ordner `icons` neben der ausführbaren Datei; `lifeplanner_core/branding.py`
sucht sie genau dort.
