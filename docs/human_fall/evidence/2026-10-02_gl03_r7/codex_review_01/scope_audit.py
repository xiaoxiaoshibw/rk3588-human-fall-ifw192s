"""Reverse submitted unified patch in memory; no old evidence writes."""
import hashlib
import json
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[5]
OUT=Path(__file__).resolve().parent
before=json.loads((OUT/'00_baseline.json').read_text(encoding='utf-8'))
r7=json.loads((OUT.parent/'00_before_manifest.json').read_text(encoding='utf-8'))
r6=json.loads((OUT.parent.parent/'2026-10-02_gl03_r6/22_source_manifest.json').read_text(encoding='utf-8'))
changed={k:{'r7_start':v,'review_start':before['files'].get(k)}
         for k,v in r7['files'].items() if before['files'].get(k)!=v}
patch=(OUT.parent/'23_source_diff.patch').read_text(encoding='utf-8').splitlines(keepends=True)
reconstructed={};i=0
while i<len(patch):
    assert patch[i].startswith('--- a/');name=patch[i][6:].strip();i+=2
    current=(ROOT/name).read_text(encoding='utf-8').splitlines(keepends=True)
    old=[];position=0
    while i<len(patch) and not patch[i].startswith('--- a/'):
        match=re.match(r'@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@',patch[i]);assert match,patch[i]
        start=int(match.group(1))-1;old.extend(current[position:start]);position=start;i+=1
        while i<len(patch) and not patch[i].startswith(('@@ ','--- a/')):
            line=patch[i];tag=line[0];body=line[1:]
            if tag in (' ','+'):
                assert current[position]==body,(name,position);position+=1
            if tag in (' ','-'):old.append(body)
            i+=1
    old.extend(current[position:])
    digest=hashlib.sha256(''.join(old).encode('utf-8')).hexdigest()
    assert digest==r6['sources'][name],(name,digest)
    reconstructed[name]=digest
report={'r7_baseline_entries':len(r7['files']),'review_baseline_entries':len(before['files']),
        'changes_since_r7_start':changed,'reverse_patch_matches_r6':reconstructed,
        'unreadable':before['unreadable']}
(OUT/'15_scope_audit.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(report,ensure_ascii=False,indent=2))
