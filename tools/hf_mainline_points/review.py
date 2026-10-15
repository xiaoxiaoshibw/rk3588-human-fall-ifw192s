"""Requested OpenCode read-only reviewer; raw conclusion is saved without author editing."""
import json,os,shutil,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];E=ROOT/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1'
def main(round_id):
 prompt=E/f'REVIEW_PROMPT_{round_id}.md'
 env=os.environ.copy()
 permissions={'*':'deny','read':'allow','glob':'allow','grep':'allow','external_directory':{'D:/Code/radar/**':'allow','D:\\Code\\radar\\**':'allow','C:/Users/30680/.codex/skills/ponytail/**':'allow','C:\\Users\\30680\\.codex\\skills\\ponytail\\**':'allow'}}
 env['OPENCODE_CONFIG_CONTENT']=json.dumps({'snapshot':False,'permission':permissions,'agent':{'plan':{'permission':permissions}}})
 cmd=[shutil.which('opencode.cmd'),'run','--pure','--agent','plan','--model','opencode-go/deepseek-v4.1-flash','--format','json','--dir',str(ROOT),'--title','HF-MAINLINE-POINTS-01 read-only review '+round_id,'--file',str(prompt),'--','请完整只读审核所附任务。最终审核结论直接输出，禁止写文件、运行命令或调用其他代理。']
 with (E/f'OPENCODE_REVIEW_{round_id}.jsonl').open('x',encoding='utf8') as out,(E/f'OPENCODE_REVIEW_{round_id}.stderr').open('x',encoding='utf8') as err:
  c=subprocess.run(cmd,cwd=ROOT,env=env,stdout=out,stderr=err)
 with (E/f'OPENCODE_EXIT_{round_id}.json').open('x',encoding='utf8') as f:json.dump({'command':cmd,'exit':c.returncode,'requested_model':'opencode-go/deepseek-v4.1-flash','snapshot':False,'permission':permissions},f,ensure_ascii=False,indent=2)
 texts=[];sessions=set();tools=[]
 for line in (E/f'OPENCODE_REVIEW_{round_id}.jsonl').read_text(encoding='utf8').splitlines():
  try:r=json.loads(line)
  except ValueError:continue
  if r.get('sessionID'):sessions.add(r['sessionID'])
  if r.get('type')=='text':texts.append(r['part']['text'])
  if r.get('type')=='tool_use':tools.append({'tool':r['part'].get('tool'),'state':r['part'].get('state')})
 with (E/f'OPENCODE_REVIEW_{round_id}.md').open('x',encoding='utf8') as f:f.write('\n\n'.join(texts))
 with (E/f'REVIEW_AUDIT_{round_id}.json').open('x',encoding='utf8') as f:json.dump({'sessions':sorted(sessions),'tools':tools,'exit':c.returncode,'reviewer_conclusion_preserved_verbatim':True},f,ensure_ascii=False,indent=2)
 print('REVIEW',round_id,'exit',c.returncode,'sessions',sessions,'text parts',len(texts),flush=True)
if __name__=='__main__':main(sys.argv[1])
