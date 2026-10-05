# GL-I04 R1 Codex开发提示词（可直接执行的主提示）

工作目录D:/Code/ldiar。任务准备于2026-10-03；本轮用户只要求任务与提示词，因此本文件尚未被执行。用户在后续开发聊天明确要求按本提示开始后，按下述范围研究、开发、迭代、二审。若跨日，新运行证据建当天目录，只更新入口引用，不搬移/覆盖本目录规划或历史证据。

## 你的角色与工作方式

你是Codex主研究/主开发/编排者，当前唯一生产writer；OpenCode CLI opencode-go/deepseek-v4.1-flash/defaultDB负责独立二审及交接后的范围内返工。最新用户授权覆盖旧“Codex不能写源码”。先完成具体可审提交，停写再交二审，不并行写入，不用OpenCode服务失败阻断本地Codex开发。二审派前一次≤1min无工具probe；异常分流BLOCKED，不换model/DB/auth/权限/全局配置，不把自验或助手当它已审。

必须理解目标再按ponytail最小实现；每个实际writer先完整读SKILL.md并记路径。Codex源C:/Users/30680/.codex/skills/ponytail/SKILL.md；OpenCode使用native skill(name=ponytail)，不读取曾被拒的外部目录。

边执行边提出可推翻假设、设计区分性实验、归纳结果、调整计划。不要机械重跑GL-I03、不为新负例伪造新需求、不靠阈值放宽/删竞争证据换PASS。先在00_diag简短写目标、实际调用链/赋值和资格门、矩阵映射、实验和最小文件范围，再直接开发；不为例行计划增加用户确认仪式。确有改变批准物理值或生产接口的必要，先完成能独立做的证据与具体改动提案，不能悄悄替换。

## 必读（当前事实源）

1. docs/human_fall/WORKFLOW.md v2的最新角色/结果覆盖和流程正文。
2. GLI04_TASK.md、GLI04_ACCEPTANCE.md v1（本单唯一判据，不复制另表）、RETURN_TEMPLATE.md。
3. GL-I03 evidence/2026-10-03_gl_i03_r1/32_CLOSEOUT.md 与research_01/27_PLAN_REVISION.md、31_EVIDENCE_AND_NEXT_STEPS.md。
4. 实际core/capture_input.py（loader/selector/member map）、core/ground.py（sampling/RANSAC/refine/competition/validation）、GL-I03 wrapper/config、新旧相关tests。按调用链读，不拉取全部历轮/无关原始CLI输出。

## 恢复基线与已知反例

开始时记录live branch/HEAD、全tracked+untracked工作树/SHA，确认无另一个本单writer。不要reset/checkout/clean/commit/push/替用户提交。已审锚点master/cbd0be1c86a1051a9a5800dfb7263f842896e1e6；后续外部HEAD/文件变化先查源分类，保留合法用户差异，不能用reset恢复旧锚点或mask不符。

必须保护当前SHA：

- GL-I03 wrapper fddeeee0b4c6e014b608b64d8805b90997977b0e6eee357d6cc28f02726322c8
- GL-I03 config16c9d983c0202bb122be300db6faf70e7415300756392569acafa7d444cd49aa
- GL-I03 tests6433fa21200d1cbae0236c3701e31a5ec7b96d6d34549279909cacb6d948eccb
- ground.py2d25ccfd9b41b4e16b36c07eec5b243ac50a63bf15230445d942e0f1bcebc4d3
- calibration.pyd29519a1cdb5e495d23115bc89886e9071e4f2055ff529285e933cebdb7c58a3
- capture_input.py56355e9594433d91c871685f58c6ae9f8fe0e47d2b3ad7d07f9b5b8050b85f16
- 原capture meta675c23ded9dcee82e6e985f17665469a487d34520408582708601eb188b1d692 / points.bin b81797f9825792655e5930edeb39c15275eb64e01999984884da61d252c599ff

真实输入：evidence/2026-10-03_gl_i02_r1/08_real/real_candidate.adapted.npz（SHA f12f48bd3977d935952f5fae685bd73f4721dca09e663fdd6219d3abae215558）；draft在同轮codex_review_01/work/filled_real_draft.json（SHA4d42b1ec3b5c5a6d489d61d537be228b1007055d4f65dd54923ae40d40461f2e）。所有路径相对docs/human_fall/。不要改它们，不重新prepare/采集覆盖原数据。

已批准up=[0.438371,0,0.898794]、height=[1.2,1.7]、四区固定。已知FIT1214，默认80 insufficient，0.05/8采1193却正X角差52.28°而早退。负X或ROI法向WHAT_IF虽角度过门，实际fit仍competition_unresolved；三个holdout事后诊断RMS .04276/.10745/.08093、P95 .08119/.29493/.19304。89帧box偏差稳定；v2/v3高侧尾部、v1低侧偏差不能直接定物理身份。9月30SDK enable/六零不等于10月2日录制配置，frame字符串本身也不是extrinsic身份。

## 开发顺序与范围

先开发可用离线诊断，然后开发独立搜索原型，不要求产出真实calibration来证明软件完成。

