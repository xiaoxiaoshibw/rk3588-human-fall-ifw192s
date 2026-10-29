"""Write best reconstruction (LF) of the two append surfaces; record the byte-level exception."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from append_docs import WF_ENTRY, RL_ENTRY
from bootstrap import OUT, ROOT

recs = {json.loads(x)['path']: json.loads(x) for x in (OUT / 'BASELINE_FILES.jsonl').read_text(encoding='utf8').splitlines()}

def original_text(name):
    b = (ROOT / name).read_bytes()
    n = b.replace(b'\r\n', b'\n')
    if name.endswith('WORKFLOW.md'):
        i = n.find(b'## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S01')
        return n[i:]
    m = b'\n## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S02 '
    i = n.find(m)
    return n[:i + 1]

out = {}
for name in ['docs/human_fall/WORKFLOW.md', 'docs/human_fall/REVIEW_LOG.md']:
    o = original_text(name)
    out[name] = o
    print(name, 'restored_text_bytes', len(o), 'baseline_bytes', recs[name]['bytes'], 'crlf_lost', recs[name]['bytes'] - len(o))

wf = WF_ENTRY.encode('utf8') + out['docs/human_fall/WORKFLOW.md']
rl = out['docs/human_fall/REVIEW_LOG.md'] + RL_ENTRY.encode('utf8')
(ROOT / 'docs/human_fall/WORKFLOW.md').write_bytes(wf)
(ROOT / 'docs/human_fall/REVIEW_LOG.md').write_bytes(rl)

summary = dict(checked=len(recs), changed=[
    dict(path='docs/human_fall/WORKFLOW.md', method='authorized prepend; original text retained, 247 original CRLF bytes normalized to LF by an earlier Python text-mode append', byte_identical=False),
    dict(path='docs/human_fall/REVIEW_LOG.md', method='authorized append; original text retained, 815 original CRLF bytes normalized to LF by an earlier Python text-mode append', byte_identical=False)],
    byte_identical_files=len(recs) - 2, content_preserved=True,
    git_identity_unchanged=True, head='c9c4ee421cb0c8a3e4590b8f5730828b093c759a', branch='master',
    PASS=False, note='two authorized append surfaces changed line endings; all other files byte-identical; no data/production/old-evidence file changed')
(OUT / 'PRESERVATION_FINAL_SUMMARY.json').write_text(json.dumps(summary, indent=2), encoding='utf8')
print(json.dumps(summary)[:400])
