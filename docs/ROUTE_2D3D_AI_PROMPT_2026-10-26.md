# AI 开发提示词：2D+3D 联合路线深化（消融 / 最小 GT / 困难场景清单 / 地面口径统一）

适用仓库：`D:\Code\ldiar`（Linux ROS 工作区 + PC 工具链，Windows 上不能编译 ROS）。
执行者：唯一写者是本会话 agent；子代理只做只读分析。

---

## 0. 背景（为什么做这件事）

- 目前只有两个"看起来很好"的会话：`cap_20261018_110029`（下称 386）与 `cap_20261017_113516`（下称 780）。它们的 2D 距离图与 3D 目标/框一致，但**2D 与 3D 是同一帧同一 ScanGrid 投影的两种表达**（同 `grid_sha256`、逐帧 `rawSha256` 绑定），一致是必然的，"互补"尚未被证明。
- 实测账（来自 `docs/evidence/2026-10-25_depth_fallen/oriented386|780/analysis.json`）：386 = 386/386 帧处理、0 丢帧、269 帧有实测目标（track `g0_t0002`）、姿态 269 `vertical_surface` + 117 unknown、规则 376 unknown + 10 `low_posture_unclassified`、主要 reason `baseline_not_ready` 259；780 = 780/780 帧、0 丢帧、355 帧有目标（track `g0_t0001`）、姿态与规则**全部 unknown**，reason `no_ground_or_candidate`。
- 两个会话 `human_annotations` 均为空，没有任何人/跌倒真值；`semantic: UNKNOWN`、`confirmedEnabled: false`、`calibrationStatus: UNVALIDATED_WITH_HUMAN_GT`。

## 1. 目标与产出

| 任务 | 产出（.md） | 判定标准 |
|---|---|---|
| A 消融对比 | `ABLATION.md` | 给出"2D 与 3D 是否真的互补"的可量化结论，或明确写"证据不足 + 需要什么" |
| B 最小 GT | `MIN_GT.md` | 帧级 GT 表 + 与算法的对照表（带样本量） |
| C 困难场景清单 | `ACQUISITION_CHECKLIST.md` | 现场可直接照做的采集矩阵（**本轮不采集**） |
| D 地面口径统一 | `GROUND_780.md` | 780 在与 386 同口径下的输出，或"不可行 + 原因" |

汇总：`docs/evidence/2026-10-26_2d3d_route/REPORT.md`。

## 2. 红线（先读，再动手）

- 不 `commit/push/reset/checkout/clean`；不部署、不启停板端服务、不采集、不训练、不下模型、不开 HR-09；不改驱动/网络。
- 不动 `data/`、`captures/remote|leveled|registration` 三个 junction、历史 `docs/evidence/**`、冻结配置（`default.yaml`/`geometry.yaml`/`geometry_constrained*.yaml`）、`ML/`。
- 不为了"让指标好看"而调阈值：任何阈值改动必须是**独立命名的新变体**，冻结配置保持原样，并在 .md 里逐条列出改动与前后结果。
- `confirmed` 保持关闭；人体/跌倒语义保持 UNKNOWN，不得写成"识别正确""已验证"。
- 采集属红线：**本轮只产出需求清单，不执行**；需要采集时必须先取得用户明确授权并由用户安排现场。

## 3. 任务 A：2D-only / 3D-only / 2D+3D 消融

### 3.1 输入（只读）

- `docs/evidence/2026-10-25_depth_fallen/oriented386/analysis.json`、`oriented780/analysis.json`：逐帧 `frameIndex/stampSec/sourceRows/box/measured/posture/state/reasons/depth{validPixels,targetPixels,preview,mask,...}`。
- 2D 来源：`src/human_fall_detection/core/range_image.py`（ScanGrid）、`pc_apps/range_fall/depth.py`（径向距离图 PNG16/preview/target mask/元数据）。
- 3D 来源：`core/range_components.py`、`range_denoise.py`、`range_background.py`、`range_tracker.py`、`range_features.py`、`range_posture.py`、`range_runtime.py`、`range_shape.py`、`range_skeleton.py`；运行入口 `pc_apps/range_fall/runtime_replay.py`（输出 `range_fall_analysis/1`）。

### 3.2 三路必须可判定（写下"每路读了什么、没读什么"）

