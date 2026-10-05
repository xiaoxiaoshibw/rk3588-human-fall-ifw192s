# GL-03 R4 独立复审 / 2026-10-02

结论：**软件REWORK，G03/G04/G05仍FAIL**。原R3反例已闭合，R4正常路径和回归通过，但reference父资格及standalone reload存在同根因遗漏。按连续失败规则先完成[计划/根因再审查](PLAN_REVIEW.md)，再提供单一[手动R5工单](../../../AI_PROMPT_GL03_OPENCODE_R5.md)，不自动启动、不换模型、不启动GL04。

## 基线与范围

master / HEAD `49eb7581faabdda031642e04d3ef4ffe75d48331`。`00_baseline.json`涵盖tracked与untracked文件；Windows `src/CMakeLists.txt`保留UNREADABLE:1920，不替换软链接。提交17_source_manifest的全部source/checker/acceptance/data SHA匹配；审查结束仍匹配（`19_final_verify.txt`），完整审查基线变化为空（`18_end_deltas.json`）。R4三声明文件变化与提交scope一致；driver/config/UI共65个保护文件与R3独立基线一致。未写生产源码/原测试/旧证据，未部署/采集/联网/commit/push/reset。

当前源码：calibration `a2d06194248dfeee404fa9ec412d295876dd9318c26850540e800737a070ac24`；node_runtime `9bd65ff9adf82b520cb588d234cb75b69418a25febb7b2e7b6ef124aec3e15b8`；GL03 tests `1e7edb6b72b6ff8ad356231988524fdfd568856f28edcda3747feabc6072842b`；lidar_candidates仍`318abc78…`。当前314主线回归包含R4新增八方法，不恢复支线六用例。

## 验收ID

| ID | 结果 | 证据与适用边界 |
|---|---|---|
| G01 | PASS | `10`原几何检查及`15`GL03非零R/t、完整reference AABB/源中心原义 |
| G02 | PASS | `10`实际点/过滤索引；`15`ground min/max/median与source不变 |
| G03 | FAIL | 原损坏记录/父schema/ID/启动冲突通过；`14`损坏kind绕过父验证、父lidar和T.from不一致仍投影 |
| G04 | FAIL | 正常locked/occluded/新版本通过；`14`standalone caller修改→同IDreload→occluded，source错移8m |
| G05 | FAIL | canonical同ID拒绝无副作用/新ID/正常caller修改通过；`14`reload重新读取raw caller，在changed=false时换有效绑定 |
| G06 | BLOCKED | 默认不开分离、旧接地/低卧行为保留；可信真实桥接身份不存在，条件性新分离未执行 |
| G07 | PASS | unknown语义/物理flags不升级；legacy正常支持；损坏reference父例外归G03 |
| G08 | PASS | 当前回归/范围/提交SHA/冻结资产/py38静态解析通过，目标运行NOT_RUN；不能抵消G03–G05 |
| O01 | PASS / BLOCKED | 沿用R3独立18_o01_audit；依赖lidar_candidates、源pool/ROI/planes及提交报告未变。探索性统计/成员通过，真实单帧根因/身份BLOCKED |
| D01 | NOT_RUN / BLOCKED | 无板端目标环境/完整真实帧及身份标签验证 |

## 12行入口/状态矩阵

| 入口/状态 | 结果 | 证据 |
|---|---|---|
| 无标定/legacy/source-only | PASS | `10/13/15`原legacy与合法standalone |
| full artifact+ground+reference | PASS（一致正常输入） | `10/11/15`完整逐点几何 |
| derived/父版本/frame/parent异常 | PASS（原derived/scheme/ID）；FAIL（reference kind/父lidar） | `10/12/13/14` |
| 采样/非法点/范围/background | PASS | `10/15`索引还原与HF04 |
| wrapper/node/replay | FAIL（reference共享链） | candidates_from_cloud透传build_snapshot，node调用同helper，pipeline/replay正常回归`15`；完整父资格在resolver漏。未声称真ROS运行 |
| 当前locked实测 | PASS（正常上下文） | `15`GL03 state/candidate一致 |
| reference优先后occluded | FAIL | `14`standalone reload错误逆变换；`12/15`原正常路径通过 |
| unselected/release/lost/ambiguous/stale/invalid/monitor | PASS（绑定未改变） | `10/15`既有状态与monitor回归 |
| 同/新版本reload/恢复 | FAIL（standalone分支）；PASS（canonical正常分支） | `11/12/13/14/15` |
| 无可信支持/disabled | PASS（保守关闭） | 分离未启用、O01决定沿用 |
| 可信synthetic桥接/standing/contact/lying/完全近地新分离 | NOT_RUN | 未启用新分离；旧低卧保留回归通过，不冒称分割效果通过 |
| ROI/pool/无空场 | PASS（诊断）/BLOCKED（物理） | R3独立O01及当前数据SHA，未新增无人空场或真实身份 |

