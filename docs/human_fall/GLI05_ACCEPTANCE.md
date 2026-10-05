# GL-I05唯一验收表 v1 / 2026-10-03

状态：GL-I05 R2软件独审PASS / STOPPED。判据保持v1；最终不可变指定二审与收口见evidence/2026-10-04_gl_i05_r2/31_CLOSEOUT.md。B01/B02 BLOCKED、D01/D02 NOT_RUN，整单未ACCEPTED；无writer、不接运行时。R1及原二审过程历史保留。

| ID | 来源 / 可观察预期及负例 | 检查与证据入口 | 当前结果 |
|---|---|---|---|
| C01 | TASK研究契约；ALL/NEAR/BEST_ONLY及三终态明确区分，完整W/所有best ties；NEAR检查全部近优两两关系，middle-best/非传递链不能被best-only吞；弱distinct即便dominant也不能声称全唯一 | 手算支持比/tie/0-6-12°链/弱distinct、独立oracle定义与终态表 | PASS（R2最终独审） |
| C02 | TASK阶段1；冻结baseline、GL-I04原型、新原型/oracle同source/selector/settings/seed/已见序列；原生fit与研究判断分开；旧trace只读有SHA，非法身份/schema/非finite参数拒；actual validation未跑不能伪造 | baseline及replay parity、序列digest、来源/hash/畸形输入负例 | PASS（R2最终独审） |
| C03 | TASK阶段1/2；所有已见合格raw有refine/reject/retained/证明合并/未完成事件，计数闭合；归因实际near-distinct/仅证书不足/预算缺口；不以结果计数或最后剩1清资格 | raw→精炼→证明/保留ledger、计数恒等式、末态回溯 | PASS（R2最终独审） |
| C04 | TASK阶段2；有界实现的闭合必须与独立同序列oracle一致；0/4/8°顺序证书反例正确归因；任何near-pool distinct/chain/tie/晚到竞争保持unresolved；清洁/低噪正例可闭合，不能永远拒；弱distinct正例只可dominant | 手算反例全部排列、≥3seed/输入置换/重复run、oracle差异逐例说明 | PASS（R2最终独审） |
| C05 | TASK阶段2/3；候选/迭代/精炼/trace/证明成本显式受控；未处理合格项和未记录trace不能终态升级，即便晚到高支持best；不足reason保留。若cache试验：依赖身份完整、成员精确核对、有界满回退或拒绝 | 0/边界/耗尽、pending→terminal、早断/无新输入/后到best、资源峰值及反例 | PASS（R2最终独审） |
| C06 | TASK阶段3/5；成本拆sampling/raw/refine/decision/serialization，至少多次本机重复与固定case汇总，cache hit/miss/refine_calls与内存峰值可核查；oracle/trace/holdout阶段不同不能冒称公平端到端加速；采用/不采用/需补实验均有证据 | 阶段计时/预算/缓存对照、归因表/否定假设/决策。cache不采用须有依赖/实验理由，不能留未验证缓存代码 | PASS（R2最终独审） |
| E01 | TASK阶段4；原四box×每源frame固定，不pool fit、不按残差筛validation；frame/box定位产物可核查sourceXYZ/row/ordinal/seq，empty显式；显示预算不改全统计，参考plane来源/WHAT_IF/physical=false标明；非法索引/alias/输出旧路径拒 | 固定box全统计和sidecar对照、frame切换/显示预算、空/损坏与离线空间产物 | PASS（R2最终独审） |
| E02 | TASK阶段4；仅定界已有/新增本地录制资料，时间绑定/配置SHA/from-to/SDK链逐项说明，缺失保持unknown；9月30零值、frame名、模型法向、光学窗口高度不能替代10月2录制证据 | 本地检索边界/增量记录清单/证据表/必要后续资料说明，无资料也可软件PASS但B02不解 | PASS（R2最终独审） |
| S01 | TASK范围/WORKFLOW；只新run_root研究/计划/回传/状态文档，所有生产/GL-I04/输入与旧证据不变；Python3.8 AST/stdlib+NumPy；单writer自验停写→真实指定Go Flash/defaultDB二审，完整manifest/关闭日志hash/会话model/exit/首尾SHA | full tracked+untracked基线/冻结比对、相关回归、来源层、实二审。服务失败不伪PASS、不换model/DB/auth/权限 | PASS（R2最终独审） |
| B01 | GL-I04继承；原bag/layout完整链不足，不升级原bag物理验证 | 既有缺口及新增证据如实分层 | BLOCKED（既有缺口） |
| B02 | GL-I04继承；录制extrinsic/world-up表达/四box地面身份不足；本单局部图和研究搜索不能关闭它 | 时间绑定资料与独立身份；未获得保持BLOCKED | BLOCKED（既有缺口） |
| D01 | TASK范围；设备/部署/新采集/网络/GL-05及板端真实性能未执行 | 本单日志/scope | NOT_RUN |
| D02 | TASK范围；GL04实际DPR/正式页面不由本单闭合 | 原GL04状态与范围 | NOT_RUN |

## 操作组合矩阵（本表子行，非第二份判据）

| 行 | 组合 | 关联ID | 当前结果 |
|---|---|---|---|
| Q01 | startup合法input/oldledger/config身份；缺source/坏schema/frame/units/非法设置；已有out/输入目录拒 | C02/E01/S01 | PASS（R2最终独审） |
| Q02 | 同内容重跑/同路径异内容/新路径/caller原地改points/settings/report；源码/settings版本改变；无旧cache污染和覆盖 | C02/C05/S01 | PASS（R2最终独审） |
| Q03 | ALL与NEAR与BEST_ONLY×best tie/弱distinct/链中间best/0.8边界；完整与budget不足终态语义 | C01/C03/C04/C05 | PASS（R2最终独审） |
| Q04 | 0/4/8°全相似集合×所有首锚/顺序；0/6/12°真正链×middle-best/排序/代表更新，distinct不能吞 | C01/C03/C04 | PASS（R2最终独审） |
| Q05 | 清洁/8mm/35mm/weakdistinct/close/double×3seed/原与置换/同run重复；oracle和旧原型/冻结baseline | C02/C04/C06 | PASS（R2最终独审） |
| Q06 | early弱候选/late强best/late第二平面×完整/早断/精炼0或耗尽/候选cap/trace/证明预算 | C03/C04/C05 | PASS（R2最终独审） |
| Q07 | 相同sample-inlier mask/不同mask/只hash相同但成员不同×up/height/fit_rows/sample/settings/source/implementation变化×cache满；不采用cache也需依赖审计及未缓存对照 | C02/C05/C06 | PASS（R2最终独审） |
| Q08 | 每frame×四box×empty/边界/alias/跨组×显示预算/研究plane标签；原映射/全统计不变 | E01/E02/S01 | PASS（R2最终独审） |
| Q09 | approved/negative-X/FIT法向研究×原录制时间/旧零值/未知extrinsic；无法由图与候选判断身份；共享树新增/修改分归因 | C02/E01/E02/S01/B01/B02 | PASS（R2最终独审） |
| Q10 | 提交/关闭日志/完整manifest/停写→一次≤1min指定model/defaultDB无工具probe→只读二审；失败保留；返工先明确单writer交接 | S01 | PASS（R2最终独审） |

本单无ROS热reload/GL02锁定生命周期，裁剪原因必须记00_diag；文件身份/算法pending→terminal/缓存版本组合不得裁剪。缺陷与新研究契约分开；补反例不变ID，语义变更要版本/来源/影响记录。C类软件结果不改变B/D层。
