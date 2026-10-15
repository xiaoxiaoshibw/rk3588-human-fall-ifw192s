# HFUS-POINTSET-01 R1 回传（2026-10-13）

## 当前状态

SUBMITTED，未ACCEPTED。唯一验收：../evidence/2026-10-13_hfus_pointset_01_r1/ACCEPTANCE_V1.md；逐ID状态ACCEPTANCE_FINAL.json。Codex唯一writer，新隔离pointset/r01。不改旧输入/GT/模型/生产、不采集部署commit/push。

## 已交付与验证

完整2605帧9段S1背景→XYZ/XY聚类→独立性诊断→RF/PointNet→点支撑骨架。逐帧UI8941和9会话独立gallery，人工人体参照NPZ，统一标注schema及部位选点/append-only审核，监督PointPartNet训练器。6个-W error测试、真实Edge9会话/时间轴/模式/审核校验通过；101个空场留帧0满足门限候选。

根因：XY可接入更多未标身份周边点，XYZ在遮挡未标身份比例49.5%→25.0%，不是已证明纯度；S8仅全场可见而小ROI0，边界仍截图近似；S9 GT错误绑定仍BLOCKED。旧test61正候选RF61/PointNet36，没有可靠负候选，特异度未知。

## 未闭合

PS05真实头部/躯干/四肢学习无人工部位标签BLOCKED；GT01解剖关节与纯人体精度BLOCKED。骨架仅点支撑区域，不当真关节。现有会话动作名不当逐帧动作GT。独审/设备/物理/部署NOT_RUN。

## 证据与范围

FINAL_REPORT.md、ACTION_CATALOG.md、MEASURED_SUMMARY.json、EMPTY_HOLDOUT.json、TESTS.txt、BROWSER_CHECK.json、GALLERY_CHECK.json及截图。19751既有regular files SHA对照0漂移；验证后仅追加当前README索引（记录新SHA），旧源码/输入/GT/模型未变。

技能实际读取：C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/references/scientific-skills/scikit-learn/SKILL.md。复现命令见隔离README。下一步真实部位/混入身份审核和ROI坐标核对；不能以本机软件交付推导生产或物理通过。
