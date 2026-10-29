"""Range download of the same pinned Microsoft archive; full SHA512 required."""
import concurrent.futures
import hashlib
import json
from pathlib import Path
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'docs/evidence/2026-10-24_console_v2_r2'
BASE = ROOT / 'console_v2/.tools'
URL = 'https://dotnetcli.blob.core.windows.net/dotnet/Sdk/8.0.426/dotnet-sdk-8.0.426-win-x64.zip'


def main():
    metadata = json.load(urllib.request.urlopen('https://builds.dotnet.microsoft.com/dotnet/release-metadata/8.0/releases.json', timeout=60))
    release = next(r for r in metadata['releases'] if r.get('sdk', {}).get('version') == '8.0.426')
    file = next(f for f in release['sdk']['files'] if f['rid'] == 'win-x64' and f['name'].endswith('.zip'))
    size = int(urllib.request.urlopen(urllib.request.Request(URL, method='HEAD'), timeout=30).headers['Content-Length'])
    partroot = BASE / 'downloads/sdk-parts'
    partroot.mkdir(parents=True, exist_ok=True)
    step = 4 << 20

    def part(start):
        end = min(start + step, size) - 1
        path = partroot / str(start)
        if path.exists() and path.stat().st_size == end - start + 1:
            return path
        for attempt in range(6):
            have = path.stat().st_size if path.exists() else 0
            if have == end - start + 1:
                print('SDK_PART', start, have, flush=True)
                return path
            assert have < end - start + 1
            position = start + have
            req = urllib.request.Request(URL, headers={'Range': 'bytes=%d-%d' % (position, end)})
            try:
                with urllib.request.urlopen(req, timeout=60) as response, path.open('ab') as target:
                    assert response.status == 206 and response.headers['Content-Range'].startswith('bytes %d-%d/' % (position, end))
                    while True:
                        data = response.read(65536)
                        if not data:
                            break
                        target.write(data)
                assert path.stat().st_size == end - start + 1
            except (OSError, AssertionError) as error:
                print('SDK_RETRY', start, attempt, type(error).__name__, flush=True)
                time.sleep(1)
        raise OSError('SDK range incomplete: %d' % start)

    starts = list(range(0, size, step))
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(part, starts))
    archive = BASE / 'downloads/dotnet-sdk-8.0.426-blob-win-x64.zip'
    h = hashlib.sha512()
    with archive.open('wb') as target:
        for start in starts:
            data = (partroot / str(start)).read_bytes()
            h.update(data)
            target.write(data)
    assert archive.stat().st_size == size and h.hexdigest().lower() == file['hash'].lower()
    with zipfile.ZipFile(archive) as package:
        package.extractall(BASE / 'dotnet')
    (OUT / 'sdk_parallel.download.json').write_text(json.dumps(dict(url=URL, official_hash_url=file['url'],
        version='8.0.426', bytes=size, sha512=h.hexdigest(), expected_sha512=file['hash'], verified=True), indent=2), encoding='utf-8')
    print('SDK_READY 8.0.426 SHA512 VERIFIED', flush=True)


if __name__ == '__main__':
    main()
