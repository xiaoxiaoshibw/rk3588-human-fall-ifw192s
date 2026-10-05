import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time

OUT = Path(__file__).parent
ROOT = OUT.parents[3]
if 'OPENCODE_DB' in os.environ:
    raise SystemExit('DB override present')
name = '16_opencode_compacted'
if any((OUT/(name+s)).exists() for s in ('.jsonl','.stderr.txt','_meta.json')):
    raise SystemExit('No evidence overwrite')
verification = json.loads((OUT/'14_compact_verified.json').read_text(encoding='utf-8'))
if not any(item.get('summary') is True and item.get('finish')=='stop'
           and item.get('providerID')=='opencode-go' and item.get('modelID')=='deepseek-v4.1-flash'
           for item in verification.get('summaries',[])):
    raise SystemExit('Compaction not verified')
prompt = ('Continue SAME GL-I01 R1 implementation after manual context abort13 and verified compaction14. All code/tests preserved; original write-before gate was PASS. Finish remaining checks/real prepare-reload/return, do not restart or reread whole history. Read-only latest remaining shared-entry issues to self-check under existing I IDs: select_group_region with neither indices nor all six bounds must reject missing selector instead of return whole group; frame_of_row must reject negative/out-of-range/non-integer/bool row ids without NumPy negative wrapping and preserve requested row order/duplicates; zero-drop bag2session source XYZ nonfinite is invalid export, whole-input reject not silently filter. Use otherwise valid selectors to test actual frame overlap/group conflict. This is continuation of '
          '(08_scope_gate +09_DESIGN_APPROVED). Read ONLY AI_PROMPT_GLI01_OPENCODE_R1_IMPLEMENT.md '
          'and current approved07_diag_revision/09 approval using compacted summary. Initial00 design conflicts are historical. '
          'Actual local ponytail full read, then implement smallest source/test whitelist. '
          'Keep strict source-backed raw f4 equality, canonical per-frame groups, integer header time, explicit declarations, '
          'group-first bounds/pooled indices, all-entry marker detection, adapted single output/no diagnostics/link-only. '
          'No real fit: existing163621 only prepare/reload/count/hash; synthetic-only CLI fit checks. '
          'Per I01-I08/B01/D01/M01-M13 commands/SHA/return SUBMITTED then STOP. '
          'Do not reread full source/tests/history; target functions/lines. Frozen math/runtime/calibration/config/driver/webui/capture '
          'and no board/network/deploy/capture/git/model/DB changes. Context near120k: stop for same-model compaction.')
command = [r'C:\Users\30680\AppData\Roaming\npm\node_modules\opencode-ai\bin\opencode.exe',
           'run','--attach','http://127.0.0.1:18094','--dir','D:/Code/ldiar',
           '--session','ses_eff575a5affevftT6g3Dzvg05e','-m',
           'opencode-go/deepseek-v4.1-flash','--format','json',prompt]
start = time.monotonic()
meta = {'start':datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
        'model':'opencode-go/deepseek-v4.1-flash','db':'default','session':'ses_eff575a5affevftT6g3Dzvg05e',
        'phase':'implementation_after_design_approval'}
with (OUT/(name+'.jsonl')).open('wb') as stdout,(OUT/(name+'.stderr.txt')).open('wb') as stderr:
    process = subprocess.Popen(command,cwd=ROOT,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
    meta['exit'] = process.wait()
meta.update(end=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(),
            elapsed_s=time.monotonic()-start,pid=process.pid)
(OUT/(name+'_meta.json')).write_text(json.dumps(meta,indent=2),encoding='utf-8')
print(json.dumps(meta))
sys.exit(meta['exit'])

