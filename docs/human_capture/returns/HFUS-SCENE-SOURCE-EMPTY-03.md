# HFUS-SCENE-SOURCE-EMPTY-03 原始回放与新空场诊断

用户继续授权，并提供八段动作备份以及空场候选 cap_20261014_221808。应用为 D:/Code/ldiar 人体融合 pointset/r01，localhost:8954。

## 已完成

八段动作原始 meta/points 共16文件恢复后逐文件SHA256与冻结catalog一致。实际原文件重新回放1934帧，原XYZ/保存账本、静态位姿、前景源行、全部三维簇成员、因果中央候选逐帧相同。报告状态 PASS_AVAILABLE_ORIGINALS；原空场 cap_20261013_131958 的两份文件仍缺失，不能把新会话冒充旧会话。

新空场 cap_20261014_221808：272帧、13364725点；28字节步长、帧offset/count与文件大小校验通过。91 FIT帧构建16006个稳定体素（至少28帧出现），91 CAL帧标定距离容差0.0551599761m；旧值0.0549238965m，未改原聚类eps/min-points等参数。90留出帧旧背景残余110492点，新候选背景11240点（下降89.827%）；0新增簇、0中央几何候选。

在八段动作46个固定抽查帧中，原中央候选86358点次有86099仍属于新前景，合计99.700%；逐帧98.506%–100%，46帧均可独立选出几何候选。这是候选点保留诊断，不是人体召回率；未完成新背景全量因果回放或独立身份审核，不据此替换默认背景。

页面保留实验运行时的XYZ账本来源记录，另显示当前原文件是否存在；恢复动作可查询原始28字节记录，查询时核对完整源文件SHA256。旧空场留出帧显示原文件缺失，提供XYZ账本而无opaque字节。Edge九会话、全簇视图、原字节/缺失分支核验PASS。Python AST与JS syntax PASS。服务只重启本轮8954，其他服务未操作。

## 结论边界

候选模型使用历史R/T与历史静态锚点补偿范围，不是新物理标定；FIT/CAL/HOLDOUT是同一连续录制中按3取余划分，互不重用帧，但相邻帧有相关性，不代表跨会话泛化。新空场为用户指定空场候选，尚无逐点独立身份GT。人体/家具语义准确率、关节与确认跌倒均未评估。页面继续显示独立新增簇、UNKNOWN身份；新背景仅诊断，不晋级默认。

历史报告与输出不覆盖；数据目录目前由既有captures/remote联接指向data/sessions，本轮后续只读取数据，无删除/清理/迁移/元数据重写，无Git写、采集、训练、部署。技能：C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。

## 证据

- ../2026-10-14_hfus_original_restore_r1/ARCHIVE_VERIFICATION.json 与 RESTORATION.json
- ../2026-10-14_hfus_original_replay_r1/ORIGINAL_REPLAY_CHECK.json
- ../2026-10-14_hfus_new_empty_221808_r1/NEW_EMPTY_ANALYSIS.json 与 background.npz
- ../2026-10-14_hfus_new_empty_action_support_r1/ACTION_SUPPORT_CHECK.json
- ../2026-10-14_hfus_original_restore_ui_r1/BROWSER_CHECK.json 与 RESTORED_ORIGINAL_SOURCE.png

当前验收：../evidence/2026-10-14_hfus_scene_source_empty_r1/ACCEPTANCE_V1.md
