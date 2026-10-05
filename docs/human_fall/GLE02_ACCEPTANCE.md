# GL-E02 现场证据包与配平输入准备 / 唯一验收表 v1

2026-10-04 当前R1：SUBMITTED / STOPPED。指定Go Flash/defaultDB独审E01–E06/S01/Q01–Q07 PASS；P01 BLOCKED（独立物理复核），D01 NOT_RUN。[收口](evidence/2026-10-04_gl_e02_r1/41_CLOSEOUT_01.md)/[独审原文](evidence/2026-10-04_gl_e02_r1/36_OPENCODE_VERDICT_02.md)。判据v1未变；用户最新1.1m/约26°下俯已记录为名义安装参数，不自动进入拟合/设备/部署。

| ID | 来源 / 要求、负例与可观察预期 | 检查入口 | 结果 |
|---|---|---|---|
| E01 | 已核原bag/bin/NPZ不改；绑定新来源链sidecar与文件SHA，路径存在不等于身份匹配，同路径异内容/foreign source拒 | GL-E01 sidecar+loader、身份负例 | PASS |
| E02 | kind/schema/单位/from-to/窗口/config/run/代码设置版本明确；坏结构/非finite/不支持版本拒；当前或旧零值无录制绑定保持unknown | 证据schema与绑定矩阵、缺口报告 | PASS |
| E03 | 向下看不等于已测角度；世界up表达在有效source系；光学窗口≠原点；测量来源/不确定度/绑定缺失不补PCA/固定角度/旧height | 测量记录负例、独立来源检查 | PASS（软件） |
| E04 | FIT与至少3独立validation区域人工身份单列；三个validation frame_group互异且不同FIT，空间分布另记；绑定源row/真实成员；重复/跨组/越界/alias拒，不能按FIT残差筛holdout | 冻结selector与独立源索引检查 | PASS（软件） |
| E05 | 只产生pending evidence packet/draft；字段齐全不自动变物理verified或运行标定；缺资料稳定输出unknown/待补清单，不永远以软件错误拒绝合法pending正例 | 输出白名单、缺输入/合法pending/齐全但未审对照 | PASS |
| E06 | 新输出独占；同内容复跑新路径可复现，同路径异内容/同ID异内容/caller修改不复用旧内容；输出不能位于capture/旧证据/生产输入目录 | identity/复跑/防覆盖组合 | PASS |
| S01 | 最多3新代码路径及新本轮证据/状态；单writer先diag、stdlib+NumPy/Python3.8，旧数学/配置/driver/UI/HR/旧证据冻结；自验停写后实际指定独审 | fresh全树SHA、相关回归、原始exit/model/session/manifest | PASS |
| P01 | 现场测量/地面身份/有效source坐标证据实际复核；没有资料就物理BLOCKED，不因E软件PASS闭合 | 人工可追溯证据与独立review | BLOCKED（独立物理复核；安装参数用户已给定） |
| D01 | 本单不运行设备算法/新录制/部署/网络或driver配置；未来需要受控录制时以具体范围执行 | 本单scope/日志 | NOT_RUN（本单不执行） |

| 行 | 组合 / 关联ID | 结果 |
|---|---|---|
| Q01 | startup正确输入/缺文件/坏schema/不支持版本/非finite/单位 → E01/E02/E05 | PASS |
| Q02 | 同内容/同路径异内容/同ID异内容/新ID/caller原地改/已有out/受保护目录 → E01/E06/S01 | PASS |
| Q03 | 当前config/9月30旧日志/10月2窗口/run不匹×known/unknown → E02/E03/E05/P01 | PASS |
| Q04 | 下视未测角/PCA/条件角示例/窗口高度/测量原点/from-to逆向混用 → E02/E03/E05 | PASS |
| Q05 | FIT/validation×源组/row重复/alias/越界/缺身份/有效成员/非法残差筛选 → E04/P01 | PASS |
| Q06 | 合法pending/字段齐全但未审/审查缺项×candidate/physical/runtime禁晋级 → E03/E05/P01 | PASS |
| Q07 | 提交/SHA/停写/probe/独审/检查器新编号/范围冻结 → S01 | PASS |

纯离线证据工具不适用ROS热reload/跟踪状态/缓存；输入/source/版本/输出防覆盖与资格晋级不得裁剪。P1不含实际拟合或runtime接入；P2的真实候选另开表，不把后续指标混入本单。阈值/物理容限先审查定版，不边实现边降低。
