# GL-I04唯一验收表 v1 / 2026-10-03

状态：软件独立二审PASS（L01–L06/R01–R06/S01/Q01–Q10）；B01/B02 BLOCKED、D01/D02 NOT_RUN；整单未ACCEPTED。来源：[任务](GLI04_TASK.md)、用户Codex开发/OpenCode二审与研究判断优化计划要求、GL-I03独审及研究反例、WORKFLOW v2。此表是本单唯一判据；不在提示词/回传复制多份要求。现行结果见[收口](evidence/2026-10-03_gl_i04_r1/32_CLOSEOUT.md)/[二审](evidence/2026-10-03_gl_i04_r1/opencode_second_review_01/00_review.md)，仅更新结果，不改变v1判据。

## 软件诊断条目

| ID | 可观察预期 / 负例 | 检查与证据 | 当前结果 |
|---|---|---|---|
| L01 | 新CLI只读已适配NPZ/批准draft/显式config，复用source/frame/manifest成员门；非法schema/frame/units/跨组/坏config拒绝；输出仅独立diagnostic kind，旧目录/文件拒绝覆盖，不生成calibration/ground_derived/生产配置 | CLI正负例、原输入SHA/列表、独占目录/输出；产物不能被当作geometry calibration | PASS |
| L02 | 用明确的active/passive、from/to和源坐标约定说明R·up与R^T·up的条件差异；批准向量与WHAT_IF分开；录制extrinsic未知如实记录；局部PCA法向不自动成为物理真值 | 可手算旋转fixture、原draft字节、actual/conditional/unknown字段；证据身份/时间表 | PASS |
| L03 | 四个原固定box×每个source frame逐帧完整覆盖，空区显式count0/null+reason；保留pooled source row、frame ordinal/seq与frame内row可回溯映射；不跨帧pool fit，不改选择或按残差滤validation | 小型group边界fixture/空帧/alias损坏；实际89帧；sidecar/摘要一致 | PASS |
| L04 | signed residual、全点RMS/P95/support、固定空间分箱/帧间统计正确，非finite/空输入有定义；可視点预算不改变全量统计，显示/统计样本数分开；几何高低尾部不自动定物理身份 | 独立手算fixture、分箱边界/预算子例、source index核查、局部空间图/报告 | PASS |
| L05 | raw冻结fit结果、replay拒绝计数、精炼/保留列表与事后holdout诊断明确来源；不能把早退后手算指标写成fitter执行了验证，也不能以reason=degenerate断言SVD退化或以truncated断言双地面 | positive/negative/ROI-normal三假设与原结果对照，early-return/竞争/真退化合成反例 | PASS |
| L06 | 已有163621上生成可复现JSON/Markdown/source-index数据及至少一份局部空间可核查产物，输入/设置/seed/代码SHA齐；研究与批准数据分层，physical=false，缺证据不阻软件完成 | 实际离线run/命令exit/报告重算；批准draft、capture与GL-I03结果不变 | PASS |

## 独立研究原型条目

