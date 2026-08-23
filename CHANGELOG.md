# Changelog

## 0.6.0 — 23. August 2026

Das Dashboard zeigt jetzt, was die Module melden — überzogene Budgets, fällige
Reinigungen, die nächsten Kontaktvorschläge. Bisher sah der Host nur, ob ein
Modul läuft; was darin schieflief, sah nur, wer das Modul öffnete.

Modulstände: BudgetManager 2.3.0, FPM 1.3.0, FreizeitManager 0.2.0.

### Funktion

- **Das Dashboard zeigt, was die Module melden.** Die Übersichtsseite führte
  nur die Modulkacheln; was in einem Modul gerade schiefläuft, stand nur dort.
  Über den Kacheln stehen jetzt die Meldungen aller Module nach
  `lifeplanner.notice.v1` — nach Dringlichkeit sortiert, mit dem Absender
  dahinter.

  **Der Host bewertet nichts.** Er sortiert und zeigt an; die Dringlichkeit
  kommt vom Modul, das die Daten hat. Eine Bewertung hier wäre eine zweite
  Fachlogik neben der ersten, und die beiden laufen auseinander. Gelesen wird
  aus allen bekannten Brückenordnern (Loop 31), den aktiven zuletzt.

  Eine unbekannte Dringlichkeitsstufe wird als `info` gezeigt, nicht
  verworfen: Sie bedeutet ein neueres Modul, keine kaputte Datei — und ein
  älterer Host darf die Meldung eines neueren Moduls nicht verschlucken,
  gerade dann nicht, wenn sie wichtig ist. Unlesbare Zeilen werden gezählt und
  angezeigt, statt still zu verschwinden. Das Format steht in
  `docs/MELDUNGEN_DASHBOARD.md`.

### Dokumentation

- **Das README sagt jetzt zuerst, was das Programm tut.** Vorher stand dort
  Technik: Modulverträge, Prozessverwaltung und Lockdateien. Was ein Nutzer
  davon hat, stand nirgends. Wer wissen wollte, wofür das Programm da ist,
  fand einen Satz und danach die Bauanleitung. Der fachliche Teil steht jetzt
  vorn und beantwortet, was man mit dem Programm tut und für wen es gedacht
  ist; das Technische folgt darunter. Drei Tests halten die Reihenfolge fest.

### Sicherheit

- **Der Ausnahmen-Ratchet sah `contextlib.suppress` nicht.** Er zählt stumme
  Schlucker (`except Exception: pass`) und deckelt sie — kannte aber nur
  `except`-Handler. Dieselbe Sache als `with contextlib.suppress(...)`
  geschrieben verschwand spurlos aus der Zählung, ohne dass sie besser
  meldete. Genau dazu rät ruffs SIM105. Der Host ist seit Loop 24 das erste
  Programm der Suite ohne einen einzigen stummen Schlucker — mit der alten
  Zählweise war das eine Aussage über `except`, nicht über Schweigen. Der
  Ratchet zählt `suppress` jetzt mit (wortgleich in allen vier Programmen),
  SIM105 bleibt begründet aus. Der Befund für den LifePlanner bleibt: null.

## 0.5.15 – Sicherheit und Stabilität

### Stabilität

- **Die Modulversionen standen an zwei Stellen und wurden an der falschen
  nachgezogen.** Neben `dependencies/modules.lock.json` trug
  `.github/workflows/release.yml` sie als feste Rückfallwerte; `sync_version.py`
  schrieb sie dort per Regex hinein. Das scheiterte am Release-Token, der
  Workflow-Dateien nur mit dem Recht `workflows` schreiben darf — dieselbe
  Sperre, an der schon der BudgetManager viermal hängengeblieben ist. Der
  Workflow liest die Refs jetzt zur Laufzeit aus der Lockdatei
  (`tools/module_sources.py --github-env`) und checkt mit
  `env.LOCK_<MODUL>_REF` aus. Ein Modulwechsel ist damit eine Änderung an
  einer JSON-Datei.
- **Die Modulstände waren fünf Fassungen alt.** Die Lockdatei zeigte auf
  BudgetManager 2.2.70, FPM 1.1.0 und FreizeitManager 0.1.8; veröffentlicht
  sind 2.2.73, 1.2.5 und 0.1.13. Jetzt nachgezogen.
