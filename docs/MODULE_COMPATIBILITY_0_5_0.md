# Modulkompatibilität LifePlanner 0.5.0

Freigegebene Kombination:

- BudgetManager 2.2.61
- FPM 0.3.05

Beide Module besitzen `module.json`, profilbezogene Datenpfade und die gemeinsame JSONL-Bridge. Die LifePlanner-Releaseworkflows bauen daraus Windows-/Linux-`.lpmodule`-Assets. Beim ersten Release sind diese über den ausdrücklichen Schalter `--allow-unsigned` nicht signiert und müssen lokal manuell bestätigt werden. Beim Start durch LifePlanner ist der interne Modul-Updater deaktiviert.

## Private GitHub-Repositories

Für reine Downloadrechte einen Fine-grained GitHub PAT mit **Contents: Read-only** für die beiden Modul-Repositories verwenden. Der Token wird nicht gespeichert. Vor dem Start des Installers eine der folgenden Variablen setzen:

```text
LIFEPLANNER_GITHUB_TOKEN=<token>
```

oder sicherer über eine nur für den Benutzer lesbare Datei:

```text
LIFEPLANNER_GITHUB_TOKEN_FILE=/pfad/zur/token-datei
```

Unter Linux muss die Datei Modus `0600` besitzen.

## Linux/Fedora

`tools/build_linux_release.py` und der Workflow `linux-release.yml` erzeugen einen
portablen Linux-Build inklusive beider Module, zentralem Updater und für den ersten
Release ausdrücklich unsignierten `Linux_x86_64.lpmodule`-Komponenten. Für Linux ist das `tar.gz` die bevorzugte
Auslieferung, weil es Unix-Ausführungsrechte zuverlässig bewahrt.
