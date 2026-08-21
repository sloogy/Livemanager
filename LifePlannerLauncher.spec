# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)

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
)
