# 给 Claude Code：GL-02 R2 返工（用户手动派发）

工作目录：`D:\Code\ldiar`。用户已授权本阶段软件开发，后续改为用户手动给Claude Code；不要调用OpenCode或自行派下一工单。你是本单实现者，Codex负责独立复审。只执行GL-02 R2返工，不执行GL-03，不部署/采集。

## 先读与基线

1. 根AGENTS.md、CLAUDE.md；`docs/human_fall/GROUND_LEVELING_PLAN.md`、`tickets/GL-02_ground_frame.md`、`DISPATCH.md`、`RETURN_TEMPLATE.md`、`GEOMETRY_CONTRACT.md`、`INTERACTION_CONTRACT.md`、`REVIEW_LOG.md`。
2. `evidence/2026-10-01_gl00_r4/CODEX_REVIEW.md`及`25_contract_extension_draft.json`；`evidence/2026-10-01_gl01_r4/CODEX_REVIEW.md`。GL00/01软件已获审，真实物理/来源仍BLOCKED，不重复实现。
3. `returns/GL-02.md`；`evidence/2026-10-01_gl02_r1/CODEX_REVIEW.md`、`codex_gl02_boundaries.py`、`40_codex_boundaries_stderr.txt`。该独立脚本6方法6失败，原样复现，不能改弱。
4. `C:\Users\30680\.codex\skills\ponytail\SKILL.md`；若环境外部读取受限，用GL02 R1的哈希验证副本`ponytail_SKILL.md`并记录真实来源/哈希，不放开全局权限。

先记录branch/HEAD、git status与相关文件SHA（未跟踪也在基线）。当前master/c96489e用户driver差异及Windows软链接保留；禁止reset/清理/commit/push。确认没有其他实现写入者。R1证据/原录制/旧标定/旧回传全部保留，本轮用新的`evidence/<实际日期>_gl02_r2/`。

## 本轮必须修复

按CODEX_REVIEW逐项解决：

- 可信地面整体连续偏移能要求重标定；稀疏、遮挡、未知ROI保持unknown/degraded。不得把旧平面支持不足直接阻断所有真实变化，不以10%杂点p95上升冒充地面整体变化。固定变换不逐帧重拟合更新，不换算法体系/库，不放宽GL00门槛。
- 自动源AABB角点映射与“可信独立地面ROI”分开；没有明确地面身份/可信区域来源，监测不能报告ok。fixture可明确synthetic可信ROI，不能升级physical_verified或single_plane_confirmed。
- 启动和apply_ground_context统一严格校验（同ID也校验），原子一致切换；损坏记录不得继续有效。换ID清旧目标位置、快照、选择/请求资格、站姿基线与动作历史，核对所有状态投影和缓存；旧事件保留，源seq/stamp/epoch原义不变。
- 父ground与派生n/d/from_frame/来源hash一致；constrained记录复用GL01严格校验。版本严格int，bool/mixed bool/非有限/坏单位/反射/错R/t/缺来源记录拒绝；数学及旧v1兼容保持。
- 监测参数/持续性严格校验；断流/无效帧清连续证据与有效监测结果。重标定失效必须进入实际观测/位置/基线门控，不能仅显示附加quality字段。
- CLI选项依赖明确，--ground-derived不能被旧路径静默忽略。已有输出/diagnostics拒绝覆盖，完整新版本记录来源hash、参数/质量与创建时间；不得先写文件再发现旧输出存在。

简单修复，复用现有校验/生命周期入口；不要做通用热更新框架。持续判据若需明确新的合成时间/样本门槛，在代码/回传解释来源与未实测限制，由Codex审查；不要将固定帧数冒称物理时长。

## 范围与现场事实

允许calibration/ground相关纯模块、标定CLI/独立配置、必要node_runtime及最小选择/基线失效入口、GL02相关测试与兼容文档。lidar_candidates只允许必要版本元数据，不做GL03框/聚类改造；网页/driver/厂商库/网络/自启不动。default.yaml、geometry.yaml冻结。

现场最新：雷达向下看，机器人地面到顶部1.4m，地面到雷达“眼球”的垂直距离约1.1m。窗口到点云原点偏移/尺量误差待核；hardware_inventory中的约26度是截图粗估，非实测外参。候选d约1.29～1.32m的差保留，不硬对齐。真实地面/物理、IMU融合/confirmed保持未验收/禁用。

Windows只跑纯函数；已授权SSH `wel@192.168.3.125`、`slam-localization`容器可用于临时隔离副本的Python3.8.10/NumPy1.17.4兼容回归。先核对可达/容器，不读或保存凭据，不升级依赖。隔离回归不需部署/采集；不得重启活动节点或driver、不得覆盖活动release/bag。SSH用LF脚本，记录inner/outer真实退出码。

## 验收与回传

1. 原样跑`python -B -W error docs/human_fall/evidence/2026-10-01_gl02_r1/codex_gl02_boundaries.py`，6方法全部通过；对其余静态待核项补能失败的实际反例，不镜像实现或改弱测试。
2. `python -B -W error -m unittest discover -s src/human_fall_detection/tests -v`；相同SHA隔离板端兼容检查。必要校准包回归。数学、生命周期、监测与CLI各自提供日志，未跑项NOT_RUN。旧262测试通过不能替代独立反例。
3. 报告实际修改清单、关键函数、配置/源码/数据/产物SHA、时间/坐标语义、真实退出码、原失败与限制；software/synthetic/device/physical分层。仅软件可提交，真实物理仍BLOCKED。
4. 向`returns/GL-02.md`追加“Claude Code GL02 R2”回传，仅SUBMITTED/BLOCKED，不自行PASS/ACCEPTED。不改Codex审查结论、不启动GL03。

完成后用户回到Codex说“复审GL-02回传”，Codex直接读取共享文件独立复审，不需要搬运长回传正文。
