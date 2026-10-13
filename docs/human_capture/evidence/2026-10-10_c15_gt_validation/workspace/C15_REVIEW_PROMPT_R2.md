# C1.5 独立复核指令 (OpenCode opencode-go/deepseek-v4.1-flash)

**你是独立审计员, 不是实施者.** 只读核验, 产出判定与证据锚; 不修改任何文件. 时间盒一轮.

## 任务背景
C1 动态人体识别稳定化已完成 R2 复核轮 (2026-10-10) 并做 OpenCode R2 复审返修. 本轮 C1.5 冻结 C1-R2、禁止改生产算法, 需你**独立复核 R2 复审发现的 2 失实 + 1 自相矛盾是否已真实闭合**(不采信 REPAIR 文档自述, 直接读源码/数据).

## 证据根
`D:/Code/ldiar/docs/human_capture/evidence/2026-10-09_c1_dynamic_stabilization/`
- 主报告: `r2/REVIEW_AND_RERUN_R2.md`
- 返修记录: `r2/REPAIR_AFTER_R2_REVIEW.md`
- 审计脚本: `workspace/c1_label_audit.py`, `workspace/c1_rf_v2.py`
- 数据: `label_audit/report.json`, `rf_v2/SUMMARY.md` (或 results.json)
- R2 manifest: `r2/SHA_MANIFEST_R2.sha256`

## 逐条独立核验 (重算或静态读源码, 给 PASS/FAIL/UNKNOWN + 一行证据锚)
1. **z_band 恒真锚点修复**: R2 复审发现 `c1_label_audit.py` 的 z_band 检查曾是 `pass: True` 硬编码. 读现行源码 — 它现在是否做真比对 (probe/overlay 各须出现 0.1/2.3 ≥1 次)? 在 `label_audit/report.json` 找 z_band 行的 `probe_occurrences`/`overlay_occurrences` 实值.
2. **v2e 真特征消融**: R2 复审发现 v2e 段曾 51 维 vstack 53 维碰撞 + `Xcomb2` 死代码 (伪消融). 读 `c1_rf_v2.py` 现行 v2e 段 — 是否已修为对 51 维做 9 噪维零填充真消融、死代码消除? `rf_v2/` 里 v2e person=0.9818/noperson=0.2989 是否有对应产物支撑?
3. **4 FAILED 如实更正**: R2 复审证伪旧 manifest 实为 4 个 FAILED 而非主报告初稿的"唯一 FAILED=manifest 自身". 读主报告 §7 — 是否已如实写为 4 FAILED (manifest 自身 + ab/summary.md + rf_v2/slice_metrics.json + rf_v2/wilson_perfeature.md)?
4. **R2 manifest 零自引用**: `r2/SHA_MANIFEST_R2.sha256` 是否不含自身条目, 且覆盖本轮新产物?

## 最终一句
R2 复审发现的 **2 失实 + 1 自相矛盾** 是否已全部闭合? (YES/NO + 一句主理由)
