## 2026-10-05 GL-A R1 / OpenCode / SUBMITTED

# GL-A R1 回传（实现者自述；只提交，不自行 ACCEPTED）

状态 SUBMITTED。实现者已停写；指定只读独审由后续流程按现行角色/服务可用性派发（本轮不自行开审）。下表 PASS 为作者自验，不等于 Codex 验收或整单 ACCEPTED。

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：GL-A（AGL-A-*，统一 PointDomain/PlaneEstimate 与三薄适配器）/ R1 / OpenCode CLI（模型自报 opencode-go/deepseek-v4.1-flash；用户直接授权启动）/ 2026-10-05（Asia/Shanghai）。
- 验收表路径 / 版本 / SHA（提交时记录）：`docs/human_fall/tickets/GL-A_adaptive_estimator_interface.md`，唯一验收表 v1，SHA256=5f16e5d679d8487160b1bba8a41cbe95bac958e5fa9e91e72e50455ae2835fa9（未改动）。设计来源：`docs/human_fall/ADAPTIVE_GROUND_LEVELING_CONTRACT.md` §1–3、`ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md` §3–4。
- 执行方式 / 实际会话与模型（可得才填）：Windows 开发机 Python 3.12.10 / NumPy 1.26.4；板端兼容目标 Python 3.8 / NumPy 1.17.4（纯 stdlib+NumPy，无 ROS/OpenCV/RKNN）。会话/流式 ID 不可得，未编造。
- 状态：SUBMITTED；软件条目作者自验见下表；设备/物理本单不适用（无设备动作）。不宣布总体软件 PASS 或 ACCEPTED。
- 起始 branch/HEAD / 工作树 / 范围内用户差异 / 源码与配置 SHA 证据：master / 8676bb479d4ae35cf22075cfe70225cf2220572a / dirty 257 行（含全部未跟踪生产资料，00_baseline.txt）；本轮只新增未跟踪文件、未修改任何已跟踪文件（30_scope_check.txt）、HEAD 提交时不变；冻结依赖 10 个 blob 哈希与基线逐一相同；无 commit/push/reset/checkout。
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail`（skill 工具加载；SKILL.md 位于该 base 目录）。使用路径：先复用冻结数值原语与校验助手（ground_diagnostics.pca_plane/residual_stats、joint_leveling.joint_rotation、ground_evidence.digest/keys/number/require/text、numeric.strict_numeric_array），未新增依赖、未重构旧 production；三适配器分文件、集中检查单一测试文件、不引入接口/工厂/配置框架等未要求抽象。

## 集中诊断与根因覆盖

实现前集中诊断与操作矩阵逐行映射见 `evidence/2026-10-05_agl_a_r1/00_diag.md`（入口、赋值顺序、保护/拒绝行为、保留行为）。本单为规划内新增能力，非缺陷修复；风险与覆盖：

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| AGL-A-01/04（无统一记录） | 旧 `ground.py` 结果语义/默认冻结、三处数值实现分散 | 后续 B/C/D/E/G 只读消费统一记录 | `core/adaptive_ground/contracts.py`、`estimators/*` | 冻结 ground/calibration/config/driver/webui/旧证据不动 |
| AGL-A-03/05（同 ID 异内容、跨配置复用） | 无内容寻址/配置 epoch 绑定 | build/validate/estimate 全路径 | `selection.py`（SHA+domain_id）、contracts（config_id 比对） | 旧记录不被修复回写；无缓存、无状态 |
| AGL-A-02（法向符号/角度约定漂移） | 符号二义与 yaw 自由度 | 三输出及后续 transform | `contracts.canonical_plane/angles_from_normal/display_rotation` | 复用 joint_leveling Rx@Ry 约定，不另立一套 |

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码 SHA256 |
|---|---|---|---|
| `src/human_fall_detection/core/adaptive_ground/__init__.py` | 新包声明（纯 core） | 新增，无既有内容 | b9bca62acd6a30ba6df8852d44b613d92f03a387d1bac55cb4be3281a619c63d |
| `.../contracts.py` | FrameKey/配置严格校验、n/d 规范、角度与 Rx@Ry 显示旋转、PlaneEstimate 装配/校验 | 新增 | d879a82ad3a0543abd5267a07e833b91c9458c9af1a9609d0bc06f884405d687 |
| `.../selection.py` | PointDomain 构建/校验/引用摘要（公共预筛、SHA、内容寻址、所有权深拷贝） | 新增 | b4d8147baf0832a09067d19556ef603f801b6047661097369f024e1fe3b79476 |
| `.../estimators/__init__.py` | `ESTIMATORS` 映射 | 新增 | b63e40aec09f74b777c28f4caae297cf96a2e61c6eb55b89e3b6421a81da85f9 |
| `.../estimators/tls.py` | 加权协方差 eigh 适配器 | 新增 | 76ee48693909fa85377000f96c21bd5b15c28dfbbe5516510b34c41d0eea461c |
| `.../estimators/svd.py` | 加权中心化薄 SVD 适配器 | 新增 | 051045b770726ef21e3729f4ea4bb5af2da061f57ecb04ec44693093343e7420 |
| `.../estimators/ransac.py` | 有界 raw RANSAC 适配器（无精修） | 新增 | 8d4cad60fb47c2c9dcd353ff3896150e4714bbe49619344da66b6aa2dfc760c7 |
| `src/human_fall_detection/tests/test_agl_a_estimators.py` | 集中检查（AGL-A-01..05） | 新增 | e37499f0f0446e9b97f89d8be147889347953801dc4fa2c41ff4003bbd540954 |
| `docs/human_fall/evidence/2026-10-05_agl_a_r1/*` | 基线/诊断/日志/样例 manifest/范围核查 | 本轮新证据目录 | 见 30_scope_check.txt |
| `docs/human_fall/returns/GL-A.md` | 本回传 | 本轮新建 | 提交后复核 |

单位/坐标：unit n、offset d（m），`n·p+d=0`；pitch=atan2(−nx,nz)、roll=asin(ny)、R=Rx(roll)@Ry(pitch)，yaw/tx/ty=0 gauge；输出 `pitch_deg/roll_deg/normal_source/offset_source_m/sign_anchor`。版本兼容：新记录独立 kind（`adaptive_plane_estimate`/`adaptive_point_domain`，schema=1），不混旧 kind；门限参数属 DRAFT profile 语义，本单不写运行 YAML。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| AGL-A-01 同域绑定 | offline synthetic | 20_test_agl_a_log.txt：test_shared_domain_binding_and_json_safe_outputs_AGL_A_01 | PASS（作者自验）/exit 0 | 三输出 domain_id/point/rows/weights SHA 与 domain 相同、FrameKey 相同、键集合相同；域数组调用前后逐字节相同；`hypothesis_count=861`（无 cap 截断）；记录 `json.dumps(allow_nan=False)` 通过；同内容重建 domain_id 相同 |
| AGL-A-02 GT/翻转/方向 | offline synthetic GT | 同上：test_known_gt_angles_flip_and_display_rotation_AGL_A_02 | PASS（作者自验）/exit 0 | pitch 10/26/45° 与 roll 0/±10° 及 26.623261/−1.394671：三法角度复现 places=6；`Rn=up` 误差≤1e-12；det=+1；yaw gauge（R[0][1]=0）；平面点映射 z≈0≤1e-9；`(n,d)`/`(−n,−d)` 规范一致；⊥anchor 与零范数拒 |
| AGL-A-03 严格拒收 | offline negative matrix | 同上：test_strict_refusals_and_invalid_no_identity_AGL_A_03 | PASS（作者自验）/exit 0 | bool/string/NaN/Inf/empty/错形状/索引重复/负/错长/weights 非正/移帧字段/units/schema 全部 raise；配置 12 个负例 raise；域与配置不匹配、跨帧 estimate×domain 校验 raise；2 点 → invalid（几何 null、confidence 0、quality NOT_EVALUATED、无 physical/runtime/identity 字段）；共线三法 `GL_DEGENERATE_GEOMETRY`；极窄输出 ratio<0.01 且不越权拒绝（留给 GL-B） |
| AGL-A-04 数值交叉/分母 | offline synthetic | 同上：test_numeric_cross_check_and_ransac_denominators_AGL_A_04 | PASS（作者自验）/exit 0 | clean/noisy（σ0/8mm）：TLS−SVD 角差≤1e-3°、|Δd|≤1e-5 m；RANSAC 全域分母=独立重算（point_count/support_count/support_fraction、basis=full_domain_untruncated）；iterations=861 记录；iterations>hard_cap=2000 配置期 raise；支持不足→invalid+`GL_RANSAC_INVALID`+`diagnostic_hypothesis`（标注 diagnostic only），不伪 valid |
| AGL-A-05 所有权/重载/顺序 | offline synthetic | 同上：test_ownership_reload_and_config_epoch_AGL_A_05 | PASS（作者自验）/exit 0 | 改源数组/改返回对象后 domain 逐字节不变、重跑逐位相同；同内容新 domain_id 相同、异内容新 ID；篡改域内容 validate/估计原子拒；同 config 内容不同对象 config_id 与结果相同；新 config（seed）→不同 config_id 且双向跨用拒；调用顺序无关 |
| AGL-A-S01 流程 | — | 00_baseline/00_diag/30_scope_check + 回归 | 作者自验部分 PASS（ponytail 使用、基线含 untracked、前置诊断、有效回归、源 SHA、停写）；指定独审 NOT_RUN（待派发；不伪报） | — |

回归明细：改动前 `Ran 458/OK/exit 0`（01_regression_before.txt）；改动后 GL-A 套件 `Ran 5/OK/exit 0`（20_test_agl_a_log.txt）、全量 `Ran 463/OK/exit 0`（21_regression_after.txt，458+5）。冻结资产对照：见 30_scope_check.txt，10 个依赖 blob 哈希逐一等于基线；无跟踪文件改动。样例 manifest：`20_sample_manifest.json`（合成离线，含 point_domain_reference + 三估计记录；两次生成 SHA256 一致 442b840b…）。设备层：本单无设备动作，NOT_RUN 不适用。

## 未闭合与限制

- 未满足的验收ID、复现条件和解除条件：AGL-A-S01 的“指定只读独审”未跑——由后续流程按现行角色与服务可用性派发（先 probe 流程）；本轮 writer 已停写，不自行开审、不无限 probe。
- 契约允许的算法/证据限制：① 极窄/覆盖/谱退化“拒绝权”按契约属 GL-B（本轮只输出 `eigenvalue_ratio` 与全域残差，不越权）；② 质量 score/consensus/时间状态机/runner 未实现（B–H）；③ `plan §10 profile` 仍 DRAFT，AGL-A 不写运行 YAML、不冒充已批准门槛；④ 权重参与拟合，支持率/残差按点计数为协议口径（加权支持率仅诊断字段）。
- 范围外新需求及后续建议（用户本轮指示，记录不实施）：最终算法展示目标为**总控制台算法工作台**，保持解耦。GL-A 已按此交付：纯 core、无 UI/文件/ROS 依赖、全部记录 JSON 安全、另有 `point_domain_reference` 摘要；后续显示/集成单（GL-G 或 P 单）只消费版本化摘要（domain_id/config_id/各 SHA/records），不得反向 import core 数组，更不得在 UI 内重拟合。
- 设备/物理未跑项：设备/部署/采集/driver/板端网络/物理标定全部 NOT_RUN（本单范围外）；1.14 m 物理记录与 observed tz 分离语义不变。
- 后续关系：A 过软件门后才可单独授权 B；本单不启动 B～I，不接 runtime。

## 交给 Codex 独立复审

- 现行验收表与本轮变更记录：`tickets/GL-A_adaptive_estimator_interface.md` v1（SHA 如上）+ 本回传 + `evidence/2026-10-05_agl_a_r1/00_diag.md`。
- 根因诊断/完整入口检查证据：00_diag.md 操作矩阵（入口/赋值顺序/检查/拒绝/保留逐行映射）。
- 源码差异与 SHA 证据：00_baseline.txt（含 untracked 基线）、30_scope_check.txt（冻结哈希对照+新文件 SHA256+HEAD）。
- 原始日志索引：01_regression_before.txt、20_test_agl_a_log.txt、21_regression_after.txt、20_sample_manifest.json、20_sample_manifest.log、20_make_sample_manifest.py。
- 当前工单下一步：指定只读独审（服务可用时按现行 probe 流程）；按唯一验收表逐条复核后由 Codex 收口；不自动派发 GL-B。

## 2026-10-05 GL-A R2 返工 / OpenCode / SUBMITTED

# GL-A R2 返工回传（AGL-A-02 FAIL 闭合；实现者自述）

状态 SUBMITTED。R1 独审 FAIL（AGL-A-02）已按最小修复闭合；实现者已停写，二审待后续派发。下表 PASS 为作者自验，不等于 Codex 验收或整单 ACCEPTED。

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：GL-A / R2 返工（对应 R1 独审 AGL-A-02 FAIL）/ OpenCode CLI（模型自报 opencode-go/deepseek-v4.1-flash；用户明确授权返工）/ 2026-10-05（Asia/Shanghai）。
- 验收表路径 / 版本 / SHA：不变——`docs/human_fall/tickets/GL-A_adaptive_estimator_interface.md` 唯一验收表 v1，SHA256=5f16e5d679d8487160b1bba8a41cbe95bac958e5fa9e91e72e50455ae2835fa9。
- 起始 branch/HEAD / 工作树：master / 8676bb479d4ae35cf22075cfe70225cf2220572a（提交时仍不变）/ R2 只修改 R1 新增的两个未跟踪文件，未动任何已跟踪文件；未 commit/push/reset。
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail`（R1 已加载；R2 按最小根因修复执行：一行修复 + 两个回归用例，无重构、无新依赖、无扩框架）。
- 证据目录：`docs/human_fall/evidence/2026-10-05_agl_a_r2/`。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| AGL-A-02 | `canonical_plane` 只除 normal、offset 未同除 ‖n‖ → 非单位法向输入的平面被放大 ‖n‖ 倍（2z−2.64=0 变 z=2.64） | 公有入口 `canonical_plane`（`assemble_estimate` 经此）；三适配器只传单位法向故产物未受损；与作者 `00_diag.md` §0「n/d 同除归一」自相矛盾 | `contracts.py` 符号对齐前加 `value = value / norm`（一行） | 单位法向输出保持稳定（实测仅 SVD 1 ulp 级 offset 变化）；翻转仍同步作用于 n/d；零范数/非有限/非法输入拒绝不变 |

同类入口一次查完：`angles_from_normal` 只归一向量、无 offset 配对；`validate_plane_estimate` 为只读校验（要求单位法向）；无第二处。测试缺口：R1 用例只覆盖单位法向（÷1.0 不可见）；R2 新增两个回归用例（直接入口 + 公有装配链），对修复前代码各自独立 FAIL。

## 实际变更

| 文件 | 本轮用途与修改 | 提交源码 SHA256 |
|---|---|---|
| `src/human_fall_detection/core/adaptive_ground/contracts.py` | 一行修复：offset 与 normal 同步归一 | 625ff68225510af3e2ad9ef0e77d988a183f388e110f046040cbb14a1225e7fd |
| `src/human_fall_detection/tests/test_agl_a_estimators.py` | 新增 2 个回归用例（缩放/翻转直接入口；装配链；共 7 tests） | d7f1045e098a341a5cfffa643d2fa735be8faa7023e9d007cf5f23f822f3cc4d |

其余 R1 文件不变（R1 回传所列 SHA 仍有效）；R1 证据与样例 manifest 未被覆盖。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| AGL-A-02（返工项） | offline synthetic | 修复前：contracts.py 临时回退至 R1 提交字节（SHA=d879a82a…，已核对）后运行最终用例；修复后：20_test_agl_a_log.txt | FAIL→修复后 PASS（作者自验）/ exit 1→0 | 修复前 Ran 7 / failures=2 / exit 1（`([0,0,1],-2.64)!=(…,-1.32)`；`2.64!=1.32`）→ 10_regression_before_fix.txt；修复后 Ran 7 / OK / exit 0 → 20_test_agl_a_log.txt |
| AGL-A-01/03/04/05 | offline synthetic | 20_test_agl_a_log.txt（专项 7 项全过，无回归） | 保持 PASS（作者自验复跑）/ exit 0 | 同上 |
| AGL-A-S01 | — | 00_diag_rework.md、10/20/21 日志、30_scope_check.txt | 返工流程完成（作者自验）；二审 NOT_RUN（待派发） | — |

回归/对照：全量 458（R1 基线）→463（R1 提交）→465（R2，+2 回归用例），OK/exit 0；冻结 10 个依赖 blob 哈希全部=基线；HEAD 不变。样例 manifest 字节对照：R1=442b840b…，R2=62588541…，差异仅 `/estimators/svd` 的 `offset_source_m` 与两个残差统计各 1 ulp（2.220446049250313e-16），TLS/RANSAC 逐字节不变（20_manifest_diff.txt）。

## 未闭合与限制

- 指定二审未跑：待后续按现行角色/服务可用性派发；本 writer 已停写、不自行开审。
- 非阻断观察（独审提出，登记为 GL-B 前置项，不在本次返工加码）：① `region_codes` 无 SHA/未入 `domain_id`；② `validate_plane_estimate` 未比对 `sign_anchor` 与 domain `up_axis`。
- 其余限制同 R1（极窄/质量/consensus/时间状态机属 GL-B～D；profile 仍 DRAFT；无 runtime/设备/物理；物理 1.14 m 与 observed tz 分离语义不变）。

## 交给 Codex 独立复审

- R2 证据：00_diag_rework.md、01_repro_before_fix.txt、10_regression_before_fix.txt（复现方法与 contracts 哈希=d879a82a… 已注明）、20_test_agl_a_log.txt、21_regression_after.txt、20_manifest_diff.py/.txt、20_sample_manifest_after_fix.json、30_scope_check.txt。
- 源码差异：contracts.py 单行 `value = value / norm`；测试 +2 回归用例；审计用 SHA 见 30_scope_check.txt。
- 当前工单下一步：指定只读二审（服务可用时按现行 probe 流程）复核 AGL-A-02 闭合与回归；通过后按 WORKFLOW 收口；不自动派发 GL-B。
