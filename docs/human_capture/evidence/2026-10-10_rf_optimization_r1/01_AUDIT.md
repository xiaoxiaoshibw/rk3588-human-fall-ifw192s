# RF-OPTIMIZATION-R1 失败归因与数据审计

本轮 PC 离线隔离研究，代码只写 workspace；用户要求先RF优化，统一融合暂停。起始 master / 347a5bf05ee82766436382f4fc3d1a8ed15c1132。`00_baseline.json`覆盖7755条 tracked+非忽略untracked、约23.69GB；不覆盖忽略文件。基线脚本结束时有未关闭输出句柄 ResourceWarning（exit0），记录真实警告；JSON已成功写入，后续源码脚本使用上下文关闭文件，不把exit0当warnings检查通过。

## 已确定问题

1. `pc_apps/human_ml/train_person_rf.py` 的 v1正样本为带auto标签的整帧ROI，负样本为单一空场整帧，生产消费者则对背景差分候选簇提特征。训练/应用统计单位不一致，v1的整帧准确率不是人体候选精度。
2. v1 `uniq+uniq` 复制空场，再把两个副本分给空场fold和最远person fold。相同向量跨折，直接泄漏；不重新修改旧报告。新研究只使用簇级数据，检查跨会话精确/round6重复，不复制样本、不混整帧域。
3. FEAT_NAMES 从40起错位。Python先降序sort eigenvalues却没有同步翻转eigenvectors，37/39轴含义互换。JS37–39直接置零；Python41为径向距离std、JS41为水平半径RMS；Python协方差n−1、JS用n。JS PCA三次方程实现还需专门数值等价验证。现有rf_person.test.js并不能代替未来69维模型的推理契约。
4. C1簇JSON fv与源点重提完全一致，强度已是原始数值（例如均值862.37），旧`cluster_fixed`/`build_cluster_set`又除0.001会放大1000倍。新研究使用实际源点量纲，不对已复现fv再缩放。不存在修复生产JS/模型的授权，本轮保留实现差异作为未来接入门。
5. C1旧扩维实验v2e曾构建53维但没有实际传入训练，旧二审明确披露。新模型用 `n_features_in_`、columns清单和69维检查证实真实训练维数，消融实际删列重训。

## 51维真实定义（0起始，保留数值基线，不篡改旧实现）

| index | 实际定义 | 单位/注意 |
|---|---|---|
| 0 | n_pts | 点数，随距离/遮挡变化 |
| 1 | 恒定10 | 非有效区分特征 |
| 2 | max(n,2000) | 与点数高度相关 |
| 3/4 | intensity均值 / log10(std+1) | 原始传感器强度；不可再次×1000 |
| 5–7 / 8–10 / 11–13 | XYZ各10/50/90分位 | m，XY位置可记住房间/柜位 |
| 14–22 | 固定Z带占比 | 无量纲；[-1,.3),[.3,.6),[.6,.9),[.9,1.2),[1.2,1.5),[1.5,1.8),[1.8,2.2),[2.2,2.6),[2.6,1e9) |
| 23–25 | XYZ均值 | m，软件配平域 |
| 26–31 | xx/xy/xz/yy/yz/zz协方差 | m²，Python分母n−1 |
| 32–34 | PCA三降序特征值 | m² |
| 35/36 | λ0/λ1、λ1/λ2 | 下限1e−9；近退化值可极大 |
| 37–39 | eigh原升序轴的abs(z分量) | 与降序特征值配对错位；JS全零 |
| 40 | λ0/λ2 | 原名r_xy_spread错误 |
| 41 | std(sqrt(x²+y²)) | m，原名z_range错误；JS为RMS |
| 42 | Zp90−Zp10 | m，原名z_tilt_log错误 |
| 43 | log10(abs(42))，高度差≤.01则0 | 原名upright_score错误 |
| 44 | z∈(1.2,2.2)点数 / z∈[.4,1.2)点数 | 原名i_p10错误 |
| 45–47 | intensity10/50/90分位 | 原名错位 |
| 48 | 水平距离<3m点比例 | 原名pca_shape_spread错误；位置捷径风险 |
| 49 | Zp90 | 与13完全重复，原名n_pts_ratio_near错误 |
| 50 | 三特征值和 | m²，cov trace；原名z_max错误 |

样本相关性和常量索引见`workspace/prepared/feature_audit.json`。保持51维旧值供真实消融，不借修特征名悄悄换算法。源数据n<10返回全0；旧提取器缺少非有限输入校验且LinAlgError后ev未定义，本轮边界先拒非有限，低点/退化新特征有测试。完整51维未来接入仍需新版本schema。

## 候选与标签边界

1239行=915弱正+324弱负，六段同房间站立，两个远段没有负候选。每候选绑定session/frame_index/原始frame_seq/rank/源点局部索引SHA，重提51维全列对照源fv；固定旧C1 R/T仅是复现的软件坐标，不能作为现场角度或光学窗口到点云原点的物理测量。

标签来自历史位置规则，不含可靠候选 source:human 签核；将其明确标 `UNVERIFIED`。输出逐候选错误和人工复核队列，不把远离人体坐标自动等同家具真值。本轮没有人工签核的新困难正负样本，因此真实补充完成为BLOCKED。未覆盖低姿态/弯腰/遮挡/新家具/4–6m，不能从静态近场外推。

候选先经Z带、空场最高包络+.25m、5cm格连通、≥30点与top4裁剪；因此“人体已被背景删掉”和“碎簇/粘连”的消失样本不在当前训练集。对保留候选可以记录分类器与弱标签不一致，但没有逐点人体GT不能确定碎簇/粘连的因果。来源点哈希证明复现，不证明候选完整。Track未重放或修改，候选级错判不冒充Track丢失根因。缺失阶段归因均UNKNOWN/BLOCKED。

时序契约留给后续：RF只提供候选人体似然；已确认track由独立有限TTL和观测逻辑维持，不凭单帧低分立即消失。本轮不实现R3/R4。

## 验证方法和限制

内层三折GroupKFold只见外层训练会话，参数与阈值由内层选择；外层完整留会话。模型数、参数网格和18项特征在运行前冻结。外层 permutation仅描述、不用于选特征；删除layers/PCA/位置三组分别重训。scikit-learn说明[留出permutation importance和相关特征限制](https://scikit-learn.org/stable/modules/permutation_importance.html)，[分组划分](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data)用于防止组内样本跨折。两次permutation仅作小预算探索，不做显著性宣称。

每折内层阈值不同，因此pool只作描述，不是一个可部署阈值的性能。两个仅正折不能估计真实误检率；同房间/同人员重复，不等于跨人跨景。报告原始计数和会话结果，不用逐帧Wilson扩大独立样本量。可靠资格门RFO-09保留BLOCKED，不生成虚假置信区间。
