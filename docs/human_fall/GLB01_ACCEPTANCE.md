# GL-B01 地面区域复核与偏差诊断 / 唯一验收 v1

2026-10-04 当前R1：SUBMITTED / STOPPED。指定Go Flash/defaultDB独审R01–R06/S01/Q01–Q06 PASS，无需返工；用户木地板/工作台语义确认及0.75m参考已记录，P01剩余行集/精度/SDK复核BLOCKED，D01 NOT_RUN。[收口](evidence/2026-10-04_gl_b01_r1/33_CLOSEOUT_01.md)/[独审原文](evidence/2026-10-04_gl_b01_r1/30_OPENCODE_VERDICT_01.md)。判据v1保持。

| ID | 要求、反例与可观察预期 | 检查入口 | 结果 |
|---|---|---|---|
| R01 | 当前NPZ+N01模型+旧draft source SHA/window/frame绑定；foreign99帧/同路径异内容/错模型或新ID旧内容拒 | loader与内容ID/文件身份 | PASS |
| R02 | 候选区按nominal XY footprint、指定单source frame，FIT+≥3互异验证帧组；保留区内全部有效场景点，不按Z/当前模型残差筛holdout；重复/alias/跨组/越界拒 | strict plan→select_group_region/gate_selection | PASS |
| R03 | 每点原pooled/source row、ordinal/seq/sourceXYZ/nominalXYZ可追溯；显示采样不影响源行全量；pending候选不能冒充人工地面标签 | rows artifact/view/统计 | PASS |
| R04 | all-scene Z分布、XY分格观察、旧固定ROI全点PCA诊断分别标域；偏移/倾斜/混杂解释分开，无资格晋级/参数替换 | known GT/混杂/退化/空区与真实报告 | PASS |
| R05 | 输出可审查区域图/CSV/待确认draft；人工已确认源行入口需person/time/basis/地标/evidence SHA且复用indices帧独立门；未经确认不输出ready selection | prepare/reviewed selection strict入口 | PASS |
| R06 | 26/1.1原模型/原数据/旧draft保持；content ID绑定plan+source+model，caller修改/同ID异内容/已有out/保护目录拒；合法unknown可交付 | 身份/输出生命周期 | PASS |
| S01 | 最多三新源码、stdlib+NumPy/Python3.8；写前diag/全treeSHA→自验/manifest/return→停写→指定Go Flash/defaultDB只读独审；不改冻结数学/配置/UI/HR/旧evidence | scope与回归 | PASS |
| P01 | 真地面身份/物理测量与旧SDK绑定独立复核；空间候选/PCA/直方图不能代替人工ground确认。参数已给，不阻工具开发 | 人工证据 | BLOCKED（剩余行集/精度/SDK） |
| D01 | 不设备/采集/部署/网络/生产/IRLS；只观察诊断，无自动ground.valid或新标定 | scope | NOT_RUN |
| Q01 | schema/kind/units/from-to/frame/source/window/NaN/空region → R01/R02/R04 | 集中tests | PASS |
| Q02 | sameID/caller/同路径异内容/newplan/newmodel/已有out/保护路径 → R01/R06 | 集中tests/CLI | PASS |
| Q03 | 独立帧/重复/alias/跨组/越界/zero/全部高度保留 → R02/R03 | 源行对拍 | PASS |
| Q04 | clean/斜面/offset/桌面混杂/line/empty × full-region stats/PCA/非测量解释 → R04 | 已知GT与真实域 | PASS |
| Q05 | pending/partial confirmations/人工source rows/残差筛选 × reviewed eligibility → R05/P01 | 严格确认入口 | PASS |
| Q06 | source/model/frozen资产首尾/原命令exit/停写/probe/model/session/new编号独审 → S01 | controller证据 | PASS |

裁剪：离线无ROS热reload或跟踪cache。本单人工确认入口仅准备reviewed-input候选选择，不等于独立物理PASS；实际没有人签认时保持pending。相机外参不是额外前置，可使用有记录的3D地标人工核查，但不自动像素→源行。当前89帧已曝光仅开发/工程验证。
