# C1 动态人体识别稳定化 — 最终报告

> 日期：2026-10-09（Asia/Shanghai）。状态：**自验完成 + 独立复审 R1 修复后重审**。
> 范围：仅 PC 离线 / 证据 / 独立工具；生产算法零改动，未触板端。

---

## 1. 复审 R1 处置总览

| # | 审计员裁定 | 本轮处置 |
|---|---|---|
| #1 统计真实性 (Wilson 帧级伪重复) | FAIL → **已修复**：`rf_v2/gate_by_session.md`（按独立段 n=6 重算，**作废** 旧 `gate_confidence.md`，person 下界≈0.61——诚实暴露非过拟合） |
| #2 泄漏审计方向反/域混合 | FAIL → 修复+重审再改：**簇级单域+3特征集**（`leakage_slice.md`）+ **有效消融补丁 `wilson_perfeature.md`**（minus 全 0 经 importances 诊断为 RF 结构性冗余；均值对称差显示真实分离力在 fv48 r_lt3/d=3.53、fv17 zb_0912/2.51、fv29 cov_yy/2.25、fv46 i_p50/1.96，含 fv0 n_pts/1.56——与采样域强绑定；"泄漏已排除"不作主张，降级为"n_pts 非主靠+域内分离强+域外未验证"） |
| #3 标签审计 | PASS（含口径外提示：全 auto/零动态）→ 在 §3 作为 UNKNOWN/know-unknown 声明 |
| #4 Track 闪烁命名/悬空引用 | FAIL → **已修复**：`ab/per_session.json`、`ab/summary.md` 字段更名 `furniture_reentry_episodes`；`flicker_analysis.json` 已复制到证据根并解释"女近 18 = 柜面最断续" |
| #5 推理耗时定性 | PASS（仅注释）→ 已补结构化耗时与 js/py prob 差上限（ab/summary.md） |
| A1 `mf_v2/` 空目录 | **已处置**：rmdir 删除 |
| A2 零动态真值 | **如实声明**：C1 目标"动态召回" 在数据上**不可测**，降级主张（§6） |
| A5 锚点 SHA/生产零改动 | PASS |

`c1_ab_metrics.py`、`c1_hierarchical_gate.py`、`c1_repair_r1.py`（新）、原 `c1_confidence_width.py`（作废，对应文档删除）在 `workspace/`。

---

## 2. C1.1 B2-A-FIX-R1 复核（任务1）

跨 session / 色缓存 / 逆序 / 重复帧 / 关联一致性：

- **探针↔生产蓝图一致**：`label_audit/report.md` 13/13 锚点全绿（find_hot/find_clusters/associate 数值指纹、TRACK_GATE/TTL/MIN_AGE/BG_CELL/z-band/+0.25/30pts/top4/claimed/阈值档）。
- **跨 session**：`replay.js load()` 单点入口（`notify_session` + `reset` + `set_leveled_in_s(true)`），`finish_load` 重挂 `attach_color(S.colour)`（E#2 修复），`reset()` 实清色缓存红点（E#3 修复）。
- **逆序 / 跳帧**：`replay.js set_idx` 的 `tracker_last_idx` 守卫——同 idx 重入跳过 `on_frame`，`|Δ|≠1` 时 reset+单帧重建（诚实不冒充历史；注释自检）。
- **重复帧**：帧 identity 防止二次 associate；overlay 层 `frame_no=2` 若被重现调用，上层守卫在 set_idx 挡。
- **结论 PASS**，证据：`label_audit/report.json` + `blueprint_consistency` 全 true。

## 3. C1.2 漏检归因（任务2）

六段 915 帧，级联四级：

| 会话 | 帧数 | 无簇 | 无人簇 | RF拒绝 | Track未确认 | shown |
|---|---|---|---|---|---|---|
| 男近/中/远 | 116/139/111 | 0 | 0 | 0 | 2+2+2 (开场 age<3) | 114/137/109 |
| 女近/中/远 | 218/107/223 | 0 | 0 | 0 | 2+2+2 (开场 age<3) | 216/105/221 |

