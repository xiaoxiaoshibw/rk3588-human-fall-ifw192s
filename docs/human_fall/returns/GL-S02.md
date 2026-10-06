# GL-S02 回传 · 2026-10-05 · writer OpenCode(opencode-go/deepseek-v4.1-flash) · Codex 独审

## 范围与实现

新增 `pc_apps/human_replay/floor_roi.py`：`detect_floor_regions_v3` 先调 v2，v1/v2 成功逐字返回；仅当 v2 抛 `INSUFFICIENT_CLEAN_ROI_SUPPORT` 才启用 15cm 细粒度 ROI。FINE_PROFILE：grid 0.15m、每帧点数 ≥20、间距 ≥0.5m、条件数 ≥0.1；纯度门（厚度 ≤0.18、|n_z|≥0.94、RMS≤0.025、贴面 0.08/0.18）与 25cm 逐字相同，仅把"每帧点数"按面积折算并抬到下游 holdout 下限 20。

`leveling.py` auto 入口改调 v3、`code_files` 加 `floor_roi.py`；`validation.py:floor_identified` 已接受 v3 kind；新增 `floor_roi_test.py`（6 用例）。`floor_detector.py`/`floor_sheet.py` SHA 未变。

## 证据（`evidence/2026-10-05_gl_s02_r1/`）

| 条目 | 结果 | 依据 |
|---|---|---|
| A1 合成回归 7 类 | PASS | floor_roi_test 6 用例全过；floor_sheet_test 12 用例全过；floor_detector_test 3 用例全过 |
| A2 223757 golden | PASS（识别侧） | `05_golden_223757.json`：v2 仍 `INSUFFICIENT_CLEAN_ROI_SUPPORT: clean_cells=6 min_sep=0.354 indep=0 cond=0.162`；v3 成功，34 clean boxes、min_sep=0.965m、indep=4、cond=0.285、full_height/no_manual 均 true |
| A3 223757 全流程 | **PASS（返工后达成）** | `07_run_job_223757.json`：recommended=tls，三法 tls/svd/ransac 全 valid 无 reject reason，四区+holdout 全 PASS，full rms 0.0146~0.0171m/p95 0.0296~0.0333m/support ≥0.999，全帧产物落盘。返工根因见下：旧 `_select_four` 纯按"分散"挑盒，挑中全组 rms 最高的 0.0234 盒；返工后选择器在"满足分散/独立/条件数门"的可行集内优先低 rms，选中 max 单盒 rms=0.0127 组合，同一 GL 门下三法全过。**不是物理问题，是算法选区 bug。** |
| A4 三在范围会话不回归 | PASS | `leveling_auto_test.py::test_real_sessions_detect_four_regions`：202456/203349/203135 自动识别逐字通过；`validation_test`/`leveling_test` 全过 |
| B1 契约只增不减 | PASS | FINE_PROFILE 厚度/法向/RMS/贴面与 PROFILE 逐字一致；点数 30→20 为面积折算且 ≥holdout 下限 20；间距/独立/条件数不降 |
| B2 冻结文件 SHA | PASS | floor_detector.py 72ce790f、floor_sheet.py 92d2ed10 与基线一致 |
| C1 失败/成功语义 | PASS | A 失败→floor_regions_invalid；双粒度不足→INSUFFICIENT_CLEAN_ROI_SUPPORT；成功 kind=v3、full_height_preserved=true、uses_manual_reference=false |
| C2 消费者 | PASS | validation.floor_identified 含 v3；leveling_test/validation_test/floor_sheet_test 回归通过 |
| C3 审计 | PASS | code_files 含 floor_roi.py；candidate.roi 含 grid/clean_boxes/min_sep/condition；selected_cells 含每盒 min_frame_count/span/rms/normal_z |
| S01 流程 | PASS | ponytail 已加载；基线 SHA 记录；无 commit/push/reset；未改 webui/captures/旧证据 |
| D01 设备/物理 | NOT_RUN | 本单仅离线软件 |

## 根因与遗留

- 首版 `_select_four` 只优化"几何分散"（间距/条件数），从不看每个候选盒的**自身拟合残差 rms**。34 个净盒 rms 范围 0.0076~0.0234，它挑中全集倒数第一差的 0.0234 盒；穷举 C(34,4) 证明存在 max 单盒 rms=0.0127、且间距/独立/条件数全过、三法质量门全 PASS 的可行组合。用户质疑"就是算法选错了"成立。
- 返工：`_select_four` 改为"先按既有门过滤出可行集（间距≥0.5/独立4/条件数≥0.1，逐字不变），再在可行集内按 (max rms, mean rms, condition, separation) 字典序选最优"。rms 只作排序，**不是新门**——过了纯度门的盒不会因 rms 被拒；所有 ≥ 门与契约一字未降。n≤60 时穷举，超出退回多起点贪心。
- 返工后 223757 golden 与全流程均 PASS（见 A2/A3）；三在范围会话仍直通 v1（leveling_auto_test 锚点逐字一致）。
- 全量回归 39 用例（floor_detector 3 + floor_sheet 12 + floor_roi 6 + leveling 4 + validation 2 + leveling_auto 5 + sessions 1 + fetch_lib 6）`-W error` 全 PASS，日志 `evidence/2026-10-05_gl_s02_r1/11_full_regression.log`。

## 源码 SHA（前 16 位，返工后）

- floor_roi.py 1d144e57851a00bc
- floor_roi_test.py 8f24d086e34da5ed
- leveling.py 3c3a88196cfd9851
- validation.py 469fff14d61ee2bb
- floor_detector.py 72ce790f656faf60（未变）
- floor_sheet.py 92d2ed105ac98faa（未变）

状态：**SUBMITTED / STOPPED**。A1/A2/A3/A4/B1/B2/C1/C2/C3/S01 全 PASS，D01 NOT_RUN；不冒称 ACCEPTED，外部独立复审与设备物理另行安排。上一版"区域 2 诊断"中"属真实非平面、GL 门正确拒绝"的结论已被穷举证伪——是选择器 bug，非数据问题。
