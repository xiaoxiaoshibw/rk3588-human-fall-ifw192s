# RF_MODEL_COMPARISON — R2 候选，不推广

2026-10-10，阈值固定0.55，未调test。

- v1 SHA: `4c83db116fe0742d5c1cca8360de6bafcc4ac9abae3910984beabea8d85bfe68`
- v2 SHA: `1b7a587e8961786f6dec21840e50ff3fb0da8a2b3c52f19aa8058c7fa530a65a`
- SPLITS SHA: `747f6af7c23ced7fe606068dc118b027841431b1ce67d2607f37748184eb856d`
- sklearn→JSON概率最大差: 0.0
- JS同51维输入概率对拍见runs_03/MODEL_JS_PARITY.json。

| 会话 | split | GT点集样本 | v1召回 | v2召回 | v1FP | v2FP |
|---|---|---:|---:|---:|---:|---:|
| cap_20261010_175227 | train | 1216 | — | — | 1216 | 0 |
| cap_20261010_175429 | train | 258 | 100.0% | 100.0% | 0 | 0 |
| cap_20261010_175553 | val | 99 | 100.0% | 100.0% | 0 | 0 |
| cap_20261010_175804 | train | 11 | 100.0% | 100.0% | 0 | 0 |
| cap_20261010_175943 | train | 6 | 100.0% | 100.0% | 0 | 0 |
| cap_20261010_180235 | stress | 71 | 100.0% | 87.3% | 0 | 0 |
| cap_20261010_180337 | test | 12 | 100.0% | 100.0% | 0 | 0 |
| cap_20261010_180557 | test | 53 | 100.0% | 100.0% | 0 | 0 |
| cap_20261010_180751 | blocked | 0 | — | — | 0 | 0 |

GT精确compact点集裁剪；S1 1464家具对象去掉同帧同点集重复248，得到1216负例，另有510 PERSON样本。BACKGROUND未混入家具。
S1训练集FP改善只是拟合；独立家具负例test缺失。S6压力样本v2漏9/71。缺跨演员/新场景信息，S9无可用绑定GT。
读取S1样本后外部移走其GT；train_02保留已导出点集特征/原GT及会话SHA，但原GT目前无法从当前store复验，来源资格BLOCKED。

**MODEL_PROMOTION=BLOCKED。保留v1；候选仅存evidence，未接管生产。**
