"""CL2-09B isolated candidate; no frozen/production source mutation."""
import hashlib,json,os,shutil,subprocess,sys
from pathlib import Path
E=Path(__file__).resolve().parent
R=Path('D:/Code/ldiar')
I=Path('D:/Code/cl208audit')
H=Path('C:/Users/30680/.codex/worktrees/traditional-clustering/ldiar/docs/sidequests/evidence')

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf8'))
def save(n,v):
    with (E/n).open('x',encoding='utf8') as f:json.dump(v,f,ensure_ascii=False,indent=2,allow_nan=False)
def inventory(root):
    out={}
    for base,dirs,files in os.walk(root,followlinks=False):
        dirs[:]=[d for d in dirs if d!='.git']
        for name in files:
            p=Path(base)/name
            if p.is_relative_to(E):continue
            if p.is_symlink():out[p.relative_to(root).as_posix()]='symlink:'+os.readlink(p)
            elif p.is_file():out[p.relative_to(root).as_posix()]=sha(p)
    return out

if __name__=='__main__':
    frozen=E/'frozen';candidate=E/'candidate'
    frozen.mkdir();candidate.mkdir()
    source=I/'pc_apps/human_replay'
    files=list(source.glob('floor*.py'))+list(source.glob('leveling*.py'))+list((source/'leveling_estimators').glob('*.py'))
    bindings=[]
    for p in sorted(files):
        rel=p.relative_to(source);dest=frozen/rel;dest.parent.mkdir(parents=True,exist_ok=True)
        before=sha(p);shutil.copyfile(p,dest);assert before==sha(p)==sha(dest)
        bindings.append(dict(origin=str(p),frozen=str(dest),sha256=before))
    shutil.copyfile(frozen/'floor_sheet.py',candidate/'floor_sheet.py')
    shutil.copyfile('C:/Users/30680/.codex/skills/ponytail/SKILL.md',E/'PONYTAIL_SKILL.md')
    history={str(p):sha(p) for folder in [H/'2026-10-09_cl2_07_r1',H/'2026-10-09_cl2_08_r1',H/'2026-10-09_cl2_09a_r1'] for p in folder.rglob('*') if p.is_file()}
    job=I/'sidequests/traditional_clustering/artifacts/leveling/389dc570b0cd4eb38dd405244effbe20'
    inputs={str(p):sha(p) for p in list((I/'audit_inputs/cap_20261009_121647').iterdir())+list(job.iterdir()) if p.is_file()}
    origin=R/'pc_apps/human_replay/floor_sheet.py'
    assert origin.read_text(encoding='utf8')==(frozen/'floor_sheet.py').read_text(encoding='utf8')
    save('01_baseline.json',dict(writer='Codex; ponytail full',scope='New isolated candidate only; main and historical sources read-only',
        main_HEAD=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
        main_branch=subprocess.check_output(['git','branch','--show-current'],cwd=R,text=True).strip(),
        main_status=subprocess.check_output(['git','status','--porcelain=v1','--untracked-files=all'],cwd=R,text=True),
        main_all_files=inventory(R),isolated_all_files=inventory(I),source_bindings=bindings,
        historical_files=history,input_files=inputs,main_floor_sheet_sha256=sha(origin),
        python=sys.version,return_before_sha256=sha(H.parent/'returns/CLUSTER-01.md')))
    (E/'return_before.bin').write_bytes((H.parent/'returns/CLUSTER-01.md').read_bytes())
    print('ISOLATED_BASELINE_PASS',len(bindings),flush=True)