- **Der Linux-Metadatenschritt lief ohne `set -euo pipefail`.** Wäre die
  Auflösung der Modulquellen fehlgeschlagen, hätte `actions/checkout` ein
  leeres Ref bekommen und stillschweigend den Standardzweig gezogen.

### Sicherheit

- **Ein Zeilenumbruch in der Lockdatei hätte eine zweite Umgebungsvariable
  definiert.** Die Werte gehen nach `$GITHUB_ENV`; `github_env_lines()` weist
  Werte mit `\r` oder `\n` jetzt ab, statt sie durchzureichen.
- **Die Versionsersetzung traf fremde Versionen.** `sync_version.py` ersetzte
  alles der Reihe des Hosts — bei einem LifePlanner 1.1.x hätte das das
  FPM-Ref `v1.1.0` mitgezogen. Die Workflow-Datei trägt jetzt gar keine
  Version mehr, und ein Test hält das fest.

## 0.5.14 – Sicherheit und Stabilität

### Stabilität

- **Bei jedem Push nach main laufen jetzt die Gates.** Vorher lief dort gar
  nichts: Der volle Lauf hängt am Tag beziehungsweise an einem
  `[release]`-Commit, gearbeitet wird in dieser Suite aber direkt auf main.
  Ein Fehler wäre erst beim nächsten Release aufgefallen — bis zu zehn
  Arbeitsrunden später. Der neue Lauf ist bewusst schlank: Linux, ein Python,
  keine Builds, zwei bis drei Minuten. Er reagiert nur auf main, nie auf Tags,
  damit das Doppellauf-Problem nicht zurückkommt, das den Push-Trigger im
  Release-Workflow ausgeschlossen hatte.
- **Zwei kaputte Einstellungsdateien in derselben Sekunde** bekamen denselben
  Namen; die zweite überschrieb die erste und die ursprüngliche Fassung war
  doch wieder weg. Außerdem wuchsen die beiseitegelegten Fassungen unbegrenzt
  — jetzt bleiben zehn.
- **Der Ausnahmen-Ratchet ist eingebaut** und läuft im Release-Lauf mit. Er
  prüft den Syntaxbaum statt Textzeilen und erfasst alles außerhalb von Tests
  und Werkzeugen — `update_helper.py` und `windows_launcher.py`, also
  ausgerechnet der Update-Pfad, standen vorher außerhalb jeder Prüfliste.
- **Ruff läuft jetzt im Release-Lauf** mit denselben Regeln wie in FPM.

## 0.5.13 – Sicherheit und Stabilität

### Sicherheit

- **Der Profilordner liegt nicht mehr offen.** Er trägt die Einstellungen, die
  Brückendateien mit Buchungen und Sparzielen sowie die Moduldaten. Angelegt
  wurde er mit dem Standard-umask, auf typischen Linux-Systemen also 0755.
  Jetzt 0700, und die Profilsicherungen bekommen 0600.
- **Update-Archive** werden zusätzlich auf ihre Kompressionsrate geprüft. Ein
  Archiv kann die Grössengrenze unterlaufen und beim Entpacken trotzdem
  explodieren.

### Stabilität

- **Nur eine Instanz je Datenordner.** Zwei Hosts hätten dieselben Module
  gestartet und in denselben Brückenordner geschrieben — beim Update zöge
  einer dem anderen die Dateien unter den Füssen weg.
- **Eine unlesbare Einstellungsdatei** wird beiseitegelegt statt
  überschrieben. Neu erkannt wird dabei auch gültiges JSON, das kein Objekt
  ist — das wurde vorher kommentarlos verworfen.
- **Modul-Logs wachsen nicht mehr unbegrenzt.** Sie werden beim Modulstart
  gerollt; ein `RotatingFileHandler` greift dort nicht, weil der Modulprozess
  selbst in den Dateideskriptor schreibt.
- **Profilsicherungen** werden auf die zwanzig jüngsten je Profil begrenzt.

### Darstellung

- Die Oberfläche wächst mit der eingestellten Schrift, mit abgestuften Radien
  nach dem Vorbild des BudgetManagers.

## 0.5.12 – Dreisprachige Oberfläche

### Der Host spricht jetzt Deutsch, Englisch und Französisch

LifePlanner war als einziges Programm der Suite einsprachig. Seine Texte
standen fest im Quelltext, während BudgetManager, FPM und FreizeitManager
längst drei Sprachen sprachen. Wer die Module auf Französisch benutzte, sah
den Rahmen darum weiterhin auf Deutsch.

