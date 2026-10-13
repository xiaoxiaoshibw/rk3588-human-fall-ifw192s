# DET-02 R1 回传

时间：2026-10-07开始，2026-10-08完成（Asia/Shanghai）。执行者Codex，唯一writer；状态 **SUBMITTED，未 ACCEPTED**。现行验收 [v1](../DET02_ACCEPTANCE.md) 与先行计划已在实现前落盘，SHA见 [18_submission_sha.json](../evidence/2026-10-07_det02_r1/18_submission_sha.json)。

实际读取ponytail路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。分支 `codex/human-detector-models`，独立worktree，原主树master/HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`，含未跟踪5148文件基线00。本会话不改原树/旧证据/模型/生产参数，未commit/push/部署/采集。

## 集中诊断与实际变更

| ID | 根因/入口 | 本轮最小处理 | 保留行为 |
|---|---|---|---|
| E02/E03 | 原模型整场未接背景；含人自建模板会吸收静立人 | 独立无人233658配平→现有reference builder冻结→前景提取 | 自建图仅供ICP几何，不授予删除权；不改mainline |
| E04 | 裁剪/背景/配准/cleanup混合会误归因 | 五个固定输入分支，253帧同权重/阈值 | A精确复现原输出，公开分数下降 |
| E05 | 跨会话坐标/临时点索引可能污染模型XYZI | 选择后以ID恢复原current XYZ和强度，逐点相等断言 | 源28B、global rows、无效零点不改 |
| E06 | 全场最大分/定位邻域/anchor分数不等同GT | 分开记账，新增voxel/head诊断 | 不报无依据P/R，不称圆柱人体mask |
| E07 | 初次合成断言float32与double表示不一致 | 按输入Float32Array原值比较 | 原失败03日志保持，要求未降低 |

代码只新增 sidequests/human_detectors 的 prepare_background.py、reference_foreground.js、infer_background.py、reference_holdout.js、plot_background.py、voxel_probe.py、head_probe.py；复用当前JS为ignored artifact snapshot，源码/hash见18及foreground manifest。新增本单计划/验收/证据/回传，更新支线入口。

## 逐条验收

| ID | 自验状态 | 命令/证据及实际退出码 |
|---|---|---|
| E01 | PASS | 计划/00基线、所有本轮写入在独立worktree |
| E02 | PASS（离线） | prepare_background.py exit0，02日志/16空场54帧三法推荐/14绑定 |
| E03 | PASS（功能） | reference_foreground.js exit0，06日志固定digest；04合成检查exit0 |
| E04 | PASS（执行） | infer_background.py exit0，07日志/summary，1265次；A逐项等于原输出 |
| E05 | PASS | 每输入原XYZI相等、ID唯一有效；04逆向/非法矩阵exit0 |
| E06 | PASS（来源/诊断契约），精确P/R NOT_RUN | 08点计数、10体素、12分类头、13图 |
| E07 | PASS（作者），无独审 | 05现有35测试exit0、11 Python7项-W error exit0、04合成exit0；03失败保留 |
| E08 | PASS | 18/19；五源/所有配平/模型/核心snapshot SHA不变 |
| D01 | NOT_RUN | 不设备/采集/部署/物理/主线 |

## 结果与未闭合

空场模板去背景后workspace约2.3万点→3800–4500点，定位圆柱保留约99.7%；E最高真人位置分0.152/0.157/0.124/0.137，比B0.220/0.280/0.400/0.414低。样本前景化未让此KITTI权重稳定识别人。代表帧max32截断后定位邻域仅剩17%–23%点；分类头在NMS前已低于0.1。输入域适配/采样是待对照假说，不宣称已确定单一根因。

215607配平冲突保持；四组新registration诊断gate WARN，未接管正式链路。所有physical/extrinsic/runtime资格false。CenterPoint仍依赖BLOCKED；精确人体框/逐点GT/低姿态训练数据仍不足。下一项采样/输入单因素实验只记录建议，本轮不自行启动。

完整可审查报告：[README](../evidence/2026-10-07_det02_r1/README.md)。

最终原树基线对照：20_original_preservation.json观察到5个外部文档/诊断文件SHA变化，本会话无原树写入、无回滚；master/HEAD保留。五源数据/固定算法snapshot/模型/提交源码SHA全稳定，E08按本单数据与算法冻结范围PASS，不冒称所有其他会话停写。
