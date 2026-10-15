import pathlib,subprocess,sys,time,json
r=pathlib.Path('D:/Code/ldiar');e=r/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1'
while not (e/'js_02/cap_20261010_180557/MANIFEST.json').exists():time.sleep(2)
commands=[['node','tools/hf_mainline_points/enrich_js.js','js_02'],[sys.executable,'-X','utf8','-B','-W','error','tools/hf_mainline_points/score_js.py','js_02']]
for i,cmd in enumerate(commands):
 with (e/f'JS_FINISH_{i}.stdout').open('x') as out,(e/f'JS_FINISH_{i}.stderr').open('x') as err:
  c=subprocess.run(cmd,cwd=r,stdout=out,stderr=err)
 (e/f'JS_FINISH_{i}_EXIT.json').write_text(json.dumps({'command':cmd,'exit':c.returncode}),encoding='utf8')
 if c.returncode:sys.exit(c.returncode)
