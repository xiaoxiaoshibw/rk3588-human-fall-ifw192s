"""Bind evidence, verify pre-existing files, append a diagnostic return without changing prior records."""
import hashlib
import json
from pathlib import Path
import sys

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]
sys.path.insert(0, str(ROOT / "pc_apps/human_replay"))
import leveling as L


def read(name):
    return json.loads((OUT / name).read_text(encoding="utf-8"))


def save(name, value):
    with (OUT / name).open("x", encoding="utf-8") as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)


baseline = read("00_baseline.json")
drift = []
current_round_prefix = str(OUT.relative_to(ROOT)).replace("\\", "/") + "/"
for name, item in baseline["files"].items():
    if name.startswith(current_round_prefix):
        continue  # This round was created before snapshot; its active log is not a protected old file.
    p = ROOT / name
    if "sha256" in item:
        if not p.is_file() or L.sha(p) != item["sha256"]:
            drift.append(name)
    elif item.get("missing") and p.exists():
        drift.append(name)
    elif "symlink" in item and (not p.is_symlink() or str(p.readlink()) != item["symlink"]):
        drift.append(name)
assert not drift, drift
levels, regs, retention = read("leveling_results.json"), read("registration_results.json"), read("retention_results.json")
for item in levels:
    assert L.source(ROOT / "captures/remote", item["sid"])[2] == item["source"]

table = ROOT / "docs/human_capture/evidence/2026-10-07_hrw03_r37_productionization/06_test_matrix.md"
v2table = ROOT / "docs/human_capture/HRRETV2_ACCEPTANCE.md"
checks = read("registration_tests.log")
assert all(item["result"] == "PASS" for item in checks)
acceptance = {item["id"]: {"status": "PASS", "scope": "fixture/unit regression", "evidence": "registration_tests.log"} for item in checks}
acceptance["T37-20"] = {"status": "NOT_RUN", "reason": "canonical audited-pair direction fixture not rerun"}
for prefix, n in (("T38", 12), ("T39", 8)):
    for i in range(1, n+1):
        acceptance[f"{prefix}-{i:02d}"] = {"status": "NOT_RUN", "reason": "new-session diagnostics do not replace original shadow/production acceptance"}
acceptance.update({
    "V2-01": {"status": "PASS", "scope": "unit", "evidence": "pipe_tests.log"},
    "V2-02-new-data": {"status": "BLOCKED", "reason": "region proxies are not person GT: divider 91.9166%, raised arm 100%; remaining pairs WARN"},
    "V2-03-new-data": {"status": "BLOCKED", "reason": "coarse candidates present in all PASS-pair frames; divider cleanup removes one ROI point in five frames, identity unknown; arm confirmation 0 due old evidence rule"},
    "V2-04": {"status": "NOT_RUN", "reason": "original WD01/WD02 not rerun"},
    "V2-05": {"status": "NOT_RUN", "reason": "original pointwise harness not rerun"},
    "V2-06-new-data": {"status": "BLOCKED", "reason": "residual furniture windows disclosed; exact nonperson cost requires GT"},
    "V2-07": {"status": "PASS", "scope": "new empty scene, identity-reference offline library; not production integration", "evidence": "empty_v2_library.json"},
    "V2-10": {"status": "NOT_RUN", "reason": "no implementation changes"},
    "V2-11": {"status": "PASS", "scope": "V2-11a/b regression fixtures only; real new-data loader remains UNAVAILABLE"},
    "V2-12": {"status": "NOT_RUN", "reason": "no new-data artifact or browser integration"},
    "V2-13": {"status": "PASS", "scope": "pipe 38, registration 23 ID records, replay 45, panel O1/O5, detect 11; all exit 0"},
    "V2-14": {"status": "NOT_RUN", "reason": "independent review not performed"},
    "device_physics_deploy_capture": {"status": "NOT_RUN", "reason": "user-supplied recordings; no board operation or physics verification"}})
save("acceptance_status.json", {"tables": {str(table.relative_to(ROOT)): L.sha(table), str(v2table.relative_to(ROOT)): L.sha(v2table)},
    "scope": "supplemental diagnostic only; historical milestone verdicts unchanged", "checks": acceptance})

