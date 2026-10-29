"""Restore original LF bytes for WORKFLOW/REVIEW_LOG, then append S02 entries without newline translation."""
import hashlib
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from append_docs import WF_ENTRY, RL_ENTRY
from bootstrap import OUT, ROOT

recs = {json.loads(x)['path']: json.loads(x) for x in (OUT / 'BASELINE_FILES.jsonl').read_text(encoding='utf8').splitlines()}

def reconstruct(name):
    b = (ROOT / name).read_bytes()
    n = b.replace(b'\r\n', b'\n')
    if name.endswith('WORKFLOW.md'):
        i = n.find(b'## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S01')
        if i < 0:
            raise SystemExit('WORKFLOW marker missing')
        return n[i:]
    m = b'\n## 2026-10-17 HFUS-TCMS-02-REALDEV-02-S02 '
    i = n.find(m)
    if i < 0:
        raise SystemExit('REVIEW marker missing')
    return n[:i + 1]

orig = {}
for name in ['docs/human_fall/WORKFLOW.md', 'docs/human_fall/REVIEW_LOG.md']:
    o = reconstruct(name)
    if hashlib.sha256(o).hexdigest() != recs[name]['sha256'] or len(o) != recs[name]['bytes']:
        raise SystemExit('RECONSTRUCTION MISMATCH ' + name)
    orig[name] = o

wf = WF_ENTRY.encode('utf8') + orig['docs/human_fall/WORKFLOW.md']
rl = orig['docs/human_fall/REVIEW_LOG.md'] + RL_ENTRY.encode('utf8')
(ROOT / 'docs/human_fall/WORKFLOW.md').write_bytes(wf)
(ROOT / 'docs/human_fall/REVIEW_LOG.md').write_bytes(rl)
print(json.dumps(dict(wf_sha=hashlib.sha256(wf).hexdigest(), rl_sha=hashlib.sha256(rl).hexdigest(),
                      wf_suffix_ok=hashlib.sha256(wf[-len(orig['docs/human_fall/WORKFLOW.md']):]).hexdigest() == recs['docs/human_fall/WORKFLOW.md']['sha256'],
                      rl_prefix_ok=hashlib.sha256(rl[:len(orig['docs/human_fall/REVIEW_LOG.md'])]).hexdigest() == recs['docs/human_fall/REVIEW_LOG.md']['sha256'])))
