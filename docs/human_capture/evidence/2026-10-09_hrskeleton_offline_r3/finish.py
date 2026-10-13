"""Guided UI-only closeout. No algorithm execution or human-label generation."""
import ast
import hashlib
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from record import OUT, ROOT, RETURN, sha, save

def read(p):
    return json.loads(Path(p).read_text('utf8'))

integrity = read(OUT/'integrity.json')
assert integrity['pass']
baseline = read(OUT/'00_baseline.json')
original_return = baseline['files'][RETURN.relative_to(ROOT).as_posix()]
assert RETURN.stat().st_size == original_return['bytes'] and sha(RETURN) == original_return['sha256']
r1 = OUT.parent/'2026-10-09_hrskeleton_offline_r1'
upstream = read(r1/'delivery_manifest.json')
pins = {n:sha(r1/n) for n in ['review.js','review_config_final.js','input_manifest.json','prototype_params_v1.json','skeleton.py','run_offline.py']}
for n,h in pins.items():
    assert h == upstream['files'][n]['sha256']
save(OUT/'upstream_pins.json',pins)
for p in OUT.glob('*.py'):
    ast.parse(p.read_text('utf8'),feature_version=(3,8))
save(OUT/'compatibility.json',{'python38_syntax':'PASS','actual_python38_execution':'NOT_RUN'})
status = read(r1/'acceptance_status.json')
status['delivery_status']='SUBMITTED / BLOCKED; R3 guided review UI only'
status['scope']='R1 algorithm outcomes carried forward by unchanged source/data SHA; R3 only revisits UI and asset checks; no real GT created'
for r in status['rows']:
    if r['id']=='SKO-01':
        r['evidence']='R3 full baseline 6711 paths/44,727,944,634 bytes; dirty/tracked/untracked/ignored assets included'
    elif r['id']=='SKO-13':
        r['evidence']='Chinese responsive guided UI; 10 synthetic UI contracts and 10 actual browser checks; original receipt/enum/source/export core reused; user old unsubmitted draft backed up, original tab untouched'
    elif r['id']=='SKO-17':
        r['evidence']='R3 guide_tests_verified exit0; Python -B -W error; old6711 asset SHA unchanged; return old prefix checked before/after append; original production/algorithms/evidence unchanged'
    elif r['id']=='SKO-18':
        r['evidence']='R3 UI-only SUBMITTED/BLOCKED; ponytail read and recorded; no agents, no production, no new algorithm or fabricated GT'
    else:
        r['evidence']='R1 unchanged evidence carried forward: '+r['evidence']
