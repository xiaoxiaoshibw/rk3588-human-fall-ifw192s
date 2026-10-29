import json, hashlib
from pathlib import Path
R = Path('D:/Code/ldiar')
O = R/'docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1'
recs = {json.loads(x)['path']: json.loads(x) for x in (O/'BASELINE_FILES.jsonl').read_text(encoding='utf8').splitlines()}
for name in ['docs/human_fall/WORKFLOW.md','docs/human_fall/REVIEW_LOG.md']:
    b=(R/name).read_bytes(); n=b.replace(b'\r\n',b'\n')
    print(name,'cur',len(b),'norm',len(n),'cr_left',n.count(b'\r'),'base',recs[name]['bytes'])
    if 'WORKFLOW' in name:
        i=n.find(b'## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S01')
        print(' marker at',i,'prefix',n[:60])
        o=n[i:]
    else:
        m=b'\n## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S02 '
        i=n.find(m); print(' marker at',i,'tail',n[i:i+60]); o=n[:i+1]
    print(' cand',len(o),hashlib.sha256(o).hexdigest(),'head',o[:40],'tail',o[-40:])
