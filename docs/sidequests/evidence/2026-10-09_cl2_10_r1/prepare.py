"""CL2-10 new evidence, immutable 09C runtime and original input bindings."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

E=Path(__file__).resolve().parent
R=E.parents[3]
I=Path('D:/Code/cl208audit')
H=Path('C:/Users/30680/.codex/worktrees/traditional-clustering/ldiar')
C=E.parent/'2026-10-09_cl2_09c_r1'
B=E.parent/'2026-10-09_cl2_09b_r1'
RETURN=H/'docs/sidequests/returns/CLUSTER-01.md'

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(path):return json.loads(Path(path).read_text(encoding='utf8'))
def save(name,value):
    with (E/name).open('x',encoding='utf8') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2,allow_nan=False)
def inventory(root):
    result={}
    for base,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if d!='.git']
        for name in files:
            p=Path(base)/name
            if p.is_relative_to(E):continue
            if p.is_symlink():result[p.relative_to(root).as_posix()]='symlink:'+os.readlink(p)
            elif p.is_file():result[p.relative_to(root).as_posix()]=sha(p)
    return result
def git(root):
    env=os.environ.copy();env['GIT_OPTIONAL_LOCKS']='0'
    return {key:subprocess.check_output(['git']+args,cwd=root,text=True,env=env).strip()
      for key,args in [('branch',['branch','--show-current']),('HEAD',['rev-parse','HEAD']),
                       ('status',['status','--porcelain=v1','--untracked-files=all'])]}

def copy_once(origin,destination):
    before=sha(origin)
    if destination.exists():assert sha(destination)==before,str(destination)
    else:shutil.copyfile(origin,destination)
    assert before==sha(origin)==sha(destination)
    return before

if __name__=='__main__':
    guards={};manifests=[]
    for directory,name in [(H/'docs/sidequests/evidence/2026-10-09_cl2_08_r1','evidence_manifest.json'),
          (H/'docs/sidequests/evidence/2026-10-09_cl2_09a_r1','10_evidence_manifest.json'),
          (B,'10_evidence_manifest.json'),(C,'10_evidence_manifest.json')]:
        manifest=load(directory/name)
        for rel,digest in manifest['files'].items():
            assert sha(directory/rel)==digest,(str(directory),rel)
            guards[str(directory/rel)]=digest
        guards[str(directory/name)]=sha(directory/name)
        manifests.append(dict(path=str(directory/name),count=len(manifest['files']),verified=True))
    for directory in ['candidate','frozen','baseline']:
        for origin in (C/directory).rglob('*'):
            if not origin.is_file() or '__pycache__' in origin.parts:continue
            destination=E/directory/origin.relative_to(C/directory)
            destination.parent.mkdir(parents=True,exist_ok=True)
            copy_once(origin,destination)
    for name in ['test_selector.py','test_equivalence.py']:
        copy_once(C/name,E/name)
    copy_once(Path('C:/Users/30680/.codex/skills/ponytail/SKILL.md'),E/'PONYTAIL_SKILL.md')
    normal=load(I/'docs/sidequests/evidence/2026-10-09_cl2_07_r1/03_normal_comparison.json')
    wanted={'cap_20261009_121647'}|{row['sid'] for row in normal if row['valid']}
    sessions=[]
    for report_path in sorted((I/'sidequests/traditional_clustering/artifacts/leveling').glob('*/report.json')):
        report=load(report_path)
        if report['sid'] not in wanted:continue
        sid=report['sid'];directory=I/'audit_inputs'/sid if sid.endswith('_121647') else R/'captures/remote'/sid
        source={}
        for name,key in [('meta.json','meta_sha256'),('points.bin','bin_sha256')]:
            assert sha(directory/name)==report['source'][key],str(directory/name)
            guards[str(directory/name)]=report['source'][key]
            source[name]=str(directory/name)
        # Original main target and frozen target must bind the same raw input.
        if sid.endswith('_121647'):
            for name,key in [('meta.json','meta_sha256'),('points.bin','bin_sha256')]:
                original=R/'captures/remote'/sid/name
                assert sha(original)==report['source'][key],str(original)
                guards[str(original)]=report['source'][key]
        local=E/'inputs'/sid;local.mkdir(parents=True,exist_ok=True)
        for name in ['report.json','manifest.json','domain.npz']:
            origin=report_path.parent/name
            if name=='domain.npz' and not origin.exists():
                origin=H/'sidequests/traditional_clustering/artifacts/leveling'/report_path.parent.name/name
                assert sha(origin)==load(report_path.parent/'manifest.json')['domain_sha256'],str(origin)
            before=copy_once(origin,local/name)
            guards[str(origin)]=before
        assert sha(report_path)==load(report_path.parent/'manifest.json')['report_sha256']
        copy_once(directory/'meta.json',local/'meta.json')
        sessions.append(dict(sid=sid,raw=source,local=str(local),original_TLS_valid=report['estimators']['tls']['valid'],
                             original_recommended=report['recommended'],report_origin=str(report_path)))
    assert len(sessions)==11 and {row['sid'] for row in sessions}==wanted
    catalog=dict(sessions=sessions,target='cap_20261009_121647',
         source='Historical reports and original raw; no session selection based on new experiment outcomes.')
    if (E/'00_input_catalog.json').exists():assert load(E/'00_input_catalog.json')==catalog
    else:save('00_input_catalog.json',catalog)
    source_context={}
    for path in sorted((I/'pc_apps/human_replay').glob('leveling*.py')):
        guards[str(path)]=sha(path)
    for path in (I/'pc_apps/human_replay/leveling_estimators').glob('*.py'):guards[str(path)]=sha(path)
    for root in [R/'pc_apps/human_replay',H/'pc_apps/human_replay',I/'pc_apps/human_replay']:
        for path in list(root.glob('floor*.py'))+list(root.glob('leveling*.py')):
            source_context[str(path)]=sha(path)
            guards[str(path)]=sha(path)
    for root in [R/'pc_apps/human_replay',H/'pc_apps/human_replay']:
        for path in (root/'leveling_estimators').glob('*.py'):guards[str(path)]=sha(path)
    before_return=RETURN.read_bytes()
    copy_once(RETURN,E/'return_before.bin')
    # Frozen old return records are prefixes, not whole-file current SHA expectations.
    for directory in [H/'docs/sidequests/evidence/2026-10-09_cl2_08_r1',
                      H/'docs/sidequests/evidence/2026-10-09_cl2_09a_r1',B]:
        old=directory/'return_before.bin'
        if old.exists():assert before_return.startswith(old.read_bytes()),str(old)
    save('00_baseline.json',dict(main_git=git(R),branch_git=git(H),isolated_git=git(I),
         main_all_files=inventory(R),guards=guards,verified_manifests=manifests,
         execution_runtime='Frozen CL2-09C candidate, not current main production',
         runtime_sha256=sha(E/'candidate/floor_sheet.py'),production_context=source_context,
         main_selector_sha256=sha(R/'pc_apps/human_replay/floor_sheet.py'),
         return_path=str(RETURN),return_before_sha256=sha(RETURN),return_before_bytes=len(before_return),
         physical_prerequisites='Original source .bag is board /mnt path; local raw has meta/bin, no bag or independent surface GT identified.',
         python=sys.version,python_executable=sys.executable))
    print('STEP0_FROZEN',len(sessions),len(guards),manifests,flush=True)
