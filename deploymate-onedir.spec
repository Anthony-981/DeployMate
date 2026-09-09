# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys

from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT

project_root = Path(SPECPATH)
icon_file = "logo.ico" if sys.platform == "win32" else "logo.icns"
icon_path = project_root / icon_file
if not icon_path.exists():
    icon_path = project_root / "logo.png"

a = Analysis(
    [str(project_root / "src" / "main.py")],
    pathex=[str(project_root)],
    binaries=[],
    datas=[(str(project_root / "logo.png"), ".")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[str(project_root / "pyinstaller_runtime_hook.py")],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DeployMate",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    icon=str(icon_path),
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="DeployMate",
)
