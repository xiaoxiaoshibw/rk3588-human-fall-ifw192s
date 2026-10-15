"""Final preservation audit; intentional edits explicitly classified, no cleanup."""
import argparse
import subprocess
from pathlib import Path
from close_data_bg import ROOT,HERE,PS,read,sha,dump


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--out',required=True);args=p.parse_args();out=Path(args.out).resolve()
    baseline=read(out/'BASELINE_BEFORE.json');changes=[];missing=[];errors=[]
    allowed={'docs/human_fall/WORKFLOW.md','docs/human_fall/REVIEW_LOG.md','docs/human_capture/README.md',
             'sidequests/human_fusion_lab_next/pointset/r01/app.js','sidequests/human_fusion_lab_next/pointset/r01/server.py',
             'sidequests/human_fusion_lab_next/pointset/r01/index.html'}
    for name,previous in baseline['files'].items():
        file=ROOT/name
        if not file.exists():missing.append(name);continue
        try:current=sha(file)
        except OSError as exc:errors.append({'path':name,'error':str(exc)});continue
        if current!=previous:changes.append({'path':name,'before':previous,'after':current,
            'authorized':name in allowed or name.startswith('sidequests/human_fusion_lab_next/real_fall/r04/'),
            'classification':'THIS_TASK_PATCH' if name in allowed or name.startswith('sidequests/human_fusion_lab_next/real_fall/r04/') else 'EXTERNAL_UNRELATED_CHANGE_PRESERVED'})
    actual_head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip()
    result={'files_checked':len(baseline['files']),'baseline_errors':baseline['errors'],'changes':changes,'missing':missing,'errors':errors,
            'unchanged_files':len(baseline['files'])-len(changes)-len(missing)-len(errors),
            'head_before':baseline['head'].strip(),'head_after':actual_head,'head_unchanged':actual_head==baseline['head'].strip(),
            'old_evidence_changed':[c for c in changes if c['path'].startswith('docs/') and '/evidence/' in c['path']],
            'production_or_raw_changed':[c for c in changes if c['path'].startswith(('src/','captures/remote/','pc_apps/human_replay/'))],
            'note':'New UUID leveling artifacts and new run evidence are not preexisting files; no old artifact rewritten or removed.'}
    dump(out/'PRESERVATION_CHECK.json',result)
    new_sources=list(HERE.glob('*.py'))+list(HERE.glob('*.js'))+[PS/'app.js',PS/'server.py',PS/'index.html']
    dump(out/'SOURCE_SHA_FINAL.json',{str(p.relative_to(ROOT)):sha(p) for p in new_sources})
    dump(out/'DELIVERY_SHA_FINAL.json',{str(p.relative_to(out)):sha(p) for p in out.rglob('*') if p.is_file() and p.name!='DELIVERY_SHA_FINAL.json'})
    print('preservation',len(baseline['files']),'files',len(changes),'intentional/external changes',len(missing),'missing',len(errors),'errors')
