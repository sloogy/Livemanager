# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)

# Das ist die Datei, die der Nutzer unter Windows anklickt und die in der
# Taskleiste steht - sie braucht das Symbol am dringendsten. None heisst fuer
# PyInstaller "kein Symbol": ein Entwickler-Build ohne Bilder bricht deshalb
# nicht ab.
ico = root / "lifeplanner_core" / "resources" / "icons" / "lifeplanner.ico"
icon_datei = str(ico) if ico.is_file() else None

a = Analysis(
    [str(root / "windows_launcher.py")],
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
    name="LifePlanner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=icon_datei,
)
