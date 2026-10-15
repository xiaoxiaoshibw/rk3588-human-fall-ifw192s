"""Close the signed-axis rework without overwriting the initial failure report."""
import sys,json
from pathlib import Path
root=Path('D:/Code/ldiar');here=root/'sidequests/human_fusion_lab_next/pointset/r01';sys.path.insert(0,str(here))
from actions import read,sha,dump
e=Path(__file__).resolve().parent
assert read(e/'SIGN_VERIFICATION.json')['status']=='PASS'
browser=read(e/'BROWSER_SIGNED.json');assert browser['status']=='PASS'
assert all(browser['source_sha256'][n]==sha(here/n) for n in ['app.js','index.html','server.py'])
assert read(e/'FINAL_CORE_AUDIT.json')['status']=='PASS'
sign=read(e/'SIGN_COMPARISON.json');detail=read(e/'SIGN_REGRESSION_DETAILS.json');global_audit=read(e/'FINAL_EXISTENCE_AUDIT.json')
(e/'FINAL_REPORT_INITIAL.md').write_bytes((e/'FINAL_REPORT.md').read_bytes())
s=(e/'FINAL_REPORT.md').read_text(encoding='utf8')
s=s.replace('6方案11796帧方案因果源重放','原6方案11796帧方案因果源重放，另完成2条符号修正×1966帧（总15728帧方案）')
s=s.replace('全树保护发现383个其他录制/配平产物消失，未解释，不报全树PASS；','全树保护首次发现383个其他录制/配平产物消失，最终存在性尾检发现'+str(global_audit['missing_count'])+'个其他文件缺失，归因UNKNOWN，不报全树PASS；')
s=s.replace('原录制/GT/生产/模型保持','本轮绑定原录制、已用GT与生产算法源/模型保持')
s=s.replace('|R1默认 / R2 component20|','|R2 component20|').replace('|R1默认 / R2 axis|','|R2 axis|')
s=s.replace('实验菜单保留R2和6个R3方案','实验菜单保留R2、原6个R3方案和2条符号修正对照')
s=s.replace('15项pointset','16项pointset（含符号寿命/换ID/当前均值检验）')
addition='''## 有界符号连续性返工与未解决退化

首次全帧后发现9次轴符号翻转，沿原诊断帧集合做根因检查：当前全局/局部轴按Z符号初始化，与继承方向的符号约定混合，近水平轴会翻转，粗槽最高跳变1.191m。SIGN_DIAGNOSIS_BEFORE_REPLAY、FROZEN_SIGN先于新2×1966全帧；只取动作诊断，不据HOLDOUT反调。原FINAL_REPORT_INITIAL、r3/r3_feedback及全部失败输出只读保留。

新增r3_signed/r3_signed_feedback只统一当前轴线的有向符号。符号参考来自此前≤.5s独立当前强几何观测；继承方向不刷新寿命，换目标/缺目标/倒退/gap清除。所有点集、原无向轴线、tracker、posture保持，粗槽用当前源点重新求均值，无节点回填。它是方向约定，不是人体头尾/解剖标定。

|返工方案|新增当前成员|轴缺测|相对R1新轴缺测|符号翻转|>45°无向变化|空场目标|
|---|---:|---:|---:|---:|---:|---:|
'''
for v,t in sign['summary'].items():addition+=f"|{v}|{t['added_count']}|{t['axis_missing']}|{t['new_axis_missing']}|{t['sign_flip']}|{t['axis_large_turn']}|{t['empty_targets']}|\n"
addition+='''
符号翻转9→4，解决原6处，但新增082623/f124一处，剩余082906/f94、082717/f263、082623/f124/f231均在可靠符号参考寿命届满后重新观测，orientation.reference=None。最大粗槽跳变仍1.191m；没有延长寿命或用不可靠继承轴伪造稳定性。无向轴>45°变化仍2次，9帧缺测保持。四处边界和新f124退化不能被总量改善掩盖，见SIGN_REGRESSION_DETAILS；当前只能说明部分连续性改善，不能宣称解剖精度或全程粗槽连续通过。两条符号修正均不晋级默认。

新增3932帧方案重算原始当前坐标，前缀原数据视图切断未来行，签名参考逐一绑定过去已核验的独立当前强观测；所有成员与原固定/独立feedback结果完全相同，所有新粗槽均值当前支撑PASS。SIGN_VERIFICATION为完整结果。最终页面重新以headed Edge查看75案例三视角及全部交互（BROWSER_SIGNED，0 pageerror），包括签名和原失败版切换。当前主图最多1500点，采样数明确显示；完整成员和新增/拒绝证据保留JSON，不将渲染像素当全量测量。

'''
s=s.replace('## 失败、代价与结论边界',addition+'## 失败、代价与结论边界')
s=s.replace('383外部路径缺失','首次383、最终'+str(global_audit['missing_count'])+'其他路径缺失；核心重新哈希PASS')
s=s.replace('383个其他captures文件在基线后消失（remote36、leveled347），原因UNKNOWN','首次383个其他captures文件在基线后消失（remote36、leveled347），最终'+str(global_audit['missing_count'])+'文件缺失（历史证据、诊断产物、缓存及其他捕获/配平产物等），原因UNKNOWN')
s=s.replace('本轮9段源与旧输出/生产/GT范围保持','FINAL_CORE_AUDIT再次哈希核对'+str(read(e/'FINAL_CORE_AUDIT.json')['hash_checked_files'])+'个生产算法源/模型/已用GT/本轮9输入/旧R1-R2输出文件，0差异；缓存与无关图标/备份缺失仍列全树FAIL，不宣称整树保全')
s=s.replace('`check_r3_browser.py`复现实际浏览器','`check_r3_browser.py --signed`复现最终实际浏览器；符号返工为`axis_sign_r3.py`＋`verify_sign_r3.py`（既有输出禁止覆盖）')
(e/'FINAL_REPORT.md').write_text(s,encoding='utf8')
receipt=read(e/'ACCEPTANCE_FINAL.json');receipt.update(sign_rework_self_check='PASS_WITH_FOUR_RECORDED_SIGN_FLIPS',total_frame_variants=15728,
    core_preservation='PASS',full_tree_preservation='FAIL_UNEXPLAINED_MISSING',missing_global_files=global_audit['missing_count'])
