# CL2-10 Codex 交叉裁决 / 2026-10-09 Asia/Shanghai

未解决逻辑FAIL：无。**总体 BLOCKED，T107修复资格不具备；有效TLS/生产仍BLOCKED。** 这不是算法修复PASS，也不以46项测试替代用户的八项停止条件。

## 真实独审事实

首轮实际shell引号错误，exit2、没有模型事件/会话；04_opencode_raw.*、opencode_completion.json及空报告均留存，不计独审完成。短提示词重试未降低read白名单：实际CLI1.18.35 / opencode-go/deepseek-v4.1-flash / session ses_eded7a292ffe2Lq0YBvy3Wax56，进程exit0、完整export0、finish stop、AUDIT_COMPLETE。实际模型由assistant providerID/modelID复算，未换模型/供应商/全局配置。

初审原文04_independent_review_02.md，实际同会话补审04_independent_review_03.md；后者原IO/argv/export/model与exact新文件allowlist保留。有效工具只有read，其余bash/edit/write/task/network等deny。独审员没有实际执行数值、测试或SHA；其UNKNOWN边界保持，由Codex执行层独立封存，不伪称双份执行。

## 动作项与裁决

| 独审意见 | 实际关闭方法 | 裁定 |
|---|---|---|
| 当前09C selector与原报告selector混读 | root末尾补记及04_cohort_integrity：原报告dd1b58=frozen，09C d0b3e3仅搜索/回归；TLS诊断原ROI/源行不经过selector，TLS/quality核心代码一致 | CLOSED |
| 四ROI身份证据不够显式 | 原report ground_confirmed=false / ground_identification=algorithm_candidate明确补记；局部拟合不证明地面身份 | CLOSED；物理UNKNOWN保持 |
| “全部TLS-valid”成功集合未打包 | inputs/cohort的原normal比较/cluster索引与CL2-08既存binding SHA匹配；11人体集合及10valid集合逐项相同；空场模板/其他capture不属原预注册cohort，非按新结果排除 | CLOSED；范围限定CL2-07 cohort |
| 加权算法身份与数值门混同 | 独立SVD直接复算：帧等权角差0.000032082°/offset7.102e-7m通过原数值门但72 P95仍FAIL；ROI等权角差0.305710216°/offset0.005684m数值FAIL且144 P95 FAIL | 已准确收窄；原AB数值不改 |
| 刚体控制区分力低 | 承认是数学恒等式/回归控制，不能检验物理姿态真值；没有以其排除外参/ROI对应误差 | 限定范围，非FAIL |
| SVD共享FIT/锚点 | 是独立求解路径，不是独立数据或物理GT | 限定范围，非FAIL |
| 性能波动/无绝对时间界 | 保留4.038/7.183s首测；同SHA原09C/本轮副本配对三次，结果精确相同。不能推测热/频率原因或板端保证 | 非算法退化证据，生产性能NOT_RUN |
| T110/T111审计时仅前置状态 | actual model/debug权限/raw/export/marker实际核验完成；最终return/manifest由finalize.py在本文件后执行，不能预判seal已完成 | 等实际封存后才闭合 |

初审和补审没有未解决逻辑FAIL。补审对T100/T108两个缺口明确CLOSED、数值门区分ACCURATE；它仍不假装重算SHA。首次空报告保留，04_independent_review.md最终作为索引追加，不把初次CLI失败改写为成功。

## 本轮结果的实质

原P95=50.291869360mm、独立标量邻值低端50.227390722mm>50mm，数学拒绝正确。共同平面与测量局部结构不匹配的数值贡献可复现，但algorithm_candidate区域身份不等于真实地面；真几何/测距/混合表面/提取链仍缺GT/bag区分。重权重失败转移，局部四平面不可作为一个刚体TLS。没有符合原定义且机制充分的修复候选，故T107 BLOCKED，不编码生产或shadow修复。

原11人体cohort点域及原门复现、10valid保持；历史留出已读，非盲测。没有新修复后泛化PASS。原50mm/30mm/点数/支持/退化/数值门全部保持，源数据/GT/原证据不修改，未B2/B3/设备/采集。

下一步只能规划取得原bag和原现场五点独立身份/相对高度证据；对应关系不足时继续BLOCKED。不能为了“完成开发”做测量补偿或用这段验收数据优化新的验证定义。
