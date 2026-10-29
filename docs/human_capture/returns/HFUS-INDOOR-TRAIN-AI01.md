## 2026-10-16 R1 / SUBMITTED(域内 AI 标签训练;T06 PointNet FAIL)

### 本轮信息
- 授权=用户 2026-10-16「继续开发,不依赖真人」+ ND05 资格(QUALIFICATION_R4,AMENDMENT_A1 口径)。单 writer=Claude Code,ponytail 实际读取 `C:/Users/30680/.claude/skills/ponytail/SKILL.md`。起点 master/c9c4ee4…,dirty 保留,无 Git/设备/下载/采集;旧资产(r7/r4/三ZIP/learn/demo/权重/EXE)只读——ledger(qual_r01/reviews/)为全轮唯一新增写数据路径(24 条 AI 署名+哈希链)。
- 唯一验收 [ACCEPTANCE_T1.md](../evidence/2026-10-16_hfus_indoor_train_ai01_r1/ACCEPTANCE_T1.md);逐项 [RESULTS.md](../evidence/2026-10-16_hfus_indoor_train_ai01_r1/RESULTS.md)(run4 终,run1/2/3 历史保留)。

### 实际变更(全新目录,不改旧码)
`sidequests/hfus_indoor_ai_test/train_ai01/`:train_ai01.py(特征12维GT无关/会话组折/RF3seed/PointNet时间帽+失效标记/Wilson 实写)+test_train_ai01.py。证据目录含 split/labels 引用、4 个 run、SOURCE_FREEZE_FINAL、REVIEW_R1..R3 全记录与处置。

### 逐条验收
T01 PASS;T02 PASS(25831 样本 join 100%、成员数逐条核);T03 PASS(run1 i%4 域泄漏、run2 i//2%4 时序泄漏均被审查/test 抓出→run4 组折 [4,4,4,4,2,1×6],HHMMSS 解析修正后重算=run4 零变化);T04 PASS(RF 31.8s);T05 PASS 域内(B0 P=0.955/R=0.724,tp21/fp1/fn8,Wilson(0.5428,0.853);B1 R=0.30;场景泛化 BLOCKED);T06 **FAIL**(PointNet 全折 2000 步跑满仍 P=0.05/R=0.96≈全正分类器,pos_weight≈526 失衡所致结构倾向,预算内不可救,不粉饰);T07 PASS;T08 PASS(OpenCode 三轮只读,READONLY_REVISE→处方全落,终冻结)。

### 未闭合
负类 conditional(AI 完备门);可信独立组 0→无 test;HDBSCAN 流召回 0.30 首因候选=簇切碎(未调参);真实人审/二审仍是最高优先补门;板端/设备/生产 NOT_RUN;不解锁 E1/HR09。


## 2026-10-16 R2 / Codex只读效果审查 / SUBMITTED

用户要求核实效果。沿用唯一 ACCEPTANCE_T1.md v1；起点master/c9c4ee421cb0c8a3e4590b8f5730828b093c759a、dirty保留；读入源SHA见 [R2证据](../evidence/2026-10-16_hfus_indoor_train_ai01_r2/REVIEW.md)。ponytail读取路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md。

RF现存计数复核PASS(21/1/8)，未重训复现。T01/T02/T04 NOT_RUN；T03 BLOCKED(录制独立性)；T05 FAIL(候选口径非目标级、帧区间缺失)；T06/T07 FAIL(PointNet模型与优化器跨折复用，后续验证已见训练)；T08 FAIL(既有审查未关闭此缺陷)。3项最小测试-B -W error exit0不代替效果验证。B0另349 U不计分，故P=.955/R=.724仅P/N子集；低FP不能验证标签可靠；PointNet路线失败结论不成立。只新增审查记录，无源码/模型/标签/旧证据更改，无数据写入、采集部署或Git写。独立复算/视觉重审NOT_RUN，真实泛化BLOCKED；不自行启动返工或下一单。
