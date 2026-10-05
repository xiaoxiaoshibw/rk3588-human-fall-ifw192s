# GL03 R6 独立复审 / 2026-10-02

结论：**软件REWORK，仅G03结构资格FAIL；G04/G05保持PASS。** R6的分类规则与旧反例已闭合，不能把本次失败说成分类修复无效。新结构复审发现父frame标签类型不合法仍投影、旧摘要损坏container泄漏AttributeError、损坏canonical子记录可被standalone fallback掩盖。先按连续失败规则完成[结构资格审查与计划](PLAN_REVIEW.md)，不自动重试/换模型。

## 基线/范围

master / HEAD `49eb7581faabdda031642e04d3ef4ffe75d48331`。00_baseline.json含tracked+untracked、全部提交22_source_manifest源码/checker/acceptance/data匹配。结束20_final_verify源码/历史GL证据/数据仍匹配；65driver/config/UI保护文件未改。R6实际两声明文件变化，node_runtime与lidar_candidates保持R5/R3 SHA，原测试断言及检查未改。

calibration `913cc2df8f87965e9060789394b90a3d41a82b896a14264dc6788a438d50090c`；node_runtime `889ead5e…`；GL03 tests `63eabfd5c1970e2046cb9419f57381815a1621af677d0395d56e30ef426c2a8d`；lidar_candidates `318abc78…`。软链接UNREADABLE:1920表示保留，未触碰。

第一次结束核对19日志保留：范围外service_probe/01_probe_exit.txt在完整文件基线之后被外部流程改动，因此“整个工作区零变化”断言失败；修订审查脚本为记录所有外部差异并仍严格拒绝GL源码/证据/保护资产漂移，产生独立20日志。未改外部probe，不归因；早期18_end_deltas为空，不用于掩盖晚些变化。R5外部human_capture差异保留，不参与本单验收。

## ID结果

| ID | 结果 | 证据/边界 |
|---|---|---|
| G01 | PASS | 10及15全点reference AABB/中心原义 |
| G02 | PASS | 10及15 ground逐点几何/非交换median/源索引 |
| G03 | FAIL | 14b分类旧反例已PASS；14d父source标签数字/bool/list、reference空容器仍投影；坏summary容器错误，坏canonical子记录被回退掩盖 |
| G04 | PASS | 14及14b固定T后source预测无8m错移，当前测量/预测分离 |
| G05 | PASS | 同/新版本、无参reload、caller冻结、known→unknown、无副作用/track退休通过，node_runtime未改 |
| G06 | BLOCKED | 默认不开分离、低卧旧回归保留；可信现场桥接身份不足 |
| G07 | PASS | 合法legacy及普通扩展兼容；unknown/物理flags未升级；损坏记录归G03 |
| G08 | PASS | 当前321主线/2follow、范围/SHA/保护资产/py38 AST子范围；设备NOT_RUN；外部probe差异单列 |
| O01 | PASS / BLOCKED | R3独立统计/消融沿用，源数据/依赖SHA相同；真实单帧根因/身份BLOCKED |
| D01 | NOT_RUN / BLOCKED | 目标环境与完整真实帧/标签未验证 |

## 12行矩阵

| 入口/状态 | 结果 | 证据 |
|---|---|---|
| 无标定/合法legacy/source-only | PASS | 10/13/15及14d合法摘要/扩展 |
| 正常full artifact+ground+reference | PASS | 10/11/15 |
| 损坏/版本/frame/parent | FAIL（类型/结构）；PASS（R6分类及已知原例） | 12/13/14/14b/14d |
| 采样/非法点/范围/background/索引 | PASS | 10/15 |
| wrapper/node/replay | FAIL（共享父frame资格）；正常路径PASS | full validator源标签仅truthiness，node也依赖它；pure resolver旧摘要容器读取未经类型验证。15正常集成回归，未宣称真ROS运行 |
| locked当前实测state/candidate | PASS（合格上下文） | 15 |
| reference优先后occluded | PASS | 14/14b/15，固定T逆变换 |
| unselected/release/lost/ambiguous/stale/invalid/monitor | PASS（合格上下文） | 10/14/15既有状态 |
| 同/新版本reload/恢复 | PASS | 12/13/14/14b与node_runtime SHA不变 |
| 无可信支持/disabled | PASS（保守关闭） | 分离未启用 |
| 可信桥接新分离/完全近地 | NOT_RUN | 未启用新分离；原低卧回归保持，不冒称分割验证 |
| ROI/pool/无空场 | PASS（诊断）/BLOCKED（物理） | 原O01独立证据+依赖/data SHA |

## 剩余共享根因：先分类了，但没有先验证父/摘要的结构类型

既有G03要求损坏记录/frame/parent不能假成功。几何契约的frame名称必须明确；合法构造器使用字符串名称，旧摘要兼容仅保留合法输入，不支持数字或列表作frame名。resolver文档约定不可用返回reason，不能靠裸AttributeError冒充明确资格拒绝。

1. **父frame标签**：完整产物frames.lidar被改为42/True/['innolidar']仍经完整validator通过。validator只检查frames对象与lidar真值，resolver只对isinstance(label,str)的字段做一致性比较，因此非字符串被跳过，产生非空reference。可选reference标签=[]/{}也被当未声明，仍投影。14d的5个标签子例FAIL。
2. **summary container**：真最小摘要frames或transforms='damaged'时，后续`.get`直接AttributeError，无法返回reference_calibration_invalid/unavailable。14d两子例ERROR；这是resolver正常拒绝链遗漏，不宣称已真机复现worker崩溃。
3. **子记录fallback**：summary.transforms.T_reference_lidar='damaged'同时提供合法standalone时，calibration_reference_transform把坏子记录视为无known canonical，resolver随后用standalone成功投影。坏声明记录被当作unknown/absent；14d单例FAIL。合法status=unknown/缺记录回退原义必须保留，不能把所有回退关掉。

以上是同一“父/摘要结构资格”根因，不新增算法要求。完整结构validator不完整，resolver不能以类型检查失败为跳过绑定的理由。入口types→labels→declared child status→record数值→跨记录绑定须串联，而非仅调用validator就自认为资格完整。

## 命令/证据

run_review.py各日志有真实argv/exit（Python3.12本机、-B -W error）：10原9、11原4、12原10、13实现者8、14原4、14b原3均exit0；14c结构矩阵初版exit1，保留；补齐同根因optional reference/子记录fallback后独立14d exit1（6子例FAIL+2ERROR，分类/版本/合法兼容方法均PASS）；15主线321、16follow2 exit0；20_final_verify exit0，AST只是py38语法证据。旧19完整树断言错误保留。

UI/O01不受影响，核保护资产/data/依赖SHA沿用既有证据；未覆写旧统计报告或为凑数量重复检查。

## 审查责任与后续

Codex先前将“完整validator”视为足够严格，未读出父frame标签只检真值，也未对legacy容器和损坏子记录回退做结构矩阵，这是已列入口覆盖遗漏。R6实现正确完成已审分类计划；本次不能直接指责模型能力不足。PLAN_REVIEW已集中核对实际结构消费者与全部类型/缺失/unknown回退规则，下一步只补G03结构资格，不重做分类/G04/G05。不自动派实现、换模型、GL04或设备操作。

结束范围附记：20_final_verify另记录src/human_capture/config/capture.yaml外部变化，属于范围外capture工作流；不影响本轮GL源码/历史GL证据/冻结资产SHA，未触碰。
