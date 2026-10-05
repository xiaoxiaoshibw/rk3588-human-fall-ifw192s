# GL-I06 R1 指定只读独立独审（OpenCode Go Flash / default DB）

- 工单：GL-I06 R1；唯一验收表 `docs/human_fall/GLI06_ACCEPTANCE.md` v1（SHA256 `58983b71…ac847`，与 manifest/实际一致）。
- 角色：只读独立二审，不写算法/生产/配置/输入/旧证据；作者 Codex 已停写（`18_SUBMISSION_01.md`）。
- 起始 branch/HEAD：master / `cbd0be1c86a1051a9a5800dfb7263f842896e1e6`（与 before/submission/manifest 一致）。
- 指定模型/库：`opencode-go/deepseek-v4.1-flash`，default DB。控制器提供的 probe：`21_service_probe_01_meta.json` / `23_probe_session_01.json`，session `ses_efa9b0eddffeCDGAhIWtGA8fpk`，回复 `PROBE_OK`，exit 0（14.34s）。本次二审流：控制器 `22_second_review_01.jsonl`（本会话）。
- ponytail：本机 native skill 读取路径 `C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（作者声明路径为 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`；未扫描外部 Codex skill 目录）。
- 本轮新检查/日志/报告只写 `opencode_review_01/`；`returns/GL-I06.md` 仅追加。未部署/采集/改driver/网络/模型/DB/auth，未改源码或自批标定。

## 1. 独立方法

不复用作者 oracle。自写“纯标量几何 oracle”（`0.8×best` NEAR、`>10°` 或 `>0.05m` distinct、ALL/NEAR/BEST_ONLY、BEST_ONLY 不作门）逐案例比对：

1. 清单/基线全量 SHA（646 清单文件 + 2917 有哈希冻结依赖 + before/submission 全表）。
2. 加载 **全部** 62×R0、62×3 K 的 `_02` 台账、90 个最终 holdout 台账，独立 oracle 核对 full-W 与 stored-subset 两个域。
3. 从源码重算（不复用已存 W）：scene/replay SHA、原生 fitter vs replay、K1/2/3 的 W/counts、`candidate_budget=0`、真实 WHAT_IF。
4. 独立推导合约反例期望（全排列 + 每预算 zero/one-short/exact/+1），只调用冻结 I05 `search_events`。
5. 无效输入拒绝、J/覆盖重算、注入 gate/cycle、AST 3.8、破坏性写入拒绝。

## 2. 命令与退出码（本轮新证据）

| # | 脚本 | 退出 | 结果 |
|---|---|---|---|
| 01 | `01_manifest_verify_01.py` | 0 | manifest 646/646、frozen 2917/2922（5 项为 before 即缺/坏符号链接，前后一致）、before/submission 哈希全匹配、changed=0、acceptance SHA 匹配 |
| 02 | `02_probe_a01_a03_01.py` | 0 | 62 R0 + K1：独立 oracle 与 full/stored 域 0 失败 |
| 03 | `03_probe_contract_recompute_01.py` | 0 | 合约 0/预算 0；重算 clean/high_noise/wall/dual K1-3 + WHAT_IF 0 失败 |
| 04 | `04_probe_a02_a03_a05_01.py` | 0 | 186 台账 full-W oracle/best/无误闭合 0 失败；A02 计数恒等式 0；J/覆盖重算 0；W 随 K 变化 25/62 |
| 05 | `05_probe_a04_a06_a07_s01_01.py` | 1 | A04/A07/S01 0 失败；末尾打印 KeyError（输出已写），由 06 修订 |
| 06 | `06_probe_a06_validation_02.py` | 0 | 非退化案例 3 组独立 validation 0 失败；区域几何 0；最终 holdout 0；freeze 早于首个 final 0.87s |
| 07 | `07_probe_invalid_inputs_scope_01.py` | 0 | 17 项非法输入全拒；ignored 输入 NPZ/bin/meta 均在且 SHA 符 |
| 08 | `08_probe_final_holdout_oracle_01.py` | 0 | 90 最终台账 full-W oracle 0 失败（36 closed） |
| 09 | `09_summary_01.py` | 0 | 汇总 `09_summary_01.json` |