(e/'ACCEPTANCE_FINAL.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf8')
for path in [root/'docs/human_capture/README.md',root/'docs/human_fall/WORKFLOW.md']:
    t=path.read_text(encoding='utf8');t=t.replace('全树保护R301因383非本轮capture文件缺失未整体通过','全树保护R301首次383、最终'+str(global_audit['missing_count'])+'其他文件缺失未整体通过',1)
    t=t.replace('13槽仅当前点支持。','13槽仅当前点支持；符号返工另2×1966帧，翻转9→4但新f124退化保留。',1);path.write_text(t,encoding='utf8')
readme=here/'README.md';t=readme.read_text(encoding='utf8');t=t.replace('全1934+32帧×6方案源点与因果前缀重放PASS','原6＋符号返工2方案全1934+32帧源点与因果前缀重放PASS，9→4符号翻转但新f124/最大槽跳变1.191m保留',1);readme.write_text(t,encoding='utf8')
ret=root/'docs/human_capture/returns/HFUS-POINTSET-ACTIONS-02.md'
with ret.open('a',encoding='utf8') as f:
    f.write(f'''\n## 2026-10-14 R3 符号返工最终追加回传

- 工单/轮次/执行者：HFUS-POINTSET-ACTIONS-02 / R3；Codex唯一writer，SUBMITTED非ACCEPTED。
- 唯一验收：ACCEPTANCE_V1.md SHA `{sha(e/'ACCEPTANCE_V1.md')}`；逐ID详见ACCEPTANCE_FINAL.json。R302–R308为作者工程自验PASS；R301核心范围PASS、整树FAIL/归因BLOCKED。设备/物理/独审NOT_RUN。
- 起始master/HEAD c21c443b0befe559e08283edb0efc2af02dcc6b8，既有脏树保留；源码与配置SHA见SOURCE_SHA_FINAL/FROZEN_EXPERIMENT/FROZEN_SIGN。
- 实际技能：C:/Users/30680/.codex/skills/ponytail/SKILL.md、C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。

|诊断/ID|根因与消费者|实际变更|保留行为|
|---|---|---|---|
|R302/R303|DBSCAN碎裂、孤立邻点与背景接触|experiment_r3.py与config_research_r3.json；当前图块/背景/过去支持|原core/actions/R1/R2只读；身份UNKNOWN|
|R304|全局轴方差竞争与近水平符号不一致|当前局部子空间；axis_sign_r3.py/.json有界符号参考|13槽当前均值、继承不刷新、无预测节点|
|R306|成员中心反馈可能改变关联|独立r3_feedback重选，signed_feedback只变符号|原tracker不改；身份漂移UNKNOWN|
|R307|同帧当前方案效果与风险需可审查|原app/index/server小范围扩展|R1默认、legacy/R2和失败方案可切换|

|验收|实际offline/synthetic命令与状态|证据|
|---|---|---|
|R301|final_core_audit.py exit0；preserve.py exit1（全树缺失未掩盖）|FINAL_CORE_AUDIT / FINAL_EXISTENCE_AUDIT / 原FAIL|
|R302–R306|experiment_r3.py、verify_r3.py、axis_sign_r3.py、verify_sign_r3.py exit0，合计15728帧方案|全帧与符号核验日志，源行XYZ/过去参考/当前均值|
|R304边界|16项unittest -B -W error exit0，SYNTHETIC非物理GT|TESTS_POINTSET_SIGN.log|
|R307|headed Edge原75＋最终75案例三视角、实际交互exit0|BROWSER_R3 / BROWSER_SIGNED / 失败日志保留|
|回归|console Python7、JS12、JS语法 exit0|TESTS_CONSOLE / TESTS_CONSOLE_JS|

点集807累计新增（每帧成员计）与固定/反馈源成员完全一致；f192恢复205/拒绝区外166。R3轴缺测9，原符号9次，新符号4次，解决6处但新造f124一处，最高粗槽跳变仍1.191m。身份/家具污染/解剖精度UNKNOWN、晋级BLOCKED，不能用节点数量冒充精度。

全树最终{global_audit['missing_count']}个其他文件缺失，归因未知、已询问用户其他清理背景，不擅自恢复或删除。核心源/模型/已用GT/9输入/旧输出末次哈希PASS；整个工作树保护未PASS。无采集/部署/训练/提交推送/confirmed。原始失败与初版报告保留，最终[FINAL_REPORT](../evidence/2026-10-14_hfus_pointset_actions_r3/FINAL_REPORT.md)。
''')
(e/'SOURCE_SHA_FINAL.json').write_text(json.dumps({str(p.relative_to(root)):sha(p) for p in here.iterdir() if p.is_file() and p.suffix in ['.py','.js','.html','.json','.yaml']}),encoding='utf8')
(e/'OUTPUT_SHA_FINAL.json').write_text(json.dumps({str(p.relative_to(root)):sha(p) for p in (here/'action_research_r3').rglob('*') if p.is_file()}),encoding='utf8')
dump(e/'FINAL_UI_BINDING.json',{'status':'PASS','default':'R1','final_browser':'BROWSER_SIGNED.json','source_sha256':browser['source_sha256'],
    'frozen_sign_unchanged':all(sha(here/n)==h for n,h in read(e/'FROZEN_SIGN.json').items()),'signed_self_check':'PASS_WITH_RECORDED_REGRESSIONS'})
print('SIGNED FINAL',sign['summary'],'global missing',global_audit['missing_count'],flush=True)
