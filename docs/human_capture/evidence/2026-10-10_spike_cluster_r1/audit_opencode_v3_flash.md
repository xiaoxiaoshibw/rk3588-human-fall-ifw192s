# OpenCode Go DeepSeek-v4-Flash 独立审计 (审计对象: spike_cluster_r1 evidence)

日期: 2026-10-10
模型: opencode-go/deepseek-v4-flash (opencode CLI 1.18.35, 仓库 cwd)
范围: 主调仓 spike_cluster_r1 evidence + 核心 spike 源码, 9 条审计要点

## 9 条审计结论 (原文, 未修改)

1. **UNKNOWN** — evidence/ 目录下没有任何 crosscheck 产物/日志 (只有源 rerun_crosscheck.py + smoke_crosscheck.js), README §4.1 的"逐帧 IoU=1.0"不可复核; 且 tie 处理仅在 rerun_crosscheck.py:68-70, eval 路径 _harness_lib.py:88 仍是 sort(key=len) 依赖字典序 → tie 未在评估路径处理.

2. **PASS (部分)** — calibrate_k.py:35 与 freeze_baseline.py:21 的 TUNING 均无 114641; 但它进了 eval_cluster.py:45 的 GT_ANCHORS 却不在 freeze_baseline.py:24-32 SESSIONS_EVAL, 其输入 SHA 未冻结.

3. **FAIL** — k 确实只用 TUNING (calibrate_k.py:60), 但 params_frozen.json:8,24 声称加了 safety_factor=1.8; 全仓 grep 该词只出现在该 json, 且 k=0.0092 恰等于原始 calibration_k.json:121 fit_k=0.009204 (1.8× 应为 0.0166). provenance 造假.

4. **PASS** — hot 只算一次共享 (eval_cluster.py:88), A/B/C 各自计时 (:99-121), B/C 用同一 eps_fn (:106). 公平.

5. **PASS (有偏差)** — Wilson 用 independent_units 段数 (summarize_eval.py:51-56,157), 未用帧数替换; 但 :128-135 把多会话帧顺序拼接成同一 bin 不重置 run, r_1_3/stand 10 会话全 True 被压成"独立段=1" (偏保守但失真).

6. **FAIL** — README §4 写"完整性 IoU (人锚圈)", 实现却是中位中心 d_anchor≤0.55 (eval_cluster.py:130-133,75), frac_in_anchor 算了 (:137-142) 但 summarize 从不使用; 该近似风险无任何记录.

7. **PASS** — detect_overlay.js / rf_person.js / bg_envelope.json / _harness_lib.py 现 sha256 与 baseline.json:6-17 code_frozen 逐字相同; git status dirty=132 与 baseline.json:34 一致. 生产文件未被 spike 改动.

8. **PASS** — 精确复现: 121622 C cab=53.3% vs A=21.5%, C rank3 为 n=34 的柜位簇 (d_cab=0.053) 越过 min_points=30 (eval_frames 121622 行), 归因成立.
旁证: 122616/637 上 C 把 A 的 90%+ 柜位捕获降到 0%, 非全输.

9. **PASS (空洞)** — "100.0%" 与 CI 同源 (wilson_ci(hot_units...), :157), 即段级 1/1, 未把帧 100% 当段级; 但 n=1 使区间 [21,100] 无信息, 标签未标"段"易误读.

附: 流程缺口 (不计入 9 条) — calibration_k_stdout.log 为 0 字节, FINAL_REPORT.md / eval_summary.json / README §7 的 attribution_fail.py 均缺失/未落盘, README 状态仍是"执行中".

## 与全过程校验的交叉比

- 与 121622 f87 case 一致 (README 提及的 n=33 小旁簇 -> A 的 f87 fr=1).
- Cab 捕获 / sf 数与各步骤先前本地输出一致.
- k=0.0092 = calibration fit. provenance 问题已在 main 修正为合法文档.