修订记录：05 首版仅打印崩溃（exit 1，结果 JSON 已产出），06 为修订版；08 首版文件名解析 bug（exit 1），修正后 exit 0。均未覆盖旧文件。

## 3. 逐条判定（对 GLI06_ACCEPTANCE v1）

| ID | 判定 | 证据 / 说明 |
|---|---|---|
| **A01** | **PASS** | 清单 646/646、冻结依赖 2917/2922（其余 5 项 before 即为 `missing_or_nonregular`/坏符号链接，before=submission 一致，非本轮变化）；before→submission `changed_sha=[]`、新增仅在 run 根；62 R0 的 source/FIT/settings/raw/sample SHA 与 K 台账一致；K1 W 与 R0 W 全等；fresh 重算 SHA 复现；每个 variant 的 W 域独立（`metric_domain` 明示）。 |
| **A02** | **PASS** | 186 台账计数恒等式全成立（`qualified=refined+unprocessed`、`produced=retained+merged_exact+unstored`、`refined_calls=produced+rejected`）；raw 逐 draw 分 `sample_separation/sample_area/angle/height/support/qualified`；资源 `resource_gap` 与收敛 `nonconverged` 分列；`reasons` 汇总不替代计数。 |
| **A03** | **PASS** | 独立标量 oracle 与 62 R0 + 186 K + 90 final 的 full-W 及 stored-subset 域逐对全等，0 失败；all-similar(0/4/8)、chain middle-best(0/6/12)、ties、weak distinct、`.8` 边界、late strong/distinct、精确合并多重性（trace `retained+2×merged_exact`）全部独立验证；BEST_ONLY 从不是门（chain 中 best 仅诊断仍 unresolved）；full best_support 恒等于 W 的支持最大值；`candidate_budget=0` 时 full W 非空且 best=max(W)，stored best 为 None。 |
| **A04** | **PASS** | 复现 R0 反例：high_noise seed7 raw0 draw `[484,148,348]`，单次 TLS 法向误差 `0.8273688078°`、offset `0.0143420495m`、成员变化 108，全标签地面 TLS `0.0864976279°/0.0010122343m`，GT 合成 `n=[0,0,1],d=1.4`。K2/K3 同 sampled 域；真实数值不收敛存在（high_noise K2 `nonconverged=682/683`）且强制 unresolved；注入 two-cycle/later-height/later-angle/degenerate/first-invalid 均保留最后有效见证、无静默成功回退；LO 资源缺口（`lo_budget=0`）单列为 unresolved。 |
| **A05** | **PASS** | full-W best 恒为最大支持；J/占用/覆盖按全 FIT 独立重算 0 差异（high_noise K1 全 W）；17 项非法输入（schema bool/2、单位、frame、source/caller/settings 变更、NaN、zero 阈值、零 up、NaN height、K=0/bool、LO>6000、非 Nx3、非单位/NaN witness）全部拒绝；J 不改状态、不吞 distinct；BEST_ONLY 为非门。**鲁棒权重 = NOT_RUN（条件未触发）**：唯一偏差为对称 Gaussian 噪声下的硬内点截断（R0），由同域 K2/K3 路线处理；wall/table/dual 是显式竞争曲面而非混杂尾部，真实 approved 合格 draw 为 0，无混合尾部证据，故 IRLS 不适用；未被当作 PASS 而记为 NOT_RUN，条件不适用经本独立审查确认。 |
| **A06** | **PASS（附限制）** | 10 类×7/19/41×输入置换（60 合成）+2 真实=62；噪声实现随 seed 变 source（同行 3 个不同 source_sha），`fixed_source_summary_01.json` 同云 3 个 RANSAC seed（source_sha 唯一、sampled_sha 不同）；非退化案例 3 个 `hold0/1/2` 独立、均非 FIT、含 `source_xyz_bounds`、按全 80 行无残差过滤打分（真实 WHAT_IF 为 2064/119/542 全行）；无 false-closed；`method_freeze_01.json` 早于首个最终数值文件（mtime 差 0.87s），实现 SHA 与冻结一致、90 最终台账 `freeze_sha` 全等、最终 36 closed 独立 oracle 无失败；最终 holdout 合成、非真实物理。**限制**：collinear/narrow_band（及 real_approved W=0）无平面，独立区域打分无从定义（13/62 dev 案例），故其区域误差缺失、不构成误闭合；另“竞争 closed”不认证区域/物理质量——wall K1 以 `0.412°/0.043m` 区域 RMS 仍被竞争 oracle 记为 closed，已在 `development_metrics_01.json`/提交中披露，属已知限制。 |
| **A07** | **PASS** | 每 K 独立 3 次 active 计时；12 组三重复 + 真实 3 次；阶段 sampling/raw/LO/refine/decision/serialization 与序列化字节均保留；decision 另列 full-domain 发布耗时（`additional_full_domain_decision_s`）；独立子进程 Windows `PeakWorkingSet/PeakPrivateCommit`（K1 `71970816/733319168`、K2 `78929920/739872768`、K3 `91549696/753819648`，含 imports 全进程）；源码每 run 一次 dtype 转换（同冻结 I05）；`runtime_scope` 明示桌面、无 RK3588/端到端加速声明。 |
| **S01** | **PASS（软件）** | ponytail 读取路径已记录（作者 + 本机）；先 diag（`00_diag.md`）、单 writer、`write_new` 拒覆盖并限 research 根（独立验证）、首尾含 untracked 与显式 ignored；实际指定 Go Flash/default DB probe 由控制器提供（`PROBE_OK`, exit 0）；本次指定二审即本报告会话。作者提交时正确地记 S01=NOT_RUN（待二审），本轮由实际指定二审闭合。 |
| **B01** | **BLOCKED** | `physical_verified=false`、无 `ground.valid`；真实 up/点云原点高度/地面身份未核；真实 approved 合格 draw=0；closed 仅指有限已见序列，未写 `ground.status=valid`。物理资料缺失，保持 BLOCKED。 |
| **D01** | **NOT_RUN** | 无采集/部署/设备运行/production 接入；仅桌面离线；RK3588 性能未跑。 |
| **Q01** | **PASS** | 身份/输入/不可覆盖/无跨调用缓存；schema bool、空序列非法 K/LO 等拒绝（独立复验）。 |
| **Q02** | **PASS** | ALL/NEAR/BEST_ONLY×tie/链/弱 distinct/晚 best×完整域；每预算 zero/one-short/exact/+1 独立期望全对。 |
| **Q03** | **PASS** | K1/2/3×stable/nonconverged/LO 缺口；注入 solver-state 单列且明确非经验 TLS；真实数值不收敛独立复现。 |
| **Q04** | **PASS（鲁棒 NOT_RUN）** | 同支持 J 仅诊断、小 J distinct 不吞；鲁棒权重零尺度条件未触发，见 A05。 |
| **Q05** | **PASS（真实最终留出 NOT_RUN）** | 硬场景/seed/置换/固定 source/真实 WHAT_IF/验证独立均已核；真实物理最终留出因 B01 BLOCKED 未跑。 |
| **Q06** | **PASS** | 成本/否定/冻结/停写均已完成；实际 probe（控制器）与本次指定二审在场；未自动下一单。 |

## 4. 集中结论

- 未发现违反 GLI06_ACCEPTANCE v1 的软件缺陷；未制造 PASS，未改需求。A06 的退化案例区域打分为契约允许的限制，且作者已在 `GT_scope`/提交中披露。
- 竞争 closed（`seen_pairwise_closed`/`seen_dominant_pool_closed`）仅为本有限已见序列关系，不是物理/区域质量或 `ground.valid` 证书；wall K1 的 `0.412°/0.043m` 提醒独审不得把 closed 读成标定合格。
- 采用结论“保留冻结单次 TLS、不采用 K2/K3”有据：K2/K3 单 seed 偏差虽降，但新增未决与真实不收敛（high_noise K2 `682/683`、wall/dual 等），未过采用门；无伪改进、无收益宣称。
- 存储/LO/迭代/trace 缺口即使有完整诊断 W 仍记 unresolved，未伪闭合；生产/配置/driver/UI/HR/旧证据在本轮前后 SHA 未变。
- 无返工（REWORK=0）；设备/物理保持 B01 BLOCKED、D01 NOT_RUN。

**SECOND_REVIEW_SUBMITTED / STOPPED**