save(OUT/'acceptance_status.json',status)
table='| ID | status | scope |\n|---|---|---|\n'+'\n'.join('| %s | %s | %s |'%(r['id'],r['status'],r['evidence']) for r in status['rows'])
(OUT/'README.md').write_text('''# 简明人工标注入口

打开 http://127.0.0.1:8884/review.html 。用户反馈原界面不会使用，本轮只改善审阅工具，保持R1成员/坐标/参数/节点与导出契约。

先只回答一个问题：蓝色这整组点属于什么？点击“确定是人”“确定是静态物”“人和物体混在一起”或“看不清/无法确认”。不确定可以如实选择，不强迫认人。这个选择本身不会写出human sidecar。

大图可用滚轮放大，“换个方向看”“从上面看”切换投影。每个视图仍显示当前完整簇，灰色其他目标作为参照；不是重新裁人体或改变成员。

随后：选择中文身体部位，显式选可见性，圈真实点并保存部位。明确无法确认剩余部位时可点击对应按钮；只有实际点击才记录不确定，不补坐标。填写实际标注者/连续目标编号并真实核对连续性，再保存目标与下载文件。

当前仍是页内草稿；离开前下载，之后导入继续。原8883旧页面未修改，也未替用户删除其圈选；user_unsubmitted_draft.json只备份旧页未提交控件值，counts_as_real_gt=false。

![窄侧栏中的新界面](after_narrow.jpg)

此处没有真实GT或新的骨架试验。只读服务保留给用户实际操作：exec session30960，127.0.0.1:8884。既有8883服务为session61867。实际操作结束后停止，不能把本轮测试状态当真人标注。
''',encoding='utf8')
(OUT/'REVIEW.md').write_text('''# R3 标注工具易用性复审

SUBMITTED / BLOCKED，未ACCEPTED；单writer Codex，无代理/OpenCode/外部签署。用户“不会用啊看不懂”是本轮现有离线审阅工具返工依据，没有扩大算法或数据范围。

根因：用户真实侧栏约570px宽，原三图并排只有约165px/图；完整SHA/JSON和英文参数在主要操作路径中。新R3只新增review.html、guide.js、只读serve_review.py及测试/记录，不改旧页或生产。一次一张大投影、四个中文目标答案、中文帧/部位/错误、分步保存/下载；诊断和原row折叠保留。冻结R1 loader/receipt/row picking/invalid source/export仍直接只读复用，原enum/value/id不改。侧栏实测与before/after截图留档。

user_unsubmitted_draft.json保存用户旧页已圈选但未提交的控件值，明确unsubmitted/counts_as_real_gt=false；未代填reviewer、PERSON、连续身份或可见正例。旧用户页保持原状态；新页面由用户实际判断。其余未检查部位“不确定”快捷按钮只有用户主动明确选择时才填写不确定，无自动人体资格或坐标。

guide_tests_verified实际exit0，10项合成检查涵盖枚举/索引不变、幂等翻译、视图、点数、错误、原ID唯一和R1源码/输入/参数SHA。实际浏览器10项UI/边界检查见browser_checks.json；与合成分列。可见但无圈点/异簇row/缺reviewer均拒绝，空帧保留；实际human文件由Codex创建0。测试页已关闭，用户新旧页面保留。首次重跑自测因固定结果文件已存在exit1（exclusive output保护），失败日志保留；指定新输出文件后通过。首次自动化填点编号没有展开折叠区而中断，展开后完成实测；未以中断算PASS。

新Python3.8语法检查PASS；实际仍PC Python3.12，Python3.8实际执行NOT_RUN。无新依赖、采集、板端连接、部署、driver/config/artifact/ML/W04-W07变更。旧6711路径逐SHA/大小/缺失/符号链接核对，changed=[]、unexpected_new=[]，HEAD/branch不变；return末尾追加并另核旧前缀。

ponytail实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）；复用现成loader/export与canvas，不引入新框架或新模型。

下表原算法项沿用已核SHA的R1证据，本轮不宣称重跑或解除真人GT阻断。唯一表仍HR_SKELETON_OFFLINE_ACCEPTANCE.md v1。

'''+table+'\n\n停止于现有标注工具可操作的handoff，不自动执行真实节点或进入主线。服务保留运行给用户实际标注，符合当前用户交接意图。\n',encoding='utf8')
append='\n\n## '+datetime.now(timezone(timedelta(hours=8))).isoformat()+' R3：标注工具易用性返工\n\n'
append+='用户反馈“不会用啊看不懂”。单writer Codex只新增R3中文分步审阅入口（127.0.0.1:8884）、UI helper/只读服务/测试和证据；复用冻结R1可信加载/圈点/导出核心。大图逐视图切换、四个中文目标判断、中文部位与错误，诊断折叠。用户旧圈选已备份为未提交草稿，旧页未改，不计GT。\n\n'
append+='ponytail实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）。起始master / '+baseline['head']+'；全6711路径/44,727,944,634字节基线与dirty记录见本R3。guide_tests_verified exit0（10合成检查），browser_checks另列10实际浏览器检查，首次输出重跑保护/折叠区自动化中断记录保留。Python -B -W error与3.8语法通过。\n\n'
append+='状态SUBMITTED / BLOCKED，未ACCEPTED；SKO13界面检查PASS，其他算法/GT项只沿用未改R1证据，仍12 PASS/6 BLOCKED，不冒充新人体性能。6711旧路径SHA无漂移，HEAD/branch不变，return旧前缀追加前后核对。完整逐ID/原因/源SHA/边界见 [R3 REVIEW](../evidence/2026-10-09_hrskeleton_offline_r3/REVIEW.md)。\n\n'
append+='没有真实人工标签由Codex生成，无新算法运行，无代理、生产修改、板端/采集/部署/commit/push/重签/ML；新旧只读服务留给用户实际标注（8884 session30960，8883 session61867），测试页已关闭。交付后不自动进入后续阶段。\n'
(OUT/'return_append.md').write_text(append,encoding='utf8')
with RETURN.open('ab') as f:
    f.write(append.encode('utf8'))
save(OUT/'prefix_check.json',{'original_bytes':original_return['bytes'],'original_sha256':original_return['sha256'],
 'prefix_unchanged':hashlib.sha256(RETURN.read_bytes()[:original_return['bytes']]).hexdigest()==original_return['sha256'],
 'return_final_sha256':sha(RETURN)})
save(OUT/'delivery_manifest.json',{'files':{p.relative_to(OUT).as_posix():{'sha256':sha(p),'bytes':p.stat().st_size} for p in sorted(OUT.rglob('*')) if p.is_file() and p.name!='delivery_manifest.json' and not p.name.startswith('finish.')},
 'return_final_sha256':sha(RETURN),'excludes':'manifest itself and finish command source/log/run metadata completed after snapshot; finish.py source SHA in finish.run.json',
 'status':'SUBMITTED / BLOCKED','human_gt_created_by_codex':0})
print('GUIDED_UI_SUBMITTED; old assets unchanged; return prefix intact; no human GT created')
