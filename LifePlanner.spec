# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

root = Path(SPECPATH)
core_exe_name = "LifePlannerCore" if sys.platform.startswith("win") else "LifePlanner"
datas = []
# Ohne diesen Anker lehnt der Updater fail-closed jedes Update ab. Der
# Release-Bau legt ihn vorher an (_materialize_host_public_key); fehlt er,
# ist das ein Entwickler-Build - dann sagt der Bau es wenigstens.
public_key = root / "lifeplanner_core" / "resources" / "lifeplanner_update_public_key.b64"
if public_key.is_file():
    datas.append((str(public_key), "resources"))
else:
    print("WARNUNG: LifePlanner.spec: kein Update-Public-Key - dieser Build kann sich nicht aktualisieren.")
themes = root / "lifeplanner_core" / "themes"
if themes.is_dir():
    datas.append((str(themes / "*.json"), "themes"))

# Die Sprachdateien fehlten im gefrorenen Build: lifeplanner_core/i18n liest
# sie ueber Path(__file__).parent, und was PyInstaller nicht ausdruecklich
# mitnimmt, ist dort nicht da. Der Loader faengt das ab und zeigt dann den
# Schluessel statt des Textes - die Oberflaeche war komplett unbeschriftet,
# ohne dass etwas abstuerzte. FPM.spec hatte das Muster laengst richtig.
# Gelesen wird das Verzeichnis, nicht eine abgeschriebene Sprachliste: Eine
# vierte Sprache soll nicht daran scheitern, dass sie hier jemand vergisst.
i18n = root / "lifeplanner_core" / "i18n"
for datei in sorted(i18n.glob("*.json")):
    datas.append((str(datei), "lifeplanner_core/i18n"))

# Die Programmbilder. lifeplanner_core/branding.py sucht sie unter "icons"
# neben der ausfuehrbaren Datei beziehungsweise im Entpackverzeichnis - der
# Zielordner heisst deshalb genauso. Auch hier wird der Ordner gelesen und
# keine Dateiliste abgeschrieben: Ein viertes Modul bringt sein Bild mit,
# ohne dass jemand diese Datei anfassen muss. Die unskalierten Quellen unter
# "original" bleiben draussen - sie gehoeren zu tools/generate_icons.py, nicht
# in den Betrieb, und wuerden das Paket um zwei Megabyte aufblaehen.
icons = root / "lifeplanner_core" / "resources" / "icons"
if icons.is_dir():
    for datei in sorted(icons.glob("*.png")) + sorted(icons.glob("*.ico")):
        datas.append((str(datei), "icons"))
    for datei in sorted((icons / "modules").glob("*.png")):
        datas.append((str(datei), "icons/modules"))
else:
    print("WARNUNG: LifePlanner.spec: keine Programmbilder - dieser Build laeuft ohne Symbole.")

# Das Symbol der ausfuehrbaren Datei selbst. PyInstaller nimmt None als
# "kein Symbol" - ein Entwickler-Build ohne Bilder bricht deshalb nicht ab.
ico = icons / "lifeplanner.ico"
icon_datei = str(ico) if ico.is_file() else None

a = Analysis(
    [str(root / "main.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=core_exe_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_datei,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="LifePlanner",
)
