"""Embed a dependency-checked Qt folder in the self-contained C# B launcher."""
import hashlib
import json
from pathlib import Path
import zipfile
import sys
from run_spike_command import ROOT, OUT, run

if (OUT / 'QT_PAYLOAD.json').exists():
    raise FileExistsError('Set CONSOLEV2_SPIKE_OUT to a new measurement directory')
package = ROOT / 'console_v2/spike/package-dev'
service = ROOT / 'console_v2/spike/service'
files = sorted(p for p in package.rglob('*') if p.is_file())
assert (package / 'platforms/qwindows.dll').is_file()
assert (package / 'QtSpike.exe').is_file()
assert not any(p.name in ('meta.json', 'points.bin') for p in files)
manifest = {p.relative_to(package).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
(service / 'payload.manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
with zipfile.ZipFile(service / 'payload.zip', 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
    for path in files:
        archive.write(path, path.relative_to(package).as_posix())
with (OUT / 'QT_PAYLOAD.json').open('x', encoding='utf-8') as report:
    json.dump(dict(files=len(files), unpacked_bytes=sum(p.stat().st_size for p in files),
                   zip_bytes=(service / 'payload.zip').stat().st_size, manifest=manifest), report, indent=2)
raise SystemExit(run(sys.argv[1] if len(sys.argv) > 1 else 'single_publish_01', [str(ROOT / 'console_v2/.tools/dotnet/dotnet.exe'), 'publish',
    str(service / 'SpikeService.csproj'), '-c', 'Release', '-r', 'win-x64', '--self-contained', 'true',
    '-p:PublishSingleFile=true', '-p:IncludeNativeLibrariesForSelfExtract=true', '-p:DebugType=embedded',
    '-o', str(ROOT / 'console_v2/spike/package-single')]))
