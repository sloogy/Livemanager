# Meldungen fürs Dashboard — `lifeplanner.notice.v1`

Wie ein Modul dem Host mitteilt, dass etwas ansteht.

## Wozu

Der Host zeigte bis 0.5.16, ob die Module laufen und wie viele Zeilen in den
Brückendateien stehen. Was in einem Modul gerade schiefläuft — ein überzogenes
Budget, ein Füller, der seit Wochen ungespült steht, ein Freund, den man lange
nicht gesehen hat — stand nur dort und war nur zu sehen, wenn man das Modul
öffnete.

Dabei ist der Host das Fenster, das ohnehin offen ist. Er zeigt diese Meldungen
jetzt auf der Übersichtsseite, über den Modulkacheln.

## Die drei Regeln

**Nur Ergebnisse, keine Rohdaten.** Eine Meldung trägt eine Überschrift, einen
Zusatz und eine Dringlichkeit. Kein Betrag als Zahl, keine Buchung, kein
Kontaktname als Datensatz. Die Datei liegt im Brückenordner und ist für jedes
Modul lesbar — das folgt aus dem [Modul-Host-Vertrag](MODUL_HOST_VERTRAG.md).

**Der Host bewertet nichts.** Er sortiert und zeigt an. Die Dringlichkeit kommt
vom Modul, das die Daten hat: Nur der BudgetManager weiß, was „80 % verbraucht"
bei dieser Kategorie in diesem Monat bedeutet. Eine Bewertung im Host wäre eine
zweite Fachlogik neben der ersten, und die beiden laufen auseinander.

**Der Text ist schon formuliert.** Was der Host anzeigt, hat der Absender
geschrieben — in der Sprache, die im Modul eingestellt ist.

## Die Datei

Eine Datei je Modul im Brückenordner, benannt `<modul>_notices.jsonl`. Der Host
sucht nach `*_notices.jsonl` in allen bekannten Brückenordnern (siehe
`bridge_registry`), den aktiven zuletzt.

Geschrieben wird **atomar** und als **vollständiger Stand**, nicht angehängt:
Die Datei ist eine Momentaufnahme dessen, was gerade gilt. Was behoben ist,
verschwindet damit von selbst — sonst bleibt eine erledigte Warnung stehen, bis
jemand aufräumt, und niemand räumt auf.

### Kopfzeile

```json
{
  "schema": "lifeplanner.notice.manifest.v1",
  "module": "Budgetmanager",
  "module_version": "2.2.73",
  "generated_at": "2026-08-22T23:15:15+00:00",
  "profile": "",
  "count": 2
}
```

`module` wird als Absender angezeigt. Fehlt die Kopfzeile, nimmt der Host den
Dateinamen — eine grobe Zuordnung ist besser als eine Meldung ohne Absender.

### Meldungszeile

```json
{
  "schema": "lifeplanner.notice.v1",
  "id": "7a1a6e6d23bfdb2e",
  "urgency": "kritisch",
  "headline": "Miete: Budget überzogen",
  "detail": "08/2026",
  "area": "budget"
}
```

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `schema` | ja | genau `lifeplanner.notice.v1` |
| `id` | ja | stabile Kennung; dieselbe Sache soll nach dem nächsten Schreiben dieselbe Meldung sein, keine zweite |
| `urgency` | ja | `info`, `warnung` oder `kritisch` |
| `headline` | ja | eine Zeile, fertig formuliert; leer heißt: Zeile wird verworfen |
| `detail` | nein | Zusatz, wird hinter der Überschrift gezeigt |
| `area` | nein | Bereich im Modul, für spätere Sprungziele |

**Die Kennung gehört gehasht.** Sie steht in einer Datei, die jedes Modul lesen
darf, und eine Kategorie kann „Therapie" heißen. Der BudgetManager bildet sie
als gekürzten SHA-256 über die Bestandteile.

## Was der Host mit unerwarteten Werten macht

| Fall | Verhalten |
|---|---|
| unbekannte `urgency` | wird als `info` gezeigt, **nicht verworfen** — eine neue Stufe heißt neueres Modul, nicht kaputte Datei |
| fremdes `schema` | übersprungen, zählt als unlesbare Zeile |
| kaputte JSON-Zeile | übersprungen, die übrigen Zeilen gelten weiter |
| Datei über 2 MB | nicht gelesen; ein Modul mit einem Schreibfehler darf den Host nicht anhalten |
| unlesbare Zeilen vorhanden | werden im Dashboard **gezählt und angezeigt** — dass ein Modul etwas zu sagen hat, das nicht ankommt, gehört sichtbar |

## Grenzen

Jedes Modul deckelt seine Meldungen selbst (der BudgetManager bei 20, mit einer
Sammelzeile für den Rest). Der Host deckelt zusätzlich bei 50 über alle Module
und zeigt davon 6 an — ein Dashboard, das man scrollen muss, wird nicht gelesen.

## Wer schreibt bereits

| Modul | Meldungen | Höchste Stufe |
|---|---|---|
| BudgetManager | überzogene Budgets, Sparziele kurz vor oder nach dem Termin, erreichte Sparziele | `kritisch` |
| FountainPen Manager | die Sammlungsprüfung (`build_collection_health`): Befüllungen über dem Safety-Limit, gesperrte Füller, Tinten zur Neige, offene Garantien | `kritisch` |
| FreizeitManager | die Vorschläge des Fokus-Cockpits, höchstens drei | `warnung` |

**Der FreizeitManager kennt bewusst kein `kritisch`.** Eine Freundschaft, die
still geworden ist, ist kein Alarm. Das Programm ist ausdrücklich so gebaut,
dass es keinen Schuldenberg aufbaut; eine rote Meldung neben einem überzogenen
Budget würde genau das wieder einführen. Ein Test hält das fest.

Der FreizeitManager schreibt weiterhin auch `freizeitmanager.focus.v1` — das
trägt die Zählwerte der Fokus-Zusammenfassung, diese Datei die Meldungen. Aus
jenem Format ist dieses hervorgegangen.