- **R2D（只 2D）**：只使用径向距离图与其 valid mask/连通域：平面轮廓完整性、连通域数、目标与背景的**平面粘连**判别；**禁止**读取 3D 结构量（height/height_layers/verticality/eigenvalues/extent）。
- **R3D（只 3D）**：只使用 3D 结构与几何（点集统计、层高、竖直度、跨度、PCA、支撑与合并）；**禁止**读取 2D 图/掩膜连通性结论。
- **R2D3D（联合）**：现有 `range_posture` + 规则链（基线口径）。
- 每路结论必须能落到同一组可比较的标签上（例如 `person_like / not_person_like / unknown` 与 `standing / low / lying / unknown`），标签定义写在 .md 开头。

### 3.3 先做"共享信息量"量化（这一步是本任务的技术核心）

因为 2D 是 3D 的投影，必须先量化共享信息，否则"一致"会被误读成互相验证：
- 同一帧进入 2D 与 3D 的**源行集合占比**（构造上≈100%，必须写明）；
- 逐条列出两路**实际独立的信息**：如 2D 贡献"平面连通/粘连"，3D 贡献"高度/竖直度/跨层结构"；
- 结论句式必须限定为："联合链在 2D/3D 结论冲突帧上的行为"，**不得**写成"两个独立视角互验"。

### 3.4 "歧义"的可操作定义（先定义再统计）

给出至少两种可机器判定的歧义类型，例如：
- 平面歧义：2D 轮廓上目标与背景**粘连**（单连通域）而 3D 上**分离**（多组件/有高度跨度）；
- 结构歧义：3D 高度/竖直度不足以判定（退化/跨度不足）而 2D 轮廓形态明确；
- 位置歧义：2D 平面位置与 3D 中心不一致（标定/地面假设冲突）。
每类给出判定式（用哪个字段、什么阈值来源：冻结配置里的既有值，不许新调）、以及该类在两个会话中的帧数。

### 3.5 产出内容

1. 逐会话**分歧帧索引表**（frameIndex + stampSec + 分歧类型 + 三路各自结论 + 依据字段）；
2. 联合链在分歧帧上的行为统计（解开了/仍歧义/判错——"判错"只能在有 GT 时使用，否则写"待裁决"）；
3. 结论一节，必须落到以下之一：**互补成立（给出量化幅度）** / **互补不成立（给出反例帧）** / **证据不足（列出还缺什么：GT 数量、困难场景、需要哪类独立信息）**；
4. 明确写出为了把结论推进到"成立/不成立"，**还需要多少帧 GT、哪些场景**（与任务 C 的清单对应）。

## 4. 任务 B：最小 GT

1. 选帧：从 386/780 里挑 **30–60 帧**，覆盖：正常站立、走动、低姿态（蹲/坐/卧）、离场/局部可见、空场（无人）、目标消失边界帧；尽量平衡两个会话。
2. 标注方式：人看渲染的 2D/3D 预览图判断。预览 PNG **只渲染一轮**，人工看完即删（任务末尾统一清理），不得为同一帧反复导出多个版本；GT 表必须自带**可复现定位**：`sessionId + frameIndex + stampSec + rawSha256`。GT 表本身是本任务唯一保留的数据产物。
3. GT 表字段（写在 `MIN_GT.md`，另存精简 JSON 同名文件）：`sessionId, frameIndex, stampSec, rawSha256, 是否有人(是/否/不确定), 姿态(站立/走动/蹲/坐/卧/其他/不确定), 是否跌倒事件(是/否/不确定), 标注依据(所见现象一句话), 置信度(高/中/低), 备注`。
4. 铁律：**不得把算法输出写进 GT 列**；不确定就标"不确定"，不要猜。
5. 随后产出"算法 vs GT"对照表：逐帧差异、按类别的混淆计数、带样本量；只在二分类定义明确的子集上给 precision/recall，并同时给出样本量与 CI 缺口的说明；`confirmed` 仍关闭。
6. 写明 GT 的局限：单场景、单人、无独立视频/时钟、真值由算法输出辅助渲染的预览辅助判断（存在泄漏风险，需在 .md 声明）。

## 5. 任务 C：困难场景采集清单（**不执行采集**）

产出矩阵，每项含：目的、验证的歧义类型、时长/帧数下限、验收条件（帧率、丢帧、点数、`frame_id`）、需要的标注、现场资源（板端/人员/场地）、是否需要用户授权：

