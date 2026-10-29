# 进度日志

追加式；最新在最后。规则见 [PROJECT_WORKFLOW.md](PROJECT_WORKFLOW.md)。

## 2026-10-18 整体项目开发（继承自旧日志）

用户明确改为整体项目开发，不再逐缺陷派工。

- 绑定运行：`docs/human_fall/evidence/2026-10-18_hfus_project_dev_r1/run_02`（386 帧，会话 `cap_20261018_110029`）。
- 默认变体 `partition`；默认坐标 ground，可切 RAW；地面配平 pitch 25.3607°、roll -0.8368°、地面 z=0。
- 回放服务：`python -B -W error sidequests/hfus_tcms_02/realdev/current/server.py --port 8934`。

## 2026-10-18 工作流重写

- 新工作流：`docs/PROJECT_WORKFLOW.md`（唯一权威）、`docs/PROJECT_STATE.md`、本日志。
- 旧工单 / 验收表 / 回传 / 复审流程全部冻结；历史日志归档为 `docs/human_fall/WORKFLOW_HISTORY.md`、`docs/human_capture/README_HISTORY.md`。
- 旧的 `docs/AI_DEVELOPMENT_POLICY.md`、`RETURN_TEMPLATE.md`、`CODEX_OPENCODE_WORKFLOW.md`、`PROJECT_PROGRESS.md` 改为废弃指针。
- 未改任何生产代码、配置、数据、证据。

## 2026-10-18 工作流重写（收尾核对）

- 新增 `docs/PROJECT_WORKFLOW.md`、`docs/PROJECT_STATE.md`、`docs/PROGRESS.md`；`AGENTS.md` / `CLAUDE.md` 工作流段改为指向这三份。
- 旧 `docs/human_fall/WORKFLOW.md`（103,663 B）与 `docs/human_capture/README.md`（89,152 B）原文完整归档到 `WORKFLOW_HISTORY.md` / `README_HISTORY.md`；新 README 只保留 §0–§8 技术契约。
- `AI_DEVELOPMENT_POLICY.md`、`RETURN_TEMPLATE.md`、`CODEX_OPENCODE_WORKFLOW.md`、`PROJECT_PROGRESS.md` 改为废弃指针，原文进 `docs/archive/workflow_legacy_2026-10-18/`。
- `run.py` 证据白名单增加 `docs/evidence`（保留旧 `docs/human_fall/evidence` 兼容）；`ast.parse` 通过。
- 本轮未跑数据管线、未跑单元测试、未改生产算法/配置/数据；下一步按新流程做自动目标获取。

## 2026-10-18 基线事实

- 本轮开发入口：`sidequests/hfus_tcms_02/realdev/current/`。
- 当前结果：386 帧 × 2 变体；210/386 帧有标定，最大 10/12；UPPER/OUTER 两条上侧/外侧分支从未达标。
- 点级 GT 缺失：purity / recall / 跌倒效果维持 UNKNOWN。

## 2026-10-18 跟踪/跌倒接入 + 主体框修正

- 新增 `current/project_fall.py`：复用 `core/tracking|features|fall_state`，逐帧单一 `t0001`；预测位置不作观测；`confirmed` 关闭，上限 `suspected`。`run.py` 写 track/fall/candidate，`server.py`/`app.js` 显示跟踪、跌倒状态、短边说明。
- 主体框由“全部前景 min/max”改为“RAW 中最大连通前景簇（5 cm 体素、26 邻域）再经同一地面变换”；其余前景点保留为 `bbox_foreground` / `outlier_points`。341 帧框宽 1.65 m → 0.91 m。
- `tools/ai_gt/point_membership.py` 点级 GT 通道（validate/audit/score/selfcheck，7/7）；无真实标签，不产出指标。
- 运行：`run.py --out docs/evidence/2026-10-18_hfus_project_dev/run_04`（386 帧，帧级 SHAs 与 run_03 相同）；`LATEST.json` 指向 run_04；服务已重启。
- 验证：`verify.py` 六段全过（api/http/foreground/calibration/fall/frozen/repro）；`run_tests.py` 8 条 exit 0；Chrome 实页 0 错误、`t0001`/直立/`3 / 12` 与 API 一致；源码态与打包 exe `--check-real-fall` 均 exit 0。
- 证据：`docs/evidence/2026-10-18_hfus_project_dev/`（run_04、BODY_BOX.json、PAGE_CHECK.json、两张截图、TESTS、CONSOLE_*）。
- 未解决：点级 GT 缺失（purity/recall UNKNOWN）；无跌倒会话（confirmed 关闭）；两条短分支边冻结门下不可认证；`--check-startup` pointset 数据缺失。

## 2026-10-18 单目标自动识别开发计划

- 新增 `docs/SINGLE_TARGET_PLAN.md`，明确五步：统一目标点集、自动获取/重获、原始帧在线等价候选、生产核心/页面接入、回归固化；下一轮先完成前两步。
- 代码核实：当前入口绑定固定 ROI/历史前景账本；页面最大连通簇框与区域/跟踪/跌倒输入点集不同。列入优先修正，不把显示框优化当作算法点集已修正。
- 验证：生产 Python 504/504、current 9/9（均 `-B -W error`）；完整回放 386 帧 × 2 变体完成，exit 0。机器日志、回放及基线比较放 `docs/evidence/2026-10-18_single_target_plan/`。
- 本轮只改规划/状态文档；未改算法、LATEST、冻结配置或原始数据，未部署/采集/训练。几何候选不是人体真值，效果指标仍 UNKNOWN，confirmed 关闭。

## 2026-10-18 自动单目标实现与框过大修正

- 实现共享 RAW 三维 5 cm / 26 邻域组件和来源行绑定；区域输入、候选特征、跟踪/跌倒与显示框取同一实际关联目标。保留全部前景、全部簇和拒绝原因；多合格候选等待，不自动取最大簇。
- 新增 `core/target_acquisition.py`，接入 current、FallNodeCore、ReplayPipeline；唯一性 + 至少 0.6 s / 5 帧获取，最大帧间隔 0.3 s；短遮挡只预测，超时/歧义自动重获新 ID；时间/标定/坐标/过期输入清空获取累计与旧基线。自动来源明确 `automatic_acquisition`，不伪装操作员。
- 原始帧入口可指定会话/地面/背景/搜索域/候选变体，默认 raw；历史账本仅 `--pipeline foreground` 对照读取。采用显式声明前 50 帧空场预热时逐帧消费后冻结背景；不给背景的 v2 完整回放 386 帧均 ambiguous、无强选。
- 用户指出框仍大：查出新路径水平聚类误并空间分离残留，341 帧框宽曾达 2.195 m。新增 `single_target_geometry_v2.json` 使用共享 RAW 三维组件，从根因修点集，未靠缩显示框。341 帧改为 0.954 m（2337 / 2462 前景点，125 未选点、64 簇）；160 帧 0.674 m、183 帧 0.708 m。旧 0.91 m 属不同 ROI/背景输入，不是人体 GT。
- 完整结果：`docs/evidence/2026-10-18_single_target_auto/raw_final_v2/`，386 帧 × 2 变体；首次锁定 frame 107 / 11.092058 s；searching 101、acquiring 6、locked 267、occluded 12；单一 t0001，本会话无重获。四次 v2 完整回放帧账本 SHA 相同；每变体前 120 帧未来隔离检查通过。
- 验证：生产 517 项 / current 10 项（`-B -W error`）、WebUI lib、console JS/Python 通过；772 个帧×变体双坐标 API 检查、实页 frame 341、console 来源行检查通过；148 帧合成生产核心/ReplayPipeline 生命周期覆盖竞争、移动/静止、短遮挡、低姿态、疑似粘连、长失锁重获，旧基线不继承；合成只验证软件。
- 逐值对照：与 run_04 比，前景路径 268 帧点数变化 / 5 帧姿态变化，原始路径 266 帧点数变化 / 8 帧姿态变化；逐帧中心、框、跟踪、姿态在 `final_validation/RUN04_FRAME_COMPARE.jsonl`，原因是持续获取门、组件点集、背景/搜索域与原始候选变化。旧账本使用前 50 帧背景和固定 ROI，原始路径不读取它。
- 边界：原始目标超旧区域研究域的 267 帧区域 UNKNOWN（明确 `OUTSIDE_REGION_DEVELOPMENT_DOMAIN`）；不裁剪目标凑旧域。已有 24 个会话只读盘点，缺独立真值的真实竞争/遮挡/身份等场景仍列缺口。人体 precision/recall、误锁率、身份切换率 UNKNOWN；confirmed 关闭、事件 0；研究地面变换的 physical_verified/runtime_eligible=false 不变。
- 性能：PC 串行 P50 79.6 ms / P95 116.2 ms / max 552.8 ms，对比源帧约 103.664 ms，未宣称实时达标，板端 UNKNOWN。未部署/采集/训练/下载权重/开 HR-09；既有手动入口回归保留，打包 Console.exe 本轮未重打。
- 证据：本轮目录包含源码/输入 SHA、状态转换/耗时、失败轮次、全部簇/目标来源行、框修正、重复性、合成生命周期、API/页面截图、测试日志；LATEST 已绑定 raw_final_v2，PC 回放在 8935。下一步是现有区域域外适配、已盘点会话的更多反例和性能分析，不能将本轮软件通过写成人体/物理效果通过。

## 2026-10-18 完整连续开发调试流程

- 新增 `docs/DEVELOPMENT_DEBUGGING.md`，以整条产品链为对象组织输入/场景、同输入实验对照与旧功能对照、源点/极值点/组件连接追溯、共享核心修复、生命周期、区域域适配、姿态、页面/console、性能与自动采用的持续闭环。没有工单、验收表、人工标注前置或复审流程。
- 更新唯一工作流与当前状态：明确“接口已接通/软件回归通过”不等于整个单目标目标完成；0.954 m 不证明人体成员正确，267 帧区域 UNKNOWN 是待修复功能回退，P95 高于输入间隔不宣称实时达标。后续不等用户逐项派工，相关模块与场景在同一循环持续处理。
- 验证：获取/生命周期相关 13 项单测通过（`-B -W error`）；完整 386 帧 × 2 变体离线回放 exit 0，逐帧账本与当前绑定 raw_final_v2 的 SHA 相同。机器日志、文档检查和 SHA 位于 `docs/evidence/2026-10-18_development_debugging_flow/`。
- 本次仅设计和更新文档，未改算法、配置、LATEST、原始数据或设备状态。初始计划保留作历史上下文，当前后续路线以新调试方案和 PROJECT_STATE 为入口。

## 2026-10-18 连续开发：区域域适配、候选性能与坐标绑定

- 固定 raw_final_v2 与旧 foreground_spatial/run_04；1818 个已跟踪/未跟踪源码、配置、文档记录 branch/HEAD/SHA。整段复现与原账本一致，确认 267 帧区域全拒绝来自旧绝对 RAW ROI，而非点数不足。
- 新增显式 target_ground_v1 区域契约：目标相对分区、绑定地面法向判直立；保留 legacy_raw_roi 对照和全部支撑/退化门，不裁剪目标。265/267 实测帧恢复区域，124 帧 13/13；372/373 因 SHORT_BODY_SUPPORT 继续拒绝，119 未观测帧无区域。225 帧有标定连接、最多 11/12；这些只说明几何功能恢复。
- 共享候选小簇先拒绝、三维组件批量量化/Python 整数键；两变体间释放上一份完整账本。隔离顺序对照结果完全一致，稳态 P50 55.4–60.6 ms → 33.0–34.2 ms，优化 P95 71.9–75.2 ms；仍有 118.4–124.9 ms 稳态尖峰、553.8 ms 背景冻结。初次性能记录保留并标出账本滞留/并行干扰，未宣称板端或队列实时达标。
- 全段保存极值来源行、10 cm 局部支撑、到几何锚点的连接路径、单桥边/切体素、前帧最近来源和 4/5/6 cm/半格相位增删行。桥边/单体素切点最多分离 27 点；最宽实际为326帧1.070499 m。证据不支持无条件剪边，不改成员掩盖语义未知。
- Store 补齐运行地面SHA、逐帧地面版本、coordinates.py SHA绑定，新增同会话另一合法地面替换反例。完整386帧×2变体重复与前120帧因果检查通过；目标/前景/组件/框/获取/跟踪/姿态与上一轮逐值相同，旧域foreground数值相同；无背景386帧仍竞争拒绝。
- 验证：Python 519/45/2、current 13项（-B -W error），相关JS/console通过；772帧×变体双坐标、40个HTTP样本、实页341的13/13区域与console来源一致。LATEST采用 raw_adopt，PC8935已加载本轮完成运行；未重打Console.exe、未部署/采集/训练/下模型/开HR-09。
- 机器证据与可复现脚本：`docs/evidence/2026-10-18_target_region_debug/`。人体点级/身份/跌倒GT、物理配平与板端性能仍UNKNOWN；confirmed关闭。下一步继续无背景竞争来源、跨场景成员归属与区域支撑稳定性，不能把本轮通过写成整条人体链完成。

## 2026-10-19 OpenCode 只读审查与修正

- R1 因本轮 OpenCode 配置 `plugins:["-*"]` 关闭了内置 agent 注册而未启动推理；移除后 R2 用 opencode-go/deepseek-v4.1-flash 完成40步只读审查，exit0，实际工具仅read/glob/grep，11个作用域文件SHA前后相同。原结论保存在 `OPENCODE_REVIEW_R2.md`，未发现需阻断的具体缺陷；它明确列出未完整读取的大文件/页面实现等审查范围边界。
- 处理具体意见：Store初始化任一后续异常均关闭源memmap，新增坐标构造失败/无效默认变体的close断言；info公开地面法向、ID和SHA。foreground是历史账本输入、仍保留旧ROI，target_ground_v1仅取消区域阶段的绝对域拒绝；RUN/info新增input_scope及CLI说明，未把新区域契约冒充输入已扩大。
- 补充分母：4cm/5cm半格/6cm改变264/263/261个实测帧，成员对称差/原目标点数中位0.413%/0.300%/0.289%，最坏9.375%/2.508%/11.576%，稀疏退场帧不能笼统称变化很小。无背景336可比帧的2617合格候选出现记录中，2293个至少95%点被声明空场参考模型解释；这不是背景真值或识别人指标。
- 生成版本缺口明确保留：初次PERFORMANCE.json没有retention字段，当前validator已增该字段及其他模式；初次/隔离性能生成时validator独立SHA未保存，不回填旧证据。隔离对照仍有候选源码SHA、基线重建SHA和逐帧等值断言；原初次记录仅作被替代的诊断，不作实时或采用依据。
- 修正后完整回放 `raw_reviewfix` 386帧×2变体与raw_adopt逐值相同，前120帧未来隔离相同；foreground_scope_reviewfix明确保留历史ROI，上游目标/簇/框/跟踪/姿态与foreground_legacy同值。current14项 -B -W error通过；772帧×变体双坐标/40HTTP、console、最终实页341核对完成，LATEST与PC8935均绑定raw_reviewfix。共享核心未在审查后再改，519/45/2和JS既有通过记录保留。
- OpenCode R3补充审查exit0（24步），实际仅read/glob/grep，作用域11文件SHA前后相同，确认错误路径close/输入作用域/比例分母修正，未发现新的阻断性缺陷。原文 `OPENCODE_REVIEW_R3.md` 同时保留低级别证据/元数据口径意见及未独立重算/未读完大文件的范围边界，不把审查视作人体/物理通过。
- R3之后仅补机器证据：integration.py改为独立重读持久化地面工件及其SHA核对info（不再只比内存对象），API_FINAL再次通过；新增final_evidence.py重现FOREGROUND_SCOPE_CHECK、REVIEWFIX_COMPARISON、SENSITIVITY_FRACTIONS、NO_BACKGROUND_CANDIDATE_COUNTS，均与原JSON逐值相等，原文件不覆盖。raw自定义search_bounds单独记录，historical_roi_applied=false不表示没有任何输入裁剪；旧性能生成器SHA缺口继续UNKNOWN。


## 2026-10-19 人体范围 AI 判读与 RK3588/RGB 可用性探针

- 用户授权调用3588资源寻找目标点归属方法；先只读盘点并保存35866个已索引/非忽略未跟踪文件的branch/HEAD/SHA基线（约11.4GB）。唯一写入者仍为本会话，子代理仅只读调查。
- 确认板端已有USB相机、yolov8n_v2.rknn、RKNNLite可用。新增joint_camera_probe.py将已有JPEG经stdin送入现有NPU内存推理，无板端输出文件/模型下载/服务启停；两段联合会话各8帧共16样本、12帧有person输出，推理62.6–108.2ms。模型SHA、输入JPEG/会话SHA、stderr版本警告保留；不把输出比例作准确率。
- 两段RGB记录cap_20261015_224744/224823只有接收时间与bag wall time，无已绑定相机内参/雷达外参，捕获/时钟偏差未知。主会话没有RGB；8081 snapshot在idle仍返回旧缓存，未当现场。没有把RGB框直接投成点掩码。
- 新增RAW中性三视图工具，agent在主会话f160/f341记录保守躯干/头部核心弱标签621/315点，包络内1711/1997点保留UNCERTAIN，来源行审计通过。blind=false、完整人体=false、独立GT=false，purity/recall仍为null；包络外点不自动算背景。图与实际源行绑定，用户无需逐点标注。
- 新增仅消费过去角格距离返回的visibility_change诊断cue，在386+178+48=612帧跑完。初始占据不被自动命名背景、无回波不当自由空间；量化杂散、传感器自身运动和静止目标缺少新变化的边界明确，未接入获取器或冒充完整人体掩码。
- 验证：AI工具36项/current14项（-B -W error）通过；386帧×2变体完整回放SHA与raw_reviewfix完全相同。第一次视图渲染因qualification字段层级错误失败，已修正、新目录重跑并保留失败产物。最新默认、源数据、板端服务、confirmed均未改。
- 路线与未完成项写入docs/HUMAN_POINTSET_METHOD.md与PROJECT_STATE：下一步是相机几何/时间关联、共享变化/语义辅助获取、可靠成员上的区域唯一支撑及跨场景回归；现有两段RGB会话没有绑定地面，本轮未宣称区域跨场景通过。证据和重现脚本：docs/evidence/2026-10-19_human_membership_probe/。


## 2026-10-19 最终产品硬件约束纠正：单雷达 + RK3588

- 用户明确最终只有一个雷达和一块开发板。修正PROJECT_STATE与HUMAN_POINTSET_METHOD：人体判断、点集、跟踪、区域/姿态与跌倒仅靠雷达输入在板端运行；agent只参与离线开发，已有RGB只作可选历史辅助，相机标定退出产品关键路径。
- 纯雷达路线改为因果候选历史、结构/形状与雷达人体判别、成员归属、静止保持、区域唯一支撑及跨场景回归；必须分别覆盖上电即静止和进入后静止，不能以运动物体获取代替人体识别。若规则不足，另评估雷达专用语义能力；本次未训练/下载模型/开HR-09。
- 仅修改路线与状态文档，未改生产算法、配置、LATEST或板端服务。静态检查共享core/current Python入口未发现相机/图像模型导入；current14项 -B -W error通过，未提供RGB的主会话386帧×2变体完整回放与raw_reviewfix逐帧文件SHA相同。仍使用显式50帧空场开发假设，这不证明无背景人体识别或板端效果已完成。
- baseline覆盖35913个已索引/非忽略未跟踪文件，未变的35863个文件哈希按大小/mtime从上轮全量基线复用，其余重算。硬件契约、检查、测试与回放证据：docs/evidence/2026-10-19_lidar_only_product/。

## 2026-10-19 候选历史、成员账本与无背景可分性

- 共享 `core/candidate_history.py` 已接入 current、FallNodeCore、ReplayPipeline 自动路径，默认 `evidence_only`。历史绑定 session/时间/epoch/坐标/地面 SHA/帧序号/实际来源行，按 0.1 m 支撑体素与中心连续性关联；`candidate_id` 只在本帧有效。初始静止候选保持 `semantic=unknown`，不因长期不动学入背景；预测不追加观测。API/页面逐帧显示 history id、观测帧数、跨度、关联状态、支撑冲突、结构/高度分层和来源行。地面上下文换代立即清空获取状态。
- 修复成员账本：合并/分裂的增删来源行改为对全部直接前驱支撑并集计算，新增 `compared_history_ids` 与明确 `comparison`。显式背景 280 条、无背景 3766 条历史记录的成员字段变化；目标获取/跟踪/区域/姿态/跌倒等核心输出 0 变化。新增合并/分裂单测。
- 固定输入完整回放：显式背景 386 帧×2 变体仍 frame 107 / 11.092058 s 首次锁定，267 locked / 12 occluded / 107 unselected；265/267 实测帧有区域，341 帧 13/13 区域。无背景 386/386 仍 ambiguous，无自动锁定。历史最长连续 27.78 s（显式背景）/25.81 s（无背景）。重复完整回放 SHA 相同；前 120 帧隔离与完整回放逐字段一致。
- 可分性检查（显式背景目标作开发参考，不是人体 GT）：266 个有参考帧、2338 个竞争候选观测；229 个竞争观测通过宽松类目标条件；单特征最高池化 AUC 0.963（scattering），逐帧 top-1 最高 244/266。窄规则（1500–5000 点、scattering≤0.05、≥5 高度层）命中 256 目标帧，但 6 个非目标命中（5 个在显式目标出现前，1 个 f369 仅 36.9% 目标重叠）并漏 11 个入场/退场帧；绝对点数下限会排除更远/更小的静止人体。未部署，避免单会话阈值堆叠。
- 场景：f0–385 静态家具/竞争；f101–120 进入；f140–165 进入后静止；f180–330 原地动作；f340–373 离场/局部可见；f374–385 无实测目标。f372/373 是离场局部可见，不是已验证蹲姿/跌倒。缺真实开机即静止人体、已验证低姿态、双人竞争、完整遮挡。
- 验证：共享核心 537 项、current 14 项、WebUI 18/55、console JS 21/Python 8 通过（Python 均 `-B -W error`）；Store 772 帧×变体双坐标、HTTP 样本、实页 341、console `--check-real-fall` 通过。PC 回放 P50 72.5–79.3 ms / P95 138.6–150.5 ms / max 0.44–1.02 s，源间隔约 103.664 ms；板端整链性能 UNKNOWN。LATEST 与 PC 8935 已绑定 `membership_background_v2`；未部署/采集/训练/下载权重/开 HR-09。
- 证据：`docs/evidence/2026-10-19_novelty_acquisition/`（BASELINE、SOURCE_CHANGE、MEMBERSHIP_COMPARISON、ADOPTION_CHECK、SEPARABILITY、NARROW_RULE_CHECK、CONSOLE_CHECK_V2、PAGE_CHECK、SUMMARY、完整回放与测试日志）。人体/点级 GT、真实身份与跌倒效果仍 UNKNOWN，confirmed 关闭。

## 2026-10-19 固定背景能力边界：前景隔离不是人体识别

- A/B 实验：同一主会话，背景 A 用声明空场 0–49 帧，背景 B 用人已在场的 140–189 帧；测试 190–330（静止/动作）和 340–373（离场/局部可见）。参考目标来自显式背景开发运行，不是人体 GT。
- 背景 A：190–330 帧 141/141 参考目标全部保留，340–373 帧 34/34 保留，平均每帧 1 个候选。背景 B：190–330 帧参考目标平均仅保留 3.66%，0/141 帧超过 50%，平均前景约 122 点；说明人在背景学习期间在场会被吸收。
- 关键细节：B 在部分帧仍留下 48–59 点碎片，这些碎片可 100% 落在参考目标行内；若把“候选大部分是目标”当人体判据，会把碎片误当完整人。A 能给出干净前景，是因为显式假设了空场且人未出现在背景学习中，不是算法理解了“人”。
- 结论：固定背景可用于显式空场开发对照、前景隔离和候选提取；不能命名人体，也不能解决开机即静止、背景变化、多人/家具移动或未知空场。未改生产默认、原始数据或板端服务；证据与复现脚本 `docs/evidence/2026-10-19_fixed_background_boundary/`。

## 2026-10-19 无背景变化获取实验：候选历史用于获取与保持

- 共享 `TargetAcquisition` 新增两个默认关闭的实验门：`change_gate`（唯一持续运动历史可作为获取线索，要求观测帧数和净位移；仍走质量/连续性门）和 `history_hold_gate`（锁定后只接受与锁定 history id 相同的实际观测，其他历史不能替换目标）。current 增加 `--change-acquisition`、`--history-hold-gate`；`FallNodeCore`/`ReplayPipeline` 通过 acquisition 配置同样可启用。语义保持 `unknown`，不把运动簇命名人体。
- 无背景 386 帧：仅变化门 f122 / 12.647 s 首次锁定，264 locked / 122 unselected；目标行与显式背景参考目标平均重叠 0.939，但退出后 12 帧误锁静态家具（f374–385 目标行 1334–1350）。
- 变化门+历史保持门：同样 f122 锁定，240 locked / 24 occluded；所有 240 个已观测帧与参考目标重叠 100%，退出后 0 帧误锁家具；代价是 f365 起目标历史与家具合并/分裂导致 `history_identity_conflict`，最后 24 帧只保留预测、不提供点集或跌倒证据。完整重复回放 SHA 相同，前 120 帧隔离逐字段一致。
- 显式背景加两个门：仍 frame 107 / 11.092058 s 首次锁定，267 locked / 12 occluded，逐帧核心输出与采用运行一致；说明历史保持门不会回退显式背景路径。采用默认仍为关闭实验门、显式背景 evidence-only；无背景模式是几何获取线索，移动家具同样可能被获取，不能当人体识别。证据 `docs/evidence/2026-10-19_change_acquisition/`（COMPARISON、PREFIX、SUMMARY、完整回放、测试与 console/page 日志）。


## 2026-10-19 单目标实时：现场配平、声明空场与既有算法复用

- 按用户实时请求，在现有 192.168.31.58 / slam-localization 启动隔离临时节点与 :8936 页面；驱动/发布服务/release/默认配置未改。用户确认空场后，复用 build_background 冻结 50 帧体素背景，两个实验门关闭，不录原始点云会话、不把静止候选自动吸收为背景。最新节点 PID 33396，临时根 /tmp/ldiar_single_target_live_20261019_1622。
- 复用候选、获取、历史、单目标跟踪、站姿基线和跌倒；共享封装 current project_regions.estimate 与 r08 CalibrationLayer，以同一实际目标来源行输出 13 区域/12 连接。预测/失效/断流/绑定换代清资格；confirmed 仍关闭。生产原基线 3 s / 15 帧与 current 原基线 0.6 s / 8 帧不同，未冒充整链完全等价。live 仅限制诊断历史保留，不改原校准门。
- 现场配平复用既有地面拟合/基向量算法，RAW z<0 仅限拟合输入；原有效性门未放宽。独立四帧支撑显示 abs(z) P95 ≤2.71 cm、法向差 ≤0.219°；物理水平精度 UNKNOWN。点云/框/区域同一显示变换，实际支撑行与数值仍在 source 系。
- 修复自动未选目标 state.time_epoch=null 导致前端拒收：改用 cloud_timebase 的权威 epoch；优化三维连通整数桶和历史体素转换，保持精确成员与遍历顺序。补原页缓存资源版本；用户报告“等待”后直接重载原标签页并连接，已显示“配平候选 · 未物理验证”、9.8 Hz / 丢帧 0，空场 no_qualified_candidate、0/13 区域、0/12 连接。完整实页截图、DOM、console 0 错误已保存。
- 独立空场 20 s / 194 帧及最终 15 s / 145 帧均 0 候选/0 锁定；最终约 9.60 Hz，process P50/P95/max=45.3/99.9/113.8 ms，接收至完成 P95 116.4 ms，队列丢帧 0。145/145 state、snapshot、地面绑定通过，无区域输出。该结果只覆盖声明空场，不证明识别人；家具移动/真人入场/多人/遮挡/跌倒现场效果及 precision/recall 均 UNKNOWN。
- 验证：542 核心、17 current、20 WebUI 通过（Python -B -W error）；两种模式×两变体完整回放文件 SHA 与原 change_acquisition 运行相同。LATEST / PC 8935 / console 更新到本轮 default_final，采用行为不变；Store 新增 region_runtime 源码 SHA 检查。console --check-real-fall 与 8935 API 通过。首次严格 ROS runtime 因 rospy 的 logging.warn 废弃警告退出，已保留日志并让实时 wrapper 使用正常 warnings；测试始终 -W error。初次 current 检查因旧 LATEST 源码 guard 拒绝，完整回放并刷新绑定后 17 项通过。
- 证据 docs/evidence/2026-10-19_single_target_live/：全量 36,383 路径 baseline、live/config/source SHA、BACKGROUND_BUILD、LEVELING_CHECK、LIVE_CHECK_FINAL、WIRE_CHECK_FINAL、REPLAY_PARITY_FINAL、PAGE_ORIGINAL_FIXED、SUMMARY、SOURCE_CHANGE、完整回放和测试日志。未 commit/push/reset/checkout/clean，未动 data/junction，未持久部署/采集会话/训练/下载权重/开 HR-09。

## 2026-10-19 3588 板端实时负载实测（只读）

- 用户问 live 入口 `http://192.168.31.58:8936/leveled/?prefix=/single_target_live/…&v=live-reuse-final` 在 3588 上的负载。经 ssh 只读采样 `/proc/stat`、逐进程/逐线程 `stat`、thermal/cpufreq、`top -bn2`、`rostopic hz`，未改板端配置/进程/release，未重启、未部署。
- 板卡 Rockchip RK3588 EVB7 LP4 V10，8 核。10–15 s 窗口整机忙碌 26.3%（≈2.1/8 核），`top` us 16.9–17.1 / sy 5.1–7.0 / si 3.5，idle 72.5–74.1%；load average 1/5/15 由 17:24 的 2.62/2.50/2.40 降到 17:31 的 2.02/2.37/2.37。
- 分进程（对单核）：live 节点 `run_reuse_final.py`（主机 PID 2608145，绑核 4–7）88%，其中单线程 75.8%；常驻驱动 `inno_lidar_node` 71–79%（主线程 45%）；给页面推流的 `foxglove_bridge` 18%；`ksoftirqd/3` 6–11%；页面 `http.server 8936` ≈0%。分核最高 cpu3 55.9%（softirq 28.9%），其次 cpu2 33.0% / cpu5 32.9%。
- 温度 39.8–41.6 °C，governor ondemand（采样时 1.0–2.35 GHz 动态）；内存已用 1.08/7.9 GB，可用 6.9 GB。速率：`/innolidar_points` 9.6 Hz、`/single_target_live/state` 与 `display_points` 9.5–9.9 Hz；节点日志 278 帧 process P50 0.044 / P95 0.100 / max 0.273 s，接收至完成 P50 0.073 / P95 0.118 s。
- 粗分解：常驻驱动+ROS 栈 ≈0.8–1.0 核，本次 live 链路（节点+页面推流+中断）≈1.1–1.3 核；页面渲染在浏览器侧。采样时为声明空场、`searching / no_qualified_candidate`、0 候选，锁定目标后的负载增幅未测（UNKNOWN）；人体/物理效果指标仍 UNKNOWN，confirmed 关闭。
- 验证：共享核心 542 项通过（`python -B -W error -m unittest discover -s src/human_fall_detection/tests`，59.3 s，exit 0）；本轮未改任何源码/配置/数据。
- 证据 docs/evidence/2026-10-19_board_load_live/：SUMMARY.md、LOAD_SUMMARY.json、probe_raw.json、probe_threads_raw.json、top_two_samples.txt、proc_stat_sample.txt、snapshot_now.txt、node_reuse_final_tail.log、core_tests.log、probe_load.py、measure_now.sh、compute_load_summary.py。未 commit/push/reset/checkout/clean，未动 data/junction。

## 2026-10-19 有人时约 4 Hz 的瓶颈定位（只读）

- 用户报告 live 单人一轮：锁定 t0002、64/67 帧有区域支撑、有人时约 4 Hz、队列丢 93 帧，要求定位性能瓶颈。本轮只做只读定位，未改算法/配置/数据/板端。
- 现场数据重分析（`docs/evidence/2026-10-19_single_target_live_person`，486 帧）：unselected 390 帧 process P50 0.046 s、occluded 28 帧 0.050 s，而 locked 67 帧 P50 0.221 s / P95 0.303 s。同一候选在锁定瞬间跳变：11.92–12.23 s 未选中（5846/5723/5881 点）0.136/0.083/0.132 s → 12.34–12.85 s 锁定（6027/6516/6748 点）0.180/0.258/0.260 s。锁定帧 target 行数 P50 6086 / max 8017。源间隔 103.664 ms，所以锁定帧 250–290 ms 的墙钟直接导致队列溢出（93 帧）。
- 板端用同一份 live 代码（reuse_v6）只读微基准 `RegionRuntime.feed`（project_regions.estimate + r08 CalibrationLayer.update，绑核 4–7）：2400 点 33 ms、7400 点 95.5 ms、14800 点 169 ms（≈12–14 µs/点，线性）。cProfile（7400 点、96 ms）：`observe()` 13 次 61 ms，其中 `numpy.array` 221 次调用 57 ms —— 即冻结 S07F 的 `observe()` 每次把 `norm['xyz']`（`local.tolist()` 产生的 Python 嵌套列表）整份重转 numpy；`normalize` 13 ms；r08 校准层仅约 3 ms。空场帧（44–50 ms）与解码/发布（约 55–60 ms）不变，锁定帧多出的 100–140 ms 与该链路 80–100 ms 同量级。
- 等价性校验：PC 上用记录会话真实锁定帧目标点（2578/2827/2845/2999 点，来自 default_final 的 target_rows）跑同一代码得 11.8/10.8/10.9/11.1 ms，同尺寸合成体形 11.4 ms（差约 5%），板/PC 同尺寸比约 2.9×；说明成本可外推。
- 修复方向（下一轮实施）：在 `project_regions.estimate` 不再传 `local.tolist()`，并在 13 次 `observe()` 前把 `norm['xyz']` 转 ndarray 一次（预期 7400 点时 96→30–35 ms）；不改冻结 S07F 文件，门限不变，改后必须用完整回放 SHA 证明数值一致；随后板端复测锁定帧 process_s < 150 ms 且不再丢帧。
- 验证：current 17 项测试通过（`-B -W error`，exit 0）；板端探针为只读（无 ROS 发布、无配置改动）。证据 `docs/evidence/2026-10-19_locked_frame_profile/`：SUMMARY.md / SUMMARY.json / REGION_PROBE_BOARD.json / probe_regions_board.py / PC_SYNTH_VS_REAL.log / pc_synthetic_vs_recorded.py / current_tests.log。人体/点级 GT 与跌倒效果仍 UNKNOWN；未 commit/push/reset/checkout/clean，未动 data/junction。


## 2026-10-19 单人进出场实时观测

- 用户同意单人走入、站稳约5秒、横移、离开；沿用既有 observe_live.py 只读订阅算法输出与源header 60秒，未录原始点云会话、未改算法/阈值/进程。背景/地面 SHA 与上一轮一致，节点仍 PID33396。证据 `docs/evidence/2026-10-19_single_target_live_person/`。
- 486 条state对应486唯一源帧：67 locked / 28 occluded / 1 lost / 390 unselected。窗口只获取 t0002 一次；source t+12.336 s 锁定、28.819 s 遮挡、31.721 s 失锁、31.825 s 释放，末尾272帧/28.093 s持续未选。编号 t0002 不表示窗口有两个人；精确动作时刻、人体身份和点级 GT UNKNOWN。
- 基线锁定后3.835571 s、15样本ready，height std0.03103m、位置spread0.12461m；53个实测帧ready，52帧特征实际绑定，首次ready晚一帧消费符合既有调度。区域64/67帧有支撑、9帧13/13，26帧有本帧CALIBRATED且measurement非空连接，最多2条。所有区域/基线绑定一致、支撑行均在本帧目标行内；预测/非锁定帧无目标行或区域泄漏。3帧整区域拒绝（2横向退化、1非直立地面契约），末实测只剩81点。4帧low_posture_unclassified不解释成真实低姿态或跌倒；事件0、confirmed关闭。
- 未解性能：有人锁定段相邻实测间隔约4.03Hz（66间隔/16.379s），处理P50/P95=220.6/303.3ms、接收到完成P95=406.6ms，队列68→161（增丢93帧）；27个相邻实测间隔>0.3s，同一t0002内34个history_id，当前evidence_only。下一优先项是定位有人场景热点并恢复历史连续，不能用空场9.6Hz宣称整链实时。
- 检查：既有WebUI20项通过；486/486 state、snapshot与显示地面绑定通过，67个实测区域payload通过现有前端门；数据审计0绑定/来源行/预测泄漏失败，analyze.py -B -W error通过。单人现场E2E已执行，算法未改，无重复离线回放。原标签页末态DOM检查超时，本轮不声称新增页面通过。SUMMARY、FRAME_AUDIT、WIRE_CHECK、RUNTIME_BINDING、完整OBSERVATION及SHA保留；无commit/push/reset/checkout/clean、无data/junction改动、无训练/下载模型/HR-09。

## 2026-10-19 点云显示：抽样/全量可选（页面）

- 用户要求“点要全部显示在我这里”。页面新增“点云 抽样/全量”切换：全量接 `/innolidar_points`（每帧 49100–49123 点全部下发），抽样仍为节点显示流 `/single_target_live/display_points`（12000/49100 s4）。切换只换订阅话题并重连 foxglove_bridge；HF 层新增 `window.hfPointMode(topic)` 清空按话题缓存的原始帧/呈现帧，换流重置 seq 基线与丢帧计数；抽样比只在显示流生效时显示，全量模式显示“N 点 · 未抽样”。模式记在 localStorage（新浏览器默认抽样），刷新保持。
- 修掉切换时暴露的既有缺陷：重连后点云首帧早于第一条 state 到达时 `hfApplyDisplayGround` 读 `hf.lastState.observability` 抛 TypeError 并丢帧；加 `!!hf.lastState` 前置判定后实页 0 异常行、未呈现 0（仅换流后等待匹配输出的正常 0–1 帧滞后）。
- 实页核对（空场，18:00–18:05）：抽样 9.6–9.8 Hz / 呈现 9–10 Hz / 丢帧 0 / 吞吐 2.7–3.0 MB/s / 渲染 12000 点；全量 9.8 Hz / 呈现 10.0 Hz / 丢帧 0 / 吞吐 11.9–14.8 MB/s / 渲染 49101–49113 点；切换后新流首帧约 1–3 s 到（bridge 对新订阅懒加载），期间状态栏显示 `--`，不显示上一流数据。
- 只读板端采样（4 s /proc CPU tick）：全量模式 bridge 24.0% 单核、节点 85.2%；抽样模式 bridge 18.5%、节点 87.8%。全量只增加 bridge 序列化/发送开销（约 +5.5% 单核），节点算法 CPU 与输入输出不变；节点 PID 33396 未重启，web PID 32002 未变，driver/release/默认配置/地面/背景未改。
- 页面仅更新到临时根 `/tmp/ldiar_single_target_live_20261019_1622/webui/leveled/`，原文件同名 `.pre_toggle` 保留；仓库 `webui/human_fall/{index.html,human_fall.js}` 同步（`human_fall.js` 缓存版本号改为新 SHA 前缀）。
- 验证：`node webui/human_fall/human_fall_lib.test.js` 20 项通过、`node --check human_fall.js`、index.html 内联脚本 vm 语法通过；未改动的 `human_fall_preview` 副本 55 项通过。
- 证据 `docs/evidence/2026-10-19_point_stream_toggle/`：SUMMARY、PAGE_CHECK（实页逐次读数）、BOARD_COST、SERVED_FILES、POINT_STREAM_TOGGLE.diff（相对切换前服务文件的精确差异）、TESTS.log 与复现脚本。
- 局限：验证期间现场为空场，真人目标框/区域/拖拽在全量流下的叠加对齐未实测；桌面窗口不可见未取截图（状态读自实页 DOM）；无线拥塞时全量流可能更大帧龄/丢帧；人体/点级效果指标与板端整链实时性仍 UNKNOWN。

## 2026-10-19 锁定帧区域链路数组复用

- 按用户“继续开发”完成第 1–2 步：共享 `project_regions.estimate` 去掉 local.tolist()，冻结 normalize 返回后一次转 float64 ndarray，13 次 observe 复用；冻结 S07F/r08、门限/契约/背景/地面均未改。新增共享数组/只读回归。
- PC 交替同输入区域+r08微基准：7400 点 P50 22.79→7.84 ms（2.91×）；四个记录目标 2578–2999 点 10.81–12.60→4.51–4.60 ms（2.39–2.79×）。每组18个配对观测区域/标定完全相同；不是板端或实时队列结论。
- 完整默认背景、变化+保持两模式，各386帧×orientation/partition，四份逐帧SHA与single_target_live的default_final/change_hold_final全部相同；1544条来源行/绑定与1544对RAW/ground显示坐标审计通过；冻结三个参考文件SHA相同。542核心、18 current、WebUI20/55、console21 JS/8 Python通过（Python -B -W error）。
- 本地LATEST/新启动console绑定新default，HTTP frame341仍2337目标点、13区域、1已标定连接、confirmed关闭。自动审批拦截了本地8935服务重启（仅返回blocked by policy，命令未执行），只读确认旧服务仍缓存default_final；其数值SHA相同，不宣称加载新源码。
- 证据 `docs/evidence/2026-10-19_region_array_fastpath/`：全仓库baseline、前源码、REPLAY_PARITY、PC_BENCHMARK、INTEGRATION、FROZEN_SHA、CONSOLE_CHECK与测试日志。未部署/采集/改板端进程，未改data/junction，未commit/push/reset/checkout/clean，未训练/下载权重/开HR-09。下一步为优化代码的板端探针与有人实时复测，再做移动椅子反例；优化后process_s/queue_dropped及人体/物理效果仍UNKNOWN。

## 2026-10-19—20 CPU 链路持续优化及本地倒地算法盘点

- 用户要求持续优化后再调用NPU，并允许效果不好时自行尝试替代方法。完成显示连续字节视图抽样、来源行tolist/高度分位数复用、精确体素块组件遍历及显式冻结背景预编译；没有改变几何门限/背景内容/区域契约或跌倒确认开关。
- 板端只读内存探针（Python3.8.10/NumPy1.17.4，绑核4–7）：7400点区域+r08 P50 95.77→28.76ms；49100点显示抽样4.62→0.220ms；记录f160/f341完整候选42.04/41.69→30.72/32.82ms，输出逐值一致。未接ROS或录原始帧、未部署或切换既有进程；真实有人场景的优化后process_s/queue_dropped仍UNKNOWN。
- 精确块遍历经26方向单体素边界、随机独立oracle、float32和超大整数fallback检查；小输入门从128调到1024以避免额外开销，属于等价执行策略。背景NumPy/zip替代未见收益而放弃，改为显式不可变集合，普通可变背景和外部frozenset规范化语义保留。
- 最终386帧×默认/变化保持×orientation/partition四份SHA全部与原运行相同；1544条来源/绑定、1544对RAW/ground显示通过。核心546项、current18项及console HTTP/前端回归通过（Python -B -W error）；LATEST/新启动console采用default_prepared，PC8935/板端仍用原运行。
- 本地DGCNN-GRU资料确为20帧×369点雷达XYZ倒地网络，未找到对应权重/RKNN；已有PointNet ONNX为person/furniture分类，RF不等于NPU倒地。静态盘点未执行训练入口、模型或下载，HR-09未开启。下一项已复现：预测/未回调缺帧可能被特征持续低位时长跨越，将独立修复并检查事件去重；人体/物理效果UNKNOWN，confirmed关闭。
- 证据 `docs/evidence/2026-10-19_pipeline_continuation/`：全量baseline、源码快照、PC/BOARD探针、ALGORITHM_INVENTORY、各阶段回放、最终prepared_validation、测试日志。探针输出文件名曾被循环变量覆盖为node_PROBE，原文件保留，SHA核验后补存BOARD_PREPARED_PROBE并记录更正；未重复设备调用。未改data/junction，未commit/push/reset/checkout/clean。

## 2026-10-20 连续实测证据、恢复计时和回放基线绑定

- 用户继续并允许效果不好时换方法。已将CPU迭代全仓库36653路径SHA审计收尾（无意外变化），从该审计和133个刷新路径派生下一基线36776路径，保持单写入者与脏工作区。
- 修复预测/缺测跨段近地计时及拟合：保留实测history，以segment隔离；默认max_gap_s=.3s（浮点容差1e-9），恢复首帧near_ground=0/descent=None；非法或非递增源时钟不追加证据。machine只中断连续计时，保留已确认episode去重；恢复途中不达高度门重新计时。ReplayPipeline补全两个消费者的selection/calibration绑定。
- 合成复现旧→新：预测恢复时长.4→0s；隐式1.8s缺口suspected→low_posture_unclassified；中断恢复的过早upright→recovering；正确ready基线不可用→可用。显式/隐式/无时间缺口后事件仍仅一次，NaN/Inf保持可严格JSON输出；仅软件证明，非人体效果。
- 核心553、定向27、current18、console HTTP通过，板端Python3.8/NumPy1.17内存24逻辑测试通过（-B -W error）；四份完整386帧SHA与CPU基线相同，1544条来源/绑定与1544对RAW/ground显示核验通过。旧数据不含短缺口后恢复，故新增合成反例承担修复验证，不将无回退回放当效果提升。
- 本地包已生成：60文件/952320字节，SHA df32674ecfd7db25e987d95116872f6f7bf35765c4386d34a126b6fdad954e69，未上传或激活。已通过异步问题请求板端临时入口切换授权，来源为AGENTS/PROJECT_WORKFLOW的部署/启停边界，尚待答复。现有板端/PC8935仍缓存旧入口；最新LATEST与新启动console已切到新完成运行。
- 板端资产只读扫描仅找到YOLOv8n相关pt/onnx/rknn；无可直接调用的雷达倒地模型。DGCNN-GRU源码可借鉴连续帧约束，但缺权重/scaler/RKNN。未训练/下载/开HR-09；NPU推理未启动，真实实时队列与人体效果UNKNOWN，confirmed关闭。
- 证据 `docs/evidence/2026-10-20_observation_continuity/`：baseline、before_core、temporal_before/after、BOARD_LOGIC_PROBE、四份回放/核验、LOCAL_BUNDLE及日志。初次新增测试误读不存在的baseline_ready字段，已改用baseline_version断言，失败日志保留。未部署/采集/改驱动网络，未动data/junction或commit/push/reset/checkout/clean。

## 2026-10-20 优化临时入口切换与实时验证

- 用户明确授权“切换临时入口并验证”。df32674e包在新临时目录核验60文件SHA、板端编译/导入和相同配置后，核对PID/argv/启动身份，仅停止旧Python节点33396并启动34783；旧入口、地面/背景和回滚命令保留。
- 前12秒116帧、后35秒339帧均无锁定，3个候选持续竞争；处理P50 58.24→41.11ms、P95 119.24→98.03ms，后窗9.6465Hz、队列增丢0。相邻窗口不等于固定输入；锁定性能/人体效果UNKNOWN。候选339/339绑定、另12秒117/117显示wire头与HTTP通过；current18项通过。未保存原始点云或重验浏览器渲染。
- 只读核对确认driver102/bridge105/HTTP174、32002启动身份及地面/背景/显示地面SHA未变。发现辅助回调与解码前now错序导致假stale，继续下一根因修复。证据 `docs/evidence/2026-10-20_optimized_live_switch/`；最初postcheck误按wrapper声明查询旧ROS节点名，保留失败日志，随后按实际话题发布者/PID核验。无默认release/驱动/网络改动。

## 2026-10-20 锁内取时消除辅助流假过期

- process/status_state增加可注入now_fn并在core锁内采样，在线1个process/3个status_state调用覆盖；watchdog移除旧流_no_data/_stale后重算。显式回放时钟不变，不钳零负age、不放宽timeout。新增2项回归及CLOCK_REPRO：旧IMU负age报stale、watchdog残留旧码；新在线fresh，显式倒退仍stale且刷新后不残留旧码。
- 核心555/定向27/current18、console HTTP、板端Python3.8/NumPy1.17定向2项通过，均-B -W error；四份386帧回放逐字节/SHA仍与上一轮及原运行相同。LATEST/新启动console采用本轮default；既有PC8935仍缓存旧运行。
- 核验后把仅替换2个源码文件的3b1e4eb5包切入新临时目录，PID35319；实际argv补ROS remap，注册名现为/single_target_live。原wrapper main中的remap未传到rospy，是原先/human_fall_node名字的原因。两层回滚入口保留，原driver/bridge/HTTP、地面/背景/显示地面SHA不变。
- 修复后35秒339帧：IMU/device各339fresh、负age/假stale码0；9.6465Hz、process P50/P95 43.03/98.52ms、接收到完成P95 115.18ms、队列增丢0、suppressed0。339候选/339显示wire头绑定无失配，338共同RAW头匹配。仍均unselected、3候选竞争，锁定性能/移动椅子/人体效果UNKNOWN；可选单人动作问题未答，不据此猜GT。
- 证据 `docs/evidence/2026-10-20_locked_clock_freshness/`：源码前件/diff、BASELINE、CLOCK_REPRO、测试、回放SHA、LOCAL_BUNDLE、部署/观测/POSTCHECK/SUMMARY。早期校验在回放结束前访问文件并漏关读句柄，后改用check_replay完整通过；finalize日志编码名误写已修正，不影响测试或运行源码。未录会话、未动data/junction、未commit/push/reset/checkout/clean；无可用雷达倒地权重/scaler，未调用NPU/训练/下载/开HR-09，confirmed关闭。

## 2026-10-20 初始高度与近期运动获取门

- 按用户“高度范围+确定在动再锁定”改共享TargetAcquisition默认：地面相对P90 .8–2.2m，同history近1.2s/最多64点至少5帧、首3/末3实测中心median净位移≥.3m，再原.6s/5帧持续窗口。关闭新默认的静物fallback，旧运动过期；只限制首次/重获取，保持分支不要求运动或直立，静止/蹲低继续同ID实测。CandidateHistory小型只读接口复用source_rows中心；固定点云+伪移动框元数据反例已拒绝。
- 显式legacy保留原生命周期测试，新增13项默认门反例及core/replay一致性；最终核心568、current18、console HTTP、板端Python3.8/NumPy1.17定向13项通过，均-B -W error。早期current因LATEST仍旧源码被guard拒绝，完成新回放/绑定后通过，未削弱guard。
- 完整最终8份386帧：legacy四SHA逐字节等于原运行；new背景首锁11.092→12.025s、267→258实测，变化保持12.647→12.854s、240→238。前景/簇来源不变，共同实测点集/框/中心/区域nodes零差；1544来源审计、1544显示坐标对和120帧因果前缀通过。末尾4帧低位部分可见406/319/222/32点仍同ID实测；真实动作/人体身份UNKNOWN。
- 标定差异完整归因：共同当前measurement零差，背景基线f115→123、变化保持f129→131、首次有效标定各晚2帧；使用旧区域节点+新获取/reset调度+原r08可重现新calibration。首次获取延后增加短期unknown，未隐藏；区域/r08算法和门未改。上轮低候选单候选反事实两组legacy各333帧locked→新0，仅软件对照。
- 延续已授权临时入口切换：新e67a6f8d包、perception_human_motion_v1、PID35611；原35319入口回滚保留。30秒290帧仍3低候选，但均不锁定，P50/P95 41.95/97.22ms、约9.65Hz、队列增丢0；driver/bridge/HTTP启动身份和地面/背景/显示地面SHA不变。无人锁定窗口不能证明有人性能；移动椅子/人体效果UNKNOWN。
- 证据 `docs/evidence/2026-10-20_human_entry_gate/` 含36918路径派生baseline（152刷新）、前件/diff、初版及最终回放、LOW_CANDIDATE_REPLAY、CALIBRATION_DIFF/COUNTERFACTUAL、INTEGRATION、包/配置/探针/观测和测试。初版运动中心使用候选metadata的边界在分析中复现，已统一实测来源并补回归；比较器误将簇disposition变化当成员变化的失败日志保留，后逐项区分；STAGED沿用configs_identical字段的措辞由STAGE_CONFIG_AUDIT更正为保护项相同、获取profile明确改变。未改data/junction、未commit/push/reset/checkout/clean、未录会话或训练/下载/调用NPU/开HR-09，confirmed仍关闭。

## 2026-10-20 真人离场后的独立低物体错误续接

- 用户完成走动/站立并声明已离开、无跌倒；60秒533处理帧先263原目标实测、遮挡11帧后同t0001接上先前独立的h000143低候选208帧，其中193suspected。离场后另5秒49帧仍锁低物体。根因为预测门扩至3.910m接纳3.675m残差，错误复用基线/下降episode；不是已修复的缺口连续计时复发，confirmed/event均0。
- 在共享TargetAcquisition的默认human_entry_gate路径增加已知非本目标历史排除：成功目标实测时，其他history至少5次实测且当前地面切向中心距>1.5m才标记，经merge/split谱系传播；持有/遮挡拒绝接管，重新获取时清标签。原始“所有并存簇排除”误伤近身碎片的失败版保留；最终固定候选/history重放精确复现旧533帧，再保留全部263原测量、拒绝208错误续接，无新增测量。未录XYZ，不把此称完整新点云跌倒回放。
- 572核心、17定向、18current、console HTTP、板端3.8/NumPy1.17定向17通过（-B -W error）。完整386帧×两模式×两变体，1544来源核验、1544对坐标显示及120帧因果前缀通过；默认两SHA不变，变化保持仅rejected/reason及clusters.disposition变化，跟踪/成员/历史/区域/标定/跌倒其余值不变。37,067路径派生baseline及源码前件保留。
- 延续临时入口切换授权，激活60文件a3d7233552b97fa69eb3cc03dae2cb4243aa34464202cc73e0bdb69e55405869包，PID36126，旧35611入口回滚保留。实际ROS注册/源SHA/绑核4–7通过，driver/bridge/HTTP及地面/背景/显示地面不变。后20秒189帧均unselected、0suspected、增丢4；冷启动与场景变化使该窗口不能单独证明错误续接修复或性能达标。
- 修正有人性能口径：原目标263帧process P50/P95=88.64/163.05ms、receive→finish=144.58/239.98ms、8.206Hz，46次丢帧全在该段；此前471 locked的77/150ms混入208个小低物体帧。process不含解码/发布，继续固定输入CPU排查。新history无前驱、1.5m内独立物体、混合谱系后的真目标恢复仍UNKNOWN；5次为历史总观测数，非连续分离5帧，移动椅子未跑。
- 证据`docs/evidence/2026-10-20_human_entry_person/`与`docs/evidence/2026-10-20_non_target_history_guard/`含OBSERVATION/POST_EXIT、LIVE_DECISION_AUDIT、LIVE_PERFORMANCE_SPLIT、初/终版回放与字段归因、包/切换/板端测试/POSTCHECK、后观测及SHA。首次后观测参数顺序颠倒在开始前失败，20_EXEC保留后已正确重跑。未改data/junction、未commit/push/reset/checkout/clean、未录原始会话、未训练/下载/调用NPU/开HR-09。

## 2026-10-20 精确冻结背景查询与第二次走动/站稳/离场

- 私有prepare_background冻结cells增加≤8M bool格精确占据表，现场背景4,348,182字节；保留原float64/floor/int64量化及超范围set fallback，先筛范围再减偏移防溢出。普通可变/替换cells与cell_m变化语义不变，不改背景内容或候选门。板端f160/f341背景查询13.81/12.84→2.97/2.95ms，完整候选32.45/32.55→21.63/22.64ms，mask与snapshot完全一致；PC候选17.74/19.11→14.34/15.41ms。为记录输入微基准，不等于现场固定输入因果结论。
- 574核心、18current、console HTTP、板端6背景定向通过（-B -W error）；四份386帧SHA均与上轮逐字节一致，1544来源/1544对显示与120帧前缀通过。初版板端测试因NumPy1.17非有限astype不一定warning失败，已改为原/新同运行时结果或异常一致，失败日志保留。极端int64/负边界/nextafter/空背景/替换与超范围回退通过；深拷贝/pickle可能使私有数组可写但查询值相同，生产无此路径。
- 激活仅改lidar_candidates的60文件7eddd07c1b2dcaca8f50d55c6f492bd62cc0f171af85753ccd0bcc51b317c700包，PID36427；旧36126入口回滚保留，实际ROS/源码/绑核核验，driver/bridge/HTTP和地面/背景/显示地面不变。先20秒193帧全部unselected、31.30/34.37ms、增丢0。
- 用户再次按走动20秒、站稳片刻、离场执行并答“好了”。80秒765处理帧中279首段连续实测，末段另一次遮挡2.28s后单帧31点P90=1.865m新history续接，身份UNKNOWN，不称正常人体恢复；随后lost释放，另6秒58帧均unselected，队列不增长。全程无suspected/confirmed/事件，765候选/显示与764共同RAW头绑定、基线/区域来源检查通过。首锁P90=1.637m、近期净移=.661m；近身拆分/合并未见已知非目标标签误伤前279帧的证据，精确动作时刻/点级人体GT仍UNKNOWN。
- 280锁定process P50/P95/max=76.49/130.41/143.94ms，receive→finish119.93/181.15/256.79ms。首连续279/286源帧约9.410Hz、7丢帧，之前263/309与46丢为不同输入动作，仅现场对照。busy间隙17.50/31.83ms仍混合发布/下一解码/调度；6次掉帧伴随123–141ms计算尖峰，另一次计算68ms但前帧排队129.68ms，不能猜GC或具体模块。零丢帧未达；后续分段定位并处理无前驱单帧续接的可信边界，NPU后置。
- 证据`docs/evidence/2026-10-20_background_dense_lookup/`：37167路径baseline（105刷新）、before源码、定向/核心测试、PC与BOARD_FINAL配对样本、完整回放/INTEGRATION、包/部署/POSTCHECK、POST_FIX/OPTIONAL_PERSON/POST_EXIT、PERSON_ANALYSIS与SHA。removed临时列表优化只省约.075ms PC、compact JSON无CPU收益，均未加入。apply_patch部分写入失败无修改，后成功小补丁/带断言文本替换，最终diff可复现。未改data/junction、未commit/push/reset/checkout/clean、未录原始会话、未训练/下载/NPU/开HR-09。

## 2026-10-20 身份可靠性轮次：采集生命周期、恢复验证与基线统一

- 先建立本轮回滚点：branch `master`、HEAD `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；全仓1898文件基线`docs/evidence/2026-10-20_baseline/BASELINE.json`与151文件源码快照；工作树原有未跟踪生产源码一并纳入，不只依赖Git HEAD。
- 阶段1采集修复：FIFO补删`<sid>/points.bin`、`meta.json`、`.bag.active`并拒绝路径重定向；`server_close`停录并join；`Recorder.start`在Popen失败时把会话转failed；DELETE对extracting返回409。四项本地故障注入修复前3F+1E，修复后capture 49项通过。新增`test_capture_lifecycle.py`。生产链仍无ground/background，演示wrapper/配置/场景地面/背景整理进`scripts/single_target_node.py`、`config/single_target_scene_v1.yaml`、`config/single_target_scene_20261019/`，只入库未部署；bundle 62文件SHA`fede2818…`。驱动默认确认`msg_source:2`、`pcap_repeat:true`且launch未覆盖，板端有效配置未核对，历史“实时”只能称临时入口观测。
- 阶段2裁定：a无前驱新history在0.5–3s缺口内先待验证，0.2s/3帧且残差≤0.8m后建立新id/新generation，不继承旧基线或动作历史；b已知非目标用3s/0.5m有限空间记忆跨一帧消失继续排除，过期后可重获；c默认tracker `size_m=None`使尺寸门失效，“ratio=3只是偏宽”不准确，接入真实size后386帧无变化但ratio=3会拒绝0.5→0.1m局部支撑，故不恢复；d恢复窗口加0.8m边界，31点反例280→279 locked；e三入口统一共享基线3s/15、位置spread≤0.25m、高度std≤0.12m、垂直span≥0.4m，代价是固定回放36帧upright→unknown；f在线解码`preserve_rows=True`保留原始PointCloud2行映射。
- 阶段3采用A1有限非目标空间记忆、A2恢复验证+新binding、A4基线统一；淘汰A3严格尺寸门（无收益且伤局部支撑）；路线B组件级成员拆分因缺点级GT未实施。固定263/208元数据保持263 locked（历史实现471），31点反例279 locked（旧280），物理身份UNKNOWN；263段原实测全部保留。合成保护测试覆盖真目标静止、低姿态、0.2s短缺口、31点/0.1m局部支撑。
- 完整386帧回放`final_adopted/`（与`final_verified/`逐字节相同）partition/orientation SHA`21cb6da1…`/`a879a68f…`；`strict_size/`逐字节相同；`before/`为`35cb3d…`/`496a8241…`。跟踪/获取/区域不变，变化仅在baseline/fall字段。新增恢复不继承旧基线/动作历史的current适配器回归后，重跑`final_adopted`并更新LATEST；current 19项通过。固定反例没有原始XYZ，只有元数据重放，不称完整XYZ跌倒回放。
- 阶段4 PC分段计时：真实386帧locked 258帧接收→发布接受P50/P95/P99/max=45.713/70.254/76.855/82.456ms；候选+背景23.770/35.189/39.242/40.976ms；regions 11.289/19.915/22.019/23.221ms；解码1.831/2.770/3.495/4.786ms。同步消费者queue wait近似0；设备时间未锚定，不能算端到端；板端未重新测量。合成4场景只验证字段/生命周期，不作为性能量级。
- 阶段5只读盘点：可定位雷达点集模型是256×3 person/furniture PointNet shadow（ONNX/PT，SHADOW_ONLY，CPU PyTorch/ONNX同输入max_abs_error=4.53e-06，RKNN NOT_RUN）；RF/XGB为表格CPU模型；没有可运行雷达倒地权重/scaler/RKNN，RGB YOLO不是雷达模型。未训练/下载/调用NPU。
- 验证：核心586、capture 49、calibration 2、current 19、定向identity 4/runtime 5/bundle 3，均`python -B -W error`；证据根`docs/evidence/2026-10-20_identity_reliability/`（WORKLOG、ADJUDICATIONS、PC_PROFILE_SUMMARY、MODEL_INVENTORY、完整回放、测试日志、bundle），部署链差异`docs/human_fall/DEPLOYMENT_CHAINS.md`。未改data/junction、未commit/push/reset/checkout/clean、未登录板端/部署/采集、未训练/下载/NPU/开HR-09。人体precision/recall、身份切换率、跌倒效果、板端实时性、驱动有效配置仍UNKNOWN。

## 2026-10-20 身份可靠性报告与实现边界核查

- 按用户“评价审查一下”核查代码与证据，仅增加机器证据及当前记录，未修生产源码、未切换LATEST。branch master/HEAD c9c4ee421cb0c8a3e4590b8f5730828b093c759a，37493路径SHA基线含非忽略未跟踪文件，见`2026-10-20_identity_reliability_audit/BASELINE.json`。
- 独立重跑核心586、capture49、current19项全部OK（`-B -W error`）；完整386帧orientation/partition SHA仍为a879a68f…/21cb6da1…，逐字节等于final_adopted，跟踪258/12/116、baseline ready227。208帧错误续接的取消来自前一轮，本轮维持263段实测；不得重复计算本轮收益。
- 四组可复现反例：FIFO选中ready后转extracting仍会删除bag/points并置purged（既有并发缺口，新清理范围扩大影响）；Recorder关闭超时使extractor/FIFO/socket清理全部被跳过；共享自动基线跨0.4s隐式缺口仍累计到3s/28样本ready；超0.8m预测残差后静止候选持续到9.9s仍不能重获，并非仅损失3帧+3s基线。
- 证据`2026-10-20_identity_reliability_audit_replay/`含probe_boundaries.py、BOUNDARY_PROBES.json、TEST_RUNS.json、完整回放与SHA_COMPARE.json。删除探针只用TemporaryDirectory，不触碰真实会话；上述缺陷保留待修，下一步优先原子清理状态、异常关闭finally及基线时间连续性。人体/物理效果、板端有效驱动来源和真实恢复率仍UNKNOWN。未部署/采集、未改data/junction或执行Git写操作。

## 2026-10-20 并发清理、异常关闭、基线连续性与恢复诊断修复

- 基线master / HEAD c9c4ee421cb0c8a3e4590b8f5730828b093c759a；完整37,507路径SHA含非忽略未跟踪源码，与审查基线16处文档/审查产物差异、生产源码无后续变化。修改前件与旧LATEST保存在`2026-10-20_concurrency_continuity_fix/preimages/`，不依赖HEAD回退。
- 先用确定性交错复现旧FIFO删除已进入extracting的会话、清理期间状态迁移、部分删除后仍可抽取、Recorder异常跳过其他关闭；旧基线三入口0.4s无回调仍ready；旧恢复诊断把未累计验证的超门候选报pending。旧实现失败日志保留，未放宽断言或改历史证据。
- FIFO/DELETE共用SessionStore安全清理，线程+进程会话锁覆盖作业/迁移，数据库锁内重查、持久化清理意图、白名单删除、最终登记；部分失败保留cleanup_pending并优先重试，阻止抽取/传输。HTTP文件流和抽取持会话锁；录制由同一看护线程持锁完成spawn到收尾，新增Event回归覆盖原请求→看护交接窗口。HTTP POST只创建且拒绝清理内部字段，extra更新不覆盖旧状态，PATCH不能直接置purged。真实会话未执行删除验证，Windows临时junction/子进程互斥通过。
- 关闭先发停止通知，Recorder/extractor/FIFO/socket逐项清理并保留首个异常。保存实际watcher句柄，重复close继续join，超时以shutdown_state报告仍存活线程/socket；同步抽取超时后可能仍在处理当前会话，不能宣称已退出。正常关闭、真实线程超时、其他清理异常、重复关闭和socket状态均回归。
- 共享基线pending按相邻实测源时间、HF-06默认0.3s连续性门判断；缺口后当前有效帧作为新段起点，显式缺测/非法/重复/倒退时间不跨段，binding变化废弃旧基线。三入口边界/整数纳秒/nextafter及manual ack回归通过，ready同binding静止/低姿态/短遮挡保留。反例旧6.5s ready/28样本→新pending/14样本；继续输入后8.3s ready，延后1.8s/18帧pending。
- 恢复只修诊断，不放宽策略。固定同一修复后collector，313组旧/新恢复裁定逐帧比较，跟踪/实测/新旧track及generation/基线决定零变化，1248帧拒绝原因纠正。0.8m为相对预测位置残差；≤0.5s短缺口可直接续接，恢复窗口内合法候选第3次观测/0.2s建立新binding，不能说至少损失3帧。2.9s附近可能来不及验证，超门/超时静止及低姿态目标可整个10s观察窗不恢复；移动可重获但未必有稳定站姿，31点/低姿态新身份不能继承或自动重建旧基线。全部为合成软件行为，人体召回/真实身份正确率UNKNOWN。
- 完整orientation/partition各386帧逐字节零变化：258 locked / 12 occluded / 116 unselected，baseline ready227，upright209 / unknown171 / low_posture_unclassified6。首ready仍f159/16.482590s，ready延迟变化0、unknown增量0；该输入无>0.3s源缺口。partition SHA 21cb6da1b1438b80bbda40e0f06ec3dc9fa651782c74f8d43d7bc40d66326ef6；orientation SHA a879a68feff9f75ce5fd88eb1175008c12d233a1cd21644c84c8f2d715cca984。两变体全386帧来源行/区域坐标和120帧因果前缀通过；533帧元数据保留263原实测，765帧元数据保留279实测并拒绝31点单帧（原始XYZ未录，不作物理验证）。
- 核心599、capture66、calibration2、候选及采用后current19、fetch13均-B -W error；console JS21/Python8、capture UI33、fall UI20、preview UI55通过。板端源码Python3.8语法检查通过；未在板端NumPy1.17重跑。完整对照/候选集成后，LATEST从identity_reliability/final_adopted切到concurrency_continuity_fix/adopted，新旧输入/地面相同，帧SHA相同、源码绑定更新，见ADOPTION.json；旧输出和回退前件全部保留。
- 机器证据统一在`docs/evidence/2026-10-20_concurrency_continuity_fix/`，包括BASELINE、前件、旧失败日志、新测试、313组恢复账本、基线反例、完整两次回放、FRAME_COMPARE、GEOMETRY_INTEGRATION与ADOPTION。已更新PROJECT_STATE。下一步独立核对板端有效输入来源及真实场景，真实人体/物理效果UNKNOWN；本轮未操作板端、data/junction、历史证据、驱动/网络，未commit/push/reset/checkout/clean、部署/采集/训练/下载/NPU/HR-09。
## 2026-10-20 板载实时只读快照（用户要求打开查看）

- 用户要求查看板载实时识别状态并打开页面。已在默认浏览器打开 leveled 实时页（`prefix=/single_target_live/`、
  `points=/single_target_live/display_points`）；仅用 `docker exec slam-localization rostopic echo` 读 `/single_target_live/state`，
  未重启节点、未改配置/驱动/网络/页面，未录原始点云、未采集/训练/下载/NPU/HR-09。
- 运行体：PID 2765358，`background_dense_20261020_7eddd07c/run_optimized.py`，已运行 4h42m；HTTP 8936 PID 2598117、driver 2957、
  foxglove_bridge 2960 未变。16:52–16:56 观测：`track_status=unselected`、`acquisition=searching/no_qualified_candidate`。
- 3 个候选均被入口门拒绝：c0000 高度 P90=0.479m（height_out_of_range）；c0001 33–38 点、高度层 0.3–0.6m（insufficient_height_span）；
  c0002 P90=0.869m 但 7 帧/0.62s 净位移 0.036m（entry_motion_not_observed，门 0.3m/1.2s）。基线 idle、跌倒 unknown、事件 0、区域无当前实测目标。
- 性能：20 帧 process min/p50/max=28.5/30.8/44.0ms，receive→finish=39.4/46.7/62.0ms；30s 窗口 312 帧 @9.59Hz、queue_dropped 增 0；
  累计 163523 帧、自起播累计丢帧 10。传感器 cloud/imu/device 均 fresh。
- 边界：无锁定不等于无人（站立不动不满足 0.3m 运动门）；本轮只覆盖空目标窗口，人体身份/召回与跌倒效果仍 UNKNOWN。
- 证据 `docs/evidence/2026-10-20_live_look/`：SUMMARY、STATE_ECHO、STATE_WINDOW、PROCESS。未改 data/junction、未 commit/push/reset/checkout/clean。
## 2026-10-20 现场试用版发布整合（打包/生命周期/部署/联调）

- 先存前件：`docs/evidence/2026-10-20_release_integration/BASELINE.json`（758 路径 SHA，含未跟踪源码；16GB 研究树不在范围）+ `preimages/` 18 个待改文件。没有用 Git HEAD 判断版本。
- 唯一打包器：`prepare_single_target_bundle.py` → 105 个 tar 成员（103 组件 + RELEASE + MANIFEST）确定性包，SHA `307fec85…`，release `01a8d2b9df8cfcd8`，page `90ba082709c8`；纳入 fall/capture/区域/解码/页面/共享静态资源/record_session，`RELEASE.json`+`MANIFEST.json`；页面 `?v=` 改内容哈希、写 `hf-page-version`，缺资源即失败。重复构建字节一致；仓库外解包去掉开发 PYTHONPATH 后可导入，fall 与 capture 的 `core` 不串用。
- 生命周期：`deploy_human_fall.sh` 改为消费标准包（不再第二套复制清单），补 `stage/preflight/activate/profile-init/verify-input/probe-scene/start/restart/stop/status/version/health/rollback/runs`；`current` 单一生效绑定，暂存不切页面；重复 start 拒绝、错 pid 拒绝且不 kill、stop 先停录再按 28s 预算收尾并检查录制子进程+端口、每 run 独立目录与限额日志。
- 现场配置：`init_site_profile.py` 建 `profiles/site_lab_20261020/profile.json`（三工件 SHA、`physical_verified/runtime_eligible=false`、未知项列明）；`release_config.py` 生成 effective node/capture + `runtime.js`，采集 `record_script` 指向 release；`verify_input_source.py` 读真实驱动 → 本现场 `live_lidar`（msg_source=1、无 pcap 打开、驱动 PID102/config SHA `bd428a1e…`），仓库默认 msg_source=2 未当现场事实。
- 页面/记录：页面新增运行版本/输入来源/运行记录/疑似提示、区域拒绝原因、基线样本数；`runtime.js` 绑定话题，页面比对 page/release 版本防旧缓存；`core/run_record.py` 写 `run_events.jsonl`（目标/基线/跌倒/可观测性/原因/输入/worker 迁移、`suspected_notification` 单调 id、30s 性能窗口），算法事件语义不变。
- 测试：核心 631（含 release/freeze/server 23 项、run_record 9 项）、capture 69、calibration 2、current 19、fetch 13、console 21JS/8Py、fall UI 20、preview 55、capture UI 33 全过（`-B -W error`）。386 帧 orientation/partition frames+summary 与 adopted 逐字节相同（`a879a68f…`/`21cb6da1…`，258/12/116），计时只比结构。
- 板端：旧临时节点 36427、旧采集 26094、旧 8936 服务 32002 核对命令行后停止（`state/legacy_cutover.json`）；release 53172/53180/53192 起于 `runs/20261020T104753Z_3526a166`，`health` OK、worker healthy、queue_dropped 增 0、空场 9.6Hz。90s 锁定窗（105 点低目标，`low_posture_unclassified`，基线 failed）process P50/P95≈40/57ms、receive→finish≈49/64ms、丢帧 0；该目标不是已验证的人。运行记录 32 个 30 s 窗口（962 s/9277 帧）：process P50/P95≈36/59 ms、receive→finish≈46/69 ms、queue_age≈10/15 ms、丢帧 0、9.54–9.66 Hz。
- 生命周期实测：沙箱 stage/activate；篡改→manifest 拒绝；pid1 伪 pid→拒绝不 kill；重复 start→拒绝；回滚旧手动降级版→停净+明确能力差异，回滚新版本→恢复启动。采集录制→停止→ready（85/47 帧），录制中 stop→先停录→shutdown_state 全清→端口释放→重启续抽 ready；`record_config: null` 被平铺 YAML 当字符串导致每次录制 `--config null` 失败的缺陷已修并加 3 条回归。
- 场景适用性与重冻结：旧工件 `probe-scene` 30 帧判 `REVIEW`（地面仍适用：支撑 17.7%、残差 P95 4.0cm；但持续前景约 770 点/2 候选）。用户确认空场后 `freeze-scene` 采 50 帧重冻结：地面 `valid`、inlier 0.62、法向 `[-0.4204,-0.0125,0.9073]`/offset 1.2963（与 2026-10-19 的 `[-0.4212,-0.0155,0.9068]`/1.3097 基本一致，说明是背景陈旧而非安装变化）；静止守卫后半窗覆盖 0.9952，冻结后同窗前景 0/0。新 profile `site_lab_20261020_v2` 激活重启后 `probe-scene` 40 帧判 `CONSISTENT`（前景中位 21 点），同一场景不再锁定重冻结前那个 105 点低目标。旧工件/旧 profile 全部保留，未在线学习有人场景。
- 浏览器与页面服务（本轮补）：Windows Chrome headless + CDP 实测固定入口（自动连接）——点云 12,000/49,108 抽样、显示 9.8 Hz/呈现 10.0 Hz、IMU 227 Hz、设备 71、运行版本=页面绑定=`01a8d2b9…`、输入来源“实时雷达 · 已观测 … 帧”、区域原因 `NO_CURRENT_MEASURED_TARGET`，截图/DOM 存 `evidence/browser/`。过程中抓到并修掉两个真实缺陷：自动连接早于 `human_fall.js` 导致 HF 话题不分发（改晚绑定派发）；节点上报 release 目录名与页面内容 id 不一致（改发 `RELEASE.json` 内容 id，目录名另存）。新增 `serve_webui.py`（全响应 `no-cache`）替代 `http.server`，页面版本不符时用 `?v=` 自动重载一次（sessionStorage 防循环）。
- 现场联调（本轮补）：①浏览器保持打开、真实 `restart` 后自动重连，run id `cffb0074`→`25f6601c`，无重复提示；②录制中并发下载 64.6 MB 旧会话（0.7 s）继续录制，重复起录 409，停止后 extracting→ready（16 帧/22 MB）；③`rollback` 往返 RC13↔RC14 时 `binding.json` 与 `runtime.json` 同步改写——修掉“回滚后 binding 滞后”的缺陷（`_write_binding` 供 activate/rollback 共用）。耐久采样 42.9 min/258 样本，`queue_dropped` 恒 0、worker 全 healthy、RSS 58–68 MB。最终固定包 `01a8d2b9df8cfcd8`（SHA `307fec85…`，RC14）。
- 未验证：真人锁定性能、身份正确率与真实跌倒效果、疑似提示整链（仅单测）、一工作日耐久/容器重启、物理配平与点级 GT（全部 UNKNOWN）；浏览器只验证了空场状态。证据 `docs/evidence/2026-10-20_release_integration/`（BOARD_RUN、REPLAY_PARITY、bundle、tests、page_check、browser/、scene_probe、live/locked observation、durability_sample、current_run、rb_*/stop_* 日志）。未改驱动/网络/固件、未动 data/junction、未 commit/push/reset/checkout/clean、未训练/下载/NPU/HR-09。

## 2026-10-20 显示配平绑定修复（本地完成，尚未部署）

- 用户截图显示“RAW · 等待配平绑定”；只读核对页面 ID `ground-only-730c58260781f29d` 与节点 `ground-only-4a6062deb6a80d1d` 不同，平面参数在匹配容差内一致。根因是冻结器用文件字节 SHA，而节点用规范 JSON 内容哈希；不是全量模式或物理未验标志阻止显示。
- 前件：master/HEAD `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`，37,808 个 tracked/非忽略 untracked 文件 SHA，4 个源码/测试和文档前件保存。冻结器改复用节点标定生成；显式 ID 错配在写盘前拒绝；固定 LF 解决 Windows 文件 SHA 自检。profile 创建/预检复用实际 core 启动绑定，检查 ID、SHA、source、显示矩阵及元数据，保留显式标定优先级。
- 新增 5 个发布回归，旧实现 8 处断言失败；修复后核心 636、capture 69、calibration 2、UI 20、最终发布 28 项通过（Python -B -W error）。包内 Python 3.8 语法检查通过，未做新版板端运行验证。
- 新跑 orientation/partition 各 386 帧，frames/summary 与 adopted 逐字节相同（258/12/116、ready227，SHA `a879a68f…`/`21cb6da1…`）。真实状态快照的离线 JS 匹配旧 ID false→修正 ID true，错 frame 仍 false；不称上线浏览器或人体效果验证。
- 待应用标准包 RC15：release `666ad0eb40a64d4d`，105 成员、SHA `4a8b2f13…`，重复构建一致；修正显示工件 SHA `6f342fdf…`。现场仍 RC14/profile v2；后续需新建修正版不可变 profile，复用原地面/背景并保留旧 profile，再部署/重启核对显示。
- 证据 `docs/evidence/2026-10-20_display_ground_binding_fix/`：BASELINE/preimages、旧失败/新测试、完整回放与 REPLAY_PARITY、live_binding_before、DISPLAY_BINDING_CHECK、BUILD/bundle。当前没有原始录制或真人测试，也未部署/启停板端；未动 data/junction、历史证据、驱动/网络，未执行 Git 写操作或训练/下载/HR-09。人体/物理效果继续 UNKNOWN，confirmed 关闭。

## 2026-10-20 配平修正版部署、新 profile 与服务重启

- 用户明确授权部署/创建修正profile/重启；所有 runtime 组件重新打包与待部署 RC15 字节相同（SHA `4a8b2f13…`）。保存旧 current/profile/进程/工件 SHA 与本轮文档前件，证据 `docs/evidence/2026-10-20_display_ground_binding_deploy/`。
- RC15 stage→新 profile 独立验证→current 仍为 RC14 时 stop（capture优雅关闭、端口释放）→原子切 profile pointer→preflight/activate/start。现 release `666ad0eb40a64d4d`（`20261020T141358Z_666ad0eb`），run `20261020T141659Z_c6ef6080`，PID `54688/54696/54708`，selected=running、health OK、live_lidar。
- 新 profile `site_lab_20261020_v2_displayfix_r1`/scene `scene_lab_a_v2`：地面 `730c5826…`、背景 `64b71b1c…` 与旧版逐字节相同；仅修显示 ID 为节点的 `ground-only-4a6062deb6a80d1d`，显示 SHA `bd4954e8…`，板端26项检查通过。原地面无需重新采集或重拟合；物理/confirmed门均false。初次准备因本地预览JSON转存与板端整数/浮点字节格式不同被拒绝，数值一致已验证；未激活目录保留，新建_r1完成。
- HTTP新runtime/页面/显示工件一致、no-cache；实时原始/抽样帧头与state依现有wire_seq映射匹配，生产JS全量/抽样关联和配平检查全true；97条状态约10s无新增queue_dropped、worker全healthy。用户刷新后确认按钮“配平候选 · 未物理验证”。自动浏览器debugger连接失败，未取得独立截图；来源明确记录在BROWSER_CHECK.json。
- 发布28、fall UI20本轮重跑通过；前轮核心636/capture69/calibration2和386帧字节一致证据保留。旧/新release全manifest通过，旧profile工件完整；driver PID102/config SHA `bd428a1e…`未变，capture未录制、会话登记仍28。
- 核对脚本初次误取runtime路径、误认为display与RAW共用seq、误要求capture命令为绝对路径；已按现有部署/visualization契约纠正并重跑，失败日志保留，没有修改产品逻辑。本轮只读状态/帧头检查未保存点云负载，未开始真人测试/原始录制；未动data/junction、历史证据、驱动/网络/固件，无Git写操作或训练/下载/HR-09。人体/物理效果仍UNKNOWN，下一步协调单人基础测试。

## 2026-10-20 跌倒识别闭环验收与躺姿证据门

- 用户要求“继续开发”，前提是人体框定/跟踪先稳住。上一轮已用 591 帧真人录制（走15s→走动约20s→站稳→举手→离场，无跌倒）核对框定不变量并通过；本轮把跌倒识别从单测推进到**真实点云闭环**：同一 MCAP 的静态场景与时间戳，只把被跟踪者点集替换成合成刚体下跌（绕脚部水平轴转到躺平，0.4/0.8/2.5 s 三种速度；或压到 50% 高度的深蹲），喂给同版本 RC15 核心（同地面/冻结背景/`perception_single_target_v1.yaml`）。合成运动不是真人跌倒 GT。
- 检测结果：站姿快倒/极快倒/慢滑倒、基线尚未 ready、走动中（20/25/35 s 三个步态相位，其中两次仅 30–41 点可见）都能从注入到 `suspected` 约 1.8–2.1 s（落地后 1.0–1.3 s）；`confirmed`/事件恒 0（诚信门未开）。`descending` 状态实际不出现——落地那帧高度已 ≤0.7 m，状态机直接 upright→低位→疑似，属既有顺序。
- **发现并修复假阳性**：持续深蹲（实测下降 0.55 m、保持 >1.5 s）修复前被判 `suspected`，但其几何是“矮而窄”（顶部 0.92 m、水平跨度 0.16 m）；躺倒几何是顶部 0.21–0.36 m、跨度 0.07–1.28 m。新增躺姿证据门：`low_min_duration_s` 到点后还必须 `horizontal_extent_m ≥ lying_min_extent_m(0.6)` 或 `height_m.max ≤ lying_max_top_m(0.7)`；缺失几何不算证据。新原因码 `low_posture_without_lying_pose` / `lying_pose_supported`，`LIMITATIONS` 增 `lying_pose_required_for_suspected`。阈值写入 `config/perception.yaml` 与现场变体 v1。修复后深蹲→低位未分类，七个跌倒场景结论不变（部分可见靠“顶部低”通过）。
- **未修复的跟踪缺陷**：`fall_fast_walking`（30.0 s 注入）在 30.29 s 身体裂成 420/482 两簇、均 `support_conflict` 且同一前驱 history，跟踪器按“近等距双候选=ambiguous”放弃锁定后 `unselected` 且无法再获取，整段无提示；其余四个相位正常，说明与步态相位相关。本轮按既有身份策略**不改** `ambiguous`；后续正确做法是在候选层合并“同前驱+互不重叠支撑”的碎片，而不是放宽 ambiguous 或让跟踪器在近等距候选间挑选。
- 回归：核心 640（636+4 个躺姿用例）、capture 69、calibration 2、current 19、fall UI 20 全通过（`-B -W error`/node）。固定 386 帧回放重跑并采用为新 `current/LATEST.json`（`docs/evidence/2026-10-20_fall_scenario_chain/adopted`）：跟踪/基线/跌倒**判定逐帧不变**（258/12/116、unknown171/upright209/low6）；字节差异仅每帧多一条 limitations，以及 368–370 三帧低位原因码改为更准确的 `measured_descent`+`low_posture_without_lying_pose`。
- 新包 `bundle/human_perception_release_rc16.tar`（105 成员/2,150,400 B，SHA `9ae2f86e…`，release `541e70fa3dc8899a`，page 仍 `90ba082709c8`，包内 Python 3.8 语法通过）；**未部署、未重启现场**，部署仍需用户明确要求。证据 `docs/evidence/2026-10-20_fall_scenario_chain/`（README、scenario.py、compare.py、各场景 SUMMARY/timeline、COMPARE.json、adopted 回放、4 份测试日志、bundle）。真人跌倒召回/精确率、躺下与跪倒/靠墙区分、点级 GT、物理配平仍 UNKNOWN；未动 data/junction、历史证据、驱动/网络，无 Git 写操作或训练/下载/HR-09。

## 2026-10-21 稳定框定能力核查与下一步开发计划

- 本轮只制定计划和核查能力，未实施分簇修复。复核 591 帧真人基础动作录制：18.0714–58.1811 s 连续 388 帧同一 `t0001` 实测锁定，随后 28 遮挡/1 丢失；初始 174 未选择不能全部算作人体识别失败，也不能把 388/591 当准确率。原始 MCAP SHA 重新匹配 `d79c8cfb…`。结论限于该现场单人基础动作，人体点级纯度/跨场景识别仍 UNKNOWN。
- 顺序已写入 PROJECT_STATE：①在候选层研究已锁目标碎片的唯一归属和安全归并，保持 ambiguous，不能只靠“同前驱+当前点行互斥”；②30 s 失败+全部 10 个合成场景+591/386 帧及竞争/粘连/时间/标定负例回归；③检查掉帧/过期观测下基线连续性与耗时；④可信目标保持后再推进跌倒与其它低姿态区分。已有 30.2926 s 分簇掉锁仍未修，合成运动不是真人跌倒 GT。
- 重跑核心 640、current 19 全通过（`-B -W error`）；复用现有完整点云回放脚本、输出重定向至本轮新证据，591 帧跟踪/基线/跌倒判定与冻结 RC15 0 差异、0 疑似。线上/冷启动离线的 14 条基线转移差异仍受丢帧/回调与前史缺失限制，不称完整线上等价。
- 证据 `docs/evidence/2026-10-21_tracking_next_plan/`：全仓 tracked+非忽略 untracked SHA 基线（排除 data/junction）、项目记录前件、PLAN、TRACKING_AUDIT、测试日志、full_replay、SHA。仅改项目记录，算法/参数/LATEST/历史证据未动；未部署、采集、重启或联系现场，无 Git 写操作/训练/下载/HR-09。最近现场记录仍 RC15，RC16 未部署。

## 2026-10-21 总控制台集成「实时锁定」现场页面

- 用户直派（附桌面 `总控制台.lnk`）：「把实时锁定项目 webui 集成进去」。快捷方式指向 `pc_apps/console/dist/Console.exe`，本轮只改控制台壳页/启动器/用例/说明并重打包，未动算法、参数、LATEST、profile 或板端。
- 入口：`console.html` 新增「实时锁定」卡片（分组 板端与平台、该组第一张），直连 `http://192.168.31.58:8936/human_fall/`；页面按 `location.hostname` 连 `ws://…:8765`，因此不能用本地代理（会改掉 hostname）。沿用 no-cors 探活：板端离线提示「当前不在内网，无法连接板端实时页面」，跨域仍不读 iframe location。板端换 IP 用 `INNO_BOARD_HOST`（`console_gui.py` → 壳页 `board_host=`，只接受主机名/IPv4 形状，非法回落默认）。
- 测试：板端/本地入口断言从固定下标改为按名字取卡片（只有「会话回放=0」是契约，联合录制 ?sid 依赖它）；JS 23（21+2）、Python 9（8+1）通过。新增 `?board_host` 覆盖/非法回落、探活成功/失败两条路径用例。
- 验证：①headless 壳页 DOM 断言 `ok=true`（选中「实时锁定」、iframe 指向板端页、错误层隐藏、板端 `hf-page-version`=`runtime.js.page_version`=`90ba082709c8`）；②打包后从 exe 内 CArchive 取出的 `console.html` SHA 与源码相同（`052f5b7d…`），含新卡片；③`--check-startup` 的 real_fall/plane 通过，`ok=false` 仅因旧 pointset 数据不在本工作区（旧 exe 同为 false，非本轮回归）；④真实 WebView2 实拍：首页出现「实时锁定」，点击后在控制台窗口内渲染实时页面（ws 8765、显示 9.8 Hz/呈现 10.0 Hz、抽样 12000/49075 帧、IMU 227 Hz、release `666ad0eb40a64d4d`、场景 `scene_lab_a_v2`、页面 `90ba082709c8`、run `20261020T141659Z_c6ef6080 · 记录 1438`、配平「配平候选 · 未物理验证」）。
- 产物：`dist\Console.exe` 重打（187 MB，SHA-256 `141d93a3d80683b5a96f8057d485c897c752c562b80f7fd3601ad39d195e7d2c`，旧 exe 保留为 `build_prev\Console_20261018.exe` 回退）。证据 `docs/evidence/2026-10-21_console_live_integration/`：README、VERIFY.json、BUILD.json、`console_dom.html`、3 张截图（首页 / 内嵌实拍 / 板端直连）、两份启动自检、2 份测试日志、`verify_console_entry.py` 与 `capture_console_window.ps1`。截图只证明嵌入与 bridge 连接，不证明配平或人体效果；「新窗口」按钮与既有卡片同受 pywebview 吞 window.open 限制。未部署/重启现场、未动 data/junction、历史证据、驱动/网络，无 Git 写操作或训练/下载/HR-09。

## 2026-10-21 完善人体框定与跟踪修复计划

- 按用户要求细化修复计划为 docs/TRACKING_REPAIR_PLAN.md：目标、已核实根因、受限归并资格、一次历史提交、权威 observed/索引域、完整连续场景、负例、三入口同步、性能和采用条件；本轮只制定，不实施算法。
- 新确认 node_runtime/ReplayPipeline 丢弃第三返回 observed，若只在 acquisition 归并会 locked 但下游无观测；current 的局部 evidence_indices 不等于会话 source_rows。计划选保留原始簇 snapshot、组合实测单独表达并带成员映射，公共几何从并集实测点重建，历史每帧仅提交一次。
- 相关 95 项 -B -W error 测试通过；重新跑 fall_fast_walking 395 帧，仍在 30.292645942 s 掉锁且无疑似。合成两表面反例展示“干净同前驱+互斥当前行”仍无法证明同对象；293 帧拓扑也会变化，完整下跌/保持段必须在候选历史下重算，不以救回292帧冒充闭环。
- 证据 docs/evidence/2026-10-21_tracking_repair_plan_detail/：新重算全仓 tracked+非忽略 untracked SHA（排除 data/junction）、项目记录前件、CODE_FACTS、95项测试、失败回放、规则反例与 SHA。仅改计划和项目记录；保留已有控制台工作、算法/参数/LATEST/现场版本，不部署/采集/重启，不联系板端，无 Git 写操作/训练/下载/HR-09。下一步从反例成员诊断与三入口观测契约等价改造开始。

## 2026-10-21 用户截图“乱锁定”范围核查与计划补齐

- 用户问当前多框画面是否会被修复。核对 human_fall.js，黄色 c000* d= 是候选，实际目标另按 track_id 绘制；裁剪图无对应同帧状态，不能直接判定实际误锁。原计划偏保持碎片，现补入 TRACKING_REPAIR_PLAN.md §0：先诊断实际误获取、背景适用性和可见成员假运动，入口修复先于保持归并，显示候选/目标区分单独验证。
- 纯合成入口计算确认：固定 XYZ，仅改变可见 source_rows，水平/竖向两种都在1.6s被 unique_height_and_motion 锁定t0001。这是入口软件边界反例，非本截图的完整点云复现/真人GT；单改水平运动门仍不足，不能靠隐藏框或不再获取任何目标消除误报。
- 入口/获取/身份37项（-B -W error）、fall UI20项通过；原591帧重放与冻结RC15判定0差异、0疑似。证据 docs/evidence/2026-10-21_false_lock_plan_scope/（新全仓SHA/前件、原截图、显示代码定位、两种反例、测试、回放、SHA）。
- 本轮只补计划与记录，未修生产算法/参数/LATEST、未联系/部署/重启/采集现场，无Git写操作/训练/下载/HR-09。下一步先固定实际获取账本和入口假运动反例，保护原真人进入，再推进碎片保持；跨场景人体语义仍UNKNOWN。


## 2026-10-21 人体框定修复开发首轮：入口假运动与观测契约

- 用户明确开始开发。固定 master/c9c4ee4、全仓 tracked+非忽略 untracked SHA、源码/记录前件；修 node/ReplayPipeline 自动 observed 消费、source_rows/局部 evidence_indices 的 offset 契约，拆出无副作用历史 analyze 与共享实测几何重建。未启用碎片归并、未改 ambiguous。
- 入口用有界实测支撑比较静止/平移残差（512点/历史帧、64帧上限、0.1m容差，新命名 v2，旧冻结配置不改）。水平/竖向固定 XYZ 只变可见成员反例：原 f16/t1.6s 获取，现全程不获取；新增密度/边界/行排列/因果前缀/重复回归。保留两次拒绝候选：全局未解谱系门导致真人全拒、过严支撑改善门导致386延迟1帧，均已纠正，失败证据不覆盖。
- 最终核心649/capture69/calibration2/current19、fall UI21/preview55/capture UI33/console23JS+9Py及replay/panel/detect/pipe JS通过。591帧所有业务state字段0差异（388 locked）；386×2变体全部业务字段0差异（258/12/116），history仅新增row_domain；10合成场景与冻结RC16 repo_*全帧相同，7疑似/两深蹲行为保留，confirmed/事件仍0。MCAP实际SHA重核匹配d79c8cfb…。
- **未解决**30.292645942s掉锁：292帧420点片自身支撑覆盖仅10.34%、前驱覆盖4.14%，另一片60.81%/31.03%，前驱带144–155帧留下的未解谱系。新同输入双解释反例证明同前驱+互斥行不足，故没有把通用归并接入生产或清洗谱系。继续研究支撑组织和关联证据；本轮不称整条跟踪修好。
- 页面增候选诊断开关，实际目标突出并标实测/预测，候选列表及拒绝原因保留；离线Chrome录制状态fixture测试切换不改状态/候选数、无JS错误。PC入口基准新P50/P95/max≈0.73/5.46/6.45ms（原0.66/0.78/5.57ms），残差优化前P95约18.6ms；峰值traced约6.71MB，状态新增最多220B。不是板端或全进程内存结论。
- LATEST绑定本轮完成的release_current；标准包release2932010e1b9347a8、page26d5ca935685、SHA1ccc0527…、105成员/2,150,400B，重复构建/manifest/Python3.8语法通过。证据docs/evidence/2026-10-21_tracking_repair_dev/；旧失败、旧包和旧证据保留。未部署/采集/重启/联系现场、未动data/junction/驱动/网络，无Git写操作/训练/下载/HR-09；现场仍RC15，人体/点级/真人跌倒/物理效果UNKNOWN。下一步C2继续定位，不需要用户逐项批准。


## 2026-10-21 支撑碎片组合修复（阶段一）+ 动态 ROI 消融（阶段二）

- 用户直派连续开发：先修人体点云碎裂导致的关联歧义/身份中断/掉锁，再在修复后的稳定基线上做动态 ROI 独立消融。读 AGENTS/PROJECT_WORKFLOW/PROJECT_STATE/PROGRESS 与上一轮证据后按符号定位；branch `master` / HEAD `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`，全树 38,576 路径 SHA、14 个将改源码前件、MCAP `d79c8cfb…` 与两会话绑定记录在新证据根。未 commit/push/reset/checkout/clean，未部署/采集/连接板端，未改 data/junction、驱动/网络、冻结配置，未训练/下载/HR-09。
- **阶段一（已修复）**：新增 `core/support_composition.py`：以“已实测锁定目标的前驱支撑锚点 + 并集覆盖 + 新增上限 + 单刚体残差（有界 ICP，行序无关采样）+ 人体包络 + 间隙连通 + 竞争/外来支持排除”判定受约束碎片组合；`CandidateHistory` 拆成无副作用 `analyze` 与唯一提交点 `commit`；`TargetAcquisition` 先分析后组合、每帧只提交一次，通过后用实际接受行号并集经 `rebuild_candidate` 重建全部几何（候选 ID `g0000`，保留原始候选快照与 unresolved ancestry）；node_runtime/ReplayPipeline/current 均传入同一 `rebuild` 闭包并消费 authoritative observed。新增命名变体 `perception_single_target_v3.yaml`（组合参数在 `acquisition.composition` 内），`default/geometry/perception/v1/v2/prod` 字节未变。
- 原失败 `fall_fast_walking`：30.292645942 s 的 420/482 双碎片 + 独立 59 点簇不再掉锁；目标点集 902→893→822→847→729→277（组合 292–295、297+），30.5043 s 低姿态、32.0550 s suspected，confirmed/事件 0；独立 59 点簇 395 帧从未进入目标（`MEMBERSHIP_VERIFY.json` violations=[]）。10 个合成场景中 9 个逐值不变（7 个可疑似首时刻相同、2 个深蹲不疑似），原失败场景恢复。
- 591 帧真人录制：track/fall/baseline/observability 逐帧 0 变化（388 locked/28 occluded/1 lost/174 unselected；fall 433/152/6）；仅 10 帧实测点集变化（各新增 34–115 个目标自身碎片实测行，无预测/补全点），速度/特征/区域随之变化、`history_id` 计数位移。386 帧 current orientation/partition 除新增 `acquisition.composition` 诊断外逐字节一致；`current/LATEST.json` 按真实重跑更新到 `round8_current`（RUN.json source/core SHA 与磁盘一致，current 19 项含 Store 契约通过）。
- **阶段一冻结基线**：`docs/evidence/2026-10-21_split_fragment_repair/BASELINE_FROZEN.json` 绑定源码/配置/输入/完整输出；组合开销（386 帧、交错 3 轮）完整 step P95 +0.6%、P50 +4.8%。
- **阶段二（ROI 消融，结论：不建议采用）**：新增 `core/roi.py`（SEARCH/LOCKED/LOST/RECOVER 四状态、源时间、预测不二次积分、地面切平面圆形+高度带、非法半径/basis/时间显式处理）、`build_snapshot(roi=None,timings=None)`（掩码在全帧 stride/距离门之后、去噪之前，索引不重编号，ROI 关闭不增字段）、`ReplayPipeline` 独立 `roi` 段、`scripts/roi_ablation.py`、`scripts/roi_timing.py`、`config/perception_roi_v1.yaml`（默认 `enabled:false`）；node_runtime 不读 ROI，current 未因 ROI 修改。预注册后开发集（386 帧）跑 A/C 与变体并冻结 C2（margin 0.5），仅在留出集（780 帧）验证。
  - G1 通过：ROI 关闭 vs 无 roi 段逐帧载荷一致（无排除字段）。G2 通过：留出 357 锁定帧目标行缺失 P95/max=0/0，无低于最小点数帧，掩码对 916,813 目标行排除 0。G3 通过：0 新增掉锁/lost/ambiguous/track_id。G5 通过：10 场景躺姿缺失 P95/max=0/0，low/suspected 时刻不变。G6 通过：负例单测。
  - **G4 失败**：留出 C2 完整 step P95 39.83→32.67 ms（−18.0%，<25%）；开发 C2 +5.1%、默认 C +36.1%，P50 基本不变。原因：目标靠近传感器，2.2–2.5 m ROI 仅裁掉约 6.6%（P50）掩码输入点，控制器+掩码约 1.4 ms/帧，与被裁工作量同量级。B 臂（固定 RAW 盒，离线先验）点集/跟踪与 A 一致但不可在线部署。ROI 不进入发布包、板端未启用。
- 测试：核心 689、capture 69、calibration 2、current 19 全部 `-B -W error`；fall UI 21、preview UI 55 JS 通过。证据：`docs/evidence/2026-10-21_split_fragment_repair/`（REPORT、BASELINE_FROZEN、PARITY、逐帧/组合帧/成员、10 场景、测试日志、SHA）与 `docs/evidence/2026-10-21_dynamic_roi_ablation/`（预注册、A/C/C2/A_off/B、COMPARE、TIMING、G5、CONCLUSION、SHA）。板端性能、人体语义/点级 GT、真人跌倒效果仍 UNKNOWN；现场仍 RC15，未部署。

## 2026-10-21 碎片组合与动态 ROI 代码审查

- 用户要求审查；只读核查两阶段实现、配置、证据与三入口调用链，未修生产代码。branch master / HEAD c9c4ee421cb0c8a3e4590b8f5730828b093c759a；关键源码 SHA 与阶段一 FINAL_CODE_BINDING.json 对应值一致。
- 新增机器反例确认三处缺口：①rigid_fit 用 moved 求增量变换却重新作用于 src、未累计，二维平面纯平移 0.2 m 的 RMS 在 1 次约 0、默认 12 次约 0.2 m；②组合保留所有含锚点的连通分量，间隙 0.29 m > 0.25 m、connected=false 仍输出 96 点 g0000 实测 locked；③前驱 >768 点先按原行序抽样，同一 1600 点几何的两种排列使组合残差约 0.00243 / 0.23565 m，接受/拒绝翻转。不能把现有负例通过视为上述边界已验证。
- 重跑核心 689 项 -B -W error 通过；开发会话 cap_20261018_110029 全 386 帧 A 臂回放与阶段二 dev/A 确定性载荷一致（equivalent=true，258 locked/12 occluded/116 unselected，点集缺失/新增均 0）。现有场景结果复现，但测试未覆盖新反例。ROI 不建议采用的性能结论不因本次审查改为建议采用；其组合基线仍含上述缺口。
- 机器产物 docs/evidence/2026-10-21_fragment_roi_review/：reproduce.py/reproductions.json、row_order.py/row_order.json、core_tests.log、replay_A、replay_compare.json、关键源码 SHA。未修改历史 evidence、LATEST、配置或算法；未 commit/部署/采集/连接板端，未动 data/junction/驱动/网络。人体语义、点级 GT、真人跌倒与板端性能仍 UNKNOWN。

## 2026-10-21 修复组合审查缺陷并制定下一步计划

- 用户要求开始修复并制定后续计划。唯一写入者修共享核心两文件：ICP 累计增量 R/t、组合强制连通拒绝、复用规范采样并在前驱首次 768 点截样前排序；新增6项回归，旧实现7个失败断言、修复后通过，三因素在内存中分别隔离验证。修复前源码/指针/记录快照与全树38,890路径SHA保留（bulk扫描跨修改边界，变动源用修改前SOURCE_BEFORE校正并明确注明）。
- 验证：核心695/capture69/calibration2/current19 全部 -B -W error，fall UI21/preview55 JS通过，核心Python3.8语法通过。591真人和10合成场景 track/ID/generation、基线及跌倒判定逐帧保持，全部合成low/suspected首时刻相同、无新增掉锁/事件；395帧原失败段仍无掉锁，独立簇/非成员混入与组合并集违规0。386×orientation/partition完整载荷0差异，LATEST已按真实重跑绑定，15入口/26核心SHA检查与Store测试通过。
- 必须保留的变化：真人7帧仅减少34–102实测行，4帧END/LOWER区域有效性变化，区域总体observed/reason不变；数值与历史统计并非完全不变。走动合成297–394帧原277点断开组合改182点单片实测（0.3865m间隙不满足0.25m门），普通关联仍连续。额外780帧/357锁定帧目标行缺失P95=0/max≈3.73%，无新增掉锁/lost/ambiguous/ID，无低于最小点数；保持跟踪不等于完整人体点集。
- PC串行交替3轮完整step P50 23.98→24.95ms（约+4.0%）、P95 35.24→38.99ms（约+10.7%），性能成本如实保留；最初与比较任务重叠的计时仅作探索，不作结论。ROI继续关闭，不把旧消融数字当新基线验证。
- docs/TRACKING_NEXT_STEPS.md已形成顺序：连续窗口逐行去向/各片运动账本→有区分力的稀疏碎片策略→区域有效性与已有负例覆盖→热点性能与本地包/页面集成。状态已更新，初始计划链接到新计划；不靠放宽连通门凑旧点数。证据docs/evidence/2026-10-21_fragment_roi_fix/（反例前后/因素、全回放/成员、PARITY/HOLDOUT、INTEGRATION、TIMING_SERIAL、日志、配置/源码SHA）。未commit/部署/采集/连接板端，未动data/junction/驱动/网络/冻结配置/历史evidence；未训练/下载/开HR-09。现场仍RC15；人体/点级GT/真人跌倒/板端性能与物理效果仍UNKNOWN。

## 2026-10-21 成员完整性定位与采样间隙修复

- 固定源码前件、全树39040路径（跨修改扫描按前件校正两源文件）、5输入SHA与原ReferenceBody行/注入。共享间隙函数仅在采样超0.25m时以128×128块核查全点，修正用距离上界证明断开的错误；无新阈值，配置/ROI关闭保持。2项新增反例旧实现均失败，新实现通过。
- 真人f232/550/553/558分别+102/+35/+36/+97当前实测行；780会话f517/752/754分别+195/+32/+90，无移除。真人f243/312及780 f522全点仍断开，f244–247另片历史已分离，继续拒绝。走动297–394仍182点：1267参考行中881被高度门排除（470行被原注入转到地面下），高度后主组件382，背景再扣109后才分182/95；0.38654265m是真实过滤后间隙，分裂最早发生在背景，不是采样误差或已证实的原始传感器空洞。未放宽门补点。
- f232 END_A/LOWER_A当前23/36行支撑恢复；f243/246/247缺支撑仍拒绝。f558新增97行使主轴对地绝对余弦0.67908→0.34740，触发原0.6直立门，新增1帧全部区域不可用明确保留；不隐藏或沿用旧节点。780完整ReplayPipeline f755下降率0.347436→0.355985跨0.35门，仅原因码改变，低姿态/事件/基线保持。全部几何与历史并非逐值不变。
- 591真人、10场景、20次配对完整基线/区域、386×两区域、780对照完成。身份/完整基线/跌倒状态及合成low/suspected首次时刻保持；合成区域有效性仅共同前缀f232恢复，动作段无新增有效性退化。独立59点簇混入/非成员混入/非并集违规0；591/395/780每帧1次历史提交，386 profile commit也恰好386次。current目标/姿态/区域全值不变，仅363/365间隙诊断改变；另一ReplayPipeline入口363/365/366增加36/30/30行，入口不同单列。
- 核心697/capture69/calibration2/current19全部-B -W error，UI21/55、核心Python3.8语法通过。旧LATEST因核心SHA过期导致的首次current测试失败保留；真实重跑绑定后19项全部通过。PC预热后串行交替3轮完整step P50 12.117→12.687ms、P95 14.788→15.989ms（+8.1%）；独立profile snapshot3.549s、历史analyze/commit0.316/0.265s、采样排序0.189s、组合0.344s、全点补核0.00394s/6次（总5.423s，累计嵌套不相加）。不声称性能提升，绝对值不与上轮机器状态直接比较。
- current/LATEST已指向本轮真实current，15入口/26核心SHA与Store核对。证据docs/evidence/2026-10-21_member_completeness/：逐行去向/全点间隙/原参考过滤与地面边界、全部配对回放/区域、原因码、串行计时/profile、源码输入绑定与失败日志；区域支撑以REGION_CAUSES_VERIFIED.json为准，保留首次提取键名错误及过严比较断言。PROJECT_STATE/TRACKING_NEXT_STEPS已更新，下一步先研究低位背景占格冲突的可区分证据，再评估补核最坏工作量和尾部性能。人体语义/点级GT/真人跌倒/物理有效性/板端性能仍UNKNOWN；现场RC15、ROI关闭，未commit/部署/采集/连接板端/改data或junction/驱动网络/训练/下载/开HR-09。

## 2026-10-21 持续上线目标：背景碰撞核查与包内回放

- 对原走动f297背景排除109行核查到21体素；录制前50帧独立参考中93行所在体素再次观测、70行持续50帧，同体素最近参考点≤0.01/0.03/0.05m分别9/42/61行。原现场背景只保存cell集合，原2455095点缺失，原背景精确距离UNKNOWN；不把参考前缀替换原背景，不采用吞回旧支撑或背景放宽。
- 本地候选release c621597f50f31410/page26d5ca935685、111 manifest条目，tar SHA4b7b960cab5372886ccd5a47577e61e65b598754460661f621cf3fcc324a2475。重复构建相同、manifest/包内Python3.8语法通过，包默认v1实际解析参数与已验证v3相同。解包来源逐模块核对后运行591真人+10合成：591完整state/snapshot/baseline_ack/event（含区域）、10场景全部已有逐帧字段均与工作树逐值相同，无新增掉锁或首次时刻变化；发布集成28/bundle3项-B -W error通过。
- 无新生产代码/配置修改，current仍指上一轮真实运行。证据docs/evidence/2026-10-21_background_collision/（逐行COLLISION/独立前缀点、BUILD/候选包/重复包、PACKAGE_BINDING、11次包内回放/PACKAGE_PARITY、测试）。状态与计划更新；上线目标仍active，尚未验证板端运行/尾部性能/现场生命周期，低位背景冲突仍有边界。未部署/连接板端/采集/改data或junction/驱动网络/Git写操作/训练/下载/HR-09。人体语义/点级GT/真人跌倒/物理效果与板端性能仍UNKNOWN。

## 2026-10-21 间隙全点核查尾部优化与最终候选

- 固定源码前件/5输入重新核SHA，定位原行序距离块在大斜面/重复点上的二次尾部；单轴排序和第一版空间分块的不足保留。最终共享核查按最长轴保全全部点分块（叶≤64）+AABB批量下界+等值剪枝，小片原路径。无新目标门/配置/ROI/预测点，理论最坏二次计算仍可能，额外块存储线性。
- 最终压力单次PC测量：30000×30000斜面12.782s→176.5ms、重复点14.995s→50.9ms，精确距离逐值相同；新增tracemalloc峰值约2.05MB（不含输入）。整链386预热/串行交替3轮P95 23.673→24.970ms（+5.5%观察值），轮间前26.42/15.08/15.26、后26.23/25.17/14.58ms，波动明显且新大点集分支在此输入调用0；不声称整体提速或板端实时上界。
- 最终源码591真人完整记录、10场景全部字段+完整基线/特征/区域、386×两区域、386/780完整Pipeline及baseline全部逐值不变，含目标行、历史、原因码/区域有效性。独立59点簇/非成员混入/非并集违规0；先前成员不足/区域拒绝边界保持。核心700/capture69/calibration2/current19全部-B -W error，UI21/55，3.8语法通过；新增暴力距离、重复/排列/分块行保全、0.25m/nextafter回归。
- LATEST已绑定gap_tail/final_runs/current，15入口/26核心SHA与Store/current测试通过。新本地候选release95ebb0d9b6d6abda/page26d5ca935685、111 manifest条目，SHA9ff94a7dbd2c484aa2d0f22b6dcb83cd8a4b19fdcdf25e841830abcfa4d205ed；重复构建/manifest/包内3.8语法通过，包内591+10场景11次回放再次逐值一致。证据docs/evidence/2026-10-21_gap_tail/保留初版/最终回归、失败及中间变体、性能、包与绑定；初次绑定脚本从不含测试项的manifest取键失败已修正并保留日志。
- 状态/计划已更新，上线目标仍active；下一步目标环境、板端离线性能与发布生命周期。未连接板端/部署/采集/动data或junction/驱动网络/Git写操作/训练/下载/HR-09。人体语义、点级GT、真人跌倒、物理有效性和板端性能仍UNKNOWN。


## 2026-10-22 现场软件上线与整段核验

- 已按持续开发至上线指令完成现场软件发布：release `95ebb0d9b6d6abda` / page `26d5ca935685`，运行 `20261021T154237Z_b0937eca`，页面 `http://192.168.31.58:8936/human_fall/`。标准包SHA `9ff94a7dbd2c484aa2d0f22b6dcb83cd8a4b19fdcdf25e841830abcfa4d205ed`；板端111条manifest核对通过，HTTP页面/两个JS与包字节相同，浏览器连接、版本、状态渲染核验通过且控制台无error/warn。旧RC15目录保留，实际未触发回滚。
- 板端Python3.8.10/NumPy1.17.4原生25项组合测试通过；386帧完整Pipeline预热后串行交替3轮，修后各轮输出确定，和PC最终结果全部字段在1e-9容差内一致。对实际RC15，跟踪/身份/代际/预测标志/跌倒状态逐帧不变，成员仅f363/365/366分别+36/+30/+40实测行；这是RC15对照，不混用前轮代码作基线。此前最终源码700/69/2/19、591真人/10场景/386两区域/780及包内591+10完整回归仍有效，本轮无生产源码或算法配置改动。
- 性能退化明确保留：板端固定386输入完整step pooled P95 30.920→55.413ms（+79.2%），max58.451→112.486ms，修后1008计时帧中1帧超过103.664ms输入间隔；不能推广PC压力优化成板端整链加速。现场启动以来812个完整窗口、235431处理帧、24410.789秒（约6.78小时）：窗口处理P95范围52.312–155.024ms，receive-to-finish P95范围62.082–224.222ms，单帧process max224.389ms。两个窗口P95超过100ms且发生丢弃，后续窗口恢复。队列累计0→43；窗口delta合计42漏掉1次跨窗边界，必须使用累计差43，不能报告全程零丢帧。此次异常无同窗调用级profile，原因UNKNOWN；后续优先解决实时性能与计数边界。
- 最终health通过、状态新鲜、worker healthy，node/capture/http启动后进程指纹保持；无Traceback/[ERROR]/FATAL日志命中。现场当前自动搜索/unselected、fall unknown、baseline idle、无当前实测目标的区域明确拒绝，不沿用RC15旧目标。现场没有人体GT，不能把未选目标解释为场景无人或误锁已根治。
- 驱动PID/启动时间/配置、boot、profile/三份几何SHA、26条sessions registry及无活动录制状态前后一致；未采集/改驱动网络/data/junction/Git写操作/训练/下载/HR-09，ROI继续关闭。原profile physical_verified/runtime_eligible仍false、confirmed关闭；软件已运行不代表物理有效、人体语义、点级GT或真人跌倒效果通过，这些持续UNKNOWN。走动297–394仍182点及f558区域拒绝等成员边界保持。
- 证据 `docs/evidence/2026-10-21_release_field_validation/`（跨日继续同一发布运行）：原生回放/性能、CUTOVER、FINAL_BOARD/DETAILS/SUMMARY、LIVE_WINDOW_ANALYSIS、FINAL_RELEASE_CHECK、最终health/status、页面截图/DOM/console及SHA。开发current继续指向已真实运行的gap_tail/final_runs/current；现场绑定是本次run，二者分开记录。下一步按TRACKING_NEXT_STEPS处理实测性能退化和低位背景可区分性，不据上线抹去算法/人体边界。



## 2026-10-22 板端人体/跌倒链审查修复与合理性核查

- 先查再修：共享features拒绝非有限/不可解析高度且打断时序；fall_state的躺姿宽度/顶高分别作有限值校验，避免无穷值错误支撑和损坏宽度屏蔽有效顶高。正常候选构造已有有限值过滤，反例证明软件契约漏洞，现场触发与人体效果未据此认定。
- 现场已知窗口漏计根因在RunRecorder：跨窗口丢帧基点丢失、超过4096样本压缩丢失早期增量；同时缓存性能块在状态刷新中重复入账。修后跨窗基点保留、样本压缩保首计数、实际处理帧独立计数、按完成帧去重；反例旧7帧→正确2帧，旧2051丢帧→正确4101（共4102处理帧）。新增delta_base明确区间；首窗从首次有效计数起算，同一run累计计数须不重置，分位数仍按有界保留样本计算。
- 校正测试夹具后，用修前字节副本复现新增5项共8失败/2异常；修后核心705/capture69/calibration2/current19均-B -W error、UI21/preview55通过，最后测试断言增强后recorder11再次通过。591真人、10合成完整记录与完整基线/特征/区域，386/780完整Pipeline+baseline，386×两区域共15项全部逐值相同；目标行、身份/代际、历史、原因码和事件均保持。
- 26核心/15入口和输入SHA绑定通过，修改核心3.8语法通过。开发LATEST指向本轮真实current；现场发布95ebb0d9b6d6abda保持。最后复查认为改动符合既有有限值/独立OR支撑/日志计数契约，不改门限、配置、ROI或confirmed资格；既有完整输入无新增回退。现场性能退化原因、低位背景可区分性仍未解决，人体/点级GT/真人跌倒/物理效果UNKNOWN，本轮无板端新性能结论。
- 证据docs/evidence/2026-10-22_runtime_fall_audit/：40182路径基线（含未跟踪，跨修改扫描3生产源用字节前件校正）、修前模块、校正前失败/校正后旧模块反例、全部测试与15项完整回放/PARITY、SOURCE_DIFF、INTEGRATION/FINAL/SHA。未连接设备/部署/采集，未动data或junction/驱动网络/历史evidence/Git写操作，未训练/下载/开HR-09。


## 2026-10-22 公开 LiDAR 下载核对与独立离线训练

- 用户明确要求开始下载、核对和训练；启用本轮独立 ML 实验，不改变原自采方案和现场软件。MM-Fi E01 原包范围读取，取回 80,190 LiDAR 帧+270 份关节标签（10 人/27 动作），80,460 成员 CRC 全通过、逐成员 SHA 留存；派生 ZIP 2,252,604,086 B / SHA c1de39e0…。Synthetic Fall 原包 673,216,404 B / MD5 与作者一致 / SHA 0e0675b9…，ZIP CRC 通过；实查 900 序列/65,487 帧（451 fall/449 nonfall），非网页标称 1000×60，保留原始包。
- 两套 CPU RF（200 树/114 维 XYZ 序列特征/seed42）独立训练，GT 不进特征。MM-Fi 按受试者 5 折 accuracy=0.662963、macro-F1=0.653919；合成集按18父目录分组5折 accuracy=0.996667、macro-F1=0.996667。所有序列有效，训练/测试组无交集，完整模型输入没有跨组精确重复；合成底层动画谱系/近重复仍 UNKNOWN。完整候选和各折模型在 ML/models/public_lidar_20261022/，重载预测一致，旧两个RF SHA保持。
- 新测试5项+原适配器6项均 -B -W error；两套折模型和全量候选分别对历史388预提取目标帧/22连续窗口完成离线推理。无对应动作/跌倒GT，不报告IFW192S准确率/召回；非原始点云整链、非板端实时/物理验证。首次编排管道ResourceWarning保留并修复，生命周期检查通过；两个训练子进程exit=0。
- 证据 docs/evidence/2026-10-22_public_lidar_training/（39,703可见路径基线、下载/CRC/SHA、源数据实际审计、划分/逐序列预测、环境、模型与最终核对、模型回放及测试）；说明 ML/docs/public_lidar_20261022.md。同期5个核心/测试文件发生非本轮修改，单列CONCURRENT_SOURCE_CHANGES并保留。未部署/采集/改驱动网络/改旧数据或junction/改现场配置/confirmed/Git写操作；本轮只新增下载与离线ML产物。下一步目标域有真值验证、跨环境比较和模型路线选择，公开集高分不等于上线资格。

- 本轮最终补充核对：合成包65,487个CSV中有14个带(1)后缀的同帧副本，逐对SHA证实与原帧字节相同，训练实际使用65,473帧，未重复入组也未删除原件；详SYNTHETIC_EXCLUDED_NAMES.json。


## 2026-10-22 ML 下一步计划与冻结模型前缀实验

- 接续用户“继续下一步计划”，实际完成目标域标注盘点与冻结模型因果前缀评估。当前data/sessions共21段/4472帧，无相邻动作标签；工作台9份最新非e2e GT文件SHA与manifest相符，但只有历史对象类（FURNITURE1520/BACKGROUND304/PERSON546），没有结构化动作/姿态/跌倒字段，对应原录制也不在当前会话根目录，不能用来计算当前跌倒效果。盘点范围/声明绑定分别记录，不将历史对象GT或伪标签当动作真值。
- 首轮MM-Fi模型/参数未变，270条全部沿用原人员留出模型，10/20/30/60/297帧前缀对整段动作类别的accuracy=0.440741/0.603704/0.633333/0.662963/0.662963，macro-F1=0.427536/0.599619/0.628893/0.652071/0.653919；完整输入预测逐条复现首轮，未来点云扰动不改变前缀特征。这不是逐帧跌倒真值，不宣称物理帧率/现场效果。
- ML/docs/NEXT_STEPS.md已明确执行顺序：先短窗口专门训练（30帧候选、20/60对照、10极短参考；来源于本轮探索），再冻结E01后做E02跨环境测试，随后目标域独立标签绑定与NumPy/Python3.8推理候选、本地整链/性能。5项训练回归全部-B -W error，前缀离线推理270×5完成。证据docs/evidence/2026-10-22_ml_next_steps/（39856可见路径SHA基线、标注清单、逐条前缀账本、日志/测试/源码绑定）。未新增下载/训练/部署/采集，未改原模型、现有数据或junction、核心/页面/驱动网络/现场配置，未Git写操作。

## 2026-10-22 因果短窗口、E02独立验证与NumPy本地候选

- 按用户授权连续完成公开数据离线研究：保留原XYZ/RF参数，新增10/20/30/60帧、步长10的因果窗口训练，复用原人员5折（重叠窗口同人同折），保存逐窗口概率/起止索引、完整序列聚合、分组与混淆。窗口仅继承序列动作标签。主要30帧首窗口accuracy63.33%→66.67%；全时段窗口61.39%→63.28%（macro-F1=0.6265），序列聚合69.26%→65.93%（0.6518），退化如实保留；其余窗口见ML/docs/causal_lidar_20261022.md。
- E01开发完成后先冻结四种配置、标签映射和权重，再下载E02全LiDAR及关节：S11–S20、27动作、270序列、80,190帧+270关节文件，80,460成员CRC全部通过、逐成员SHA留存，206 Range/磁盘检查通过。派生ZIP2,480,678,786B，SHA44c6c8024fa2a11805c240abe2e4f14aff8f480933089c2e991cd9721bb9cefc；E01仍为c1de39e07689ebbac4d9eb9b60741fc0f5256a8c21b3c6dc78796f935573af17。两环境完整序列无精确内容重复，不声称近重复穷尽核查。没有丢弃困难样本。
- E01→E02主要30帧模型窗口accuracy=35.78%、macro-F1=0.3193，序列聚合37.41%/0.3382；原完整训练模型对应窗口30.77%/0.2982、序列聚合36.30%/0.3328，直接完整297帧35.19%/0.3305。四窗口和每类/每人/源点数条件全部保留。环境与人员变化混合，跨域退化明显；未在E02拟合或根据其成绩选型，E03/E04未参与本轮。
- NumPy RF导出/推理及因果特征缓存实现：Python3.8语法、stdlib+NumPy独立导入检查通过；身份/代际/选择/时间epoch/标定改变、断档/倒退或坏帧清历史。主要30帧全部7290留出窗口、7290个E02窗口、2031边界探针、229原始回放输入类别一致，概率最大误差≤2.23e-16，重载一致。8项ML、705核心、69capture测试均-B -W error通过。失败v1、缺失points盘点中止、辅助命令ResourceWarning及修复重跑记录保留。
- 原始cap_20261018_110029的386帧逐帧读文件/解码+完整检测/跟踪/几何/状态链，旁路模型预热1对+串行交替3对，8次完整result/baseline SHA一致，229预测/次。30帧连续段暖机3.006258秒；PC三轮缓存特征P95 0.846–1.270ms、推理就绪P95 0.375–0.544ms、加入模型的读解码整链P95 24.577–36.054ms，对照24.906–41.399ms，负载波动明显，不据此声称整链提速/板端实时；审计开销另存。
- IFW192S重新绑定21段meta/4472声明帧，其中20段points.bin共4425帧存在，字节数与meta相符、时间严格递增，另一段cap_20261020_172855缺points.bin/47帧；meta/points/时间offset/目标行和回放同源地面SHA留存。21段human_annotations为空；9份历史对象GT无可绑定的当前录制和动作字段，PERSON不升为站立。目标域动作/真实跌倒、轴对齐、人体物理效果与原生板端3.8/NumPy1.17性能持续UNKNOWN。
- 新模型ML/models/causal_lidar_20261022_v2/，失败v1与全部旧模型保留；证据docs/evidence/2026-10-22_causal_lidar/（39872可见路径基线、下载/输入SHA、冻结、逐窗口/序列/混淆、NumPy核对、完整原始回放、源码副本和测试）。PROJECT_STATE和ML下一步已更新，复现脚本ML/docs/causal_lidar_reproduce.ps1。未改生产核心/现场版本/confirmed、未部署/采集/启停板端服务/改驱动网络/Git写操作，不将离线分类结果写作现场或真人跌倒通过。

## 2026-10-22 公开LiDAR真实点云与冻结预测预览

- 按用户“数据集看看效果”，新增只读生成器ML/src/preview_public_lidar.py与预览模板，展示E01/S01/S02、E02/S11/S15的A12深蹲：每环境选整段聚合正确/错误各1段，显式说明选样非总体比例、标签继承序列非逐帧GT。124个原始显示帧逐成员SHA与ZIP CRC核对，108份既有30帧概率直接复用；显示每10帧/至多600原始行，0.001原始坐标单位量化、误差≤0.000501，不生成假人体或关节。
- 可播放、拖帧、旋转/缩放与显示最近已截止的30帧预测；不足30帧明确暖机，末帧停止。浏览器实际核对E02错误样例、概率更新、暖机与播放至297帧，无console error/warn；8项ML测试-B -W error通过。证据docs/evidence/2026-10-22_lidar_preview/保留输入绑定、抽样行、payload、截图和播放结束DOM。预览约665KB，未重训、调参、修改原数据/旧模型/历史证据/生产页面或操作设备。

## 2026-10-22 深度 v2：同环境提升、跨环境塌缩与多环境训练

- 接续用户“上深度学习/找数据集合”。先修正上一轮未收敛的深度基线：训练前登记只改每帧 64→256 点、固定 10→40 轮，网络/优化器/batch/seed/人员 5 折/30 帧窗口不变（`docs/evidence/2026-10-22_deep_lidar_v2/PREREGISTRATION.json`）。E01 窗口 accuracy 24.10%→89.22%（macro-F1 0.8915），序列聚合 31.85%→95.56%（0.9557）；五次留出 90.47/89.85/84.29/90.60/90.88%，固定末轮、不按留出选轮。同轮 RF 仍为 63.28%/65.93%。提升来自点预算与训练预算，不是结构变化。
- 冻结 5 个 fold 权重做跨环境推理（不重训）：E02 11.14%/11.48%、E03 4.61%/4.07%、E04 3.95%/4.07%，随机 3.70%；E03/E04 只输出 3/2 个类别、最大类占 53.6%/95.2%。冻结的 E01 30 帧 RF 在同一批 E03/E04 上是 15.82%/17.04% 与 10.78%/10.37%，同样低但退化较轻。结论：同房间 95.56% 主要来自环境几何，不能当动作识别能力或上线依据。
- 多环境训练（E01+E02+E03，30 人/810 序列/21,870 窗口，24 轮固定，逐轮检查点）在第 4 个环境 E04 上仍是窗口 4.01%/序列 3.70%，训练集自测 95.74%/97.53%；同协议 RF 由 10.78%/10.37% 提到 14.49%/15.19%。增加 2 个环境（5.3 GB、160,380 帧）没有解决整场景 XYZ 的跨房间迁移。
- 新取得 E03/E04 原始 LiDAR+关节：2,706,265,418 B（SHA `5eded03b…`）与 2,637,307,802 B（SHA `a053da6b…`），各 80,460 成员 CRC 通过、派生根 ZIP 与逐成员 SHA 留存。E04 首次下载被后台 runner 崩溃中断，旧文件保留未删/改名，完整包重新下载到 `e04_r1/`。
- 变长序列落地：短于 30 帧的序列生成单个 `(0,len)` 因果窗口，批次右侧补零、按每条样本最后一个有效帧预测；真实 20 帧 MoMo 样本上补零批与单条推理最大概率差 5.5e-10，测试新增短序列窗口与补零批等价 2 项。
- 对照检查：27 类标签置换是双射、不能当泄漏对照，8 轮 47.4% 已标注为无效设计并保留；改为逐窗口独立随机标签后 8 轮留出 3.1–4.5%（随机 3.7%），未见窗口/批次串折泄漏。5 折训练前断言训练/测试人员无交集。
- 运行事故：17:45 后台 job runner 以 `1073807364` 退出，同时终止 fold 2 第 16 轮与 E04 下载。训练脚本改为逐折检查点 + `fold_N_probs.npz`，fold 0/1 从检查点重算、fold 2 重训，最终 5 折齐全；训练 14 项 ML 测试全部 `-B -W error` 通过。
- 模型 `ML/models/deep_lidar_20261022_v2/`（旧 v1 保留）与 `ML/models/deep_lidar_multi_20261022_v1/`、`ML/models/rf_multi_20261022_v1/`；证据 `docs/evidence/2026-10-22_deep_lidar_v2/`（登记、缓存、逐折/逐窗口/跨环境/多环境、RF 对照、随机标签对照、COMPARISON.json、下载记录）。未改生产核心/现场版本/confirmed/驱动网络，未部署/采集/Git 写操作；IFW192S 动作/跌倒、点级 GT、跨传感器轴对齐与板端性能仍 UNKNOWN。下一步先做人体点集（训练期关节裁剪→推理期 IFW192S 跟踪点集）与尺度/背景归一化，再谈扩环境。


## 2026-10-22 人体点集裁剪审计与本地跟踪点接口

- 接续“继续设计开发”，新增纯NumPy的显式刚体变换/关节包络裁剪、固定seed的256点采样、实测锁定目标30帧缓存，以及原始ZIP审计与完整本地回放入口。换身份/epoch/动作代际/选择版本/标定、时间重复倒退断档、非法行或预测目标清历史；空裁剪不回退整场景，任何不足10点帧阻止整份训练缓存发布。
- 预固定E01/S01、E02/S11、E03/S21、E04/S31各A01/A12/A27，共12序列/3564帧，直接恒等坐标裁剪全部0点。GT和LiDAR不能直接共用坐标，真实外参/单位验证尚缺，未生成真实训练缓存。显式外参manifest须声明verified并绑定校验证据SHA，软件绑定不替代物理认证；未做猜轴或占用率最大化拟合。
- ML共19项测试-B -W error通过（新增5项）。cap_20261018_110029原始points.bin读取/解码及完整386帧几何链对照，258实测目标帧/229推理窗口，原链与旁路完整result/baseline SHA均6aa6629066956d9949e4188d8c31b1ea69ed6214d0b4a112b1c8924359a21017；逐帧采样源行可重建。冻结整场景v2 fold0仅测接口分布，不作为动作效果。
- 修订实验逻辑：先外参绑定和全量审计，再分开GT裁剪训练/GT裁剪测试的oracle消融与无GT提取器差异；测试期GT裁剪携带姿态信息，不能冒充部署效果。E04已观察，后续为探索性复测；环境和人员共同变化，几何依赖尚非唯一因果解释。
- 证据docs/evidence/2026-10-22_human_pointset/（含未跟踪可见文件基线、修改前关键源码SHA、预固定协议、四环境逐帧账本、两轮完整回放与测试），说明ML/docs/human_pointset_20261022.md；状态和下一步同步更新。未启动新实验训练/下载模型数据、未动生产核心/页面/现场版本/confirmed、未部署采集/改驱动网络/Git写操作或既有数据junction。IFW192S动作/跌倒、点级人体GT、跨传感器对齐与板端性能均UNKNOWN。


## 2026-10-22 跌倒候选链、弱监督与真实人员隔离：总体目标尚未完成

- 用户要求持续开发直到跌倒识别，并明确允许公开数据下载和本地训练，排除部署/采集。新增纯NumPy二分类候选运行器、身份/代际/标定/模型配置SHA绑定、因果窗口、事件去重/恢复、RF与MIL训练、导出阈值核对及训练人员内部校准。核心/页面/现场/confirmed不改，模型只旁路输出ml_fall_candidate。
- 原合成包900序列/65473帧原始成员重读与SHA绑定，复用18父动作目录5折，非人员隔离。旧完整RF固定30帧窗口检出349/451、非跌倒触发0/449；积累上下文探索447/451、0/449。专门短窗RF437/451、112/449；同网络逐窗标签监督451/451、193/449；bag-max MIL450/451、12/449。保持同网络/seed/优化器/上下文的监督对照支持弱序列标签处理，但不冒充逐帧GT、真实效果或新的独立测试。
- 下载完整LaserAct person包4602081280B，作者SHA2c2229a943cd02d2c5a73e2a27ec5083ee9f04ad313bdd248f113db7dedf2644通过。旧部分包与本轮首次下载保留；新完整包data/downloads/fall_recognition_20261022/laseract_person_r2.tar。小Range与分块SHA账本、已完成前缀复制及最终整包SHA验证取代慢大分块；所有输入先校验后训练。官方5人1430训练/4人911测试，Falling只有16训练/14测试，训练12条集中P08。
- Velodyne预登记主实验MIL检出8/14，1/889可观测非跌倒触发；901/911有有效窗口，2正例无窗口、4正例有输入未检出，假阳性是主动Lying。RF事件0/14。后续同事件视图探索Cepton6/14、2/886；Livox三包聚合7/14、1/893，不能把多传感器重复视图增加为独立事件。单包Livox正例有效连续帧最多2，首次训练停止；按作者30Hz包→过去3包完整模式修正，记录原包跨度/时间/点数并验证因果性，不造点/不跨长缺口。
- 官方训练5人LOPO只有3/16条正例候选，21组预设规则均未满足本次研究逐人负片段触发预算，输出NO_SUPPORTED_RULE且未发布新规则；预算不是项目验收门，不拿测试分数放松阈值。主实验有效输入召回8/12不能替代全14分母的8/14，99%总体accuracy不能称可靠识别完成。IFW192S独立真值、真实跌倒效果、跨传感器轴/物理标定和板端性能持续UNKNOWN。
- 最终34项ML、705核心、69capture均-B -W error通过；57,373合成留出窗口与真实各传感器留出窗口NumPy/PyTorch阈值0.2/0.5/0.8判断一致。多模型原始386帧整链对照完整result/baseline SHA均6aa6629066956d9949e4188d8c31b1ea69ed6214d0b4a112b1c8924359a21017，10帧最小上下文249就绪窗口；零旁路触发不解释为真实零误报。
- 证据docs/evidence/2026-10-22_fall_candidate/，说明ML/docs/fall_recognition_20261022.md；模型ML/models/fall_mil_20261022、laseract_mil_fall_20261022及RF/控制/多视图/LOPO变体全部保留。输入/折/源码SHA、失败、分块、校准拒绝和完整回放均绑定；原权重与生产源码不变。未Git写操作、改驱动网络、部署、采集、启停板端或改已有会话/junction。当前交付是离线候选实现与真实失败边界，未宣称总体可靠跌倒识别完成。

### 2026-10-22 跌倒候选：三项训练侧消融，无改善

- 延续离线训练授权，固定LaserAct训练5人LOPO/40轮/seed42/MLP/优化器/阈值，对比连续三窗正例监督、仅动态63维、有序六段114维。结果分别3/16+FP4/1403、0/16+FP3/1403、3/16+FP4/1403；原bag-max对照3/16+FP4/1403，重跑5份数值权重SHA逐份复现。未重测官方测试人员，未采用失败变体。
- 新训练选项与显式ordered schema共用训练/流式汇总，缺帧断窗，遮蔽列折入权重，原格式与默认行为保持。37项ML/705核心/69capture均-B -W error通过；三个变体各完成原始386帧全链回放，249就绪窗口且输出SHA均6aa66290…；464个既有生产路径SHA保持。
- 新证据docs/evidence/2026-10-22_fall_sustained/，说明ML/docs/fall_training_ablation_20261022.md。可靠识别未完成，IFW192S效果/物理标定/板端性能UNKNOWN；不把开发集反复消融称独立验证，不以失败推断单一瓶颈。下一步检验更充分时序表示与独立人员真实困难正负例。未部署、采集、改confirmed、删改会话或Git写操作。

### 2026-10-22 三项训练消融审查

- 仅审查，未改算法/模型：确认1项P2，validate_fall_mil.py:26忽略模型manifest的feature_schema，对ordered模型仍生成旧moment特征，双后端对同一错误输入比较会假通过。全5折验证均报告通过；P01共4348窗口正确/错误schema最大概率差0.982668，阈值0.5判断不同10窗。
- 回查trainer已显式传schema，P01保存概率与重算最大差2.53e-7（批量大小变化），0.2/0.5/0.8判断保持；未发现该缺口改变上一轮训练成绩。37项ML测试复跑通过，导出验证端到端复现完成。初次严格逐位断言因上述浮点差失败，已按既有容差与阈值验证并保留说明。
- 证据docs/evidence/2026-10-22_fall_sustained_review/，FINDINGS.json与错误schema复现；待修正导出校验读取/校验manifest并分派schema，增加回归。未修复源代码、重训、部署或采集。

### 2026-10-22 修复MIL导出校验schema分派

- 修复审查P2：validate_fall_mil.py复用FallCandidateRuntime校验模型manifest/权重SHA及二分类契约，按feature_schema调用matrix，记录manifest/特征矩阵SHA；当前矩阵只支持10..30帧/0.5秒缺口，其他上下文明确拒绝，空模型或无可观测窗口不报成功。新增新旧schema及损坏绑定/未知schema/不支持上下文回归。
- 39项ML测试-B -W error通过；原对照/连续监督/动态特征/有序汇总20份权重全部端到端重校验，每变体33,894个训练侧留出窗口，三个阈值0.2/0.5/0.8判断一致，四组最大概率误差2.38e-7/1.79e-7/1.79e-7/1.49e-7。有序P01特征矩阵SHA与正确公式相同、与旧公式不同。
- 新证据docs/evidence/2026-10-22_fall_schema_fix/；原模型/清单SHA全部保持，未重训或重测官方测试人员，未修改生产链/confirmed，未部署/采集/Git写操作。该修复恢复导出校验契约，不改变既有跌倒识别失败结论，IFW192S效果持续UNKNOWN。

### 2026-10-22 跌倒正例输入归属：多数 Falling 片段不含下降过程

- 接续用户「先查输入损失」。新增 `ML/src/fall_observation_ledger.py`（逐帧观测账本）与 `ML/src/analyse_fall_observations.py`（输入归属），对作者 person 包 2341 段 × 每帧重建点数/时间戳/零长帧/连续有效段/人体点集主轴，Velodyne 与 Cepton 各一份；整包 SHA `2c2229a9…f2644` 两次全量读取核对通过，逐成员 SHA 留存。
- 姿态指标（主轴与传感器 +z 夹角，且要求该帧垂直跨度 ≤1.10 m 才算在地面）先在对照类验证：Standing 55 段 100% 直立、卧姿 0（各片中位 7.3°）、Stumbling 50 段 100%/4%（8.2°）、Bowing 46 段 100%/0%（7.6°）、Sit_Down 51 段 70.6%/7.8%（32.3°）、Lying 42 段 0%/100%（87.3°）；12 个 session 的 Standing 中位都在 2.0–10.5°，说明裁剪与轴向上正常。跨度判据不可省：双人互动类（`Cheers` 37 段）裁剪横跨两人、主轴水平但 z 跨度仍有 1.6–1.8 m，不加判据会被 100% 误判为低姿态。
- 主结果：Velodyne 30 条 Falling 中 26 条（87%）整段没有直立帧、100% 出现卧姿（这 26 条整片最大垂直跨度仅 0.38–1.07 m，站立人体同包为 1.56–1.69 m，两个指标独立同向），只有 4 条含连续「直立→卧倒」（跨度 1.08/1.55/1.68/1.68 m）；**测试 14 条中仅 `S07A09T02` 一条含直立帧，而它正是主实验检出的那一条**。Cepton 同向（直立比例 0.172 vs Lying 0.000、Standing 1.000；测试 14 条 2 条）。因此上一轮「检出 8/14」测的是卧姿外观而非跌倒事件。
- 同一 session S12 的两段可直接对照：`S12A09T01`（Falling，漏检）33 帧全有效、夹角 78.5–82.0° 恒定、质心 −1.39 m，模型 0.087；`S12A20T02`（Lying，唯一误触发）夹角 85.2–87.3° 恒定、质心 −1.34 m，模型 0.994。几何几乎同类而分数相反。
- 「无有效窗口」2 条性质不同：`S06A09T03` 前 8 帧夹角 54.5°→84.5°、质心 −1.250→−1.320 m，**下降后半段在输入里，被 10 帧下限挡掉**（8 帧即可成窗）；`S09A09T01` 第一帧已 76.0°、之后 24 帧全零，任何窗口下限都无下降过程可看。
- 零帧来自作者 person 包本身（`frame_offsets` 差分为 0、时间戳仍在），且三路传感器同一时段同时丢；本地无全场景点云（core 包仅 labels/splits/meta），故「原始雷达是否仍看到人体」保持 UNKNOWN，本轮不下载。「不可观测」也随传感器变化：Velodyne 与 Cepton 的无窗口集合不同，`S12A09T01` 在 Cepton 上 49 帧全零而在 Velodyne 上全有效。
- 新增 20 项回归（合成站立/卧倒/断档/上行/无有效帧及解码反例），ML 共 54 项 `-B -W error` 通过。证据 `docs/evidence/2026-10-22_fall_observation_ledger/`（两份账本、两份归属、SUMMARY、测试日志），说明 `ML/docs/fall_observation_20261022.md`。
- 下一步修正：先改评测协议（正例=含可观测下降的事件窗口），第 2 步几何+时序链改在含下降过程的片段上验证（公开集仅剩 4 条，合成集 451 条），第 3 步独立人员数据优先级提高。未改生产代码/配置/模型/阈值，未部署/采集/训练/下载，未动 data 与 junction，无 Git 写操作；IFW192S 真实效果、物理有效性与板端性能仍 UNKNOWN。

### 2026-10-22 更新完整雷达路线树与临时点子分支

- 更新用户桌面HTML并保存仓库同版docs/diagrams/雷达数据流-完整路线与卡点.html；保留原17步细节，加入几何/动作/跌倒候选分支、失败结果与最终卡点，明确公开人员留出和训练LOPO、旧现场性能与新ML性能的边界。原HTML备份及SHA放docs/evidence/2026-10-22_radar_flow_tree/。
- 新增点子挂接/状态/备注、浏览器本地保存、JSON导入导出；点子不改变固定结论。node --check通过，54项ML测试-B -W error通过，真实浏览器端到端新增→刷新保留→文本标签安全显示→删除通过。JSON文件导入导出未做浏览器往返验证；不宣称已验证。
- 本轮未改算法/权重/生产配置/设备/数据，未新增训练下载部署采集或Git写操作。可靠识别仍未完成，IFW192S效果与新版板端实时性能UNKNOWN；接下来按路线树继续针对有效观测和跨人员泛化做离线研究。

### 2026-10-22 跌倒数据与开发总计划 + 准入闸门/标注 schema 落地

- 新增 `docs/FALL_DATA_PLAN.md`（数据来源、处理链、观测口径、文件级代码改动、M0–M6 里程碑与闸门）与 `docs/FALL_CAPTURE_PROTOCOL.md`（自采协议：≥10 人、≥60 事件、≥20 h 日常、动作清单、命名/标注/采后 15 分钟 QA）。计划明确：自采是唯一验收来源，公开集只做开发，合成只做预训练；召回分母只算可观测事件，不可观测单列。
- 新增 `ML/src/fall_dataset_gate.py`：几何准入闸门，判定 `OK / NEVER_UPRIGHT / NEVER_LOW / EVENT_IN_GAP / TOO_SHORT`（直立 ≤30°、倒地 ≥65° 且垂直跨度 ≤1.10 m、下降过程必须被真实采样、断档不跨）；直接在 LaserAct 30 条真实 Falling 上复核为 `NEVER_UPRIGHT 26 / OK 4`，与本轮人工分析一致，证明闸门可当数据集入口用。
- 新增 `ML/src/fall_annotation.py`：`fall_events_v1` 事件级标注（t_start/t_impact/t_end、kind、certainty、observable、时钟偏移±不确定度），含校验（重叠/越界/非法 kind/重复 id/BOM 兼容）、事件窗口（秒制、带前后文）与 CLI；`data/annotations/<session>.json` 为落地位置。
- 设计取舍写进计划：时间一律用秒与真实时间戳（30 帧在 7/10 Hz 分别是 4.3/3.0 s）；观测质量进特征而不是补零；两演员裁剪靠垂直跨度 1.10 m 阈值排除（`Cheers` 类不加阈会被 100% 误判为低姿态）；误报按小时、召回按可观测事件、人员隔离划分预注册。
- 下一步（M2）几何证据链与 UR Fall 验证：UR Fall 已核实为 70 段（30 跌倒/40 日常）、逐帧 -1/0/1 姿态标签、CC BY-NC-SA 4.0；只作方法验证，不作效果证据。
- 新增 28 项回归（闸门 10、标注 17、BOM 1），ML 共 82 项 `-B -W error` 通过。未改生产代码/配置/模型/阈值，未部署/采集/训练/下载，无 Git 写操作；IFW192S 真实效果、物理有效性与板端性能仍 UNKNOWN。

### 2026-10-23 历史开发路线实际补入雷达树

- 回查10-10至10-22当前日志/旧只读归档/研究说明，新增44条有来源的历史分支：背景/粗骨架/传统聚类/旧RF与PointNet协议修正/Markov-HMM-HSMM/候选历史失败门/变化获取/高度运动入口/身份恢复/碎片组合/ROI失败/成员与背景碰撞/板端性能/公开集训练/事件输入审计/闸门与标注计划。每条列尝试、结果、最终卡点和来源，已更新用户桌面原HTML与仓库同版，不把旧归档流程当现行规则。
- 修正8/14的解释为Falling标签片段触发，非真实跌倒事件召回；最新几何审计30条中26条无直立帧、4条OK，公开集事件资格不足仍是核心缺口。旧几何链已发布与新ML候选未部署分列，旧4Hz和后续板端P95退化/累计43丢帧按时间分列。仍无IFW192S效果或新版ML板端性能结论。
- 82项ML测试-B -W error通过，node --check通过；浏览器真实展开六组、44条历史、Markov/ROI/准入闸门可见性端到端通过。来源章节存在性与SHA、桌面/仓库字节一致检查通过；新证据docs/evidence/2026-10-23_radar_flow_history/，旧证据不覆盖。本轮未改算法、配置、权重、原始数据或设备，无训练/下载/部署/采集/Git写操作。


### 2026-10-23 秒制几何旁路、事件评测与 UR Fall 代理

- 按用户“开始开发”，先修评测分母/UNKNOWN 标签及几何诊断跨断档、首段误拒、坏时钟/坏点；同步修订总计划与采集协议。新增纯 NumPy 秒制几何候选、原始会话旁路、NaN+mask/连续段缓存和独立事件评测器；一对一匹配、重复/及时召回、显式非跌倒小时、UNKNOWN 覆盖、人员分层及区间均保留。几何诊断不决定主召回分母，缺上下文 Falling 不当负例。
- 最终 ML106/核心705/capture69/calibration2 均 -B -W error 通过。386 帧真实原始会话开关旁路完整输出 SHA 均6aa6629066956d9949e4188d8c31b1ea69ed6214d0b4a112b1c8924359a21017；128 UNKNOWN/256 upright/2 transition，0候选不解释为零误报。合成事件→缓存→CLI评测端到端通过，两次缓存字节SHA一致；514个既有生产路径SHA保持，9个相关Python文件通过3.8语法检查（非板端原生验证）。
- 用户另授权联网与资源下载：官方UR Fall共75文件/64,405,496B到data/downloads/urfall_20261023_v1，逐文件SHA、深度ZIP CRC和16位灰度头核对。固定规则只用作者已分割深度H/D/P40，共11916同步帧/11544特征行，29/30条fall命中姿态过渡参考窗、0/40条ADL触发；不是原始点云、独立人员或IFW192S效果。标签和可能含未来参照的HHmaxRatio不输入。
- 首次UR运行因adl-37特征331..350帧无时间而拒绝，失败目录保留；后续20行逐行UNKNOWN、不外推时间。唯一漏检fall-21低位后只剩0.233s，未满固定0.3s保持，保留漏检，状态改为low_hold_pending；前后候选报警时刻一致，未调参。说明ML/docs/fall_geometry_20261023.md；证据docs/evidence/2026-10-23_fall_event_geometry/（全仓40957路径基线、前件、失败、最终final_checks及final_synthetic_e2e）。
- 未动既有数据/junction/历史证据/生产链/权重/设备，无训练、部署、采集或Git写操作。M2原始深度内参/地面/点集验证仍缺，M3/M4目标域独立真值与长时数据、M5时序模型对照和M6板端尚未完成；IFW192S效果/物理有效性/新版板端性能UNKNOWN。下一步继续原始深度适配和作者特征输入差异，再确定学习表示。


### 2026-10-23 原始深度全量回放、测量连续性与旧版NumPy验证

- 接续M2：新增urfall_raw_depth.py/evaluate_urfall_raw.py、显式标称相机配置和像素来源账本。其余68个官方深度ZIP共2,233,370,776B下载到新目录，CRC/SHA通过；共70段11936原始帧，ADL-37后20帧无时钟照样保留UNKNOWN。推理不读作者特征/标签，评价阶段另读姿态参考，分母全30/40不缩。
- 默认下方40%地面输入仅29/70验证通过，目标3859帧、参考窗11/30命中、ADL0/40触发；不能把无输入解释为低误报。保持验证门限，仅换底部四分之一后为62/70、目标8716帧、25/30+1/40；具名参数变体，不动生产默认。先后修复角度未知丢高度、直立参照被下降覆盖，再对“真实中间高度”和“角度缺测期间低位保持”做独立消融：26/30、27/30，合并28/30，三者ADL均1/40；最终原始全链重跑确认。作者特征当前29/30+2/40，旧0/40退化保留。
- 剩余fall-10为初始人体被背景吸收、fall-22为0.1s已开始下降而0.3s预热尚未完成；保留漏检，不补造直立。ADL-23具体动作未知。协议增加无人前缀/已有背景绑定、≥30s动作前后文和失败保留。旧原文PDF一地址及API下载403已记录，网页工具可读的论文f=580只作标称参数，不假称逐台标定。
- 最终ML119项、核心705/capture69/标定2均-B -W error通过，514生产路径SHA保持；IFW原始386帧开关旁路完整SHA均6aa6629066956d9949e4188d8c31b1ea69ed6214d0b4a112b1c8924359a21017。90帧因果前缀逐值一致；早期fall-01的160帧138166点全部由源像素精确重建。高度/角度缺测mask、端点噪声不作中间过程、真实断档与高度超界、全缺输入分母等回归加入。
- 新check_fall_geometry_compat.py在本地隔离Python3.8.10/NumPy1.17.4对386帧IFW和160帧深度目标点与当前环境逐状态/数值核对，通过，最大差2.89e-12/4.07e-13；不等于ARM/ROS原生性能。下载来自Python.org/PyPI并绑定SHA，不改系统解释器。
- 证据docs/evidence/2026-10-23_urfall_raw_depth/（41027路径前件、来源、失败、两因素账本、核对图、最终verified/）；说明ML/docs/urfall_raw_depth_20261023.md。M2软件链推进，逐台内参/物理资格/人体点级GT及M3-M6仍不齐，IFW效果和新版板端性能UNKNOWN。未部署、采集、训练、下模型、开HR-09或Git写操作，既有数据/junction/历史证据不改。下一步继续前缀/背景与困难负例的离线验证，再做目标域模型对照。


### 2026-10-23 事前地面/背景参考入口与默认回放保持

- 新增urfall_scene_reference.py，参考包绑定源/目标ZIP、时间表、相机、栅格、来源帧与SHA；共同时间/安装/空场仅metadata_declared，含不确定度的源结束必须早于目标，拒绝同录制/错相机目标步长/损坏或NaN参考/地面不达原门限。不编造片段间顺序，不用目标未来帧回填。raw单段与batch均接入显式参考，指定失败不回退；批量缺参考单列，不缩30/40分母。新增实际binding供可移植核对，旧账本兼容。
- 合成CLI端到端：独立事前空场使40/40目标帧可见、首帧76点、0.7s候选；原片内预热无候选。重复包SHA相同，6帧因果前缀逐值一致；仅软件例，不是真人效果。40帧2510点在隔离本地Python3.8.10/NumPy1.17.4与当前环境状态/事件一致，最大差1.42e-14，不冒称ARM性能。
- 真实UR70段11936帧重跑，除新增binding外所有逐帧字段一致、目标缓存逐份SHA相同，保持28/30参考窗命中+1/40日常触发。现有sync只有片内相对时间，无共同epoch/空场依据，未为两个真实漏检制造参考或报告30/30。IFW原始386帧旁路整链SHA保持6aa6629066956d9949e4188d8c31b1ea69ed6214d0b4a112b1c8924359a21017。
- ML123/核心705/capture69/标定2 -B -W error均通过，514生产路径SHA保持。capture日志为Windows GBK兼容编码，按gb18030读取计数，不重写原日志。新证据docs/evidence/2026-10-23_fall_scene_reference/（42211路径前件、合成与拒绝检查、默认全量对照、兼容及机器结果）；说明ML/docs/fall_scene_reference_20261023.md。
- 未动既有数据/junction/历史证据/设备/权重，无部署、采集、训练、模型下载、HR-09或Git写操作。已询问可用IFW事件真值文件路径；整体仍缺独立目标域事件与长时日常、物理资格、模型对照和原生板端，效果UNKNOWN。下一步按真实事前工件/上下文和困难负例推进，不把合成验证当作目标域成绩。


### 2026-10-23 事件时序接口、隔离预检与纯NumPy数值核对

- 新增event_model_numpy.py/train_event_model.py：8个实测特征+8个mask、单层GRU、秒制上下文/候选保持、显式几何门控或纯时序模式；缺测/断档重置隐藏，身份/代次/标定重置事件绑定，未训练夹具禁止发候选。旧RF/MIL类AST保持，factory接原始回放。事件缓存补首次接触/可信度/时钟不确定度，只对明确下降至接触/明确非跌倒动作计算损失，边界/未知/预热忽略但保留逐事件audit；train/validation/test人员互斥且SHA绑定，仅train数组参与归一化。
- 最终ML136/核心705/capture69/标定2项-B -W error通过；解析合成账本→注释→缓存→CLI预检接通，train4正/9负帧仅软件例。固定随机初始化512步/4次重置在本地3.12/NumPy1.26和3.8.10/NumPy1.17.4对PyTorch最大概率差1.11e-16、隐藏差2.22e-16；纯NumPy端未导入torch，另测float32导出1e-6容差，均非ARM/ROS原生性能。
- IFW原始386帧新未训练旁路253帧诊断分数、旧MIL249窗口，两条开关完整感知输出SHA均6aa6629066956d9949e4188d8c31b1ea69ed6214d0b4a112b1c8924359a21017，514生产路径SHA保持。新旁路PC p50约0.421ms/p95约0.685ms只是局部开销；0候选受untrained状态强制禁止，不当低误报。新增两次开发错误（预检括号、夹具常量名称）已修，早期产物/最终verified结果分开保留。
- 证据docs/evidence/2026-10-23_fall_event_model/（42401路径基线、前件、CHECKS.json、verified数值/预检/双回放），说明ML/docs/fall_event_model_20261023.md。0优化器更新，显式拟合分支未运行，其收敛/模型质量未验证；没有完成M5。独立IFW事件和长时真值、实际拟合后的冻结对照及原生板端仍缺，效果/物理有效性/板端性能UNKNOWN；无部署/采集/下权重/HR-09/Git写操作，既有数据/junction不改。


### 2026-10-23 真实输入与目标完成条件核对

- 前一目标轮为进展（时序接口实现与验证）；本轮重新对照M3–M6和事件指标。data/sessions为22目录/21份meta，声明总时长461.483696s，全部human_annotations为空、无人编号/视频时钟字段；cap_20261017_141348缺meta，原样保留。data与ML/data无fall_events_v1 JSON，data/annotations不存在；找到的3个工作区视频为点云跟踪渲染，不是独立真值。时长不计已确认负例暴露，事件数/现场指标仍UNKNOWN。
- 标注/事件相关测试-B -W error通过；一次旧解析合成CLI评测JSON与冻结产物逐值一致，未新增效果结论。前轮记录11个源码/文档SHA在本次记录更新前一致，无算法/模型/数据/设备/Git写操作。机器证据docs/evidence/2026-10-23_fall_remaining_inputs/INPUT_AUDIT.json含每份metaSHA、命令/日志与未满足要求。
- 当前实质缺口是独立目标域人员/事件/同步真值和长时数据；M5还缺真实拟合后冻结对照，M6缺原生板端验证。可用软件工作不能证明物理事件，停止重复扩充接口。本次为同一真实输入阻塞的第1次连续核对，目标active而非complete/blocked；若有资料位于其他目录，需要其位置才能继续真实评测。

### 2026-10-23 真实输入阻塞复查（第2次）

- 前轮输入盘点提供新证据；本轮复核21份metaSHA均未变，data/annotations仍不存在，data与ML/data仍无fall_events_v1。未收到外部真值路径，剩余M3–M6没有可独立完成的现场证据工作；本轮属于no progress，不重复运行已通过的模型/合成测试。
- 机器记录docs/evidence/2026-10-23_fall_remaining_inputs_recheck2/RECHECK.json。同一实质阻塞连续2轮，目标仍active且未完成；无软件/模型/原始数据/设备改动。

### 2026-10-23 真实输入阻塞复查（第3次，目标blocked）

- 前轮及本轮均no progress；重新核对21份metaSHA未变、无新增完整会话、无data/annotations及fall_events_v1。同一真实输入缺口连续3轮，且没有能建立独立物理事件证据的剩余本地软件动作，已调用目标工具设为blocked，整体未完成。
- 证据docs/evidence/2026-10-23_fall_remaining_inputs_recheck3/RECHECK.json。恢复需独立IFW事件/人员/同步资料位置或新的现场数据；已保留全部软件与回放结果，不重复测试或扩充无关接口，无算法/模型/原始数据/设备改动。

### 2026-10-23 总控制台最新几何预览与明确授权的板端影子发布

- 用户“继续”后先完成总控PC集成；随后明确“部署几何影子模式”。复用人体开发回放接秒制几何，按源帧顺序预计算并添加测量/候选栏，GRU不加载。1544组旧API字段逐值一致；源码、冻结EXE、桌面实际目标自检通过，EXE与ZIP更新且旧版备份，快捷方式/passthrough不改。浏览器341帧测量正常，前后跳帧UNKNOWN保持。
- 新增只读LiveGeometryShadow，单一标准包用显式manifest特性开启，沿用同一ML纯NumPy内核；不改原状态/正式事件/持久化，源错配/预测/掉锁/过期输出UNKNOWN。标准stage/preflight后发布60ce5d467478863c，页面d8f87458b2f3，run20261023T035039Z_1500a566。总控实时锁定入口实见新版本/影子行，网页warning/error0。
- 本地核心710/ML136/页面22通过，最终定向5与RK3588 Python3.8.10/NumPy1.17.4原生5通过（含正几何候选不写正式事件）。原生386帧旧95版/新关/新开原算法SHA均33509fbe90b46a0171998f5b9cfbc8c31e9c039d7cbe4c4c34cd58da82c2ec5d；影子和PC最大差2.44e-12。旧候选三组串行计时单列，最终候选另跑开关1轮，测试循环（含校验/序列化）P95 88.377→89.215ms、后处理P95 16.048→18.109ms；非现场人体负载/端到端承诺。PC阶段另有总控9Python/24JS、current19/capture69/标定2通过。
- 114项manifest与HTTP包字节一致，runtime/实际node/capture版本一致；40条连续状态确认shadow=true、model_loaded=false、confirmed=false。最终健康通过，至4729帧约8分钟worker/postprocess错误0、重启0、累计队列丢帧0；核验时无锁定可评估目标，shadow UNKNOWN，非零误报证明。boot、驱动PID/启动时间/配置、profile与26项会话登记SHA前后保持，录制false。人体node/capture/http按发布控制器重启，旧release保留且未实际回滚，无新采集/训练/改驱动网络/Git写操作。
- 异常保留：板端旧临时xyz.npy与原SHA不一致，首次验证拒用；从本机原始会话重建新副本，原记录/传输SHA一致后验证，旧临时文件不覆盖、原因UNKNOWN。初次计时与旧版比较任务有重叠，未用于最终计时结论。证据docs/evidence/2026-10-23_console_event_integration与2026-10-23_event_geometry_shadow；说明docs/EVENT_GEOMETRY_SHADOW.md。本次软件发布完成，真实事件/长时负例和训练模型效果仍缺，人体/物理有效性UNKNOWN。

### 2026-10-23 传感器适配判断与一次性开发计划

- 新增 `docs/RADAR_DATA_FIT_PLAN_2026-10-23.md`：从 IFW192S 的原生 192×240 固定射线网格出发，判断该数据格式/扫描方式适合什么，并给出 W0–W8 一次性开发包（range-image 前端、距离自适应跟踪、AI 标注+人验、事件头、板端移植、评测与数据采集）。
- 实测证据 `docs/evidence/2026-10-23_sensor_characterization/`：386 帧上网格 192×240、az 0.5°/el 0.469°、10 Hz/103.65 ms、49,107 点/帧、有效点 75.7%、零回波 24.2%、静止射线 σ 1.17–1.71 cm（1–10 m）、深度边缘 >0.2 m 占 11.2%；2 m 人体约 2,385 点，按 1/r² 到 8 m 约 149 点。复现脚本 `analyse_sensor.py` 与 `METHOD.md` 同目录。
- 关键判断：近距 2 m 现有链路目标点集 2,385 点、距离图像聚类 2,452 点（约 97% 重合），近距不是瓶颈；主要矛盾是 0.1 m 冻结占据背景、0.25 m 固定水平栅格、100 ms 整帧扫描、远距碎片和无跌倒真值。计划把表示改为逐射线距离图像+残差、聚类改为深度连续+距离自适应、标注改为 AI 提候选+人验子集；AI 不能替代跌倒事件真值，没有 staged/public 跌倒数据时目标域效果维持 UNKNOWN。
- 本轮只读分析 `data/` 并新增计划/证据；未改生产代码、配置、模型、数据或 junction，未部署/采集/训练/下载/开 HR-09，无 Git 写操作。

### 2026-10-23 W1 标定距离图前端与全帧离线对照

- 新增4个纯NumPy核心模块及`replay_range_frontend.py`、22项回归、使用说明；显式前缀背景/绑定/未知格、深度支撑、run连通和实测来源行，3D合并仅显式消融，默认生产链不接入。找到既有192×256方向表，纠正192×240等角近似及float32时间/边缘比例解释；386帧14,361,073个非零点全量无碰撞，range重建误差0。
- 386帧逐格/组件来源通过，3重复账本SHA `6cb7da753dee47e6beb9685005ab624381cfc290ebd6e29f26cdb3dd257281b1`；120前缀及本地Python3.8/NumPy1.17完整386账本一致。780帧完成；22目录卡为20可读/1缺meta/1缺points。旧感知链完整SHA保持`6aa6629066956d9949e4188d8c31b1ea69ed6214d0b4a112b1c8924359a21017`。
- 258旧锁定参考帧：诊断分量点数中位2402.5，总旧行保留率97.0892%/主分量96.8497%，分散度中位0.2165%/P95 0.6976%/最坏5.4480%。最坏f360两片最近8.3088cm>6cm门，拒合保留；可选merge收益小且67帧扩张参考外成员，未默认采用。它们不是人体GT指标，最佳交集分量不是新目标选择器。
- G1未全过：最终串行3轮前端PC P95 15.911/19.307/15.829ms，写压缩数组另列15.039ms；不以早期单次8.99ms冒充稳定<10ms，也不隐藏最坏分散度超5%。核心732/capture69/标定2/旧3.8定向22全部`-B -W error`通过；首次1.17 NaN比较告警失败日志保留，修后真实全帧核对通过。
- 证据`docs/evidence/2026-10-23_range_frontend/`含前件SHA、逐帧数组/账本/计时、原始方向核对、重复/前缀/兼容、合并消融、最坏帧探针与图。说明`docs/RANGE_FRONTEND_W1.md`。未动既有数据/junction/历史证据/设备，无部署/采集/训练/下载权重/HR-09/Git写操作；人体/跌倒效果、物理资格、板端性能UNKNOWN。下一步是decode开销和基于时序的碎片归属，G1未通过前不把W2集成视为已完成。
- 全文件SHA核对发现范围外`pc_apps/bathroom_demo/range_pipeline.py`从118cc0e2…变为01ebbcf4…，写入来源UNKNOWN，本会话未编辑/回滚，首次完整性断言失败日志保留；单列变化而不冒称全仓未变。主线src/webui/console/replay既有源码保持，bathroom demo不计入W1验证。

### 2026-10-23 浴室小场景采集协议

- 新增 `docs/BATHROOM_FALL_CAPTURE_PROTOCOL.md`：明确本次目标是浴室小场景（0.5–3 m），不是大房间/10 m 泛化。安装三方案（角落高位推荐/天花板/门上方）、环境状态矩阵（干湿×浴帘×淋浴蒸汽×玻璃/镜面/浴垫/门）、6 个浴室跌倒动作、20 段浴室负例、长躺 5 s/30 s/2 min、马桶长坐 5 min 关键负例、fixture/遮挡/玻璃/蒸汽分层。
- 规模按浴室重定：试点 3 人×6=18 事件 + 60 段负例；正式 8–10 人×6=48–60 事件 + 160–200 段负例；长时用 ≥20 h 全屋日常（含浴室进出），不把“浴室站 20 h”当误报分母；同时报每墙钟小时、每浴室使用小时、每次使用误报。
- 更新 `docs/RADAR_DATA_FIT_PLAN_2026-10-23.md` W7/3.2：浴室按 1/2/3 m 分层（门口 4 m 另计），背景模板必须按浴室重采（现有 21 段不是浴室数据；B1 计划也已指出大房间空场模板在浴室不可用）。
- 本轮只写协议/计划；未采集、未连接设备、未改生产代码/配置/模型/数据，无部署/训练/下载/HR-09/Git 写操作。浴室真实效果仍 UNKNOWN。

### 2026-10-23 浴室 Demo 原型（独立，非生产前端）

- 新增 `pc_apps/bathroom_demo/`：`range_pipeline.py`（等角 192×240 距离图、逐射线背景、深度连续分量、跟踪、规则状态、合成胶囊跌倒）、`fall_hmm.py`（5 状态因果 HMM）、`make_demo.py`/`demo_template.html`（离线 HTML 播放器）、`test_range_pipeline.py`（14 项）。输出 `docs/evidence/2026-10-23_bathroom_demo/`（386+120 帧、`SUMMARY.json`、`metrics_*.csv`、contact sheet）。
- 真实 386 帧：281 帧有目标，目标点中位 2,423、距离 2.028 m、高度 1.752 m；规则层 0 跌倒，HMM 0 跌倒/0 长躺；HMM 在出生低姿态处输出 `low_unconfirmed` 而不是跌倒。合成胶囊 120 帧：第 35 帧 `fall_suspected`、第 85 帧 `long_lie_suspected`（demo 的 long_lie=5 s；生产协议 30 s）。14 项测试 `-B -W error` 通过；PC P50 19.7 ms/P95 26.9 ms（非板端）。
- 与 W1 的关系：本 Demo 用等角 192×240 近似网格，只用于可视化/跟踪/HMM；生产测量以 `src/human_fall_detection/core/range_image.py` 的标定 192×256 方向表和 `docs/RANGE_FRONTEND_W1.md` 为准。前一轮 W1 SHA 记录中 `pc_apps/bathroom_demo/range_pipeline.py` 的变化来源为本会话新增/编辑，不是外部写入；W1 源码/证据未改。
- 未采集浴室数据、未改生产链/配置/模型/设备，无部署/训练/下载/HR-09/Git 写操作；浴室召回/误报/板端性能仍 UNKNOWN。

### 2026-10-23 完整执行计划与 AI 提示词

- 新增 `docs/FALL_DETECTION_EXECUTION_PLAN_2026-10-23.md`：按 P0 G1 处置（f360 逐行归因、延迟拆分、不改 6 cm 门）→ P1 W2 接 W1 source_rows → P2 W3 200 条人验 → P3 W4 HMM/规则对照 → P4 W5 板端影子 → P5 浴室试点 → P6 评测，给出文件、门槛、时间表、停止条件和证据格式。
- 新增 `docs/FALL_DETECTION_AI_PROMPT_2026-10-23.md`：可直接交给代码代理的完整提示词，含先读清单、W1/G1 当前事实、红线、P0–P6 步骤、测试命令、输出格式、停止条件和第一动作。
- 本轮只写计划/提示词；未改算法/配置/数据/模型，未部署/采集/训练/下载/HR-09/Git 写操作。G1 仍按“正确性通过、尾部与 PC 延迟未过”记录；目标域效果 UNKNOWN。


### 2026-10-23 执行计划完善与开工提示词

- 重写两份FALL_DETECTION计划/提示词，修正原G1/G2与候选20/30ms预算冲突、f360精确21/163行和集合分母，补同源绑定/指标测试/受控profile、跨帧来源与缺测、标注precision/recall、事件匹配/暴露统计及软件/外部数据依赖；不再要求人工输入才能推进独立代码，不写ML或自动拟合/部署。
- 定向22项-B -W error通过，原始386帧离线CLI账本与历史SHA 6cb7da753dee47e6beb9685005ab624381cfc290ebd6e29f26cdb3dd257281b1一致，468源码文本SHA保持、8本地链接通过。首次默认临时目录权限失败保留，工作区TEMP/TMP重跑通过；证据docs/evidence/2026-10-23_fall_plan_revision/，最终verified/CHECKS.json。
- 仅修改计划/提示词/状态/日志；未执行P0逐行归因或三轮优化，未实现W2、未动数据/junction/历史证据/设备/模型/Git。原G1仍未过，目标域与新链板端UNKNOWN；下步按新提示词先P0再显式W2。

### 2026-10-23 外部跌倒项目借鉴精读

- 精读teguh/lcfall/fusion/mmfall/RadmoX/DarkSZChao并对照现有实现，新增`docs/REFERENCE_ADOPTION_2026-10-23.md`。六仓库210个文件与远端提交对象匹配；借同步审计、采样质量与严格隔离的对照设计，保留当前绑定地面、W1与秒制事件，不新增重复背景/模型链。
- 修正点计数min_hits、消息数48帧、逐帧p1抵消下降风险、测试分布参与预处理选参、fusion19类及lie_down末姿态默认错标、RadmoX报警后3s和mmfall未来帧。独立小算例已复现空帧归一化成非零点、单帧5点满足hit、FPS重复索引、p1平移抵消与末姿态错误。
- 最终前端22/绑定7/状态机34项`-B -W error`通过；386帧全部历史共同字段逐值相同，新增10个诊断字段，当前完整SHA为c7ad4134b09088505b5bfce229aabd31ac9745bdf95d065cd6b66ea92781d4b4且两次当前运行相同。首次历史完整SHA断言失败保留；期间5个W1源码/测试有本会话之外变化，来源UNKNOWN，未编辑/回滚；最终重跑盘点378个现有源码文本稳定。证据`docs/evidence/2026-10-23_reference_adoption/`，最终CHECKS.json。
- 本轮只写说明、状态、日志和机器证据，未改生产/配置/ML/原始数据/设备，无部署、采集、训练、权重下载、HR-09或Git写操作。G1未由本轮重新判定，目标域人体/跌倒与新链板端UNKNOWN；后续沿现有P0→W2及同步伴随审计推进。


### 2026-10-23 联合录制下载直连修复与215952恢复

- 复现系统代理/IDM接管：同一points.bin经系统代理HTTP204/0B，直连HTTP200/71,310,848B（0.734s）。路径原本正确，captures/remote解析到data/sessions；不改系统网络/下载器设置。fetch.py控制面/HEAD/数据面统一私有无代理opener，失败补状态码/字节数/异常日志，联合与同步共用。
- cap_20261023_215952仅补缺失points.bin：51帧，SHA256 d4f7cc881c614af3ceeaf9ab81040833d4a9fdb049f49d7bc7b5d5340b9742c5；meta与板端逐字节相同，既有相机69帧/索引/meta/joint失败记录全部SHA保持，未改板端登记。当前8901目录识别local=true，完整HTTP读取SHA一致；51帧离线解码与69帧JPEG索引通过。
- fetch15（含模拟IDM全局204代理完整ready→transferred本机端到端与204诊断）/联合11/console Python9+JS24/回放JS46通过，Python均-B -W error；Python3.8语法通过。证据docs/evidence/2026-10-23_joint_download/，包含43044项含未跟踪工作树基线/传输探针/恢复/回放/源码SHA；数据新增文件不属基线删除或移动。
- 现有控制台INI源码旁路有效，联合每次runpy加载新版fetch；同步面板缓存模块需重开控制台。未重打包/部署/采集/启停板端/改驱动网络或Git写操作。


### 2026-10-23 P0证据契约修补与显式离线W2

- 开工五个W1源码SHA与历史最终版相同；先保留真实旧CLI前件，再修ground输入/RAW坐标/grid/epoch/provenance与背景cache侧车，补compare/reference_rows/percentiles/SUMMARY直接回归、有效n/微汇总及组件统计。386帧全部保存数组和旧字段逐值一致；新账本SHA c7ad4134b09088505b5bfce229aabd31ac9745bdf95d065cd6b66ea92781d4b4，旧6cb7da…仅属前件。
- f360逐行守恒2263=2100主片旧行+121其他存活+41去噪拒+1背景未知；主片2121=2100+21新增，未覆盖163。分散度121/2221、未覆盖163/2263、union2221/2263不混写；row34145前缀仅4观测。无decode丢失，语义尾部UNRESOLVED。扩张分清79总点数/67参考外新增行。
- 新增纯NumPy W2 tracker/features/CLI与16项合成回归；复用既有测量几何/保守支撑归组，因果ray/空间关联、竞争unknown、低姿态出生、预测空测量、时间/绑定重置。初次竞争回归和组合竞争反例已修并留日志；仅显式离线range_v1，生产默认不接入。
- 386/780各三轮确定，120前缀逐字段一致，去旧参考纯推理SHA不变。f360当前23+17归组2308行=2221旧+87参考外，没有补回波或按旧参考挑121行。独立XYZ/组件/特征审计1551691实测轨来源行通过；本地3.8.10/1.17.4定向45及386整段通过，最大差8.88e-15，非ARM。
- 代理258帧中256有目标99.2248%，诊断组件行数加权交集99.9512%，f372/373全帧97%门失败；780非预热730帧，W1有组件378/无352，W2有目标355/空375、有到无16次。不是人体召回/真人ID切换率或780效果通过。
- 三轮串行细分/无细分及原始n/P50/P95/P99/max保存，不相加阶段P95或挑最快。G1a2402.5 PASS、G1b5.448% FAIL，G1c最终8.934/8.934/12.882ms仍未稳定<10；W1+W2含特征P95 386为23.521/18.952/22.025ms、780为27.600/21.895/23.771ms，原G2<15及候选PC≤20均未稳定过，更早慢轮保留，负载归因未解。
- 核心755/capture69/标定2全部-B -W error通过。首次3.8相对路径写SUMMARY失败已修并保留日志；全仓42871文件基线跨编辑边界的8路径用显式前件校正、原扫描保留，一次性SHA lambda文件未关闭的ResourceWarning单列。证据docs/evidence/2026-10-23_range_p0_w2/，最终verified/G1_DISPOSITION.json和G2_DISPOSITION.json；说明docs/RANGE_TRACKING_W2.md。
- 本会话未改数据/junction/历史证据、ML/、生产默认或设备，无Git写操作/部署/采集/拟合/训练/下权重/HR-09。人体点级/真人身份/倒地/浴室/物理资格/板端UNKNOWN。收尾发现其他会话更新PROJECT_STATE/PROGRESS与fetch下载修复，保留并合并，不归本轮认领。独立离线开发已完成，下一步CPU尾延迟与独立目标/身份/事件证据，不重复核查缺失GT。

- 中断恢复收尾：冻结源码SHA保持，45项定向-B -W error再通过，120帧显式离线CLI与最终既有前缀逐字节一致；核对结果verified/RESUME_CHECK.json。根目录G1/G2指向最终结果，初始P0处置独立保留，状态/日志的并行外部追加按混合归属记录。


### 2026-10-23 独立离线同步审计开发

- 按不干扰现有开发的范围新增tools/sync_audit.py、tools/test_sync_audit.py及docs/SYNC_AUDIT.md，无现有生产调用者。五源文件与锚/工具SHA绑定；自动建议不自动采用，双路原始锚、来源、不确定度、独立check残差/跨度漂移可追溯，修改后旧审计STALE。输出不进原始数据、不覆盖历史。
- 最终11项新增回归、capture69/联合录制11均-B -W error通过；3.8语法解析通过，非3.8运行时测试。既有215952的51雷达/69相机帧全量两次逐字节一致，重查UNCHANGED，索引字节/连续性/JPEG首尾标记通过。合成锚CLI参考时钟变化触发STALE；仅软件夹具，不是该会话真值。证据docs/evidence/2026-10-23_sync_audit/verified/，周边回归日志与早期运行在父目录。
- 未改W1/W2/演示页/控制台/原始会话/设备/ML，无部署、采集、训练、权重下载或Git写操作。真实同步偏移/误差、采样丢帧与人体/跌倒效果UNKNOWN；提取器自报丢帧另列。同步审计工具已可独立使用；采样来源审计与同输入规则对照尚未作为本轮新增实现，不认领其他会话进度。

### 2026-10-23 单会话点云/相机对比页（单人绿框 + 跌倒候选）

- 用户要求"单人人体框定绿色从头到位、跌倒识别报警并展示，点云与视频放一个 HTML 对比"。新增 pc_apps/range_fall/session_compare.py、template.html、test_session_compare.py、test_page.js、README.md；对 cap_20261023_221125（126 雷达帧 / 140 相机帧 / 12.96 s）生成单页离线对比。链路全部复用既有实现：core.range_image.ScanGrid（标定 192×256）→ 离线逐射线 p98 背景 + range_denoise → range_components → RangeTracker（W2 单目标）→ rebuild_candidate → FeatureExtractor + StanceBaselineCollector + FallStateMachine；未新增检测算法。
- 会话内容：相机可见单人走入→下蹲/跪→趴地→起身离开。点云侧同一 track g0_t0001 覆盖 112/126 帧（0.21–11.71 s），绿框随目标移动/下蹲/躺下。地面由本会话点云 RANSAC 拟合：设备高 1.309 m，法向 (-0.426,-0.010,0.904)，内点残差中位 12.6 mm，above_fraction 0.73，physical_verified=false。背景为整段逐射线 p98（非因果），仅展示用；生产 W1 仍要求显式空场前缀。
- 状态机结果：low_posture_unclassified 4.87 s 起、suspected 6.43–8.71 s（23 帧，原因 measured_descent+sustained_low_posture+lying_pose_supported）、recovering 9.33 s 起；4.87–5.70 s 为跪姿低姿态且无 lying 支持，按规则不升级。confirmed 关闭，events=[]。自动站立基线未建成（进入后位置/高度不满足 3 s 稳定门），站立段显示 unknown（未建立站立基线），不影响 suspected 判定。
- 页面：左侧 3D 点云用自写 lookAt/透视/画家算法（无 three.js/CDN），绿点=目标实测点、绿线=三维框 12 条边、地面 0.5 m 网格、青点=传感器原点；右侧相机最近帧并显示"接收时刻-雷达帧时刻"；报警条按状态变色；底部目标高度中位曲线 + 逐帧状态色条 + 红线报警区 + 时间轴；支持拖动/滚轮/双击复位/播放/跳到报警/点击时间轴/方向键。相机无外参，故不把点云投影到画面。
- 测试：16 项 Python（-B -W error：地面拟合含天花板竞争、背景分位与稀有单元、显示基正交与地面归零、体素采样确定性、厘米量化、相机索引校验/最近帧、输出目录守卫、真实会话端到端）与 7 项页面 JS（最小 DOM 桩：首帧绘制、报警变色与原因码、播放/键盘/跳转、无相机降级、无目标不崩溃、拖拽缩放、时间轴点击）全部通过；页面脚本 node --check 通过。首次运行中 3 处断言与 2 处夹具错误（JPEG 长度、NaN 单元、浮点等距）已修正并保留过程。
- 产物 docs/evidence/2026-10-23_single_person_fall_compare/：index.html（27 KB）+ data/frames.js（4.6 MB）+ camera/123 张 + PREVIEW.png（站立 014/过渡 047/报警 062/恢复 090）+ SUMMARY.json + FRAMES.jsonl + GROUND.json + README.md。
- 未改 W1/W2/生产默认/配置/数据/junction/设备/ML，未部署、未采集、未训练、未下载权重，无 Git 写操作。人体语义、跌倒真值、召回/误报、目标域与板端性能仍 UNKNOWN；suspected 不等于 confirmed。
- 按用户要求删掉相机时间差一行末尾的“（无硬件同步）”括注；页面底部说明块仍保留“无硬件同步、无外参”的边界陈述。16 项 Python 与 7 项页面 JS 通过，页面/SUMMARY/CHECKS 已按新源码重新生成（artifacts 130，14.0 MB）。
- 演示页按“项目演示、不加文字描述”收敛：删掉相机时间差行的“（无硬件同步）”和报警条里的“confirmed 关闭（无真值）”；顶部徽标去掉，口径与边界收进“说明”“复现与参数”折叠区；状态标签不再带括注。16 项 Python + 7 项页面 JS 通过，页面/SUMMARY/CHECKS 重新生成。

### 2026-10-23 W2与同步审计合并推进

- 将链接任务“开始跌倒检测借鉴开发”的已有同步工具与P0/W2接成独立`tools/range_experiment.py`；新增26项回归和`docs/RANGE_EXPERIMENTS.md`。复算同帧组件并集/互斥归属、decode五桶守恒与重复分母，校验五源/配置/地面/provenance/完整源码清单/推理摘要，源码漂移或清单缺项STALE，不用旧证据解释新源码。规则旁路复用既有FeatureExtractor/FallStateMachine，同输入且不拟合基线、不启确认。
- 新跑386/120帧W2 CLI，联合审计386/780及51联合源；1,551,691实测轨来源行无重复/外来/非法，因果前缀相同，386纯推理SHA c8ad205a…与780既有3b165209…保持，38个原W1/W2源码/测试及sync工具SHA不变。规则386 unknown376/低姿态未分类10、780 unknown780；不是跌倒/误报成绩或W4/HMM完成。
- 51雷达/69相机源两次完整输出相同、重查UNCHANGED；2,546,816原始=1,890,889有效+620,722零近拒绝+35,205重复回波。原joint failed/下载错误与当前71,310,848B完整分别记录，最大header间隔0.207329s不冒认实际丢帧；无双路锚，物理同步UNKNOWN。未为该段臆定空场前缀。
- 新增26/同步11/核心755/capture69/联合11均-B -W error通过；隔离3.8.10/1.17.4新增26/同步11、实际386帧CLI通过，来源账本逐字节相同、规则数值最大差1.11e-15。首次隔离CLI缺tools导入路径已修，失败日志保留；手工只读检查曾遇GBK解码及未关闭句柄的ResourceWarning，另记诊断错误，不计算法通过。证据docs/evidence/2026-10-23_range_sync_integration/，最终complete/CHECKS.json及冻结SHA、命令与逐帧账本。
- 原G1a通过、G1b5.448%/G1c<10ms、原G2<15ms及候选PC20ms仍未稳定过，本轮不重判性能。人体/身份/倒地/浴室/实际采样丢帧/物理同步/新链板端UNKNOWN，f360语义仍UNRESOLVED。未改生产/W1/W2/同步工具源码、数据/junction/历史证据/ML，无Git写操作或设备/拟合/训练/权重下载。其他任务并行新增单会话对比页和状态/日志已保留且不认领；本轮合并软件完成，下步CPU尾延迟及独立锚/GT，不重复缺失核查。

### 2026-10-23 cap_20261023_215952 实时纸飞机绿框（点云 × 相机同屏对比页）

- 用户要求“实现实时的纸飞机框定绿色标注从开始到结束、展示，点云和视频放在一个 html 对比”。新增 `sidequests/plane_track/r03/`：`plane_live_core.py`（射线格 → 逐射线背景 → 前景 → 聚类 → 关联 → OBB，纯 stdlib+NumPy，KD 树可选，无 scipy 时退化体素哈希）、`make_plane_page.py`（跑检测 / 量单帧耗时 / 导证据 / 生成页面，ffmpeg 编 MP4 后 base64 内嵌）、`compare_template.html`（自写 canvas 3D 点云 + 视频 2D 覆盖层 + 时间轴）、`test_plane_live_core.py`（23 项）、`check_page.js`（页面自检 24 项）。
- 会话 cap_20261023_215952（只读）：51 帧 / 254.7 万点 / 5.29 s，相机 69 帧。第 0–20 帧按射线格取距离中位数建立背景（37,208 / 49,152 条射线有背景点），之后冻结；前景 = 同射线距离近 >0.12 m ∪ 3D 上 0.035 m 内无背景点；0.09 m 单链接聚类，≥16 点且跨度 ≤0.7 m；命中 ≥4 或单帧位移 ≥0.30 m 确认；PCA 有向盒（中心取投影区间中点，半长 = 区间半宽 +2 cm）。
- 结果：第 24 帧（2.48 s）首次检出 28 点、第 26 帧确认；飞行 25–30 帧速度 1.98/3.11/3.14/4.82/2.88/0.58 m/s（质心 (1.28,1.68,0.94)→(2.40,0.90,0.57) m，第 28 帧框被 100 ms 拖影拉到 0.71×0.40×0.16 m）；静止 30–50 帧中心 (2.31,0.87,0.55) m、框 0.42×0.26×0.13 m；相机 2D 框 26 帧（t=2.43–4.97 s，落到桌面 (576,313)-(651,333)）。时钟偏移用起飞/落地两个共同事件锚定 = 1.065 s（两锚相差 0.095 s ≈ 1 帧）。单帧检测中位 16.5 ms / P95 19.5 ms（本机 Python 3.12 / NumPy 1.26，非板端），背景窗口结束建索引那一帧 354 ms（一次性）。
- 页面：`pc_apps/console/plane01_pages/cap_20261023_215952/compare.html`（单文件 1.05 MB，内含 MP4 + 背景点云 + 逐帧结果，离线双击可开；支持 `?t=` 深链、拖拽旋转、时间轴/倍速/循环）；`plane01_pages/index.html` 加了入口链接（手加，`sync_plane01_pages.py` 重跑会丢，已在证据 README 注明）。
- 测试：r03 23 项 `-B -W error` 通过；页面自检 24/24；console Python 9 + JS 24、human_capture 69、human_replay JS 46 通过；Chrome 无头截图 `page_flight.png` / `page_rest.png` 实拍绿框与视频框同现。证据 `docs/evidence/2026-10-23_plane215952_realtime/`（README / CHECKS.json / detections.json / contact_sheet.png）。
- 诚实口径：目标语义 UNKNOWN（用户口头“纸飞机”，无分类器、无 GT；1 段 5 s、1 目标、1 次抛掷，不构成统计指标）；背景窗口后冻结，长时场景需周期重估，本页不声称支持；相机与雷达无硬件同步（偏移锚定 ±1 帧）、无投影标定，2D 框与 3D 框各自独立、不能互相当真值；单帧耗时为 PC 实测，板端 ARM 性能 UNKNOWN。未改 data/ 或 junction、未改会话数据，未部署 / 采集 / 训练 / 下模型，无 git 写操作。

### 2026-10-24 按指定效果推进可复用回放展示

- 用户确认最终展示形态为点云绿框+相机+高度曲线/状态/时间轴/报警。新增range_fall/replay_compare.py、replay_template.html及15项Python/14项JS测试；只导入已保存结果或已审计W2/规则账本，不运行拟合或算法更新。说明docs/RANGE_REPLAY_VIEW.md，README/RANGE_EXPERIMENTS和当前状态已接入口。
- 126帧样例冻结SHA通过，112帧绿框/23个疑似帧及点、框、指标、状态逐值保持；旧非因果/来源行缺失边界不改写。实际导出因果386/120/780，前缀相同、1,530,598目标来源行计数与账本匹配、纯推理SHA保持；38个既有W1/W2源码/测试不变。两因果会话无相机，未借其它会话图片填补。
- 修过期/加载失败/延迟相机回调、失锁未知、测量空值、源时间轴/绘制耗时补偿、分段曲线/报警/断档色条；0.20s只是显示预算。首轮旧预览126导出102.269s，7条网格线屏幕NaN但深度有限；独立预览拒绝非有限/近面后/越界坐标，新增回归。保留首轮慢日志/部分产物及主动停止本地worker记录，未停止设备服务；诊断过期PID和NaN探针口径在RUN_DISPOSITION单列。
- 新增Python15/JS14、range45/既有显示helper9/旧页面7通过；Python均-B -W error。隔离3.8.10/1.17.4新增15及实际126/386完整导出通过，显示数据与3.12逐值一致。file://浏览器验证被协议策略拒绝，未绕过；以DOM/canvas测试和同源点云相机PNG核对，PNG非浏览器截图。证据docs/evidence/2026-10-24_range_replay_view/，最终complete/CHECKS.json和各页面。
- 未改生产默认/W1/W2/旧生成器模板/原始数据/junction/历史证据/ML，无设备操作、拟合、训练、权重下载或Git写操作。旧生成器和PROGRESS外部修改单列保留，不归本轮认领。G1/G2失败及f360语义UNRESOLVED保持，人体/身份/真实跌倒/浴室/物理同步/新链板端UNKNOWN；后续沿已固定展示契约推进运行时/尾延迟，不重复GT缺失核查。

### 2026-10-24 显式逐帧运行时 → 源节奏 → 同款动态页 → 整链诊断

- 新增core/range_runtime.py与range_fall/runtime_replay.py及7+7项新回归，复用W1/W2/既有特征和规则；不读未来检测、不拟合、不补点、confirmed关闭，生产默认旧链。来源/时钟重置停用背景；前缀缺帧不臆定空场；队列跳过帧显式打断低位时长/下降拟合。复用size-1 latest单worker，逐输入记录五个单调时钟及丢弃处置，消费序列单独重放。
- 同款模板持续接收，本地127.0.0.1服务/浏览器各240帧，暂停和历史选择不被最新帧覆盖，源帧缺口断开曲线/报警。HTTP实际120/120；浏览器暂停60时缓存到110仍停60，恢复119看到2884实测点/绿框/1.13m高度，同源相机缺失。当前离线会话http://127.0.0.1:61100/，进程身份在HTTP_CHECK；入口与完整数字见docs/RANGE_RUNTIME.md。
- 386/780各三轮全帧与旧W2/来源/规则0新增差异，纯推理SHA c8ad205a…/3b165209…保持，120前缀逐值一致，原W1/W2清单38项SHA不变。1×源节奏386处理384/384/383、丢2/2/3，780各处理778/丢2；消费序列重放均0差异。386第三轮跳过309相对全帧W2有2帧、规则派生11帧差异，归因实际缺测及连续段重开，不称改进。注入220ms落后120帧处理76/丢44，账本完整。
- 三轮含事件算法P95：386 24.741/24.236/23.041ms，780 28.682/28.992/30.754ms；含来源核验/显示/JSON/IO/发布循环79.712/75.412/79.426与77.071/77.551/81.500ms。源节奏本地发布帧龄P95 79.345/82.553/81.605与71.796/71.293/71.835ms，不是设备延迟。初始化281.472ms覆盖50/51；第三轮308输出IO162.179ms、循环227.721ms覆盖309，底层阻塞原因UNKNOWN。原G1c/G2及候选PC20ms仍FAIL；G1a原PASS/G1b5.448% FAIL/f360 UNRESOLVED保持。
- 显示去重单因素优化保持完整显示账本逐值相同，120帧显示P95 41.680→14.988ms；来源正确性检查保留，profile确认逐行类型校验仍是热点。首组可能与测试重叠的基线独立保留不用，正式采用无并发测试的serial_baseline三轮；所有原值、预热/初始化及n/P50/P95/P99/max在PERFORMANCE与timings。
- 最终核心762（含range52）、离线入口7、JS17通过，既有审计26/展示15通过，Python均-B -W error。本地3.8.10/1.17.4实际52+7测试及386/780完整CLI；测量/状态数值最大差8.88e-15。780 f716拒绝组合有两项诊断漂移0.008672/0.134862m，原W2的3.8完整入口同样复现；完整数值一致性保留FAIL，消费测量/归属/状态通过。保留初始ctypes类型、cProfile相对路径、核验脚本编码错误和差异发现日志。
- 证据docs/evidence/2026-10-24_range_runtime/，CHECKS/FINAL_SOURCE/ARTIFACT_SHA256/命令及逐帧账本。未对会话做地面RANSAC、站姿或模型拟合；完整核心回归含既有合成地面夹具，单列不冒充实测。数据/junction/历史证据/ML/设备不变，无Git写操作。人体/身份/真实跌倒/浴室/物理同步/设备端到端/新链ARM性能UNKNOWN。后续独立热点为来源核验、IO尾延迟和拒绝组合数值稳定性；外部GT与板端实测不阻断本轮交付，不自动采集/部署。

### 2026-10-24 工作区数据清理（点云副产物 / 大文件）
- 按用户指令“只保留点云数据库里面的会话”，清理开发副产物与本目录外非会话数据；先出清单再删（160,932+438 文件）。
- Tier A 仓库副产物：160,932 文件 / 92,656,085,151 B / 86.293 GB，0 错误；只删未跟踪文件（证据 jsonl/npz/npy/bin/打包 zip、旧备份 _archive、构建 exe/zip、pointset 研究点集、tmp），保留 .md/.py/.js/.html/小 json 账本与页面。另清空目录 343 个。
- Tier B data 非会话：438 文件 / 46,082,764,528 B / 42.918 GB，0 错误，逐文件 SHA256；downloads 只留 DOWNLOAD/REQUEST/manifest（URL+sha256 可重下），leveled 只留 gt_store_backup 565.9 MB 与 README_REGENERATION.md。sessions 24 目录 6.80 GB 未写入，registration 未动。
- 清理后工作区 23.84 GB（含 .git 5.0 GB 未动），清理前 153.0 GB，释放 129.2 GB；data 7.44 GB、docs 8.44 GB、sidequests 1.40 GB、ML 1.44 GB、文档收集 241 MB。
- 校验：ITEMS/DELETED/DATA_DELETED 清单均 0 missing/0 size mismatch/0 error；captures 三个 junction 目标均在；22 个有 meta 的会话 points.bin 与 meta 帧计数×stride 全部一致（cap_20261017_141348 原缺 meta、.joint_fetch_staging 为空目录，保持原样）；webui/human_capture capture_lib.test.js 33 通过；human_capture Python 套件见 CHECKS。
- 记录与脚本：docs/evidence/2026-10-24_data_cleanup/（SUMMARY.md、SUMMARY.json、ITEMS/DELETED/DATA_DELETED.jsonl、scan/delete 脚本、check_sessions.py）。删除前已生成清单并两次请求确认，会话内 7 分钟未回复；按用户明确指令执行 A+B，未删 ML/models、gt_store 标注与模型权重。旧会话（2026-10-07/10/11 等不在 data/sessions 内）的逐帧转储不可再生，已在 SUMMARY 写明。
- 未改源码/生产配置/算法，未 commit/push/reset/checkout/clean，未部署、采集、训练或下权重；历史 evidence 中被跟踪的账本文件未删。

## 2026-10-24 2D深度形状旁路首轮（计划1—3，本地完成）

- 新增core/range_shape.py与tools/range_shape_shadow.py：同帧source_rows反查标定栅格，输出像素/角跨度、填充率、Σr²距离代理、边界接触、邻接无效回波及继承组件分布；连续1.2s/最多128帧的变化比。预测/歧义/缺测无形状，换绑定/目标/代次/时钟异常/跳帧重开历史。通用特征接口也可接3D候选，本轮CLI仅验证W1/W2旁路，未改生产默认、目标、关联或跌倒门限。
- 证据docs/evidence/2026-10-24_range_shape_shadow/：41,718项非忽略跟踪/未跟踪文件区间SHA基线（9.598GB，非原子快照，状态在扫描结束记录）。46份原core保持；原逐帧历史账本已清理，重新生成关闭旁路对照，不冒称复核缺失历史。serial386/780各基线+三轮，269/355帧有形状，原跟踪/规则/来源摘要逐帧差异0，描述子三轮一致，两段独立120因果前缀差异0；真实源跳过f104后f105样本数1、历史比值null。
- 三轮新增旁路P95（非预热全部帧）：386 2.677/2.625/2.641ms，780 2.945/2.836/2.890ms；仅实测目标帧分别2.712/2.677/2.674与3.258/3.109/3.301ms。事件链加旁路逐帧总和P95分别30.557/28.911/29.556与35.691/36.188/35.426ms；不含显示/审计/IO/发布，不是设备端到端。早期与扫描/测试重叠的运行保留且排除最终计时，原G1/G2失败不翻绿。
- 126帧非因果p98探索112帧有形状、0帧触表边，但入画f2/f3/f4/f6只有52/44/49/103像素且邻接无回波44.2%/45.5%/49.0%/35.9%；未触边不能证明完整，邻接无回波不等于遮挡。f30/f68像素5330/755、列行比0.444/1.359，Σr²9266.85/4159.03px·m²，仅描述量，不是物理面积或姿态真值。
- 核心全量771（当时含9项新增）、最终2D定向10、入口3、原运行时13均-B -W error通过（重叠数量不相加）。新增4份Python通过3.8语法解析；先前本地3.8运行目录已缺失，实际3.8/NumPy1.17.4与ARM本轮NOT_RUN。已有核心合成拟合夹具不算真实会话拟合。说明docs/RANGE_SHAPE_SHADOW.md，CHECKS/VALIDATION保存具体对照、SHA及计时。
- 首轮计划1—3完成；新特征只旁路，不用质量阈值压制规则。人体完整/遮挡/真实跌倒效果、板端性能UNKNOWN，f360语义未解决。下一步针对观测缺失的反例研究辅助信号，再决定单因素规则接入。未改原始数据/junction/历史证据、设备或ML，无Git写操作；未部署/采集/训练/下载。

## 2026-10-24 2D旁路真实快照交互展示

- 按用户查看效果的要求生成四帧（f2/30/68/88）点云+同源相机近邻+标定距离图+2D字段对照。新证据docs/evidence/2026-10-24_range_shape_view/；126帧重新回放与原旁路完整跟踪/规则/描述子逐帧差异0，目标栅格与来源行一一对应。显示抽稀不参与计算，无新拟合。
- 692KB左右独立会话交互内容，node --check通过；浏览器实测f30→f68，5330→755像素、列行比0.444→1.359，图像与点云同步切换。修复canvas直接使用未解析主题色导致黑色的问题，浏览器复看高亮正常。非因果p98、无同源地面、相机仅接收近邻、非识别效果验证均明确显示，原算法/生产默认未改。CHECKS保存输入/生成SHA与浏览器观察。


## 2026-10-24 ConsoleV2 R0事实基线与用户要求的OpenCode审核

- 新增docs/console_v2/FACTS.md、API_CONTRACT.md候选契约，清点旧入口/多服务端口、16/28B布局、会话与相邻子路由、状态码/Content-Type/缺省/null/安全策略；不写V2业务。实际root open_console.bat缺失、sync在线程内调用fetch.process_session、旧列表固定28B筛选、旧delete直接删及rename/annotations写meta等差异分别记录，删除/只读/全兼容冲突留R1 ADR明确，不修改旧实现。
- 证据docs/evidence/2026-10-24_console_v2_r0/：master/c9c4ee421cb0c8a3e4590b8f5730828b093c759a，41771份非忽略文件/9,609,477,505B的SHA基线在文档初稿后、测试前采集，非修改前原子快照；11份受查旧源码SHA保持。24目录22段meta/points完整，全部28B且大小与帧点数和一致；54份会话文件SHA前后一致，缺meta会话和staging未动，junction未重建。
- 旧Python sessions_test 7、board_mode_test 4均-B -W error通过；JS human_replay_lib 46、人检11、管线38及panel行为集通过。真实cap_20261014_164522只读HTTP列22段→meta逐值一致→完整points流式SHA一致，板端调用0；三帧原字节SHA与首点解码留REAL_READ_ONLY_E2E.json。诊断脚本struct格式与Windows键分隔符两次失败已修且保留FAILURE_01/02，不隐去失败。
- 按用户要求OpenCode只读审查，工具权限全部deny。前两次DeepSeek推理长度/无文本未完成记录保留；第三次实际opencode-go/gpt-6-luna#low完成，提出2中3低文档意见。修正artifact400与job/latest404、Origin缺省/无Content-Type检查、GT null与export、job恢复及证据链接；第四次核对五项全部解决、无R0阻断。03/04完整报告与实际模型/会话/0工具事件均在证据；审核未独立复算作者测试。不是新增永久审核流程。
- R0完成；API仍是候选契约，V2 Golden和旧页面连接新服务NOT_RUN，V2业务/R2性能UNKNOWN。386帧530,652,080B最大49,124点，780帧1,072,369,704B最大49,133点；没有真实16B样本。下一轮R1架构/ADR收口安全语义与多服务拓扑，再做R2真实解码/50万负载/打包门槛；不提前写R3—R9。未Git写操作、部署、设备控制/采集、训练或下载模型；未改旧控制台、数据与生产默认。


## 2026-10-24 ConsoleV2 R1架构与六份ADR（设计交付，OpenCode修后复核凭据阻断）

- 新增docs/console_v2/ARCHITECTURE.md与ADR-001..006；六程序集单向依赖，Host唯一组合根、Api唯一公共兼容HTTP归属；规划Application端口/查询facade、Gate内部executor、独立Retain帧句柄、Qt拥有副本后CopyCompleted归还与Presented分计，首帧Provisional与后台完整SHA分开。不创建V2业务工程/占位实现，未冻结未解决的兼容契约。
- A为R2待验证候选，未因官方README或缺工具链宣称Qt6/.NET8绑定可行/失败；B保持Qt C++壳+C#服务，C需书面同意。dotnet --list-sdks空，仅见8.0.14等运行时；R2需准备SDK并盘点Qt工具链，当前新栈构建/渲染/打包/性能UNKNOWN。首次产品仅127.0.0.1:8901，非环回配置拒绝；端口冲突不自动随机/停旧服务，用户并行安装不等于两监听器共占8901。
- 旧v1 delete/meta写入/远程策略/授权/GET副作用冲突仍列C1-C5，未擅自批准403/侧表作为兼容例外；R7/R9不能据此宣布全兼容。写Python worker无已验证强隔离时UnsupportedIsolation且不启动，不用固定SHA/参数冒称隔离；R6/R8能力仍缺。字节Range续传未验证，不等同任务恢复；默认AppData与D盘隔离跨卷拒绝，未经确认不移动数据。
- 本轮旧Python sessions7+board_mode4均-B -W error通过，JS46/11/38及panel行为集通过；真实cap_20261014_164522只读HTTP列22段、meta逐值、完整points SHA与三帧解码通过，板端调用0，结果与R0完全相同。54份会话文件前后及与R0清单一致，11份受查旧源码保持，69份R0机器证据SHA保持。8份正文/ADR链接/围栏检查与2份诊断Python语法通过；这些不是新栈/安全运行证明。
- 证据docs/evidence/2026-10-24_console_v2_r1/：41848份非忽略文件的区间SHA基线，设计改动前启动、包含活动证据且非原子快照；SOURCE_SHA/DATA_SHA/CHECKS/CONTINUITY/真实E2E/PRIMARY_SOURCES及命令日志。OpenCode实际opencode-go/gpt-6-luna#low、r1audit、0工具事件；首轮指出Gate执行链/worker隔离等问题，修正与作者核对已记录。修后复核返回401 api_key_expired，未生成结论，REVIEW_RESULT_02与BLOCKER保留；不记复核通过，未改凭据或切换被策略禁用的连接。
- 下一轮R2：本地SDK/Qt环境与最小加载→真实3帧/约5万点与精确50万压力分开→exe/无VS/DPI/性能门；写worker与全兼容未解项不阻止只读spike。未修改旧控制台/数据/junction/历史证据/生产默认，无Git写、设备控制/部署/采集、训练或模型下载。

## 2026-10-25 点云标注台 v2（annotator_v2）首版落地

- 按用户规范十～十五节新建 `pc_apps/annotator_v2/`（React+TS strict+Three.js+Vite；vitest 73 项、server.py 单测 7 项、tsc+vite build 全过）：2D 俯瞰双层画布（底图=点云仅帧/视图变化重绘，覆盖层=框/柄/预览 rAF 合并）、Pointer Events+捕获的显式选择/画框/平移工具（松手回选择、最小拖动距离、画布外松手即停）、柄>体>背景命中、拖动=预览+单次撤销提交、编辑即暂停播放、3D 共帧复用缓冲关窗即停、时间轴按 stamp_sec+nanosec 逐源帧播放、LRU24 帧缓存+代次防过期、Worker 解码 28B 结构、gt_annotate/2 存储原子保存/409 冲突/v1(gt_workbench/1)只读迁移、算法适配入口（demo-cluster@0.1.0，建议与人工分开、显式采用保留来源、可整体禁用）。
- 浏览器（IAB+cap_20261023_221125，126帧/每帧约4.91万点）端到端：反例1/2/4/5/7/8/9 全过（含 3 次画框回选择、画布外松手不跟随 19.249,-1.536 稳定、柄缩放 1.062→0.566 无平移、面板拖拽零误建、3D 三开关内存 18→16MB/rAF 残留 0、播放中框上起手即暂停帧冻结、算法关闭下保存 v1/v2+导出 2238B）；反例3 为状态机单测（4 打断路径）+接线；反例6 为 loader/算法 generation 单测。修两个真 bug：stamp_nanosec 亚秒丢失（播放会按秒跳帧，已修+回归）、保存首存 null/0 判冲突（已修）。
- 性能实测（本机）：指针→覆盖层重绘 0.2ms（单帧≤5.6ms，51 次均值 0.43ms）；暂停逐帧切换 0.1–0.7ms；帧切片网络 7–30ms、播放呈现 p50 60.6/p95 92.1ms（6 秒到帧 62 无积压、在途 0、缓存 24/24 封顶）；点云底图重绘均值 21.5ms 仅帧/视图变化触发。降级垫片（rAF→setTimeout16ms，IAB 面板被遮挡冻结 rAF）只用于播放/CE8 两项，证据注明。
- 证据 `docs/evidence/2026-10-25_annotator_v2/`（BROWSER_E2E/PERFORMANCE/CHECKS+49 源文件 SHA256/vitest.log/python_server.log/saved_draft_v1/browser_canvas_frame2.png）；草稿在 `pc_apps/annotator_v2/gt_store_v2/`（gitignore）；说明 `pc_apps/annotator_v2/README.md`+`ARCHITECTURE.md`（模块边界/数据流/四类状态/修改入口）。旧 gt_annotator R1 与其 gt_store 未动。未 commit/部署/采集/训练；标注框的人体语义仍 UNKNOWN（本工具不产出真值判定）。


## 2026-10-25 ConsoleV2 R2 实测、路线B与OpenCode修正

- 新增console_v2/spike（C#三帧stride28只读解码/共享缓冲、Qt6.5.3 C++ QML/Quick3D宿主）及构建/打包/测量/差分脚本，SPIKE/README与ADR-001更新。SDK8.0.426/GCC11.2本地可携；固定Qml.Net0.11.0实际net8编译过但加载失败、Qt5 imports留证，A窗口/FPS NOT_RUN，按约定切B，不用C、不提前做R3业务。
- 最终corrected_gui实际exe三真帧×原始/5万/50万模式全字段/XYZ/构造SHA与Python容差0；4自检/4坏数据/3参数反例及数据目录输出/覆盖拒绝通过。Qt映射前正容量≤18MB/三帧连续范围，活动GUI前缀/后缀固定时钟自检与布局一正五反例均在24轮启动实际执行。C++/C#最终构建零警告错误，单文件96,298,082B、嵌Qt590文件75,373,138B；无数据打入。
- 最终50万动态三轮133.97/132.65/131.75FPS、5万最低168.82；GUI drain活动区间P99最高2.217ms，不等于完整当前回调/outer-notify按帧预算（NOT_RUN）。10新进程首帧P95 730.99ms，首Qt解包1839.95ms；整24轮启动P95 1792.20/max1839.95ms。OS/QML/驱动缓存未清；旧measured_final8.683s异常完整保留，阶段约8.115s在payload复核/解包，三次同输入缓存0.591–0.614s未复现、根因UNKNOWN，不借重跑删异常。
- DPR1/1.5/2原生PNG逐张查看文字/视口/压力标识；当前无交互，非多屏/坐标证明。PATH仅System32的实际包运行及模块路径留证，但独立干净无VS/SDK/Qt系统、真正全冷机NOT_RUN，完整R2未翻绿。旧Python sessions7/board4（-B -W error）、JS46/11/38及panel行为、真实旧HTTP列22→meta→完整points流SHA与三帧E2E通过，板端0；54会话文件、11旧源码、142份R0/R1证据与三junction SHA/目标保持，工作树外部annotator_v2变化不归本轮认领。
- OpenCode按用户要求四次只读附件审核，均实际opencode-go/gpt-6-luna#low、0工具事件。修字段/摘要/参数拒绝、GUI前后缀记账及映射前边界；最后明确采用计时范围收窄、完整帧UI预算NOT_RUN，04确认03唯一意见解决；不冒称审核方独立执行测试。原始编译/网络/部署/汇总脚本失败与最早2.77s QA保留，SDK首用未信任开发证书副作用记录。证据docs/evidence/2026-10-24_console_v2_r2/：RESULTS/FINAL、corrected_*及corrected_gui为当前，旧两版不混算。
- 下一步补独立环境/全冷机、旧启动异常与完整帧UI计量，再进入R3；1GB/seek/1×/API Golden和人体物理效果仍NOT_RUN/UNKNOWN。未修改旧控制台/原始数据/历史evidence、驱动/网络或ML，无Git写、部署/设备/采集/训练/权重下载。

### 2026-10-25 稀疏标注支持（只标几帧）

- 应用户"只标几帧、不全 session 标注"需求：doc 新增可选字段 sampleFrames（兼容 v2 不升版本，旧文档按空表解析）+ setSampleFrames 可撤销操作；左侧新增「标注帧清单」（当前帧入清单/每N帧取样/清空/单帧移除/点击跳帧，已标未标分列，清单外已标帧另计）；时间轴新增帧号直达输入与标记（清单帧空心点、有框帧绿色实心，悬停提示）。测试 78 项（新增 sparse 5 项：取样/覆盖/操作往返/越界校验/存储兼容）+ build + server 7 项全过；浏览器实测：每 25 帧取样生成 0/25/50/75/100/125，时间轴 6 空心+3 实心标记，跳转帧 25，保存 v3 落盘 sampleFrames。校验不要求覆盖全 session 的既有语义不变（不建清单直接标几帧保存即可）。


## 2026-10-25 ConsoleV2 统一开发入口与可迭代边界

- 用户明确控制台应方便迭代。新增console_v2/dev.py的build/check/run，开发目录增量构建/直接运行与单文件发布分开；DEVELOPMENT给出页面/数据/回放/算法/板端/API修改位置，README/ARCHITECTURE接入口，不建通用插件或空工程，QML热重载仍未实现。R2未测项保持，未提前写R3业务。
- 首跑Python AppData输出被C#拒绝，保留失败后统一私有.tools/spike-evidence输出；当前C#不接受历史evidence报告根。共享命令工具默认全新私有目录、拒绝目录链接/历史根，stdout/stderr/command.json均独占创建。每次dev命令不publish、不改payload.zip/已测单文件。最终三真帧×三模式逐字段/SHA差分、4自检/4坏元数据/3坏参数与原生E2E通过（Python-B -W error），其他cwd的5万压力run通过；编译零警告错误、板端0。历史输出拒绝与模拟竞争不覆盖通过。
- OpenCode实际opencode-go/gpt-6-luna#low两次、0工具事件；修历史默认根/记录独占与测试计数表述，修后无具体问题，静态审核不算独立复跑。54会话SHA、三个junction及R0—R2非忽略证据SHA保持，12既有忽略PNG没有本轮前SHA故单列；两次盘点脚本误把PNG当新增/Windows CRLF检查失败已记录并改NUL输入，不改图片。源码/文档/SHA及全部机器输出在docs/evidence/2026-10-25_console_v2_iteration，42889文件区间基线始于初稿/首跑后、非原子。
- 无Git写、原始数据/旧控制台/历史evidence/设备/ML/驱动网络修改，无部署/采集/训练/模型下载；冻结单文件exe SHA仍3029aaea64d78d6197770391977ad83abad8cb062adeba9128e380e725d1708f。下一步仍补R2残余验证，并沿独立模块/离线测试/快速开发反馈推进产品。

## 2026-10-25 Qt / Web / 2D距离图三线集成与OpenCode审查

- 三个子代理只读并行分析，主会话独立写码/集成，外部审核分开。新增Qt开发应用（C#数据与用例、Qt6/QML/Quick3D）、完整会话源时钟回放/seek、同帧RAW目标与状态、只读Foxglove实时入口、USB联合录制客户端和显式空闲服务入口；异步QLocalSocket+共享内存ACK，500次seek不阻塞队列。旧spike/包保持。
- Web接共享analysis结果，修帧/会话异步代次、旧帧、草稿上下文、禁用与区间采用/坐标校验；浏览器真实f105=g0_t0002/0.44m，采用/保存/3D共帧通过，仅写本轮测试store。旧录制后端拒绝已有登记、独占新sid目录且异常不覆盖旧数据，新增三反例。
- 核心772、运行时13、共享4、Web84/server8、联合14、原生3通过（Python-B -W error）；最终原生含模拟实时/联合录制和ACK校验。386/780完整回放均0丢弃、复算差异0；两段全部raw/XYZ/目标SHA对C#/NumPy容差0，386改前/后tracking/rule差异0。核心47文件未改。386=376 unknown+10低姿态，780全unknown，无疑似区间；人体/跌倒GT UNKNOWN、confirmed关闭。
- 串行单次事件链P95 24.189/32.340ms；完整本地循环81.616/89.072ms，原性能门仍FAIL，不冒称板端。Windows PIN锁屏使追加原生手动点击NOT_RUN；原生自动联测和QQuickWindow截图完成。
- OpenCode三轮实际opencode-go/gpt-6-luna#low、0工具事件；区间中段显示问题修正，NaN行错位首轮意见确认误报，最终未发现新具体缺陷；静态附件审核未独立复跑。45份meta/points、junction目标和原R2 exe SHA保持；全树区间基线+定向改前源码清单，camera未入本轮前SHA范围。
- 证据docs/evidence/2026-10-25_fall_integration/（FINAL/CHECKS/CONTINUITY、final386/final780、native_final、audit_01..03）；启动见console_v2/app/README.md。仍需真实设备/USB录制/物理同步与GT、性能、R2/发行/兼容收口，不宣称完整项目完成。未Git写、部署/真实采集/训练/下权重/HR-09或驱动网络修改。

## 2026-10-25 删除旧网页版总控制台（Qt console_v2 已替代）

- 用户确认桌面 总控制台.lnk（指向 pc_apps/console/dist/Console.exe）已被 Qt 版 console_v2 替代并要求删除。已删：桌面快捷方式、console 网页壳全部源码（console.html/console_gui.py/两份 console 测试/Console.spec/make_*.py/console_icon/passthrough 示例/README*）、plane01_pages 全部 20 个文件与 sync_plane01_pages.py、build/dist/__pycache__ 派生物；目录 202MB→60K，git 跟踪删除 32 文件。
- 保留且未改：joint_capture.py/.html/joint_capture_test.py——console_v2/joint_server.py 运行时 import 的联合录制后端（删除前已核实全仓无其它引用；源 evidence 页面仍在 docs/sidequests/evidence 只读区）。新增 pc_apps/console/README.md 说明现状。
- 验证：python -B -W error joint_capture_test.py 14 项全过；joint_server.py 引用路径不变。.gitignore 清理 6 条失效 console 条目；AGENTS.md/CLAUDE.md 的 pc_apps 描述与测试清单同步更新。无 Git 写、未动 data/、captures junction、板端 webui、历史 evidence。
- 证据 docs/evidence/2026-10-25_remove_web_console/DELETION.md。

## 2026-10-25 板端离线预检 + console_v2 QML 热重载落地

- 用户"你看着办"承接上轮建议先做联合录制真机实测：预检发现板端离线（本机 192.168.31.111 同网段；.58 ping 全丢、:8766/:8081/:8090 超时、候选地址与 /24 全扫三端口零命中），实测无法进行；未部署、未采集，录制引擎是否移植 C# 继续挂起待板端上线。
- 转做离线可验证项：把 R5 界面开发模式的 QML 热重载提前落地。`app_dev.py run --qml-file <Main.qml>` 从磁盘加载，QFileSystemWatcher+300ms 防抖仅重建 QQmlApplicationEngine（Viewer/几何/命名管道/回放代次不动）；坏 QML 窗口消失、进程存活、保存即恢复；不带参数仍走 qrc，发布路径不变。C# Program.cs 转发新参数，app_dev.py 透传。
- 验证（-B -W error，证据 docs/evidence/2026-10-25_console_v2_hot_reload/）：build 通过；check qrc 回归 PASS（nativeExit 0、截图 145,740B）；--smoke-reload 正例 PASS 退出 0（副本追加注释→watcher 重载，计数≥2 才发 quit）；broken.qml 反例 FAIL 退出 2、进程存活无崩溃。改动仅 main.cpp/Program.cs/app_dev.py 与文档；无 Git 写、无 publish、板端 0 调用、R2 单文件包未动。

## 2026-10-25 联合录制真机实测：PC 链路全通，板端雷达零数据阻塞

- 板端恢复在线后按用户指示继续实测。joint_server 空闲启动后经真实 API 驱动 10s 联合录制（与 Qt 面板同协议）：starting→recording→stopping→failed，sid=cap_20261025_202824。PC 侧全部环节真实工作：板端 HC 调度/幂等/登记、相机 MJPEG 91 帧@≈8.3fps 落盘 camera.mjpeg+逐帧索引、失败会话目录保留 joint.json 失败原因，无覆盖旧数据。
- 失败点唯一：板端 bag 4117B 无 PointCloud2。Foxglove 桥（ws://192.168.31.58:8765，子协议 foxglove.websocket.v1）证实 /innolidar_points、/inno_imu、/device_status 已广播但 6.5s 零消息，仅 rosout 1.7Hz 与 single_target_live/state 1.5Hz——驱动在跑、雷达无输出（未上电/网线/驱动 msg_source 配置），设备侧问题。按红线未改板端驱动/网络/配置，未部署。
- 本地 joint_server 保持运行于 127.0.0.1:60301；雷达出数据后同一入口重跑。失败会话与板端登记保留为证据，数据目录未删。证据 docs/evidence/2026-10-25_joint_recording_realtest/。无 Git 写。

## 2026-10-25 联合录制重跑成功 + 错误归因收口

- 用户恢复雷达后同一入口重跑：completed，sid=cap_20261025_203653，雷达 85 帧＋相机 91 帧、回拉 117.9MB；meta/points SHA 与 joint.json 落盘。`app_dev.py check --session`：85/85 帧全解码（每帧 49,105 点、逐帧 SHA）+ 原生冒烟 PASS。Qt 面板已接 --joint-url 真实服务拉起。
- 归因收口：雷达零数据为设备侧偶发故障（当天 18:27 前三段成功、20:28 失败、恢复后一次成功；10-15 有同型史），软件两侧（失败如实/成功零容差）均验证；设备侧根因（供电/链路）未定位，留 fgprobe 只读检测。详见 evidence/2026-10-25_joint_recording_realtest/SUMMARY.md。无 Git 写、板端零修改。

## 2026-10-25 LiDAR距离图转正与已躺倒几何候选

- 新增同源ScanGrid径向PNG16/preview/mask/元数据，Qt/Web同帧显示导出；按用户图片反馈统一上下、左右转正（v2原生栅格旋转180°，v1显示兼容），保留RAW算法坐标。新增独立持续低位水平形状旁路，动态门限/状态不变，只修f371诊断理由；结构见DEPTH_FALL_ARCHITECTURE.md。三子代理只读、主会话写码，开发/审查分开。
- 核心778、运行时/共享/距图19、另1合成原始射线E2E、Web84/server9、原生5+780全帧1通过，Python-B -W error。386/780完整回放0丢弃/复跑0差异，跟踪/规则特征/动态状态差异0；3498PNG/1166侧车SHA/CRC/像素对应、毫米量化≤0.5mm与目标来源行通过。386新分支269竖直+117unknown、780全unknown；合成非人体长方体可候选，不冒充人体GT。
- 修正0.3s浮点边界、Web标定绑定、Qt元数据生命周期与重连残图；OpenCode首轮提出ACK无限等待，补10s超时/错误ACK退出及故障注入。实际opencode-go/gpt-6-luna#low/工具deny；修后复审401密钥过期、无结论，未切凭据，不记复审完成。
- 浏览器8943已更新转正v2，f105真实37219/611、0.44m；PNG16实际下载SHA通过，未写GT。Qt标准DLL被另一个在运行进程锁住，未终止它，独立目录完整构建与原生截图/E2E通过。核心性能/真实人体效果/板端/物理同步/实时距图及R2发行缺口保持。
- 证据docs/evidence/2026-10-25_depth_fallen/（CHECKS、oriented386/oriented780、FULL_DEPTH_E2E_ORIENTED、BROWSER_ORIENTED、native_oriented、CONTINUITY）。55既有会话文件及40846历史证据SHA保持；并发另有8个新会话文件与Qt热重载变更，不归本轮。本会话无Git写、部署/真实采集/训练/下模型/HR-09或驱动网络操作。

## 2026-10-25 console_v2：实时页无进度条 + 本地人体框选 + 右键平移 + 相机空闲预览

- 用户反馈三项：实时锁定不需要进度条、做不了人体实时框选、USB 页相机看不到（第三条补充：右键拖动平移）。修复全部落地：live 模式隐藏回放进度条/播放控件（提示「画面跟随实时流」）；「框选目标」模式左键拖矩形即本地视锥框选——QML 用相机 mapToViewport 探针经验标定投影模型（不依赖 Quick3D 欧拉角/深度约定，item↔视口方向也由探针实测），C++ RectSelection 对每帧点云按同一视锥重投影收集框内点（橙色点集+传感器系 AABB+高度中位数），旋转缩放后仍逐帧跟踪框内目标，纯查看端测量、零板端命令；右键拖动按抓取语义平移；USB 页打开期间每秒轮询录制状态。
- 相机预览根因：/api/preview 只有录制中才有帧（recorder.latest 仅由录制相机线程填充），Qt Image 又不能直连板端 MJPEG。joint_capture.py 新增空闲预览泵：/api/preview 被持续请求（每次续约 5 秒）才连板端相机流，窗口外零设备访问；camera_stream_lock 与录制相机线程互斥且锁覆盖连接整个生命周期（并发回归测试抓出「先放锁后关流」的双流缺陷并修复），录制中泵让路；状态新增 preview_state/preview_error，UI 不再只有「等待预览帧」。预览 1 fps 定位取景确认。
- 验证（离线/回环，真实设备未实测）：app_dev check PASS（构建零警告错误+386 帧解码+原生冒烟）；集成 6 项 OK（新增 --smoke-pick：框住窗格中央必须选中点，否则退出码 2）；joint_capture_test 17 项 OK（新增 3 项预览泵合同）。截图见 docs/evidence/2026-10-25_console_live_pick_preview/（框选 48768 点视觉验收、live 页无进度条、回放回归）。文档同步 console_v2/app/README.md 与 pc_apps/console/README.md。无 Git 写、未动 data//板端/驱动/ML；用户旧控制台与 joint_server 实例为加载新代码而重启（60301→随机新端口），现按 cap_20261025_203653 + joint-url 57011 运行；预览泵真机实测：/api/preview 首次 404→3 秒后 200（74KB JPEG），持续请求 preview_state=live、停 8 秒回 off。

## 2026-10-25 console_v2：删除会话（本地+板端）+ 保存路径选择 + 点云三模式着色

- 用户四项反馈落地（第 4 条「2D 距离图可否实时渲染」按要求只答复不实施）。删除会话：C# deleteProbe/deleteConfirm 两段式——先出 sid/bytes/sha256 清单对话框显式确认（符合数据红线），confirm 重算清单比对摘要（防确认期间漂移）；先板端 DELETE /api/v1/sessions/<sid>（HC 状态机 ready/failed/transferred 可删、录制中 409 拒绝、404 注明后照常删本地），本地删除校验路径无目录链接；删当前打开会话自动切换剩余会话，最后一个本地会话拒绝。原生 --smoke-delete 自检脚本 + 集成 3 项新测试。
- 保存路径：USB 页「浏览…」FolderDialog 目录选择 + 空值预填录制服务 output_root。
- 点云着色：协议随帧携带逐点反射强度（回放 offset12 float32 同过滤序、live ROS intensity 字段、缺失自动回退单色），target 后追加强度段 + SHA 进 ACK 零容差合同；着色模式 单色/深度(0.1–8m 红近蓝远,与 2D 距离图同标尺)/高度(逐帧 z 范围 viridis)/反射(逐帧强度范围 inferno)，UV 采样 qrc 内嵌 256×1 渐变 PNG，DefaultMaterial diffuseMap 双 Model visible 切换。三点教训记录在案：块作用域局部量被 [&] 定时器捕获即悬空（0xC0000005 根因，改按值捕获）；Quick3D DefaultMaterial 对 Points 确实采样 diffuseMap（品红底×渐变实验证实），CustomMaterial 运行时编译管线脆弱已回退；多次「失效」实为陈旧 exe/QML 变体文件，最终以三模式像素互异 10349px 定量收口。顺带修复 BoxGeometry/空几何 stride=0 每帧告警（既有问题）。
- 可诊断性：服务端现在捕获 Qt 子进程 stderr/stdout 进报告（nativeStdout/nativeStderr 事件）并设 QT_ASSUME_STDERR_HAS_CONSOLE=1。
- 验证：app_dev check PASS；集成 9 项 OK（删 3 项、live 强度 SHA Python 独立复算）；joint 17 项 OK。截图 docs/evidence/2026-10-25_console_session_delete_color/（replay_mono_ui + color_depth/height/intensity）。真机板端删除未实测（回环假板端）；未部署任何板端改动（DELETE 为 HC 既有路由）。无 Git 写、未动 data//驱动/ML；用户控制台已停用旧实例并以新构建重启（cap_20261025_203653 + joint-url 57011）。

## 2026-10-26 Qt旋转与右键平移突跳

- 修Main.qml按下未初始化旧坐标：真实Qt1px旧转256.865°，新为0.35°；锁定主按键并清理取消/失焦/隐藏/工具变化，避免多键串动作；框选滚轮先取消。热重载保存4项相机状态并忽略QML内容未变的目录事件。
- 标准构建（C++ -Wall -Wextra -Werror）通过；Python-B -W error相机2用例（13手势+4重载断言，含120次连续小拖、右键、混键、取消和坏QML恢复）与原回放/框选2用例通过。早期重载检查失败留存，诊断/输入隔离后复测通过，未臆断原瞬时原因。
- 已重新打开标准Qt同85帧会话，computer-use两次不同起点短拖实操通过；录制服务idle，仅只读查询，未采集。63会话/48core/44593历史证据SHA保持；证据docs/evidence/2026-10-26_mouse_camera/。无Git写、原数据/算法/板端/网络驱动改动或训练下载。
## 2026-10-26 板端 eth1 二层中转接入 192.168.31.0/24
- 用户要求把 3588 的 eth1 做成网口中转，让别的设备接入 31.1 网段。将 eth3（上行千兆）+ eth1（下行百兆）做进 Linux 网桥 br0，192.168.31.58/24、默认路由 192.168.31.1 和 DNS 从 eth3 平移到 br0；br0 沿用 eth3 MAC 60:80:47:83:b5:7b，板端地址/ARP 不变。STP 开、forward-delay 4 s，插线约 8–10 s 转发，防环路。
- 未动 eth2 雷达 192.168.1.35、eth0、eth4（192.168.127.1 旧 NAT 原样）、驱动、容器/服务；netplan 已持久化，改动前备份 /root/netbridge-backup-20261026T132852。
- 验证：换桥后 SSH/ping .58 正常；板端上网/DNS 正常；8766/8936/8090/8765/8081/11311 全部在听，Windows 侧 8936=200、8766=204；临时 netns+veth 挂 br0 实测二层通板端/网关/PC/公网，并经网桥从 192.168.31.1 拿到 DHCP 192.168.31.69/24；真实设备插 eth1 的物理链路与吞吐 UNKNOWN（测试时该口无载波）。
- 证据 docs/evidence/2026-10-26_eth1_bridge/（BEFORE/AFTER、L2_TEST、L2_TEST_DHCP_DNS、apply_bridge.sh、l2_test*.sh、SUMMARY）。首次 netplan 因桥端口未在 ethernets 声明被 generate 拒绝，自动回滚生效、连接无损；补 eth1/eth3 dhcp4:no+optional 后二次应用成功。既有 systemd-networkd-wait-online 失败（2026-10-05 起因 eth1 无载波）非本次引入；未 Git 写，未重启板端、未改驱动/其它网络配置。


## 2026-10-26 RK3588实时距离图旁路：本地实现与回放验证

- 新增ROS-free PointCloud2适配/最新帧转换core、独立ROS1 range_image_node、可复现live_replay_check；复用ScanGrid，按真实26字节float64点时间布局读取，支持行填充/大小端/长点。输出同header的径向距离/原始点索引/有效图/可选RGB及诊断，不碰现有识别节点；无NPU或新依赖，实时不压PNG/写盘。CMake登记入口，说明见RANGE_LIVE.md。
- 最新帧队列容量1，过期帧前后双检、坏帧拒绝、断流心跳；明确ROS上游丢帧不在内部计数内，各图须按源header关联。逐点时间降float32是现有输入契约限制，未当成物理同步；语义及跌倒UNKNOWN。
- 核心791项（新增13，含ROS消息/发布替身）、距离图导出2项通过（-B -W error）；新增板端文件Python3.8语法通过，真实3.8/NumPy1.17及ROS运行未测。386/780各3轮3498帧，距离/源行/valid和历史PNG预览零差异；源节奏386/386，内部覆盖/失效/过期0。PC源节奏转换含四图打包P50=9.519/P95=11.684ms，非板端、非ROS网络/绘制端到端；早期串行测试存在并发负载，逐轮原值保留。
- 证据docs/evidence/2026-10-26_range_live/：BASELINE、core_tests/depth_tests、serial/paced逐帧账本、CHECKS。47047份非原子全树非忽略文件基线；定向153份已有文件仅CMake改变，旧算法核心未改。两段源文件SHA与既有绑定保持。无Git写、板端访问/部署/服务操作/采集/训练/模型下载/HR-09、数据删除或移动。下一步是显式授权后的板端启动及计时，板端性能/ROS真机收发/Qt与Web实时接图尚未完成。

## 2026-10-26 实时点云低帧率只读诊断
- 未改生产代码；两次18秒Foxglove原始点云订阅实测到达4.526/3.036Hz；第二轮53帧首尾seq跨度154、缺101，源stamp/seq推算9.647Hz（103.664ms），单流完整原始消息约需98.57Mbps。PC有线断开、WLAN协商144.4Mbps；带宽/桥接传输为嫌疑，未证明硬件丢帧或具体丢失位置。额外探针订阅增加带宽，不能当原UI帧率。
- 实际前缀/single_target_live/状态16条约1.984Hz，source=null、required_cloud_stale，cloud age约62641秒；是存活心跳而非有效识别帧。初探错误订阅/human_fall/state无消息已更正，不据此断言节点缺失。LiveSource同帧匹配8帧/2秒缓存及0.8秒等状态显示门、USB页每秒状态请求串行阻塞均是软件风险；当前状态失效，不能把等待门当本次已证实主因。
- 端到端只读探针Python -B -W error运行，保存原始header/状态及源码SHA至docs/evidence/2026-10-26_live_fps_diagnosis/。未改生产源故未跑源码回归；未启停/部署/采集/网络驱动/Git写/训练。下一步分别核对板端发布与算法订阅连接及单订阅传输，网络吞吐及Qt实际显示fps仍UNKNOWN。


## 2026-10-26 RK3588实时距离图：真实ROS验证与源seq修复

- 用户明确授权板端验证，使用wel SSH/docker在独立/tmp目录放44份源码/方向表（压缩约248KB），独立ROS节点/前缀限时运行，不覆盖release、不启停现有服务。板端Python3.8.10/NumPy1.17.4，表SHA一致；板端15项-B -W error通过（含真实ROS序列化），PC核心793项完成、1项ROS专用测试本地跳过且板端已通过。
- 首轮四图与状态各282条但完整源header关联0：根因是rospy.msg.serialize_message改写header.seq。修正为继承Image线格式/md5/type、仅关闭本地_has_header改写的SourceImage；补2项回归，失败run01保留。修后真实约30秒282/282处理，四图/状态同帧关联282，抽14帧距离/源索引/valid/RGB逐像素一致，内部覆盖/失效/过期0。
- 预热后272帧：消息适配/ScanGrid/四图含RGB打包合计P50=23.788/P95=32.770/max69.995ms；本地接收到转换完成P95=32.976ms、Image发布调用P95=0.836ms。原始点云前/中/后9.662/9.651/9.664Hz且seq缺口0，短窗能跟随约103.664ms源间隔，但P95≤20ms优化目标FAIL；不含设备采集/跨网/PC绘制，非长期稳定性或人体效果证明。
- 验证后自己的子进程与observer均退出；驱动/桥/识别PID及driver config/effective_node配置SHA保持。既有识别input_valid=true、unselected/unknown，处理慢/丢帧计数仍增长，前中后观察保留，不宣称新链替代或改善它。ROS1订阅/退出产生socket ResourceWarning，预检也复现；-W error析构路径被Python忽略，实际收发像素契约过但不能称无告警。初预检set -u与ROS setup不兼容的失败亦保留。
- 证据docs/evidence/2026-10-26_range_live_board/（run01/run02、BOARD_UNIT_TESTS_FIX、CORE_TESTS_FIX、PRODUCTION_COMPARISON、POSTFLIGHT、live_preview.png、SHA）。更新RANGE_LIVE/STATE；新增board_probe复现实验工具。无Git写、真实bag/会话采集、数据删移、训练/模型/HR-09、驱动/网络配置改动或既有服务重启。当前临时旁路已停，Qt/Web实时显示接线及常驻运行未实施；后续性能热点为ScanGrid，人体/跌倒UNKNOWN。


## 2026-10-26 Qt固定最新版桌面快捷方式

- 创建桌面“雷达控制台（最新版）”快捷方式，固定指向console_v2/start_latest.cmd；每次调用当前app_dev.py增量构建，成功才启动，失败不回退旧exe；QML使用当前源码热重载。构建控制台最小化，日志按运行独立保留。
- app_dev新增--isolated-run：构建缓存不执行，C#/Qt各复制到本轮私有service/runtime，避免旧窗口/DLL占用锁构建；不改变原固定目录开发入口。默认离线启动，不猜测录制服务端口，不自动连接设备/采集。运行参数可从固定cmd传入，README更新。
- 3项回归-B -W error通过：旧运行文件仍打开时源更新→新运行副本、失败不启动旧exe、真实cmd的任意cwd及空格路径转义。初次测试调用cmd自身的引号错误已修，失败日志保留。isolated check两次（含窗口保持打开再构建）均构建/386帧/原生播放seek截图通过，board/joint/delete计数0；快捷方式实际启动PID27640，exe SHA与当前native构建一致。
- 证据docs/evidence/2026-10-26_qt_latest_launcher/：SOURCE_BEFORE、SHORTCUT、LAUNCHER_TESTS_02、ISOLATED_CHECK、CHECK_WHILE_OPEN、CHECKS、截图；直接改前SHA与收尾全树非原子快照分开。另一会话同期启动标准路径实时Qt PID43884，保留它与原joint_server，不归本轮创建。无Git写、算法/原始数据更改、板端访问/部署/采集/训练/模型下载/HR-09或驱动网络操作。

## 2026-10-26 Qt实时锁定未生效：根因排查（只读，未改码）

- 用户报告Qt「实时锁定」仍看不到目标。板端只读探针10s：/innolidar_points 9.646Hz/94帧、seq连续；/single_target_live/state 4.9Hz/50条，source全非空、49/50能在本次点云中找到、cloud age 7–117ms、observability=valid；但track_status 50/50 unselected、target_source_rows全0、acquisition全searching/no_qualified_candidate。入口门拒绝累计：entry_motion_window 318、entry_height_out_of_range 289、insufficient_height_span 212、entry_motion_not_observed 102、extent_out_of_range 4；最像人的簇p90 1.89m/0.99m但位移≈0。静止场景本来不会自动锁定。
- 真实Qt实时入口跑279s（app_dev run --live-url，14:01旧构建，LiveSource.cs SHA a5d1f656…）：点云2680帧、9.64Hz、seq缺口0，仅1帧匹配到state（frame17243526/t0035/locked/3591点/bbox1.19×0.76m），其余2679帧无目标。根因是旧LiveSource每来一帧点云就立即发布并推进lastPresentedOrder，而state总在100–300ms后才到，TryMatch的cloud.Order<lastPresentedOrder几乎必然命中并丢弃；假桥测试点云与state背靠背发送，未覆盖该时序。
- 运行期间工作区外进程14:02改了LiveSource.cs（当前SHA 4602dfb9…，新增PreviewDelayS=.35与matches缓存，按延迟帧取匹配结果），方向正确但未包含在本轮运行构建中；未终止另一个app_dev隔离实例，未改该文件。下一步：用包含该改动的构建重跑，并让人走进/走过视场满足≥0.3m/1.2s入口门；可选把acquisition.reason/拒绝计数透传到Qt状态栏。
- 证据docs/evidence/2026-10-26_qt_live_lock_diagnosis/（SUMMARY、CHECKS、PROBE_SUMMARY、QT_RUN_SUMMARY、probe_live.py）；完整运行报告在console_v2/.tools/app-evidence/49532d8b…/run.json。无Git写、未部署/重启板端/采集/改算法阈值/原始数据；单场景单次锁定样本，人体/跌倒真值UNKNOWN。

## 2026-10-26 实时点云掉帧修复与控制台抽屉/会话名称/标注入口

- 板端只读定位原始点云约9.65Hz；识别节点存活但三个传感器TCPROS入站连接全失、state仅心跳且source=null/age约17.4小时。向既有节点重发Master已登记的publisher列表恢复cloud/imu/device订阅，随后fresh及当前源帧恢复；无重启服务/部署/采集/驱动网络修改。断连原始触发原因未证实，本地新增10秒无连接重建的SubscriptionGuard和诊断，尚未部署防复发补丁。
- Qt/C#启用桥已有permessage-deflate全量点云传输；移除按识别结果节流的0.8秒门，增加固定350ms本地同帧缓冲，8帧/2秒有界缓存、完整header与目标来源行约束保留，迟到结果不贴新帧。录制HTTP请求后台串行排队，状态慢请求不再挡点云/ACK；强度大端解码回归补齐。HUD显示接收fps、源频率估计和接收跳号。
- 新增功能抽屉统一会话回放/实时锁定/USB联合录制/标注台，点击选项自动收起；设置侧栏可单独收起，放大点云同时收起侧栏/结果卡，恢复面板还原。中文会话显示名称原子存console_v2/user_data/session_names.json，sid/目录/meta/points/分析GT绑定不改。标注台入口按当前会话/回放帧打开浏览器；按需本机端口启动现有服务或复用显式URL，继承data root/analysis，不自动写标注；按需服务跟随控制台生命周期。
- 串行14秒真实流：源估计9.6466Hz，接收9.6631fps、送到Qt9.6656fps，接收跳号0/预览队列跳过0；130收到、127送达（末尾350ms缓冲尚有在途帧），67帧带同源识别结果，Qt副本ACK中位4.5519ms；非GPU物理呈现fps。识别仍约5fps，人体/跌倒GT UNKNOWN；未改识别阈值。桌面computer-use实点抽屉→实时锁定自动收起→放大点云，确认侧栏/结果卡隐藏、接收9.6fps/跳号0；标注浏览器真实cap_20261018_110029第105帧深链接通过，未写GT。
- 回归：核心795项完成（1项需实际ROS本地跳过），原生9项含386全帧XYZ/目标/强度SHA零容差、同帧ACK/seek/距图/坏输入/删除保护；相机2、工作空间1、延迟识别+2秒慢录制状态1、Web86/server9、联合录制17均通过，Python-B -W error，C#/C++构建零警告错误。失败尝试保留：最初绝对启动时刻断言错误改为首帧锚定；标准DLL被同期新窗口占用后误跑旧DLL，改私有构建复测；无缓冲版虽满速但迟到结果全错过，已用350ms同帧缓存修复。后台启动脚本退出时Popen ResourceWarning单列，最终应用本身无stderr、单元测试未抑制警告。
- 新版Qt PID28308/服务29992已打开实时流并实点收起面板；原joint_server57011保持idle、preview off，未发真实开始/停止命令。为替换实时连接关闭旧标准Qt PID43884；另一个快捷入口开发窗未由本轮终止。当前私有runtime/service已测；固定“最新版”入口下一次启动会构建当前源，保留同期新增--isolated-run/桌面入口及range旁路改动。
- 证据docs/evidence/2026-10-26_console_live_workspace/（CHECKS、serial summary、desktop_expanded、各测试/失败日志、baseline/continuity/SHA）。47150文件区间基线、既有49个core文件SHA保持；源会话只读、386全帧对既有分析源SHA保持。同期range_image_node/test、RANGE_LIVE/STATE/PROGRESS和launcher变更未归本轮；既有8943服务按GET自动追加其历史browser_server_oriented.log，故不声明历史evidence全量SHA不变，未手工改写/回填。无Git写、部署/采集/训练/模型下载/HR-09或设备网络驱动改动。

## 2026-10-26 标注台 v2：卡顿 / 无法标注人 / 无法放大

- 用户反馈真实 780 帧会话 `cap_20261017_113516`（每帧约 49.1k 点 / 1.37 MB）标注台太卡、无法标人、无法放大。定位并修复三处根因：①2D 底图逐点 `fillStyle+fillRect`（真实帧 498×543，P50 49.8 ms、max 303.7 ms）改为 24 级 z 色板离屏 `ImageData`（P50 2.7 ms、max 18.7 ms）；②滚轮监听原在底层 base canvas 且 React `onWheel` 为 passive，改为 wrapper 原生 `{passive:false}` 监听，滚轮缩放生效；③画框要求先手动加人物并选中，否则静默无效；现在点「画框」自动建 `P1`/默认选第一个，打开草稿自动选首个目标。
- 暂停时切帧/拖时间轴增加 80 ms 去抖，预取改为停手 150 ms 后；分析结果请求暂停时 120 ms 去抖并 AbortController；播放时仍即时取帧。Worker 不再解码未使用的 intensity。20 次快速 ArrowRight 实测只请求 6 帧（最终 88 + 邻域 87/89/90/91/92），不再每步 6 个。
- 自动取景由全量 min/max 改 1%–99% 分位，该会话 scale≈50.5 px/m（旧约 25），人和局部细节不再被少量远点压小。
- 验证：`npm test` 13 文件 / 90 项通过（新增 renderer 3、clock 1）；`python -B -W error -m unittest test_server` 9 项通过；`npm run build` 通过。真实浏览器：滚轮 `defaultPrevented=true`、无人物点「画框」自动 P1、合成拖动落框 666 点。桌面截图因当前桌面不可见未采集，绘制路径以纯函数/假 canvas 单测 + 同页 Canvas2D 真实帧计时为准。
- 证据 `docs/evidence/2026-10-26_annotator_v2_zoom_perf/`（CHECKS、bench_real_frame.json、live_e2e.json、vitest.log、test_server.log）；入口说明同步到 `pc_apps/annotator_v2/README.md` 与 `ARCHITECTURE.md` 的已知边界。未改数据/服务端帧格式/算法语义，未 Git 写、未部署/采集/训练/下模型/HR-09；人体/跌倒真值与桌面肉眼效果仍 UNKNOWN。

## 2026-10-26 两会话区域骨架：同目标2D/3D显示与规则对照

- 新增range_skeleton（纯NumPy实测区域骨架、解剖关节UNKNOWN）、skeleton_replay（独立目录只读重放/封存/复制验证深度资产）；analysis未来导出同字段。Qt显示金色连线/浅色节点，2D按同源ScanGrid像素逆映射；C#核对节点支撑属于当前目标且XYZ为实测支撑中位数，缺测/切帧清空。
- 最终386/780全帧分别269/354帧有边（780另1帧主轴歧义），复算确定，原目标/框/姿态/动态状态/距离图全部逐值或逐字节保持。现有动态规则386=376unknown+10low_posture_unclassified、780全unknown；未验证人体关节/跌倒准确性，UNKNOWN，未将骨架区域中心接成跌倒证据。
- 核心796（1ROS跳过）+最终定向2、analysis4、原生10（含当前目标支撑/位置篡改拒绝）通过；最终780全帧C#检查、386 f160原生2D/3D截图布局复核通过。所有Python测试-B -W error，构建零警告错误。首轮结果卡溢出修复后重新构建截图；初次单测导入路径失败已修。最终结果及机器日志在docs/evidence/2026-10-26_target_skeleton/，新增start_skeleton_preview.cmd，独立预览service36400已打开且stderr空。
- 同期其它会话视频接线保留，仅修SessionVideo的C#1./30语法。初始全量SHA长IO中断，记录完整路径/大小+定向91文件SHA，未宣称全树SHA保持。预览后台启动助手出现TypeError及Popen析构ResourceWarning但应用成功启动，失败如实记录于PREVIEW.json。中间replay/v2不作为最终源码证据，final绑定已封存。无Git写、数据改写/删除、板端访问/部署/采集、网络驱动/模型训练下载/HR-09。下一步先提升骨架语义与时序可检查性，再尝试可靠姿态跌倒判定。


## 2026-10-26 身体部位2D距离图 → 同源3D → 相对几何旁路

- annotator_v2默认主区改为用户截图的LiDAR径向距离图（不是XY俯瞰图），复用DepthView/ScanGrid/ThreeView；原XY整人框/人物/时间轴保留。新增头、躯干、上臂/前臂/大腿/小腿1/2区域编辑、遮挡/不可见/无法判断、重画/删除、独立撤销重做、版本锁原子保存/重载/导出，2D/3D按同源行着色与反向点选。入口start_body_parts.cmd，本机8946，默认cap_20261017_113516源453帧。
- body_parts.py仅映射同帧唯一最近代表回波，180°逆变换、无效像素/范围外背景排除计数；索引冲突/跨部位争点拒绝，不补背面点。保存绑定会话/帧/人物/源帧及整会话SHA/方向/标定/坐标单位，错帧错源错人错标定拒绝。独立body_store_dev，原会话/GT/analysis不写；切帧前须本区保存，缺测/切换清旧叠加。
- 自动image_extent_bands_v1可无需人工跑链路，但头/躯干仅图像条带假设（举臂可把手臂纳入头候选），四肢不补齐；human/automatic/propagated保留方法与不确定原因，人工赋标签不计自动识别成功。旁路输出部位表面代表点、头躯干差向量/距离、主轴及段无向轴角；不把区域中心叫关节、不默认传感器Z为重力，站立/躺倒/离地高度/跌倒事件UNKNOWN，不改告警。人体部位和姿态准确性UNKNOWN。
- Web94、body+server17、核心797（1实际ROS跳过）通过，Python均-B -W error；最终TS/Vite构建成功但>500kB bundle提示保留。1166真实帧(780/386)、43,410,912有效像素、1,530,598原目标像素的源行/XYZ/回显及背景过滤一致，原目标跟踪/规则/距离图输入保持；16抽帧保存重载与错绑拒绝通过。HTTP真服务save/load/版本冲突/错帧错SHA错方向错人错标定通过；浏览器f453重画165点→撤销238→重做保存重载165、3D躯干点反选2D、切454清空、f0无建议通过。human editor记录为agent软件探针，不是独立人体GT。
- 对照780 f400侧/斜走、f453焦点、f550正或背面外观、f600举臂、f650斜姿、f700弯腰低姿/部分遮挡外观、f750边缘；386 f105/120/160侧斜、f200/240举臂、f350正或背面外观、f380有外观但跟踪缺目标，以及两段f0。仅距离图无法确认正背面/解剖遮挡，场景标签不是GT。举臂头候选误指手臂的失败边界有原图与实际2D/3D截图，未藏成算法成功。
- 证据docs/evidence/2026-10-26_body_mapping/：replay逐帧JSONL/16份完整映射JSON及独立保存、HTTP_E2E、UI状态、距离图/3D截图、测试日志、SHA基线。完整基线为非原子区间扫描（HEAD/master/c9c4ee4…），不能等同某一瞬间全树快照；延迟/整链物理实时帧率未验证。本轮无Git写、源数据删移改名、板端/驱动/网络操作、训练/模型下载/HR-09/部署或采集。

- 收尾：Web最终94项（含刷新建议保留手工/传播部位），新增derivedFrom编辑来源链与当前整人框重新过滤；真实UI刷新后仍保留165点手工区域。完整区间基线/对照共50,829已有文件，缺失0；区间差异14项，其中8项为同期外部video/Qt/joint源码及其持续写入日志，本会话未改。3,610份目标骨架历史证据/共享range算法/原fall core定向SHA保持，两会话meta/points完整SHA再次保持。基线是226秒非原子扫描，server.py和DepthView.tsx在扫描到它们前已被修改，因此不是严格全树修改前快照；最终源码SHA与完整区间差异分开记录，不声称所有历史证据全量不变。最终截图frame453_sealed_pair.png；最终源码SOURCE_SHA256_FINAL.json，CHECKS_FINAL.json、CONTINUITY_FINAL_SUMMARY.json、SESSION_SOURCE_POSTFLIGHT.json。

## 2026-10-26 会话视频同步窗口与联合录制连续预览

- 新增SessionVideo/video_worker：会话目录自动发现非空本地视频，优先camera.mjpeg，支持常见MP4/MOV/AVI/MKV/WebM；独立Qt窗口自动打开，随点云播放/暂停/逐帧/seek/倍速，支持多视频切换和±60秒偏移。索引MJPEG按recv_unix_ns与bag_time_sec最近帧匹配（>250ms缺口不补旧画面），普通视频按PTS相对起点对齐；跨设备时钟/物理同步UNKNOWN。切会话/seek/实时/隐藏窗口用session+generation+mediaVersion清旧图；读文件进程释放后才允许删除私有测试会话，删除清单SHA改流式避免视频大文件整块分配。
- 复用本机已安装PyAV17.1/Pillow12.2，仅PC侧只读解码，最新请求/结果单槽、最多30次/秒、预览1280×720；不阻塞点云，不在源目录转码/写索引。Qt无需新增Multimedia运行库；附带视频损坏只报告视频错误，点云保留。原始data会话四文件meta/points/camera/index前后SHA保持。
- USB预览从随1秒状态轮询更换JPEG改为独立50ms异步最新帧读取，最多一个在途；PC代理给帧号/年龄、未更新204，重复内容的新源帧仍算新帧，超过1.5秒遮蔽旧图。收起面板停止请求，保留原唯一上游相机连接、5秒租约及录制互斥，不自动录制。
- 最终整套原生23项通过（含旧386全帧/骨架/ACK/鼠标/改名/标注入口，新增视频6、预览3）；文件扫描/本地解码协议限制收尾后视频6项再通过；joint17通过，Python均-B -W error，C#/C++零警告错误。合成MJPEG/MP4用确定色帧验证实际解码像素及源帧，覆盖500请求合并、坏索引/反向seek/偏移/2×/无视频会话/关闭重开/持有视频时私有删除；静态同内容相机10Hz和断流遮蔽均过。
- 真实85帧全部找到视频帧，软件记录时间最大取帧差70.973ms、单帧解码中位5.849ms，非硬件同步误差。真实原生8流程检查通过。真机相机预览10.017fps，同时原始点云接收9.681Hz/Qt送达9.711Hz，短窗接收跳号/预览跳过0、未发真实录制开始/停止；非GPU物理呈现/长时稳定性或人体效果证据。已看真实视频窗/连续预览截图，未动GT、识别算法或阈值。
- 自动审批拦截两项：停止并重启旧本地代理、最后后台打开新版窗口，均只返回blocked by policy无详细原因，未执行被拒动作，也未改工具绕过。旧15116/57011保留；采用并行空闲本地实例45316/62911作只读验证，收尾两实例均idle/preview off。最终展示窗未自动打开，准备start_video_sync.cmd供用户手动启动当前85帧会话（现有最新版构建入口，绑定本轮62911，可用--joint-url覆盖）。
- 证据docs/evidence/2026-10-26_video_sync_preview/（CHECKS、real_media_summary、real85账本/summary、真实PNG、before/input SHA与所有测试日志）。初次视频QA误用旧标准二进制超时、改隔离路径；初次预览报告按Windows GBK读中文失败，改UTF-8；失败日志保留。保持同期骨架/标注台/启动器改动；无Git写、源数据改写/删除、板端部署/服务启停/驱动网络修改、真实bag/视频采集、训练下载模型或HR-09。

## 2026-10-26 2D+3D 联合路线深化（消融 / 最小 GT / 困难场景清单 / 780 地面口径）

- 用户给定四个任务与红线；本轮只做只读分析 + 一次性渲染 + 文档，不采集、不部署、不改生产规则。
- 新增 `pc_apps/range_fall/exp_2d3d/ablate.py`（一个脚本六个子命令：survey / fit-ground / ablate / render / tables / compare）。`ablate --run` 逐帧核对复算前端与既有账本：386 386/386、780 780/780 帧一致（连通域 id、`ambiguous_component_ids`、目标来源行），证明用的是同一条链。
- 消融（`docs/evidence/2026-10-26_2d3d_route/ABLATION.md`）：2D 与 3D 不互补。源行逐帧完全相同（1166/1166 帧、1,530,598 行），`targetPixels` 恒等于 `len(sourceRows)`；同一行集 2D/3D 分块一致 386=266/269、780=339/355。2D 独占像面截断（38 帧）但 0 帧姿态；3D 独占地面相对结构。歧义计数（平面断裂/粘连/结构退化/位置冲突/截断）：386 = 29/1/0/0/15，780 无地面 = 117/1/312/1/23，780g = 117/1/6/1/23。联合链在 2D/3D 分歧帧上 386 29/32、780 无地面 0/118、780g 101/118 给出 vertical_surface。
- 780 地面（`GROUND_780.md`）：与 386 同一估计器与 fit/held 帧集合，只从 780 自己的帧拟合，`consensus=GOOD`，留出 RMS 27.6/27.3/27.3 mm，与 386 差 0.3514°/19.87 mm；同口径重跑 780/780 帧 0 丢帧 PASS，`sourceRows/box/trackId` 与无地面运行 0 差异；355 目标帧 → 313 vertical_surface + 4 lying_pending + 55 low_posture_unclassified，0 suspected/0 confirmed。
- 最小 GT（`MIN_GT.md` + `MIN_GT.json`，agent 判读非人体真值）：48 帧（386 20 / 780 28）。存在性 44 确定帧 TP33/FP0/FN0/TN11（选择偏倚，不当效果）；姿态 站立 24（联合 18、R3D 24）、蹲 9（联合 7+1 躺、R3D 3+1 躺+2 unknown）。逐帧差异 11 帧已列表。
- 未统一项：`FallStateMachine` 用 `height_median_m ≤ 0.7`、`range_posture` 用 `height_m.max`，同一帧相反（386 8 帧、780g 27 帧）。本轮不改规则，写入状态与下一步。
- 采集清单 `ACQUISITION_CHECKLIST.md`：12 类 + 最小 3 会话批次 + 前置设备检查（引用 2026-10-25 20:28 `cap_20261025_202824` 的 `joint.json` 失败原文）+ 保留策略（每类 1 条、不导序列）。未采集。
- 回归：核心 797 OK(skip 1)、`pc_apps/range_fall` 53、capture 69、follow_calibration 2、joint 17、JS 9 套件全过，均 `-B -W error`。附带修既有缺陷 `make_release.py` 白名单缺 `analysis.py`/`depth.py`（修前 test_release 1 FAILED，修后 53 OK）。
- 删除：派生数据 3,163 文件 / 169,447,525 B 全部删除（聚合 SHA `4453fa68…3bdf94`，逐项清单与再生命令在 REPORT.md §4）。只留 5 份 md + `MIN_GT.json`。
- 未 Git 写、未改 `data/`（只读两段会话与一份失败 joint.json）、junction、历史 evidence、冻结配置、ML；未部署/采集/训练/下载/HR-09。人体/跌倒效果 UNKNOWN，confirmed 关闭。并发写：`PROJECT_STATE.md` 在读取与插入之间被另一会话追加过一节，已保留其内容并在顶部插入本轮小节。

## 2026-10-26 2D+3D 路线复验（只读复跑，未重生派生数据）

- 复验对象是上节六份产物与 `pc_apps/range_fall/exp_2d3d/ablate.py`；不重跑 780g——重跑会再生成约 169 MB 派生数据，与"一次性生成、一次性删除"冲突。
- `ablate.py survey` 复算：386 386 帧 / 269 目标帧 / 632,913 = 632,913；780 780 帧 / 355 / 897,685 = 897,685；合计 1,166 帧 / 1,530,598 行，`targetPixels == len(sourceRows)` 386/386、780/780，与 ABLATION §3.1 逐值相同。
- 既有 `oriented386|780/analysis.json` 复核：386 state 376 unknown + 10 `low_posture_unclassified`、posture 269 `vertical_surface` + 117 unknown、reason `baseline_not_ready` 259 / `target_not_locked` 116；780 全 unknown、reason `target_not_locked` 409 / `no_ground_or_candidate` 355 / `target_changed` 16；两会话 `semantic=UNKNOWN`、`confirmedEnabled=false`、`intervals=0`、`calibrationStatus=UNVALIDATED_WITH_HUMAN_GT`。
- `MIN_GT.json` 复核：48 条（386 20 / 780 28）、10 字段齐全、`rawSha256` 全 64 位；计数 有人33/无人11/不确定4、站立24/蹲9/不确定15、跌倒否35/不确定13、置信25/19/4，与 `MIN_GT.md` 一致。
- 回归复跑：核心 797 OK(skip 1)、`pc_apps/range_fall` 53、capture 69、follow_calibration 2、joint 17、JS 9 套件全 exit 0，均 `-B -W error`；`ablate.py` 3.8 语法与"仅 stdlib+NumPy"复检通过。
- 现场状态：`%TEMP%\opencode\route2d3d` 不存在（派生数据已按 REPORT §4 删除）；工作树新增只有 6 份产物 + `ablate.py`（均未跟踪），`perception.yaml` 改动时间 2026-10-20（非本轮）；未 Git 写。人体/跌倒效果仍 UNKNOWN，confirmed 仍关闭。


## 2026-10-26 四肢与脚部同源区域候选

- annotator_v2新增脚部1/2与稀疏像素点集，body_branches以同一目标实测掩膜细化/分支拓扑+RAW XYZ邻接（≤0.15m）提出四肢/脚候选；只移除像素，不补洞/缺测，不换目标，不改变跟踪与告警。上下段按实测弧长比例分开，不声称肘/膝；脚另须末端实测转向≥30°和跨度≥45mm/足够源点，直腿图底不会强行补脚。origin/evidence/settings/不确定原因随每部位保存，未解析标签uncertain无点集，分支号仅当前帧排序。矩形旧标注与保存重载兼容，遮挡编辑保留稀疏可见点；增加小腿—脚表面无向轴角。
- 第453帧纯自动上臂59/118、前臂32/93、小腿97/110点，大腿和脚未解析；页面保留原165点手工编辑器头区域，属agent软件探针而非GT。第二会话200帧上臂48/162、前臂110/117、大腿220/267、小腿152/169、脚20/27；头部举臂粘连留空。末端69.8°/56.1°转向不是解剖脚/地面接触证据。人体部位/姿态/跌倒效果全部UNKNOWN，不默认传感器Z=重力，不把静态形状叫跌倒。
- 全1166真实帧（780+386）最终回放PASS，43,410,912有效像素/1,530,598目标行同源往返、源点互斥/范围过滤、重复计算确定性及16份旧保存标注原样重算通过；807,123点分配区域，其余723,475留未解析。780/386有候选258/251帧、有脚候选149/188帧，非准确率；旧条带有建议但拓扑留空97/18帧（分支不足93/18、低姿紧凑4），逐帧输出差异。诊断117个早期留空帧发现3帧根点在小连通域；最大脊线根点修复后668/755恢复候选，旧有候选帧无丢失，另1帧仍分支语义不足。
- Web95、body+server23、核心797完成（1实际ROS本地跳过），Python-B -W error；构建通过，Vite>500kB包提示保留。合成非人体T形/分叉形验证四肢末端支撑、直端不造脚、RAW刚体旋转不变、深度跳变/缺像素不桥接、稀疏脚保存和空/错索引拒绝；不当人体效果证据。首轮T形被全宽高比误拒，改用中心截面宽度；第二轮浮点刚体变换使等距归属漂移，路径代价纳米级量化稳定（RAW XYZ未量化）；失败日志BODY_TESTS_01/02保留。
- 真HTTP保存重载、错帧/SHA/方向/人物/标定、版本冲突拒绝通过；UI脚1遮挡保持20源点，撤销恢复automatic并保存重载，切201清旧脚部通过。新增完整图适配，新增支撑扩展时3D重新取景/选择变化不重置。f453四肢与f200脚部2D/3D实图及状态保留；最终IAB旧tab失效后新建页视口311px，滚动坐标越界未盲重试，未把窄截图当完整并排实图，采用此前984px实图，底部浏览器打开请求queued。
- 新入口start_body_parts.cmd本机8947，默认cap_20261017_113516第453帧；脚部演示cap_20261018_110029第200帧。仅重启本轮自己创建的8947本地开发进程载入最终根点代码；旧8946及其它本地/板端服务均未动。证据docs/evidence/2026-10-26_limb_foot_mapping/（replay_final封存、replay01早期对照、CANDIDATE_COMPARISON、ABSTENTION_DIAGNOSTICS、HTTP/单测/截图/SHA），README/STATE更新。完整50951文件区间基线扫描结束后才改生产代码，已有历史证据/核心保持；同期STATE/PROGRESS外部更新保留。原会话只读，无Git写/源数据删移/部署采集/驱动网络/训练下载模型/HR-09。

- 收尾追加：Web最终96项通过（新增区域扩展重新取景及颜色GPU属性复用回归），3D颜色缓冲按容量复用，避免逐帧/逐次部位选择创建新GPU属性；Python/最终1166帧算法源码封存保持。完整图适配已构建，最终工具视口311px限制与旧tab失效留存，采用先前984px实图作脚部检查，不宣称最终大视口截图。3680份原核心/共享range/前轮body与skeleton证据定向SHA保持，两会话meta/points全SHA保持；最终CHECKS_FINAL/SOURCE_SHA256_FINAL/CONTINUITY_FINAL_SUMMARY及ARTIFACT_SHA256已封存。


## 2026-10-26 实图反馈修复：头部消失、躯干窄条漏分

- 直接看图确认v1缺陷，未再把映射/测试通过当部位划分可用：举臂头部不是脊线端点而被整块漏掉，躯干线种子有界分配被手臂路径竞争截成窄条。body_branches升v2，用实测中央顶帽/横截面区域，要求原RAW邻接连通；不放宽0.15m边/0.16m路径门、不填无效/背面点。躯干内部优先、边缘保留实测肢体路径，肩/颈/髋边界仍是启发式而非关节。
- 386 f200纯自动头0→137点、躯干515→1045点，两脚20/27且源行逐项保持；780 f453纯自动头336→171（旧区域进肩）、躯干318→916，原165点手工编辑器头探针保留而非计自动成功。贴身上臂仍无法可靠分开而留空，前臂19/62、小腿97/110；f700低姿仍全空。初版修复把低姿背部当大头、过宽顶帽吞掉上臂，已通过帽宽/躯干支撑约束和中位轮廓宽度/边缘路径竞争修正，早期v2/v2b机器产物保留。
- 1166真实帧新方法回放PASS，原sourceRows摘要/trackId/generation/state/posture/目标数逐值0差异；43,410,912有效像素/1,530,598目标行映射与区域互斥通过，分配1,179,728、未解析350,870点。头候选180→260/139→259、躯干256→329/251→264；上臂和部分前臂候选减少，loss逐帧及原因公开记录，未用统计隐藏；腿脚候选帧数保持。没有人体GT，人体/姿态/跌倒准确性UNKNOWN，不把点数或更宽的着色当精度。
- body+server25（Python-B -W error）、Web96、核心797完成（1实际ROS跳过），构建成功（Vite>500KB提示保留）。合成举臂中央帽/躯干两侧覆盖、深度不连通帽拒绝、紧凑轮廓不造大头通过；首个V形测试夹具在一行顶帽后即接到手臂，修正为有独立可见顶帽的几何夹具，生产最小支撑约束未为它放宽，TESTS01失败保留。旧16份标注仍原样重算一致。
- 真HTTP当前两示例重算/版本锁保存重载、错帧/SHA/方向/标定/人/版本冲突拒绝通过；保留手工头区域，当前dev store的自动结果升级v2，旧缓存加载有提示。实际页面AX与窄工具截图已确认v2、头137/躯干1045和新头躯干相对几何；临时IAB标签失效不冒充已保存的大窗截图。另用matplotlib按同源完整RAW点集生成高分辨率2D/3D前后对照并逐图查看，灰色未解析点保留；3D每个源点只画一次，避免灰底点覆盖重复彩点造成渲染假缺失。这是诊断渲染，不冒充浏览器截图。
- 证据docs/evidence/2026-10-26_head_torso_repair/：replay_final、BEFORE_AFTER、HTTP_REFRESHED_EXAMPLES、HTTP_E2E、head_torso_3d_before_after.png、两帧2D/3D完整对照、测试/源码SHA。DIRECT_SOURCE_BEFORE在修改前同步封存；全树BASELINE为区间扫描，不是原子修改前快照。仅重启自己创建的8947本地服务，原会话/历史证据只读；不Git写、不动板端/驱动网络、不部署采集/训练模型/HR-09。用户当前页刷新8947第200帧即可看到新结果；剩余肩/腋下/贴身上臂语义尚未解决，不宣告完整人体部位识别。


## 2026-10-26 实时锁定现状诊断（22:09:08，未改生产）

- 用户询问为何实时无法锁人及2D→3D是否已实现。本轮只读核对：Qt LiveSource仅订阅原始点云和/single_target_live/state；RangeRuntime为离线前景/组件/3D跟踪链，range_image_node仅距离图转换，尚未接入此实时锁定入口，不能把距离图转换或几何候选称为人体识别完成。
- 现场8秒15条状态均automatic/unselected/invalid、target_source_rows为空、source=null、acquisition.reason=required_cloud_stale，末条cloud age=14941.049s，IMU/device同样stale；worker健康只说明心跳仍在。另4秒只读原始点云38帧、9.585fps，说明桥/驱动有流而识别节点输入已过期；与既有订阅失联症状一致，具体底层复发原因未确认。本轮未重发publisher列表或重连/重启板端。截图时刻的精确状态未保存，不能把本次采样当该帧诊断。
- range_live/runtime/subscription_health 24项运行（23通过、1实际ROS本地跳过），Python-B -W error；386真实帧经26字节驱动消息替身→距离图及历史preview对照零差异，非实时找人效果验证。证据docs/evidence/2026-10-26_live_lock_diagnosis_220731/，含原始状态、仅源header观测、测试、回放及关键源码SHA；人体锁定/跌倒效果UNKNOWN。无生产源码修改、Git写、部署/启停/采集/驱动网络/数据改写/模型或HR-09操作。

## 2026-10-26 倒地报警（持续低姿态）首轮：真实会话报出 1 段

- 按用户"先能倒地报警"新增默认关闭的命名变体 `ground_alert_v1`：`core/range_ground_alert.py`（纯判定，无 I/O）+ `pc_apps/range_fall/ground_alert.py`（CLI，读会话/analysis/地面，`--verify` 逐帧对账）。判据只用两个既有值——`low_height_m 0.7`、`low_min_duration_s 1.5`（原样引用 `fall_state.DEFAULT_SETTINGS`），删掉生产链的"确认下降"与"躺倒几何"两门；零新增阈值、不改默认、`confirmed` 恒 False。
- 结果：386 = **0 段**（两段低姿态 0.52 s / 0.31 s，正好是 GT 标"站立、局部可见"的帧）；780 原状（无地面）= 0 段 / 780 帧高度不可用；780 自拟合地面 = **1 段 f674–f707 / 3.42 s / 34 帧**，与 GT 蹲坐地帧（676/680/690/700/706）重合，在起身帧 712 前结束。
- 可信度：386 上 269/269 个有目标帧的复算 `height_m.median` 与既有 `analysis.json.heightMedianM` **完全相等（maxAbsDiff 0.0）**；低姿态帧集合与生产规则层一致（386 = 10、780g = 55），变体与生产的差别只在两个门。
- 780 报警起点被单帧空洞推迟：659–664、666、668–672 三段被 665/667/673 三个空洞切断，直到 674 才累计到 1.5 s，即"单帧空洞推迟报警约 5 帧"。
- 回归：核心 **810 OK**（原 797 + 新增 13，skip 1）、`pc_apps/range_fall` **53 OK**，均 `-B -W error`；三个新文件 `ast.parse(feature_version=(3,8))` 通过、仅 stdlib+NumPy。
- 证据 `docs/evidence/2026-10-26_ground_alert/`：`REPORT.md` + `ALERT_INTERVALS.json`；派生 10 文件 / 42,616 B 已整体删除（聚合 SHA `33ecbb1d…baff`）。未 Git 写、`data/` 只读、未部署/采集/训练、冻结配置与 ML 未动；人体/跌倒效果 UNKNOWN，confirmed 关闭。**未接 runtime/控制台**，接法是默认关闭的 `--alert-variant` 开关。


## 2026-10-26 同源目标→部位/持续低姿态→Qt/Web 本地集成与流畅性

- 固定入口 `console_v2/start_integrated_preview.cmd`，注册本轮 `run386_final/run780_final`，默认780 f690；Qt当前源码私有实例已打开（PREVIEW_WINDOW.json），不自动连板端或录制。共享analysis包含原动态状态、独立groundAlert、预计算bodyCandidates、距离图和同源骨架；网页打开即显示预计算候选，既有手工部位保留，独立flow_store_dev。Qt显示部位点数，完整同色2D/3D部位仍在网页；新增时间条和触发帧跳转。原生/Web标注台显式GT根现一致。
- `--alert-variant ground_alert_v1`与`--body-candidates`均默认关闭。低位提示保留独立语义，蹲/坐地也触发，不改原state/confirmed；采用建议标为持续低姿态动作。780段f674–707、首次实际提示f689（非f674），f688观察中、f708消失；386无提示。补跳帧/时钟/间隔/目标/代际/绑定重置，在线前缀不借未来结果。
- 两段1166帧最终全量重跑，sourceRows/trackId/generation/box对旧结果0差异；性能改前后**整帧结果**（含姿态、部位、提示）0差异。386 f200头137/躯干1045；780 f453自动头171/躯干916（不是旧165点手工区域）。重计算不写源会话/GT。
- 首次780源节奏因背景初始化与审计/显示开销覆盖10帧，原账本保留。逐射线中位/MAD改为等价排序取中值，保留原数值门；来源审计与分区守恒采用NumPy整数数组，校验不删除。最终单独1×源节奏780/780、0覆盖、实际消费序列复算及全帧对照0差异；循环P95=63.259ms、发布年龄P95=63.400ms（含诊断/显示/JSON/IO，非ROS网络/GPU），原更严G1/G2及f360缺口仍保留。前轮有短时前端构建/HTTP并发，不把前后耗时当严格控制的加速比。
- 原生真实f640–734共95帧/95个同帧ACK，播放中94帧约9.645fps，间隔P95=112.565ms/max124.577ms，提示亮起恰为f689–707；初始暂停/Qt启动间隔另列，不混入播放fps。原生f690距离图/提示和f200 3D已看图。网页真HTTP与实际AX核对137/1045、预计算及提示；IAB约504px窄窗截图明确标窄，不声称大视口并排检查。
- 本地订阅恢复补“连接仍在但回调沉默”的10s重建，按接收回调而非推理速度判断；Qt显示required_cloud_stale与输入年龄。**尚未部署**；现场仍走旧/single_target_live/state，新2D/3D实时跟踪、现场地面/空场背景绑定与实时部位传输尚待板端授权后接入，不能称实时锁人完成。
- 回归：核心814 OK(skip1实际ROS)、range55、body/server26、Web97，Python均-B -W error；Qt/C#构建及原生11回归、2实时模拟、两会话全帧与专项、10秒播放通过（一个会话专用用例按输入跳过）；相关9份Python3.8语法通过，板端实际运行未做。源码/输入绑定检查保持；同期开发main.cpp的外部修改已保留，曾短暂非UTF8导致补丁拒绝，刷新后有效源码构建通过。
- 证据 [evidence/2026-10-26_unified_flow/](evidence/2026-10-26_unified_flow/)；运行/重建/实时缺口见 [UNIFIED_FLOW.md](UNIFIED_FLOW.md)。完整51156文件非原子基线（跟踪+非忽略未跟踪，忽略数据/构建未纳入），最终关键SHA另存；没有历史evidence全量后验SHA声明。无Git写、源数据删移改写、板端部署/启停、采集、驱动网络、训练下载模型或HR-09。人体/部位/姿态/实际跌倒效果UNKNOWN，confirmed关闭。


## 2026-10-26 标注台改为 Qt 原生页面（重新写，不嵌入网页）

- 用户要求「把标注台集中进 Qt 界面、重新写」：`console_v2/app` 新增原生标注页面，功能抽屉「标注台」切到窗口内页面（左侧会话/人物/区间，中间 XY 俯视画布，底部沿用回放控件），不再打开浏览器；原浏览器入口保留为「旧版网页标注台 ↗」，只用于尚未搬入的部位/区间细标。
- 新增 C++ `native/AnnotationView.h`（QQuickPaintedItem）：当前帧点云米制 XY 俯视（高度色带、网格、比例尺、原点十字、拖框虚框），拖出新框、点选、拖框身移动、拖角缩放、右键平移、滚轮缩放；paint 在渲染线程，共享状态用递归互斥量保护。
- 新增 C# `service/GtStore.cs`：沿用 `gt_annotate/2`，默认写 `pc_apps/annotator_v2/gt_store_v2/<sid>/draft.json`（`--gt-root` 指私有目录），临时文件原子替换、版本冲突拒绝，字段校验对齐 `pc_apps/annotator_v2/src/domain/validation.ts` 的 error 规则（格式/坐标系/帧数/帧界/宽高/z 范围/人物引用/同人物同帧重复/区间/取样清单），并拒绝含目录链接的写入路径。协议新增 `gtLoad`/`gtSave`；管道单行上限 8192→1 MiB 以容纳整份文档（其余命令不变）。
- QML：人物 P1/P2… 与「当前人物」、动作/事件区间（起点/终点取当前帧、新增、列表跳转/删除）、框属性（z 上下限/可见性/复核）、撤销/重做、保存/重载、状态行；同一人物同帧禁止第二个框；载入网页草稿后 persons/suggestions/sampleFrames/annotator 原样写回。
- 自检 `--annotation-report`（真实窗口鼠标事件，私有 GT 根）：拖框 0→1、拖框身移动 dx0.525/dy-0.2625 m 且宽度 0.7399 m 不变、保存 0→1、重载保留、区间 [0,24] 保存 1→2、旧版本保存被拒（标注版本冲突：磁盘 V2 / 界面 V0）、`zMax<=zMin` 被拒；真实 386 会话截图与 draft.json 在证据目录。
- 回归：`test_annotation.py` 2 项（合成两会话 + 真实网页草稿 `cap_20261023_221125` 追加 1 框/1 区间后 V3→V5，suggestions/sampleFrames/persons 原样、源会话 SHA 不变）；`test_workspace.py` 1 项、`test_camera.py` 2 项（用现存会话）、`console_v2/app` 全套 30 项中仅 camera 2 项因本机缺 `cap_20261025_203653` 会话报 `DirectoryNotFoundException`（既有环境缺口）失败；构建 `-Wall -Wextra -Werror` 零警告、`-B -W error`。
- 边界：本轮只搬整人框 + 区间；身体部位像素标注、2D 距离图像素层、算法建议采用、同帧 3D 视图仍在网页版。框是人工范围，不是人体/跌倒真值；未写原始会话、未连板端、无 Git 写/部署/采集/训练/HR-09。
- 同期另一会话在相同源文件上并行改动（疑似区间提示/`--smoke-frame`/`test_unified.py` 等），其改动全部保留并随本轮构建通过。过程中一次 PowerShell 整文件改写把 `main.cpp` 中文写成非 UTF-8 并吃掉 16 个字符，已逐处修复并复验编译与全部相关测试。
- 证据 [evidence/2026-10-26_native_annotation_bench/](evidence/2026-10-26_native_annotation_bench/)。

## 2026-10-26 原生标注台代码/证据审查（只读，不改功能）

- 复核方式：不采信既有报告，重新构建并跑 `python -B -W error console_v2/app_dev.py build`、`test_annotation.py` 2/2、真实 386 帧会话 `--annotation-report` 全 PASS；源码未改，证据文件未改。
- **纠正数字**：真实自检报告里框为 5.82301 × 4.20179 m、拖框身 dx 4.13175 / dy −2.06587 m、宽度不变；上一节的「dx0.525/dy-0.2625、宽 0.7399」「`PROJECT_STATE.md` 第 7 行」「`CHECKS.md` 第 48–50 行」同一组数来自**合成测试**，不是真实 386 会话。该报告生成于 `main.cpp` 补上移动用例之前，只有 13 项、无 `box_move_changes_center`/`box_move_keeps_size`。
- `evidence/.../source_shas.json` 记 `test_annotation.py` 为 9100 B、实际 9045 B（其余 8 项 SHA 一致），即证据与当前源码不同版；`CHECKS.md` 的「2/2 OK」按现文件重跑仍成立。
- 待修缺陷（按严重度）：① 跨会话串标注——`Main.qml` `onSnapChanged` 换 sid 不清旧框，`applyGtMessage` 不看 `gt` 消息里的 `sessionId`，`gtLoad` 回来前按保存就把旧会话框写进新会话；② 保存/脏标记竞态——`gtSaved` 无条件清 `gtDirty` 并设版本，保存中编辑被标成已保存，连点保存第二次报版本冲突；③ 选中框跨帧残留——画布只画 `frameBoxes`，属性面板改/删的是别的帧的框；④ z 控件标「/ m」实际是厘米（`Math.round(z*100)`，步长 10=0.1 m）；⑤ `AnnotationView` 鼠标处理写 `m_gesture/m_drawScreen/m_dragWorld` 不加锁而 `paint` 加锁读，与「共享状态用互斥量保护」的说明不符；⑥ `GtStore` 未校验 `suggestions`，缺 `validation.ts` 的 `suggestion.duplicate-id`/`suggestion.empty`；⑦ `SessionPattern` 允许 `..`，`Load` 可越出 store 根（`Save` 有 `EnsureWritable` 挡）；⑧ `--gt-root` 带尾分隔符时 `Root+separator` 前缀判断恒假，保存必失败。
- 自检设计小问题：`invalid_box_rejected` 是在界面版本被压到 V0、磁盘 V2 时触发，只因 `GtStore.Save` 先校验后比版本才看到 zMax 错误；两条后端拒绝无法在同一次运行里各自独立观察。
- 语义不变：框仍是人工范围，不是人体/跌倒真值；本轮只读审查，无源码改动、无证据文件改写、无 Git 写/部署/采集/训练/HR-09。

## 2026-10-26 标注台审查修复（8 条全修，含证据勘误）

- 按上节审查顺序修完 1→8：① 换会话走唯一入口 `selectSession()`（`resetGt` + 版本归零 + 重新 `gtLoad`），`applyGtMessage` 先比 `message.sessionId !== selectedSessionId` 丢弃迟到回包，新增 `gtLoadedSessionId`：本会话没载入完 → `saveGt` 拒绝；`open` 先于 `gtLoad`，帧消息确认会话切换后补一次载入（`gtLoading` 防逐帧重发）。② `gtSaving` 期间禁用保存并在 `saveGt` 里再拦一次；`gtSaved` 只认在飞那次，用发起时的 `gtSnapshot()` 比对，保存期间又改过就保持未保存；`error` 也转发到 gt 通道以解除 `gtSaving/gtLoading`。③ `selectedBox` 改为只从 `frameBoxes` 取，`onSnapChanged`/`onGtBoxesChanged` 调 `pruneSelection()`，删除按钮与函数都以 `selectedBox` 为准。④ z 标签 `/ m`→`/ cm`。⑤ `AnnotationView` 的 `mousePress/Move/Release`、`setDrawMode` 写侧补同一把递归互斥量，类注释改成与实现一致。⑥ `GtStore` 补 suggestions 校验（id 重复、框与区间都为 null），注释写明只覆盖 error 级。⑦ 会话编号正则加 `(?!\.\.?$)`，`Load`/`Save` 共用 `ResolveDirectory()`（编号 + 根目录包含检查）。⑧ `Root=Path.TrimEndingDirectorySeparator(...)`，前缀判断改 `RootPrefix`（盘符根不重复补分隔符）。
- 新增 `--self-check-gt`（`GtStoreChecks.cs`，不启动 Qt）：15 项，包括带尾分隔符根目录保存、子 store 上一级的诱饵 `draft.json` 证 `Load("..")` 读不到、suggestions 两条例、warning 级 adopted 不拒绝、网页草稿形状往返。`test_annotation.py` 增 1 项（3/3 OK，18.7 s）。自检新增 6 项：`save_releases_saving_flag`、`foreign_session_response_ignored`、`save_blocked_until_loaded`、`selection_cleared_off_frame`、`reload_restores_disk_version`、`invalid_probe_keeps_version`；`invalid_box_rejected` 改为先重载恢复磁盘版本再发非法框，两条后端拒绝现在各自独立。
- 真实 386 帧 `cap_20261018_110029` 自检 21 项全 PASS，1 框 + 1 区间，V0→V1→V2；归档这次画布 1057×562，框 5.82301 × 4.20179 m，dx 4.13175 / dy −2.06587 m，宽度不变，与旧报告（23:01）和审查复跑逐值相同。本轮另一次画布 1057×668 的运行（未归档，窗口 1360×880，原因未定位）得到 4.899 × 4.20179、dx 3.47611 / dy −1.73806：宽度与位移按 668/562=1.1886 反比变化、框高不变（只由视图 y 跨度决定）。这些米数是拖框像素比例 + fit 缩放的产物，引用时必须带画布尺寸，不能跨运行当固定几何真值。
- 证据勘误：旧 `docs/evidence/2026-10-26_native_annotation_bench/` 的 `CHECKS.md:48-50` 把合成用例的 `0.7399 × 0.5339 m`、`dx 0.525 / dy −0.2625` 记在真实会话报告名下，该目录自己的 `annotation_report.json` 是 `5.82301 × 4.20179` 且没有移动两项；`0.7399` 那组数见于 `console_v2/.tools/app-evidence/test_*/annotation.json`。旧目录按「历史 evidence 只读」未改写，勘误写在本轮证据与 `PROJECT_STATE`。旧 `source_shas.json` 记 `test_annotation.py` 9100 B 而审查时 9045 B，说明那份清单与源码不同版。
- 回归：构建 `-Werror` / C# `TreatWarningsAsErrors` 零警告；`test_annotation.py` 3/3（18.7 s）；`console_v2/app` 全套 31 项 OK、skip 6、167.9 s（`FALL_SESSION` 指向现存会话，避开既有 camera 环境缺口）。证据 `docs/evidence/2026-10-26_annotation_review_fixes/`（CHECKS、source_shas、annotation_report、两张截图、gt_store、测试日志）。
- 边界：跨会话用例是注入回包 + 状态检查，不是真双会话竞态；保存期间编辑、双击保存无自动化时延用例（靠 `gtSaving` 禁用 + 快照比对）；第 5 条只保证锁覆盖一致，无并发压力测试。未做低优先级项：每帧无条件 `setFrame` 整帧拷贝、色带原始 min/max、切会话未保存修改无确认。框仍是人工范围，不是人体/跌倒真值；无 GT、无准确率结论；`data/` 与历史 evidence 未改，无 Git 写、未连板端/部署/采集/训练/HR-09。

## 2026-10-27 Qt 默认会话回放 + 功能页自选巡检

- 用户要求：Qt 启动默认停在会话回放、功能自己选，并确保 Qt 无明显缺陷。实测默认落地本来就是第 0 页，但没有任何用例锁住它；本轮补上真实窗口巡检并顺手清掉启动路径的 Qt 告警。
- 新增 `--tour-report`（20 项，真实窗口）：900 ms 核对「第 0 页 / replay / 暂停首帧 / 会话已载入 / 会话列表 12 条 / 标注页隐藏 / 点云画布 1059 px / 无多余第二窗口」，再依次点开实时锁定(1)、联合录制(2)、标注台(3，画布 1057×537)回回放(0)，播放 300 ms 帧号 0→2、暂停、逐帧 2→3。`test_ui_tour.py` 断言 20 项全过、report 的 section=0/mode=replay/frameCount=386、源会话 meta/points SHA 不变，并要求 `nativeStderr` 为空（只放行下面那条已知布局告警）。
- 清掉两类每次启动都出现的 Qt 告警：① 7 个 `QQuick3DGeometry`（点云/目标/框/骨架线/骨架点/框选/框选框）在首帧前就被渲染，构造时 stride=0 → `0 is an invalid stride`，给 `CloudGeometry/SkeletonGeometry/BoxGeometry` 构造函数补 stride+Position；② 视频子窗 `flags` 绑定读没有 NOTIFY 的 `root.flags` → `non-NOTIFYable properties`，改读可 NOTIFY 的 `headlessChecks`（C++ 报告/自检模式同时置位，主窗口 flags 不变）。修前最近一次运行 `nativeStderr` 9 行，修后标注台重跑 0 行。
- 诊断辅助：`nativeStderr` 日志条目加 `atMs`。靠它定位到布局告警发生在切页后 ~1 s，并逐项改 QML 副本隐藏顶部控制行/底部播放行/结果卡/侧栏/标注页重跑，都没消除，判定为外层布局 + 窗口尺寸的已知 Qt 行为（历史 22 份 run.json 已有同一行，早于本轮），测试里显式放行并注明。
- 未改既有「带视频会话自动打开同步视频窗口」行为（`test_video.py` 覆盖，`--video-report` 走 9 项）；不带视频的会话启动只有主窗口。没把「自己选功能」扩大成移除该自动窗，若用户要的是这个，改 `videoWindowOpen/autoVideo` 默认值并同步那个用例即可。
- 回归：构建 `-Werror`/C# `TreatWarningsAsErrors` 零警告；`test_ui_tour.py` 1/1（7.1 s）；`console_v2/app` 全套 32 项 OK、skip 6、163.7 s；标注台 21 项 PASS 重跑（画布 1057×562，数值同上轮）。证据 `docs/evidence/2026-10-27_qt_default_tour/`（CHECKS、source_shas、tour_report/tour.png、annotation_report/截图/gt_store、ui_tour 与全套日志）。
- 边界：巡检只覆盖启动、四个功能页、播放/暂停/逐帧；改名/删除/实时连接/联合录制开始停止仍靠各自套件；「无告警」是就本轮路径与日志而言。窗口高度随桌面可用区变（本轮 tour 1360×749、标注台画布 1057×562），上一轮「米数随画布尺寸变」的结论继续成立。未改 `data/`、历史 evidence；无 Git 写、未连板端/部署/采集/训练/HR-09。

## 2026-10-27 上位机页面优化调研（联网受限）与本站审计

- `web_search` 本轮不可用：返回 `HTTP 402 Insufficient Balance`，没做成关键词检索；改为直接抓取已知页面，成功两份：Qt 6.12《Performance considerations and suggestions》、ISA-101 系列标准页。NN/g 两个 URL 猜错 404、ISA 远程监控文章讲网络接入不涉设计，均未采用；HPHMI 的灰底/颜色只给异常/不做装饰动画等具体做法按领域经验列出，**未取到原文**，文档里已标注。
- 审计写成 `docs/UI_OPTIMIZATION_AUDIT_2026-10-27.md`：8 条可迁移原则 + 现状表（顶部 68 px 装饰、会话列表两行且 `Button.text` 是死属性、状态区 UNKNOWN 重复且颜色同时表示正常/提示/选中、3D 无坐标轴与色带图例、无键盘快捷键、9 级字号且 10–11 px 有 12 处、未注册 analysis 时无空状态解释、每帧无条件 `setFrame` 与 n×20 字节颜色映射重建），以及 P0/P1/P2 排序、不建议做法、可自动化的验收（tour 增状态条/快捷键/空状态检查，`setFrame` 计数前后对比）。
- 本轮只调研+审计，未改界面代码（等用户选 P0 再动）；无构建/测试（无代码变更）、无 Git 写、未动 `data/` 与历史 evidence。

## 2026-10-27 界面 P0：状态条 / 字号与颜色角色 / 快捷键 / 惰性拷贝

- 按审计 P0 实施：① 顶部 68→52 px，右侧常驻状态条（`objectName: statusBar`）显示模式/会话/帧 `n/总数`/目标状态/低位提示/未注册分析/当前页；目标状态颜色只表达“是否偏离正常”，无结果用次要灰。② 固定 4 级字号（12/14/18/22）与 5 个颜色角色（info/warning/alarm/selection + muted/dim），状态条和结果卡先迁移；结果卡大号状态在无结果时显示「无结果」并用次要灰（目标/高度两栏仍是 UNKNOWN，留 P1），未注册 analysis 由状态条徽标+悬停说明。③ 快捷键：空格播放/暂停、←/→ 逐帧、Home/End 首末帧、Esc 取消框选/选中；播放按钮改走同一个 `togglePlay()`；滑块右侧常显 `当前帧/总帧数`，控件行下常显快捷键提示。④ 标注画布只在标注页可见时 `setFrame`，切到标注台由 150 ms section 轮询补一次当前帧。
- `--tour-report` 从 20 项扩到 25 项：新增状态条可见（472 px）、帧号文本（`帧 0 / 386`）、未注册分析徽标、6 个快捷键注册（`Space/Left/Right/Home/End/Esc`）、`togglePlay()` 真正起播；播放时长从 300 ms 拉到 500 ms 让发布帧数≥5。另把巡检失败路径从 `app.exit(2)` 改成 `quit`：此前 GUI 先退会让服务写管道失败，真正原因被 `Pipe is broken` 盖住（本轮实际踩到一次）。
- 性能：同一次巡检服务端发布 6 帧，`frameCopies=6`、`annotationCopies=1`（只在切标注台时补一次）；改前是每帧无条件 `setFrame`。`test_ui_tour.py` 断言 `annotationCopies<=2` 且 `frameCopies>=published-2`。
- 回归：全套 **34 项 OK、skip 6、215.9 s**（其中 `test_local_bridge.py` 2 项是本轮期间另一会话新增的文件，mtime 01:03，一起跑过、非本轮改动）；`test_ui_tour.py` 1/1（7.3 s）；标注台真实 386 帧 21 项 PASS，画布 1057×551、框 6.57689 × 4.65289 m、dx 4.66667 / dy −2.33333 m、宽度不变（数值随画布尺寸变，只在同次运行内自洽）。
- 证据 `docs/evidence/2026-10-27_ui_p0/`：CHECKS、source_shas、before/after 截图、tour_report/tour.png、annotation_report+截图+gt_store、全套与 tour 日志。行为说明写进 `console_v2/app/README.md`。
- 边界：字号/颜色只迁移状态条与结果卡，列表副行/区间列表仍是 10–11 px 旧字面量；快速连续切页仍有一条 Qt 布局自恢复告警（巡检放行）；会话列表单行+过滤、3D 坐标轴/图例、错误就近显示、尺寸记忆、两层结构属 P1/P2，未做；未做对比度测量。框仍是人工范围，不是人体/跌倒真值；无 GT、无准确率结论；未改 `data/` 与历史 evidence，无 Git 写、未连板端/部署/采集/训练/HR-09。



## 2026-10-27 本机实时2D→3D链接线完成；真实45秒推理被工具拦截

- 新增PC `live_engine.py/live_bridge.py`，只订阅板端原始点云，在本机复用唯一ScanGrid/RangeRuntime/GroundAlertObserver；不依赖旧识别state，不发ROS或设备控制。loopback Foxglove仅接订阅（拒绝发布和浏览器Origin），主链/部位各一个最新任务槽；部位独立进程隔离GIL。Qt按完整源header+原消息SHA、目标源行、骨架支撑、PNG SHA/尺寸验证并显示实时距离图/目标/骨架/部位点数。跨帧、过期、坏SHA拒绝；实时标题不再沿用旧回放sid/帧总数。
- 用户明确回复空场后，实际连续接收接下来50帧，40788背景像素观测充分；原始点/背景只留本机RAM，落盘仅header/sha/参数清单。内存服务URL在EMPTY_BACKGROUND_SERVICE.json，采满即关闭上游订阅；没有继续学习人物。交接校验清单/标定/数组/来源epoch，重连或时钟回退要求重绑；默认无背景仅显示距离图，不假定空场。支持显式--declare-empty-prefix，但仅用于确实空场。入口console_v2/start_local_range.cmd。
- 现场地面未绑定：允许几何目标跟踪，低位判断明确unavailable。拒绝直接套离线会话地面；新增live_site_ground/1需现场site/frame/grid/provenance SHA一致，物理有效性仍UNKNOWN。新依赖只用PC已有websockets/NumPy，不进板端。
- 完整1166帧既有会话重封驱动26字节ROS1消息→新实时engine，最终源SHA封存重跑：目标源行/ID/高度、PNG、部位源行及因果提示0差异，780活跃提示仍f689–707。不是现场/人体GT验证。
- 本机假上游→真实新算法→本机bridge→C#/Qt端到端：初两轮线程版处理19/30，未下调检查；进程隔离后30/30、主链/客户端覆盖0，30帧深度同源匹配、28帧实测目标，25帧部位赶上期限（4个待处理部位被替换）。缺部位不挡主链、不跨帧套旧部位。坏wire SHA拒绝、无地面时高度UNKNOWN/提示不可用、默认Qt回放与功能巡检均过；截图明确标MOCK，不把LIVE标签当真实现场。
- 用户随后又明确授权本机只读45秒真实流推理。该启动两次均被自动审批拒绝；第二次已含明确授权，理由仍只有blocked by policy，无详细原因。没有换工具/启动方式绕过，没有真实45秒推理、锁定、报警或性能结论，板端未动。已在POLICY_BLOCKS.json和LOCAL_RANGE_LIVE.md记录；内存背景服务保留供用户使用，其他测试进程正常结束。
- 核心814 OK（1实际ROS本地跳过）、range61、engine6；原生14回归及最终4项local桥/坏SHA/无地面/UI tour通过，Python-B -W error；Qt/C#构建通过，Python3.8仅语法核对，运行桥明确PC Python3.12/websockets15。原core及两份上一轮analysis的54份定向SHA保持；基线55172文件为跟踪+非忽略未跟踪的非原子扫描，新PC文件在扫描期间新增而未改既有文件，源码最终SHA另存。
- 证据 [evidence/2026-10-27_live_local/](evidence/2026-10-27_live_local/)，用法与尚未执行的用户终端复现命令见 [LOCAL_RANGE_LIVE.md](LOCAL_RANGE_LIVE.md)。没有Git写、data/junction删移改写、板端部署/启停、采集落盘、驱动网络或模型训练/下载/HR-09。人体/身份/部位/真实跌倒准确性UNKNOWN，confirmed关闭。



## 2026-10-27 代操作真实45秒完成；修复Qt目标框与地址显示

- 用户再次要求代操作后，正常前台入口成功运行已授权45秒，复用50帧RAM背景；431/431帧、源seq17979285–17979715连续、主链/客户端覆盖0、错误0。397帧有几何目标、31帧候选竞争、3帧无稳定实测，g0_t0009/g0_t0001间3次ID切换；稳定同人/人体语义UNKNOWN。主算法P50/P95 47/78.5ms，本机接收至结果P95 86ms、max172ms（不含网络/显示）；部位进程423、待处理替换6、错误0。
- 启动顺序暴露问题：Qt构建消耗45秒窗口大部，仅最后22帧进入Qt并ACK，目标/深度SHA差异0、源跳号0；不宣称完整45秒端到端。Qt真实3D有43次input layout + 43次pipeline失败。BoxGeometry重复声明Position是根因，删同一提交中的第二次声明，自动/手动框共用修复；CLI live-url同步QML地址框，smoke真实核对字段值，避免仍显示旧板端URL。
- 缺地面loopback用例保持3D可见并检查渲染日志：修前112条GPU错误、用例失败；修后local桥/坏SHA/无地面3项 + UI巡检1项通过（39.755s，-B -W error），仅既有布局自恢复告警。MOCK截图亲眼检查框可见、地址正确；是既有会话经loopback，不是现场。首次共享runtime复制因WinError32文件锁失败，隔离构建通过，未结束他人进程。
- 新证据 docs/evidence/2026-10-27_live_operate_user/：REPORT/READY、ACTUAL_SUMMARY、CHECKS_AFTER、SOURCE_SHA256、前后测试和构建日志、明确MOCK截图。PROJECT_STATE/LOCAL_RANGE_LIVE更新。历史两次工具拒绝不覆盖，本轮成功事实单列。
- 45秒到期自动停止，未追加真实流运行/采集，原始点云与背景不落盘，板端未改，无Git写/data-junction变更。地面未绑定，实时低位提示unavailable，confirmed关闭；下一步仍是候选竞争/ID稳定性和现场地面绑定，不能宣称稳定锁人或现场报警完成。


## 2026-10-27 P0 审查修复：真实按键、同帧证据和标注惰性拷贝

- live 禁用五个回放键并在公共 send 拦截 play/pause/step/seek；视频播放按钮共用 togglePlay。隐藏加载/热重载不再无条件 setFrame，所有调用计数。颜色/字号角色用上，当前页 header 对比度 4.172→7.371:1；quit 的说法收窄为仅 tour。
- tour 49/49：QTest 真实 Space/左右/Home/End/Esc、改名文字/光标与无回放误发、按钮路径、状态条文案/12px/滑块帧号、画布 49,115 点且同帧；frameCopies=12 / annotationCopies=1。初轮模拟 live 的空格曾重新激活持焦点的改名按钮，截图检查发现后改为点云区焦点并增加关闭对话框断言；失败记录保留。
- 同帧图均 cap_20261018_110029 f3、1360×749、49,113 点，raw/XYZ/强度 SHA 全相同。原 P0 证据冻结，旧 before f3/after f5 与“34 项当前全绿”均在审计/README 勘误；不回填旧 CHECKS。
- 全套 36 项（30 通过、6 缺丰富 fixture 跳过），287.958s，显式使用现存386帧会话；含完整只读解码、标注、回放和 loopback 端到端。先前两项 camera 默认会话缺失、一次热重载时限失败均保留，camera 隔离复跑与最终全套通过。并发 local bridge 3→4 项且 LiveSource/live_engine 继续变化，最新独立服务构建后相关 8 项全过（82.822s），各轮 SHA/二进制版本分列。
- 证据 docs/evidence/2026-10-27_ui_p0_review_fix/：非原子全树基线55,272文件（master/c9c4ee4，定向修改前源 SHA 匹配）、源码快照、全套/定向日志、tour_final、同帧匹配与 SUMMARY。封存又发现独立现场 CLI live_site_check.py 更新；本轮无导入/执行，单列未覆盖，其他96份源码无漂移，不宣称整棵并发树全绿。
- P1未开始，150ms切页轮询保留；本轮无真实设备连接、Git写、data/junction变更、部署/采集/训练/HR-09。软件通过不代表人体/物理有效，GT效果UNKNOWN。


## 2026-10-27 现场地面绑定、真实45秒高度链与失效历史修复

- 当前28帧RAM现场拟合，复用floor_roi与TLS/SVD/RANSAC原质量门；RAW/innolidar法向(-0.4382335451,0.0021274862,0.8988586284)、offset1.3063137140 m，12002候选/11949内点，残差中位/P95/max=9.594/33.504/64.082 mm，连通片2.5 m²，逐帧角/偏移最大0.1921°/3.143 mm；四区、留出、方法一致性均过。SITE_GROUND/provenance同次SHA，runtime在seq17999800后加载；物理地面/安装真值UNKNOWN，没有保存原始云。
- 一轮真实只读45秒：432源/417算法，覆盖15；337地面有效、310当前目标及高度(0.797–1.710 m)，103竞争/4无稳定；选中ID切换1次。Qt431发布/431 ACK、414同源深度、309当前高度，SHA差异0/GPU错误0，最后源帧未发布Qt；部位409、覆盖6、错误0。初次Qt报告目录校验失败发生于订阅前、上游0帧，修正后才运行唯一真实窗口，不续跑。
- 修复现场地面质量/源/正负号契约和当前冻结选区监视；源/标定/地面失配、断流、过期统一清高度相关历史。修失效消息固定epoch=0被新代际Qt拒绝的问题，原生专项证实当前代际心跳在raw TTL前清空。普通连续短重连清历史而不直接废弃绑定，真正源回退或长缺口仍要求重绑。Qt透传动态下降/姿态/拒绝证据。
- v1仍只提示持续低位；命名候选gap_v2只暂停同ID唯一预测短空洞，不计缺测、不跨ID、不替换默认。修候选误清其它组件歧义。最终386/780整段1166帧源行/ID/高度/动态状态/PNG/部位/v1均0差异，v2也为780 f689–707；实际窗口低位/疑似均0、confirmed关，跌倒效果UNKNOWN。
- 现场处理P95=125 ms、接收→算法P95=188 ms、队列P95=93 ms；Qt拷贝ACK P95=13.15 ms且有350 ms等待，显示延迟UNKNOWN。随后消除地面重复decode，80帧离线配对输出0差异、P95 50.63→43.44 ms，未再接现场。实际2D截图落在算法覆盖帧17999954，显示无结果；真实末尾截图因Qt粗定时器合并漏拍，clearTarget有日志，改PreciseTimer后49秒MOCK末尾目标/高度/深度清空通过；不冒充现场补测。
- 回归核心814 OK(1 ROS跳过)、engine/ground13 OK、原生5项+epoch专项1项OK。原地面/配平30项29过，1缺旧captures/remote/cap_20261004_202456/meta.json失败，未动数据。源码/输入SHA、启动失败、初始回归失败及最终修复日志均在docs/evidence/2026-10-27_live_ground/，真实运行与最终优化版分开封存；55344文件非原子清单和定向改前副本保留。无Git写、板端/驱动网络/模型/HR-09动作。
- 下一步优先候选竞争与同源成员连续性、ID抖动造成证据丢失、处理尾部和实际显示延迟；物理地面、人体、真实跌倒GT及基线资格继续UNKNOWN。


## 2026-10-27 板端服务与Qt直连的后续计划

- 用户要求制定下一步计划，保存docs/BOARD_SERVICE_NEXT_PLAN.md：只读核实板端实际版本/发布者→共享核心接入ROS→对齐现有Foxglove/Qt契约→修候选/时间连续性与处理尾部→回归、最小发布准备及后续授权范围内实际验证。Qt只消费接口，服务独立于窗口生命周期。
- 明确新版链目前仅PC验证、板端实际版本尚UNKNOWN；不再以Qt启动本机桥作为产品交付。部署控制器同时管理capture/页面，发布准备需限定识别服务影响范围。可靠跌倒效果与接口可用分别记录，confirmed继续关闭。
- 本轮仅计划与本地源码只读核对，无runtime修改、无相关算法测试重跑、无板端访问/部署/启停/真实接流。来源SHA与检查范围在docs/evidence/2026-10-27_board_service_plan/SOURCE_INSPECTION.json；PROJECT_STATE已更新。


## 2026-10-27 2D→3D 人体算法打包到桌面（只含算法）

- 新增 `tools/make_human_2d3d_package.py`（可复现打包器）与 `tools/human_2d3d_package/`（唯一 API `human_2d3d.py`、CLI、合成场景、10 项单测、README、ALGORITHM）。打包器按 AST 求取 `core/` 闭包，逐字节复制 25 个算法模块 + `core/__init__.py` + `scripts/sensor_health.py` + `body_branches.py` + IFW192S 方位/仰角角表，写 `MANIFEST.json`（逐文件 SHA、仓库来源路径、grid SHA），固定 ZIP 元数据；输出目录/压缩包只创建不覆盖，生成后立即重校验。
- 桌面产物：`C:\Users\30680\Desktop\Human2D3D-1.0.0\`（39 文件、1,067,504 B）与 `Human2D3D-1.0.0.zip`（224,092 B，SHA-256 `5804be40429c7639d88b30176a680f283174eee71b94093f8d04985bed0c0de0`，临时目录与桌面两次构建字节相同）。包内不含会话/采集数据、网页、Qt、ROS 节点、模型权重、地面拟合或部署脚本；27 份算法文件与仓库对应文件逐字节相同（`PROVENANCE.json` 的 `mismatches` 为空）。
- 验证：桌面目录 `run.py check` rc=0（38 文件 SHA 全过、角表 grid SHA 匹配）、`run.py test` **10/10 OK**、`run.py demo --body` 54 帧 `ready` 并锁定 `g0_t0001`（1062 点、高度中位 0.9934 m、可见部位 torso/thigh_1/thigh_2/shin_1/shin_2）；桌面 ZIP 解压到临时目录后 check/test 均 rc=0；仓库 `pc_apps/range_fall` 既有 **68/68 OK**（33.734 s，本轮未改这些源码）。单测覆盖显式空场前缀与 3 帧出生窗口、2D 连通域→3D 来源行逐元素一致、原始字节输入、非法行/时刻/帧号拒绝、前缀不连续要求重绑、声明地面与非法平面、骨架/部位只消费锁定行、两次相同输入完全一致、`encode_points` 回环与严格 JSON。
- 角表事实：本机 IFW192S 每条 ring 的方位跨度不同（row0 ±77.2°、row100 ±63.8°），"按仰角中位数猜 ring" 不成立；`encode_points` 改为在整张角表按 (方位, 仰角) 找最近方向，合成点回环 ring 差异为 0。
- 证据 `docs/evidence/2026-10-27_human_2d3d_package/`：SUMMARY、CAPTURE、CHECK、TEST、DEMO.jsonl、DEMO_FRAMES、ZIP_ROUNDTRIP、REPO_TESTS、PACKAGE_SHA256、PROVENANCE。合成 demo 不是实测数据；无 GT，准确率/召回/误报/人体语义/物理有效性一律 UNKNOWN，confirmed 关闭；本轮无 Git 写、未改 `data/` 与 junction、无板端部署/启停、无采集/训练/下载/HR-09。

## 2026-10-27 界面 P1：会话列表单行+过滤 / 坐标轴+色带图例 / 就近错误 / 配平视图

- 改：会话列表单行（名称·次要编号·分析状态点，30 px、正文 12 px、省略 + tooltip/Accessible.name）+ 按名称/编号过滤（真实按键、清除、匹配数、无匹配提示），过滤不动已加载会话/播放位置；3D 右下角坐标轴（X/Y/Z，方向取相机 mapToViewport 实测投影）与工具行色带图例（范围读 CloudGeometry.colorRange：深度固定 0.10–8.00 m、高度逐帧 Z、反射逐帧强度并声明非置信度、缺强度回退单色）；视图按钮移入工具行；就近错误提示（按通道归因、控件旁显示、可单清、状态条红点、迟到/无主回包只计数）；「配平视图」按绑定地面法向旋转显示（--ground，只改显示）。
- 测：--tour-report **108 项 PASS**（过滤 real 按键/清除/无匹配/过滤后选择；图例范围与当前帧真实范围逐值相等；yaw=0/90 坐标轴方向；配平残差 25.4°→<0.01°）；新增 	est_alert.py（本机 mock 503 → 真实按钮 → 提示/红点/清除/持续失败/迟到回包）PASS；	est_camera.py 用现有会话 2/2 OK；Python 三套 825(skip1)/69/2 OK。全套在不设 FALL_SESSION 时 2 项 camera 因本机缺 cap_20261025_203653（既有缺口）失败；显式会话全套结果见证据日志。
- 修：自检辅助 lambda 在 -O2 下取到未初始化捕获值导致崩溃 → 改为无捕获自由函数；指示器不再逐帧 mapToViewport（只随相机姿态刷新）。一次 PowerShell 5.1 往返把 main.cpp 按 GBK 写回，89 处行尾字符被替换成 ?，按行修复后重编译（_damage.txt/_repair_main.py 留证）。
- 证据 docs/evidence/2026-10-27_ui_p1/（SUMMARY、before/after/配平截图 1360×749 同会话帧 3、tour/alert 报告、全套日志、改前/改后源码与二进制 SHA）。未 Git 写、未改 data/junction、未连板端/采集/部署；人体与跌倒有效性 UNKNOWN。

## 2026-10-27 界面 P1 审查（只读，无源码改动）
- 只读审查 P1 三份源码 + Program.cs + 两条用例 + 证据；重跑 `test_ui_tour.py`（OK，14.647 s，108 项、staleReplies=1、frameCopies=13）与 `test_alert.py`（OK，8.573 s，15 项、jointMutationRequests=4、directBoardCalls=0），日志在本轮证据目录。复核 `SOURCE_SHAS_AFTER.tsv` 12 个源码项与 AppService.dll 与磁盘逐字节相同；过滤/图例逐值核对/真实按钮/配平旋转/源会话 SHA 不变等 P1 主张成立；色带 PNG 实测为 depth 红→蓝、height viridis、intensity inferno；main.cpp/Main.qml 无 GBK 残留（合法 UTF-8、无 U+FFFD、无 CJK+`?`）。
- **高**：就近错误按"最后发出的命令"归因，回包不带 op（Program.cs:362/365/178），跨通道会记错；`inFlight>1` 把真实错误算成 staleReplies 丢掉——两次运行 staleReplies=1 正是唯一的 commandError；`poll:true` 只挡发送，轮询回包仍可结算真实命令、轮询失败的错误会落到别的通道；pendingReplies 无超时。**中**：每次点会话行都会给上个会话发一次注定被拒的 gtLoad（证据里 open→gtLoad(新)→gtLoad(旧)→commandError→gtLoad(新)，因 snapshot 对每条 status 都 NOTIFY，onSnapChanged 用旧 sid 反切）；「持续失败」在 15–30 s 重试节奏下不可达（state 的 now 是 Q_UNUSED）；缺强度时深度/高度被一起降级（Viewer.h:45 守卫对 mode1/2 不必要）；一次慢 ack 超时直接终止整个会话（Program.cs:387→446），不只是环境抖动。**中低**：深度图例写死 `0.10–8.00` 且用例断言字面量；坐标轴归一化丢投影长度，yaw=0 时 Y/Z 都是 (0,-1)、箭头与标签重叠（P1 报告 detail 自证），resize 后不刷新，Canvas 无断言；迟到/无主回包是直接调 C++ 方法；tour 硬编码会话/帧号；500-seek 无自动化守卫；stderr 闸门含平台层 `qt.qpa.mime` 故不稳。
- 建议顺序：协议回声 op/seq + 轮询回包不结算 + inFlight 不静默丢弃 + pending 超时；open 加 pendingOpenSid 守卫并断言 commandError 为空；ack 超时改为非致命；深度图例读常量、mode2/3 分开降级、持续失败改滑动窗口；指示器用投影长度并挂 resize。证据 docs/evidence/2026-10-27_ui_p1_review/（REVIEW.md + 两次重跑日志）。未改生产源码、未改 P0/P1 证据、未 Git 写、未连板端；人体/跌倒/配平物理有效性仍 UNKNOWN。

## 2026-10-27 界面 P1 审查问题修复（改生产源码，39 项全集首次全绿）
- 修 A（归因）：每条要回包的命令分配 `seq` 写进 JSON，服务端在**终止**回包回声（status/notice/openUrl/gt/gtSaved/deleteManifest/joint/error）；`jointStart/jointStop` 不再先发通用 status（否则先结算、真结果变重复）；`Viewer::noteReply` 按 `seq` 精确匹配，删除 `lastSentOp/pendingReplies/isTerminal` 和“inFlight>1 静默丢弃”；无主/重复 seq 只计 `staleReplies`，30 s 未回包计 `expiredCommands`；`poll:true` 不发 seq，轮询回包天然不结算也不误归因。
- 修 B（切会话）：`openSession` 记 `pendingOpenSid`，`onSnapChanged` 在快照仍是旧 sid 时不反切（6 s 超时放开）。日志从 `open→gtLoad(新)→gtLoad(旧)→commandError→gtLoad(新)` 变成 `open→gtLoad(新)`，整轮 `commandError` 为空。
- 修 C/D/E/F：持续失败改 30 s 滑动窗口（`state(now)` 真用 now）；`CloudGeometry::submit` 只有 mode 3 需要强度（缺强度只回退反射，深度/高度照常着色，mode 1 不再扫强度）；深度图例文案由 `colorRange.lo/hi` 拼出；坐标轴箭头按投影长度缩放（yaw=0 时 Y/Z 标签像素距离 0→14.97 px）、视口尺寸变化也刷新、加 `refreshCount`（整轮 13 次）。H：ack 超时 10 s→30 s，超时写 `ackTimeout`+`failed`（含 submission 与等待毫秒）再以 2 退出；ack 是“槽已读走”的唯一证据，所以没有改成“丢帧继续”（原审查建议按此修正）。
- 测：`console_v2/app` 全集（FALL_SESSION=cap_20261018_110029）**39 项 OK（skip 6，296.647 s）**；`--tour-report` **112/112 PASS**（新增 标签分离/刷新计数/高度无强度/深度无强度，深度文案改与 colorRange 逐值比），`staleReplies=0`、`expiredCommands=0`、`frameCopies=13=published`、`annotationCopies=1`；`--alert-report` **20/20 PASS**（新增 seq 跨通道/成功不清别通道/重复回包/超时命令/滑动窗口，`staleReplies=3` 全是合成探针、`expiredCommands=1`）；`test_ui_tour.py` 新增 commandError/stale/expired 三断言，stderr 闸门把 `qt.qpa.mime:` 平台消息与 QML 告警分开（全集这次一次过绿的直接原因之一）。
- 证据 docs/evidence/2026-10-27_ui_p1_review/：REVIEW.md（当时发现什么）、FIXES.md（逐条改法/验证/边界）、suite_after_fix.log、build_after_fix.log、after_fix_tour(.json/_run.json/.png/leveled)、after_fix_alert(.json/_run.json)、SOURCE_SHAS_AFTER_FIX.tsv（含路径与 mtime）。旧 P1 证据 docs/evidence/2026-10-27_ui_p1/ 只读保留，其 108 项/迟到回包语义/“缺强度回退单色”等说法以 FIXES.md 为准。未 commit、未连板端/采集/部署、未动 data/junction；人体/跌倒/配平物理有效性仍 UNKNOWN，P2 未开始。


## 2026-10-27 共享核心常驻ROS服务接入、Qt直连契约与识别专用发布准备

- 只读核实板端current/release/有效配置/进程/ROS发布者：仍为20261023T034639Z_60ce5d46旧single_target_node，规范话题单一旧发布者但两次XMLRPC快照无输入连接，缺新版SubscriptionGuard；新鲜驱动帧/算法结果/Qt现场交付UNKNOWN。getBusStats整型溢出、首次错误shell预检失败保留；未进行持续订阅或服务操作。
- 把PC识别封装收敛为core/RangeEngine、共享wire/PNG与range_site_ground；地面纯算法迁入core/ground_fit，PC路径保留兼容导入。新增range_service_node/launch/config，有界最新槽、单decode、独立预览/骨架、spawn地面拟合、当前epoch心跳、订阅沉默恢复和规范发布者冲突拒绝。Qt只连接/校验/显示；默认背景未声明、地面未加载，不自动学习有人场景。
- 修短空洞丢选择偏好和None误触发换人清历史：≤0.3s且关联无歧义保留同轨绑定，缺测不发布旧行/框、不累计时间；恢复分段、不跨空洞拟合下降。新增continuity字段的SHA审计兼容旧账本。v1/gap_v2默认不变；103帧现场竞争的成员成因仍UNKNOWN，未凭合成回归宣布修复。
- 最终ROS服务386/780整段1166帧，与同输入完成结果目标行/ID/高度/动态状态/PNG/v1逐帧0差异，780仍f689–707；PC含部位全帧另存。827核心（1 ROS跳过）、range64、工具26通过；旧地面30项29过/1缺历史会话失败，未动数据。Qt8项相关回归通过；最终板端标签专项两次窗口70帧、客户端前10帧、实例/背景保持，缺地面/有效离线地面/结束清理通过，6.1 Terra按用户授权只读核对最终6张界面图。
- 80帧交替配对封装对照0差异：旧同步P95 21.26ms，新主链13.44ms，含辅助21.17ms，仅PC调度证据；板端性能、真实15帧覆盖是否减少和实际GPU呈现延迟UNKNOWN。新增地面监视/各段/序列跳号/槽覆盖/心跳统计，未假称板端跑过新版。
- 识别专用包range_service_product.tar：release641d458580651ed4…、SHA50d1fe955ba39ecc5ecad58e766b9b6677c85650a169732c86cf182fae39b6fb，75payload文件和源完全一致、3.8语法/隔离入口/确定性通过。首次隔离包漏sensor_health依赖已修并加回归，失败保留。准备独立识别release/PID替换及旧识别新run回滚，不切共享current、不联动capture/页面。
- 证据docs/evidence/2026-10-27_board_range_service/（含55747文件非原子清单、277份改前副本、完整失败及最终源码/输入/配置/二进制SHA、原生截图）。PROJECT_STATE与BOARD_RANGE_SERVICE已更新。尚缺明确范围的设备迁移、当前背景/现场地面初始化、限时真实ROS/Foxglove/Qt/板端性能，以及竞争/人体/物理/跌倒GT；不宣称只剩设备启停。confirmed关闭，准确率/召回率UNKNOWN；无commit/push/reset/checkout/clean、部署、设备启停、真实采集、驱动网络、data/junction或模型动作。

- 封存发现Program.cs/main.cpp及Main.qml其它段有本会话未写的同期UI变化，保留当前内容，单列UI_CONCURRENT_CHANGES和diff；最终Qt实测二进制及源码/依赖另有SHA，不归属为本轮识别算法改动。


## 2026-10-27 Sol/Terra 联合继续开发：500ms时效、失效代际和拟合生命周期

- 用户明确指定6.1 Sol+6.1 Terra协作；子代理只读分析/独立计算/界面核验，主会话唯一写入。复现940ms旧源仍valid、推理中途失效后旧提示复活及Qt忽略500ms TTL；先加失败回归再修复，TTL_BEFORE保留2失败。
- 服务按结果源帧接收时钟过期，加失效revision拒绝跨代在途结果；Qt缓存/呈现按原始云接收时间和声明TTL，重复心跳不续命，身份改变立即清空。liveStatus补单调atMs以核对软件清空请求时序，不当作GPU呈现延迟。
- 拟合由可终止spawn进程承担，默认60s、异步收发完整报告、非阻塞poll；超时/半包/停机回收不堵主链。保存/子进程/加载失败隔离为地面不可用，错误可显示；加OS存活锁与ROS注册前检查，重复启动不先杀同名节点。算法和阈值不放宽。
- 核心834项（1ROS跳过）OK；ROS386/780全帧1166帧逐帧零差异；原生12项OK+4项截图专项OK。持续合成header/冻结低位XYZ的独立源跨两Qt窗口，已触发提示保持triggerFrame689与同一背景，无客户端时仍处理，Terra只读截图确认非确认跌倒文案。没有新现场运行结论。
- 新包release 54c3856352434373…，tar SHA 019fbeb8eb7be5bfb085c40a920306afbd26c19572782125314c7db1bf319786；76payload、源字节/3.8语法/隔离导入通过，识别专用替换/回滚重新绑定。56869文件非原子清单及246份改前副本，失败日志、当前源码/输入/配置/二进制SHA在docs/evidence/2026-10-27_board_service_joint/。初轮新测试的导入fixture、liveStatus缺时间戳失败保留；前轮缺历史地面数据不补写。
- PROJECT_STATE与BOARD_RANGE_SERVICE已更新。无板端部署/启停/新真实订阅/采集、Git写、驱动网络、data/junction或模型动作；真实竞争成因、现场适用性和板端性能仍待，confirmed关闭，人体/跌倒效果UNKNOWN。


## 2026-10-27 Sol/Terra 继续开发：回调竞争、拟合收尾、ACK与状态流诊断

- 唯一写入仍为主会话；Sol只读复现回调入槽逆序和拟合收尾阻塞，Terra只读定位Qt等ACK跳过时效清理并核对末态截图。新证据 `docs/evidence/2026-10-27_service_diagnostics/`；57516份非原子tracked+untracked源码SHA、176451条含忽略文件的树元数据、212份定向改前副本；未覆盖旧证据或其它Qt改动。
- 修复回调计数/接收时间与入槽不原子（50/51最终留下50）；拟合spawn、poll/reap、保存/文件验证移到单一后台完成线程，识别只安装内存结果；Qt在ACK等待期间仍清TTL/身份，不消费共享槽。无source心跳也校验协议/version/instance/能力；状态流沉默与原始流沉默分别显示UNKNOWN。修前1项回调、2项慢拟合、2项缺ACK、1项状态沉默失败均保留；首次旧源码fixture路径错误和诊断fixture跨session失败也保留。
- 增加默认关闭、固定上限的组件/成员摘要/关联/选择/历史诊断，覆盖header128条+overflow，以及输入/算法/发布各自时效。没有第二套算法、XYZ保存、阈值放宽或gap_v2采用。旧432/417逐帧账本重建15个未处理序号，仍不能凭缺失的阶段明细归因每次覆盖；103帧竞争和1次ID切换仍缺完整成员/关联及人体GT，最早错误阶段UNKNOWN。NEXT_WINDOW_MINIMUM给出下一次获授权短窗口字段，不代表已执行。
- Python核心838项（1 ROS环境跳过）、PC Range68项通过；诊断开启386/780整段1166帧源行/ID/高度/动态/v1/PNG与同输入完成结果零差异，780仍f689–707。可控压力覆盖后恢复不拼下降/低位持续时间，长缺口清目标并要求重绑。该PC耗时含并行本地测试/基线IO，不作为隔离性能提升或板端结论。
- 最终原生16项全过：ROS消息替身→Foxglove替身→真实Qt，缺/有效地面、坏协议/instance/能力、源/状态沉默、epoch/迟到结果、两窗口与持续已触发低位均覆盖。缺ACK原生探针先有2711目标点、高度0.8091167688和深度，末态target0/resultnull/depthnull；clear请求距发布约132/48ms，只是软件请求时序。新编译C#/Qt二进制SHA与截图/原生JSON已封存。真实ROS传输/板端运行仍未执行。
- 新包release `01bdd510aa64cbe84463b63195b0a286961e850c4779e4ebb2b9708ab406a96b`，tar SHA `05539bd8b5ad6490515a4b4dd609bf3ce1f0f0f68ef2e5a0883ed322070cfa81`；76payload与当前源码逐字节、Python3.8语法和隔离入口通过。仅准备识别单独迁移/旧识别回滚配置，不切共享current，不联动capture/页面/驱动，保留全部旧release。冷启动背景未声明/地面未加载保持具体原因；不换sid挪用旧环境。
- PROJECT_STATE/BOARD_RANGE_SERVICE已更新。本轮没有设备访问，旧60ce5d46/single_target_node仅历史引用；仍需获授权的识别迁移、当前空场/现场地面初始化和限时真实ROS/Foxglove/Qt/性能检查。103竞争归因/人体身份/物理地面/跌倒GT仍为证据缺口，不能声称只剩设备启停。不可中断磁盘IO可能超过daemon join，stop禁止交付安装；客户端状态沉默不能单独归咎服务或网络。confirmed关闭，准确率/召回率UNKNOWN。无Git写、部署/activate/启停、实际订阅采集、驱动网络、data/junction或模型动作。

- 2026-10-27 板端识别单独迁移 `01bdd510…`（PID 63877；不切共享 current），空场授权后建立背景并完成现场地面几何拟合；真实 Qt 直连/重开看到相同实例，141 对原始消息 SHA 一致，40 秒主槽新增覆盖 0。现场走动未执行，人体、物理地面和跌倒效果 UNKNOWN；较晚累计覆盖 53 次根因未明。修复实时配平同帧地面法向/版本接线，新包 `7530fd08…` 已暂存未激活（等待再次确认当前空场）。核心 838（1 跳过）、Qt TTL/地面版本错配测试、386/780 回放零差异；机器证据 `docs/evidence/2026-10-27_board_live_validation/`。

- 2026-10-27 用户再次确认空场后激活配平修复 release `7530fd08…`（PID 64149），背景和现场地面几何就绪；真实 Qt 两次限时探针实际点击配平，法向残差 0°，显示地面版本和“已配平”，另有早先人工窗口按钮灰色且原因未明。15 秒 142 对原始消息 SHA 一致，初始化 1 次覆盖，测量窗口无新增覆盖；Qt 重开后实例/背景/地面版本保持，活动报警历史未测。结果及截图 `docs/evidence/2026-10-27_board_live_validation/LEVEL_LABEL_LIVE_LEVEL.json`。人体走动、断流恢复和跌倒 GT 未测；nohup 不提供重启自恢复。

- 2026-10-27 离线查看 Qt 2D/3D：打开 780 帧会话 f500；该帧原始点 49123、目标 4242，实际源行经 ScanGrid/旋转映射到 2D mask 的对称差 0。386 会话 f103–371 共269帧有实测目标；780 f387–757 间 355 帧有实测目标、含短缺测，不能据此认定人体/身份 GT。depth 3项通过，386 帧同输入回放差异 0；证据 `docs/evidence/2026-10-27_offline_2d3d_review/`。未触碰板端。

- 2026-10-27 回放/USB 可用性：增加显式相机预览按钮和按地址配置的空闲本地预览服务；新增后台本地算法、空场声明、自动会话地面拟合及默认配平，按源 SHA 绑定、切会话不借旧地面。真实 Qt 双会话自动配平、前景同帧、算法开关通过；模拟相机4项、联合录制17项、核心20项、386帧回放同输入差异0。新结果跨应用重启未自动注册；实时相机与物理地面未测，持续自适应控制器尚未接运行链；证据 `docs/evidence/2026-10-27_offline_2d3d_review/`。

- 2026-10-27 核查新会话 `cap_20261023_221125`：数据126帧完整、无空场前缀，旧版能显示是整段p98非因果背景+单会话RANSAC；重跑仍112帧几何目标、23帧动态suspected、confirmed关闭。严格ROI地面原窗与3个替代窗均未过门。修复未注册状态与重启后按SHA恢复本地分析；新增明确标注非实时的离线对比入口，真实Qt流程及386恢复通过，session_compare 16项通过。证据 `docs/evidence/2026-10-27_unregistered_session/`；未访问板端。

## 2026-10-27 离线/在线收敛到同一 core 算法

- 用户要求“离线和在线只保留核心算法”。只读核对三条链：在线 `range_service_node → RangeService → RangeEngine → RangeRuntime`；Qt 离线分析 `local_replay_worker --kind analysis → runtime_replay → RangeRuntime`；旧整段对比 `local_replay_worker --kind offline-preview → session_compare` 自建 p98 前景、RANSAC 地面，再直接调用 `denoise/label_components/RangeTracker/lidar_candidates/FeatureExtractor/StanceBaselineCollector/FallStateMachine`，是第二套装配和第二套前景/地面模型。
- 新增 `core/range_offline.py`：整段逐射线 p98 背景 `QuantileBackground`（`non_causal=True`、`runtimeEligible=False`、只认更近回波）与离线平面 `fit_declared_plane`（`offline_only=True/runtime_eligible=False/physical_verified=False`）。`RangeRuntime` 新增 `background=`：必须显式 `non_causal`+声明+绑定匹配，且与 `empty_prefix_frames` 互斥；已声明的离线背景不因时间跳变被当成空场重学，来源/标定改变仍失效。`session_compare` 改为 `RangeRuntime` + 这两个声明输入，删掉自制前景/跟踪/特征/状态/基线装配，SUMMARY/GROUND 写明 `pipeline.module`、背景声明与非运行资格。
- 选型探针（同会话同地面，只换背景）：整段 p98 → 112 帧目标/单一 `g0_t0001`/23 帧 suspected；整段中位/MAD → 91 帧、4 个 track、0 suspected。因此离线非因果输入保留 p98 语义，但只作为声明输入，不进入在线引擎。
- 行为：126 帧与 10-27 收敛前 `legacy_preview` 逐帧（含状态 reason_codes）0 差异，112 目标/23 suspected 保持；与 10-23 旧证据仅 10 帧 `rs` 文本不同（core 演进，状态相同）。386 帧 prefix 模式 `config_sha256` 与改前相同，逐帧决策/规则 0 差异、软件 PASS；ROS 消息替身服务对新 `analysis.json` **386/386 0 差异**（目标行/ID/高度/状态/preview SHA/wire SHA/地面提示），证明离线与在线执行同一条 core。G2 仍 FAIL（P95 17.73ms，改前 17.91ms），非本轮引入。
- 测试：core **846 OK（1 skip）**、`pc_apps/range_fall` **69 OK**、`session_compare` **17 OK**；Qt worker `offline-preview` 路径产出 RESULT.json。证据 `docs/evidence/2026-10-27_offline_online_core_unify/`（AUDIT/PROBE/两份逐帧对照/logs/SHA）。未操作板端；人体身份/物理地面/跌倒真值 UNKNOWN，confirmed 关闭。`tools/range_experiment.py`（冻结运行的只读审计 oracle）、`pc_apps/human_core`（休眠 JS 研究引擎）和 `webui/` 不在本产品链，未改。

## 2026-10-28 下一次现场验证清单（计划，未执行）

- 用户同意把“下一次现场窗口采什么、怎么判”整理成清单。新增 `docs/BOARD_LIVE_WINDOW_CHECKLIST.md` 与机器计划 `docs/evidence/2026-10-28_board_live_window_plan/VALIDATION_PLAN.json`：60 秒动作脚本（空场 → 站立 10 s → 走动 → 蹲坐负例 → 空场 → 受保护躺下 ≥5 s → 起身 → 空场）、逐帧最小字段（服务身份/源 SHA/组件与轨/地面/高度/groundAlert v1/时效/Qt 同源）、P0–P5 判定门和“不能得出的结论”。
- 判定口径把“几何锁定”和“跌倒检测”分开：P2 只说明本窗口同一 track 连续，P4 只说明 v1 低位提示与躺倒区间一致；`confirmed` 仍关闭，准确率/召回率、人体身份、物理地面仍 UNKNOWN。垫子/保护员须在背景初始化时已存在；开窗后才引入的静态物单独标记，不计入 P2 成败。
- 字段与上一轮 `NEXT_WINDOW_MINIMUM.json` 的 9 组逐项对齐；边界仍为 32 组件/8 行样例/32 轨/每轨 8 边/128 覆盖 header，不落原始云。
- 本轮只写计划：无设备访问、无部署/启停、无采集、无生产代码改动。`check_plan.py` 结构校验 26 项全过（相位 0–60 连续、字段全覆盖、授权全关、无越界结论），产物 `PLAN_CHECK.json`；未跑算法回归，因为没有改算法/运行时。
- 执行前仍需用户给出现场时间与人员，并在隔离目录确认只读探针与当前 `range_recognition/1` 字段匹配（仓库内 `board_probe.py` 只服务旧 `range_image` 节点，不能直接用）。

## 2026-10-28 Qt 成熟度检查（只读；当前源码未全绿）

- 用户问 Qt 是否成熟。按正常入口 `console_v2/app_dev.py build` 重建后跑当前源码全集：**51 项、6 失败、6 跳过、369.802 s**。上一轮 16:25 的 39 项 OK/skip 6 对应的是旧源码；22:48–23:16 `Main.qml`/`main.cpp`/`Program.cs`/`LiveSource.cs` 等仍有改动，旧结论不能沿用。
- 失败：5 项 native 用例因 `qrc:/Main.qml:472:5: Unable to assign [undefined] to bool` 失败；`test_ui_tour` 112 项中 11 项失败（配平 6 项、过滤清除 1 项、analysis badge/status/axis 4 项）。`levelAvailable` 在 `ground.normal` 缺失时返回 `undefined`，旧快照那行是 `ground.available === true`；本轮未改代码。tour 的 6 项配平失败是自动配平与旧断言不一致（`applyOfflineGround` 置 `levelView=true`），不是无地面或功能不可用。
- 过程失败保留：第一次 `FALL_SESSION` 只写 sid 导致会话路径错误；第二次用 16:18 的旧 DLL 导致 9 项 `Bad ACK fault option`；重建后降到 6 项。两次日志都在证据目录。
- 结论：功能覆盖已经宽，但当前版本不能称“成熟/可交付”；先修 QML 绑定与过滤清除，再重跑 tour 和全集。证据 `docs/evidence/2026-10-28_qt_maturity_check/`（SUMMARY、两次 suite 日志、build、TOUR_FAILURES、SHA）。
- 未连板端、未部署/启停/采集、未改源码/数据；跳过项仍是既有 fixture 缺口。

## 2026-10-28 配平修复、Qt 全绿与实时低位链路

- 用户要求“解决问题，明天要能实时倒地识别”。先修 `Main.qml:472`：`levelAvailable` 外层加 `!!(...)`，无地面时返回 `false`，消除 `Unable to assign [undefined] to bool`；5 个 native stderr 用例恢复。tour 适配回放自动配平（`applyOfflineGround` 置 `levelView=true`）：先验证自动配平/残差≈0，再手动关/开/再关；坐标轴检查移到配平关闭；`--no-restore-local` 让巡检不受本机可恢复分析影响；过滤清除后 `QTest::qWait(80)`；坐标轴刷新阈值 18→80（整轮实测 53，逐帧会 ≥386）。`test_ui_tour.py` 检查键名同步。
- 结果：`console_v2/app` 全集 **51 项 OK、skip 6、365.489 s**；`--tour-report` **115/115 PASS**；构建通过。修复过程未再出现 GBK 写回，`test_ui_tour.py` 从 19:00 封存副本恢复后按 UTF-8 打补丁。
- 板端只读复核（**未重启/部署**）：PID 4166027，release `7530fd08…`，实例 `live_range_808475d4…`，background ready（`explicit_empty_prefix_50`），ground available/SHA `4b0c1700…`，输入 receiving（received 101438/processed 101436，overwritten 1）。当前目标 `g35_t0155` 20 源行、高度 1.19 m、低位提示 inactive，更像静止小物体；明天开窗前需确认/移出，否则可能先锁它。
- 新增 [REALTIME_LOW_POSTURE_RUNBOOK.md](REALTIME_LOW_POSTURE_RUNBOOK.md)：开窗前只读检查、现场布置、Qt 启动、40 秒动作、判定口径、故障排查、重启后空场/地面重绑。证据 `docs/evidence/2026-10-28_qt_live_alert_fix/`（suite/tour 日志、tour 截图、board state/shape、探针、SHA）。
- 边界：没有真人现场测试；`ground_alert_v1` 仍是 ≤0.7 m/1.5 s 低位提示，蹲/坐可触发，`confirmed` 关闭，准确率/召回率 UNKNOWN；板端 nohup 无重启自恢复，重启后背景丢失。

- 2026-10-28 用户要求开启真人实时识别：增量构建并打开隔离 Qt 实时窗口，连接 ws://192.168.31.58:8765；真实窗口约9.7fps且显示目标框，与板端同实例 live_range_808475d4。启动前背景ready/地面available，窗口检查时当前目标地面支撑失败、高度UNKNOWN、低位判断不可用，不能宣称现场低位识别就绪。未重启/部署/重新学习背景或录制；无源码修改，未重跑单测，本轮执行真实连接检查。启动日志 console_v2/.tools/app-evidence/b15df3ca416b4ab2a6f4dea487257e4d；状态证据 docs/evidence/2026-10-28_live_open_085733。

## 2026-10-28 自动配平窗口修复与 2D 深度图保留

- 用户问“现在为什么都配平不了，以前纯 3D 算法可以”并补充“2D 指深度图”。自动配平入口（`local_replay_worker --kind ground` → `ablate.py fit-ground`）逐段跑 `data/sessions` 12 段：修复前仅 4 段成功。根因是拟合窗口固定前 50 帧（fit 0..48、留出 50/75/99）且种子只看第 0 帧；前段有人时留出帧整段被遮挡，48 帧会话还会索引越界并被 `Program.cs` 的“至少 100 帧”挡住。旧回放工作台用整段帧，所以旧“纯 3D”能出结果。
- 改：`fit-ground` 按 `head`（旧口径）→ `spread`（全段 ≤50 帧）→ `wide`（全段 ≤120 帧）依次尝试，同一 `floor_roi` v3、TLS/SVD/RANSAC 一致性、留出质量门均不放宽；种子改为拟合点集子样本 RANSAC；失败时在 `GROUND_FIT.json.attempts` 逐窗口记录原因；`Program.cs` 最低帧数 100→4；新增 `pc_apps/range_fall/test_ground_window.py` 5 项回归。结果 4/12→9/12 成功（386/780/082623/082717/083044/083120/083254/224823/221125）；082829/082906/083218 仍被一致性/留出/地面域质量门拒绝，未放宽阈值。
- 2D 深度图实测（08:57 板端直连 run.json）：1054 个发布帧里带深度的只有 309（29%），深度图更新间隔中位 210 ms（约 4.8 Hz），>500 ms 82 次、>1 s 15 次；识别状态有 44 次 stale、44 次 history invalidated。板端 `previewExpired` 仅 70/89503，说明预览基本算出来了，问题在带预览的状态没在展示前送达；Qt 又在缺预览时清空深度图，于是闪空。
- 改（Qt，重建生效）：`main.cpp` 在缺同帧预览时保留上一张深度图，记录来源帧/旋转版本并新增 `depthStale`；切会话/身份变化/清目标时清空。`Main.qml` 用 `depthRotation` 旋转旧图，`depthStale` 时隐藏骨架叠层并用黄字标“深度图来自帧 N · 当前帧缺同帧距离图”，不再闪空。
- 继续：新增“同帧晚到预览只刷新深度图”通路——帧已展示但预览在 500 ms TTL 内才到时，服务发 `type=depth`（同 submission），Qt 只替换深度图、不碰目标/3D/骨架；同时修 `LiveSource` 缺 `preview` 键时抛 `The given key was not present` 导致整条状态流断开的问题（缺键按空预览处理）。新增 `test_service_ttl` 的 `depth-late` 场景：无预览结果先展示、同帧预览晚到，断言 `depthUpdate` 且不断流。
- 改（板端代码，未部署）：`RangeService.updated` 事件 + `range_service_node` 用 `updated.wait(.05)` 发布，预览一补进状态就立即发出；本地 386 对照 20 Hz 轮询覆盖 99.1% vs 事件 100%。需要新 release/部署才对现场生效。
- 验证：`pc_apps/range_fall` 74 项 OK、新增窗口回归 5 项 OK；核心 848 项 OK（skip 1）；`test_service_ttl.py` 11 项 OK、`test_ui_tour.py` 1 项 OK、`test_board_service.py` 1 项 OK。`test_local_bridge.py` 单独复跑 5 项中 2 项失败（heightMedianM 为空、published 24<25），属该用例本身 30 帧/2.4 s 的时隙边界；未改其负载条件，未把它算作通过。完整 Qt 全集在并发负载下仍有既有 flaky，未重跑全绿。
- 边界：地面仍是离线几何候选（physical_verified=false）；深度图保留只是显示层，旧图帧号会明示且不叠骨架，不代表当前帧识别有效；未连板端/部署/采集，未改 data 或 junction。证据 `docs/evidence/2026-10-28_ground_fit_window/`、`docs/evidence/2026-10-28_depth_preview_delivery/`。

## 2026-10-28 Qt 与旧 Web 3D 同会话离线对照

- `cap_20261018_110029` 全 386 帧：Qt 当前离线 worker 使用声明 50 帧空场及已绑定地面；旧 `human_replay` 自动 3D 管线逐帧运行，显式应用同一地面平面的 R/t，整段静态背景为非因果。两端输入 SHA 与对照脚本、逐帧账本见 `docs/evidence/2026-10-28_qt_web_3d_compare/`。
- Qt 269 帧目标/高度，1 条 ID，ground_alert_v1 激活 0 帧；旧 Web 有簇 386 帧、几何候选 247 帧，形状标签 94 帧，事件 12 帧。Qt 目标帧最近 Web 簇中心均在 0.5m 内（269/269，中位 0.058m）；中心接近不证明目标或人体身份相同。旧 Web 事件语义与 Qt 低位提示不同，不能用数量评优；人体及跌倒 GT、物理地面 UNKNOWN。
- 完整离线回放与逐帧索引校验成功；`test_runtime_replay.py` 14 项、`human_pipe_lib.test.js` 38 项通过。调用实际算法库和 Qt worker，未运行两套 UI、未访问板端、未采集或改生产代码。

- 2026-10-28 按用户要求打开同一会话的 Qt 与旧 Web：本地只读查看服务提供已绑定的相同地面变换并禁止 POST；Web 载入 386 帧、自动管线已启用，Qt 以刚才生成的 analysis.json 启动。没有访问板端或改数据。算法回放与相关测试沿用上一条记录。

## 2026-10-28 Qt 配平目标框与状态说明

- 目标框原在传感器系轴对齐后整体旋转，配平后倾斜。现用同帧实测目标点计算配平世界坐标轴对齐框；切换地面方向立即重算、空目标清框，未配平仍用原框；点集、跟踪、算法输出未改。
- 状态显示“动作未判定”，目标实测明确显示“目标已跟踪”，将 baseline_not_ready 解释为“站立基线未建立，动作状态未知”。`RangeRuntime` 仍未供站立基线，未假称动作直立或人体已确认；状态与阈值未改。
- 构建成功；目标点旋转包围、旋转重算和清空原生测试通过；界面巡检首次因过滤清除结果 10/12 失败，单独复跑通过；386 帧逐帧 XYZ/目标点一致性回放测试通过。真实 Qt 会话 184 帧显示配平框与清晰状态。证据 `docs/evidence/2026-10-28_qt_box_state_fix/`；人体/跌倒 GT、物理地面 UNKNOWN，无板端访问。

## 2026-10-28 实时配平状态链诊断（未完成修复）

- 排查确认：`RangeService.snapshot` 超时将 `local_range` 清空；`RangeEngine.invalid` 不带地面绑定；Qt `Main.qml` 只从当前 `result.groundStatus` 取得地面；`LiveSource` 无源状态清目标，故识别失效会连带丢失配平显示。旧失效心跳没有独立地面 SHA，不能安全推断绑定仍有效。尚未修改生产代码，修复未完成。
- 历史 08:57 快照显示实例 `live_range_808475d422244c9c8b619417786fce04` 的地面 `current_patch_support`、SHA `4b0c1700d43bf1599695f2e433f1ce53f158bcc522ccfd4d4bff38264afdd3c9`；不是截图失效同期状态，现场根因仍 UNKNOWN。原实测 44 次识别 stale、44 次 history invalidated；无同输入预览开关板端对照，不能断言 2D 是超时原因。
- `test_range_service.py` 18 项通过；386 帧标准离线回放完成且消费序列/复跑差异为空，G1b/G1c/G2 仍 FAIL。板端替身对照尝试两次因参考 analysis 缺 `groundAlert` 报 KeyError，保留日志，不能计为通过。证据 `docs/evidence/2026-10-28_live_ground_contract_diagnosis/`；未访问设备、部署或重新拟合。
- 后续：设计独立地面绑定状态及版本/实例校验，客户端单独维护并在不可验证或绑定变化时清除；补超时/换 SHA/换会话原生回归，再做同输入预览开关耗时对照。

## 2026-10-28 实时配平与识别状态解耦

- 服务新增 `independent_ground_binding` 能力和独立地面状态，保留绑定地面的 SHA / 显示平面，`supportCurrent` 标明检查是否仍对应当前源。识别 TTL 或处理中途失效继续清目标、源行、高度、报警；配平只保留显示旋转，不把旧支撑检查当当前测量。地面拟合安装/失败前清绑定；源或标定失效、停止时撤销。Qt 验证服务实例、会话、同源云 TTL、法向、偏移和 SHA；换 SHA 等待新同源云，较旧源不能恢复旧平面，同 SHA 异常改变平面拒绝；状态流沉默清绑定。跟踪 epoch 变化不误清相同地面，旧协议在无效识别时仍保守清除。
- 增加主计算/源龄 >500ms 和预览计算/超时/被后续结果替换计数，保留已有 previewExpired；结果过期仍保留阶段耗时用于诊断。386 帧本机无节拍双模式对照：目标源行、轨迹、高度、动作状态、低位提示和姿态逐帧 0 差异；预览关/开主计算 P95 31/62ms，预览 P95 39.5ms、最大 58.6ms，主计算及预览 >500ms 均 0；开启后预览 385 次计算、328 次成功装入状态、57 次被新结果替换、0 次 TTL 超时、1 次槽覆盖。这是PC压力回放而非板端/网络/显示性能，也不能解释截图同期状态或证明2D是现场超时根因。
- 验证：核心 850 项通过（1 跳过，完整套件在最后添加 supportCurrent 前；最终服务专项 20 项和节点专项 3 项通过），最终 Qt 原生实时套件 18 项通过，涵盖失效保留、会话/SHA变化、同SHA篡改、旧帧复活、epoch和状态流沉默。全套早期有测试替身缺新接口、一次并发 Qt 异常及一次模拟初帧 TTL 窗口抖动；原日志保留，修替身/让窗口启动稳定后复跑。真实窗口截图见 `retained_final_LIVE_LEVEL.png`。
- 本地识别候选包 `range_service_candidate.tar`，release `12c7a0c1e3379752f840f4a2bc51af37bf14c1adfdaa9e72b6e58ab30dd0ddd0`，tar SHA `404fe3de9e491463f0c76b1c3cd10112bead5e4c7482cd36ed9382549c7a64ab`；77 payload 与当前源码一致、Python3.8语法与隔离导入通过。无设备访问、部署、采集、重拟合或数据修改；证据 `docs/evidence/2026-10-28_live_ground_decoupling/`。
- 人体检测和跌倒识别仍未达到上线：RangeRuntime 当前传 `baseline=None`，confirmed关闭，当前低位提示不是跌倒确认；人体/跌倒 GT、当前板端性能和物理有效性 UNKNOWN。继续评估现有自动基线与跟踪绑定，使用同输入离线对照和有真值的数据验证，不将配平修复视为完成总体目标。

## 2026-10-28 阶段进度文档与实时开发暂停

- 按用户要求整理 `docs/STAGE_PROGRESS_2026-10-28.md`，列出联合录制、Qt、共享核心、配平/深度图修复的完成范围，以及人体目标、站立基线、跌倒真值、板端版本和运行稳定性缺口；引用已有日志及机器产物，明确历史真机成功不代表设备当前状态。
- 实时开发保持暂停；本轮只核对源码、已有证据和文档链接，没有改运行代码、重跑算法测试/回放、访问设备、部署或采集。文中测试数量均为历史对应运行结果，不作本轮新测试声明。文档检查结果放 `docs/evidence/2026-10-28_stage_progress_doc/`。

## 2026-10-28 四会话 demo 预处理诊断（未完成）

- 确认鞋带/弯腰为 `cap_20261028_jixiedaiwanyao`。四段 169/241/230/265 帧现有 `session_compare.py` 完整离线回放，整段分位背景非因果、简化 RANSAC 地面仅为未经物理验证的显示候选；逐帧与输入 SHA、相机抽样图在 `docs/evidence/2026-10-28_demo_four_sessions/`。
- 后倒/前倒/慢倒/鞋带弯腰依次有目标候选 134/238/190/233 帧，疑似状态 0/40/0/0 帧；候选不是人体真值、状态不是确认跌倒。后倒末帧相机中人体已离开而仍有候选，慢倒切换多个轨迹。人体框、骨架/重心、2D 到 3D、慢倒告警和完整逐帧人工核对均未完成，不可作为企业演示成品；人体和跌倒准确率 UNKNOWN。
- 独立严格地面拟合后倒/前倒/慢倒均未通过质量门；鞋带弯腰拟合运行状态见本目录日志。`test_session_compare.py` 17 项通过；无设备访问、部署、采集或数据修改。
- 补充：鞋带/弯腰严格配平也返回 INFEASIBLE（三个窗口均缺满足空间分布条件的干净地面支持），因此四段严格配平均未通过。

## 2026-10-28 四会话简洁多视角离线页面

- 在 `pc_apps/demo_viewer/` 基于上一轮现成逐帧输出生成四会话导航、立体/正面/侧面/俯视视角、状态和报警条及相机近邻；简化文案，实际规则状态与点云候选不变。页面依赖本工作树 `docs/evidence/2026-10-28_demo_four_sessions/`，不是独立发布包。
- 逐帧浏览器逻辑核验 169/241/230/265 帧状态、报警及对应相机文件；旧页面 7 项测试通过；实际浏览器前倒跳转第153帧显示跌倒嫌疑与相机帧169，俯视按钮可点击。源码、输入 SHA 与日志在 `docs/evidence/2026-10-28_demo_multiview/`。
- 几何候选、非因果背景、未经物理验证地面及最近时间相机配对的边界仍在；后倒和慢倒没有跌倒提示，目标误选仍存在。2D 距离图到 3D、骨架、重心与逐帧人工标注仍未完成，不能称为完整企业演示或有效跌倒检测。未改数据、设备或报警算法。

## 2026-10-28 四会话连续视频

- 新增 `pc_apps/demo_viewer/render_video.py`，使用上一轮完整离线账本和相机近邻逐帧合成正面、侧面点云和相机同屏；四会话顺序连续，简短显示场景、实际状态与警告，点云为已有抽样的几何候选。`人体跌倒四会话演示_最终.mp4` 为 H.264、1440×810、20 fps、94.1 秒；169/241/230/265 个源帧全部保留，重复帧按原时间近似，未加入音乐。
- 最终渲染与完整视频解码通过，检查输出 1882 帧、四段顺序、相机文件与状态；报警画面抽帧确认文字完整。首个导出报警符号缺字形，保留首版和失败记录，最终版改为文字。回放账本、逐段逐帧映射、SHA、测试、视频元数据和截图位于 `docs/evidence/2026-10-28_demo_video_final/`。
- 仍使用非因果背景和未验证地面；后倒/慢倒未触发报警，不能据成片声称跌倒识别可靠；人体语义、骨架/重心及2D到3D展示未完成。摄像机按接收时间近邻，非硬同步/外参标定。未改原始数据和设备。

## 2026-10-28 四会话完整点云与两阶段离线演示

- 新增独立演示比较规则：同一轨连续实测、地面相对高度中位≤0.5m、顶部≤0.7m、水平跨度≥0.5m，连续1.5s为疑似、3s为规则确认；缺测、换轨或时序不连续重置，并保留原状态机疑似输出。只在离线视频内使用，未修改生产算法；这是按四段开发数据调的几何提示，并非经验证的真实跌倒确认，坐地或误选仍可能误报。完整逐帧账本及 SHA 在 `docs/evidence/2026-10-28_demo_two_stage/`。
- 后倒首疑似帧83/规则确认97，前倒153/173，慢倒139/153，系鞋带与弯腰均无；不是独立测试集，准确率/召回率 UNKNOWN。对照既有规则前倒40帧疑似被保留。原有目标误选、非因果背景和地面物理有效性边界未解决。
- 最终 `pc_apps/demo_viewer/跌倒演示_完整点云_两阶段报警.mp4` 含3D完整场景、正侧视点云和相机，全部905源帧、20fps、约94.2s；3D视图逐帧读取原始全部有限XYZ，屏幕裁切中位约98%，二维像素重合不可辨，正侧视仍是既有抽样。相机按接收时刻近邻。音频只在规则报警期间合成提示声；去掉视频中的“地面未验证”文案，既有严格地面拟合失败的事实及本次平面未物理验证不变。
- 四项演示测试和既有地面提示15项通过，完整MP4视频音频解码成功，确认截帧、状态/音频逐帧核对与SHA已保存；此前两个中间视频作为本轮产物保留。未改原始数据/设备或部署。

## 2026-10-28 演示视频目标标签、坐标与状态

- 完整点云视频在目标框旁增加“人体候选”与轨迹编号，在画面底部给当前目标配平系 X/Y 中位坐标（厘米量化）和地面相对高度中位 Z（米）；无测量不沿用旧坐标。候选点集可能误选，坐标不是人体质心。规则只对已有 unknown 状态额外标示满足高度和包围盒条件的“站立候选”，原下降/低位/恢复和两级报警不变。
- 四会话905帧逐帧核对坐标计算、状态显示及与前版输入点数、目标轨迹、相机、报警、时序零差异；候选位置帧为134/238/190/233。Python 5项测试通过，最终 H.264/AAC 完整解码通过，截帧、SHA、账本和检查见 `docs/evidence/2026-10-28_demo_labels/`。
- 输出 `pc_apps/demo_viewer/人体标签_坐标_状态演示.mp4`。人体身份、站立候选和物理地面仍未验证，存在空场误选，坐标不等于人体真实位置真值；未改生产算法、设备或原始数据。

## 2026-10-28 人体识别工程路线调研与尺度先验摸底

- 用户问"人体与跌倒之外，工程领域 3D 激光雷达怎么实现人体体素特征、2D 距离图又怎么做"，并要检索方案。逐段读完现有链路（`range_image`/`range_background`/`range_components`/`range_tracker`/`lidar_candidates`/`features`/`fall_state`/`range_posture`/`range_shape`/`baseline`/`range_runtime`），确认缺口不是"体素化"（`support_cells` 已按 0.1 m 体素做支撑、`range_shape` 已有像素级描述子、`rebuild_candidate` 已有高度分位 + PCA），而是人体相容性判别、目标选择先验、`baseline=None` 硬编码和事件级证据链。
- 检索并写入 [HUMAN_ID_ENGINEERING_PLAN.md](human_fall/HUMAN_ID_ENGINEERING_PLAN.md)：三条可落地路线（几何先验+浅层分类器 / 体素·柱体深度网络 / 距离图语义分割）的对比与代价，14 个可实现的体素特征定义，2D 距离图的投影、通道、距离补偿与分辨率上限，以及 A–E 五步落地方案（人体相容描述子 → 选择门 → 基线接入 → 跌倒证据链 → 需授权的学习路线）和对应改动文件、测试、验收。
- 标定表实测：`192×256`，方位 0.6°/列、俯仰逐列 0.4° 步进，方位视场 154.4°、俯仰总跨度 95.6°；据此估算 IFW192S 在 4–6 m 内可做人体形态判别，8 m 仅约 6 列×30 行，不能当作"8 m 也能识别人"。
- 用四段开发会话的既有逐帧账本做只读摸底（`docs/evidence/2026-10-28_human_prior_feasibility/`，`analyze.py` 仅 stdlib、确定性）：当前锁定目标里 12–30% 与任何人体姿态都不相容（慢倒 27 帧、系鞋带弯腰 38 帧为碎片）；跌倒低位帧主轴垂直度可到 0.00–0.12 而弯腰低位帧最低 0.46（多数 ≥0.9）；跌倒段水平跨度 1.28–1.53 m，弯腰段最大 0.88 m。→ 跌倒判据应是"垂直度崩塌 + 跨度拉长 + 快速下降 + 持续"的合取，高度只是其中一项；单一尺度门会把躺倒的人判掉，必须用"站立∪坐蹲∪躺倒"的相容集合。
- 边界：账本是几何候选包围盒，不是人体真值；本轮阈值是宽区间初值，未在独立数据复核；没有改任何生产代码、未跑算法测试/回放、未连设备、未部署、未采集、未训练/下模型。准确率、召回率、误报率仍 UNKNOWN。

## 2026-10-28 单人几何相容性描述子与单人选择策略

- 用户要求"基于现有实现继续开发算法、尽量效果好、先只做单人"。新增 `core/human_prior.py`（纯 NumPy、Py3.8、确定性）：地面系体素描述子（高度/水平跨度/足迹面积/占用率/分层直方图/层宽/接地占比/PCA 四量/距离补偿密度）+ 姿态相容分档（`standing_geometry`/`sitting_geometry`/`lying_geometry`/`fragment`/`planar_structure`/`not_compatible`/`unknown`，前三种 compatible），加 `quick_screen`（无 PCA 的组件预筛）与 `choose_single`（单人排他 + 迟滞 + 无人形目标时不锁）。输出固定带 `semantic/identity='UNKNOWN'` 与 `definition='anthropometric_geometry_only_not_identity'`，不输出概率。
- `core/range_tracker.py` 集成三个开关写进 `SETTINGS`（进 `config_sha256`）：`human_prior_enabled=True`（默认影子，每条实测轨迹附 `human_prior` 块与 `single_person_policy`，不改变选择）、`single_person_lock=False`、`drop_fragment_candidates=False`；输出新增 `single_person_policy`、`dropped_fragments`。默认行为与改动前逐帧一致。
- 新增 `pc_apps/range_fall/human_prior_probe.py`：与 `session_compare.py` 同一输入（同标定表/同非因果背景/同离线地面/同 `RangeRuntime`），逐帧对**所有实测轨迹**跑 `describe` 并用 `choose_single` 复算，与跟踪器实际目标对比。四段 905 帧：**632/795（79.5%）目标帧与人形相容，163 帧（20.5%）与任何人体姿态都不相容**（主导形态是约 1.1 m 高、0.06–0.19 m 宽的竖直细条，悬空且位置固定 → 静止场景物；以及弯腰时的腿/躯干碎片）。策略在这 163 帧里 122 帧改为不锁、41 帧改选另一条相容轨迹；632 个相容帧里 630 帧与跟踪器一致；帧内"≥2 条相容轨迹"只有 11 帧。
- 阈值经三轮同输入对照（v1/v2/v3 产物全部保留）：v1 `lying_top≤0.75` 把 `houdao` 第 116 帧真人躺倒（top 0.7515、跨度 0.91、垂直度 0.24）判掉；v2 收紧接地门又误拒"腿被家具挡住"的坐姿（houdao 坐姿 21→15、qiandao 30→15）；v3 改为接地门 1.0/0.7/0.4、`lying_top≤0.85` 且接受"跨度或低垂直度"，相容帧 620→632。
- 验证：`test_human_prior.py` 18 项通过（站立圆柱/躺倒条/坐姿/小物体/墙/悬空板/边界 top 0.75/竖条/未绑定地面/点数不足/非法行/确定性/quick_screen/选择策略 5 例）；核心完整套件 **868 项 OK（skip 1）**。开销本机 `describe`≈3.5 ms/轨迹（1200 点）、`quick_screen`≈0.7 ms/组件，影子模式每帧 +4–10 ms，板端需实测。
- 未做：姿态状态机分层与最短驻留、站立基线接线（`range_runtime` 仍 `baseline=None`）、多人关联、板端部署。`single_person_lock` 默认仍关闭：打开会把 20.5% 当前目标变成无目标，需先用带真值片段确认 `houdao` 第 55/158–168 帧这类"遮挡下的真人"不是误拒。人体身份、跌倒真值、准确率/召回率 UNKNOWN。
- 文档 `docs/human_fall/SINGLE_PERSON_ALGORITHM.md`；证据 `docs/evidence/2026-10-28_single_person_prior/`（逐帧 `PROBE.json`、`AGGREGATE.json`、v1/v2/v3 对照、`SUMMARY.md`、SHA256）。未连设备、未部署、未采集、未训练/下模型，未改数据与 junction。

## 2026-10-28 人体检测亮色演示视频

- 新增 `pc_apps/demo_viewer/render_enterprise.py`，复用上一轮逐帧链路，展示标题改为“人体检测”，固定标签“人体”，去掉跟踪ID，使用暖白和陶土色轻量布局。仍在缺测时隐藏框/位置，不跨缺测复制旧目标；视频保留离线和规则确认说明。
- 最终 `pc_apps/demo_viewer/人体检测_亮色展示.mp4`，H.264/AAC 1600×900、20fps、94.2s，四段 905 帧账本与前版逐字段一致（包括原轨迹、位置、报警、相机及点数），6项测试通过，完整视频音频解码通过；截图、SHA和机器结果 `docs/evidence/2026-10-28_demo_light/`。
- 标签固定仅改变显示文字，原跟踪仍切轨且可误选背景，不代表身份已稳定或人体语义已验证。原非因果背景、离线告警、物理地面与泛化限制不变；未修改数据或设备。

## 2026-10-28 展示视频精简文案

- 按用户要求从亮色视频移除底部“离线演示 · 目标可能误选 · 确认为规则判定”，保留状态、坐标和规则确认报警；同步删除生成脚本该行。新视频 `pc_apps/demo_viewer/人体检测_简洁展示.mp4` 基于既有成片局部遮盖并重编码，音频流复制。
- 6项演示测试、视频音频完整解码通过；首版与新版音频流 MD5 一致，检查截图和 SHA 见 `docs/evidence/2026-10-28_demo_clean/`。此为显示层变更，既有误选、离线规则确认和未验证的人体/物理有效性限制不变，未改数据与设备。

## 2026-10-28 单人跌倒链连续性与账本回归

- 修复 runtime 推理 SHA 统一旧 15 键，并在读取端严格兼容独立 W2 回放的完整跟踪字段哈希；旧规则与轨迹绑定仍校验。修复缺 ID 的特征重置误清 episode、有 ID 的 held 超时、姿态转移单独触发 confirmed，以及探针切换计数和分析导出姿态集合。真实会话测试改核对逐帧与摘要，不把无 GT 片段的报警写成必然。
- 最终 `-W error`：核心 884 OK（skip 1）、capture 69、calibration 2、range_fall 10 脚本 74 项 OK；额外工具套件 26 项中 1 项错误，旧合成夹具缺 `frame.binding`，不在本轮允许写入范围。四段默认/带锁完整离线回放与初跑诊断均保留，`docs/evidence/2026-10-28_episode_continuity/` 有 SUMMARY、AGGREGATE、逐帧 probe、日志和 SHA。
- 默认四段疑似帧旧→新：后倒 0→33（8.708 s）、前倒 40→0、慢倒 0→0、弯腰 0→0；慢倒带锁 43 帧（12.543 s）。后倒 65–67 缺口不再误清，慢倒 104 帧仍选中几何碎片，前倒因跨度不足 0.6 m 未进入躺姿；弯腰仍有最长 45 帧连续 recovering。目标锁定有漏选风险，默认保持 False，confirmed 关闭；上述预测锚点未全部达成，不能称行为收尾完成。
- 基线 ready 默认前倒 162、慢倒 35 帧，后倒/弯腰 0 帧，后两段无法验证 ready 基线。四段为开发集、无人体/跌倒 GT，准确率/召回率/误报率 UNKNOWN；非因果背景和离线地面不可外推板端。未部署、未测板端性能、未验证多人或在线因果背景，未采集、训练、下载模型或修改数据/junction。

## 2026-10-28 在线实时链审查与连续性修复

- 本会话唯一写入；只读分析定位并修复实时历史生命周期：TTL/地面重绑清理实际 runtime 姿态与基线资格（保留退休基线及版本），新姿态链的不可观测长缺口与地面失效清旧动作证据、站立恢复计时不跨缺口，缺目标同帧标定/选择变化也清历史；无姿态旧调用路径保留原契约。姿态 unknown 不再自动冒称 upright/recovering。默认选轨在旧轨非歧义短缺测时不抢选另一轨；关联或单人选择歧义不输出旧框、清动作证据。运行中跟踪/人体先验全局配置漂移被拒绝重绑，confirmed 与单人锁默认均未开启。
- 修改前新增 8 项软件回归均复现失败；最终新增 15 项、TTL 服务回归覆盖通过。最终 `-W error`：核心 900 项 OK（1 ROS 跳过）、capture 69、calibration 2、range_fall 10 脚本共 74 项 OK。额外 `tools/test_range_experiment.py` 仍 26 项中 1 错：既有测试夹具无 frame.binding，测试文件不在当前授权写入范围。Qt 板端服务联动测试尝试将报告放新证据目录，但程序要求 console_v2/.tools/app-evidence，启动前拒绝；未绕过目录限制，Qt 联动未验证。
- 四段同源完整离线前后与带锁比较：后倒疑似 33→0（65–67 帧旧轨关联歧义，现明确清证据）；前倒 0→0（低矮姿态未知，不再误称恢复）；慢倒默认 0→0、带锁 43→0（104 帧关联歧义），弯腰疑似 0→0、recovering 67→26。实验性碎片预筛慢倒出现 44 帧疑似，但前倒/弯腰选中帧减少 36/22，后倒仍未恢复；未启用该开关。这些均为几何候选帧，不能等同真人或真实告警。
- 完整 386/780 帧本地 ROS 消息替身→识别服务回放对照隔离的修改前源码：386 逐帧目标行/ID/高度/状态/低位提示/原消息 SHA 一致；780 目标行及 ID/高度各变 2 帧、状态 24 帧，原消息 SHA 一致，低位提示 active 均为 689–707 的同一 19 帧（提示元数据 3 帧有差异）。历史 2026-10-26 参考与上轮算法本已不同，原工具按历史全等会报错，日志保留；新检查仅验证逐帧传输/覆盖/关闭 confirmed 并列出差异。候选识别包本地封存、78 个打包文件逐字节验证及 Python 3.8 语法检查；未部署。
- 证据 `docs/evidence/2026-10-28_online_recognition_audit/`（COMPARISON、逐帧探针、关联诊断、服务前后账本、日志、包与 SHA）。非原子 61,017 条跟踪+非忽略未跟踪树清单在编辑期间完成，不能当原子改前基线；定向改前文件副本另留。没有人体 GT，身份/跌倒准确率和召回率 UNKNOWN；四段开发集、非因果背景及离线地面不能外推在线物理效果。未做真实板端部署/采集、现场背景与地面初始化、板端性能、多人和人体真值；目前不能称完整在线实时识别已完成。

## 2026-10-29 关联歧义回退修复与逐帧对照

- 修正上一条“清除旧事件证据”的归因：后倒 33→0、慢倒带锁 43→0 是短暂关联歧义前的同轨下降/姿态证据被提前清除，属于开发集回退；四段当时 `observation_gap_timeout` 为 0。此前 qiandao 有 39 帧 `posture=unknown` 和 2 帧 `posture=transitioning` 从 recovering 变 unknown，后者是已知过渡态，不能称为姿态不明。
- 受阻旧轨不再屏蔽其他已跟踪的非歧义候选；竞争和单人锁规则仍生效。短歧义只打断持续时间、保留同轨动作史；超时、明确地面失效或切轨清史。长缺测检查不再依赖 posture，旧 ROS 节点传入当前有效帧的明确地面失效，普通无帧不伪称失效。歧义或已锁定不可观测帧缺时间戳时先中断计时，待有效时间判断是否超限。关联歧义下游标 `target_ambiguous`。
- 姿态、基线、特征、跌倒与低姿态默认配置纳入运行时配置快照/SHA 和漂移检查；漂移报 `settings_drift_requires_new_runtime`，历史清理按快照重建。历史回放旧配置兼容、工具合成夹具 binding/非退化 PCA 修复。confirmed 和单人锁默认仍关闭。
- `-W error`：核心 907 OK（skip 1）、capture 69、calibration 2、range_fall 74、工具 range_experiment 26 均 OK；Python 3.8 语法检查通过。386/780 全帧服务替身：原消息 SHA、预览一致；对上一轮 sealed，386 目标行/ID/高度 0 差异、状态 2 帧；780 目标行/ID/高度各 2 帧（506、508），状态 15 帧，低姿态 active 均 689–707 共 19 帧。508 恢复 g0_t0027 的 5844 点，但 506/507 仍选 98/84 点碎片。
- 四段逐帧：后倒疑似 0→33、慢倒带锁 0→43；慢倒默认仍 0，前倒和弯腰仍 0。默认慢倒/弯腰分别有 2/5 帧目标变化，身份切换、碎片选择和重识别仍待解决。Qt 板端联动本轮未跑；此前目录约束导致启动前失败的事实不变。无真人 GT，人体身份/真实跌倒/准确率召回率及地面物理有效性 UNKNOWN；没有部署、采集、训练或改数据/junction。
- 证据 `docs/evidence/2026-10-29_ambiguity_continuity/`：COMPARISON、逐帧账本、测试日志、源/输入 SHA。回放中修改源码曾触发 source changed 自检并保留失败日志，最终两段均在稳定源码下通过传输核验；历史参考算法本就不同，其全等断言按脚本记录差异。改前有定向副本、HEAD 和定向 SHA，但没有完成含所有未跟踪文件的改前全树 SHA，不能声称具有原子全树基线。

## 2026-10-29 借鉴四会话演示规则接入实时链

- 读取「预处理跌倒演示会话」及其代码：演示规则要求同轨连续实测，地面相对高度中位数≤0.5 m、最大高度≤0.7 m、水平 5–95 分位跨度最大值≥0.5 m；连续 1.5/3.0 秒分两级。视频还将该规则与既有 suspected 合并；固定“人体”文字不代表身份跟踪已修复。演示规则是在这四段开发集调出的几何候选，不含下降门，主动躺下、部分坐卧或误选也可能触发；3 秒不是真实跌倒 confirmed。
- 将规则移到 `core/range_demo_alert.py`，演示和共享 `RangeEngine` 复用；实时按当前有效地面、同帧源行、同轨/代际/绑定及源时间计算，缺测、跳帧、换轨、上下文变化和 TTL 清理中断计时。新增 `local_range.demoFallCandidate`、能力标识和配置快照/SHA；旧 `groundAlert`、fall 状态和 confirmed 开关保持原契约。Qt 对新字段可选校验并展示“水平低位疑似 / 持续 ≥3 秒”，明确为几何候选，旧协议仍可用。
- 四段相同输入完整回放：后倒一级/二级 33/19 帧（首帧 83/97）、前倒 30/16（159/173）、慢倒默认及带锁均 43/29（120/134）、弯腰 0/0；实时原始精度与演示四舍五入规则逐帧等级 0 差异。它们是本轮同源开发集，不是独立测试或人体/跌倒 GT；采用全段非因果背景和离线未物理验证地面，不能推断现场结果。
- 386/780 服务替身完整回放：新提示一级分别 0/13 帧（780 为 693–705），二级均 0；与上一轮逐帧源行 SHA、目标数/ID/高度、动态状态、旧低位提示和原消息 SHA 全一致，预览与既有参考一致；本机回放服务循环 P95 分别为 93.75/109 ms，非配对负载测量，不能当板端性能。初次试图从旧 PROBE 复算时发现其未保存水平跨度，产生的全零 SCREEN 已明确标无效；随后改从运行时实测特征重放。780 506/507 帧碎片误选及主轨被附属组件冲突连带阻塞的根因已定位，未凭三帧就改变跟踪器；人体身份与重识别仍未解决。
- 验证：核心 `-W error` 911 OK（skip 1）、range_fall 74、demo 6、range_experiment 26；Python 3.8 语法检查、Qt/C# 本地构建通过。ROS 消息/伪 Foxglove → 两个真实 Qt 窗口的合成持续低位测试传递新候选并保持 confirmed 关闭；板端服务联动 1 项和旧协议 2 项通过。一次 Qt 测试发现未列出的姿态会显示 undefined，已补空字符串并重跑通过；初次失败日志保留。最终两次 Qt 截图一张点云未呈现、一张点云与提示均可见，不能仅凭 ACK 推断 GPU 稳定呈现。
- 机器证据 `docs/evidence/2026-10-29_demo_method/`：DEMO_COMPARISON、逐帧账本、服务前后对照、源/结果 SHA、Qt 报告截图与测试日志。变更前 HEAD 及跟踪+非忽略未跟踪文件 SHA 以两段非原子清单记录（61,333 项列出、61,269 文件摘要、0 读取错误；受保护数据及本轮证据目录排除），定向改前副本保留。未部署/采集/训练/下载模型，未修改数据与 junction；板端性能、现场人体身份、跌倒准确率/召回率及物理地面有效性均 UNKNOWN。

## 2026-10-29 板端演示规则部署准备

- 用户授权将新方法放到板端。当前可连接 `192.168.31.58`，容器内实际识别 PID 64149、release `7530fd08938238d1003abb54576310007197db41754388315c57e1b81566ff90`，带空场前缀及现场地面拟合参数；该状态不同于历史记录，未停止或替换。
- 新包 release `2c19d73989dfc4e2b5afa0e082da5bc71eac95b57697ee3218a1356991636bb4`、tar SHA256 `bf6ce862243c356cc4ceb7009f218ee0b3ec6736c94ca6331955d3e4b5250562` 已放入板端独立 recognition_releases 目录，79 个 manifest 文件哈希一致；板端 Python 3.8.10/NumPy 1.17.4 和服务入口导入检查通过。尚未切换/启动新服务；已有识别现场内存背景无法跨进程直接保留，新服务需重新声明空场和地面拟合，正等待用户确认现场空场及授权初始化。未改驱动网络、未采集记录、未改 data/junction；板端真实识别效果 UNKNOWN。
- 本轮证据 `docs/evidence/2026-10-29_board_demo_deploy/`；本地新方法的离线回放及完整测试见 `docs/evidence/2026-10-29_demo_method/`。

## 2026-10-29 板端演示规则启用与现场初始化

- 用户确认视野清空并授权建立背景及地面。停止已核验的旧识别进程（PID 64149，release 7530fd08），保留旧版本和共享 current；新识别服务 PID 65456，release 2c19d73989dfc4e2b5afa0e082da5bc71eac95b57697ee3218a1356991636bb4，独立运行目录 `runs/range_2c19d739_20261029/`。初次切换检测将旧僵尸 PID 当活进程，后续启动脚本 CRLF 导致重定向失败，均已定位修正，失败日志/脚本保留。
- 板端即时状态：背景 ready、地面 bound/current_patch_support，输入 receiving，订阅连接 1，处理 149 帧；实时状态已声明 `horizontal_low_posture_v1`，空场无目标时 demoFallCandidate unavailable、confirmed 关闭。当前平面 normal [-0.463888, -0.032116, 0.885311]、offset 1.366635 m，几何质量门通过但物理地面与人体/跌倒 GT UNKNOWN；没有做真人跌倒或可靠性验证。启动参数已自动进行空场背景和一次拟合，进程内背景不能跨进程恢复；本次手动启动并未证明设备重启后自动启动。
- 证据 `docs/evidence/2026-10-29_board_demo_deploy/health.json` 与安装包；未改驱动、网络、数据目录。既有现场资源保护与识别服务单独回滚适用。


## 2026-10-29 四会话本机伪实时动作观察

- 新增 `pc_apps/demo_viewer/pseudo_live.py` / `pseudo_live.html`：同轨实测的既有姿态、下降/恢复/疑似和 `DemoAlert` 合并为因果几何观察标签；低位水平观察/1.5s/3s 与原疑似分别保留，缺测、换轨、代际/绑定变化、跳帧、时间异常及观测缺口中断持续计时，不把低位当已确认跌倒。生产规则和阈值未更改；这是本机组合分类，不是学习模型或人体身份识别。
- 四会话 905 帧全部离线运行，对 `2026-10-29_demo_method` 逐帧目标 ID、原状态、低位等级零差异；新增标签中前倒旧状态 unknown 的 84 帧得到几何描述，不表示描述正确率提高。后倒/前倒/慢倒第 83/159/120 帧首次低位提示（8.708/16.483/12.543 s），弯腰段无；全部为同源开发集，无逐帧 GT，准确率/召回率 UNKNOWN。
- 本机 localhost 逐帧实际调用同一 runtime，源时间近似节拍，2D 为同帧 192×256 径向距离图，白色为同帧目标像素；3D 显示有限抽样点、可拖动旋转。后倒 169 帧无节拍包括 2D PNG/3D 生成 P50/P95 41.6/87.0 ms，最大 101.9 ms；不含浏览器和传输，非板端性能。浏览器核对逐帧显示/疑似与深度、点云；源码/输入 SHA、逐帧结果、比对、计时、截图位于 `docs/evidence/2026-10-29_pseudolive_actions/`。
- 新增组合分类测试 5 项、姿态 6 项、低位规则 2 项、演示规则 2 项和旧页面 JS 四会话检查通过。初次对照脚本在回放完成前执行报缺文件，待完整输出后复跑通过；基线 HEAD `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`，git 可见跟踪/非忽略未跟踪文件非原子 SHA 清单 10399 文件、0 错（不含 data/captures、本轮证据及被忽略文件），不宣称全树原子基线。
- 四段无已声明空场前缀：运行前使用整段非因果背景和离线地面；目标身份、物理地面与真实跌倒仍 UNKNOWN，碎片/遮挡/主动躺下可能误判。未部署、采集、训练、下载模型或修改 data/junction。

## 2026-10-29 GitHub 仓库同步（未推送历史清理 + 首次推送）

- 盘点：本地 `master` 领先 `origin/master` 30 个提交（末次提交 2026-10-15），工作区另有 101 个已跟踪改动、838 个未跟踪源码/文档（约 9.4 MB）。未推送提交内新增 blob 合计 4.6 GB，其中 6 个文件 ≥100 MB（最大 `docs/human_capture/evidence/2026-10-07_hrw03_r39_closeout/09_visualization_data.json` 500 MB），直接 push 会被 GitHub 单文件 100 MB 上限拒绝，另有 4.6 GB 远超单次推送 2 GB 上限。
- `.gitignore` 补齐：`*.log`、`/.dsh_tmp/`、`/node_modules/`、`/dist/`、`/damage.txt`、`/pc_apps/demo_viewer/*.mp4`（318 MB 演示视频）、`/docs/evidence/` 与 `docs/{human_fall,human_capture,sidequests}/evidence/`（新增批量证据不入库，已有跟踪账本仍由 `git add -u` 维护）、`/sidequests/**/results|work/`。
- 工作区提交 926 个路径 / 10.6 MB（`src/`、`webui/`、`pc_apps/`、`console_v2/`、`sidequests/`、`ML/`、`tools/`、`docs/` 的源码与文档），不含 `data/`、`captures/`、evidence 批量产物、日志、演示视频、`node_modules`。该提交同时包含 12:44–12:49 另一会话写入的 `pseudo_live.*` 与 PROGRESS/PROJECT_STATE 改动（按当时快照入库，未逐条复核其结论）。
- 历史重写：用 Python 走 plumbing（`cat-file commit` → 过滤 `ls-tree -r` → `update-index --index-info` → `write-tree` → `hash-object -w -t commit`）重放 `origin/master..master` 共 31 个提交，剔除 1908 个路径：全部 `*.log`、evidence 下 >256 KB、`sidequests/**/results|work/`、任意 >5 MB 文件；作者/提交者/时间/消息原样保留，工作树不动。备份分支 `backup/pre-sync-20261029` 保留原 31 个提交（`c9c4ee4` 链），旧 `master` 可用它恢复。
- 推送：新链 tip `a60c62c`，远端 `master` `d8efaba..a60c62c` fast-forward；传输 6324 个对象、压缩后约 31.8 MiB（本地估算未压缩新增 blob 109 MB，最大单文件 2.4 MB）。本地 `master` 用 `git reset --mixed` 对齐新链，磁盘文件（含全部 evidence、`data/`、junction）一个未删。
- 校验：`git diff master-backup sync/20261029` 只有删除、无新增或内容修改；重写后 `git status` 仅剩并发改动与被剔除的 sidequests 输出，随后补 `.gitignore` 收口。未改 `data/`、junction、驱动/网络，未部署/采集/训练。语义边界：GitHub 上现在没有 2026-10-10 至 10-15 的 evidence 大件与 runner 日志，它们仍在本机；需要时按会话 SHA 重跑再生。

## 2026-10-29 两条算法线拆分支（algo-3d / algo-2d3d）

- 用户要求算法全部入库，并把「3D」与「2D 距离→3D」拆成两个分支。新增 `BRANCHES.md`：`master` 保留全部；`algo-3d` 只保留 3D 点云算法链；`algo-2d3d` 保留 2D 径向距离图→同源 3D 全链。
- 依赖实况决定了两条线不是对称的：`core/range_runtime.py` 直接 import `baseline/features/fall_state/lidar_candidates/human_prior/support_composition/candidate_history`，`core/human_prior.py` 又 import `range_features.bound_ground`；因此 `algo-2d3d` 必然是 `algo-3d` 的超集，`range_features`/`range_contract` 作为共享原语留在 `algo-3d`，两分支的差集就是 2D 距离图这条线新增的文件。
- `algo-3d` 移除 231 个路径和 18 个测试文件：`core/range_*` 19 个（保留 `range_features`/`range_contract`）、range 入口与配置 7 个、`tests/test_range_*.py` 与 `test_episode_continuity`/`test_online_continuity`，以及依赖该链的 `pc_apps/range_fall`、`pc_apps/annotator_v2`、`pc_apps/bathroom_demo`、`console_v2`、`tools/range_*`、`tools/human_2d3d_package`、`pc_apps/demo_viewer/pseudo_live.*`、`demo_alert.py`。
- 验证：`algo-3d` 上 `python -B -W error -m unittest discover -s src/human_fall_detection/tests` = **733 tests OK（43.7 s）**；剩余 1568 个 Python 文件 `py_compile` 3 个失败均为改动前既有（`pc_apps/human_ml/train_person_rf_v3.py` 第 178 行 JSON 注释、两份 `docs/human_capture/evidence` 探针脚本），与本次拆分无关。`algo-2d3d` 内容与 `master` 相同，未改代码。
- 推送：`algo-3d` `f652a06`、`algo-2d3d` `0ecfb81` 已建立远端分支；`master` 内容不变并保留全部。拆分只动文件归属，未改算法、阈值、配置或数据；`data/`、junction、驱动/网络未动，未部署/采集/训练。文档仍保留两条线的历史记录，`algo-3d` 上部分 doc 链接指向已移除文件，属已知边界。人体/跌倒语义仍 UNKNOWN，`confirmed` 关闭。
