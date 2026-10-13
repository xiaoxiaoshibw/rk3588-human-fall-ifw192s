"""Append the item return and record actual command exits from this turn."""
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).resolve().parent
ROOT = HERE.parents[3]
ACCEPTANCE = ROOT / "docs/human_capture/HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md"


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


commands = [
    ("python -B -W error pc_apps/human_ml/train_person_rf_v2.py --outdir docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/train_01", 1, "train_01.log"),
    ("python -B -W error pc_apps/human_ml/train_person_rf_v2.py --outdir docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/train_02", 0, "train_02.log"),
    ("node --max-old-space-size=2048 pc_apps/human_core/evaluate_fusion_gt.js docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/train_02 docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/runs_01", 1, "runs_01.log"),
    ("node --max-old-space-size=2048 pc_apps/human_core/evaluate_fusion_gt.js docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/train_02 docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/runs_02", 1, "runs_02.log"),
    ("node --max-old-space-size=2048 pc_apps/human_core/evaluate_fusion_gt.js docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/train_02 docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/runs_03", 0, "runs_03.log"),
    ("node pc_apps/human_core/test_fusion_gt.js", 0, "test_fusion_gt.log"),
    ("python -B -W error pc_apps/human_ml/test_frozen_gt.py", 0, "test_frozen_gt.log"),
    ("node --max-old-space-size=2048 pc_apps/human_core/test_fusion_specific.js", 0, "test_fusion_specific.log"),
    ("python -B -W error docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/verify_artifacts.py", 0, "verify_artifacts.log"),
    ("python -B -W error docs/human_capture/evidence/2026-10-10_human_unify_fusion_r2/run_review.py", 0, "review_driver.log"),
]
with (HERE / "COMMAND_RESULTS.json").open("x", encoding="utf-8") as f:
    json.dump({"source": "actual Codex exec_command/write_stdin completion exit codes; failures preserved",
               "commands": [{"command": c, "exit": e, "log": l, "log_sha256": sha(HERE / l)} for c, e, l in commands]}, f, indent=1)
source = json.loads((HERE / "SUBMITTED_SOURCE_SHA.json").read_text(encoding="utf-8"))
rows = [
    ("F3-GT", "BLOCKED", "train_02/GT_AUDIT.json：8会话读取时绑定通过；S1外移/S9无可用版本"),
    ("F3-SPLIT", "PASS", "train_02/SPLITS.json，0.55固定，无test调参；无独立家具/演员限制公开"),
    ("F3-TRAIN", "PASS", "train_02与RF_MODEL_COMPARISON，1726样本，独立v2；真实回退保留"),
    ("F3-KEEP", "PASS", "before/verify_artifacts：v1/frame_feature/rf原SHA保持"),
    ("F4-RUN", "PASS", "runs_03/SUMMARY.json：72完整运行，20840帧tick，原输入/实现SHA守卫"),
    ("F4-PARITY", "PASS", "FRAME_PARITY_REPORT：18/18；同点集概率无不一致"),
    ("F4-GT", "BLOCKED", "7会话56组合可信已标指标；S1/S9其余16组合BLOCKED"),
    ("F4-S9", "BLOCKED", "V2消失，原绑定错误；test_fusion_gt合成断点PASS"),
    ("F4-PERF", "FAIL", "PERFORMANCE_REPORT：S3-far FUSION两版P95超50ms；70/72"),
    ("S01", "PASS", "GT JS / Python2 / FUSION16均exit0，独审独立复跑GT检查"),
    ("S02", "BLOCKED", "before/after_final/SCOPE_AUDIT范围核对，外部human_replay_lib.py/GT变动保留"),
    ("Q01", "PASS", "probe12.75s，Go Flash plan独审315.64s，均exit0"),
    ("D01", "NOT_RUN", "无设备/物理/部署/采集/commit/push/生产切换"),
]
text = """\n## 2026-10-10 R2 / Codex 离线F3/F4回传

- 工单：HUMAN-UNIFY-FUSION-R1 / R2；状态SUBMITTED/停写，未ACCEPTED。
- 授权：本轮用户交接及三份替代工单材料确认；旧R1结果不回填。
- 唯一验收表：docs/human_capture/HUMAN_UNIFY_FUSION_R2_ACCEPTANCE.md v1，SHA `%s`。
- 起始branch/HEAD：master/026e06303f60ed1bbe4ddc4d037836db68da6d27；全tracked/untracked基线before.json与最终范围after_final/SCOPE_AUDIT。
- ponytail实际使用路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md；另读取scikit-learn技能，使用已有NumPy/sklearn，不安装依赖。
- writer：Codex唯一writer；指定只读reviewer opencode-go/deepseek-v4.1-flash，agent plan，session ses_ed9b3145dffeAnHifopu28e5gy，probe/独审原日志与exit见evidence。
- 五判定：FUNCTIONAL PASS / GT_EVALUATION BLOCKED / PERFORMANCE FAIL / MODEL_PROMOTION BLOCKED / PRODUCTION_RELEASE BLOCKED。

集中诊断：旧家具导出只支持sessions/frames/rois，与新冻结objects/frames_objects不兼容；新入口用精确compact点集及来源，去重248件重复家具。按整会话划分，未标帧UNKNOWN，跳过e2e；S9原points=a×64且缺meta，随后V2消失；S1在样本导出后外移，均阻断相关指标。GT、生产算法、录制和旧证据未由本轮改写。

实际变更：新增frozen_gt/train_person_rf_v2及最小Python检查、evaluate_fusion_gt/test_fusion_gt；新增R2验收/证据/回传，README仅维护当前入口。engine/runner/生产特征/旧模型不改。源SHA如下。

| 文件 | 提交源码SHA |
|---|---|
""" % sha(ACCEPTANCE)
text += "\n".join("| %s | `%s` |" % pair for pair in source.items())
text += "\n\n| ID | 结果 | 本轮证据/入口（均offline） |\n|---|---|---|\n"
text += "\n".join("| %s | %s | %s |" % row for row in rows)
text += """

原命令/退出码：evidence/2026-10-10_human_unify_fusion_r2/COMMAND_RESULTS.json逐条记录。训练01、runs01/02失败日志保留；train02、runs03、GT JS/Python/FUSION16、核验exit0。模型/产物SHA见ARTIFACT_MANIFEST与SUBMITTED_SOURCE_SHA，最终source核对没有改变冻结v1契约。

未闭合：S1/S9可信GT恢复及会话绑定；S3-far两项真实性能FAIL；候选v2近/远行走与遮挡track召回回退；独立家具及跨人跨景证据不足。S8静止收益不抵消运动回退，保留v1。不自行新增优化单/采集/部署/发布。外部human_replay_lib.py及board同步新文件保留不回滚，S02全树冻结BLOCKED。

独审附记：独审无评估工具逻辑FAIL，五判定建议已采用。结束范围快照和退出码在收口补齐，原独审全文不改；CODEX_REVIEW_RESPONSE说明记录差异。完整逐项结果/限制/日志入口见evidence/2026-10-10_human_unify_fusion_r2/FINAL_REPORT.md。
"""
ret = ROOT / "docs/human_capture/returns/HUMAN-UNIFY-FUSION-R1.md"
with ret.open("a", encoding="utf-8") as f:
    f.write(text)
print("command results recorded and return appended")