- 遮挡度：无 / 部分（半身、腿部、侧身） / 全身遮挡后重现；
- 距离档位：1 / 2 / 3 / 4+ m（含"刚好在有效边界"）；
- 人数：1 / 2 / 3（并排、交叉、先后）；
- 姿态：站立 / 走动 / 蹲 / 坐 / 卧 / 起身 / 跌倒过程；
- 进出画：进入 → 静止 → 离开，含"开机即静止的人"（当前入口门要求 1.2 s 内 ≥0.3 m 位移，静止起始必然不锁，这一条要单独列）；
- 地面与传感器：同一地面不同材质、传感器高度变更（影响地面相对高度）；
- 设备风险提示：2026-10-25 20:28 曾出现雷达零输出导致联合录制失败；采集前须确认雷达出数与 `single_target_live/state` 新鲜。

清单结尾给出**最小可行采集批次**（建议 3 个会话、每类 1 条）与"采完能回答哪个问题"的映射。

**采集时的保留策略（写进清单，供现场执行）**：每类场景只录 **1 条**会话即可，同场景不重复录制多条——点云体积大，重复录制只是浪费存储；录完把原始点云保留在 `data/sessions/` 一份即可，不另存副本、不导 PNG 序列，除非某条明确需要人工标注才导出该条的必要帧。

## 6. 任务 D：780 地面口径统一

1. 复现 386 的同口径：用同一套工具与流程为 **780** 绑定同源地面（386 用的是 `docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json`；场景件在 `src/human_fall_detection/config/single_target_scene_20261019/{ground_candidate.json,declared_empty_background.json,display_ground.json}`），记录产物的 SHA256、绑定依据（源帧/坐标系/残差）。
2. 若 780 无法同源拟合（几何不足、源帧不匹配等）：**如实写"不可行 + 具体原因"**，不得拿别的会话地面冒充，也不得用"看起来对"的地面凑。
3. 在统一口径下重跑 780（`pc_apps/range_fall/runtime_replay.py`，同 `--empty-prefix-frames` 与 ground 绑定方式），产出两会话同口径对照表（姿态分布、规则状态、主要 reason、帧数/丢帧）。
4. 结论写清：780 之前的"好看"有多少是显示层好看、多少是规则层真实输出。

## 7. 交付与清理（用户硬要求）

- **最终只保留 .md 结果**：
  - `docs/evidence/2026-10-26_2d3d_route/{REPORT.md, ABLATION.md, MIN_GT.md, ACQUISITION_CHECKLIST.md, GROUND_780.md}`；
  - `MIN_GT.md` 可附同内容的精简 JSON —— **GT 表是唯一允许保留的数据产物**（它是后续评测的输入）。
- **点云等大产物只保留一份，且绝不重复生成**：
  - 原始点云只在 `data/sessions/...`（只读）**就地分析**：不复制、不重导出、不切片段、不做第二份副本；
  - 派生的点云/深度图/掩膜/预览/逐帧账本（PNG、CSV、JSONL、NPZ、缓存、临时目录、临时数据库）**一次性生成、一次性删除**，任务中间不要反复导出多轮；
  - 需要多轮计算时复用同一份内存/临时结果，不落地第二份；确需落地时用**同一个**临时目录，任务末尾整体删除。
- 清理前先生成**删除清单**（路径、字节数、sha256、可再生命令），写进 `REPORT.md`，并把清单作为 .md 保留。
- 代码脚本默认保留（放 `pc_apps/range_fall/exp_2d3d/`，属代码不是数据）；若要求彻底只剩 .md，则把脚本内容以附录形式内联进 .md 后删除脚本目录。脚本数量保持最少：能一个脚本出全部表格就不要拆成四个。
- 禁止触碰：`data/`、三个 junction、历史 `docs/evidence/**`（除新建的 `2026-10-26_2d3d_route/`）、冻结配置、`ML/`、板端。

## 8. 工作方式与验收

- 先读 `docs/PROJECT_WORKFLOW.md`、`docs/PROJECT_STATE.md`、`docs/PROGRESS.md` 再动手；连续做完读→改→测→记录，不做人工审批环节。
- 唯一写者；子代理只读。
- 回归：Python 全部 `-B -W error`（`python3 -B -W error -m unittest discover -s src/human_fall_detection/tests`、`-s pc_apps/range_fall` 相关测试按其 README 入口）；JS 套件按 `AGENTS.md` 列表；新增代码必须 3.8 语法兼容（板端口径）、仅 stdlib + NumPy、不得新增依赖。
- 文档：结束时**追加** `docs/PROGRESS.md` 一节，并在 `docs/PROJECT_STATE.md` 顶部新增"最新"节，写清结论、未决项、删除清单与"人体/跌倒效果 UNKNOWN"。
- 禁止宣称：互补已成立（除非 A+D+B 三者共同支持）、人体识别正确、召回率、板端实时达标。
