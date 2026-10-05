# Change Proposal / P02 v2

用户明确四个区域全部参与算法，截图编号与当前annotator ROIS一致。旧单#3角度容易只拟合局部；这次从同A/C全部193帧冻结四区联合源行，B不拟合。四个区域每侧内缩2cm，XY在旧Ry26+Z1.34显示系选一次，finite/nonzero，保留全高度，不用待估Z/残差筛选，不更改公式或门。

使用原始点等权，每区点数公开，不假装四区等权。复用已读R2纯数值RANSAC861/seed20261001/.05、TLS covariance、centeredSVD，不新算法/optimizer/采样变体。三估计器吃相同source float64数组，统一normal符号，返回source→display Rx@Ry/tz=d。统一残差使用全冻结域及逐区全点，保留失败；再三FIT区→一个未参与此fit区的四折TLS诊断，不称为未见最终物理holdout。

范围：本新evidence脚本/不可变源点/结果，用户明确要求的06_PREVIEW.html模型与四色源点/逐区残差表。原3D annotator、原capture、物理1.14记录、旧结果不改。当前HTML修改前再核SHA，遇外部变化停止覆盖。单writer Codex研究，不部署。回退用00_HTML_BEFORE.html，旧P02 v1表保存为00_ACCEPTANCE_V1_BEFORE.md；现行唯一表升v2因用户扩大点域，历史条件不追改。

| 操作 / 边界 | ID | 预期 |
|---|---|---|
| A/C/B × 四区 × 全frame | C | A/C union，B0拟合点，源行/session/region/frame保存；无漏区/重复行 |
| 旧名义XY vs新参数/矩形 | C | source行先冻结，算法/绘图参数不重选拟合输入 |
| RANSAC/TLS/SVD | D | 同数组同SHA；无offset gate/inlier子集精修/cap；全点RMS/P95 |
| 全局拟合 vs单区偏差 | D/E | 逐区表；全局均值不替代单区；PASS/FAIL保留 |
| 留一区三FIT | E | 每折不含该ROI，固定另三块，不筛待验证行、不调门 |
| 数值成功 vs物理/部署 | E/S01 | 仍observed display模型，physical/runtime=false，1.14不覆盖 |
| 原HTML/source变更/重复输出 | S01 | initial实际SHA、独占新输出，HTML更新前核不并发覆盖 |

ponytail与scientific-toolkit已读。数据门仍RMS≤.03、P95≤.05、support≥.8、至少20点；consensus2°/.03m只工程参考。
