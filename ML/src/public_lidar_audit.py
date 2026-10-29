"""Snapshot visible source tree and read-only IFW192S source bindings."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import time


def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def baseline(out):
    started = time.time()
    files = subprocess.check_output(['rg', '--files', '--hidden', '-g', '!.git']).decode('utf-8').splitlines()
    records = []
    for name in files:
        p = Path(name)
        if not p.is_file() or str(out) in name:
            continue
        records.append({'path': name, 'bytes': p.stat().st_size, 'sha256': sha(p)})
    result = {'branch': subprocess.check_output(['git','branch','--show-current']).decode().strip(),
              'head': subprocess.check_output(['git','rev-parse','HEAD']).decode().strip(),
              'scope': 'rg visible tracked and untracked including hidden; ignored data excluded; new experiment source already present',
              'files': records, 'started': started, 'elapsed_s': time.time()-started}
    (out/'BASELINE.json').write_text(json.dumps(result), encoding='utf-8')
    print('baseline',len(records),flush=True)


def targets(out):
    # Reuse the inspected label inventory without running its prefix experiment.
    old = Path('docs/evidence/2026-10-22_ml_next_steps/experiment.py')
    spec = importlib.util.spec_from_file_location('previous_inventory', old)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    module.HERE = out.resolve(); module.target_inventory()
    records = []
    for meta in sorted(Path('data/sessions').glob('*/meta.json')):
        doc = json.loads(meta.read_text(encoding='utf-8'))
        records.append({'session': meta.parent.name, 'meta_sha256': sha(meta),
                        'points_sha256': sha(meta.parent/'points.bin') if (meta.parent/'points.bin').is_file() else 'MISSING',
                        'frames': doc.get('frames',[]),
                        'calibration_metadata': {k:v for k,v in doc.items() if 'calib' in k or 'level' in k},
                        'independent_action_GT': 'UNKNOWN'})
    (out/'TARGET_SOURCE_BINDING.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print('bound sessions',len(records),flush=True)


if __name__ == '__main__':
    ap=argparse.ArgumentParser();ap.add_argument('mode',choices=['baseline','targets']);ap.add_argument('output',type=Path)
    a=ap.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    if a.mode=='baseline':baseline(a.output)
    else:targets(a.output)
