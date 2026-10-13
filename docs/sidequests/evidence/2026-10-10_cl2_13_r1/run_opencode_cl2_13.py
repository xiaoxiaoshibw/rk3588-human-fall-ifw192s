"""CL2-13 run Opencode read+bash-constrained audit (only real CLI invocation).

Config via OPENCODE_CONFIG_CONTENT env var (CL2-10/12 precedent). KEY hardening vs CL2-12:
in CL2-12 the auditor has ONLY read and could NOT execute; the audit caught the intercept bug
by pure code-reading, but could not itself confirm sigma2/intercept numerically. The user's
CL2-12 review explicitly demands "修正版本独立复算" — so this round the auditor gets `read` +
a CONSTRAINED `bash`:

- bash PRE-REGITERED restricted to: `python <script in this dir>` and read-only pipelines.
  Enforcement is at prompt level (opencode permission wildcard strings can't easily do
  command-prefix ACL without writing temp config to disk; we keep the config in ENV only).
- We additionally assert the effective agent: `read:true`, `bash:true`, everything else false.
  If the opencode-go provider refuses prompt-level bash restriction, the auditor is still set
  to read+bash and the prompt still contains the whitelist — this mirrors CL2-09C route
  ("debug agent" asserted read-only tools and the audit honored it).

The prompt carries the F-AUTHOR-1 finding and asks the auditor to CONFIRM or REFUTE it by
rerunning this directory's scripts itself.
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
    'agent': {'cl213audit': dict(
        description='CL2-13 corrected-version independent recompute audit',
        mode='primary',
        permission={'*': 'deny', 'read': {'*': 'allow'}, 'bash': {'*': 'allow'},
                    'external_directory': 'deny'},
        prompt=(
            'You are a CL2-13 independent recompute auditor. You have `read` and `bash` tools; '
            'bash is STRICTLY limited to: (1) `python <script.py>` where script.py lives in the '
            'CL2-13 evidence directory (D:/Code/ldiar/docs/sidequests/evidence/2026-10-10_cl2_13_r1/), '
            'and (2) read-only shell pipes (cat/head/tail/grep/find on files inside this repo). '
            'No writing outside this directory, no network, no edit/write task tools. If a bash '
            'command would violate this whitelist, refuse and mark that check UNKNOWN. '
            'Do not claim numerical/SHA executions you did not personally run; reserve UNKNOWN '
            'for anything you cannot verify from files you actually read or commands you actually ran.'
        ))},
    'mcp': {}, 'plugin': [],
}
save('cl2_13_effective_config.json', config)
env = os.environ.copy()
env['OPENCODE_CONFIG_CONTENT'] = json.dumps(config)
env['OPENCODE_DISABLE_AUTOUPDATE'] = 'true'

assert cli('cl2_13_agent_dbg', 'opencode debug agent cl213audit --pure', env) == 0, 'debug agent failed'
agent = json.loads((E / 'cl2_13_agent_dbg.stdout').read_text(encoding='utf-8'))
save('cl2_13_agent.json', agent)
# Assert read+bash allowed, everything else denied
t = agent.get('tools', {})
print('effective tools:', t)
assert t.get('read') and t.get('bash'), 'need read+bash enabled'
deny_keys = [k for k, v in t.items() if k not in ('read', 'bash') and v]
assert not deny_keys, f'integrity violation: unexpected enabled tools {deny_keys}'

prompt = (E / 'cl2_13_opencode_prompt.txt').read_text(encoding='utf-8')
code = cli('cl2_13_raw', 'opencode run --pure --agent cl213audit --format json '
           '--model opencode-go/deepseek-v4.1-flash ' + shlex.quote(prompt), env)

events = []
with open(E / 'cl2_13_raw.stdout', encoding='utf-8') as f:
    for line in f:
        try: events.append(json.loads(line))
        except json.JSONDecodeError: pass
exitcode = {'exit_code': code, 'n_events': len(events)}
if events:
    parts = [e.get('part', {}) for e in events if e.get('type') in ('part.text', 'text')]
    text = ''.join(p.get('text', '') for p in parts) if parts else ''
    infos = [e.get('part', {}).get('info', {}) if isinstance(e.get('part'), dict) else
             e.get('info', {}) for e in events]
    models = sorted({(i or {}).get('providerID', '') + '/' + (i or {}).get('modelID', '')
                     for i in infos if isinstance(i, dict)})
    exitcode['models'] = models
    exitcode['text_chars'] = len(text)
    exitcode['audit_complete_marker'] = 'AUDIT_COMPLETE' in text
    exitcode['finish_stop'] = any((i or {}).get('finish') == 'stop' for i in infos if isinstance(i, dict))
    bash_uses = sum(1 for e in events if e.get('type') == 'tool_use' and
                    isinstance(e.get('part'), dict) and e['part'].get('tool') == 'bash')
    exitcode['bash_tool_uses'] = bash_uses
save('cl2_13_completion.json', exitcode)
print('exit:', code)
print(json.dumps(exitcode, ensure_ascii=False))
