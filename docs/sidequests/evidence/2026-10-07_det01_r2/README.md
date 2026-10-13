# DET-01 R2 — 人工定位种子与 PointPillars 逐帧对照

2026-10-07 用户提供四段同一真人的位置、姿态、完整脚到头轮廓和手高度。接收为 [human来源的位置/姿态种子](user_truth_seeds.json)，不伪造精确逐帧3D框或逐点人体mask。原主线保持暂停；本轮只读取既有四组PointPillars CPU输出，未重跑几何候选主线，未改模型或阈值，未新采集/部署。

用户引用 montage_215607.png / montage_215643.png；本机仓库、已知worktree和visualizations内未找到文件，已请求绝对路径。**本轮没有独立看见这两张图片**，完整人体和姿态依据是用户文字确认；图对应的变换SHA尚未提供。以下暂把用户leveled XY当作本分支各TLS坐标的近似定位点，结论受这一坐标绑定限制。

## 逐帧结果

复用 r1 最终 `artifacts/static_four_r2` 的253帧输出，检查用户XY是否落在每个旋转Pedestrian预测框的俯视范围。只计算位置点覆盖，**不是框IoU、召回率、真人完整覆盖率**。模型原输出阈值0.1，不降低阈值追求命中。

| 会话后缀 | 用户姿态 | 真人定位点被框包含的帧 | 这些框最高分 | 框顶高度中位数（m） | 用户头/手高度（m） | 全场最高分框距真人定位点（m） |
|---|---|---:|---:|---:|---:|---:|
| 215540 | 站立 | 5/64 | 0.111 | 1.524 | 1.71 | 1.537 |
| 215607 | 举手保持 | 66/67 | 0.293 | 1.680 | 1.95 | 2.355 |
| 215623 | 举手 | 54/66 | 0.260 | 1.618 | 1.95；f2约2.03 | 2.331 |
| 215643 | 站立 | 16/56 | 0.134 | 1.574 | 1.71 | 1.355 |

真人定位点相关的预测框**全部低于0.3**。上一轮0.464/0.359/0.338/0.469全场最高分均不在用户真人站位上；不能将其称为真人得分。举手两段位置点更经常落在低分框里，但不能仅由这些比例声称“举手识别准确率更高”。站立两段位置点覆盖较少。

框底/顶已逆转模型Z偏移：`z_ground = z_model - model_z`，本轮 model_z=-1.73。举手两段这些框的最高顶分别1.781m、1.679m，均低于用户报告手高度1.95m；统计反映预测框高度不足，不是人体输入缺失的证据。没有精确宽度/长度/逐帧对应，暂不计算IoU。物理外参仍未验证。

PointPillars输入范围上限model z=1对应leveled z=2.73m，用户报告最高2.03m在范围内；依据用户XY，真人也在模型XY范围内。因此“整个人因模型范围被裁掉”不符合本次数值范围。还需用精确人体点mask检查体素单柱32点上限是否丢掉关键形状，不把位置邻域里的家具点冒称人体点。

## 下一步判断

这四段可以作为当前站立/举手检测的可信人工定位种子。先固定输入、取得图片路径及其坐标绑定，再针对真人逐帧建立精确框/点mask，核查预测得分、体素采样、score top-k和NMS阶段；人与家具粘连可作为对照项。不能把现行几何门预计HUMAN_CANDIDATE当成已经实跑，也不凭这一消息恢复W04或HF/GL生产。

低姿态样本仍缺，未来验证弯腰/蹲坐/躺需补独立样本；本次已有四段可先分析模型为何给站立真人低分。215607只使用有效TLS离线分析，原TLS-RANSAC 3.69cm冲突和正式入口不采纳状态保留。CenterPoint依赖仍BLOCKED，未新增成绩。

## 验证和追溯

现行验收表仍 [DET-01 v2](../../DET01_ACCEPTANCE_V2.md)；本轮补充 A04/A06，不新增主线工单。

| ID | 本轮状态 | 证据 |
|---|---|---|
| A01 | PASS：独立支线新增证据 | 原树未写；沿用r1基线，当前范围仅audit脚本/新r2证据/支线入口与回传 |
| A02/A03 | PASS：沿用既有解码/配平执行证据 | 未改模型输入；读旧predictions并记录SHA/transform SHA |
| A04 | PASS：253帧缓存输出位置核对 | location_audit 四份逐帧文件与 summary.json |
| A05 | BLOCKED：沿用原依赖阻塞 | CenterPoint未跑 |
| A06 | PASS：用户truth seed与模型来源区分；精确P/R NOT_RUN | user_truth_seeds.json，坐标图片绑定未验证 |
| A07 | PASS：旋转点包含/非法尺寸自检；GPU等价NOT_RUN | 00_self_check.log，exit0 |
| D01 | NOT_RUN | 无设备/采集/部署/物理验证 |

本轮状态 SUBMITTED，作者诊断，不称独审/ACCEPTED。命令：

```powershell
python -B -W error sidequests/human_detectors/audit_truth.py --self-check
python -B -W error sidequests/human_detectors/audit_truth.py --results sidequests/human_detectors/artifacts/static_four_r2 --truth docs/sidequests/evidence/2026-10-07_det01_r2/user_truth_seeds.json --out docs/sidequests/evidence/2026-10-07_det01_r2/location_audit
```

两条命令exit0。来源hash在location_audit/summary.json；源码/验收表/输入hash在02_sha.json。没有人体3D框或截图绑定时，本报告只能提供条件性的定位点诊断。