- 93 Texte liegen jetzt als Sprachdateien vor; die Sprache wählt man auf der
  Darstellungsseite.
- Eine fehlende oder kaputte Sprachdatei lässt den Start weiterlaufen.
- Ein Test verhindert, dass neue feste Texte in die Oberfläche zurückkommen.

### Die Oberfläche wächst mit der Schriftgröße

Feste Pixelwerte setzten sich über die Profilschrift hinweg. Radien folgen
jetzt der Staffelung des BudgetManagers, der Design-Vorlage der Suite.

## 0.5.11 – Signierte Releases und eine sichtbare Brücke

### Die Suite baut endlich mit aktuellen Modulen

Der Host zog seine Module aus festgeschriebenen Ständen — BudgetManager 2.2.63,
FPM 1.0.3, FreizeitManager 0.1.1 —, während die Programme längst weiter waren.
Wer den LifePlanner installierte, bekam eine fünf Stände alte Suite.

- Die Lockdatei zeigt jetzt auf BudgetManager 2.2.68, FPM 1.0.8 und
  FreizeitManager 0.1.6.
- Die Tests nennen keine festen Versionen mehr, sondern prüfen, dass Lockdatei
  und Release-Workflow übereinstimmen. Genau weil sie Versionen nachschrieben,
  blieb der Rückstand so lange unbemerkt.

### Die Integrationsseite zeigt beide Richtungen der Brücke

Bisher wurde nur `fpm_to_budgetmanager.jsonl` gelesen. Die Gegenrichtung und
die Sparziel-Spiegelung des BudgetManagers sah der Host gar nicht an — genau
die beiden Dateien, deren Ausbleiben als „der Transfer funktioniert nicht"
auffällt.

- Alle drei Dateien werden gelesen und einzeln ausgewiesen.
- Unterschieden wird zwischen „Datei fehlt" und „Datei ist leer": Fehlt sie,
  hat das schreibende Programm noch nichts abgelegt — dann liegt es dort und
  nicht an der Brücke.
- Ungültige Zeilen werden gemeldet statt verschluckt.

### Releases werden signiert

Der Erst-Release ging bewusst unsigniert heraus; der Workflow erzwang das
sogar. Der Updater prüft seine Manifeste aber fail-closed — solange keine
Signatur mitkommt, ist jedes weitere Release für eine installierte Fassung
wertlos.

- Die Signierschlüssel liegen jetzt im Repository hinterlegt.
- Beide Gates kehren sich um: Windows und Linux brechen ab, wenn die Signatur
  *fehlt*, statt wenn sie da ist.

### Systemvorgabe wählt aus einem Designpaar

Die Auswahl „Systemvorgabe" gab es schon, aber sie liess offen, welche Designs
gemeint sind. Zu einem dunklen Profil gibt es kein helles Gegenstück, das der
Host erfinden könnte — darum wählen Sie beide Seiten selbst.

## 0.5.9 – Gemeinsamer Designkatalog

### Ein gemeinsamer Designkatalog

LifePlanner, BudgetManager, FountainPen Manager und FreizeitManager liefern
jetzt dieselben **26 Designs** aus — byteweise dieselben Profildateien, erzeugt
und geprüft von `tools/design_sync.py`.

**Warum das nötig war.** Vorher kannten BudgetManager und LifePlanner 26 Designs
mit 29 Rollen, FPM und FreizeitManager sieben mit 38–40. Wer im LifePlanner ein
Design wählte, das ein Modul nicht selbst mitbrachte, bekam dort dessen
Hintergrund, aber Standardblau für Akzent, Karten und Statusfarben — was der
Host nicht mitliefert, fällt im Modul auf das eingebaute Profil zurück. Und drei
Designs trugen in beiden Lagern verschiedene Namen (`Kontrast - Schwarz/Weiß`
gegen `Kontrast Schwarzweiss`, `Hell - Warm (Sepia)` gegen `Warm Sepia - Hell`,
`Dunkel - OLED (Kontrastarm)` gegen `OLED Schwarz`), sodass das Modul das
Hostprofil unter einem Namen suchte, den es selbst nicht führte.

- **55 Rollen je Profil** — ein Kern von 33 für alle Programme plus die
  Bedeutungsfarben der einzelnen. Fehlende Rollen wurden nicht erfunden, sondern
  aus vorhandenen Farben desselben Profils abgeleitet; handverlesene Werte
  blieben unangetastet. Wo zwei Programme dieselbe Rolle unterschiedlich
  führten, gilt der Wert des Hosts.
