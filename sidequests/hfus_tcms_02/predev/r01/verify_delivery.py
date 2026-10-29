"""Read-only full-tree preservation + artifact audit, writes only a fresh PREDEV output."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
from contracts import ROOT, HERE, new_output, sha, write_new


def main(baseline, output, runs):
    b=json.loads(Path(baseline).read_text(encoding='utf8'))
    paths=subprocess.check_output(['git','ls-files','-z','--cached','--others','--exclude-standard'],cwd=str(ROOT)).decode('utf8').split('\0')
    output=new_output(output)
    allowed=['sidequests/hfus_tcms_02/predev/r01/',
             'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_predev_r1/',
             'docs/human_fall/returns/HFUS-TCMS-02-PREDEV.md',
             'docs/human_fall/WORKFLOW.md','docs/human_fall/REVIEW_LOG.md']
    rows=[]
    for name in sorted(set(paths)):
        if not name:
            continue
        p=ROOT/name
        if any(name==x or name.startswith(x+'/') for x in ['data','captures/remote','captures/leveled','captures/registration']):
            rows.append(dict(path=name,excluded='protected_data_or_junction'))
            continue
        try:
            if p.is_symlink():
                rows.append(dict(path=name,symlink=os.readlink(p)))
            elif not p.resolve().is_relative_to(ROOT.resolve()) or p.resolve().is_relative_to((ROOT/'data').resolve()):
                rows.append(dict(path=name,excluded='resolved_outside_workspace_or_data'))
            elif p.is_file():
                rows.append(dict(path=name,bytes=p.stat().st_size,sha256=sha(p)))
            else:
                rows.append(dict(path=name,error='missing_or_not_regular'))
        except OSError as exc:
            rows.append(dict(path=name,error=str(exc)))
    old={r['path']:r for r in b['files']}
    now={r['path']:r for r in rows}
    changes=[]
    for name in sorted(set(old)|set(now)):
        if old.get(name)!=now.get(name):
            changes.append(dict(path=name,before=old.get(name),after=now.get(name),
                scope='THIS_ITEM_ALLOWED' if any(name.startswith(a) for a in allowed) else 'OUTSIDE_ITEM_UNATTRIBUTED_PARALLEL'))
    write_new(output/'ALL_FILES_AFTER.json',rows)
    write_new(output/'CHANGES.json',changes)
    (output/'GIT_STATUS_AFTER.txt').write_bytes(subprocess.check_output(['git','status','--porcelain=v1','-uall'],cwd=str(ROOT)))
    artifacts=[]
    for run in runs:
        run=Path(run)
        index=json.loads((run/'OUTPUT_INDEX.json').read_text(encoding='utf8'))
        valid=all(sha(run/name)==h for name,h in index.items())
        inputs=json.loads((run/'SOURCES_FINAL.json').read_text(encoding='utf8'))
        manifest=json.loads((run/'REPLAY.json').read_text(encoding='utf8'))
        source_valid=all({k:sha(Path(e['path'])/n) for k,n in [('meta','meta.json'),('points','points.bin')]}==e['source_sha256'] for e in manifest['entries'])
        artifacts.append(dict(run=str(run),index_valid=valid,explicit_sources_valid=source_valid,
                              source_audit_entries=len(inputs),output_index_sha256=sha(run/'OUTPUT_INDEX.json')))
    protected=[dict(path=name,before=old[name],after=now.get(name),unchanged=old[name]==now.get(name))
               for name in old if (name.startswith(('src/','webui/','pc_apps/','tools/')) or
                   name.startswith('sidequests/') and not name.startswith('sidequests/hfus_tcms_02/'))]
    write_new(output/'PROTECTED_SOURCES.json',protected)
    append_checks={}
    for name,mode in [('docs/human_fall/WORKFLOW.md','suffix'),('docs/human_fall/REVIEW_LOG.md','prefix')]:
        data=(ROOT/name).read_bytes();n=old[name]['bytes']
        segment=data[-n:] if mode=='suffix' else data[:n]
        append_checks[name]=hashlib.sha256(segment).hexdigest()==old[name]['sha256']
    result=dict(branch_before=b['branch'],head_before=b['head'],
                branch_after=subprocess.check_output(['git','branch','--show-current'],cwd=str(ROOT)).decode().strip(),
                head_after=subprocess.check_output(['git','rev-parse','HEAD'],cwd=str(ROOT)).decode().strip(),
                protected_all_unchanged=all(r['unchanged'] for r in protected),
                out_of_scope_changes=[r['path'] for r in changes if r['scope'].startswith('OUTSIDE')],
                append_preserves_old_bytes=append_checks,artifacts=artifacts,
                this_item_sources={p.name:sha(p) for p in HERE.iterdir() if p.is_file()},
                acceptance_sha256=sha(Path(baseline).parent/'ACCEPTANCE_V1.md'))
    write_new(output/'FINAL_CHECK.json',result)
    print(json.dumps(dict(output=str(output),protected_unchanged=result['protected_all_unchanged'],
                          outside_changes=len(result['out_of_scope_changes']),artifacts=artifacts)))
    if not all(a['index_valid'] and a['explicit_sources_valid'] for a in artifacts):
        raise SystemExit(1)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--baseline',required=True)
    p.add_argument('--out',required=True)
    p.add_argument('--run',action='append',required=True)
    a=p.parse_args()
    main(a.baseline,a.out,a.run)
