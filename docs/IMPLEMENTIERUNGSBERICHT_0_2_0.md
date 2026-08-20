# LifePlanner 0.2.0 – Implementierungsbericht

## Umgesetzt

- FPM-Modul von 0.3.03 auf 0.3.04 aktualisiert.
- LifePlanner-Hostpfad `LIFEPLANNER_BRIDGE_DIR` in FPM 0.3.04 wiederhergestellt.
- Review-first-Importer im BudgetManager ergänzt.
- Import-Inbox als Seitenleisten- und Extras-Menü-Aktion eingebunden.
- Zustands- und Auditpersistenz ergänzt.
- Kategorienauflösung, kontrollierte Kategorienanlage und Fremdwährungs-Gate umgesetzt.
- Upsert- und Orphan-Erkennung umgesetzt.
- Windows-Paketnamen und Versionsstände auf LifePlanner 0.2.0 angehoben.
- DE/EN/FR-Texte ergänzt.

## Bewusste Grenzen

- Kein automatischer Wechselkursabruf.
- Keine automatische Buchung beim Start.
- Keine direkte Einbettung der beiden Qt-Anwendungen.
- Kein direkter Zugriff auf fremde Moduldatenbanken.

## Nächste fachliche Ausbaustufe

Bankimport kann denselben Review-Inbox-Vertrag wiederverwenden. Dafür sollte ein generischer Provider-Adapter mit Quellfiltern, Regelvorschlägen und konfigurierbarer Duplikatstrategie ergänzt werden.
