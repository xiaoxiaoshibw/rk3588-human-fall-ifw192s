# DET-05 人体点 GT 标注与纯人体柱采样隔离预注册（v1，2026-10-08）

授权：本轮唯一现行用户指令 = 2026-10-08 会话中选择 **(a) 人体点 GT 标注轮**，并确认执行主体为 OpenCode、标签来源为"writer 初标 + 用户确认后冻结"。独立 sidequest；唯一 writer 本会话（opencode-go/deepseek-v4.1-flash）。ponytail full 经由 opencode skill 工具实际加载（id=ponytail；base dir `C:/Users/30680/.config/opencode/skills/ponytail`，SKILL.md 已核对存在），使用方式记录于回传与 17 manifest。工作树 `C:/Users/30680/.codex/worktrees/human-detector-models/ldiar`，分支 `codex/human-detector-models`，起始 HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`。主树 `D:/Code/ldiar` 只读；不启动 HF/GL/HC/HR/ML，不 commit/push/reset/checkout/clean，不部署/采集/训练/物理标定，不改上游/权重/变换/历史证据。

唯一验收：[DET05_ACCEPTANCE.md v1](DET05_ACCEPTANCE.md)。新证据 `evidence/2026-10-08_det05_r1/`；回传 append `returns/DET-05.md`；`sidequests/human_detectors/README.md` 顶部同步。先完成指定资料全文阅读及 00 baseline（原 6053 / 工作树 10720 / 继承 3211 资产全匹配），再写本计划/验收表，再实现，再执行。消费资产继承 DET-04 的 3211 条路径复验；本轮新增消费 DET-03/04 存档、FG/PRE 输入、种子与标注件，绑定于 03/17/18。

## 帧集与条目

- 标签帧（10 个 (session,frame)）：215540/32、215607/33、215623/33、215643/3、7、11、12、17、28、37。标签绑定在 prepared 帧（含全部变体共用的点集）上。
- 实验条目（10 个 (session,frame,variant)）：代表帧 4 个 = 215540/32/B_workspace、215607/33/B_workspace、215623/33/B_workspace、215643/28/B_workspace；负帧 7 个 = 215643 B3、B28、E7、E11、E12、E17、E37（B28 与代表帧同条目，不双算，共 10）。负帧集合复现 DET-03/04 的 local head_delta<0 选择。

## 标注协议（预注册；冻结前允许作者修正并逐条记录）

- 类别：`human`（人体）、`furniture`（邻近非人体静态结构，**含近地/地面带**）、`mixed_uncertain`（小碎片/接触区等无法判定的点）。scope 外的点不带标签；未标点**不默认背景**，纯度与统计不得把未标点当人体或当背景使用。
- 绑定：scope 内 prepared 帧行（`det02_prepared_r1`）逐点记录，并经 `.ids`（FG 变体行→prepared 行）与 `.rows`（prepared 行→原始采集全局行）双链绑定；PRE/FG manifest、帧 sha、rows sha、ids sha 全部断言。标签同时绑定 prepared 与 raw 行号。
- scope：水平距会话种子 ≤1.0m、leveled z ∈ [0.05, 2.30]；z<0.15 不开放人体类别（脚部下沿可能被保守归入地面，**宁漏不假**）。
- 初标算法（确定性；scipy cKDTree 仅用 xyz 三列）：
  1. scope 内 z≥0.15 点按 r_link=0.08m 单链聚类；
  2. 人体块 = 满足 n≥50 且 z_max≥1.2m 的簇中水平质心距种子最近者；若其距种子 >0.45m，该帧不自动定人体块、转人工处理并记录；
  3. 其余 scope 点：z<0.15 → furniture（地面带）；z≥0.15 非人体簇 n≥10 → furniture；n<10 → mixed_uncertain；
  4. 逐帧渲染 BEV + 距离-高度侧视（类别着色、柱网格、簇编号、种子与 GT 标记）与簇表，作为用户审核件。
- 用户确认与冻结：审核件提交用户；用户确认或提出修正；修正落盘后生成 `gt_v1`——每帧 human prepared/raw 行号列表、XY 质心（human 点均值）、z 顶（human z_max）、AABB、provenance（标签件/渲染 SHA、确认日期与渠道）。冻结后标签/GT 不回写；实验只使用 `gt_v1`。帧集、各会话 TLS 变换 SHA、输入 SHA、类别定义一并冻结。

## 纯人体柱与切换（预注册）

- 有效点 = 有限且落在模型范围（配平 z−1.73 后 [0,−39.68,−3]×[69.12,39.68,1]）的点，与既有采样一致。
- `pure_human` 柱 ⇔ 该柱（0.16×0.16 柱格）内**全部**有效点标签均为 `human`；任一 furniture/mixed_uncertain/未标点（含 z<0.15、scope 外）即非纯。
- `base` = 全柱 first32（与既有模型输入一致）；`pure_switch` = 仅纯人体柱改用 z_rank32（按 z 排序等距覆盖 32 点，沿用既有实现），其余柱逐值冻结为 base：张量/计数/坐标/选点槽位逐值断言。
- 输出：逐条目纯/非纯/未标原因计数；纯柱 32 点 z 列表、prepared/raw 行号、输入 SHA、切换柱数。

## 指标（预注册）

- GT 位置分三口径（用 `gt_v1` XY）：`local_raw` = GT 0.55m 邻域 anchor 原始行人最高；`decoded` = 解码框包含 GT 的最高原始分；`final` = 最终 NMS/max50 框包含 GT 的最高分（0 = 无）。
- GT 匹配 anchor = 全部 anchor 中中心距 GT 最近者；报告其原始分、全库降序排名（并列按既有 trace_heads 实现）、GT 0.55m 邻域内排名。
- 竞争位 = 最终行人框中中心距 GT ≥0.8m（预注册最小分隔）中距 GT 最近者；报告其分与边距 `margin = GT final − 竞争位分`（GT 无框按 0 并注明）。
- 框空间匹配 = 是否存在包含 GT XY 的最终行人框；`gt_v1` AABB 与最终框最大 2D IoU（Shapely；旋转框 vs 轴对齐框）。
- 一致性：以本轮新运行复算 DET-03 存档的 seed 口径 local/containing/global 三值，要求逐值一致。GT 口径的"全场 zrank"对照无缓存全头可用，本轮不列，需另行授权。
- 不以全场最高分/跨帧中位冒充识别指标；不报 P/R/误报率（无独立人/场景泛化 GT）；单帧同人同场景，仅描述性。

## 前向预算与失败

- 新网络前向预算：正好 20（10 条目 × {base, pure_switch}），无其他网络前向。
- 断言/一致性失败：修复后仅重跑失败条目，重跑原因与次数记录；失败日志保留不覆盖。
- `python -B -W error` 全程；不改阈值/容量/强度/z/权重/编码/上游。

## 记录与收尾

- 编号证据：00 baseline（已交付）；01 输入审计；02 计划/验收预运行副本与 config；03 标注件与渲染；03b 用户确认；03c 冻结 `gt_v1`；04 纯度审计；05 运行 rows；06 指标对照；07 归因小结；08 回归；09 实验；10 独立复核；11 报告；17 打包（代码 diff/快照/逐文件 SHA/manifest）；18 完整性；22 范围；23 封口。大数组置于忽略目录 `sidequests/human_detectors/artifacts/det05_r1/`。
- 状态 SUBMITTED、不自行 ACCEPTED；E03/G01 保持 BLOCKED；L01 物理标定与独立人/场景泛化仍 NOT_RUN；D01 设备/部署/采集 NOT_RUN。