- `attribution/summary.md` + `attribution_v2/summary.md`：
  - **BG→cluster→RF**：0 漏（98.7–99.1% shown；仅开场 2 帧 age<MIN_AGE）。
  - **v_airoi 100% 不作独立证据**（GT-ROI 喂检测器，循环论证——审计员 §3 提示）；可信项是 `v_p`（生产拓扑）。
- **家具非人主因**：柜位出现在女近 53/218、女中 23/107、男近 119/116、男中 128/139 帧，0 帧下 0.55。
- 距离变异：男远（122700）person 簇 prob p10=0.95（**未证实"远距离漏检"**，但测试域仅 ≤2.5m）。

## 4. C1.3 标签审计（任务3）

- `label_audit/report.json`：6 段 `posture_set=['stand']`，`confidence_set=['auto']`，`human_annotations=0`（全 AI 自动判读）。
- 5 段帽子会话语义 `UNKNOWN`；训练 pod 按 `train_person_rf.py` LoS，dedup_none 正常，跨会话无共享帧。
- `c1_label_audit.py`：13/13 锚点全绿（见 §2）。

## 5. C1.4 RF v2 离线候选（任务4）

- 独立审计 R2 裁定泄漏消融"退化"（minus 全 0）→ 已补 `wilson_perfeature.md`（双特征组合 + 均值对称差 + importances 诊断），结论修正为三条诚实主张（非"泄漏已排除"）。

- 保留 RF v1 工件不变（`rf_person_v1.json` sha 4c83db）。
- 训练/评测（LoS）：`rf_v2/results.json` / `SUMMARY.md`。
  - `v1_base`（仅帧级 pod）= furniture_reject 0.000；
  - `v2b_hard_neg`（+324 家具簇作 noperson）= person 1.000 / furniture_reject 0.270；
  - `v2c/v2d/v2e` = 0.24–0.27 —— 重训 RF 是弱家具判别器，**C1.6 用硬门，不依赖重训**。
- **泄漏审计修复**（`leakage_slice.md`）：簇级单域，3 特征集（full/noleak/minimal）+ 逐特征消融。
  - minimal_3（zmax/z_range/upright）furniture_rej **0.605 > full_51 0.568**——新特征候选可单独作进 C2 方向，但 C1 未授权新增。
- **主张降级**：RF v2 重训不足以过 furniture 关；离线 v2 = 硬门 `n_pts≥500`。

## 6. C1.5 Track 闪烁/丢失研究（任务5）

- `flicker_analysis.json`（上游锚点）+ 6 段 jsonl。
- 根因（生产零改动如实）：
  - 检测侧间歇成簇：柜位 presence run 中位 = 1 帧 → TTL=15 未被击穿；
  - 柜 prob 自始至终 ≥0.76（无 RF 参数可调）；
  - 截图 #8/#11 = 跨会话 uid 累积（显示缺陷，已修复 E#2/E#3）。
- 无 TTL 延长：缺陷定位在检测侧成簇 + RF 不能把家具 vs 人分开（样本域外）。

## 7. C1.6 A/B 对比（任务6）

`ab/per_session.json` + `ab/summary.md`（R1 修复版），0.55 档：

| 会话 | 人簇 confirmed | 家具簇(RF≥0.55) | 人 episodes | 家具 reentry |
|---|---|---|---|---|
| 男近 | 117→116¹ | 119→**0** | 2→1 | 12→**0** |
| 男中 | 139→139 | 128→**0** | 1→1 | 13→**0** |
| 男远 | 111→111 | 0→0 | 1→1 | 0→0 |
| 女近 | 218→218 | 53→**0** | 1→1 | 18→**0** |
| 女中 | 108→107¹ | 23→**0** | 1→1 | 15→**0** |
| 女远 | 223→223 | 0→0 | 1→1 | 0→0 |

¹ 121622 frame87 n=33 小旁簇 + 男近 1 帧；两帧同帧主簇（rank0, n≈2000）仍 confirmed — track show 症状零。

- **动态真人召回/轨迹碎片/ID 切换** → **UNKNOWN**（6 段全静态站立，xy 跨度 0.03–0.06m，无动态真值；C1 不制造假 GT）。
- Track ID 切换（静态）：v1 12/13/18/15 → v2 全 0。
- 推理：硬门 O(1)，省 26% RF 调用（≈324/1235 簇），JS vs Python prob 差 max 0.05（已在 ab/summary.md 明示）。

