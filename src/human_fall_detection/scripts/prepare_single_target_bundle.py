#!/usr/bin/env python3
"""The ONE deterministic release bundle builder (no SSH, ROS, deployment or start).

The tar keeps the repository-relative layout on purpose:

* the region closure (``project_dependencies.py``) resolves its root by walking
  four directories up, so ``sidequests/.../current`` and
  ``docs/human_capture/evidence/...`` must keep their depth;
* ``single_target_node.find_root`` looks for layout markers, so the same code
  runs from the repository and from ``<release>/bundle``.

Contents (single source of truth -- ``deploy_human_fall.sh`` no longer keeps a
second copy list):

* ``human_fall_detection`` core/scripts/config (recursive YAML+JSON)/launch and
  package metadata;
* ``human_follow_calibration/scripts`` (the point-cloud decoder the node needs);
* the ``current`` region entry points, ``r08/calibrate.py`` and the frozen
  skeleton + params they load at import time;
* ``human_capture`` core/scripts/config (including the concurrency / graceful
  shutdown fixes);
* the ``human_fall`` page plus the shared static assets it references;
* ``RELEASE.json`` (release id, page version, algorithm config SHAs) and
  ``MANIFEST.json`` (per-file bytes + SHA).

Page script tags are rewritten so their ``?v=`` equals the packaged file hash and
a ``hf-page-version`` meta tag is inserted; packaging fails if the page has no
rewritable tags. That removes the "browser still runs yesterday's JS" class of
field bug without a manual bump.
"""

import argparse
import hashlib
import io
import json
import re
import sys
import tarfile
from pathlib import Path

SCHEMA_VERSION = 1

CORE_GLOBS = (
    'src/human_fall_detection/core/**/*.py',
    'src/human_fall_detection/scripts/*.py',
    'src/human_fall_detection/scripts/*.sh',
    'src/human_fall_detection/config/**/*.yaml',
    'src/human_fall_detection/config/**/*.json',
    'src/human_fall_detection/launch/*',
    'src/human_follow_calibration/scripts/*.py',
    'src/human_capture/core/**/*.py',
    'src/human_capture/scripts/*.py',
    'src/human_capture/config/**/*.yaml',
    'src/human_capture/config/**/*.json',
)

CORE_FILES = (
    'ML/src/fall_geometry.py',
    'ML/src/human_pointset.py',
    'src/human_fall_detection/package.xml',
    'src/human_fall_detection/CMakeLists.txt',
    'src/human_fall_detection/setup.py',
    'src/human_capture/package.xml',
    'src/human_capture/CMakeLists.txt',
    'src/human_capture/launch/human_capture.launch',
    # region closure, loaded by path at import time
    'sidequests/hfus_tcms_02/realdev/current/project_regions.py',
    'sidequests/hfus_tcms_02/realdev/current/project_dependencies.py',
    'sidequests/hfus_tcms_02/realdev/current/region_runtime.py',
    'sidequests/hfus_tcms_02/realdev/r08/calibrate.py',
    'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/skeleton.py',
    'docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/prototype_params_v1.json',
)

PAGE_DIR = 'webui/human_fall'
PAGE_FILES = ('index.html', 'human_fall.js', 'human_fall_lib.js')
PAGE_ASSETS = ('webui/ui.css', 'webui/three.min.js', 'webui/OrbitControls.js')

EXCLUDED_SUFFIXES = ('.pyc',)
EXCLUDED_NAMES = ('__pycache__',)

_VERSION_RE = re.compile(r'(?P<name>human_fall(?:_lib)?\.js)\?v=(?P<version>[0-9a-fA-F]+)')
_META_RE = re.compile(r'<meta\s+name="hf-page-version"\s+content="[^"]*"\s*/?>', re.IGNORECASE)


class BundleError(RuntimeError):
    pass


def _sha256(data):
    return hashlib.sha256(data).hexdigest()


def _collect(root):
    files = {}
    for pattern in CORE_GLOBS:
        for path in sorted(root.glob(pattern)):
            if not path.is_file():
                continue
            rel = path.relative_to(root).as_posix()
            if any(part in EXCLUDED_NAMES for part in path.parts):
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            files[rel] = path.read_bytes()
    for rel in CORE_FILES:
        path = root / rel
        if not path.is_file():
            raise BundleError('missing required bundle file: %s' % rel)
        files[rel] = path.read_bytes()
    for name in PAGE_FILES:
        rel = '%s/%s' % (PAGE_DIR, name)
        path = root / rel
        if not path.is_file():
            raise BundleError('missing page file: %s' % rel)
        files[rel] = path.read_bytes()
    for rel in PAGE_ASSETS:
        path = root / rel
        if not path.is_file():
            raise BundleError('missing shared page asset: %s' % rel)
        files[rel] = path.read_bytes()
    return files


def rewrite_page(files):
    """Point each script tag at its packaged hash and stamp a page version.

    Returns ``(page_version, index_bytes)``. Deterministic: the same inputs
    always produce the same bytes.
    """
    index_rel = '%s/index.html' % PAGE_DIR
    try:
        index = files[index_rel].decode('utf-8')
    except UnicodeDecodeError as exc:
        raise BundleError('page index.html is not UTF-8: %s' % exc)
    hashes = {}
    for name in ('human_fall_lib.js', 'human_fall.js'):
        hashes[name] = _sha256(files['%s/%s' % (PAGE_DIR, name)])[:12]
    seen = {'human_fall_lib.js': 0, 'human_fall.js': 0}

    def repl(match):
        name = match.group('name')
        seen[name] = seen.get(name, 0) + 1
        return '%s?v=%s' % (name, hashes[name])

    rewritten = _VERSION_RE.sub(repl, index)
    if seen['human_fall_lib.js'] < 1 or seen['human_fall.js'] < 1:
        raise BundleError('page index.html has no rewritable ?v= script tags')
    page_version = _sha256(
        (rewritten + hashes['human_fall_lib.js'] + hashes['human_fall.js']).encode('utf-8'))[:12]
    meta = '<meta name="hf-page-version" content="%s">' % page_version
    if _META_RE.search(rewritten):
        rewritten = _META_RE.sub(meta, rewritten, count=1)
    else:
        marker = '<meta charset="utf-8">'
        if marker not in rewritten:
            raise BundleError('page index.html has no charset meta to anchor the version tag')
        rewritten = rewritten.replace(marker, marker + '\n' + meta, 1)
    files[index_rel] = rewritten.encode('utf-8')
    return page_version, hashes