| ID | 可观察预期 / 负例 | 检查与证据 | 当前结果 |
|---|---|---|---|
| R01 | 比较冻结baseline和独立prototype时使用同输入、selector、有限抽样序列/seed与阈值；冻结baseline实际输出/关键计数一致；oracle仅对同一已见假设序列定义，不宣称排除所有未见物理假设 | baseline parity、固定fixture/真实研究样本、source SHA | PASS |
| R02 | prototype对每个已见合格假设记录精炼/拒绝/保留/合并/未完成的处理，不能先截掉候选再因最终剩1个清不确定性；相似阈值不称数学等价，需处理非传递相似链与代表漂移 | trace映射、raw→refined→retained计数闭合、链A~B/B~C但A不~C的反例 | PASS |
| R03 | 清晰单平面正例可产生已见搜索已闭合的结果，不得永远unresolved；噪声、多seed/顺序下记录可重复结果与baseline差别，不硬编码真实数据或答案；无改进可诚实结论 | 清洁/噪声单平面、至少3固定seed、输入置换、同次重跑；比较oracle | PASS |
| R04 | close competitor、晚到第二平面、distinct假设不能被merge/更新代表/排序/预算操作掩盖；证据支持竞争时保持未决，支持不足时不虚构完整证据 | 至少单平面/双平面/late/重复/chain五类语义fixture，独立已见假设oracle | PASS |
| R05 | 候选存储、迭代/精炼/trace预算显式受控；无法处理的合格假设或预算不足必须unresolved并给原因，不能清truncated凑PASS；记录最大保留数量/处理数/实际成本，不设未经依据的强性能目标 | cap边界、精炼预算0/耗尽、trace截断与无新输入末态；cost记录 | PASS |
| R06 | 比较结果足以作采用/不采用/需补实验决定；列改进/代价/失败和仍未证明条件；原型只在本单evidence，不接现有core/runtime/候选入口/设备，不宣布真实candidate | experiment ledger/反例/决策说明与scope；不以单个成功case或总tests收口 | PASS |
| S01 | 新生产文件/本单研究脚本范围清楚，旧core/config/GL-I03三文件/批准draft/data/driver/UI/HR/历史证据不变；Python3.8 AST/纯std+NumPy分层；Codex停写后OpenCode实际二审、真实session/model/exit/SHA齐，不伪报服务失败后通过 | 首尾全树含untracked/SHA、相关回归、新负例、独立二审与回传 | PASS |
| B01 | 原bag/layout完整来源链仍不足，报告不升级为原bag物理验证 | 沿用GL-I01–03来源层缺口 | BLOCKED（既有缺口） |
| B02 | 录制窗口extrinsic/世界up在source-frame表达与区域地面身份缺证据，unknown保持unknown；旧零值/模型法向/残差筛选不能代替测量和独立身份 | 时间绑定证据表/条件推导，不设为L/R软件完成前置 | BLOCKED（当前证据未闭合） |
| D01 | 设备/物理/真实性能/部署/采集/网络/GL05未执行 | 本单scope和日志 | NOT_RUN |
| D02 | GL04真实DPR与正式页面不属本单，不由新诊断图闭合 | GL04原独审/边界 | NOT_RUN |

## 操作组合矩阵（此表子行，非第二份判据）

| 行 | 必查组合 | 关联ID | 当前结果 |
|---|---|---|---|
| Q01 | startup：合法adapted+批准draft+显式GL-I03变体；默认/显式冻结标签与setting来源；缺输入/legacy/坏metadata/source/frame/units拒 | L01/L05/L06 | PASS |
| Q02 | 同输入重复新CLI/同路径异内容/新路径；输入篡改和代码SHA变化不能复用旧缓存；caller原地改report或settings不污染下一次；已有out拒覆盖 | L01/L03/S01 | PASS |
| Q03 | 每frame×四固定box；empty/zero/边界indices/跨组/alias；显示抽样预算×全统计；原source映射可回溯 | L03/L04 | PASS |
| Q04 | 批准up/负X假设/数据法向；已知/未知extrinsic；R与逆R方向；同输出不能混approved和WHAT_IF资格 | L02/L05/L06/B02 | PASS |
| Q05 | insufficient早退/角度-height拒/真正退化/真竞争/搜索truncated/validation失败；actual fit与replay/事后诊断分开 | L05/R01 | PASS |
| Q06 | 单平面低噪/高噪×多seed/顺序；baseline/prototype同序列比较，positive不是靠永远拒绝 | R01/R03 | PASS |
| Q07 | close/late第二平面/重复近似/非传递chain×代表替换/排序/cap；真实distinct不能消失 | R02/R04 | PASS |
| Q08 | 候选cap/精炼预算/trace预算耗尽×pending/terminal；未处理合格假设不能在末态升级单平面资格 | R02/R05 | PASS |
| Q09 | 真实既有capture+四box×89frame；可复现结果但无physical与calibration产物；外部共享树差异分类 | L06/R06/S01/B01/B02 | PASS |
| Q10 | Codex提交/停写→≤1min指定model/defaultDB probe→OpenCode只读二审；失败保留，不以助手或自验代替；返工须单writer交接 | S01 | PASS |

本任务是一次性离线CLI/研究程序，无ROS热reload/目标锁定/GL02 lifecycle，相关组合裁剪理由必须写入00_diag；文件内容变更/输出资格/算法候选处理不能因裁剪而漏查。判据变更需版本记录；单纯补反例不改ID/语义。
