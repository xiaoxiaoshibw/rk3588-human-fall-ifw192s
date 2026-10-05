# P02 离线配平预览 / SUBMITTED（作者自验）

2026-10-04。用户问能否实现配平，随后明确参考 `pc_apps/human_replay/annotator.html`。单writer Codex，只新研究目录和状态记录；不修改源网页、runtime、driver、配置或原始数据。

## 已交付

- `06_PREVIEW.html`：自包含离线预览。默认沿用原annotator的 **Ry(+26°)→Z+=1.340m**；可调下俯角与显示Z平移，可切原始雷达/名义显示，A/B/C各首/中/末帧，共9段预览。参考方式读取当前源码与SHA，不借用静态图的旧#3编号。
- 第二个选项是 **#3局部平面修正**，明确只用于对照，不直接改整场模型。source→display数据模型：pitch27.901584°、roll−5.862777°、tz1.339780910m，R=Rx@Ry，yaw/tx/ty=0；实测高度另存 **1.14m**，未覆盖。
- `01_DISPLAY_MODEL.json`和`05_REFERENCE_MODEL.json`分开保存两模型，kind不是正式calibration，physical/extrinsics/runtime资格保持false。
- `04_FROZEN_LEVELED_POINTS.npz` 保存全部101948 A/C #3源点、变换点、source_rows、session_code、frame_ordinal，point membership不随参数改变。
- `02_METRICS.json` / `03_FRAME_STATS.json`：A/B/C全部306帧运算检查，B不参与拟合。完整数值保留，预览抽样不参与门控。
- `05_BEFORE_AFTER.png`：实际查看过的名义显示/局部修正XZ和YZ对照；橙色#3、灰色周边全高度点，视口裁剪只作展示。

## 数值验收与边界

| ID | 当前结果 | 本轮证据 |
|---|---|---|
| P02-C | PASS（作者自验） | A48075/C53873、源行SHA与R2一致；04完整冻结数值、session/ordinal绑定；原meta/bin首尾匹配 |
| P02-D | PASS（source坐标数值子项/沿用R2有效同域搜索） | 10三estimator源系n/d、全部同101948点全残差；最大角差.427021°、d差.000738511m；原域RMS刚体一致。非本轮独立重跑RANSAC搜索 |
| P02-E | PASS（离线source-frame数值模型）；物理/全场适用BLOCKED | Rn≈up，全306帧所有有效点forward误差≤1.78e−15m、inverse误差≤3.55e−15m；#3 signedres与groundZ差≤4.44e−16m；10有193帧source TLS spread；模型不是物理安装真值 |
| S01 | PASS（作者自验范围/数值/页面逻辑）；指定独审与真实browser NOT_RUN | 09源代码/current inputs零漂移；08 Node模拟Canvas/DOM控件、非法值、九帧、物理记录不改；PNG实际查看；不称mock为browser PASS |
| D01 | NOT_RUN | 不设备、新采集、部署、网络/driver配置或生产接入 |

作者自验不是指定OpenCode独审/ACCEPTED。P1-01仍NO：#3局部模型尚不能推为全场物理ground transform；只交付用户已授权的离线显示。

## #3与整场区分

101948点#3局部修正后 RMS=**.01310329m**、P95=**.02521987m**、|Z|≤.05支持=.99990191。A/C各自结果相近，没删异常点或失败帧。

其他内缩XY footprint在该局部修正下仍有更大偏移：A #1 RMS/P95=.05194/.08638m、#2=.03429/.06906m、#4=.04506/.07968m，C近似。这些域保留所有高度，可能含非地面结构；**不是已确认ground误差**，也不能直接判成真实地板起伏。PNG侧向周边出现明显斜带，因此默认沿用用户指明的简单annotator参考模式，局部roll修正作为可见对照，不自动推广。

source TLS逐帧：A pitch27.87366±.21961°、roll−5.84850±.12933°、d1.339052±.005644m；C pitch27.93177±.18010°、roll−5.87629±.13956°、d1.340539±.004729m（±为193帧各态std，不是仪器精度/独立holdout）。10保留min/max。

## 变更、命令和失败保留

最小Change Proposal：复用pure `core.calibration.apply_transform/invert_transform`与`joint_rotation`，一个新research生成脚本、一个本地HTML模板、一个Node检查器。用既有NumPy/Matplotlib，不新增依赖、接口或SDK补偿。旧源网页不编辑，忽略本研究产物即可停止使用，无需回滚用户文件。

`python -B -W error build_preview.py` exit0；`node 08_CHECK_PREVIEW.js` exit0，9片段参考模式逐点标量误差≤4.44e−16m，参数切换/局部模式/非法值/1.14记录检查通过；Python3.8 AST语法检查PASS，不冒充板端环境实测。原SDK a/b根因未知、不做dist-.10。

首次基线采集在name过滤前调用is_file触及Windows catkin reparse失败；初次生成器因无基线退出1，尚无数值产物。00_INITIAL_FAILURES.txt保留，修正文件名检查顺序后成功；未替换链接。源码未改所以不重复无关全ROS回归，输入/保护文件SHA在00/09。

技能实际读取：C:/Users/30680/.codex/skills/ponytail/SKILL.md；scientific-toolkit-skill/SKILL.md；scientific-toolkit-skill/references/scientific-skills/matplotlib/SKILL.md。SHA见07作者产物、09保护检查以及12最终manifest。旧证据/输入/正式网页原样保留。
