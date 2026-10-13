# HR-SKELETON-OFFLINE 交付复审

**SUBMITTED / BLOCKED，未ACCEPTED。** 单writer本聊天Codex；没有外部审阅者/代理签署。用户2026-10-09明确授权A–F PC离线实施，后又确认真实sidecar“无”。本轮完成可独立执行的工具、审阅与证据工作；真人粗节点阳性及效果验收尚未闭合。

## 1. 实际工具与节点能力

bind_inputs.js只读核R2交付及传递导入，再调用authority/source/receipt；从指定R1完整成员和raw28B建立120帧审阅数据，不运行历史main/prepare/run。CONTRACT/params-v1在首算法前冻结，绑定错误修复后只更新源码冻结记录freeze_r2/r3，参数与节点规则SHA始终不变。最终freeze_r3和pass5/pass6为交付口径，早期失败/冻结/运行均保留。

skeleton.py实现全部有效成员纯XY标准化、原Z和一一row/global映射、无符号PCA描述、5固定槽和有分离支撑的A/B。合成合法形状有7个有效区域代表，胸中心[10,20,1.05]及rows32–47可独立手算；逆变换误差0m。HEAD仅在人工独立标明HEAD_CONFIRMED区域时取支撑中心，是条件化区域代表，未实现自主头部检测。固定Z带仅直立片段工具默认值，真人开发标定因GT阻断，不声称从真实开发数据优化过。

独立SkeletonTracker使用参考坐标滤波、实际整数stamp差值，EMA/跳变/当前缺失/重新获得及键/seek清理；不改原human Tracker、3/5、EMA、lost或Fall。缺支撑时raw和当前filtered为null，历史单列。真实输出120行/文件、336成员的1680基础槽全部无效；真实normalized=null且BLOCKED_GT，不拿空输出当阳性能力通过。

## 2. 修改范围及原因

仅本轮新evidence内新增工具/契约/派生帧/测试/页面/报告，另追加returns/HR-SKELETON-OFFLINE.md。record.py负责新轮基线、实际运行日志与旧资产；bind_inputs.js负责可信入口与GT校验；skeleton.py/run_offline.py负责独立几何和受控运行；test_skeleton.py/binding_tests.js/review_tests.js/independent_audit.py负责明确正负预期与独立复算；review.html/review.js/review_config_final.js/serve_review.py负责只读本地审阅和sidecar；closeout.py负责清单与记录。完整文件SHA见delivery_manifest.json，范围与源摘要见changes.json。

没有src/pc_apps/webui/captures/ML/旧limb/旧evidence/冻结门变更，没有生产接入或安装artifact，未连接板端、部署、采集、commit/push/reset/checkout/clean。WD02未消费，额外历史代码相等检查未删除或绕过；原SEM/W03/HR-RET-V2表与状态不变。

## 3. 测试、实际失败与复审方法

最终15 Python数学/生命周期测试、20绑定/区域正负检查、6 headless审阅契约检查全部exit0；相关replay45、pipe38、registration23回归exit0。实际浏览器12项显示/切帧/空场/非法row/摘要/保存门检查，并额外验证人工声明门；headless与真实浏览器分列，不伪称标签为人工GT。Python3.8语法检查通过；实际运行Python3.12.10/NumPy1.26.4，Python3.8实际执行NOT_RUN。

首次binding exit1：误用R2未导出的R辅助函数；修复新包装。binding_r2 exit1：空场实际分支名V2_IDENTITY曾误写V2；保留split_attempt_r2和binding_r2_partial_frames后按原计划正确分支重建，没有改变窗口或样本。首次binding_tests exit1揭示新输入摘要比较多做了一次字符串哈希；直接比原文件SHA后重验通过。其余冻结是增加区域负向检查/重复person-frame防护，参数未变。浏览器隔离环境拒绝访问纯导出函数，不绕过；导出数学/绑定用明确合成headless入口检查，真人合法导出未执行。一次编辑命令的PowerShell解析失败无文件写入，随后用单引号here-string完成新页面清理修复。

独立复审不导入算法或R2校验器：struct原始字节、标量矩阵逐步骤f32复算全部871476坐标、336完整簇global/票据；独立原点判断184125无效成员；独立重算合成support中位数/逆变换，显式胸中心及rows预期。pass5/pass6 normalized/raw/filtered三个实际文件摘要逐项一致。没有第三方签署，真实节点正确性不由工具PASS证明。

## 4. GT、分母、节点效果与成本

| sid / branch | 计划帧 | 簇 | 全成员 | 原无效成员 | 已审PERSON | 无簇行 |
|---|---:|---:|---:|---:|---:|---:|
| cap_20261008_114205/REF_SHADOW | 20 | 44 | 67776 | 0 | 0 | 0 |
| cap_20261008_114254/REF_SHADOW | 20 | 60 | 73413 | 0 | 0 | 0 |
| cap_20261008_114340/V2 | 20 | 60 | 45765 | 0 | 0 | 0 |
| cap_20261008_114422/V2 | 20 | 60 | 51897 | 0 | 0 | 0 |
| cap_20261008_114819/WORKSPACE | 20 | 112 | 632625 | 184125 | 0 | 0 |
| cap_20261008_114819/V2_IDENTITY | 20 | 0 | 0 | 0 | 0 | 20 |