- **Der Name des Hosts gilt.** Gespeicherte Einstellungen lösen über Aliase
  weiterhin auf.
- **Die Schriftgröße bedeutet überall dasselbe:** 10 heißt normal. Der
  FreizeitManager zeichnet dabei weiterhin 14 Punkt und rechnet den gemeinsamen
  Wert als Faktor darauf um.

### Lesbarkeit ist jetzt Bedingung, nicht Zufall

- **4,5:1 für jede Schrift auf jedem Grund** — die strengste der vier bisherigen
  Schwellen, übernommen aus dem BudgetManager.
- **Die Seitenleiste folgt der Helligkeit des Profils.** Schrift, die auf ihr
  nicht lesbar ist, wird verworfen und neu abgeleitet — in „Solarized – Hell“
  war sie exakt die Farbe der Leiste selbst.
- **Signalfarben heben sich mit mindestens 2,6:1 von der Karte ab.** Ein
  abgeleitetes Gelb erreichte 1,77:1 und war als Ampelfarbe wertlos.
- **Gedimmte Schrift unterscheidet sich messbar von der normalen.** In
  „Solarized – Dunkel“ waren `text` und `text_gedimmt` buchstäblich derselbe Wert.
- **Farbfehlsichtigkeit wird geprüft.** Erfolg/Warnung/Gefahr, die Budget-Typen,
  die vier FPM-Bereiche und die fünf Dringlichkeitsstufen müssen auch bei
  Protanopie, Deuteranopie und Tritanopie unterscheidbar bleiben (Simulation nach
  Viénot/Brettel/Mollon 1999). Vorher waren **348 von 1716 Farbpaaren** nicht
  auseinanderzuhalten, teils sogar identisch — jetzt keines. Repariert wird über
  Helligkeit und Sättigung, nie über den Farbton; der geht dabei gerade verloren.

### Werkzeug

- `tools/design_sync.py check` prüft die eigenen Profile, `build` erzeugt den
  Katalog in allen vier Programmen, `preview` schreibt eine HTML-Übersicht (mit
  den Signalfarben, wie Farbfehlsichtige sie sehen), und `new --name … --akzent …`
  baut aus einer Akzentfarbe ein vollständiges, regelkonformes Design.
- **`build` ist ein Fixpunkt.** Jede Profildatei führt mit, welche Rollen erzeugt
  (`_abgeleitet`) und welche nur nachjustiert wurden (`_vorlage`) — sonst wanderte
  der Katalog mit jedem Lauf ein Stück weiter, statt reproduzierbar zu sein.
- `tests/test_shared_design.py` hält den Katalog zusammen;
  `docs/GEMEINSAMES_DESIGN.md` erklärt Aufbau und Regeln.


### Weiteres
- Der Host verteilt nur noch Profile, die jedes Modul vollständig darstellen
  kann — `lifeplanner.theme.v1` trägt jetzt alle 55 Rollen.
- Neu: `tools/sync_version.py`. Die Version stand an sechs Stellen und musste von
  Hand nachgezogen werden, in der Workflow-Datei allein neunmal.

## 0.5.8 – Das erste Modul lässt sich wieder installieren

- **Modulinstallation repariert.** Unter Linux meldete 0.5.7 nach jedem Installationsversuch `Modulordner fehlt: …/payload/modules`. `apply_plan.py` verschiebt ein Modul mit `os.replace` nach `modules/<id>`, legte den Ordner `modules/` aber nie an — und eine Core-Installation ohne Module bringt keinen leeren Ordner mit. Damit scheiterte das **erste** Modul jeder frischen Installation zuverlässig, egal welches; zurück blieben nur `.__lifeplanner_update_*`-Reste. Das Zielverzeichnis wird jetzt angelegt.
- Ein fehlender Modulordner ist kein Fehler mehr, sondern schlicht „noch keine Module installiert“. Bisher warnte der Start mit einer Meldung, die einen Defekt nahelegte, wo keiner war.
- **Die Version steht nur noch an einer Stelle.** `tools/build_release.py`, `tools/build_linux_release.py` und die drei User-Agent-Zeichenketten lesen sie aus `lifeplanner_core.APP_VERSION`, statt sie zu wiederholen; der Windows-Paketest prüft gegen dieselbe Quelle statt gegen eine eingetippte Zahl.

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
