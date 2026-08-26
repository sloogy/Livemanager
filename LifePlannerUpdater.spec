# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)

# Der Updater laeuft sichtbar, waehrend der Host geschlossen ist - ohne
# Symbol steht er dort als namenloses Fenster. None heisst "kein Symbol".
ico = root / "lifeplanner_core" / "resources" / "icons" / "lifeplanner.ico"
icon_datei = str(ico) if ico.is_file() else None

a = Analysis(
    [str(root / "update_helper.py")],
    pathex=[str(root)],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["PySide6"],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="LifePlannerUpdater",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_datei,
)
