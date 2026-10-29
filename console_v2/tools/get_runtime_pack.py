"""Acquire a stalled official NuGet runtime pack via resumable ranges and catalog SHA512."""
import base64
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import zipfile
from run_spike_command import ROOT, OUT

NAME = 'microsoft.windowsdesktop.app.runtime.win-x64'
VERSION = '8.0.32'
URL = f'https://api.nuget.org/v3-flatcontainer/{NAME}/{VERSION}/{NAME}.{VERSION}.nupkg'


def main():
    registration = json.load(urllib.request.urlopen(f'https://api.nuget.org/v3/registration5-semver1/{NAME}/{VERSION}.json', timeout=30))
    catalog = json.load(urllib.request.urlopen(registration['catalogEntry'], timeout=60))
    assert catalog['packageHashAlgorithm'] == 'SHA512'
    expected = base64.b64decode(catalog['packageHash'])
    size = int(urllib.request.urlopen(urllib.request.Request(URL, method='HEAD'), timeout=30).headers['Content-Length'])
    root = ROOT / 'console_v2/.tools/downloads/windowsdesktop-parts'
    root.mkdir(parents=True, exist_ok=True)
    step = 4 << 20
    def part(start):
        end = min(size, start + step) - 1
        path = root / str(start)
        for attempt in range(6):
            have = path.stat().st_size if path.exists() else 0
            if have == end - start + 1: return path
            request = urllib.request.Request(URL, headers={'Range': f'bytes={start + have}-{end}'})
            try:
                with urllib.request.urlopen(request, timeout=60) as response, path.open('ab') as stream:
                    assert response.status == 206
                    while True:
                        data = response.read(65536)
                        if not data: break
                        stream.write(data)
                assert path.stat().st_size == end - start + 1
            except (OSError, AssertionError) as error:
                print('RETRY', start, attempt, type(error).__name__, flush=True)
                time.sleep(1)
        raise OSError('Incomplete runtime package range')
    starts = list(range(0, size, step))
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool: list(pool.map(part, starts))
    feed = ROOT / 'console_v2/.tools/nuget-local'
    feed.mkdir(exist_ok=True)
    package = feed / (NAME + '.' + VERSION + '.nupkg')
    digest = hashlib.sha512()
    with package.open('wb') as target:
        for start in starts:
            data = (root / str(start)).read_bytes(); digest.update(data); target.write(data)
    assert digest.digest() == expected
    with zipfile.ZipFile(package) as archive: assert archive.testzip() is None
    (OUT/'runtime_pack.download.json').write_text(json.dumps(dict(url=URL, catalog=registration['catalogEntry'],
        bytes=size, sha512=digest.hexdigest(), catalog_sha512=expected.hex(), verified=True),indent=2),encoding='utf-8')
    print('Runtime pack SHA512 and ZIP CRC verified',flush=True)


if __name__ == '__main__': main()
