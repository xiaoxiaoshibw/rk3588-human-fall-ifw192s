
## 2026-10-15 R1 · Codex · SUBMITTED

- 唯一验收：`docs/human_capture/evidence/2026-10-15_hfus_markov_r01/ACCEPTANCE_V1.md` v1 / SHA256 `0c412e925990f1e3d95a5a429c7e5b90ec62fc60073141ec83f8bb7299e87832`。
- branch master / HEAD c9c4ee421cb0c8a3e4590b8f5730828b093c759a；起始完整dirty状态BASELINE_STATUS，相关tracked/untracked源码SHA在BASELINE；VERIFICATION_R1显示检查时已有基线文件变化0。只新增实验侧链/证据/回传并追加HC入口，不改用户原差异。
- ponytail实际读取：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。另scientific-toolkit-skill、matplotlib；论文子代理paper-lookup，独立审查子代理只读。无OpenCode派工，不能冒称其审核。

### 集中诊断与根因覆盖

M01/M02：旧动作RF占位0不可评估，改用既有JS RF+真实强度重算；E0 uint8 selected验证二值后转bool，R1失败保留。M04/M06：按sid+ID缓存/解码/切换分母，时间倒退/长隙/显式reset、缺失、交错ID、非法输入和前缀均检查。M05：HSMM零质量拒绝及真实秒≤.02子步，保留近似上限。M08：异步点云先清场/绑定sid-fi-token、infer代次/restore失效、呈现帧才能复核；探索参数与冻结结果显式分开。独立只读审查复验无新实质缺陷，详REVIEW_R1。

### 实际变更

`sidequests/human_fusion_lab_next/temporal_markov_r01/`：NumPy时序/原RF batch/固定实验与敏感性/10测试/Demo/九报告。`docs/human_capture/evidence/2026-10-15_hfus_markov_r01/`：baseline、唯一表、失败/成功运行、原输入/输出、图件、浏览器证据、代码SHA索引。HC README仅新增本工单入口；原GT、模型、数据、生产代码未改。逐文件提交SHA以DELIVERY_MANIFEST为准，不Git提交。

### 逐条验收与命令

|ID|层级|结果|证据|
|---|---|---|---|
|M01|offline|PASS|BASELINE/INPUT_MANIFEST/VERIFICATION|
|M02|offline|PASS|features/FEATURE_STATS/八段PNG-SVG|
|M03|offline/mechanism|PASS|逐帧原RF与滤波/MC|
|M04|offline/mechanism|PASS|10单测/前缀/九会话新推理相等|
|M05|offline/mechanism|PASS|HSMM时间/零质量/快慢低位反例|
|M06|offline/mechanism|PASS|E1–E6执行，真实条件不足单列|
|M07|offline|PASS|描述性AB/PC计时/三档敏感性；语义与实际延迟未知，简单滤波独立计时NOT_RUN|
|M08|local browser/HTTP|PASS|BROWSER_CHECK/DEMO_FINAL；人审提交NOT_RUN|
|M09|independent semantic GT|BLOCKED|K0，282+66审核缺失|
|M10|literature|PASS|核实primary refs和真实代码状态|
|M11|delivery|PASS|九报告/命令/manifest/本回传|
|M12|device/physics|NOT_RUN|本轮未授权，无板端性能结论|

原始命令/exit见COMMANDS、FINAL_CHECKS；R1提取exit1保留，R2提取/R3新推理/verify均exit0，Python含-B -W error，最终10单测exit0/JS语法exit0/既有rf_person.test exit0。35检查与九会话新推理全相等。不是人工GT或全生产回归。

### 未闭合与限制 / 交给后续独立复审

语义准确率/混淆矩阵/真实事件P-R/真实P50-P95延迟BLOCKED/UNKNOWN；真实家具条件误报、遮挡、多人覆盖不足，合成反例不得冒充现场。RK只检查Python3.8语法，未在3.8/NumPy1.17实际运行；PC原RF依赖Node，不声称板端可部署整链。唯一表/逐项RESULTS/REVIEW_R1/DELIVERY_MANIFEST为入口；当前SUBMITTED，不自行ACCEPTED，不解锁HFUS E1/HR09/生产。无capture/deploy/driver/network/Git写。