def _release_identity(files, manifest_extra):
    digest = hashlib.sha256()
    for name in sorted(files):
        digest.update(name.encode('utf-8'))
        digest.update(b'\0')
        digest.update(_sha256(files[name]).encode('ascii'))
        digest.update(b'\n')
    for name in sorted(manifest_extra):
        digest.update(name.encode('utf-8'))
        digest.update(b'\0')
        digest.update(str(manifest_extra[name]).encode('utf-8'))
        digest.update(b'\n')
    return digest.hexdigest()


def _git_head(root):
    try:
        head = (root / '.git/HEAD').read_text(encoding='utf-8').strip()
        if head.startswith('ref: '):
            ref = root / '.git' / head[5:]
            return ref.read_text(encoding='utf-8').strip()
        return head
    except OSError:
        return None


def prepare(root, destination, *, strict=True, geometry_shadow=False):
    """Build the release tar at ``destination`` and return the file manifest."""
    root = Path(root)
    files = _collect(root)
    page_version, page_hashes = rewrite_page(files)
    perception_rel = 'src/human_fall_detection/config/perception_single_target_v1.yaml'
    scene_rel = 'src/human_fall_detection/config/single_target_scene_v1.yaml'
    release_id = _release_identity(files, {'page_version': page_version,'geometry_shadow':bool(geometry_shadow)})
    release = {
        'schema_version': SCHEMA_VERSION,
        'kind': 'human_perception_release',
        'release_id': release_id[:16],
        'features': {'event_geometry_shadow':bool(geometry_shadow)},
        'git_head_metadata_only': _git_head(root),
        'layout': 'repo-relative; run with scripts/single_target_node.py',
        'page_version': page_version,
        'page_script_versions': page_hashes,
        'algorithm_config': {
            'scene': {'path': scene_rel, 'sha256': _sha256(files[scene_rel])},
            'perception': {'path': perception_rel,
                           'sha256': _sha256(files[perception_rel])},
        },
        'runtime': {
            'python': '3.8+ (board 3.8.10)',
            'third_party': ['numpy', 'PyYAML', 'ROS1 rospy/rospkg/sensor_msgs',
                            'inno_lidar_msg'],
            'rosbag_cli_required_for': 'human_capture recording/extraction',
        },
        'entry': 'scripts/single_target_node.py',
        'capture_entry': 'scripts/capture_server.py',
        'components': {
            'fall_core': sum(1 for n in files if n.startswith('src/human_fall_detection/core/')),
            'fall_scripts': sum(1 for n in files
                                if n.startswith('src/human_fall_detection/scripts/')),
            'fall_config': sum(1 for n in files
                               if n.startswith('src/human_fall_detection/config/')),
            'capture': sum(1 for n in files if n.startswith('src/human_capture/')),
            'regions': sum(1 for n in files
                           if n.startswith('sidequests/') or n.startswith('docs/human_capture/')),
            'page': sum(1 for n in files if n.startswith('webui/')),
        },
        'file_count': len(files),
        'total_bytes': sum(len(data) for data in files.values()),
        'semantic': {'mode_verified': False, 'allow_confirmed': False,
                     'confirmed_enabled': False, 'human_effect': 'UNKNOWN'},
    }
    files['RELEASE.json'] = json.dumps(release, sort_keys=True, indent=1).encode('utf-8')
    manifest = {name: {'bytes': len(data), 'sha256': _sha256(data)}
                for name, data in sorted(files.items())}
    files['MANIFEST.json'] = json.dumps(manifest, sort_keys=True, indent=1).encode('utf-8')

    destination = Path(destination)
    if destination.exists() and strict:
        raise BundleError('refusing to overwrite existing bundle: %s' % destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb') as output, tarfile.open(fileobj=output, mode='w') as archive:
        for name, data in sorted(files.items()):
            info = tarfile.TarInfo(name)
            info.size = len(data)
            info.mtime = 0
            info.mode = 0o644
            info.uid = info.gid = 0
            info.uname = info.gname = ''
            archive.addfile(info, io.BytesIO(data))
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--root', type=Path, default=None)
    parser.add_argument('--geometry-shadow',action='store_true',help='enable geometry telemetry only; no learned model or confirmed alarms')
    parser.add_argument('--force', action='store_true',
                        help='replace an existing output file')
    args = parser.parse_args(argv)
    root = args.root or Path(__file__).resolve().parents[3]
    try:
        manifest = prepare(root, args.out, strict=not args.force,geometry_shadow=args.geometry_shadow)
    except BundleError as exc:
        parser.exit(5, 'bundle failed: %s\n' % exc)
    data = args.out.read_bytes()
    with tarfile.open(fileobj=io.BytesIO(data)) as archive:
        release = json.load(archive.extractfile('RELEASE.json'))
    print(json.dumps({'files': len(manifest), 'bytes': len(data),
                      'sha256': _sha256(data), 'release_id': release['release_id'],
                      'page_version': release['page_version']}))
    return 0


if __name__ == '__main__':
    sys.exit(main())