允许新生产文件：core/ground_diagnostics.py（纯std+NumPy）、scripts/diagnose_gli04_geometry.py（薄CLI）、tests/test_gli04_geometry.py（集中测试）。可以合理减少文件；增加生产路径或接入点须先有具体计划/范围记录。不编辑任何已有core/config/GL-I03三文件/原tests/批准draft/capture/driver/webui/pc_apps/HR；不部署/板端网络/采集/GL05/正式页面。

本单新证据默认evidence/2026-10-03_gl_i04_r1/，记录root路径供二审引用；只新增不覆盖。研究prototype放research_01/search_prototype.py，不接入core/runtime/候选标定入口。纯core无ROS/YAML/浏览器依赖；CLI复用已存在loader/config能力，无必要不加依赖。Python3.8兼容；本机运行不冒称目标Python3.8.10/NumPy1.17.4真机验证。

### A. 离线诊断工具

- 接受既有adapted NPZ、批准draft、可选显式constrained config；复用来源hash/frame/group与strict selector，非法输入拒绝，默认/WHAT_IF来源清楚。
- 输出独立kind/schema的diagnostic JSON、Markdown、source-index sidecar和至少一份可核查局部空间产物。可以用简单静态图或自包含HTML，不动生产webui；报告只读不自动提交新ROI/先验。全部输出独占新目录；计算失败/非法输入不能覆盖已有输出、capture或draft。不生成geometry calibration/ground_derived。
- 按原四box逐source frame全点分析；empty/zero/边界显式记录。保留pooled row/frame ordinal/seq/frame内row映射；若显示抽样，列显示数量/索引/规则，统计仍全量，禁止暗滤validation。
- 用signed residual/RMS/P95/support、独立于残差的固定空间分箱及逐帧变化区分现象。source轴与world轴不混；高低残差只称几何尾部。
- 旋转方向给出明确条件及可手算小例；approved up、negative-X/数据法向假设、unknown extrinsic分别标记，不自动纠正批准值。
- frozen fit raw输出与replay/后算holdout指标分开。复现拒绝阶段/候选cap/trace；早退后不能假称实际执行validation，replay计数不标成fitter原生trace。复现不符时先查路径/设置/源码hash，不能改预期答案。

### B. 保守搜索研究原型

比较同输入/seed/设置/已见抽样序列的冻结baseline与独立prototype。候选“先精炼、再按已审相似判据判定、再有界保留”是待证假设，不是已证明正确的方案；可因反例改设计，记录理由。

- 每个已见合格raw假设有精炼/拒绝/保留/合并/预算未完成事件；不能仅最后剩1块就清不确定性。有限RANSAC不证明未见假设不存在，oracle也仅覆盖同已见序列。
- 现10°/.05m是协议相似判据，不是数学等价关系。必须查A~B、B~C但A不~C与代表更新/顺序导致distinct候选被吞的风险，保留必要见证或保守unresolved。
- 单平面清洁/噪声正例、至少3seed、输入置换、close竞争、晚到第二平面、重复相似/真正distinct、candidate/refine/trace预算截断必须比较。任何竞争或证据不足误接受都要集中修复，不能以研究原型免责。
- 明确候选/迭代/精炼/trace预算，处理不了的合格假设仍是unresolved。记录峰值保留、处理计数、运行成本和失败；不先许诺速度收益或在真实数据上改阈值凑结果。
- 小型oracle/额外研究trace仅在测试/证据，不能偷偷让实现变为不受控全量缓存。真实WHAT_IF可以对照，但不得写candidate/应用生命周期/提升physical。

## 自验、二审、收口

按唯一表L/R/S/B/D与Q矩阵逐项做：独立手算/已知反例→新功能兄弟状态→受影响回归→实际既有capture→首尾范围/SHA。必需软件未跑NOT_RUN；来源/物理缺口保持B类BLOCKED，不阻软件工具和synthetic研究。保持GL-I03软件结果不倒退。

先自验提交并停生产写入，按RETURN_TEMPLATE追加returns/GL-I04.md，只SUBMITTED/BLOCKED，含验收版本/SHA、实际writer/技能路径、每ID/source层级/原命令exit、newfile完整SHA/冻源对照、根因与更新计划、实验成功和被推翻假设。输出本轮11_submission_manifest.json（全部相关源码/测试/config/input/报告路径+SHA，含完整首尾基线引用）供二审使用。

Codex准备具体OpenCode二审提示与run_root，执行指定model/defaultDB一次≤1min无工具probe；成功后只读二审，报告全部缺陷后再交接单writer返工。失败保留原stdout/stderr/真实exit/model请求条件，二审NOT_RUN/BLOCKED，不让Codex自验冒充独审。停写后核提交SHA再维护表结果/REVIEW_LOG/README/DISPATCH；不由实现者写ACCEPTED。

交付必须包含诊断代码、研究原型、逐ID证据与决策：采用/不采用/需补实验，以及下一步最小可判别实验。研究没赢baseline可如实结论；安全负例失败不能标PASS。只推荐后续接入方案，本单不自动改冻结算法/physical协议/设备。
