"""Preserve the feasibility probe and append its result; do not authorize a milestone."""
import hashlib
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / "pc_apps/human_replay"))
import leveling as L

baseline = json.loads((OUT / "00_baseline.json").read_text(encoding="utf-8"))
prefix = str(OUT.relative_to(ROOT)).replace("\\", "/") + "/"
drift = []
for name, item in baseline["files"].items():
    if name.startswith(prefix):
        continue
    p = ROOT / name
    if "sha256" in item and (not p.is_file() or L.sha(p) != item["sha256"]):
        drift.append(name)
assert not drift, drift
result = json.loads((OUT / "results.json").read_text(encoding="utf-8"))
rows = [r for s in result["positives"] for r in s["rows"]]
hits = sum(r["semantic"] == "HUMAN_EVIDENCE" for r in rows)
assert len(rows) == 24
text = f"""# 新会话人体语义冻结复核：优化可行性（2026-10-08）

状态：SUBMITTED（可行性诊断完成）；不声明新算法已交付或生产已改善。

用户询问能否进一步优化。按既有离线诊断约定，使用已有 S-A+ v1 冻结分类原型做新增数据复核；没有调阈值、改生产代码或启用旗标。

## 实测

- 四段新人体会话，每段第0/中间/最后帧，各检查原固定圆柱区域与参考保留区域：人体结构证据 {hits}/24。等价于12个抽样帧的两种相关输入，不是24个独立样本。
- 新空场第0/142/284帧自动提取全部点数≥400的XY连通结构分量：12个簇帧样本（约4个空间分量×3帧），HUMAN {result['empty_human']}/12。
- 普通静立样本 HEAD/TORSO/LEGS 有证据；举左手样本 ARM/TORSO/LEGS 有证据，但 HEAD=false，仍由腿+躯干组合支持人体判定，不能宣称头部识别已解决。
- 结果见 results.json / probe.run.log。冻结函数通过精确源片段运行，原文件 SHA 与函数片段 SHA 均保存；没有执行历史脚本main或回写旧证据。

## 可以推进的优化范围

第一优先：直立/举臂语义判定。先将已有结构原型作为离线旁路，取清理后的真实簇全点集，逐帧与当前 joint_status 比较。两段gate PASS用v2输出；另两段WARN仅做REF影子诊断，不混入正式v2资格。需要检查人与家具合簇及负样本误判，不能只保留人体圆柱。

第二优先：人工核实隔板旁被删除的区域边缘点与cleanup少量删除点，获得人与物的明确标签。91.9%圆柱区域保留不能直接当作人体保留；标注补齐之前不以缩小区域或改删除半径让指标变绿。

配准对应集/调度/gate为独立项：新数据已有两段PASS，另两段WARN。若要改这层，按仓库规定建立新工单与设计评审，并验证静态面距离/覆盖/支撑，不靠降低50%门槛。

## 下一轮可审查的目标（草案，不是生效验收表）

1. 全帧真实簇输入，输出 HUMAN_EVIDENCE / OBJECT_EVIDENCE / UNKNOWN 与数值原因；输入缺失不补结构。
2. 举手与普通静立的语义漏判和UNKNOWN分布公开，对比旧规则；冻结参数，不用本批新数据反复调参又充当留出。
3. 新空场全部相关簇、家具/箱子/格栅/远场及旧负样本逐帧复测；有限样本0误判不作普遍准确率承诺。
4. 时间确认先做离线票序列与track关联审计：按实际帧检查3/5，不把单帧多个簇当多帧票，不忽略断帧。既有Tracker缺陷未修复时不能把模拟确认率当可靠生产结论。
5. 保留/融合/配准/Tracker/Fall生产逻辑不在本轮可行性探针中修改。语义切换、artifact重签/安装、生产旗标必须进入明确工单与接入评审。

## 记录与边界

- 本轮仅 frozen_probe.js、record_probe.py、baseline/结果/日志/报告，returns/HR-W03.md追加；原始captures、所有生产文件、历史证据无漂移。
- 现行表仍为R3.7 06_test_matrix.md v1及HRRETV2_ACCEPTANCE.md v1；本轮T37/T38/T39、V2-01..14均NOT_RUN，不替代上一轮PASS/FAIL/BLOCKED。H01–H08仅是语义草案：本轮支持H02/H03/H06抽样诊断，不构成正式验收。全帧整簇、人体GT、多人物/多姿态均未闭合。
- Node v24.14.0；probe.run.log exit0。完整性记录 integrity.json。未运行板端、部署、采集或ML。
- ponytail实读路径沿用本聊天 C:/Users/30680/.codex/skills/ponytail/SKILL.md；复用S-A+已有函数与上一轮点云抽样，不引入依赖。

结论：数据足以开始针对直立/举臂的离线语义优化与全帧旁路验证；尚不足以直接切换生产判定或宣布通用人体识别完成。
"""
with (OUT / "README.md").open("x", encoding="utf-8") as stream:
    stream.write(text)
ret = ROOT / "docs/human_capture/returns/HR-W03.md"
old = ret.read_bytes()
append = f"\n\n## 2026-10-08 新会话语义冻结复核 r1（优化可行性）\n\n- 用户询问能否进一步优化；承接离线诊断约定，只做已有S-A+参数冻结的新数据验证。状态SUBMITTED，不授权/交付新生产算法。\n- 证据 evidence/2026-10-08_semantic_new_holdout_r1/README.md / results.json / probe.run.log：四段×3帧×原区域/参考保留区域 HUMAN_EVIDENCE {hits}/24；空场4分量×3帧0/12 HUMAN。相关区域样本、同一人、非全帧整簇、非逐点GT；举臂ARM可见但HEAD未检出。\n- 优先方向：真实簇全帧语义旁路AB+空场/家具负例+按实际帧的确认审计；隔板旁边缘GT另闭合；registration协议/算法/gate改动需独立工单设计评审。\n- 现行R3.7与HRRETV2唯一表不变，本轮T37/T38/T39和V2全NOT_RUN，语义H01-H08仍草案；W03 REWORK_REQUIRED不变。生产源码/captures/历史证据未改、未重签/开旗标/部署/采集/ML；本文仅追加。\n- 起始 {baseline['branch']} / {baseline['head']}，完整tracked+untracked SHA见00_baseline.json；ponyail实际读取 C:/Users/30680/.codex/skills/ponytail/SKILL.md（同聊天），Node24.14.0 probe exit0，record_probe Python-X utf8 -B -W error；完整性见integrity.json。\n"
with ret.open("ab") as stream:
    stream.write(append.encode("utf-8"))
assert ret.read_bytes()[:len(old)] == old
with (OUT / "integrity.json").open("x", encoding="utf-8") as stream:
    json.dump({"preexisting_file_drift": drift, "baseline_count":len(baseline["files"]),
        "return_prefix_unchanged":True,"return_original_sha256":hashlib.sha256(old).hexdigest(),
        "return_final_sha256":L.sha(ret),"report_sha256":L.sha(OUT / "README.md"),
        "frozen_probe_sha256":L.sha(OUT / "frozen_probe.js"),"binding":result["binding"]},stream,indent=2)
print("Frozen semantic feasibility recorded; no preexisting drift")
