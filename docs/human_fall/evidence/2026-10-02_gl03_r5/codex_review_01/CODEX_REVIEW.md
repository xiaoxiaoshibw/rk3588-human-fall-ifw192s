# GL03 R5 独立验收 / 2026-10-02

结论：**软件仍REWORK，仅G03 FAIL；G04/G05已PASS。** 固定standalone、prospective有效绑定、原子reload及8m错移均已闭合。剩余为完整artifact与旧最小摘要分类：完整schema99父在kind缺失/null时仍投影。先完成[兼容输入审查与修订计划](PLAN_REVIEW.md)，不自动重试或换模型。

## 基线/范围

master / HEAD `49eb7581faabdda031642e04d3ef4ffe75d48331`；全部提交22_source_manifest的源码/checker/验收/数据SHA在审查开始匹配（00_baseline.json），结束仍匹配（19_final_verify.txt）。tracked+untracked完整基线审查前后无变化（18_end_deltas.json）。三声明文件范围与提交scope一致，65个driver/config/UI保护文件仍与R3独立基线一致；Windows软链接UNREADABLE:1920表示保留，未替换。

源码：calibration `1c1d40ef908e07a4d3979d19228dd520e0c2d299cf429710a9d2084233b6bbad`；node_runtime `889ead5e24ea9553cb728d403fc2e47fd42634ba15a920124314225b0f13b06f`；GL03 tests `6c0ce2f646462f4095d23436a495bb2fe0cf10b813e70766b270a5e60d9c6399`；lidar_candidates `318abc78…`未变。

外部human_capture两个文件差异按提交21_scope单列，不归因、不回滚、不在本单验收。原检查/旧证据未改，未写生产源码或原测试，未联网/部署/采集/GL04/commit/push/reset。

## 按ID验收

| ID | 结果 | 证据/边界 |
|---|---|---|
| G01 | PASS | 10原几何与15主线GL03；全点reference AABB/源中心原义 |
| G02 | PASS | 10过滤索引还原与15 ground逐点min/max/median/source保留 |
| G03 | FAIL | 原错kind/父lidar/记录异常/冲突检查通过；14b完整schema99记录kind缺失/null仍reference有效 |
| G04 | PASS | 14原8m错移修复；14b无参reload及新ID回退状态；15测量/预测坐标分离 |
| G05 | PASS | 12/13/14/14b固定caller、同ID拒绝零副作用、新ID known→unknown、旧track退休、旧事件/源epoch保留、既有生命周期回归 |
| G06 | BLOCKED | 默认分离关闭/旧低卧保留；无可信真实桥接身份，不启用新分离 |
| G07 | PASS | unknown语义/物理flags无升级、合法standalone/legacy回归，无在线背景/深度模型 |
| G08 | PASS | 319主线/2follow、范围/源码SHA/保护资产、py38 AST通过；目标环境实跑NOT_RUN |
| O01 | PASS / BLOCKED | R3独立统计/消融沿用，依赖/数据SHA保持；真实身份/单帧根因BLOCKED |
| D01 | NOT_RUN / BLOCKED | 无目标环境/完整真实场景证据 |

## 12行矩阵

| 入口/状态 | 结果 | 证据 |
|---|---|---|
| 无标定/legacy/source-only | PASS（既有合法形态） | 10/13/15；完整损坏记录伪装legacy例外归G03 |
| 正常full artifact+ground+reference | PASS | 10/11/15 |
| 损坏/版本/frame/parent | FAIL（输入分类） | 12/13/14原例通过；14b schema99+无/null kind泄漏 |
| 采样/非法点/范围/background/索引 | PASS | 10/15 |
| wrapper/node/replay | FAIL（pure helper完整父分类）；正常节点/回放PASS | candidates_from_cloud透传build_snapshot；node/ROS显式artifact本来经完整validator，正常路径15通过；未声称真ROS实跑 |
| locked当前实测state/candidate | PASS | 15 GL03 |
| reference优先后occluded | PASS | 14 before/after x均1、source相同；15预测几何 |
| unselected/release/lost/ambiguous/stale/invalid/monitor | PASS | 10/14/15既有状态 |
| 同/新标定reload/恢复 | PASS | 12/13/14/14b；无参reload冻结、新ID退休track/旧事件与epoch保持 |
| 无可信支持/disabled | PASS（保守关闭） | 当前未开启分离/物理资格 |
| 可信桥接新分离/完全近地 | NOT_RUN | 没有启用新分离，旧低卧回归通过，不称分割验收 |
| ROI/pool/无空场 | PASS（诊断）/BLOCKED（物理） | R3独立O01与当前数据SHA，无身份/空场新宣称 |

## 已闭合与唯一剩余根因

R4-A已闭合：startup持有standalone输入深拷贝；reload先解析prospective有效绑定，同时比较声明canonical和实际有效绑定；任何赋值前拒绝同ID变化。14_context_checks原4方法通过，打印before/after均 `[1,-2,.7]`，source均约 `[2.006022,.094090,-.495816]`。14b独立无参reload、caller旋转/平移修改无效、新ID known→unknown退休旧track通过，不再报G04/G05失败。

G03分类遗漏：取由构造器生成的**完整artifact**，保留units/created_at_utc/status/verification/rotations/input/ground等完整产物字段，令schema_version=99，再分别删除kind或置null。build_snapshot仍输出非空center_reference_m。它不是现有旧最小摘要fixture。日志14b_closure_checks两个子例FAIL（exit1），其他reload检查通过。

来源是固定G03“损坏/newer版本不能假成功”及R3–R5“完整父严格资格、旧最小摘要兼容”。不是提高新门槛。当前只按kind值决定是否验证，缺失/null被放入legacy，使不支持schema99绕过完整validator。上一轮修显式错误字符串kind，仅修一个分支，未定义legacy的正向形态。

责任：Codex原计划虽写“最小摘要”，却没有将其结构与完整artifact区分，也未事前提供kind缺失/null+完整schema99组合。实现者遵照了不够完整的分类设计；本次不能直接归为模型能力不足。先补分类规则和固定反例，不再继续按kind单值零散修补。

## 命令证据

run_review.py日志均有实际argv/退出码，Python3.12本机 `-B -W error`：10原9方法、11原4、12原10、13实现者8、14原4均exit0；14b新增3方法exit1（一个分类方法的2子例FAIL，其余2个生命周期方法PASS）；15主线319、16follow2 exit0。19_final_verify exit0，py38 AST仅静态证据。

沿用不受影响UI/O01：保护UI65文件范围核对、R3独立O01输入/依赖仍适用；没有重复运行旧统计脚本覆写报告。未因回归总数通过而宣称软件整体PASS。

下一步仅收敛G03分类，保留G04/G05和其余已过证据；详已审PLAN_REVIEW。手动实施入口为docs/human_fall/AI_PROMPT_GL03_OPENCODE_R6.md；不自动启动任何实现会话。
