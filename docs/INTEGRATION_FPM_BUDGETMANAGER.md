# FPM ↔ BudgetManager Integrationsvertrag v1

## Datenfluss

```text
FPM-Datenbank
   │  nur lesen
   ▼
FPM budget_export_service
   │  atomarer JSONL-Snapshot
   ▼
<Profil>/bridge/fpm_to_budgetmanager.jsonl
   │  nur Vorschau
   ▼
BudgetManager Import-Inbox
   │  Benutzer: Bearbeiten / Übernehmen / Ablehnen
   ▼
BudgetManager-Datenbank
```

Es existiert kein direkter SQL-Zugriff zwischen FPM und BudgetManager.

## Vertrag `budgetmanager.import.v1`

Pflichtfelder:

- `schema`: `budgetmanager.import.v1`
- `operation`: aktuell `upsert`
- `external_id`: stabile ID, z. B. `fpm:expense:42`
- `source`
- `date`: ISO-Datum
- `amount`: endlicher positiver Betrag
- `currency`: ISO-artiger dreistelliger Code
- `description`

Optionale Felder:

- `category_path`
- `counterparty`
- `notes`
- `metadata.item_type`

## Zustände

- **Neu**: ID wurde noch nie verarbeitet.
- **Geändert**: dieselbe ID besitzt einen anderen Payload-Hash.
- **Buchung fehlt**: der Datensatz war importiert, die zugeordnete Buchung wurde aber gelöscht.
- **Übernommen**: identischer Snapshot wurde bereits verarbeitet.
- **Abgelehnt**: identischer Snapshot wurde bewusst abgelehnt. Eine spätere Änderung wird erneut vorgelegt.

## Idempotenz und Upsert

BudgetManager speichert pro `external_id` den Hash des vollständigen Quell-Payloads. Ein identischer FPM-Snapshot erzeugt keine zweite Buchung. Ein geänderter Snapshot aktualisiert die bisher zugeordnete Buchung erst nach erneuter Freigabe.

## Fremdwährungen

BudgetManager führt seine Beträge in einer konfigurierten Hauptwährung. Weicht die FPM-Quellwährung ab, muss der Benutzer den Betrag bearbeiten beziehungsweise die Umrechnung ausdrücklich bestätigen. Es wird kein Online-Wechselkurs verwendet.

## Auditdaten

Die lokale Tabelle `lifeplanner_import_state` enthält:

- externe ID und Quelle
- Quell-Payload-Hash
- Status
- zugeordnete Tracking-ID
- Verarbeitungszeitpunkt
- ursprünglichen Quell-Payload
- tatsächlich importierten Entwurf

Die Tabelle liegt ausschließlich in der BudgetManager-Datenbank und ist Bestandteil der normalen Backups.
