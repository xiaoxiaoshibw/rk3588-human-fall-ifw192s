"""Range Replay 0.1.0：PC显式离线发行入口与源码包校验。"""
import hashlib
import json
from pathlib import Path
import sys

VERSION = '0.1.0'
ROOT = Path(__file__).resolve().parents[2]


def verify_package(root):
    root = Path(root).resolve()
    manifest = json.loads((root/'MANIFEST.json').read_text(encoding='utf-8'))
    if manifest.get('version') != VERSION or manifest.get('kind') != 'pc_offline_source_release':
        raise ValueError('unsupported release manifest')
    files = manifest['files']
    required = {'run.py','start.cmd','pc_apps/range_fall/release.py','pc_apps/range_fall/runtime_replay.py',
        'pc_apps/range_fall/replay_template.html'}
    if not required <= set(files): raise ValueError('incomplete release manifest')
    for name, expected in files.items():
        path = (root/name).resolve()
        if root not in path.parents or path.is_symlink(): raise ValueError('unsafe release path')
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError('release SHA mismatch: '+name)
    return manifest


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if (ROOT/'MANIFEST.json').exists(): verify_package(ROOT)
    if argv == ['--version']:
        print('Range Replay '+VERSION+' (PC offline; confirmed disabled)');return
    if sys.version_info < (3,8): raise RuntimeError('Python 3.8 or newer required')
    import numpy as np
    if argv == ['--check']:
        print(json.dumps(dict(version=VERSION,python=sys.version,numpy=np.__version__,
            package_verified=(ROOT/'MANIFEST.json').exists(),mode='PC offline',confirmed_enabled=False),sort_keys=True))
        return
    import runtime_replay
    runtime_replay.main(argv or ['--help'])


if __name__ == '__main__': main()
