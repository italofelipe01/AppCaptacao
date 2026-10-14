# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path


project_root = Path.cwd()
datas = [
    (str(project_root / "project"), "project"),
]

hiddenimports = [
    "customtkinter",
    "waitress",
    "pyodbc",
    "pymssql",
    "win32security",
    "win32api",
    "win32con",
    "pywintypes",
]


a = Analysis(
    ["src/app_captacao/desktop/desktop_app.py"],
    pathex=[str(project_root / "src")],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="AppCaptacao",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
