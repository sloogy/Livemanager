# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

root = Path(SPECPATH)
datas = []
public_key = root / "lifeplanner_core" / "resources" / "lifeplanner_update_public_key.b64"
if public_key.is_file():
    datas.append((str(public_key), "resources"))

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
    name="LifePlanner",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
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
