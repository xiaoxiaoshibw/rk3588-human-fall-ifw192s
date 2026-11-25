"""Create the ConsoleV2 source bundle for LAN colleagues (build-it-themselves).

Only source, build scripts, configuration and docs are copied: no data/, captures/,
docs/evidence/, .tools/, node_modules/, build outputs, logs or user state.  The
bundle layout mirrors the repository, and `编译并启动.cmd` at the bundle root builds
and starts the app (toolchain discovery in launcher/BuildAndRun.ps1).

Usage:
    python -B -W error console_v2/tools/make_source_bundle.py --out dist/console_v2_source_20261030
    python -B -W error console_v2/tools/make_source_bundle.py --out ... --zip

Output directories are created, never overwritten.  The zip is deterministic
(sorted entries, fixed timestamps) and a MANIFEST.json records every file.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
EXCLUDE_DIRS = {'__pycache__', '.pytest_cache', '.mypy_cache'}
EXCLUDE_SUFFIXES = {'.pyc', '.pyo', '.pdb', '.log'}
ZIP_EPOCH = (2020, 1, 1, 0, 0, 0)

# Directories copied whole (with per-entry pruning).
TREES = [
    'console_v2',
    'pc_apps/range_fall',
    'pc_apps/annotator_v2/dist',
    'src/human_fall_detection/core',
    'src/human_fall_detection/scripts',
    'src/human_fall_detection/config',
    'src/inno_lidar_ros/config/ifw192s',
    'docs/console_v2',
]
# Individual files copied as-is.
FILES = [
    'console_v2/app/video_worker.py',
    'console_v2/app/local_replay_worker.py',
    'pc_apps/annotator_v2/server.py',
    'pc_apps/console/joint_capture.py',
    'pc_apps/console/joint_capture.html',
    'tools/range_experiment.py',
    'tools/sync_audit.py',
    'AGENTS.md',
    'BRANCHES.md',
]
# console_v2 subtrees that are development-only or generated.
CONSOLE_SKIP = {
    'console_v2/.tools',
    'console_v2/user_data',
    'console_v2/app/build',
    'console_v2/app/build-dist',
    'console_v2/app/runtime',
    'console_v2/app/service/bin',
    'console_v2/app/service/obj',
    'console_v2/spike/build',
    'console_v2/spike/package-dev',
    'console_v2/spike/package-single',
    'console_v2/spike/a_probe',
    'console_v2/spike/native',
    'console_v2/spike/service/bin',
    'console_v2/spike/service/obj',
    'console_v2/spike/service/payload.zip',
    'console_v2/spike/service/payload.manifest.json',
    'console_v2/release',
}


def relative(path):
    return path.relative_to(ROOT).as_posix()


def skip(rel):
    parts = rel.split('/')
    if any(part in EXCLUDE_DIRS for part in parts):
        return True
    if any(rel == item or rel.startswith(item + '/') for item in CONSOLE_SKIP):
        return True
    return Path(rel).suffix.lower() in EXCLUDE_SUFFIXES


def collect():
    paths = set()
    for tree in TREES:
        base = ROOT / tree
        if not base.is_dir():
            raise FileNotFoundError('missing source tree: ' + tree)
        for path in base.rglob('*'):
            if path.is_file() and not skip(relative(path)):
                paths.add(relative(path))
    for item in FILES:
        path = ROOT / item
        if not path.is_file():
            raise FileNotFoundError('missing source file: ' + item)
        paths.add(item)
    # AppService.csproj links ../../spike/service/FrameCodec.cs.
    paths.add('console_v2/spike/service/FrameCodec.cs')
    return sorted(paths)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def git(*args):
    try:
        return subprocess.run(['git', *args], cwd=ROOT, capture_output=True,
                              text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def git_head():
    return git('rev-parse', 'HEAD')


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf8')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--zip', action='store_true')
    args = parser.parse_args()
    out = args.out if args.out.is_absolute() else (ROOT / args.out)
    out = out.resolve()
    if out.exists():
        raise SystemExit('输出目录已存在，不覆盖：%s' % out)
    if ROOT == out or ROOT in out.parents:
        # Allowed under dist/ only, and never inside data/captures.
        rel = out.relative_to(ROOT).as_posix()
        if rel.startswith('data/') or rel.startswith('captures/'):
            raise SystemExit('输出不能放进 data/ 或 captures/：%s' % out)

    paths = collect()
    out.mkdir(parents=True)
    manifest = []
    for rel in paths:
        source = ROOT / rel
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        manifest.append({'path': rel, 'bytes': target.stat().st_size, 'sha256': sha256(source)})
        print('copy', rel)

    # Distribution kit at the bundle root (launcher/, config/, cmd files, README).
    kit = ROOT / 'console_v2/release'
    for item in kit.rglob('*'):
        if not item.is_file():
            continue
        if any(part in EXCLUDE_DIRS for part in item.parts) or item.suffix.lower() in EXCLUDE_SUFFIXES:
            continue
        rel = item.relative_to(kit).as_posix()
        target = out / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(item, target)
        manifest.append({'path': rel, 'bytes': target.stat().st_size, 'sha256': sha256(item)})

    # Empty, writable defaults that the app/user creates anyway.
    (out / 'console_v2/user_data').mkdir(parents=True, exist_ok=True)
    (out / 'console_v2/user_data/sessions').mkdir(parents=True, exist_ok=True)

    manifest.sort(key=lambda item: item['path'])
    write_json(out / 'VERSION.json', {
        'name': 'ConsoleV2 source bundle',
        'commit': git_head(),
        'builtAt': git('show', '-s', '--format=%cI', 'HEAD'),
        'fileCount': len(manifest),
        'totalBytes': sum(item['bytes'] for item in manifest),
        'layout': 'source + launcher; run 编译并启动.cmd',
    })
    write_json(out / 'MANIFEST.json', {'files': manifest})

    if args.zip:
        zip_path = out.with_suffix('.zip')
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
            for item in manifest:
                info = zipfile.ZipInfo(item['path'], date_time=ZIP_EPOCH)
                info.external_attr = 0o644 << 16
                info.compress_type = zipfile.ZIP_DEFLATED
                archive.writestr(info, (out / item['path']).read_bytes())
        print('zip', zip_path, zip_path.stat().st_size)
    print('files', len(manifest), 'bytes', sum(item['bytes'] for item in manifest))
    return 0


if __name__ == '__main__':
    sys.exit(main())