lines = ["# 2026-10-08 五段新会话离线诊断（r1）", "",
    "状态：**SUBMITTED（诊断完成），不宣告 W03/HR-RET-V2 ACCEPTED**。用户交付五段会话并确认：雷达、门、家具、支架均未移动；人体四段全程静立。", "",
    "## 结果", "", "五段自动配平均推荐 TLS；三帧独立留出全部通过现行配平门。新空场 cap_20261008_114819（29.44s / 285 帧）作参考。", "",
    "| 会话 | sid 后六位 | inlier | XY 覆盖 | fit / holdout p50（cm） | gate |",
    "|---|---|---:|---:|---:|---|"]
for item in regs:
    lines.append(f"| {item['name']} | {item['sid'][-6:]} | {item['support']['inlier_ratio']*100:.2f}% | {item['support']['coverage_xy']*100:.2f}% | {item['residual']['fit']['p50']*100:.2f} / {item['residual']['holdout']['p50']*100:.2f} | {item['gate']} |")
lines += ["", "两段 WARN 的唯一不通过项均为 inlier_ratio < 0.50（SPARSE_CORRESPONDENCE）。该比例是固定诊断调度中**裁剪后对应数 / 静态源点数**，不能解释成其余点全部配错；调度、匹配与 gate 门槛均未改动。", "",
    "**质量 PASS 与 loader VALID 是两件事。** 本轮只调用固定算法与质量测量，不调用 publish/writeJob；未创建、重签或安装 registration artifact。新 pair 的生产 loader 仍应为 UNAVAILABLE，不具备启用条件。", "",
    "## 人体区域与链路", "", "所有对照在同一已配准坐标系中运行，P 是用于隔离融合差异的在线-only 对照臂，不是浏览器未配准生产路径的实测。", "",
    "圆柱半径固定 0.45m，z∈[0.10,2.30]，圆心由新数据中三帧残留点云定位；它是空间代理，**不是逐点人体 GT**。保留率是各臂点数 p50 / 原区域点数 p50。WARN pair 只跑 P/REF 诊断，V2/UNION 留 BLOCKED。", "",
    "| sid | P 区域保留 | REF 区域保留 | V2 区域保留 | V2 粗几何候选帧 | V2 有确认轨道帧 |",
    "|---|---:|---:|---:|---:|---:|"]
for item in retention:
    arms = item["arms"]
    v2 = arms.get("V2")
    lines.append(f"| {item['sid'][-6:]} | {arms['P']['retention_pct']:.2f}% | {arms['REF']['retention_pct']:.2f}% | " +
        (f"{v2['retention_pct']:.2f}% | {v2['candidate_frames']}/{len(v2['rows'])} | {v2['confirmed_frames']}/{len(v2['rows'])} |" if v2 else "BLOCKED | BLOCKED | BLOCKED |"))
lines += ["", "- 隔板旁：V2 区域保留 91.92%，低于 95% 区域目标；相对 P/UNION 的 0.43% 已恢复大部分区域点，281 帧都有粗几何候选，230 帧有确认轨道。参考臂自身仅 91.96%，损失主要发生在参考匹配，非融合新增删除。中间帧参考删除 185 点，全部集中在 Y=0.23–0.36m 的圆柱家具侧边缘（与主立人体结构分开）；可能是混入区域的家具点，需人工 GT，不能直接称为人体损失 8%。cleanup 在 5 帧各删 1 个区域点，身份同样未标注。", "",
    "- 举左手：V2 区域保留 100%，195 帧都有粗几何候选，但确认轨道 0。联合判定为 NON_HUMAN 183 帧 / HUMAN_CANDIDATE 9 帧 / CONFIRMED_HUMAN 3 帧，未形成 3/5 确认。中间帧 spread_cv=0.104，被旧证据规则 SOLID_UNIFORM 判为均匀体；这是分类/确认问题，不是前景点被吞。", "",
    "- 中央普通静立与右桌前：REF 区域保留 100% / 99.97%，而在线-only 臂仅 0.30% / 0.16%；V2 因 gate WARN 不跑。纯 REF 下中央普通静立也未确认，右桌前 268/271 帧确认，说明姿态/形状证据门仍有独立局限。", "",
    "- 新空场 identity-reference V2 函数层检查：0 candidate 帧 / 0 confirmed 帧。此项不证明跨会话生产链已经可用。", "",
    "## 家具窗诊断", "", "固定两个空间窗（不是人工标注桌面）：X=[0.8,3.5], Y=[0.45,1.8], Z=[0.65,1.30]；X=[1.8,3.5], Y=[−1.8,−1.05], Z=[0.65,1.30]。分别抽第 0、中间、最后帧。三维欧氏最近距离对比 occ≥0.5 的参考体素形心，搜索上限 0.60m；本轮所有窗内点均找到邻居。", "",
    "| sid | 正 Y 家具窗距离 p90（cm） | 正 Y 参考删除率 | 负 Y 家具窗距离 p90（cm） | 负 Y 参考删除率 |",
    "|---|---:|---:|---:|---:|"]
