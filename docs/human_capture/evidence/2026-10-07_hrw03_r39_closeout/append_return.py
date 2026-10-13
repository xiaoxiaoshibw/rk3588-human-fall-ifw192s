"""Append this round only; earlier returns remain a byte-identical prefix."""
import hashlib
import json
from pathlib import Path

out = Path(__file__).parent
root = out.parents[3]
target = root / 'docs/human_capture/returns/HR-W03.md'
before = target.read_bytes()
assert b'## R39-CLOSEOUT' not in before
baseline = json.loads((out / '00_baseline.json').read_text(encoding='utf-8'))
report = (out / '08_final_closeout.md').read_text(encoding='utf-8')
table = report[report.index('| ID | 状态 | 当前证据 |'):report.index('\nS1/2/3/5/6')]
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()
body = f'''

## R39-CLOSEOUT — W03收口审计/统计返工（2026-10-07）

### 本轮信息

- 授权：用户完整粘贴的本轮任务A–F；只收口W03，禁止进入W04–W09及registration R3.9生产接入。
- 执行者：本聊天Codex唯一writer，未派工/无并行writer；本机Node v24.14.0，Python日志/清单包装使用 `-B -W error`；模型身份不另推测。
- 状态：**SUBMITTED / REWORK_REQUIRED，未ACCEPTED**；GT子问题BLOCKED，设备/物理/部署/采集NOT_RUN。
- branch/HEAD：{baseline['branch']} / {baseline['head']}；原dirty tree保留，含untracked/ignored可读文件5466项基线见 `00_baseline.json`。
- 唯一验收：R3.7 `06_test_matrix.md` v1，SHA `70c82e401d0e4055ad85e1bef847d82dd32e718d682533ff25f22a24ac1f9b18`；不放宽或复制版本。
- ponytail实际读取：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`，full；复用现有PL/Three.js/OrbitControls，零新依赖。
- 本轮证据根：`docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/`。`r39_closeout`仅表示新收口轮，不是R3.9生产许可。

### 集中诊断与根因覆盖

| 缺陷/门 | 根因与消费者 | 本轮处置 | 保留行为 |
|---|---|---|---|
| BUG-R39-M01 / T38-06 | pipeline_frame簇数组相减→NaN，count字段输出数组；human_detect.js显示、R38 shadow统计均消费 | 先05_metric_reproduction复现/登记，然后三个表达式改用length | cleanup/聚类/特征/分类/Tracker/events逐位不变；严格delta==0门仍FAIL |
| T38-05/S4 | clean31损失：30注册后越过z=0.10，1reference命中；2点P本已cleanup，29属候选track1 | 原始point index与7帧逐点追踪，01/02和可标注viewer | 语义UNKNOWN31，不自动ground，不扣减既有31cohort |
| T38-06/S7 confirmation | 去背景同时改变点成员、几何/拓扑和独立Tracker票 | 257行逐点交集对应，r2纠正初次cleanup过归因，保存两侧历史 | 不称FP/FN；非静态155行真实人/物/连续性UNKNOWN |
| sparse gate | 9897raw×60%trim→5938 /11959=49.652981%，比50%差42keep | 固定R/t/支撑集诊断，07逐11959样本 | 不改ICP/matcher/PIPE/gate；旧gate仍DEGRADED |
| code binding | 最小统计修复改变PL全文件SHA，builder/code身份绑定失效 | native旧artifact STALE + SAFE=P实测；原代码/输入普通副本sandbox复现历史DEGRADED | 原artifact不重写、不静默重新绑定 |

### 实际变更

- production仅 `pc_apps/human_replay/human_pipe_lib.js` 三行诊断；SHA `{sha(root / 'pc_apps/human_replay/human_pipe_lib.js')}`，diff=`05_metric_fix.diff`，起始文件副本在baseline_code。
- 新增本轮evidence工具/JSON/报告/153帧只读viewer与人工GT校验、工单 `tickets/HR-W03-R39-CLOSEOUT.md`；README和HUMAN_RECOGNITION_NEXT_STAGE_PLAN只新增当前状态/证据/下一步；本文仅追加。
- 输入meta/bin、绑定leveling、registration四文件、registration/math源码及历史证据SHA收尾见 `09_scope_check.json` / `09_input_source_sha.json`。未commit/push/reset/checkout/clean/采集/部署/改网络。
- 保留初次03诊断（由03_confirmation_attribution_r2.json supersede）与真实失败：refinement首轮257/267计数断言exit1；before/after完整shadow按安全/共同门exit1。不回写旧R38/r1/r2/r3。

### 逐条验收（作者自验）

{table}

S1/2/3/5/6 PASS；S4/7 FAIL。逐命令stdout/stderr/exit为各 `.run.json` 与同名前缀日志；完整shadow165帧且第二跑确定性通过，exit1为T38-05/06真实失败。新metric5项、新r2 attribution5项、pipe35、replay45、registration逐ID、原R3.6 19项与当前STALE/故障全帧SAFE回归均通过，不以总数替代完成。

### 未闭合与限制

- W03最终 **REWORK_REQUIRED**：31语义/候选连续性GT未闭合，原gate和共同门未过；不能进入W04。
- new green61=gain39/history20/topology2；new purple70=gain58/history1/topology11；disappeared126=WD01静态102/reference8/history6/candidate-loss6/topology4。净green -65、purple -67，不能冒称误报/漏检。
- 跨P/S候选overlap split10/merge2需真人/静态/混合GT；cleanup自身split/merge0，S128帧count delta减少，严格delta==0仍FAIL。
- WD01 93423→1754（98.1225%）、WD02 159247→24508（84.6101%）只是本机离线背景残留改善，不是人体准确率。
- 原R3.6原代码sandbox完整digest `23830edefcb28f04774e328af64abce014dfeff35df75462f8a6f68d68eb3357` 精确复现；当前源码原script19项/算法结果/CSV SHA相同；新完整digest含新PL SHA，正常变为 `5da7a60d3e23b1b718194d21049246a7820ded62468018604e5171ca1000cb8c`，旧证据未覆盖。
- 真人弯腰HP02 BLOCKED，骨架/姿态/真实跌倒性能/设备/物理均NOT_RUN或未验证。

### 交给独立复审

当前工单 `HR-W03-R39-CLOSEOUT.md`；最终集中报告 `08_final_closeout.md`；唯一验收原06 v1。31点逐表01/02、现行r2归因03/04、metric复现/回归05、完整shadow/故障06、gate07、SHA/范围09均可审查。独立复审尚NOT_RUN，不自行ACCEPTED。

下一步仅人工GT与gate支撑/契约审查：viewer `09_point_review.html`，具体point/frame/cluster/track清单 `09_gt_pending.json`；人工导出后 `review_gt.js <人工导出.json> <新结果.json>` 校验绑定/标签，复跑全链需新evidence轮，不覆盖本轮。GT也不能自动绕过未通过的gate。
'''
with target.open('ab') as f:
    f.write(body.encode('utf-8'))
assert target.read_bytes().startswith(before)
print(json.dumps({'appended_bytes':len(body.encode('utf-8')),'previous_prefix_preserved':True,'path':str(target)}))
