

# HFUS-DEEP-RD-02 2026-10-15 回传（r1）

## 本轮信息

- 用户本轮授权深化聚类/学习/二维深度图调研并尝试；本轮仅本机离线研究原型，SUBMITTED，不ACCEPTED、不默认晋级。
- 唯一[验收v1](../evidence/2026-10-15_hfus_deep_routes_r1/ACCEPTANCE_V1.md)，SHA 73438486ecf001b9bb9435e6418fedd3056dd5c5e2c445c1f411bca3364c87b9；上一工单N01–N11不改。
- 单writer当前Codex；独立OpenCode opencode-go/deepseek-v4.1-flash plan只读复审（edit/bash deny，snapshot=false），非独立实验重跑/人审。
- 起始branch/HEAD：master / c21c443b0befe559e08283edb0efc2af02dcc6b8；dirty状态GIT_STATUS_BEFORE/FINAL及RUN_MANIFEST原源/模型SHA，SOURCE_FREEZE_R2记录新源实际执行SHA。
- 实际技能：C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md，另读取其scikit-learn/matplotlib参考技能。

## 集中诊断与根因覆盖

数据→冻结B→4种组分→同选择器独立窗口→当前粗槽/点成员；投影→视场/CSR/最近层→轴深度→共同分母侧表，实际调用者/检查顺序见[00_diag](../evidence/2026-10-15_hfus_deep_routes_r1/00_diag.md)。首次HDB默认copy警告、补充helper同名导入失败均保留，前者显式copy=True，后者唯一消费者显式文件路径加载；没有降warnings或执行旧训练main。独审D1–D9集中响应见REVIEW_RESPONSE，不修改旧结果。

## 实际变更

仅sidequests/human_fusion_lab_next/deep_routes/r01新增probe.py、summarize.py、depth_probe.py、audit_addendum.py及本轮证据；每文件SHA见SOURCE_FREEZE_R2/EXECUTED_SOURCE/ARTIFACT_INDEX。旧pointset/旧lab源码、模型与原数据前后SHA相等，无原页/控制台/服务/默认/驱动/网络/部署/训练/HR09/Git写入。

## 逐条验收

|ID|synthetic/offline证据|作者结果|
|---|---|---|
|Q01|原论文/官方实现研究RESEARCH.md，架构与环境边界|PASS；高级官方模型推理NOT_RUN|
|Q02|18原SHA重核，2206来源帧，148诊断帧，原源/模型不变|PASS；数据已消费非未见集|
|Q03|1332表示帧+444轴深度及全部分辨率CSR，反例/裁外/孔洞/分母侧表|PASS本机表示契约；物理标定NOT_RUN|
|Q04|592方案帧源成员及90共同可算转移，窗口独立状态|PASS执行；非完整会话晋级，人体语义BLOCKED|
|Q05|580次CPU推理Torch/ONNX一致，原权重冻结|PASS；不是语义或关节推理，不训练|
|Q06|逐帧/真实图/方向变化合成诊断/复现脚本|PASS范围；人体/关节GT指标BLOCKED|
|Q07|最小反例、实际进程退出、源SHA、只读AI复核|PASS本机交付；非ACCEPTED|

实际命令与退出见COMMAND_RESULTS.json；Python均-B -W error。首pilot1→新attempt_r2为0，汇总0/轴深度0，补充首次1→修复0，独审两轮0；不以总数代替要求。

## 未闭合与限制

HDBSCAN轴缺测更多；学习连边总体变化小、90共同转移有局部信号但最差仍约1m；距离图选中源点减少且全可算槽P95恶化。最近层全景压缩严重，固定裁剪漏8%–11%，需要真实扫描视场适配/有效mask/多深度与3D互补，不能补造测量。148帧窗口不能代替1934全会话、原3空场不能代替90留出；人体/家具/实例/关节GT缺，未下载/训练新模型、未激活ML/HR09，物理/板端/部署/泛化NOT_RUN。上轮EXE/旧空场缺口未被解除。

## 交给独立复审

[FINAL_REPORT](../evidence/2026-10-15_hfus_deep_routes_r1/FINAL_REPORT.md)、[RESULTS](../evidence/2026-10-15_hfus_deep_routes_r1/RESULTS.md)、REVIEW_R1/R2、REVIEW_RESPONSE及完整产物索引为本轮交付。下一实质实验方向是源绑定标注与学习语义/实例前端、结构预测/因果时序消融，不自动启动训练或替换默认。

