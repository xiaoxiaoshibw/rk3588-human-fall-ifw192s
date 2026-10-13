# -*- coding: utf-8 -*-
"""把 prob 分歧根因追加进 W1B_PROB_CONSISTENCY.json（幂等）。"""
import json
import os

EVID = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                    "..", "..", "..", "docs", "sidequests", "evidence",
                    "2026-10-12_HFUS_RD_02_r1")
op = os.path.join(EVID, "W1B_PROB_CONSISTENCY.json")
with open(op, encoding="utf-8") as f:
    d = json.load(f)
d["root_cause_found"] = {
    "evidence": "ledger frame6 (S1) model_calls[0].features[0:2] == [5018, 10]",
    "interpretation": (
        "生产引擎传给 RF 的特征首维=候选点数 5018、第二维=10（采样点数）。"
        "即生产在抽特征前对候选点数做了上限采样（约 10 点），而 RD-01 "
        "rf_extract_node.js 用全量 5018 点抽 50 维特征 → 两者特征域不同 "
        "→ 同一候选 ledger=0.0029 vs 复刻=0.89。"),
    "impact": (
        "D3 数据集全部 f51/x18/rf_prob 由该复刻生成 → M0-M5 的输入特征与"
        "生产打分不一致；RD-01 中一切与生产 metric 的对比失去共同基准"
        "（含 classifier_ablation、layer_attribution §3）。"),
    "not_fixed_here": (
        "本轮不复刻生产采样协议（属 HF/GL 生产侧改动，无授权）；只如实登记，"
        "并在 W4 报告内区分 'ledger 真分' 与 '复刻特征' 两条线。"),
    "open_for": "生产侧 RF 采样协议确认（points cap / seed 规则）",
}
with open(op, "w", encoding="utf-8") as f:
    json.dump(d, f, ensure_ascii=False, indent=2)
print("updated", op)
for sid, v in d["per_sid"].items():
    print(" ", sid[-6:], "agree=%.3f" % v["accept_agreement_at_0.55"])
