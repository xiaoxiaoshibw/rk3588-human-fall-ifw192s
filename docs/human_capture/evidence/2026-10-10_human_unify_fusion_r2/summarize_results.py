"""Generate immutable R2 reports from the completed train/run artifacts."""
import hashlib
import json
import pathlib

HERE = pathlib.Path(__file__).parent
TRAIN = HERE / "train_02"
RUN = HERE / "runs_03"


def read(p):
    with p.open(encoding="utf-8") as f:
        return json.load(f)


def put(name, lines):
    with (HERE / name).open("x", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")


def pct(v):
    return "—" if v is None else "%.1f%%" % (100 * v)


def main():
    model = read(TRAIN / "RF_MODEL_COMPARISON.json")
    summary = read(RUN / "SUMMARY.json")
    lines = ["# RF_MODEL_COMPARISON — R2 候选，不推广", "", "2026-10-10，阈值固定0.55，未调test。",
             "", "- v1 SHA: `" + model["v1_sha256"] + "`", "- v2 SHA: `" + model["v2_sha256"] + "`",
             "- SPLITS SHA: `" + model["split_sha256"] + "`", "- sklearn→JSON概率最大差: " + str(model["export_probability_max_diff"]),
             "- JS同51维输入概率对拍见runs_03/MODEL_JS_PARITY.json。", "",
             "| 会话 | split | GT点集样本 | v1召回 | v2召回 | v1FP | v2FP |", "|---|---|---:|---:|---:|---:|---:|"]
    for r in model["runs"]:
        lines.append("| %s | %s | %d | %s | %s | %d | %d |" %
                     (r["sid"], r["split"], r["n"], pct(r["v1"]["recall"]), pct(r["v2"]["recall"]), r["v1"]["fp"], r["v2"]["fp"]))
    lines += ["", "GT精确compact点集裁剪；S1 1464家具对象去掉同帧同点集重复248，得到1216负例，另有510 PERSON样本。BACKGROUND未混入家具。",
              "S1训练集FP改善只是拟合；独立家具负例test缺失。S6压力样本v2漏9/71。缺跨演员/新场景信息，S9无可用绑定GT。",
              "读取S1样本后外部移走其GT；train_02保留已导出点集特征/原GT及会话SHA，但原GT目前无法从当前store复验，来源资格BLOCKED。",
              "", "**MODEL_PROMOTION=BLOCKED。保留v1；候选仅存evidence，未接管生产。**"]
    put("RF_MODEL_COMPARISON.md", lines)
    lines = ["# 四路线GT评估 — R2", "", "9会话×4路线×v1/v2，共72次完整会话运行，每个版本10420帧tick。",
             "匹配：XY中心距≤0.75m、最大匹配数后最小距离、一对一；另在每次run JSON保留0.5/1.0m敏感性。",
             "accepted候选与human_confirmed且lost=0的当前track分开。precision仅在协议声明零/单人的reviewed已标帧假定真人标注完整；未标帧UNKNOWN。",
             "S1 GT外部变化、S9无可用非e2e绑定GT，均不输出可信指标。gt_snapshot保存其余7份实际消费的冻结字节。",
             "FP/hour单位为错误track观测/已标帧暴露小时，并非完整会话误报事件率。", "",
             "| 会话 | 模型 | 路线 | 标帧 | candidate R/P | track R/P | track FP | 已标相邻ID switch |",
             "|---|---|---|---:|---|---|---:|---:|"]
    episodes = []
    for r in summary["runs"]:
        g = r["gt"]
        if g["status"] == "BLOCKED":
            lines.append("| %s | %s | %s | BLOCKED | — | — | — | — |" % (r["sid"], r["version"], r["mode"]))
            continue
        lines.append("| %s | %s | %s | %d | %s/%s | %s/%s | %d | %d |" %
                     (r["sid"], r["version"], r["mode"], g["annotated_frames"],
                      pct(g["candidate"]["recall"]), pct(g["candidate"]["precision"]),
                      pct(g["track"]["recall"]), pct(g["track"]["precision"]), g["track"]["fp"], g["adjacent_annotated_id_switches"]))
        full = read(RUN / r["sid"] / (r["version"] + "__" + r["mode"] + ".json"))
        by_frame = {f["frame_index"]: f for f in full["frames"]}
        observed = {}
        for f in g["frames"]:
            matches = {pid: tid for tid, pid in f["matched_tracks"].items()}
            for track in by_frame[f["frame_index"]]["tracks"]:
                e = observed.setdefault(track["id"], {"id": track["id"], "first_annotated_frame": f["frame_index"],
                    "last_annotated_frame": f["frame_index"], "gt_ids": [], "matched_observations": 0, "unmatched_observations": 0})
                e["last_annotated_frame"] = f["frame_index"]
                if track["id"] in matches:
                    tid = matches[track["id"]]
                    if tid not in e["gt_ids"]:
                        e["gt_ids"].append(tid)
                    e["matched_observations"] += 1
                else:
                    e["unmatched_observations"] += 1
        false = sum(not e["gt_ids"] for e in observed.values())
        episodes.append({"sid": r["sid"], "version": r["version"], "mode": r["mode"], "observed_track_episodes": list(observed.values()),
                         "unmatched_only_episodes_on_annotated_frames": false,
                         "unmatched_only_episode_rate_per_annotated_hour": false * 3600 / g["exposure_seconds"] if g["exposure_seconds"] else None})
    with (HERE / "TRACK_EPISODE_EVALUATION.json").open("x", encoding="utf-8") as f:
        json.dump({"scope": "annotated observations only; unknown intervals excluded; no complete-lifetime claim", "runs": episodes}, f, indent=1)
    lines += ["", "## 专项边界", "", "S3近/远、S4走停走、S5转身、S6遮挡、S7远场、S8静止的数值逐行如上。S4只有11标帧、S5只有6标帧；不能外推整段连续召回。",
              "S6 visibility/episodes没有给出真实遮挡区段，报告已标点召回，不伪造再捕获延迟。S8仅53/523标帧，静止场景采样召回不是整段保留率。",
              "S9原V2 18标帧/35对象且f1缺P2；随后V2消失、当前仅e2e。GT_BREAKS对当前可用快照运行；真实双人断点/ID switch BLOCKED。",
              "test_fusion_gt.js独立构造f1缺P2断点及采样gap，不以合成守卫替代真实S9验收。",
              "TRACK_EPISODE_EVALUATION.json记录已标观测上的track片段及GT身份；未知间隔不计ID switch，不用ever身份数冒充人数。"]
    put("FUSION_GT_EVALUATION.md", lines)
    lines = ["# FUSION↔BASE_B 全帧同源对拍", "", "对拍要求输入/时戳/配平/模型/参考SHA相同；两算法候选和跟踪本来不同，不要求输出相等。",
             "同点集RF概率要求差≤1e-6；逐帧候选数、accepted数、track数与共有点集概率差见各会话__PARITY.json。", "",
             "| sid | 模型 | 同源帧 | 共有精确点集 | 概率不一致 | 结果 |", "|---|---|---:|---:|---:|---|"]
    for r in summary["parity"]:
        lines.append("| %s | %s | %d | %d | %d | %s |" % (r["sid"], r["version"], r["same_source_frames"],
                                                          r["common_exact_point_sets"], r["probability_mismatches"], r["status"]))
    put("FRAME_PARITY_REPORT.md", lines)
    lines = ["# PERFORMANCE — R2 当前机器实测", "", "CPU: " + summary["cpu"] + "; Node: " + summary["node"],
             "每次顺序全帧运行，前5帧预热剔除；门P95<50ms且peak heapUsed<1500MB。总耗时只计engine.tick，加载/背景建模/诊断哈希不计入。",
             "RSS/external另报，不等于heap门；BASE_A不加载RF，两模型标记下重复测量。", "",
             "| sid | 模型 | mode | P50 | P95 | P99 ms | heap MB | RSS MB | 门 |", "|---|---|---|---:|---:|---:|---:|---:|---|"]
    for r in summary["runs"]:
        p = r["performance"]
        lines.append("| %s | %s | %s | %.2f | %.2f | %.2f | %.1f | %.1f | %s |" %
                     (r["sid"], r["version"], r["mode"], p["p50"], p["p95"], p["p99"], p["peak_heap_mb"], p["peak_rss_mb"], "PASS" if p["pass"] else "FAIL"))
    lines += ["", "通过 %d/%d；本机单次离线测量，不代表设备物理/部署。" %
              (sum(r["performance"]["pass"] for r in summary["runs"]), len(summary["runs"]))]
    put("PERFORMANCE_REPORT.md", lines)
    print("reports written", len(summary["runs"]), "runs")


if __name__ == "__main__":
    main()
