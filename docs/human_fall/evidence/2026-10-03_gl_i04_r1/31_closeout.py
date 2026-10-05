"""Verify independent submission and update only this item's status documents."""
import hashlib
import json
from pathlib import Path
import re

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[3]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def insert_current(path, text):
    source = path.read_text(encoding="utf-8")
    head, rest = source.split("\n", 1)
    path.write_text(head + "\n\n" + text + "\n" + rest, encoding="utf-8")


def main():
    manifest = json.loads((OUT / "11_submission_manifest.json").read_text(encoding="utf-8"))
    addendum = json.loads((OUT / "25_manifest_addendum.json").read_text(encoding="utf-8"))
    for rel, expected in manifest["files"].items():
        expected = addendum["sha_addendum"].get(rel, {}).get("actual", expected)
        assert sha(ROOT / rel) == expected, rel
    meta = json.loads((OUT / "28_second_review_meta.json").read_text(encoding="utf-8"))
    session = json.loads((OUT / "29_review_session.json").read_text(encoding="utf-8"))
    models = {(m["info"].get("providerID"), m["info"].get("modelID")) for m in session["messages"] if m["info"].get("role") == "assistant"}
    assert models == {("opencode-go", "deepseek-v4.1-flash")}
    assert meta["exit"] == 0 and meta["db"] == "default" and not meta["timed_out"]
    assert meta["sessions"] == ["ses_efdc5ab31ffeBwyoFXmoG3GmHX"]
    assert [m["info"].get("finish") for m in session["messages"] if m["info"].get("role") == "assistant"][-1] == "stop"
    events = [json.loads(line) for line in (OUT / "28_second_review.jsonl").read_text(encoding="utf-8").splitlines()]
    skill = [event for event in events if event.get("type") == "tool_use" and event.get("part", {}).get("tool") == "skill"]
    assert any(event["part"]["state"]["input"].get("name") == "ponytail" and event["part"]["state"]["status"] == "completed" for event in skill)
    before = json.loads((OUT / "23_submission_baseline.json").read_text(encoding="utf-8"))
    after = json.loads((OUT / "30_after_review_baseline.json").read_text(encoding="utf-8"))
    changes = [rel for rel, value in before["files"].items() if after["files"].get(rel) != value]
    extra = [rel for rel in after["files"] if rel not in before["files"] and not rel.startswith("docs/human_fall/evidence/2026-10-03_gl_i04_r1/")]
    forbidden = [rel for rel in changes if not rel.startswith("pc_apps/human_limb/")
                 and rel != "docs/human_capture/returns/HR-07.md"
                 and rel != "docs/human_fall/evidence/2026-10-03_gl_i04_r1/24_submission_run.txt"]
    assert not forbidden, forbidden
    review = (OUT / "opencode_second_review_01/00_review.md").read_text(encoding="utf-8")
    software = ["L%02d" % i for i in range(1, 7)] + ["R%02d" % i for i in range(1, 7)] + ["S01"]
    qrows = ["Q%02d" % i for i in range(1, 11)]
    for item in software + qrows:
        assert re.search(r"\| " + item + r" \| PASS \|", review), item
    # Review's comparison command outputs exist in raw tool events, not the named .txt.
    compare_outputs = [event["part"]["state"] for event in events
                       if event.get("type") == "tool_use" and event.get("part", {}).get("tool") == "bash"
                       and "compare_real_reports.py" in event["part"].get("state", {}).get("input", {}).get("command", "")]
    with (OUT / "31_comparison_command_evidence.json").open("x", encoding="utf-8") as handle:
        json.dump(compare_outputs, handle, ensure_ascii=False, indent=2)
    audit = {"source_manifest_and_addendum_match": True, "production_drift": False,
             "head": after["head"], "model": sorted(models), "session": meta["sessions"][0],
             "exit": meta["exit"], "finish": "stop", "review_elapsed_s": meta["elapsed_s"],
             "db": "default", "native_ponytail": True,
             "after_submission_external_changes": [rel for rel in changes if not rel.startswith("docs/human_fall/evidence/2026-10-03_gl_i04_r1/")],
             "after_submission_external_additions": extra,
             "external_change_classification": "pc_apps/human_limb and HR-07 return changed concurrently outside GL-I04; reviewer/root issued no writes to them. Preserve, no rollback. stdout24 timing covered by25 addendum, not source drift.",
             "source_SHA": manifest["new_production_source"], "software": {item: "PASS" for item in software},
             "Q": {item: "PASS" for item in qrows}, "B01": "BLOCKED", "B02": "BLOCKED", "D01": "NOT_RUN", "D02": "NOT_RUN"}
    with (OUT / "31_review_audit.json").open("x", encoding="utf-8") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2)
    lines = ["# GL-I04 R1收口 / 2026-10-03", "",
             "**离线软件独立二审PASS，无源码返工；B01/B02 BLOCKED，D01/D02 NOT_RUN，整单未ACCEPTED。**",
             "Codex完成三份新生产文件后停止生产写入，指定OpenCode只读二审实际运行997.735秒/exit0/finish stop；session ses_efdc5ab31ffeBwyoFXmoG3GmHX，实际provider/model opencode-go/deepseek-v4.1-flash，default DB。派前唯一无工具probe12.703秒exit0/PROBE_OK。实际模型由29_review_session.json核实；原生ponytail在审查前已加载，路径C:/Users/30680/.claude/skills/ponytail/SKILL.md。原始CLI事件/命令/输出保留28_second_review.jsonl。", "",
             "| ID | 最终结果 | 证据 |", "|---|---|---|"]
    for item in software:
        lines.append("| %s | PASS | opencode_second_review_01/00_review.md §4/§5、独立probe及31_review_audit.json |" % item)
    lines += ["| B01 | BLOCKED | 原bag/layout来源链不足，无新增物理证据 |",
              "| B02 | BLOCKED | 录制窗口extrinsic/世界up表达及区域地面身份未闭合 |",
              "| D01 | NOT_RUN | 未设备/部署/采集/网络/GL05，未验证目标板性能 |",
              "| D02 | NOT_RUN | 未GL04真实DPR/正式页面；SVG不代替DPR |", "",
              "Q01–Q10全部PASS；完整逐行独立证据见二审§5与31_review_audit.json。本地423+2回归、额外独立反例和真实报告重算均通过，测试数量不代替ID判据。Python3.8 AST通过；实际本机Python3.12.10/NumPy1.26.4不冒称目标板Python3.8.10/NumPy1.17.4验证。", "",
              "首尾完整tracked+untracked基线03/23/30，三新生产文件提交SHA与二审后完全一致，冻结ground/calibration/capture_input、GL-I03三文件、原config/tests/draft/capture/driver/UI/历史证据保持。32收口后的变更仅当前工单状态文档。本轮树外部差异见31_review_audit.json，保留未回滚；无reset/checkout/clean/commit/push。", "",
              "## 研究决策", "",
              "采用离线诊断工具用于观察：12_real_final包含356 box×frame记录与351255源索引点，全点统计/固定XYZ分箱与显示抽样分离；二审独立重跑四产物字节一致。approved/negative-X/FIT法向研究输入分开，raw冻结结果/replay/事后holdout分开，没有真实calibration/ground_derived。", "",
              "**不采用搜索原型接入运行时。** 保留research_01/search_prototype.py作研究：逐个已见合格假设精炼、固定锚点包络证书/全跨度约束、预算不足持续未决，非传递链/晚到竞争不被吞。30场景+语义反例与同序列oracle通过；清洁/低噪正例可闭合，高噪/竞争/真实WHAT_IF未决。成本仍>2×基线，不声称速度收益或排除未见物理假设。被推翻的精炼结果逐个存储方案及replay早退错误、修订依据保留06/07及19，未降门/删除验证点。", "",
              "下一步最小判别实验：软件上量化包络造成的额外拒绝、噪声/候选顺序与close-to-best见证关系，对照同序列oracle而不改协议门；物理上先取得与2026-10-02录制窗口绑定的配置/extrinsic及from/to轴，再依据独立空间身份核查四box高低几何尾部。若改ROI需新批准选择版本，不以FIT残差筛validation。当前不自动启动后续工单/接入/设备操作。", "",
              "## 二审报告审计附记", "",
              "二审报告称interface interactive/session未提供，实际是已保存CLI run，真实session及model/finish见29导出，本收口已补齐。其compare_real_reports.txt未落盘；对应命令的原始工具输出在28 JSONL，已新增抽取31_comparison_command_evidence.json，不伪造该文件。", "",
              "二审曾修订自身certificate边界fixture（浮点1.05−1.0并不精确等于0.05），这是审查预期的修正，不是被审源码返工。其自身probe重复写出的日志，早期命令/输出仍完整保存在28 JSONL，原作者旧证据没有覆盖。", "",
              "流程观察：审查者原生加载ponytail后，为对照字节另以只读shell读取了Codex技能文件哈希；这超出派工要求的仅native查找路径，予以保留并要求后续避免。原生技能先行使用已验证，无生产写入/权限变更，也不影响可独立复现的软件结论，不伪报其全程只访问native路径。", "",
              "Manifest11捕获了正在写的stdout24的空SHA；只新增25日志SHA附记保留原证据。独立首尾111项清单按该附记全部匹配，无源码/input/report漂移。源码自验不是独审；本轮独审的model/session/exit实际齐全。"]
    with (OUT / "32_CLOSEOUT.md").open("x", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")
    docs = ROOT / "docs/human_fall"
    acceptance = docs / "GLI04_ACCEPTANCE.md"
    text = acceptance.read_text(encoding="utf-8")
    text = text.replace("状态：DRAFT_READY / 未执行。", "状态：软件独立二审PASS（L01–L06/R01–R06/S01/Q01–Q10）；B01/B02 BLOCKED、D01/D02 NOT_RUN；整单未ACCEPTED。", 1)
    text = text.replace("当前所有新软件/研究检查NOT_RUN，不预填PASS。", "现行结果见[收口](evidence/2026-10-03_gl_i04_r1/32_CLOSEOUT.md)/[二审](evidence/2026-10-03_gl_i04_r1/opencode_second_review_01/00_review.md)，仅更新结果，不改变v1判据。", 1)
    for item in software + qrows:
        text = re.sub(r"(^\| " + item + r" \|[^\n]*\|) NOT_RUN \|", r"\1 PASS |", text, flags=re.M)
    acceptance.write_text(text, encoding="utf-8")
    pointer = "2026-10-03当前入口：[GL-I04 v1](GLI04_ACCEPTANCE.md)/[收口](evidence/2026-10-03_gl_i04_r1/32_CLOSEOUT.md)/[指定OpenCode二审](evidence/2026-10-03_gl_i04_r1/opencode_second_review_01/00_review.md)。Codex三新文件停写后独立二审：L01–L06/R01–R06/S01/Q01–Q10 PASS，无源码返工；B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED。离线诊断可用，搜索原型保留研究、不接运行时；无活动writer，冻结算法/批准输入保持，GL04DPR/正式及GL05设备边界不变。下方准备/GL-I03入口均为历史。"
    for name in ("WORKFLOW.md", "README.md", "DISPATCH.md", "GLI04_TASK.md"):
        insert_current(docs / name, pointer)
    with (docs / "REVIEW_LOG.md").open("a", encoding="utf-8") as handle:
        handle.write("\n## 2026-10-03 GL-I04 R1指定OpenCode独立二审收口\n\n" + pointer + "\n\n实际session ses_efdc5ab31ffeBwyoFXmoG3GmHX/Go Flash/defaultDB，997.735秒exit0/finish stop，原生ponytail先行加载。全部缺陷集中检查，无源码FAIL/不返工；完整ID、证据、研究决策、报告审计附记和范围差异见32_CLOSEOUT.md及31_review_audit.json。批准capture/up/height/四box与冻结core/config保持；未部署、采集、设备/网络或真实物理验证。\n")
    with (docs / "returns/GL-I04.md").open("a", encoding="utf-8") as handle:
        handle.write("\n## Codex二审接回附记 / 2026-10-03\n\n状态记录SUBMITTED/STOPPED；实际OpenCode独立二审已完成（不以自验冒充）。L01–L06/R01–R06/S01/Q01–Q10独审PASS，B01/B02 BLOCKED、D01/D02 NOT_RUN。session ses_efdc5ab31ffeBwyoFXmoG3GmHX/Go Flash/defaultDB/exit0/finish stop，提交源码SHA全部保持。完整证据与对审查报告的事实补正见evidence/2026-10-03_gl_i04_r1/32_CLOSEOUT.md；无ACCEPTED声明、无源码返工/原型接入。\n")
    print(json.dumps({"software": "PASS", "B01": "BLOCKED", "B02": "BLOCKED", "D01": "NOT_RUN", "D02": "NOT_RUN", "external_changes": changes, "external_additions": extra}))


if __name__ == "__main__":
    main()
