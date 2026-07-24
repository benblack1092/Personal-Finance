# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build spec for Personal Finance.

Build (from the project root):
    pyinstaller packaging/PersonalFinance.spec

Produces a single-file executable in dist/ (PersonalFinance.exe on Windows).
"""
import os

from PyInstaller.utils.hooks import collect_submodules

# Project root = the directory this spec is run from.
ROOT = os.path.abspath(os.getcwd())

# Bundle the whole static site (HTML/CSS/JS + vendored Chart.js) as data.
datas = [(os.path.join(ROOT, "static"), "static")]

# uvicorn, anyio and SQLAlchemy import parts of themselves dynamically, which
# PyInstaller's static analysis can miss — collect them explicitly.
hiddenimports = (
    collect_submodules("uvicorn")
    + [
        "anyio._backends._asyncio",
        "sqlalchemy.dialects.sqlite",
        "multipart",  # python-multipart, used by FastAPI form parsing
    ]
)

_icon = os.path.join(ROOT, "packaging", "icon.png")
icon = _icon if os.path.exists(_icon) else None


a = Analysis(
    [os.path.join(ROOT, "launcher.py")],
    pathex=[ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
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
    a.binaries,
    a.datas,
    [],
    name="PersonalFinance",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    runtime_tmpdir=None,
    console=True,  # keep a console window so users can see logs / close to quit
    icon=icon,
)
