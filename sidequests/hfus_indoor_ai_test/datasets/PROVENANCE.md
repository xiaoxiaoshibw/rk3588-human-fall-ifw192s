# OD1 数据溯源记录（HFUS-INDOOR-AI-TEST-01）

记录时间：2026-10-15。原始 zip 保留于 `ML/data/`，未改动；解压副本在 `sidequests/hfus_indoor_ai_test/datasets/raw/{det,track}/`，检查脚本 `inspect_od1.py`（本目录，`python -I` 运行）。

## 来源

- `ML/data/det_dataset-20261015T080607Z-1-002.zip`
  SHA256 `11aadd3f…a5ea1c853`（全值：11aadd3fb65cdf91d43307a77fda9785d225648808bcdc02a96d27ba5ea1c853），108,500,828 B
- `ML/data/track_dataset-20261015T080614Z-1-001.zip`
  SHA256 `af13138d…5d51523c`（全值：af13138d1a9579eceb47222180e68d47ccf5c5ab12a519a95969e9745d51523c），134,566,148 B
- 文件名后缀 `-1-001/-1-002` 为分片编号，疑似 O-LiPeDeT（OD1，俯视室内 LiDAR 人体检测）Google Drive 文件夹的分卷导出；github.com/drive.google.com 当日网络不可达，**许可与完整分片清单待确认**。

## 格式（实测）

- 点云 `.bin`：float32 × 4/点，第 4 列恒 0（无强度）；每帧 144k–168k 点（文件约 2.7 MB）。
- 房间几何（各帧几乎相同，静态场景）：x∈[-6.0, 23.6]，y∈[-17.1, 7.6]，z∈[0.11, 3.19]。
- 坐标系（投影验证推断）：**z 轴向下、原点在上顶传感器**；地板 z≈3.05–3.19，人体点 z≈1.2–3.0。x/y 水平。
- 标签 `.txt`：每行 `box x y z dx dy dz ID`（空格分隔，无类名字段——全部为人体 3D **轴对齐框 AABB，中心表示**；dx≈0.6、dy≈0.55、dz≈1.7–1.8，符合人体尺寸；末列 ID 为实例/跟踪号）。
- 框→点云投影（track 6 帧实测）：xy footprint 内有点云 1.6k–4.1k 点，z 跨度与框高一致 → **track 的 GT 与点云同帧同系、真实有效**。
- 禁止事项遵守：未把数据伪装成 IFW192S 28B/点格式；框内点≠逐点人体语义 GT（AABB 含背景），demo/评估须按框级处理。

## track_dataset（可用 ✔）

- `test/`：pointclouds 80 + labels 80，**stem 80/80 完全配对**。
- 每帧框数：1 人帧 29、4 人帧 51（共 233 框，49 个实例 ID）。
- 时间戳分簇：14833006xx–14833007xx（约 55 s 内 2 簇）与 14833910xx（约 25 s）——即约 2–3 段会话（2017-01-02 采集，传感器时钟），可作会话级划分单位。
- 结论：真实室内 LiDAR + 真实人体框 GT，满足本轮 P0（显示）与第一/二阶段基线、AI 训练评估的最小需求；无空场帧（每帧至少 1 框）。

## det_dataset（暂不可用于检测训练 ✘，点云可作背景素材）

- `test/`：pointclouds_all 65 + labels 28。
- **标签与点云 stem 交集 = 0**：点云名为 `cloud_stack3_<epoch_s>_<ns>.bin`（epoch≈2017-01-02），标签名为 `cloud_stack3_20251021/22_<hhmmss>_<ms>.txt`（2025-10 录制/导出命名），zip 内**无 data.yaml/mapping/README** 可供对账。
- 标签内容与 track 标签内容交集 = 0（77 行 vs 233 行，均为 box 行，坐标不同批次）。
- 65 帧点云中仅 8 帧 stem 与 track 点云重合；其余 57 帧为同源场景的新点云、本地无标签。
- 处置：det 点云仅作"真实室内背景/家具杂物"素材；其 28 个标签在找回配对（Drive 文件夹内 `-1-001` 等其他分片或映射文件）之前**不得用于训练/评估**。

