# GL-E01 原始录制证据恢复与主线输入核验 / 唯一验收v1

状态：GL-E01 R1来源链/软件取证独审PASS / STOPPED；B02 BLOCKED、D01 NOT_RUN、D02 BLOCKED，整单未ACCEPTED。见evidence/2026-10-04_mainline_evidence_r1/17_CLOSEOUT.md。
2026-10-04 用户“继续与推进主线”授权已有录制的只读恢复核验；不启动新采集/部署/driver或网络配置/GL-05。仅新evidence/2026-10-04_mainline_evidence_r1审计与允许状态文件；旧源码/输入/旧证据冻结。Codex单证据实现者，完成停写后指定Go Flash/defaultDB独立复核。GL-I05既有软件PASS不返工；本表不复制其软件判据。

| ID | 要求来源与可观察预期/负例 | 检查/证据 | 结果 |
|---|---|---|---|
| A01 | GL-I05 B01；指定原bag存在、ROS bag v2头、首尾SHA实际一致且等于meta的声明，错误/外国bag拒；不是只信声明字段 | 02/03 board只读观测、metadata声明比对 | PASS（指定独审） |
| A02 | B01原layout；独立解码原PointCloud2字段/offset/datatype/count/endian/point_step/row_step；全89frame逐header/点数/offset/丢点/序号/bag time与meta一致 | 原26字节→canonical28字节独立重建，逐帧表；畸形字段/行padding等拒 | PASS（指定独审） |
| A03 | B01完整来源链；原bag独立canonical byte hash等于本地points.bin实际SHA，逐帧hash与canonical XYZ hash等于bin及已批准NPZ；不修改原input_manifest里的历史未核字段 | 本机meta/bin/NPZ实际比对；同计数异内容/hash/帧alias/错绑定拒 | PASS（指定独审） |
| A04 | 时钟契约/不虚报；float64@18→float32@20有损量化明确输出数值误差/范围，不推断单位/硬件同步，不沿用未验证微秒精度说法 | 原始实际量化误差、独立手算浮点负例 | PASS（指定独审） |
| A05 | GL-I05 B02；录制时SDK配置/日志只能有时间和source/run绑定才算证据；当前文件/9月30日志/mtime/模型法向不得代替，缺项unknown | 指定目录有限检索、SHA/mtime/摘录来源与不足表 | PASS（指定独审） |
| S01 | WORKFLOW；先诊断与全树baseline，只新审计脚本/证据及状态，board只读命令/不发布话题/不写配置/不捕获；停写后实际指定二审+首尾SHA | 原始command/exit/model/session、冻结比对、Python3.8 AST | PASS（指定独审） |
| B01 | 本次链路核验仅原bag→提取bin→适配NPZ来源，所有A01–03通过并独审后可记该链PASS；不等于地面/人体/单位标定物理PASS | 证据链最终结论 | PASS（仅来源链） |
| B02 | 保留录制外参/source-world-up/点云原点高度/四box地面身份缺口，缺独立证据不解除 | A05边界 | BLOCKED |
| D01 | 设备跌倒算法/真实性能/安装测量/部署/新采集均未执行；board只读文件取证另列，不能冒称设备阶段 | scope | NOT_RUN |
| D02 | GL04真实DPR-only环境无控制接口；不以JS覆盖或CSS resize替代，旧V04/C12/M03保持未完成 | Browser当前capability与R7限制 | BLOCKED |

| 行 | 组合与已有ID映射 | 结果 |
|---|---|---|
| Q01 | 正确/缺失/同计数异内容/foreign bag SHA与schema → A01/A03 | PASS（指定独审） |
| Q02 | 原字段/offset/count/endian/rowstep/全frame/times → A02 | PASS（指定独审） |
| Q03 | 89帧映射/alias/乱序/header变化/本地bin篡改/NPZ身份变化 → A02/A03 | PASS（指定独审） |
| Q04 | timestamp保持/有损转换/非finite/单位未验证与header原时间独立 → A04 | PASS（指定独审） |
| Q05 | 当前config/旧SDK日志/录制窗口绑定缺失/有证据 × physics unknown → A05/B02 | PASS（指定独审） |
| Q06 | 只读取证/关闭日志/提交SHA/停写/probe/独审/冻结不变 → S01 | PASS（指定独审） |

不适用ROS热reload/目标锁定/缓存生命周期：本单不改运行时、不创建标定资格，不输出calibration或candidate。文件/source身份/原frame映射不得裁剪。缺陷按本表ID集中反馈，不要求“必找到外参”才能软件证据审计完成。
