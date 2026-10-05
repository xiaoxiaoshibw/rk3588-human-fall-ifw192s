# Codex GL03 R7 独立复审 / 2026-10-02

判据：GL03_ACCEPTANCE v1，固定条目及语义未改。结论：G03 结构资格 PASS；已验证软件范围 PASS，无新 FAIL，不派 R8。G06/真实身份 BLOCKED，D01 NOT_RUN/现场 BLOCKED；整单不标 ACCEPTED，GL04 未授权。

用户本轮交接授权生效：Codex 接回唯一编排/独立复审/状态收口角色；Claude Code 17:54 顶替为历史（时间来源为用户交接说明）。生产代码单写入者仍 OpenCode，R7 已 SUBMITTED 并停止写入。范围内自动 CLI 派工恢复，实际模型仍 `opencode-go/deepseek-v4.1-flash`；本轮无返工需要，未启动 CLI 推理或生产写入者。

## 基线与范围

`00_baseline.json`：master / `8a5a2b28f922794bc25277319fd8dc85681802f1`，1480 个可读 tracked+untracked 文件 SHA，完整工作树状态；`src/CMakeLists.txt` Windows 软链接不可读单列，未替换。`01_submitted_sha.json`：R7 manifest 中源码/checker/数据/验收 SHA 全匹配。检查过程 `14_end_deltas.json` 的 existing changed 为空，HEAD 未变，所有提交源码未变。

`15_scope_audit.json` 独立逆应用提交 unified patch（仅在内存）得到三处改动文件的 R6 SHA，严格校验每个 context/+ 行；node_runtime 当前 SHA 另与 R6/R7 manifest 相同。旧测试主体/旧分类及 G04/G05 逻辑未改。R7 起点既有文件仅 calibration/lidar_candidates/GL03 tests 三个声明源码变动；CLI_RECOVERY 外部流程改动、returns 实现者追加单列；软链接 UNREADABLE 表示差异不是文件修改。无冻结配置/driver/webui/数据/旧证据变化。外部 human_capture 推进 HEAD 不归因、不回滚。

提交源码：calibration `d29519a1cdb5e495d23115bc89886e9071e4f2055ff529285e933cebdb7c58a3`；lidar_candidates `30330e9a793565964310363fa2c2bea2fdce62448e2783f6edd24bdf3bd7fb75`；tests `c8203bd65223672d825beb75336d5ceaffd74a16a0165d73073b4c2e90ee76ce`；node_runtime `889ead5e24ea9553cb728d403fc2e47fd42634ba15a920124314225b0f13b06f`。

## R6 结构表逐格覆盖

14d 不是完整类型组合表：其中 lidar 数字/bool/list、reference 空容器、坏 container 字符串、坏 child 字符串已覆盖；其余格不能仅凭 7/7 判 PASS。本轮 `structure_checks.py` 沿 R6 PLAN_REVIEW 补齐，125 行逐条实际结果在 `11_structure_cells.json`，均 PASS；每行检查 resolver 与 build_snapshot（候选必须非空）、明确 unavailable、finite JSON 和 caller 未修改；完整父负例另要求 validator 抛标准 GeometryCalibrationError，无裸 AttributeError。

| R6 对象/规则 | 14d 覆盖 | 本轮独立补齐及结果 |
|---|---|---|
| full frames.lidar 非空 str | 42/True/list | 0/False/空list/dict/空串/None/缺失，全部拒绝 PASS |
| full frames.reference None/非空 str | []/{} | 数字/bool/list/空串拒绝；None/缺失保留 PASS |
| full frames/transforms/rotations object | 部分经父验证 | 字符串/数字/bool/list 拒绝；空 frames 拒绝；空 transform/rotation object 配 standalone 保留 PASS |
| full transform/rotation child object | 未列全 | 数字/bool/list/字符串/None 标准资格异常，PASS |
| 真摘要 frames/transforms | 坏字符串 | 数字/bool/list/空串拒绝；缺省/None/空 dict 保留 PASS |
| 真摘要 lidar/reference label | 未列全 | 数字/bool/list/dict/空串拒绝；缺省/None 保留，正常标签及错配 PASS |
| 真摘要 canonical child 损坏 | 字符串 + standalone | 数字/bool/list/字符串分别有/无 standalone 均拒绝，不能回退 PASS |
| child absent/None/legal unknown | 原旧检查 | 缺失/None/make_unknown_transform 配 standalone 仍投影 PASS |
| 合格 canonical + explicit T | 旧绑定断言 | 正常同 T 通过；冲突不同 T 拒绝；标签 from/to 错配拒绝 PASS |
| R6 classifier/full blocks/schema | 原 14d 三方法 | 本轮只读重跑 `10_r6_matrix.txt` PASS，不改分类 |

此表无软件结构格遗留 BLOCKED。合法 unknown 的内部语义按既有契约，不新增身份/物理要求。14d 保留旧断言不改；新增复审检查只在新证据子目录。

