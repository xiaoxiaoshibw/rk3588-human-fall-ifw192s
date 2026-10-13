# Registration gate 冻结复核

结论：原 `reg_gate_v1` 仍 **WARN / DEGRADED / SPARSE_CORRESPONDENCE**。49.652981% 确为不足；接近边界不构成PASS或放宽门理由。当前生产 loader 另为 **STALE / REFMAP_DRIFT / METHOD_STALE**，原因是统计修复改变全文件SHA；保持SAFE，未重绑定或写旧artifact。

## 精确分子/分母

- source strong fineStatic(0.06m)：11,959；target occ≥0.9 fineStatic：17,053，其中15,537有有效normal。
- 最终固定0.08m球门：9,897有效对应（82.754% source）；1,684无target、378最近target normal无效；合计2,062 source没有用于求解的pair。
- 60% trim：floor(9897×0.60)=5,938；另外3,959个有效pair仅因固定残差trim剔除。
- gate ratio=5938/11959=49.652981018%，并非 raw match ratio。50%需 ceil(11959×0.5)=5,980，即多42个keep；相同60% trim需≥9,967 raw pairs，比现在多70。
- 缺口=0.347018982 percentage point；不是42点修改就能构造PASS，必须来自既定协议的真实对应支撑。

## 成因分解与可证边界

| 面 | 证据 | 判断 |
|---|---|---|
| correspondence coverage | 1684球门外、378无有效normal，60%trim以后49.653% | 直接可复现的有限支撑不足，是精确gate根因 |
| reference coverage | 2062无效pair中813距occ≥0.5 coarse centroid<0.12m；410连0.30m内coarse支持也没有 | 入图层/normal/fine采样支撑不等价；未观察物理表面不能假定存在 |
| 动态污染 | source来自strong长期占用；无每点动态GT | UNKNOWN，strong不证明静态，更不证明人体不存在 |
| occlusion | 无跨会话射线/可见性GT | UNKNOWN；不能用稀疏对应直接断言遮挡 |
| FOV | source仅sector2–5有支持；sector5 2337source/1137raw/505keep，明显弱于sector2 1869/1845/1259 | 测得空间不均匀，实际FOV/遮挡/场景变化归因UNKNOWN |
| leveling/registration residual | fit p50=14.522mm/p90=57.301mm；holdout p50=11.088mm；condition≈104.272 | 已有pair上残差良好，但条件化残差不能证明未配对点安全；不换解 |
| voxel discretization | frozen coarse/fine bins、51个最近fine距离处于79–81mm附近 | 有边界点；不能证明它们全由量化造成或能补70pair，未改变网格做干预 |
| sample support | fine source n min1/median118/p90=622/max1250003；11,959 samples空间/时间相关 | 数量实测；不能假设iid或编造CI证明统计等价 |

无效pair中1695在0.30m内有fine近邻，367没有；这些桶可能交叠，不能相加当互斥物理根因。原始11959样本、状态、近邻距离、normal、trim身份保留于 `07_gate_samples.json`。

判定：**这是接近门的真实协议支撑不足；现有单pair数据不能把它裁决成无害统计边界。** 即使数值距离门小，预注册50%保持。matcher/ICP/normal半径/trim/PIPE/leveling/R/t均未修改，gate脚本只做固定解诊断；R3.6回归另按原数学复算，不用于替换解。

artifact id=`ae5c8f4c021e91665c9e23cedd66730122d5f0552fd794de86a9b5f99e7a5e66`。transform/旧code binding/当前code binding见06.registration；matrix、method文件SHA未变。注册/参考图数据digest未变，但全文件builder身份变化使旧loader如实STale。

