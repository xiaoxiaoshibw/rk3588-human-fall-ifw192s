# HFUS-POSE-JITTER-01

## 开始登记 / 2026-10-18

用户新数据离线诊断，RESEARCH；唯一writer Codex。技能实际路径 C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md；其references/scientific-skills/matplotlib/SKILL.md。唯一验收 ../evidence/2026-10-18_hfus_pose_jitter_01_r1/ACCEPTANCE_V1.md。无生产源码修改；不进入S07。结果待追加，各项NOT_RUN。

## R1 提交 / 2026-10-18

状态SUBMITTED（J04科学测量BLOCKED），非ACCEPTED；独立复审NOT_RUN。唯一验收 ../evidence/2026-10-18_hfus_pose_jitter_01_r1/ACCEPTANCE_V1.md；当前协议PROTOCOL_V2（只合并用户在运行前给出的334/348标记，方法/ROI/参数不变），最终RESULTS.json、REPORT.md、NODE_STABILITY_V2.png。

起始branch/HEAD：master / c9c4ee421cb0c8a3e4590b8f5730828b093c759a；原树dirty，原用户差异保留。BASELINE_ALL全tracked+非忽略untracked共34747路径SHA；最终all-path mtime/size扫描、变化路径重算SHA，输入双SHA/旧复用源全SHA重核，范围外变化0，HEAD不变。没有二次全树SHA重算的虚假声明。输入cap_20261018_110029双SHA见INPUT/VERIFICATION：meta63a94ef3…0358、points4da1e1ec…29a5；386帧/18951860点/530652080B（28B每点）。只读数据，不改GT/配置/生产/模型/旧证据，无Git写。

实际技能路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/references/scientific-skills/matplotlib/SKILL.md。唯一writer Codex；策略RESEARCH（节点稳定性未知），科学证据优先。

集中诊断：旧区域提取器G.observe的内禀横截面跨度>0.8m→CONFLICTING_SPATIAL_SUPPORT，中线即使有数百点也被拒。固定ROI含背景残留，空场本身也能产生几何节点。OUTER_A支持区域在f188→189从15点到22点，代表点跨1.069m，而ROI中位点6.24mm；不再把输出标为雷达噪声。未改门/参数或算法。

| ID | 状态 | 证据与限制 |
|---|---|---|
|J01|PASS|INPUT/BASELINE_ALL/VERIFICATION：386帧、18951860点、28B；源双SHA、单调设备戳；HEAD不变|
|J02|PASS|ROI_V1事前冻结，图核对与386帧源行账本通过；AI诊断ROI并非纯人体GT，f50同框仍326点|
|J03|PASS|USER_WINDOWS_V1在节点分析前记录；183–333张开保持、334–347轻晃、348起放下离开，各段分列|
|J04|BLOCKED|原始节点有效率/std/连续跳变已完成；CHEST151帧全无效，相对胸部统计全部N/A；真实关节/纯雷达噪声不能从当前ROI输出判定|
|J05|PASS|统计4个小自验、386帧源行/2361个节点重算通过；输入/旧源SHA不变，范围无外部差异，图V2断开缺测间隙、N/A不填0；独审NOT_RUN|


命令：python -B -W error docs/human_fall/evidence/2026-10-18_hfus_pose_jitter_01_r1/diagnose.py preview / locate / check / analyze / plots，均exit0；独立源行/节点坐标重算（python -B -W error <stdin>）exit0，VERIFICATION记录386帧账本与2361个有效节点误差4.44e-16m；stats四负例/换算自验PASS。原图跨缺测连线可误导，修图V2断线并标N/A，原图留存；统计结果未变，运行版本快照SOURCE_AT_ANALYZE.py.txt，当前diagnose.py只加绘图修正。

交付源码仅新证据内diagnose.py，旧r04/old skeleton/params四SHA首尾相同见INPUT；当前诊断源码SHA见MANIFEST。原始点行映射ROI_ROWS.npz/FRAMES.jsonl支持反查。无M0/聚类/跟踪/关联/预测/显示平滑；固定ROI选择由AI视觉核对，不冒充纯人体逐点GT。用户姿态保持包含自然微动，胸部参考缺失，相对胸部与真实关节抖动不可测；原始统计不是传感器独立噪声。设备/物理/独审NOT_RUN，不进入S07；复测可继续用本段数据，未实施后续算法。
