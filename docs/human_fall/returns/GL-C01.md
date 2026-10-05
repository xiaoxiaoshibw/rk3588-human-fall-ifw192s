

## GL-C01 当前小点 / R1 / Codex / 2026-10-04T19:20:07.145809+08:00

- 状态SUBMITTED / STOPPED；唯一GLC01_ACCEPTANCE.md v1；未指定独审，不称软件独审PASS或ACCEPTED。
- 用户最新明确“这一个小点做完先停下来”，完成联合反解+必要自验/落档后停，不派新probe/Go/后续优化/接入/部署。
- 基线master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6；01全tree tracked/untracked/ignored，18保护对照/源码SHA。原99meta/bin当前实际SHA再次匹配03，旧89获审链未冒用。
- ponytail实际路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。

### 诊断与最小实现

继承Rx@Ry、冻结点集和模型估计/测量分开。修正外部pool/重新按rectangle分区/trim validation/各区self-fit代替共同FIT的口径。单FIT TLS平面闭式pitch/roll/tz，固定三验证frame所有选定行，与原指标子集对照。无IRLS、无运行时资格、无measured height覆写。00完整操作矩阵、20完整根因/限制。

| 文件 | 与原差异区分 | SHA |
|---|---|---|
| src/human_fall_detection/tests/test_joint_leveling.py | 本轮新增联合反解/CLI/集中tests | 8197db69bf03cde22068bbdefb519b8b05b8cae6c8a7a657e823a3673e0036c7 |
| src/human_fall_detection/core/joint_leveling.py | 本轮新增联合反解/CLI/集中tests | 751ef7a8c4cdb47d18966cce404e9e43c054057d3e4c0a5ab0276593785ab046 |
| src/human_fall_detection/scripts/fit_joint_leveling.py | 本轮新增联合反解/CLI/集中tests | cb7e35ac04a323d28e9229f1b76064e8efbf4f9ff4198307bb4dd199d0bba69a |

### 逐ID作者自验

| ID | 层 | 命令/入口 | 结果 | SHA证据 |
|---|---|---|---|---|
| C01 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| C02 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| C03 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| C04 | offline | 05/14/15/09/12/13与20逐ID | PASS（软件自验；真实质量FAIL） | 18/19 SHA |
| C05 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| C06 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| C07 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| S01 | offline | 05/14/15/09/12/13与20逐ID | NOT_RUN（按用户完成小点后停，独审未派） | 18/19 SHA |
| P01 | offline | 05/14/15/09/12/13与20逐ID | BLOCKED | 18/19 SHA |
| D01 | offline | 05/14/15/09/12/13与20逐ID | NOT_RUN | 18/19 SHA |
| Q01 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| Q02 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| Q03 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| Q04 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| Q05 | offline | 05/14/15/09/12/13与20逐ID | PASS（作者自验，未独审） | 18/19 SHA |
| Q06 | offline | 05/14/15/09/12/13与20逐ID | NOT_RUN（按用户完成小点后停，独审未派） | 18/19 SHA |

14新增5、15fall458 exit0，10/16 AST3.8；此前B follow2不变仍适用。09真实CLI exit0且quality FAIL；13 existing out exit2；12全2318行scalar差4.44e-16、before/after正交res不变6.67e-16。冻结frame0 FIT528，frame33/66/98 val890/276/624。数据估计pitch26.314310°/roll-0.612061°/tz1.323137m；pick01/02 P95=.050762/.057539m未过.05，RMS均过.03、pick04 PASS，完整失败保留。未运行原fitter搜索竞争全套/独立测量，仍candidate/physical/extrinsics/runtime=false。

输入异常：原accumulator第13行相邻字符串不是合法JSON，初次07真实CLI缺selection exit2保留；03明列AST.literal_eval仅提取已读Python PICKS常量，不执行源脚本，不导入ALL_GATES_PASS旗，不改旧JSON。04为新严格冻结行JSON，09新路径成功。core源码01/02、CLI02、test02/03版本保留。11 PNG实际可视，原外部脚本/报告/数据只读。

### 未闭合与停写

模型值不等于仪器安装测量，roll与地面坡度不可辨；99原bag链仍metadata_declared，精确ground行/SDK/物理精度P01 BLOCKED。软件失败与数据质量失败分列，不为转绿删点/换局部val模型/放宽门。S01/Q06独审阶段NOT_RUN依据用户最新停写要求；19_manifest/20收口/本return已落档，停止全部源码写入与自动后续，不启动设备/采集/生产/部署。



### 当前停写补记 / 新编号scope与manifest

18首scope发现外部PC console/human_replay九个既有文件并发变化，原assert失败保留；24_scope_exception_02按明确路径记录首尾SHA及外部归因，HF/GL源/配置/driver/原99数据无漂移，root不改不回滚外部文件。此前回传引用19_author_manifest_01未形成（scope assert后未到manifest）；当前以25_author_manifest_02和27_final_stop_record_02为准，失败历史保留。当前三源码SHA与18/10/16相符、source meta/bin actualSHA再核相同。用户要求小点完成后停，独审/probe未派，无新优化/接入/部署。