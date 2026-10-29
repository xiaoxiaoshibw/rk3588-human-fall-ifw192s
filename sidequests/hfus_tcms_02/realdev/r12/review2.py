"""Read-only S07F OpenCode dispatch, transport capture and actual-model audit (r12)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'r11'))

from common2 import EV, ROOT, sha
from register2 import put

BINARY = r'C:\Users\30680\AppData\Roaming\npm\node_modules\@opencode\cli\bin\opencode.exe'


def main(label):
    request = EV / (label + '_REQUEST.md')
    permission = {'*': 'deny', 'read': 'allow', 'glob': 'allow', 'grep': 'allow', 'list': 'allow', 'external_directory': {'C:/Users/30680/.codex/skills/**': 'allow', 'C:/Users/30680/.config/opencode/skills/**': 'allow', 'D:/Code/ldiar/**': 'allow'}}
    env = os.environ.copy()
    env['OPENCODE_DISABLE_AUTOUPDATE'] = 'true'
    env['OPENCODE_CONFIG_CONTENT'] = json.dumps(dict(snapshot=False, permission=permission, agent=dict(plan=dict(permission=permission))))
    cmd = [BINARY, 'run', '--standalone', '--agent', 'plan', '-m', 'opencode-go/deepseek-v4.1-flash', '--format', 'json', 'Please read ' + request.as_posix() + ' and perform the complete read-only review. Return findings in Chinese.']
    own = {label + '.jsonl', label + '.md', label + '_EXPORT.json', label + '_STATUS.json', label + '.stderr'}

    def snap():
        out = {p.name: sha(p) for p in HERE.glob('*.py')}
        for p in sorted(EV.rglob('*')):
            if p.is_file() and p.name not in own:
                out[EV.name + '/' + p.relative_to(EV).as_posix()] = sha(p)
        return out

    before = snap()
    t = time.perf_counter()
    timed_out = False
    with (EV / (label + '.jsonl')).open('x', encoding='utf8') as out, (EV / (label + '.stderr')).open('x', encoding='utf8') as err:
        process = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=out, stderr=err)
        try:
            code = process.wait(timeout=1200)
        except subprocess.TimeoutExpired:
            timed_out = True
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], stdout=err, stderr=err)
            code = process.wait()
    events = []
    for line in (EV / (label + '.jsonl')).read_text(encoding='utf8').splitlines():
        try:
            events.append(json.loads(line))
        except ValueError:
            pass
    text = '\n\n'.join(e.get('part', {}).get('text', '') for e in events if e.get('type') == 'text')
    put(EV / (label + '.md'), text)
    sessions = sorted({e['sessionID'] for e in events if e.get('sessionID')})
    models = set()
    if sessions:
        cp = subprocess.run([BINARY, 'session', 'export', '--standalone', sessions[0]], cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf8', timeout=60)
        put(EV / (label + '_EXPORT.json'), cp.stdout)
        if cp.returncode == 0:
            data = json.loads(cp.stdout)

            def walk(obj):
                if isinstance(obj, dict):
                    if obj.get('type') == 'assistant' and isinstance(obj.get('model'), dict):
                        m = obj['model']
                        models.add(m.get('providerID', '') + '/' + m.get('modelID', m.get('id', '')))
                    if obj.get('role') == 'assistant' and obj.get('modelID'):
                        models.add(obj.get('providerID', '') + '/' + obj['modelID'])
                    for value in obj.values():
                        walk(value)
                elif isinstance(obj, list):
                    for value in obj:
                        walk(value)

            walk(data)
    toolparts = [e.get('part', {}) for e in events if e.get('type') == 'tool_use']
    after = snap()
    reads = [p.get('state', {}).get('input', {}).get('path', p.get('state', {}).get('input', {}).get('filePath', '')).replace('\\', '/').lower() for p in toolparts if p.get('tool') == 'read' and p.get('state', {}).get('status') == 'completed']
    status = dict(command=cmd, exit_code=code, timed_out=timed_out, seconds=time.perf_counter() - t, sessions=sessions, actual_models=sorted(models), source_before=before, source_after=after, source_unchanged={k: before[k] for k in before} == {k: after[k] for k in before}, request_sha=sha(request), request_read_observed=request.as_posix().lower() in reads, ponytail_read_observed=any('ponytail/skill.md' in p for p in reads), tools=sorted({p.get('tool', '') for p in toolparts}), read_only_tools=all(p.get('tool', '') in ('read', 'glob', 'grep', 'list') for p in toolparts), tool_calls=len(toolparts), independent_execution='NOT_RUN', text_chars=len(text))
    put(EV / (label + '_STATUS.json'), status)
    print(json.dumps(status), flush=True)


if __name__ == '__main__':
    main(sys.argv[1])
