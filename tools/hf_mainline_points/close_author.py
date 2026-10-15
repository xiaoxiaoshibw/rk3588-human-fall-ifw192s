"""Append author delivery records; preserve earlier evidence and reviewer conclusions."""
import hashlib,json,sys,time
from pathlib import Path
R=Path(__file__).resolve().parents[2]
E=R/'docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1'
PS=R/'sidequests/human_fusion_lab_next/pointset/r01'
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
files=list((R/'tools/hf_mainline_points').glob('*.py'))+list((R/'tools/hf_mainline_points').glob('*.js'))+[PS/n for n in ['research_retention.py','research_retention_guard.py','config_research_retention.json','config_research_retention_guard.json','server.py','app.js','index.html','test_retention.py','test_retention_guard.py']]
with (E/'FINAL_SOURCE_MANIFEST.json').open('x',encoding='utf8') as f:
 json.dump({'time_unix':time.time(),'files':{str(p):sha(p) for p in files},'python':sys.version,'post_inference_ui_change':'explicit missing original source status and opaque null; no algorithm change'},f,indent=2)
entry='''## 2026-10-14 HF-MAINLINE-POINTS-01 实施交付（原始源当前缺失，复跑BLOCKED）

用户明确授权计划v3实施、实验、原页面、1966帧回归、返工和OpenCode只读审核，覆盖下方旧“仅计划授权”。Codex单算法writer，加载ponytail与scientific-toolkit-skill。首轮6×1966及护栏2×1966源行/因果前缀验证完成；护栏最大中心偏移0.093991m、无新增轴缺测，但粗槽跳变仍退化，299975点次均UNKNOWN，无可信完整人体/纯度收益，不晋级R1默认。80帧明确REUSED_REGRESSION。最终浏览器检查发现captures/remote为空，18个主链meta/points文件当前缺失，原录制复跑及opaque查询BLOCKED，冻结页面/全量账本仍可用；不归因、不猜测替换。当前[唯一验收v1](evidence/2026-10-14_hf_mainline_points_r1/ACCEPTANCE_V1.md)/[报告](evidence/2026-10-14_hf_mainline_points_r1/FINAL_REPORT.md)/[交付索引](evidence/2026-10-14_hf_mainline_points_r1/CURRENT_DELIVERY_INDEX.md)，SUBMITTED，未ACCEPTED。页面http://[::1]:8944/（IPv4同端口另有PLANE服务，不停止其进程）。无训练、采集、部署、提交推送、旧GT或生产修改；物理/完整人体/晋级BLOCKED，独审结论独立登记。

'''
for p,txt in [(R/'docs/human_fall/WORKFLOW.md',entry),(R/'docs/human_capture/README.md',entry.replace('](evidence/','](../human_fall/evidence/'))]:
 with (E/(p.name+'.pre_delivery')).open('xb') as f:f.write(p.read_bytes())
 p.write_text(txt+p.read_text(encoding='utf8'),encoding='utf8')
accept=sha(E/'ACCEPTANCE_V1.md')
with (R/'docs/human_fall/returns/HF-MAINLINE-POINTS-01.md').open('a',encoding='utf8') as f:
 f.write(f'''\n## 2026-10-14 实施回传 · Codex\n\n状态SUBMITTED；当前原始源复跑BLOCKED，非ACCEPTED。唯一验收docs/human_fall/evidence/2026-10-14_hf_mainline_points_r1/ACCEPTANCE_V1.md，SHA256 {accept}。实际技能C:/Users/30680/.codex/skills/ponytail/SKILL.md及C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。起始branch/HEAD/全树差异见BASELINE_BEFORE、ENVIRONMENT、GIT_STATUS_BEFORE，源码SHA见FINAL_SOURCE_MANIFEST。\n\n### 集中诊断与实际变更\n\nPython当前background_removed近目标真实点可追溯恢复，独立FIT覆盖33/33无鉴别力；JS近地1159标签点实际first reason背景而非高度。复用原加载/掩码/聚类，隔离research_retention.py和guard.py，旧R3仅FG契约保留。首轮中心0.355695m/新增9轴缺测，按旧参数依据加整组扰动护栏；中心最大0.093991m、新轴缺测0，仍有粗槽跳变退化。新增点UNKNOWN，不声称人体改善。共享页面scene_change外部变更单列保留。\n\n### 逐条验收\n\nPR01 FAIL外部漂移；PR02当前BLOCKED（此前基线/1966帧成员重现PASS，最终原始源缺失）；PR03/04/05/06/07a/07b/09作者自验PASS；PR07c NOT_EVALUATED缺家具分母；PR08当前原录制查询BLOCKED，冻结页面/实际下载49130条可用；PR10交付及独审另记；PR11/12 BLOCKED。逐ID命令、范围、退出码以唯一验收及报告引用的原日志为准，单测总数不替代结果。\n\n### 未闭合与独审\n\nFINAL_SOURCE_AVAILABILITY记录18个主链原文件缺失，恢复SOURCE_BINDINGS同SHA原文件才能重跑，不能猜测替换；本writer未删除。所有旧全帧验证/失败日志保留，80帧标REUSED_REGRESSION。完整召回/家具污染/解剖/泛化UNKNOWN；设备物理未跑，无部署/Git写/confirmed/默认晋级。独审读取FINAL_REPORT、唯一表、索引、FINAL_SOURCE_MANIFEST和各轮ALL_FRAME_VERIFICATION；结论原样另存。\n''')
p=E/'REVIEW_PROMPT_01.md'
with p.open('a',encoding='utf8') as f:
 f.write('''\n\n最终当前事实（优先于早先清单）：主候选为run_02护栏combined/feedback，旧run_01六臂为消融与失败保留。须读research_retention_guard.py、config_research_retention_guard.json、verify_retention_v2.py、run_02/ALL_FRAME_VERIFICATION.json、run_02/ANALYSIS.json、REWORK_02_FROZEN.json与GUARD_VERIFICATION。80帧及全回归已在护栏返工中重用，作者标REUSED_REGRESSION，不是新独立测试。JS最终身份依据verify_js_identity.js与JS_ORDINAL_IDENTITY_PROOF.json，原坐标匹配仅等价验证。\n\n最终额外阻断：captures/remote为空，八动作与131958共18个meta/points缺失，见FINAL_SOURCE_AVAILABILITY、BROWSER_CHECK、API_CHECK_SOURCE_MISSING。此前API_CHECK_FINAL有真实原字节PASS但不能冒充当前可用；现在查询明确MISSING_ORIGINAL_SOURCE/opaque=null，冻结账本可查/实际完整下载49130条可用，原录制复跑BLOCKED。作者未删除、不归因、不生成替代原数据。请审查作者是否仍有夸大或不一致，不要求猜测恢复丢失原录制。端口为IPv6回环http://[::1]:8944，IPv4另有PLANE服务未停止。\n''')
print('AUTHOR RECORDS SAVED',flush=True)
