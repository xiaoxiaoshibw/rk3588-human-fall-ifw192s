"""CL2-12 run Opencode readonly audit (only real CLI invocation).
Config via OPENCODE_CONFIG_CONTENT env var (CL2-10 precedent; --config is not valid in CLI 1.18.35).
Assert the effective agent is read-only before submitting the audit prompt.
Prompt carried in argv[1] (avoids shell quoting issues on Windows).
"""
import json, os, shlex, subprocess, sys
from pathlib import Path

E = Path(__file__).resolve().parent
SHELL = 'bash'

def save(name, obj):
    (E / name).write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding='utf-8')

def cli(label, command, env, stdin_text=None):
    argv = [SHELL, '-c', command]
    capture = label.endswith('_command')
    with open(E / (label + '.stdout'), 'w', encoding='utf-8', newline='\n') as out, \
         open(E / (label + '.stderr'), 'w', encoding='utf-8', newline='\n') as err:
        proc = subprocess.run(argv, cwd=E, env=env, stdout=out, stderr=err,
                              input=stdin_text, text=True)
    if capture:
        save(label + '.json', dict(argv=[command], exit_code=proc.returncode))
    return proc.returncode

config = {
    'permission': {'*': 'deny', 'read': {'*': 'allow'}, 'external_directory': 'deny'},
    'agent': {'cl212audit': dict(
        description='CL2-12 identifiability readonly audit', mode='primary',
        permission={'*': 'deny', 'read': {'*': 'allow'}, 'external_directory': 'deny'},
        prompt='Read-only audit. No shell, writing, edit, task, network or other tool actions. Only read.')},
    'mcp': {}, 'plugin': [],
}
save('cl2_12_effective_config.json', config)
env = os.environ.copy()
env['OPENCODE_CONFIG_CONTENT'] = json.dumps(config)
env['OPENCODE_DISABLE_AUTOUPDATE'] = 'true'

assert cli('cl2_12_agent_dbg', 'opencode debug agent cl212audit --pure', env) == 0, 'debug agent failed'
agent = json.loads((E / 'cl2_12_agent_dbg.stdout').read_text(encoding='utf-8'))
save('cl2_12_agent.json', agent)
assert agent['tools']['read'] and not any(v for k, v in agent['tools'].items() if k != 'read'), \
    'integrity: only read tool allowed'

prompt = (E / 'cl2_12_opencode_prompt.txt').read_text(encoding='utf-8')
code = cli('cl2_12_raw', 'opencode run --pure --agent cl212audit --format json '
           '--model opencode-go/deepseek-v4.1-flash ' + shlex.quote(prompt), env)

events = []
with open(E / 'cl2_12_raw.stdout', encoding='utf-8') as f:
    for line in f:
        try: events.append(json.loads(line))
        except json.JSONDecodeError: pass
exitcode = {'exit_code': code, 'n_events': len(events)}
if events:
    parts = [e.get('part', {}) for e in events if e.get('type') == 'part.text' or e.get('type') == 'text']
    text = ''.join(p.get('text', '') for p in parts) if parts else ''
    infos = [e.get('part', {}).get('info', {}) if isinstance(e.get('part'), dict) else
             e.get('info', {}) for e in events]
    models = sorted({(i or {}).get('providerID', '') + '/' + (i or {}).get('modelID', '')
                     for i in infos if isinstance(i, dict)})
    exitcode['models'] = models
    exitcode['text_chars'] = len(text)
    exitcode['audit_complete_marker'] = 'AUDIT_COMPLETE' in text
    exitcode['finish_stop'] = any((i or {}).get('finish') == 'stop' for i in infos if isinstance(i, dict))
save('cl2_12_completion.json', exitcode)
print('exit:', code)
print(json.dumps(exitcode, ensure_ascii=False))
