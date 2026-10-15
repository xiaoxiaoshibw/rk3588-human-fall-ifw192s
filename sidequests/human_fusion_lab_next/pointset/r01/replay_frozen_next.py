"""Reproduce the archived numerical run in a NEW directory with explicit source paths."""
import argparse
import copy
import importlib.util
from pathlib import Path
from actions import HERE,load,read,dump,sha
from next_contract import validate_frozen_inputs
from next_dev import validate_source_directory,ROOT


def reproduce(source_evidence,output,check_only=False):
    manifest=validate_frozen_inputs(source_evidence)
    for name,h in manifest['code_sha256'].items():
        if name!='next_dev.py' and sha(HERE/name)!=h:
            raise ValueError('Immutable imported numerical dependency drift')
    for sid,expected in manifest['source_sha256'].items():
        validate_source_directory(ROOT/'captures/remote'/sid)
        _,raw,actual=load(sid)
        if actual!=expected:raise ValueError('Original source drift')
        del raw
    spec=importlib.util.spec_from_file_location('hfus_archived_numerical',source_evidence/'EXECUTED_SOURCE/next_dev.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # This code actually executes the archived file. Logical code names resolve
    # to that archive; other imports were checked byte-for-byte above.
    module.HERE=source_evidence/'EXECUTED_SOURCE'
    if check_only:
        print('Archived numerical entry/import/source closure PASS',flush=True)
        return
    output.mkdir(parents=True,exist_ok=False);fresh=copy.deepcopy(manifest);fresh['run_id']=output.name
    fresh['reproduces_manifest_sha256']=sha(source_evidence/'RUN_MANIFEST.json')
    fresh['executed_code_paths']={n:str(module.HERE/n) for n in fresh['code_sha256']}
    fresh['launcher_sha256']=sha(Path(__file__))
    dump(output/'RUN_MANIFEST.json',fresh)
    module.run(output)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--source-evidence',type=Path,required=True);p.add_argument('--out',type=Path);p.add_argument('--check-only',action='store_true')
    a=p.parse_args()
    if not a.check_only and a.out is None:p.error('--out requires a fresh directory')
    reproduce(a.source_evidence.resolve(),a.out.resolve() if a.out else None,a.check_only)
