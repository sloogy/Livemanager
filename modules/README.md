# Laufzeitmodule – nicht in diesem Repository versionieren

Dieser Ordner enthält ausschließlich **installierte oder lokal verknüpfte Laufzeitmodule**.
Der Quellcode von BudgetManager und FPM gehört nicht in das LifePlanner-Repository.

Im Entwicklungsbetrieb werden die separaten Repositories über
`tools/prepare_dev_modules.py` als Symlink, Windows-Junction oder ignorierte Kopie
eingebunden. Im Windows-Release kopiert die Buildpipeline ausschließlich die gebauten
Binärartefakte in diesen Ordner.
