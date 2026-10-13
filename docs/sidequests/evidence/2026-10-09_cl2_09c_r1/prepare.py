"""CL2-09C evidence helpers and isolated baseline, never mutate previous evidence."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

E = Path(__file__).resolve().parent
R = E.parents[3]
B = E.parent / '2026-10-09_cl2_09b_r1'
I = Path('D:/Code/cl208audit')

def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

def load(path):
    return json.loads(Path(path).read_text(encoding='utf8'))

def save(name, value):
    with (E / name).open('x', encoding='utf8') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)

def inventory(root):
    result = {}
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d != '.git']
        for name in files:
            path = Path(base) / name
            if path.is_relative_to(E):
                continue
            if path.is_symlink():
                result[path.relative_to(root).as_posix()] = 'symlink:' + os.readlink(path)
            elif path.is_file():
                result[path.relative_to(root).as_posix()] = sha(path)
    return result

def run(label, args, env=None):
    import time
    argv = [sys.executable, '-X', 'utf8', '-B', '-W', 'error'] + args
    start = time.perf_counter()
    with (E / (label + '.stdout')).open('xb') as out, (E / (label + '.stderr')).open('xb') as err:
        process = subprocess.run(argv, cwd=E, env=env, stdout=out, stderr=err)
    save(label + '_command.json', dict(argv=argv, cwd=str(E), exit_code=process.returncode,
         elapsed_sec=time.perf_counter() - start, candidate_sha256=sha(E/'candidate/floor_sheet.py'),
         environment_overrides=({k:env[k] for k in ['PYTHONPATH','TEMP','TMP'] if k in env} if env else {})))
    print(label, process.returncode, flush=True)
    return process.returncode

if __name__ == '__main__':
    expected = load(B/'10_evidence_manifest.json')['files']
    for name, digest in expected.items():
        assert sha(B/name) == digest, name
    for name in ['candidate', 'frozen', 'input_snapshot']:
        shutil.copytree(B/name, E/name, ignore=shutil.ignore_patterns('__pycache__'))
    (E/'baseline').mkdir()
    shutil.copyfile(B/'candidate/floor_sheet.py', E/'baseline/floor_sheet.py')
    shutil.copyfile(B/'test_selector.py', E/'test_selector.py')
    shutil.copyfile('C:/Users/30680/.codex/skills/ponytail/SKILL.md', E/'PONYTAIL_SKILL.md')
    old = load(B/'01_baseline.json')
    guards = {str(B/name):digest for name,digest in expected.items()}
    guards[str(B/'10_evidence_manifest.json')] = sha(B/'10_evidence_manifest.json')
    guards.update(old['input_files'])
    guards.update(old['historical_files'])
    guards[str(R/'pc_apps/human_replay/floor_sheet.py')] = sha(R/'pc_apps/human_replay/floor_sheet.py')
    save('01_baseline.json', dict(branch=subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip(),
         HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
         status=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=R,text=True),
         full_tree=inventory(R), guards=guards, baseline_manifest_verified=len(expected),
         source_sha256=sha(E/'baseline/floor_sheet.py'), python=sys.version, python_executable=sys.executable))
    print('BASELINE_READY', len(expected), flush=True)