100唯一原始帧、120分支行不能报成120独立样本；全部已观察过，不称盲测。336簇真实身份/节点reviewer=0，各基础节点可见/不可见/不确定标注均0、未审336、valid0、UNKNOWN336；合计1680槽观测不是1680独立帧。20 V2_IDENTITY无簇行无节点槽，依然保留行分母。空场两分支40行当前0有效PERSON节点是无人工输入下的拒绝纪律，不是自动人体零误报率证明。

真人躯干阳性、头/手判断、区域参考误差、已标可见漏检、真实跳变/延迟/缺失恢复全部BLOCKED_GT。不存在精确关节GT，不报告关节精度；躯干工具合成成功不代表头或四肢成功。详见pass5/metrics.json、coverage_by_branch.json与GT_TASKS.md。

拒绝/状态路径的PC每分支行中位耗时 0.000051s、最大0.000215s（不含绑定SHA与raw IO），只是拒绝路径成本；真实人体几何代价、板端性能NOT_RUN。实际整次命令runtime见COMMANDS.md和*.run.json。

## 5. 完整性与逐项状态

旧6299路径逐SHA/大小/符号链接/既有缺失状态复算无变化，branch/HEAD不变，范围外新增0。return原字节前缀在追加时与最终prefix_check再次核验。原冻结输入、旧证据和验收表未漂移。完整性见integrity_final.json、05_integrity.md、prefix_check.json；新交付SHA见delivery_manifest.json。

| ID | 状态 | 实测证据与限定 |
|---|---|---|
| SKO-01 | PASS | 6299旧路径/44,460,273,500字节基线；branch/HEAD不变；用户本轮明确离线授权 |
| SKO-02 | PASS | R2全部交付SHA/传递导入、固定TLS与诊断矩阵核对；独立raw复算336簇/871476坐标/票据 |
| SKO-03 | PASS | 100唯一raw帧/120分支行；336未审簇/20无簇行全部保留；固定按会话划分，不称盲测 |
| SKO-04 | BLOCKED | 真实reviewer/PERSON/连续person_id=0；两个开发sid各3连续实际帧门未满足，用户回复无 |
| SKO-05 | PASS | CONTRACT/params-v1在首算法前冻结；参数SHA三次源码冻结间未变；无验证调参；真人参数标定BLOCKED |
| SKO-06 | PASS | 纯XY平移、全有效成员/原Z/row保存；synthetic独立逆变换0m≤1e-5；真实PERSON标准化BLOCKED |
| SKO-07 | PASS | 完整raw/member/global映射独立核验；20绑定/节点区域挑战；synthetic合法节点support独立重算；真人支撑BLOCKED |
| SKO-08 | PASS | 空、非有限/原零XYZ、低支撑、家具/MIXED/UNKNOWN拒绝测试；184125无效源成员已定位，无上游重聚类 |
| SKO-09 | BLOCKED | synthetic真实形状数学正例产7节点，真人可见躯干正例没有GT；不得用全拒绝算阳性通过 |
| SKO-10 | BLOCKED | synthetic头/手和缺头拒绝PASS；实际举手窗口HEAD可见性未标，不验证真实头能力 |
| SKO-11 | BLOCKED | PCA退化/符号UNKNOWN、单下部/双A-B synthetic PASS；真实分离/朝向GT未闭合 |
| SKO-12 | PASS | 独立SkeletonTracker；实际整数stamp/dt；重复/倒退/seek/缺帧/换5类键/恢复/跳变实测；原Tracker/Fall无变化 |
| SKO-13 | PASS | 实际浏览器12检查+人工声明门；完整簇/row拾取/切帧/空场/篡改清状态；headless 6合成导出绑定检查另列；真人导出未发生 |
| SKO-14 | BLOCKED | 逐节点336未审/valid0/UNKNOWN336；1680槽观测；区域误差、真人跳变/恢复和精度均BLOCKED，无伪造正确率 |
| SKO-15 | BLOCKED | 固定验证/举手/空场拒绝流程运行；40空场分支行0有效PERSON节点；隔板/举手真人效果因GT缺失BLOCKED |
| SKO-16 | PASS | 独立struct+标量变换复算raw/票据，synthetic显式胸中心[10,20,1.05]/support/逆变换；最终pass5/6三个数据SHA相等 |
| SKO-17 | PASS | Python -B -W error；15 Python+20绑定+6审阅工具检查；replay45/pipe38/registration23回归exit0；旧资产SHA无变化，最终return前缀另核 |
| SKO-18 | PASS | 本轮工具/GT/效果/资产/失败/停止报告齐全；ponytail实读路径；SUBMITTED/BLOCKED，未ACCEPTED，无代理或下一阶段 |

## 6. 后续建议及停止点

下一项数据工作是实际人工审阅：114205 ordinal112–114、114254 ordinal125–127优先逐完整簇确认reviewer/连续person_id/epoch，并标至少一个躯干可见区域和真实缺失/拒绝对照；其余全部未审继续保留。完整336待审receipt、每帧来源/成员SHA与URL在gt_pending.json；frame_index.csv含全部120行。导出实际sidecar后在另获授权新轮先复核绑定，再做真人节点阳性与固定验证；旧轮禁止覆盖。

正式W03未冻结/W04/W05未放行、WD02 BLOCKED不因本单改变。弯腰、坐蹲、躺卧、多人、真实跌倒、完整四肢、精确关节、W06/W07/生产/ML/设备/物理均NOT_RUN/BLOCKED。测试只在127.0.0.1:8883，服务已核进程身份并停止。现在交付后停止，不自动进入后续阶段。

ponytail实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）；没有自动派代理/OpenCode或更换模型。