## 集中剩余根因

### R4-A：只固定返回绑定，reload仍从raw caller读；比较的也仅是canonical记录（G04/G05）

来源：G03 caller/不混版本、G05同版本保持绑定；R4 F3“快照与prediction消费同份固定绑定”；计划操作表“caller修改不是reload授权”。

`node_runtime.py:373 self.transform=transform`仍保存外部活引用；`:460 _resolve_reference_binding`在无known canonical时每次读取self.transform。`:563`同ID拒绝只比较父canonical记录，不比较本节点实际有效的standalone绑定。

有效fixture：完整artifact reference=unknown，合法standalone T.x=1，正常select/locked；caller原地把T.x改9；调用`apply_ground_context(calibration=deepcopy(原artifact))`，没有传入任何新reference。返回changed=false，却将有效T.x从1换9。随后有效时间的空候选帧，旧track reference被新inverse解码：source x `2.0060224766` → `-5.9939775234`，差8m。`14_context_checks.txt`打印全部前后数值。

预期：普通same-ID reload继续固定原standalone绑定，或在任何副作用前明确拒绝；不能把caller改动重新采纳。canonical同ID拒绝无副作用独立检查已PASS，修复该兄弟分支不能破坏它。

### R4-B：父完整产物与legacy分类/跨记录源绑定仍漏（G03）

来源：G03损坏/parent/from-frame不一致不能假成功；R4 F1完整父严格资格同时保留**无kind旧最小摘要**。

`calibration.py:331`只有kind恰好合法才调用完整validator。将完整artifact kind改为`unsupported_geometry_calibration`后，它被当legacy而投影；现有validator本来明确拒绝该kind，并非缺新契约。不能把“无kind最小摘要可用”扩大成“任意错误kind完整artifact免验”。

`:356`只将T.to绑定frames.reference，不把T.from绑定父frames.lidar。将合法完整父的frames.lidar改other_lidar，T.from与实际输入仍innolidar，仍给reference坐标，父源上下文与消费变换矛盾。`14`两反例FAIL。严格构造器R/t通过只证明数值合法，不证明跨记录一致。

保持真实legacy摘要及合法standalone，不借修父资格强制所有旧摘要补齐完整artifact，也不新增schema。

## 独立命令与结果

运行器`run_review.py`，各日志头记录实际argv，尾记录退出码；本机Python3.12，`-B -W error`：

- `10_prior_geometry.txt` R1原九方法 exit0。
- `11_prior_reference.txt` R2原四方法 exit0。
- `12_prior_failures.txt` R3原十方法 exit0。
- `13_worker_checks.txt` R4实现者八方法 exit0。
- `14_context_checks.txt` 新四方法exit1：三个FAIL，canonical拒绝无副作用PASS；没有修改旧反例。
- `15_fall.txt` 当前主线314 exit0（GL03 42/GL02现有回归在其中）。
- `16_follow.txt` follow2 exit0。
- `python -B -W error .../codex_review_01/final_verify.py` → `19_final_verify.txt` exit0；py38 AST通过不是板端实跑。

未重跑已SHA未变的UI/O01来凑测试数；相应先前证据和R4原始日志保留。停止使用总数作为PASS判据。

## 责任与后续

实现者已修原反例，但方案只拷贝resolver返回值、只比较canonical记录，未固定所有reload输入来源。Codex上一轮事前反例没有覆盖“unknown artifact+standalone+caller修改+same-IDreload+occluded”这一操作组合，分类检查也漏错kind/父源标签。这是已列规则的覆盖遗漏，责任已在PLAN_REVIEW记录，不能称用户新增要求。

下一步先按已审单一上下文来源方案修订集中设计，再单写入者实施；不自动同文重试。模型能力不足仍未证实。设备/数据限制不是本次软件FAIL的原因。
