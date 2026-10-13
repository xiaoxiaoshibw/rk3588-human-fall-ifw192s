# HUMAN-FUSION-DEMO-V2 唯一验收表 v1

2026-10-11（Asia/Shanghai）；用户“开发优先级纠偏”直接授权。Codex 单 writer，只改 sidequests/human_fusion_lab V2 新文件与当前工单文档。继承 V1 真实数据、权重和管线；主线、V1、R9/Q01及所有旧证据只读。不部署、不现场发布、不接生产、不训练或激活 ML、不提交推送。

| ID | 软件/效果验收要求 | 当前结果 |
|---|---|---|
| V01 | 九真实会话切换、逐帧、拖动、播放暂停、回退重建、显式重置 | PASS（作者自验；详REPORT） |
| V02 | 原始点、真实背景过滤点、候选、分类、轨迹独立开关；同步3D/XY/XZ | PASS（作者自验；详REPORT） |
| V03 | 四模型对当前相同候选原始行点集评分；明确与独立重跑的区别 | PASS（作者自验；详REPORT） |
| V04 | 人体成功/漏检、家具误检、模型分歧及未知GT定位；真实浏览器截图 | PASS（作者自验；详REPORT） |
| V05 | GT文件SHA/会话SHA/身份/审阅绑定；缺失和S9错误绑定显示UNKNOWN | PASS（作者自验；详REPORT） |
| T01 | 两默认模型九会话全帧不共享ID；每帧一票、失配清票、寿命和重置回归 | PASS（作者自验；详REPORT） |
| G01 | S9可信GT恢复；禁止把占位哈希改写为真实人工确认 | BLOCKED（源绑定丢失，须重新标注/确认） |
| A01 | 真实点投影2D圈选、3D框选、人工类别/编号、下载导入撤销；草稿不冒称GT | PASS（作者自验；详REPORT） |
| E01 | 跨会话正/负例指标，训练/历史验证/稀疏未知分母分列，不宣称新人员泛化 | PASS（作者自验；详REPORT） |
| K01 | 核查既有骨架算法/测试与真实资格；分割/标定/关节/拓扑/姿态分列 | PASS（作者自验；详REPORT） |
| K02 | 真点粗几何轴及支撑统计；四肢/精确关节/姿态UNKNOWN，无可靠标定显示UNCALIBRATED | PASS（作者自验；详REPORT） |
| S01 | 全Git清单含untracked基线SHA；生产/原数据/V1/R9旧证据不变 | BLOCKED（外部5个既有文件漂移（含V1 server.js）；生产源与输入未见变化） |
| D01 | 板端部署、生产替换、采集、现场发布 | NOT_RUN（用户禁止） |
| P01 | 人工确认检测、骨架与姿态效果/可靠物理标定 | BLOCKED（不能由软件自验替代） |

逐条结果为作者自验；不得标整单ACCEPTED。证据目录：evidence/2026-10-11_human_fusion_demo_v2_r1。回传：returns/HUMAN-FUSION-DEMO-V2.md。
