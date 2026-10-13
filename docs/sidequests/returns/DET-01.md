# DET-01 R1 回传（2026-10-07，Asia/Shanghai）

执行者Codex，唯一writer；状态 **SUBMITTED / CenterPoint BLOCKED，未 ACCEPTED**。现行表 [DET01_ACCEPTANCE_V2.md](../DET01_ACCEPTANCE_V2.md)，版本v2、SHA见 [22_submission_sha.json](../evidence/2026-10-07_det01_r1/22_submission_sha.json)。

实际读取 ponytail 技能路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。按最小方案复用上游PointPillars模型和本仓库配平，不安装整套新主线，不接入ML/ROS/回放生产；matplotlib用于诊断视图。

起始原树master/HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`，全Git文件含未跟踪基线 [00_baseline.json](../evidence/2026-10-07_det01_r1/00_baseline.json)。分支 `codex/human-detector-models` 与独立工作区同HEAD，无提交/推送。

## 集中诊断与变更

| ID | 根因/入口 | 最小处理 | 保留行为 |
|---|---|---|---|
| A02/A03 | 实际源28B、ring/padding/time会导致16B读取错位 | 独立只读XY Z I decoder及布局/长度校验 | 源行、帧序、原bin不改 |
| A03 | 原始XYZ=0经平移会形成假点堆；首次four_r1漏处理 | 统一adapt在变换前过滤，新增负例，全四会话重跑r2 | r1保留，计数记录 |
| A03 | 源变换不能跨会话套用，215607三法offset冲突 | 各自调用既有auto配平、source SHA绑定、仅显式TLS实验 | 门槛/FAIL/物理资格不改 |
| A04/A07 | 上游CUDA扩展不适配本机CPU | 复用模型体，仅hard voxel/旋转NMS用CPU；严格全权重加载 | 网络、anchors、推理阈值原样；GPU数值等价NOT_RUN |
| A05 | mmdet3d缺失，当前Python3.12无可用MMCV2.1二进制 | 保存真实导入/下载失败，CenterPoint入口保留 | 不伪造输出/比较排名 |

代码只新增 `sidequests/human_detectors/`；文档/证据只新增 `docs/sidequests/`。源码提交SHA、验收表SHA在22文件。原工作树观察到四外部变更见16文件，本轮无写入原工作区/数据/旧证据。

## 逐条自验

| ID | 状态 | 证据 |
|---|---|---|
| A01 | PASS，本会话隔离及基线记录 | 00/16；不声称外部工作树全静止 |
| A02 | PASS | 14_tests_zero_xyz_r2.log，7项通过、exit0 |
| A03 | PASS，仅离线TLS；215607一致性FAIL保留 | 四report/transform、15日志 |
| A04 | PASS，仅253帧推理执行 | 四predictions / summary，batch exit0 |
| A05 | BLOCKED | 12下载失败 / 19导入异常，早期run exit1 |
| A06 | PASS，准确性NOT_RUN | source=model，无GT、无P/R |
| A07 | PASS，GPU逐值等价NOT_RUN | 7检查、20 KITTI真实前向 |
| D01 | NOT_RUN | 无设备/采集/部署/物理验证 |

具体命令、输入/输出/来源、范围和限制见 [本轮报告](../evidence/2026-10-07_det01_r1/README.md)。未安排独立复审，不把作者自验称为独审或整体软件ACCEPTED。CenterPoint环境与真人框GT尚未闭合；主线开发保持暂停。

---

## R2 — 2026-10-07 用户人工定位补充后诊断

执行者Codex，SUBMITTED，未ACCEPTED；现行验收v2不变，补充A04/A06证据。ponytail实际使用路径仍为 `C:/Users/30680/.codex/skills/ponytail/SKILL.md`。独立分支/HEAD同上，未写原工作树或旧证据，不恢复主线。

新增 `audit_truth.py`、r2用户truth种子和逐帧空间诊断，更新支线入口；源码/输入/验收SHA见 [02_sha.json](../evidence/2026-10-07_det01_r2/02_sha.json)。根因覆盖：之前全场最大分不能归给真人，旋转框XY点包含核查后，真人位置的最高分0.111/0.293/0.260/0.134；位置点被框包含5/64、66/67、54/66、16/56帧。保留原模型、0.1输出阈值、全部原预测和215607一致性FAIL。

自检/诊断命令 `python -B -W error sidequests/human_detectors/audit_truth.py --self-check` 及带 `--results/--truth/--out` 的命令均exit0，原始日志00/01；A04/A06本轮PASS仅针对诊断执行/来源标识，精确人体框P/R NOT_RUN；其余沿用r1，A05 BLOCKED、D01 NOT_RUN、GPU等价NOT_RUN。

限制：真人轮廓依据用户文字确认，本机未找到两张蒙太奇，已请求路径；图片所用transform未绑定。用户数据是约略位置/姿态种子，不是每帧精确框或点mask。不能将覆盖帧比率当Recall，不声称几何管线已给出HUMAN_CANDIDATE。完整报告：[R2 README](../evidence/2026-10-07_det01_r2/README.md)。
