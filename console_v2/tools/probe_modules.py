"""Read native loaded-module paths with PSAPI, including the managed service process."""
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
import subprocess
import time
import psutil
from run_spike_command import ROOT, OUT, environment


def modules(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    api = ctypes.WinDLL('psapi', use_last_error=True)
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    api.EnumProcessModulesEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.HMODULE), wintypes.DWORD,
                                       ctypes.POINTER(wintypes.DWORD), wintypes.DWORD]
    api.GetModuleFileNameExW.argtypes = [wintypes.HANDLE, wintypes.HMODULE, wintypes.LPWSTR, wintypes.DWORD]
    handle = kernel.OpenProcess(0x410, False, pid)
    if not handle: return dict(pid=pid, error=ctypes.get_last_error())
    try:
        array = (wintypes.HMODULE * 2048)()
        needed = wintypes.DWORD()
        if not api.EnumProcessModulesEx(handle, array, ctypes.sizeof(array), ctypes.byref(needed), 3):
            return dict(pid=pid, error=ctypes.get_last_error())
        assert needed.value <= ctypes.sizeof(array)
        paths = []
        for module in array[:needed.value // ctypes.sizeof(wintypes.HMODULE)]:
            buffer = ctypes.create_unicode_buffer(32768)
            if api.GetModuleFileNameExW(handle, module, buffer, len(buffer)): paths.append(buffer.value)
        return dict(pid=pid, paths=paths, psapi_status='PASS')
    finally:
        kernel.CloseHandle(handle)


def main():
    out = OUT / 'module_probe'
    out.mkdir()
    env = environment()
    env['PATH'] = str(Path(os.environ['SystemRoot']) / 'System32')
    env.pop('DOTNET_ROOT', None)
    for key in ['QT_PLUGIN_PATH', 'QML_IMPORT_PATH', 'QML2_IMPORT_PATH']: env.pop(key, None)
    env['DOTNET_BUNDLE_EXTRACT_BASE_DIR'] = str(ROOT/'console_v2/.tools/extracted/module-native')
    argv = [str(ROOT/'console_v2/spike/package-single/SpikeService.exe'), '--extract-root',
            str(ROOT/'console_v2/.tools/extracted/module-qt'), '--session', str(ROOT/'data/sessions/cap_20261018_110029'),
            '--count', '500000', '--duration', '5', '--report', str(out/'result.json')]
    with (out/'stdout.log').open('xb') as stdout, (out/'stderr.log').open('xb') as stderr:
        child = subprocess.Popen(argv, env=env, stdout=stdout, stderr=stderr, creationflags=subprocess.CREATE_NO_WINDOW)
        process = psutil.Process(child.pid)
        marker = Path(str(out/'result.json')+'.first.json')
        limit = time.monotonic()+40
        while child.poll() is None and not marker.exists() and time.monotonic()<limit: time.sleep(.02)
        snapshots = []
        for p in [process]+process.children(recursive=True):
            entry = modules(p.pid)
            try: entry['psutil_paths']=[m.path for m in p.memory_maps()]
            except psutil.Error as error: entry['psutil_error']=type(error).__name__
            snapshots.append(entry)
        code = child.wait(timeout=30)
    record=dict(argv=argv, exit_code=code, snapshots=snapshots, path=env['PATH'], dotnet_root=None,
                scope='Supplemental dependency inspection; excluded from formal FPS/startup runs')
    (OUT/'NATIVE_MODULES.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    assert code==0 and all(s.get('psapi_status')=='PASS' for s in snapshots)
    print(json.dumps([dict(pid=s['pid'],modules=len(s['paths']),runtime=[p for p in s['paths'] if 'coreclr' in p.lower() or 'hostpolicy' in p.lower()]) for s in snapshots],ensure_ascii=False))


if __name__=='__main__': main()