audit = read("region_audit.json")
for item in audit["sessions"]:
    vals=[]
    for key in audit["windows"]:
        distances=[r["furniture_windows"][key]["nearest_distance_m"]["p90"]*100 for r in item["rows"]]
        deleted=[r["furniture_windows"][key]["deleted_pct"] for r in item["rows"]]
        vals += [f"{min(distances):.1f}–{max(distances):.1f}",f"{min(deleted):.1f}–{max(deleted):.1f}%"]
    lines.append(f"| {item['sid'][-6:]} | " + " | ".join(vals) + " |")
lines += ["", "PASS 两段的抽样家具窗 p90 约 7–10cm，参考删除约 95–100%；WARN 两段正 Y 窗尾部仍约 12–18cm。global point-to-plane p50 小于 1.2cm 不等于桌区全点三维距离 <12cm；本轮也没有物理测量或全桌面 GT，不能宣布桌子整体合格。", "",
    "## 边界、验收与证据", "", "- 唯一验收表仍为 R3.7 06_test_matrix.md v1 / HRRETV2_ACCEPTANCE.md v1；SHA 与本轮逐 ID PASS/FAIL/NOT_RUN/BLOCKED 状态见 acceptance_status.json。新数据人体验收受 GT 缺口阻塞；不覆盖历史验收表或历史证据，不改变 W03 REWORK_REQUIRED。", "- 命令：python -B -W error level_sessions.py；node --max-old-space-size=8192 diagnose_registration.js / retention_diagnostic.js / audit_regions.js；python -X utf8 -B -W error plot_preview.py / plot_region_audit.py；均 exit 0。所有输出为本目录独占新文件。", "- 收尾完整性首轮 exit 1：把本轮已创建的 leveling.run.log（启动时空、运行后增长）误纳入保护旧文件。首轮日志 finalize.run.log 保留；修正为保护本轮目录之外的起始文件，最终 finalize_r2.run.log 为准；数据/算法未重跑或改变。", "- 五套回归：human_pipe_lib 38/0；registration 23 个 PASS ID（T37-20 未跑）；human_replay_lib 45；panel O1/O5；human_detect_lib 11/0，均 exit 0。T38/T39 原 gold/shadow/生产集成本轮 NOT_RUN，不能被这些数字替代。", "- 名义配平参数 26°/0°/1.14m 仅复用已有工作台输入，非本次安装角或坐标原点高度的物理核验；TLS 自动拟合结果亦不作外参核验。", "- 原始 captures 与生产文件保持只读；branch/HEAD/全 git tracked+untracked SHA 基线见 00_baseline.json，忽略的本轮原始会话由 meta/bin SHA 额外绑定。前缀完整性见 integrity.json。未 commit/push/deploy/capture/调阈值/改算法/重签/开启旗标。", "- ponytail 实读：C:/Users/30680/.codex/skills/ponytail/SKILL.md；matplotlib 实读：C:/Users/30680/.codex/skills/scientific-toolkit-skill/references/scientific-skills/matplotlib/SKILL.md。", "- 本轮新工具共 7 个小脚本，复用原 L.run_job、fixedICP、measure、PL 函数；配平派生数据仅位于 evidence/leveling，不注册到 captures/leveled。", "",
    "![点云对照](pointcloud_preview.png)", "", "![圆柱边缘点审计](region_audit.png)", "",
    "后续可评审两个独立事项：为质量 PASS 的两对生成并安装新的绑定 artifact；人工标注隔板旁区域边缘及审查静立/举臂形状判定。两段 WARN 仍需对应集/质量契约层的设计评审，不能靠本轮诊断自行降低门槛。"]
