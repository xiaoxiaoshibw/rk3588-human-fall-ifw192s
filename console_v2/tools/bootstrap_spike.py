"""Portable, version-pinned R2 tools. No global installation or device changes."""
import concurrent.futures
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / 'console_v2/.tools'
OUT = ROOT / 'docs/evidence/2026-10-24_console_v2_r2'
TOOLS.mkdir(parents=True, exist_ok=True)
OUT.mkdir(parents=True, exist_ok=True)


def fetch(url, path, expected=None):
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        print('DOWNLOAD', path.name, flush=True)
        with urllib.request.urlopen(url, timeout=90) as response, path.open('xb') as target:
            while True:
                block = response.read(1 << 20)
                if not block:
                    break
                target.write(block)
    data_hash = hashlib.sha512(path.read_bytes()).hexdigest()
    if expected and data_hash.lower() != expected.lower():
        raise ValueError('SHA512 mismatch: ' + str(path))
    record = dict(url=url, path=str(path.relative_to(ROOT)), bytes=path.stat().st_size, sha512=data_hash,
                  expected_sha512=expected)
    (OUT / (path.name + '.download.json')).write_text(json.dumps(record, indent=2), encoding='utf-8')
    return path


def sdk():
    metadata = json.load(urllib.request.urlopen('https://builds.dotnet.microsoft.com/dotnet/release-metadata/8.0/releases.json', timeout=60))
    version = '8.0.426'
    release = next(r for r in metadata['releases'] if r.get('sdk', {}).get('version') == version)
    file = next(f for f in release['sdk']['files'] if f['rid'] == 'win-x64' and f['name'].endswith('.zip'))
    package = fetch(file['url'], TOOLS / 'downloads' / ('dotnet-sdk-' + version + '-win-x64.zip'), file['hash'])
    destination = TOOLS / 'dotnet'
    if not (destination / 'sdk' / version / 'dotnet.dll').is_file():
        with zipfile.ZipFile(package) as archive:
            archive.extractall(destination)
    print('SDK_READY', version, flush=True)


def qmlnet():
    for name in ['qml.net', 'qml.net.windowsbinaries']:
        versions = json.load(urllib.request.urlopen('https://api.nuget.org/v3-flatcontainer/' + name + '/index.json', timeout=60))['versions']
        stable = [v for v in versions if '-' not in v]
        version = stable[-1]
        url = 'https://api.nuget.org/v3-flatcontainer/{0}/{1}/{0}.{1}.nupkg'.format(name, version)
        package = fetch(url, TOOLS / 'downloads' / (name + '.' + version + '.nupkg'))
        destination = TOOLS / 'qmlnet-packages' / (name + '.' + version)
        if not destination.exists():
            with zipfile.ZipFile(package) as archive:
                archive.extractall(destination)
        print('QMLNET_PACKAGE', name, version, flush=True)
    for name in ['RuntimeManager.cs', 'RuntimeManager.Configure.cs', 'RuntimeManager.Discovery.cs']:
        fetch('https://raw.githubusercontent.com/qmlnet/qmlnet/master/src/net/Qml.Net/Runtimes/' + name,
              OUT / name)


def aqt():
    target = TOOLS / 'python'
    argv = [sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check', '--target', str(target), 'aqtinstall==3.3.0']
    if not (target / 'aqt').is_dir():
        result = subprocess.run(argv, cwd=ROOT, capture_output=True)
        (OUT / 'pip_aqt.stdout').write_bytes(result.stdout)
        (OUT / 'pip_aqt.stderr').write_bytes(result.stderr)
        assert result.returncode == 0
    print('AQT_READY', flush=True)


if __name__ == '__main__':
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results = [pool.submit(task) for task in [sdk, qmlnet, aqt]]
        for result in results:
            result.result()
