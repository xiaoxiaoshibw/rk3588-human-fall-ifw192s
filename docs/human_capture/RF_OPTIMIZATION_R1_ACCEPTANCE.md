# RF-OPTIMIZATION-R1 唯一验收表 v1

2026-10-10，依据用户本轮明确调整：暂停 HUMAN-FUSION-OFFLINE-R1，先执行 R1/R2 离线研究。Codex 唯一 writer；OpenCode `opencode-go/deepseek-v4.1-flash` 只读独审，修复仍由 Codex 完成。所有代码、数据衍生物和模型仅位于本轮 evidence/workspace；不激活 HR-09，不写 ML/ 或生产模型。设备、物理、采集、部署不在本单授权内。

| ID | 验收要求 |
|---|---|
| RFO-01 | branch/HEAD、tracked+非忽略 untracked SHA 基线，提交后核查受保护文件；明确 ignored 覆盖边界 |
| RFO-02 | 按真实索引逐项审计 51 维、单位/坐标/实现差异、常量与相关性、训练/使用域、旧验证泄漏 |
| RFO-03 | 候选源帧/rank/点数/位置/特征可复现绑定；逐候选误判清单；背景删除/碎簇/粘连/关联仅在有对应 GT 和源点时归因，否则 UNKNOWN |
| RFO-04 | 困难正负样本与标注来源审计；没有 source:human 候选标签不得称金标；建立人工复核队列，不能把位置规则产生标签当真实困难样本补充完成 |
| RFO-05 | 相同簇级数据 RF-v2(51)、RF-v3(51+18)、HistGradientBoosting(相同69维)实际训练；冻结 baseline，有限调参包含 depth/leaf/features/class_weight；不预定赢家 |
| RFO-06 | 外层留会话、内层 GroupKFold 调参及阈值选择，报告 split 清单、重复与单类问题；人员/场景未知或重复不能声称新人/新场景泛化 |
| RFO-07 | 留出 permutation importance、分组消融、相关性、PR 数据和阈值扫描；不根据外层结果再选生产阈值 |
| RFO-08 | 距离/姿态/会话及少点分层，缺失 strata 记 BLOCKED；本机特征/推理耗时与模型大小实测，不冒充 RK3588 性能 |
| RFO-09 | 预注册资格门：独立 source:human 候选标签；未见人员和家具/场景；站立/静止/弯腰/遮挡及 0–2/2–4/4–6m 各有覆盖；每层至少2独立会话、总体至少3独立场景。锁定内层阈值后每层 precision≥0.95、recall≥0.90，报告会话级重采样区间。缺数据即 BLOCKED，观察数字不能放行 R3 |
| RFO-10 | OpenCode CLI 实际只读独审、原文存档；FAIL 修复后复测/复审，不能以 prompt 代替复核 |
| RFO-11 | 非有限值、少点、PCA退化、分组重叠/重复、阈值与实际模型维数检查，-B -W error；冻结生产与旧证据 |
| RFO-12 | 按 RETURN_TEMPLATE 逐 ID 回传，R3/R4 保持 NOT_RUN；Track 维持独立决策为下一阶段契约，本单不改 Track |
| D01 | RK3588/设备/物理/部署/采集 NOT_RUN |

探索集为现有 C1 六静态会话、位置关联弱标签，只支持同房间探索。模型选择使用内层平均 balanced accuracy；阈值以内层 precision≥0.95 时最大 recall，无法达到则内层最大 F1并明确未达标。外层指标仅报告，不用于选择模型/阈值或特征。相邻帧不当独立统计样本。18项附加特征预先冻结：五层归一化高度占比、五层XY稳健宽度、层宽变异、整体PCA三比例、中心0.3/0.6m邻域平面度和0.6m散射度、点数×水平距离²密度代理。距离平方修正只是代理假设，不代表传感器物理校准。

运行前补充：两个远距离会话无负候选。单类验证折仅报告存在类别召回均值（两类时等于 balanced accuracy），不能测该折 precision/误检泛化；记录 validation_classes。单类训练折拒绝运行。此覆盖缺陷不通过重命名、复制空场或随机帧切分填补。
