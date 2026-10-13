

## R40 — W03人体安全收口研究与最小方案（2026-10-07）

### 本轮信息

- 授权：用户本轮A–D研究、诊断与开发方案设计；明确禁止production算法补丁与registration接入。本聊天Codex单writer，无派工。
- 状态：SUBMITTED / **REWORK_REQUIRED**，未ACCEPTED；真人GT BLOCKED，设备/物理/部署/采集NOT_RUN。未进入W04及后续阶段。
- 唯一验收表：R3.7 06_test_matrix.md v1，SHA 70c82e401d0e4055ad85e1bef847d82dd32e718d682533ff25f22a24ac1f9b18。没有修改验收表/门/原artifact。
- branch/HEAD：master / cfbb80c57508be1a0435fdb92260f698dc763934；含untracked/ignored全树基线00_baseline.json，dirty保留。
- ponytail实际读取：C:/Users/30680/.codex/skills/ponytail/SKILL.md（full）。本机Node v24.14.0，Python脚本均-B -W error，纯stdlib及既有PL/helpers。
- 新独占证据根：docs/human_capture/evidence/2026-10-07_hrw03_r40_research_r1/；集中报告07_research_and_minimal_plan.md，最小补丁设计08_bug_and_patch_design.md，GT格式06_gt_label_format.md。

### 集中诊断与根因覆盖

| 项 / 现行验收 | 根因与受影响入口 | 研究结果 | 方案/停止条件 |
|---|---|---|---|
| T38-05 / S4 | source拟合地面registration后不同于reference面，S多处extract/pipeline直接crop reference z | 两面倾斜1.770153°；31点处竖向差1.353–24.565mm；source面crop反事实翻转30点，固定图下仍2点reference命中 | GT先行；不是已证正确消地面或人体修复，不改阈值/数学；旧31cohort保留 |
| T38-06 / S7 | 固定XY网格重分箱+成员变化+独立Tracker历史 | 33帧全候选raw-index交集与旧结果一致；f151无删除Q也merge；f105/f146点保留而票变 | GT区分去粘连/真人碎裂；原strict gate仍FAIL |
| BUG-R40-I01 | leveling.py exporter保留invalid；registration.loadFrames及浏览器apply_Rt无条件变换零XYZ | source1250003/ref778477零XYZ与既有invalid_xyz_count精确相等；raw零被denoise删，配平后通过；gate源i0为虚点且normal无效 | 小guard草案核所有入口，保留索引/opaque字节；生产未改，不靠改变分母翻gate |
| BUG-R40-T01 | PL.Tracker.tick缺used集合，同帧可多簇更新一个track/votes | S f46实际复用track3两次0票；合成一帧3正簇能满足3票 | 每帧一对一used set草案，保持顺序/EMA/门；禁止本轮实施 |
| BUG-R40-T02 | votes按观测push，missing frame不老化票 | S track4 f61使用53/55/56/61观测确认；最近5帧只1正票；gap最小repro已存 | 按frame过期草案；先T01，seek生命周期另核；不改3/5或Fall |
| gate协议 | numerator确为trim后支撑，文本final iteration与fixed B重测集需澄清 | 9897raw→5938keep/11959，50%仍差42keep/70raw；50%与60%非逻辑冲突 | 双覆盖命名/独立依据建议而已；不放宽50、不发布profile、不换解/挑样本 |

### 实际变更与逐条验收

- production代码/PIPE/matcher/ICP/registration/leveling/人体几何门/确认门/Tracker/Fall **零修改**；只新增本轮evidence工具、JSON、CSV与研究报告，本文仅追加。原captures/历史evidence未覆盖。
- R39整目录293文件/1,257,292,336字节完整读入，大型JSON完整解析不直接打印；03_r2为现行归因。
- 本轮只执行新的diagnostic/assertion：baseline、full evidence read、02_research、03_followup、04_reports，实际exit0；stdout/stderr/exit/参数在同前缀run.json日志。没有重复R39 full shadow或既有test suites。
- 07_acceptance_status.json逐ID列T37-01..21含05b、T38-01..12本轮均NOT_RUN，旁列R39既有PASS/FAIL；**T38-05/06承接FAIL，不被诊断exit0取代**。T39-01..08 NOT_RUN；HP02真人BLOCKED；设备/物理/部署/采集NOT_RUN。
- 初次诊断collisions.final_votes保存可变数组引用，03跟进从不可变旧snapshot校正r2；旧输出保留，r2为当前。原R39/production没有这项工具修订。

### 未闭合与独立复审入口

- GT优先31点7帧→24非WD01消失行→12拓扑帧，去重38帧；仍须覆盖155行97帧。原viewer复用，pair单标签不足以表达P/S各簇/person_id，最小sidecar格式已交付；邻帧缺81/82/89/91/142的补充方案仅设计，NOT_RUN。
- 不称FP/FN、真人fragmentation或准确率。31语义/真实身份仍UNKNOWN；gate保持历史DEGRADED，当前STALE/SAFE结论承接R39，不重绑定。
- 先GT与I01/T01/T02审查，生产补丁另授权；高度参照/拓扑人体方案依赖GT，gate设计需独立依据。GT补齐仍不能绕严格安全/共同门或支撑gate。
- 审查集中报告07、repro/trace r2 04、逐点03、gate05、GT06、patch草案08；09_integrity.md列SHA与范围。未commit/push/reset/checkout/clean/部署/采集/网络变更。
