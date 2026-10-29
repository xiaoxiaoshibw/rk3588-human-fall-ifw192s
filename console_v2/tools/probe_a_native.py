"""Inspect the released A native bridge, then test loading beside real Qt 6."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import PySide6
from PySide6.QtCore import qVersion

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/evidence/2026-10-24_console_v2_r2'
DLL = ROOT / 'console_v2/.tools/qmlnet-packages/qml.net.windowsbinaries.0.11.0/runtimes/win-x64/native/QmlNet.dll'
qt = Path(PySide6.__file__).parent
result = subprocess.run(['D:/APPS/mingw64/bin/objdump.exe', '-p', str(DLL)], capture_output=True)
assert result.returncode == 0
(OUT / 'A_QmlNet_PE_IMPORTS.txt').write_bytes(result.stdout)
imports = re.findall(r'DLL Name:\s*([^\s]+)', result.stdout.decode('utf-8', errors='replace'))
with os.add_dll_directory(str(qt)):
    try:
        ctypes.WinDLL(str(DLL), winmode=0x1100)
        loaded, error = True, None
    except OSError as exc:
        loaded, error = False, str(exc)
record = dict(package='Qml.Net.WindowsBinaries/0.11.0', sha256=hashlib.sha256(DLL.read_bytes()).hexdigest(),
              imports=imports, available_qt=qVersion(), qt6_directory=str(qt), native_load=loaded, error=error,
              conclusion='Released bridge imports Qt5 DLLs; it is not a Qt6 ABI bridge. No Qt6 fork was implemented.',
              scope='PE imports plus native load, not a .NET/QML window or FPS test')
(OUT / 'A_NATIVE_PROBE.json').write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding='utf-8')
print(json.dumps(record, ensure_ascii=False))
