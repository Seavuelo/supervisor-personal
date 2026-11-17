# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import os

block_cipher = None
project_root = Path.cwd()

added_files = [
    (str(project_root / 'src' / 'supervisor' / 'ui' / 'index.html'), 'supervisor/ui'),
    (str(project_root / 'src' / 'supervisor' / 'ui' / 'assets'), 'supervisor/ui/assets'),
]

a = Analysis(
    ['run_seeu.py'],
    pathex=[str(project_root / 'src')],
    binaries=[],
    datas=added_files,
    hiddenimports=[
        'PyQt6',
        'PyQt6.QtCore',
        'PyQt6.QtGui',
        'PyQt6.QtWidgets',
        'PyQt6.QtWebEngineWidgets',
        'PyQt6.QtWebEngineCore',
        'webview',
        'webview.platforms.qt',
        'google.genai',
        'dotenv',
        'keyring.backends.Windows',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['tkinter', 'matplotlib', 'numpy', 'scipy', 'unittest'],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='seeU',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon=str(project_root / 'assets' / 'icon.ico'),
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='seeU'
)
