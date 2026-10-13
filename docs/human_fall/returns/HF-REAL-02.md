# HF-REAL-02 追加回传

## 2026-10-13 / R1 / Codex唯一writer / SUBMITTED

用户指定空场131958，要求完整锁定人体/骨架并展示倒地检测过程。[唯一v1](../evidence/2026-10-13_hf_real_02_r1/ACCEPTANCE_V1.md)/[报告](../evidence/2026-10-13_hf_real_02_r1/FINAL_REPORT.md)。可查看 http://127.0.0.1:8931/ ，原8929/R01保持。

RS01/02/06/07自验PASS；RS03工具PASS/全人体保留BLOCKED；RS04完整纯人体FAIL（f10家具污染）；RS05几何骨架支撑显示PASS/解剖关节BLOCKED；RS08已跑数学/core PASS、真人长遮挡/重置NOT_RUN；RS09真人GT/泛化BLOCKED、独审与设备物理部署NOT_RUN。未ACCEPTED。

空场97帧独立配平GOOD，初始静态匹配65.2%FAIL保留，新注册复用existing fixedICP，仅排除活动区的上午0–4初始化，5/10留出原门通过，match94.77%；不把旧ICP_SAVED字段当当前验收。164真人帧均关联，空场0关联/0事件仅self-reference sanity。f72/7.46s一次prototype告警，至f131保持，起身后撤销。core confirmed关闭；骨架未进入告警语义通过门。

局部身体轴13粗部位都有真实源行绑定；45帧13槽有点非关节精度，3帧主轴歧义0节点。站姿.50m躯干圈修正11帧，原版污染证据保留，新版仍f10残留；不能称完整人体/全关节成功。

基线master/026e06303f60ed1bbe4ddc4d037836db68da6d27，19253全SHA/non-atomic/errors0/drift0；只新r02/本证据/return/授权入口。源SHA/end/checks见完整报告。2数学测试/全261帧源行/支撑核验、原HF06 20tests、真Edge WebGL八阶段/empty/控件/支撑高亮/非法400完成。未派独审，不冒称独立验收；没有Git写/采集/部署/生产/GT/模型/原capture变更。

ponytail C:/Users/30680/.codex/skills/ponytail/SKILL.md。后续优先纯人体成员/关节GT/困难负例；过程已可查，但用户要求的完整准确锁定未完成。
