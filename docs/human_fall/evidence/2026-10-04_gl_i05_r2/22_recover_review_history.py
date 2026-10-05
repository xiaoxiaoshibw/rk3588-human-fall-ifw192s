"""Recover all review-script revisions and command outputs from append-only CLI events."""
import hashlib
import json
from pathlib import Path

OUT=Path(__file__).resolve().parent
TARGET=OUT/'22_review_history'
TARGET.mkdir()
raw=(OUT/'20_second_review.jsonl').read_bytes()
with (TARGET/'captured_cli_prefix.jsonl').open('xb') as f:f.write(raw)
events=[json.loads(line) for line in raw.decode('utf8').splitlines() if line.strip()]
versions={}
records=[]
counter=0
for event in events:
    if event.get('type')!='tool_use':continue
    part=event['part'];state=part['state'];data=state.get('input',{})
    if state.get('status')!='completed':continue
    tool=part.get('tool')
    name=Path(data.get('filePath','')).name
    if tool=='write' and name.endswith('.py'):
        versions[name]=data['content']
    elif tool=='edit' and name in versions:
        old,new=data['oldString'],data['newString']
        if data.get('replaceAll'):versions[name]=versions[name].replace(old,new)
        else:
            assert versions[name].count(old)==1,(name,'ambiguous edit reconstruction')
            versions[name]=versions[name].replace(old,new,1)
    elif tool=='bash':
        if 'opencode_second_review_01' in data.get('command',''):
            counter+=1
            record=dict(index=counter,kind='command',command=data['command'],
                        tool_exit=state.get('metadata',{}).get('exit'),
                        raw_output=state.get('output',''),timestamp=event.get('timestamp'))
            with (TARGET/('%03d_command.json'%counter)).open('x',encoding='utf8') as f:json.dump(record,f,indent=2,ensure_ascii=False)
            records.append(record)
        continue
    else:continue
    counter+=1
    recovered=TARGET/('%03d_%s'%(counter,name))
    with recovered.open('x',encoding='utf8') as f:f.write(versions[name])
    records.append(dict(index=counter,kind='script_version',original_name=name,
        mutation=tool,sha256=hashlib.sha256(versions[name].encode()).hexdigest(),
        recovered=recovered.name,timestamp=event.get('timestamp')))
summary=dict(kind='review_evidence_history_recovery',captured_prefix_sha256=hashlib.sha256(raw).hexdigest(),
    records=records,overwritten_script_names=sorted({r['original_name'] for r in records
        if r['kind']=='script_version' and r['mutation']=='edit'}),
    limitation='prefix snapshot only; CLI may still be running. No original files overwritten. '
               'Initial false checker outputs remain raw command evidence, not author failures.')
with (TARGET/'manifest.json').open('x',encoding='utf8') as f:json.dump(summary,f,indent=2,ensure_ascii=False)
print(json.dumps(dict(versions=sum(r['kind']=='script_version' for r in records),
    command_outputs=sum(r['kind']=='command' for r in records),overwritten=summary['overwritten_script_names'])))
