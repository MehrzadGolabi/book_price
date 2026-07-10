# -*- mode: python ; coding: utf-8 -*-
# Build: .venv\Scripts\python.exe -m PyInstaller BookCostCalculator.spec
# Bundles resources/ into the one-file exe; bookcost/resources.py finds them
# via sys._MEIPASS at runtime.

a = Analysis(
    ['main.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('resources/style.qss', '.'),
        ('resources/tahoma.ttf', '.'),
        ('resources/arial.ttf', '.'),
        ('resources/logo.png', '.'),
    ],
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
    a.binaries,
    a.datas,
    [],
    name='BookCostCalculator',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
