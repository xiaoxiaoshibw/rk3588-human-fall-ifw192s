# P02 四区联合离线配平 / 唯一验收 v2

2026-10-04 用户要求四个区域全部参与算法，因此点域从单#3扩大为四区，v1原文保存在evidence/2026-10-04_p02_four_roi_r1/00_ACCEPTANCE_V1_BEFORE.md。只研究与用户指定HTML，不扩大设备/生产权限。当前SUBMITTED（作者自验）；[结果](evidence/2026-10-04_p02_four_roi_r1/08_REPORT.md)。结果按固定ID，作者自验不冒称指定独审/ACCEPTED。

| ID | v2要求/检查 | 当前结果 |
|---|---|---|
| P02-C | A/C全部193帧四ROI union源行；当前annotator SHA/ROIS/旧显示matrix绑定；2cm内缩/finite/nonzero/全高度；B不入FIT、无跨区重行；实际meta/bin/冻结point与row SHA | PASS（作者自验）；02完整冻结/05全源行与bin精确对应，392196点 |
| P02-D | 同source数组给既有raw RANSAC/TLS/SVD，统一符号、全域/逐区RMS/P95/support、source n/d/pose差；公开原始点等权；consensus2°/.03m参考不当物理精度 | PASS（作者自验）；03同域三方法，四区联合拟合质量PASS，最大normal差.74136°/d差.000781m |
| P02-E | R=Rx@Ry/source→display、yaw/tx/ty0、tz=d、Rn=up、proper/inverse/signedZ；全frame source TLS spread、三FIT区留一区四折全点诊断；FAIL保留；1.14物理记录与数据显示模型分开，资格false | PASS（离线数值/如实报告）；留一区3/4 FAIL保留，物理/外推BLOCKED、P1 NO |
| S01 | 仅新evidence与指定HTML，旧版/旧模型证据保留；HTML更新前SHA、源点/共享数据不变；三算法同帧横排/四色ROI/逐区表；ponytail、作用范围、自验，独审和真实browser单列 | PASS（范围/页面逻辑作者自验）；06三列九帧/四色/逐区表，指定独审/实际browser NOT_RUN |
| D01 | 不设备/采集/部署/网络/driver/正式外参写入 | NOT_RUN |

冻结数据质量参考20点、RMS≤.03m、abs P95≤.05m、support(.05m)≥.8；不为PASS裁尾。三个其他区域是用户指定的研究地面域，不能凭截图升级为穷尽行级物理真值。四区均已曝光，因此留一区是几何泛化诊断，不是最终未见holdout。P1放行/真实物理另评，不自动启动下游。

## R3 分区/逐帧地面建模（2026-10-05 追加）

范围：只写 `evidence/2026-10-04_p02_r3_region_frame/` + 本表 R3 条目 + `returns/P02.md` 末尾追加。证据：[09_REPORT.md](evidence/2026-10-04_p02_r3_region_frame/09_REPORT.md)。状态 SUBMITTED（作者自验），指定独审/真实 browser NOT_RUN。

| ID | R3 要求 | 当前结果 |
|---|---|---|
| P02-F | 分区诊断完整：6 对成对矩阵、8 分区平面参数、193 帧×4 区残差序列、三项分解占比、类型A/B/C 结论与量化依据 | PASS（作者自验）；四区自身拟合全 PASS 数据门，6 对互预测全 FAIL 保留，8 cell 两 session 平面稳定（d 差<5e-5m），类型 C（max夹角9.396°/max d差0.23283m、分区逐帧std>0.05°或5mm；重尾形态如实保留） |
| P02-G | 模型 I 分区平面集：存储格式、联合评估与单平面对照、region 查表与回退规则文档化 | PASS（作者自验）；04_MODEL_I.json 每区 source-frame 记录+footprint，全点 RMS 0.01335/P95 0.02632/support 0.99870 PASS，对照单平面 RMS −0.00557/P95 −0.01160/support +0.01308；消费接口与显式 None 回退文档化 |
| P02-H | 模型 II 逐帧序列（如类型C）：193×4 参数+协方差、时变性报告、消费接口草案 | PASS（作者自验）；03_PER_FRAME_MODEL.npz 772 条 n/d+ordinals+协方差（PPCF 型一阶 delta，PSD），05 逐 cell median/MAD/相邻差 MAD/线性趋势/robust CUSUM，重尾形态如实保留，查表优先接口 |
| P02-I | 全部分析只用冻结 392196 点或其 R3 切片；不裁尾、不调 ROI、不降门；FAIL 保留 | PASS（作者自验）；只用 R2 冻结 NPZ，annotator/ROI/门未动，3.1a 六对 FAIL 与 R2 留一区 FAIL 全部保留在 07_REPORT.html |
| S01 | 范围与页面逻辑自验；ponytail 声明；指定独审与真实 browser NOT_RUN | PASS（范围/页面逻辑作者自验）；00_BASELINE.md 输入/保护 SHA、HEAD、用户差异全录，ponytail SKILL.md 实际读取路径已载；Node 检查含 404/坏数据显式拒绝 |
| D01 | 不设备/采集/部署/网络/driver/commit/reset/生产外参写入 | NOT_RUN |
