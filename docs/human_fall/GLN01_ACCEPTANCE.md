# GL-N01 名义安装参数离线配平 / 唯一验收 v1

2026-10-04 当前GL-N01 R1：SUBMITTED / STOPPED。指定Go Flash/defaultDB独审N01–N06/S01/Q01–Q06 PASS，无需返工；P01独立物理BLOCKED，D01 NOT_RUN。实际浏览器NOT_RUN/BLOCKED单列。[收口](evidence/2026-10-04_gl_n01_r1/22_CLOSEOUT_01.md)/[独审原文](evidence/2026-10-04_gl_n01_r1/19_OPENCODE_VERDICT_01.md)。本表判据v1不变。

| ID | 要求 / 负例 / 预期 | 检查入口 | 结果 |
|---|---|---|---|
| N01 | 先R_y(+pitch_down)旋正，再t=(0,0,+height)；源原点→(0,0,h)，已知地面→z=0，正反变换一致，不先平移再旋转/不反号 | 合成GT、独立标量公式 | PASS |
| N02 | pitch_deg/height_m显式可配置；0/26/40/-10°与不同高度可复用；strict numeric/单位/frame/schema/finite拒坏值；R proper且元数据一致 | 新集中tests与CLI负例 | PASS |
| N03 | 模型内容ID绑定参数/坐标约定/来源，caller改或同ID异内容拒；变参生成新ID/新路径，旧结果不覆盖；非cache | 生命周期组合tests | PASS |
| N04 | 复用load_adapted，只读全部既有NPZ/meta/bin；记录source/window/header/代码/输入SHA；finite非零点显式有效mask，输出保留原pooled row，逐帧数量一致 | 真实89帧及独立源行对拍 | PASS |
| N05 | 真实nominal_leveled NPZ+逐帧统计+前后对照HTML；仅固定同源采样显示，用户参数可预览变化，导出/预览参数分明；不按拟合残差筛点、不改原选区、不假造ground身份 | 同帧对照/源行/页面源码/显示检查 | PASS（离线/静态/逻辑；真实browser NOT_RUN/BLOCKED） |
| N06 | kind=nominal_installation_leveling、frame=ground_nominal、status=nominal、physical/extrinsics/runtime=false；不得伪造geometry_calibration/ground.valid/support；旧消费者拒资格 | 冻结validator及明确标签 | PASS |
| S01 | 最多三新代码路径；stdlib+NumPy/Python3.8；现有ground/calibration/配置/driver/webui/旧数据/evidence冻结；写前diag/SHA→自验/manifest/回传→停写→指定独审 | 范围/回归/probe/model/session | PASS |
| P01 | 当前数据名义变换的地板误差/身份及旧SDK绑定未独立核定；如约数后不z=0如实显示，不能自动用拟合d替换1.1或挑点解释成功 | 独立物理层 | BLOCKED |
| D01 | 不设备/新采集/网络/部署/生产接入/IRLS；本单只本地固定变换，后续实际candidate另单 | scope | NOT_RUN |
| Q01 | startup正例/缺文件/schema/NaN/单位/frame/from-to → N01/N02/N04 | 集中tests | PASS |
| Q02 | 同内容/同ID异内容/caller改/变参/已有out/保护路径 → N03/N04/S01 | 集中tests/CLI | PASS |
| Q03 | 0/正下俯/负俯角/高度变化/逆变换/假SDK二次旋转 → N01/N02/N06 | 符号与资格tests | PASS |
| Q04 | 原始零/非finite/分组/row对照/仅显示采样/高度仍有偏差 → N04/N05/P01 | 真实对照+合成边界 | PASS |
| Q05 | nominal参数已给/无独立测量/字段齐全 × verified/runtime晋级禁止 → N06/P01 | 冻结consumer拒绝 | PASS |
| Q06 | 提交/冻结SHA/停写/原始exit/新编号/probe/指定只读独审 → S01 | controller记录 | PASS |

裁剪：离线无ROS热reload或跟踪状态/缓存；旧选择版本失效由新内容ID/输出绑定表达，本单不改运行时。名义视图不是地图世界坐标；roll/yaw=0为显式初始约定，有效source按X前/Y左/Z上假设，SDK历史未知单列，不将其当名义开发前置阻塞。