## 8. C1.7 回归（任务7）

- 旧参数 (`b2a_shadow_probe.js`: claimed + z带/bg差分/聚类/RF v1 0.55) 零改动（`git status` 未跟踪，与 working tree `detect_overlay.js` 锚点 SHA 一致）。
- `workspace/shadow_raw` 与 2026-10-09_b2a_fix_r1/after_fix 逐位一致（cmp 两类 jsonl 122637 + 121723 均 IDENTICAL）。
- 生产 protected (`human_pipe_lib.js`/`human_pipe_lib.test.js`) 不受本轮影响（报告中 4 枚 SHA 与工作树一致）。

## 9. C1.8 独立复审（任务8）

- opencode `opencode-go/deepseek-v4.1-flash` 已执行 R1 复审，`C1_INDEPENDENT_REVIEW.md` 记录 5 裁定 + 5 附加。
- 本轮修复 #1/#2/#4/#5+A1 后重审触发；R1 FIX 与 R2 判定在 §10。

---

## 10. C1 最终判定（复审修复后）

| 维度 | 结论 | 证据 |
|---|---|---|
| 关联/会话/色缓存生命周期 | PASS | label_audit/report.md 13/13；E#2/E#3 已在 replay.js |
| 漏检归因（静态 stand） | PASS | attribution(_v2)/summary.md |
| 标签审计 | PASS（know-unkonws 明示） | label_audit/report.json |
| RF v2 离线候选 | PASS（外部重训弱；硬门候选） | rf_v2/results.json + leakage_slice.md |
| Track 闪烁/梯量化 | PASS | flicker_analysis.json + per_session.json |
| **C1 统计 泛化主张** | **FAIL（修复后仍受限）** | gate_by_session.md person 段级下界 0.61，非 0.99 |
| **动态真人召回** | **UNKNOWN（不可测）** | 6 段全 stand |
| **生产接入** | **BLOCKED（独立验收）** | 未动生产 |

### **C1：PASS（限本采样域的静态 stand 任务，6 段 915 帧）**
### **端到端进入 C2 资格：NO（维持审计 R2 裁定，理由如实保留）**

**R2 维持 NO 的核心理由（不可争议，被本报告采纳为最终判定）**：
1. **核心目标无真值**：C1 名义"动态稳定化"，但全数据零动态帧（xy 跨度 0.03–0.06 m），动态召回 UNKNOWN——诚实声明 ≠ 完成目标；
2. **统计主张自我作废**：修复把 Wilson 从帧级 0.994 降为段级 0.61，即"非过拟合"论据被撤回，泛化维度自判 FAIL；
3. **泄漏消融证据仍虚**：full≡noleak、逐特征/去二组合 Δ≡0（importances 实测=max 10.8% (i_p90)、n_pts 7.5% 高度分散 → RF 结构性冗余吸收，非特征无贡献），"泄漏已排除"未真正成立。

**可采信部分（供 C2 继承，带条件）**：硬门 `n_pts≥500` 作为**未经泛化验证的域内预过滤**、Track/关联/HUD 生命周期一致性（13/13 锚点）、标签审计口径、证据命名/引用——可入 C2 草案，但**不构成放行**。

**C2 最小门槛（冻结，需用户另行授权开工）**：
1. 采集 ≥1 段真实动态（walk/起落）会话作 GT，把动态召回从 UNKNOWN 变可测；
2. 远距/遮挡/异房间新采样，把段级 Wilson 下界 0.61 撑回（域伪影剥离）；
3. 泄漏消融升级为域外 holdout 评测（域内消融已证明无效），清理残留过度主张（**本轮已清理 SUMMARY.md:8**）；
4. 证据目录卫生（**本轮已做：mf_v2、workspace/ab、workspace/rf_v2 空目录已删；flicker_analysis.json 入库**）。

### 生产接入：**继续 BLOCKED**
- 本轮零改动生产（`human_pipe_lib.js` / `detect_overlay.js` 未 commit）；
- 硬门 n_pts≥500 目前只在 `b2a_shadow_probe_v2.js` + `c1_repair_r1.py` 的离线探针里；
- 上线需独立验收 + 用户授权。
