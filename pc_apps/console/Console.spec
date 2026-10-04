# -*- mode: python ; coding: utf-8 -*-
# 从 pc_apps/console/ 目录跑: python -m PyInstaller --noconfirm Console.spec
# (PyInstaller spec 无 __file__/SPECPATH, 路径相对于 cwd; 固定在此目录跑)

a = Analysis(
    ['console_gui.py'],
    pathex=[],
    binaries=[],
    datas=[('console.html', '.'), ('console_icon.png', '.'),
           (r'D:\Code\ldiar\pc_apps\human_replay', 'human_replay')],
    hiddenimports=['json', 'urllib.request', 'webbrowser'],
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
    name='Console',
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
    icon=['console_icon.ico'],
)