with (OUT / "README.md").open("x", encoding="utf-8") as f:
    f.write("\n".join(lines) + "\n")

return_path = ROOT / "docs/human_capture/returns/HR-W03.md"
old_bytes = return_path.read_bytes()
old_sha = hashlib.sha256(old_bytes).hexdigest()
assert old_sha == baseline["files"][str(return_path.relative_to(ROOT)).replace('\\','/')]["sha256"]
append = "\n\n## 2026-10-08 新五段静立/空场诊断 r1（Codex，仅诊断）\n\n" + "\n".join([
    "- 用户授权：承接本聊天离线诊断约定；用户交付五段本地会话并确认布置无移动、人体全程静立。状态 SUBMITTED（诊断完成），W03 REWORK_REQUIRED 与 HR-RET-V2 历史状态不变，不宣告 ACCEPTED。",
    "- 证据/结果：evidence/2026-10-08_new_static_sessions_r1/README.md；五段配平 recommended=tls；114340/114422 配准 gate PASS（52.85/50.88%），114205/114254 WARN（49.38/49.51%，仅 SPARSE_CORRESPONDENCE）。没有生成 production artifact，新 pair loader 仍 UNAVAILABLE。",
    "- 固定区域 V2 函数层：114340 保留 91.92%、候选281/281、确认轨道230/281；114422 保留100%、候选195/195、确认0（SOLID_UNIFORM 183帧）。区域非逐点GT；隔板旁185删除点集中家具侧边缘；5帧cleanup各1区域点，身份未核。新人体验收 BLOCKED，详见 acceptance_status.json。",
    "- 家具窗三帧抽样：两段 PASS 的 p90 三维参考形心距离7–10cm、参考删除95–100%；WARN正Y窗p90约12–18cm。不是全桌面GT/物理验收。",
    "- 现行唯一表与 SHA：R3.7 06_test_matrix.md v1 SHA " + L.sha(table) + "；HRRETV2_ACCEPTANCE.md v1 SHA " + L.sha(v2table) + "。T37回归已跑ID均PASS，T37-20及T38/T39 NOT_RUN；原T38-05/06 FAIL不被新诊断替换；V2新数据02/03/06 BLOCKED GT；V2-07仅identity-reference离线0/0；V2-13五套回归PASS；V2-14 NOT_RUN。",
    "- baseline master / " + baseline["head"] + "；00_baseline.json覆盖原git tracked+untracked SHA，原始五会话SHA单独绑定；原existing文件无漂移，本文只追加。原source/captures/历史evidence只读，新增本轮evidence脚本/JSON/图/派生配平。",
    "- ponytail实际读取路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md；Python3.12.10/NumPy1.26.4、Node24.14.0，Python均-B -W error，绘图/收尾加-X utf8。未调参数、未改算法、未重签、未开生产旗标、未设备操作、未commit/push。",
    "- 独立复审入口：README.md、acceptance_status.json、registration_results.json、retention_results.json、region_audit.json、00_baseline.json、integrity.json及各*.run.log。下一步：审查GT/形状规则或授权PASS pair artifact生产化；不自动进入R3.9/W04。"
]) + "\n"
with return_path.open("ab") as stream:
    stream.write(append.encode("utf-8"))
assert return_path.read_bytes()[:len(old_bytes)] == old_bytes
scripts = {p.name:L.sha(p) for p in OUT.iterdir() if p.suffix in (".py", ".js")}
save("integrity.json", {"preexisting_file_drift": drift, "baseline_file_count": len(baseline["files"]),
    "excluded_current_round_prefix": current_round_prefix,
    "source_sha_verified": {r["sid"]:r["source"] for r in levels},
    "return": {"path":str(return_path), "original_sha256":old_sha,"original_bytes":len(old_bytes),"prefix_unchanged":True,"final_sha256":L.sha(return_path)},
    "scripts": scripts, "report_sha256":L.sha(OUT / "README.md"),"runtime_flags_modified":False,"registration_artifact_created":False})
print("REPORT READY; verified",len(baseline["files"]),"preexisting file records and five source SHA bindings")