## 磁盘

- zip 243 MB + 解压 ~389 MB，预算 2 GiB 内 ✔；未下载任何新数据。

## 2026-10-15 补包检查 R1（覆盖上文 det 暂不可用判断；旧记录保留）

用户补充 `det_dataset-20261015T080607Z-1-001.zip` 后，直接从 ZIP 流式检查，未整包解压或改动原始文件。

- 新包 1,352,849,995 B，SHA256 `b0acbb61f59fb0ff806df968a9941ef459f91531010035b854888bcedbf5b5b7`；905 文件，解压尺寸 2,162,106,730 B。两个 det 包解压合计 2,335,484,409 B，因此不应整包解压；新增检查输出不到 1 MB。现有 ZIP 本身总占用已超过原初始 2 GiB 预算，加上旧解压副本更高；本轮不再复制数据。
- **新包单独**有 training 29/29 对、validation 1/1 对，test 点云 76、标签 48；旧包的 28 个 test 标签补齐剩余标签。
- **两个 det 包合并视图**：training 29 对/87 框；validation 1 对/3 框；test 76 对/203 框；合计 **106 对/293 框**，无缺点云或缺标签。
- `pointclouds_all` 合计 786 帧，是另一个命名体系；不据此自动映射 GT，也不能当作已标注空场或背景负例。旧结论“无标签点云可作背景素材”只能指可视化素材，不能指可信负类。
- 全部 106 对读取并完成 ZIP CRC（读取到成员结尾）、float32×4 整除、有限数、标签字段与正尺寸检查。第4列全为0。训练/验证点数约55,950–56,044，test约111,636–168,100；不能把旧报告14.5–16.8万点概括到训练集。
- 按中心+全尺寸、零旋转AABB解释，293 框均有点，框内点数 min/median/max=58/844/15033。**这是几何可读性检查，不是人工标签质量验收，也不能证明框内全部为人体。** 尚未进行逐帧人工可视化审查。
- 标签实际为 `box` 加7个数字；前6数符合中心与尺寸，末列为整数样式但语义尚未核实。上文直接断言“ID”的表述应降为 UNKNOWN。官方 README 将末列写为 yaw，与本地文件数值不一致，不能直接送入按 yaw 解析的检测器；须核对导出器再决定是否AABB/实例ID。
- training/validation/test 之间原始点云 SHA 无完全相同文件；**不等于会话独立**。training/validation 使用 frame 编号且无会话映射，验证仅1帧，不足以建立可靠无泄漏评估。不得直接将目录名当作会话级划分证据。
- 无空标签帧；空场 FP 为 NOT_EVALUABLE。逐点语义/实例 GT 不存在。
- 来源网站本轮可访问：项目 README 链接同一 Drive 数据目录；项目 LICENSE 为 MIT（软件与文档），本地ZIP无许可文件；尚未核实独立数据许可适用范围，不宣称数据可任意再分发。
  - https://github.com/nilushacj/O-LiPeDeT-Overhead-LiDAR-Person-Detection-and-Tracking
  - https://github.com/nilushacj/O-LiPeDeT-Overhead-LiDAR-Person-Detection-and-Tracking/blob/main/LICENSE
  - https://drive.google.com/drive/folders/1tsfBmIWU3GAmrgPrOE7vaS2pqDw016Co

复现：`python -I -B -W error sidequests/hfus_indoor_ai_test/datasets/inspect_det_parts.py <新的输出JSON路径>`（拒绝覆盖已有输出），exit 0。逐帧原始成员 SHA、框参数、点数和ZIP SHA见 `DET_PARTS_INSPECTION_R1.json`。脚本仅依赖已有 NumPy 与标准库。

本次范围：补包可用性检查。格式/106配对 PASS；标签人工对齐审查 NOT_RUN；会话划分 BLOCKED（无映射）；模型训练/检测指标/Demo NOT_RUN。当前分支 master，HEAD `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；已有用户差异保留，未改生产/冻结权重/原始数据，未部署、采集、提交或推送。技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`、`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`。