源码审查：calibration `_validate_geometry_calibration` 在消费前拒绝父 labels/container/child 错类型；`_legacy_summary_reason` 在取 canonical 前拒绝损坏，None 与 unknown 保持既有缺省语义；resolver 继续旧 canonical/explicit 冲突及 from/to 比较。`calibration_reference_transform` 返回 None 的防御不能绕过上游资格；node startup 的整份 validator、prospective binding 的 resolver 均先资格后采用。`build_snapshot` coordinate 对 frames 做 object 守卫；`candidates_from_cloud` 直接调用该共享入口；ROS 启动载入整份 validator；现有 replay 无标定路径未新增热更新。未用 catch-all 掩盖损坏。

## 逐条独立结论

| ID | 结果 | 依据和适用边界 |
|---|---|---|
| G01 | PASS | R7 10 原几何证据、diff 几何运算未改，本轮 12_fall 含 GL03 reference 全点/非零变换回归 |
| G02 | PASS | 实际 ground 点 min/max/median 与索引回归通过；diff 不改连接/点集合/变换数学 |
| G03 | PASS | 原失败 10_r6_matrix + 125 格独立结构检查 + 共享消费者源码审查；分类及入口回归通过 |
| G04 | PASS | 沿用 R5/R6 独立结论；node_runtime SHA 889ead5e 未变，未重做原 context checker |
| G05 | PASS | 沿用 R5/R6 固定 standalone/prospective 原子 reload 结论；同一 node SHA，未重做原生命周期 checker |
| G06 | BLOCKED | 默认分离关闭、无可信支持时保留行为通过；可信 synthetic 分离路径未启用 NOT_RUN，真实桥接/人体分离无证据 BLOCKED |
| G07 | PASS | 合法缺省/legacy/unknown 新独立正例通过，原 semantic/物理 flags/显式空场约束未改 |
| G08 | PASS | 相关 fall 326 回归、本轮 AST/首尾 SHA/独立 scope；follow R7 17 2/2 沿用（不相关未变），GL02 原收口保持；目标设备运行 NOT_RUN |
| O01 | PASS | 仅本地 ROI/pool 探索统计层；独立核 R7 与 R3 JSON 逐字节一致，SHA 7b0a9e79f4fbe3b219bd848d44480a77d39cc6d826bdb33f5d9e735eec07c2ab；真实单帧根因/人体机器人身份 BLOCKED |
| D01 | NOT_RUN | Python3.8.10/NumPy1.17.4 真机运行未做；完整帧/现场地面及人体机器人身份 BLOCKED |

验收表 12 行入口/状态覆盖：无标定/legacy/source-only、本候选 full ground/reference、损坏/版本/frame/parent、采样/非法点/过滤、wrapper/node/replay 均有上述运行或源码证据 PASS；locked 实测、occluded 预测、unselected/release/lost/ambiguous/stale/invalid/monitor、同新版本 reload 保留 R5/R6 已独立 PASS（node 未变）；无可信支持/disabled 保留 PASS；可信分离 synthetic/contact/lying 路径未启用 NOT_RUN；真实 ROI/pool 统计 PASS、身份物理 BLOCKED。未以总测试数代替条目结论。

## 命令与证据

`python -B docs/human_fall/evidence/2026-10-02_gl03_r7/codex_review_01/run_review.py`：子命令使用实际 Python3.12.10、`-B -W error`；原 R6 matrix exit0；125 cells exit0；unittest fall 326/326 exit0（包含 GL03 54）；源码 `ast.parse(feature_version=(3,8))` PASS，只代表静态语法。原始 COMMAND/EXIT 在 10/11/12，汇总 13。`python -B -W error .../scope_audit.py` exit0，独立逆 patch 与范围结果在 15。

相关全量 fall 回归用于验证改变共享 validator 的影响；未重复 R1–R6 已独立 PASS checker、GL02 专项、UI 或板端检查凑数。O01 只核已回传重跑产物一致性，不覆盖/重写历史证据。

R6 事前覆盖遗漏已承认，本轮补齐结构表后未发现实现违反明确格子，模型能力不足仍无证据。无新 FAIL，连续失败流程无需启动 R8。使用 ponytail `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。未写生产源码/生产测试、未部署/采集/联网/切模型/commit/push/reset/checkout/clean。

收口外部变化补记：测试核查阶段 HEAD 保持 8a5a2b2；文档收口期间外部 human_capture 提交推进至 `2f5385ab8ff44213a5bbcc904dfc4c379a56d306`（HR-01 PC 回传链路，五文件仅 docs/human_capture 和 pc_apps/human_replay）。此提交非本轮动作，不归因、不回滚。最终核查见 `16_final_verify.json`：GL03 源码/提交checker/旧证据 SHA 继续保持，已有文件修改限于九个授权状态文档，全部本地链接已检查；不把外部 HEAD 推进当作 GL03 证据失效。
