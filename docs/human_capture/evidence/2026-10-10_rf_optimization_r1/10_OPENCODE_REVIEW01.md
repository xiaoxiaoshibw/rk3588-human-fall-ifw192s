# RF-OPTIMIZATION-R1 独立只读复核（opencode-go/deepseek-v4.1-flash）

ponytail 使用路径：已读取 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`（并加载 skill，full）。全程只读：未编辑/未生成 pycache（`-B`，已验 `no_pycache`）/未改生产/未装依赖/未部署/未采集/未 commit、push/未派 subagent。独立核算用 stdin 脚本（无文件落盘）。

## 一、实际执行

- `python -B -W error -m unittest discover -s . -p test_research.py -v` → **Ran 3 tests, OK, exit=0**，无 pycache。三条测试覆盖：退化/稀疏/非有限与置换不变（`prepare.extra/shape`）、分组与跨组重复守卫、阈值选择与 69 维/维度错配拒绝。与 03_tests_run01.log 一致。
- 环境复现：Python 3.12.10 / NumPy 1.26.4 / scikit-learn 1.9.0，与 results.json 头部一致。

## 二、独立复算（不看报告自述）

逐路线把 `run01/results.json` 各外折 `metrics` 的 tn/fp/fn/tp/n 求和、重算 P/R，与 `pooled_descriptive` **逐位相等**，亦与 SUMMARY 表一致：

| route | dims | tn | fp | fn | tp | P(复算) | R(复算) |
|---|---|---|---|---|---|---|---|
| baseline51 | 51 | 184 | 140 | 1 | 914 | 0.8672 | 0.9989 |
| rf_v2 | 51 | 196 | 128 | 1 | 914 | 0.8772 | 0.9989 |
| rf_v3 | 69 | 196 | 128 | 1 | 914 | 0.8772 | 0.9989 |
| gbdt | 69 | 312 | 12 | 1 | 914 | 0.9870 | 0.9989 |
| v3_no_position | 59 | 196 | 128 | 1 | 914 | 0.8772 | 0.9989 |
| v3_no_layers | 58 | 196 | 128 | 1 | 914 | 0.8772 | 0.9989 |
| v3_no_pca | 63 | 196 | 128 | 1 | 914 | 0.8772 | 0.9989 |

嵌套划分检查（results.json 全路线×6 外折）：外折 holdout **从不**出现在 `train_sessions`；每个内层 split 的 train/validation 会话**无交集**且并集恰等于该外折训练会话（未越界触碰外折）。`validation_classes` 本次全部为 `[0,1]`（无单类验证折触发）。`within_session_duplicates=0`。预测队列 7×1239=8673 行，每 route 覆盖 row 0–1238 各一次，`gt_status` 全 `UNVERIFIED`、`label_source` 全 `legacy_C1_position_rule`。跨组重复、非有限、69 维、`model.n_features_in_` 维度断言均在 experiment.py 内实际执行（`experiment.py:107-115,127-128,151`）。

## 三、源码主张核验

- 51 维真实定义与 `pc_apps/human_ml/frame_feature.py` **逐行吻合**：index1=常数10、index2=max(n,2000)、37–39 因“特征值降序但特征向量未同步翻转”轴义互换（frame_feature.py:86-99）、40/41/42/43/44/48/49/50 名实错位、49 与 13 精确重复（相关 1.0）。01_AUDIT 无误。
- v1 泄漏核验属实：`train_person_rf.py:56-60` `uniq+uniq` 复制空场，`:88-93` 把后半份改挂 `far_sid`，使同一向量跨 fold 出现 → 旧整帧研究不可信。
- JS/Python 接入差异属实：`rf_person.js:151` 37–39 置零、`:153` 41=RMS(≠Python 径向std)、`:86` 协方差除以 n（Python `np.cov` 为 n−1）、PCA 用三/cos 三方程且无特征向量。属“保留差异作未来接入门”，未越权改生产。
- GBDT permutation 首项为 X 中位数、位置敏感，与作者结论一致。

## 四、逐条判定

| ID | 判定 | 依据 |
|---|---|---|
| RFO-01 | **PASS（范围限定）** | 00_baseline master/347a5bf… 7755 条；06 如实列出 4 项外部变化+本轮 README，ignored 边界声明，不冒充整树冻结 |
| RFO-02 | **PASS** | 51 维逐索引定义与源码吻合，相关性/常量(1,22)在 feature_audit |
| RFO-03 | **BLOCKED** | 1239 源点重现 PASS（prepare.py:148 断言通过），但背景删除/碎簇/粘连/Track 因果无逐点/轨迹 GT → UNKNOWN |
| RFO-04 | **BLOCKED** | 无 `source:human` 签核，未增可靠困难样本；review_queue 已生成 |
| RFO-05 | **PASS** | 实跑 51/51/69/69 维、有限网格（含 depth/leaf/features/class_weight），模型 SHA/列清单/`production_eligible=false` |
| RFO-06 | **BLOCKED（泛化）/ 划分机制 PASS** | 嵌套会话划分、无跨组重复、split 清单已报告；但无新人/新景证据 |
| RFO-07 | **PASS（描述性）** | 外层 permutation、相关性、**实际删列重训**、逐会话 PR 数据+PNG/SVG、阈值扫描；代码确认未据外层选模型/阈值/特征 |
| RFO-08 | **BLOCKED** | 本机计时已测；弯腰/遮挡/动态/4–6m 层 BLOCKED，未冒充 RK3588 |
| RFO-09 | **BLOCKED** | 缺独立 source:human、3 场景/每层 2 会话，无法检验预注册门 |
| RFO-10 | **PASS** | 本次即实际只读独审，原文由调用者存档（05）；复测 exit0；未发现需修复的硬性软件 FAIL |
| RFO-11 | **PASS** | 3 项检查 `-B -W error` exit0；非有限/退化/分组重叠/重复/维度检查齐备 |
| RFO-12 | **PASS** | 工单/唯一表/回传已建，R3/R4 保持 NOT_RUN，未改 Track/生产模型 |
| D01 | **NOT_RUN** | 无设备/物理/部署/采集 |

**总体：不允许 ACCEPTED。** 软件探索无硬性 FAIL、可作为离线研究记录；可用性/完整数据验收 BLOCKED。

## 五、必须修复的软件问题（非本轮 FAIL，但需在下一轮冻结网格修正）

1. `present_class_score`（experiment.py:58-59）对单类验证折恒返回 1.0，却被用于**模型选择平均**（:94）。本数据集内层验证折恰好全部为两类，故未触发；一旦无负会话单独落进内层验证折，即会抬高该折的选参分数、偏置参数选择。应把单类折排除出选择均值（仅报告），与验收“单类折仅报告存在类别召回均值”一致。
2. `session_macro_recall`（:186）对含 `None` recall 的外折会 `np.mean` 崩溃（本数据无全负折，属潜在缺陷），应做空值保护。
3. 消融只覆盖 RF：`v3_no_position/no_layers/no_pca` 均为 RF（:133-135,150）。真正高 precision 的 gbdt 的**位置/特征组消融不在冻结网格内**，仅在事后 `sensitivity01` 以 58 维补测，故冻结 run 无法把 gbdt 优势归因到特征组。建议下一轮把 gbdt 三组消融预注册进网格。
4. `no_cross_group_duplicates`（:107-115）用 69 维浮点的 round-6 精确相等判重，抓不到“近重复”泄漏；旧 C1 是精确复制才被此守卫覆盖，健壮性有限。
5. `stand_weak` 切片是 `np.ones`（:166），等于整折，不是真实分层，报告不应把它当作“姿态覆盖”。

## 六、数据阻塞

- 六会话中 `…121723`、`…122700` **零负例**，其折 precision 名义 1.0 是空指标；pooled P 实际只由 4 个含负会话支撑。
- FP 高度集中单会话：RF 的 128 FP 全在 `…122616`，GBDT 的 12 FP 全在 `…122637`；各外折内层阈值在 0.05–0.95 间剧烈跳变。**GBDT 相对 RF 的“高 precision”主要由逐折阈值选择的不稳定性驱动，跨会话不稳定**，不能据此判 gbdt 优于 RF 或可替换生产。
- 缺独立 source:human、未见人员/家具/场景、站立以外姿态与 0–2/2–4/4–6m 分层覆盖 → RFO-09 无法检验。

## 七、关于位置泄漏（按要求特别指出）

当前 `no_position` **仅为部分删除**，不得称位置泄漏已排除：
- 只删 10 维 `{5,6,7,8,9,10,23,24,48,68}`（→59 维），仍保留 `z_p10/p50/p90(11,12,13)`、`cz(25)`、`n_pts(0)`、`max(n,2000)(2)`、径向 std(41) 等距离/位置代理，以及强相关对（3↔46/47、31/32/50、42/43）。
- 事后 `sensitivity01` 仅再删 41（共 11 维→58），仍留 `n_pts`、`max_pts` 等距离代理。
- 经验证据：`121622` 的 `range_2_4` 切片 24 个候选全为负（recall 0.0、precision None），即该会话中“水平距离”几乎完全分离类别。
- 作者在 08 报告与 `position_sensitivity.py:13` 明确写明“不声称排除位置捷径”，表述**未过度声称**，符合要求——但仍不能对外讲“位置泄漏已排除”。

## 八、R3 放行结论

**不允许 R3。** 依据 RFO-09：无独立 `source:human` 标签、无未见人员/家具/场景、姿态与距离分层不足，预注册资格门无法检验（BLOCKED）。本轮同房间、弱标签、零负会话与单会话 FP 集中，不构成可用性证据；R3/R4 应维持 NOT_RUN，直至补齐可靠人工标签与真正跨人跨景数据并有新授权。

## 九、须修复 vs 数据阻塞小结

- 软件（下一轮冻结网格前修）：上节 1–4 项；第 5 项为报告口径修正。
- 数据（须补采集+签核）：独立 source:human 困难正负样本、未见人员/家具/新场景、弯腰/遮挡/动态/远距分层；本轮无采集授权，无法自动补录。

无硬性软件 FAIL，无需立即返工；但不得据本轮宣称识别优化完成，RFO-09 未闭合前禁止 R3。