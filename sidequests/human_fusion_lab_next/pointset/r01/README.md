## 2026-10-14 全部新增簇与活动区外锚点

scene_static同页对照：外部参考锚点、双解释过滤、全部新增3D簇多色同屏、冻结观测与逐簇几何。当前原始meta/points缺失，显式baseline_02保存XYZ做1966帧几何回归；原字节核验BLOCKED、未知簇无人体骨架，不晋级R1默认。当前 http://127.0.0.1:8954/?dataset=actions&variant=scene_static&fi=0 。[报告](../../../../docs/human_capture/evidence/2026-10-14_hfus_scene_static_r4/FINAL_REPORT.md)。旧记录保留下方。

## 2026-10-14 场景新增点与抗抖动对照

原同页新增 scene_change：静态锚点补偿、冻结局部背景表面、双姿态歧义过滤、当前新增点三维候选。当前产物 action_research_scenechange_guarded，首轮失败 action_research_scenechange 保留。R1默认和旧输出保持。1966帧源行/XYZ/背景守恒与Edge九会话回归通过；人体身份/完整率/家具污染仍UNKNOWN。

同一 server.py --port 8954，深链 /?dataset=actions&variant=scene_change&fi=0。[报告](../../../../docs/human_capture/evidence/2026-10-14_hfus_scene_change_r2/FINAL_REPORT.md)。此前入口保留下方。

# 2026-10-14 R3 当前人体点集与粗部位实验

原8944页面，R1保持默认，R2保留。R3增加图连接/背景排除/因果时序消融、组合点集与当前局部体轴、独立tracker反馈。原6＋符号返工2方案全1934+32帧源点与因果前缀重放PASS，9→4符号翻转但新f124/最大槽跳变1.191m保留；身份/解剖精度UNKNOWN、生产晋级BLOCKED。实验入口experiment_r3.py、verify_r3.py、check_r3_browser.py；输出action_research_r3，存在时拒绝覆盖。见[FINAL_REPORT](../../../../docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r3/FINAL_REPORT.md)。

# 2026-10-14 R2 当前诊断与实验

继续使用 http://127.0.0.1:8944/ 原页面。默认R1；上方实验方案切换/五层同帧对照/诊断帧导航。四种局部恢复与有界历史轴均未晋级默认；当前节点仍粗部位中心，人体完整率/污染率/解剖精度UNKNOWN。

新输出action_research_r2；原action_output/output/core/配置/模型保持。[R2报告](../../../../docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r2/FINAL_REPORT.md)。`research_actions.py diagnose`、`experiment_actions.py`均独占输出，存在时拒绝覆盖；不要直接重跑历史目录。核验`verify_research_actions.py`；单测仍`python -B -W error -m unittest discover -s . -p "test_*.py"`。当前R2完整核验已完成，日志见报告索引。以下R1与原九会话保留作历史。

# 2026-10-14 当前八段动作入口

当前原页面：http://127.0.0.1:8944/ ，默认只显示中央目标/框体/点支撑骨架/倒地姿态；下拉切回原九会话。新数据action_output，原output与core.py不改。总控制台桌面快捷方式已指向Console_Pointset.exe；旧窗口需要重新打开才能看到新版本。

`python -B -W error actions.py` 写入独占新action_output（存在时拒绝重跑，保留历史）；`python -B -W error server.py --port 8944`；单测照旧，增加test_actions.py；全源行校验verify_actions.py，实际浏览器check_actions_browser.py。[最终报告](../../../../docs/human_capture/evidence/2026-10-14_hfus_pointset_actions_r1/FINAL_REPORT.md)。以下是原九会话历史入口。

# HFUS-POINTSET-01：九会话三维点集合离线分支

当前入口 http://127.0.0.1:8941/ ，独立九会话展示 `output/gallery.html`。

从本目录执行：

```powershell
python -B -W error run.py
python -B -W error summarize.py
python -B -W error train_parts.py
python -B -W error make_gallery.py
python -B -W error server.py
```

单测：`python -B -W error -m unittest discover -s . -p "test_*.py"`。

输入是固定九会话，S1=`cap_20261010_175227`；不含新联合录制。旧数据/GT/模型/源码只读，新代码/数据/模型只写本目录；当前唯一writer Codex。实际应用 ponytail（C:/Users/30680/.codex/skills/ponytail/SKILL.md）和 scikit-learn 技能；无新增依赖，无板端部署或Git写。

## 当前实际算法

1. 验证原始28B记录、帧边界、输入SHA与device时间；保持frame-local raw索引，可回到完整原始字段。
2. 共用旧REF_RT米制坐标。S1帧序号 mod3=0只用于冻结背景，mod3=1标定最近背景距离，mod3=2独立留帧检查。5cm体素、FIT中≥30%帧出现，得到16151参考体素；CALIBRATION p95≈3.0cm，添加半体素后容差≈5.5cm，未碰12cm上限。无有人序列背景更新，无按身高抹掉低姿态。
3. 同当前单帧前景做全场XYZ DBSCAN、小ROI XYZ DBSCAN、全场XY DBSCAN三路；体素只参与邻域查询，成员还原原始点，不吸附、生成或跨帧叠加点。
4. 独立性按紧半径核心比例、其他簇间距、近背景比例给几何诊断分数；它不是人体概率。GT只在推理后算已有参照覆盖、家具/其他人混入、未标身份与碎片数。缺标/未知不当负例。
5. 冻结PointNet居中XYZ输入，原权重不改；新RF用无序点集的3D协方差、XYZ跨度、径向分位数与高度分布学习。按旧会话分组，S1分类器训练仅用FIT帧。不把此前开发用过的test会话当新人/新景泛化证据。两模型页面可切换，UNKNOWN候选未当确定真人。
6. PCA体轴/区域中心构建有源点支撑的13槽骨架预览。当前解剖头/手身份、左右、肘腕膝踝不确定；无未来点、无上帧补节点。缺支撑或轴歧义显示UNKNOWN。

## 部位标注与学习

格式见 `ANNOTATION_SCHEMA.json`。点级类：UNKNOWN、HEAD、TORSO、LEFT_ARM、RIGHT_ARM、LEFT_LEG、RIGHT_LEG；对象身份包含scope，避免ROI与full同名候选串绑定。

回放页选择自动候选或已有人工人体参照，开启部位标注，点击源点（仅显示采样点），填写实际审核人并保存；事件追加到本目录labels/human_parts.jsonl，不改旧GT。刷新/换帧可读回颜色。UNKNOWN不作为监督标签。

`train_parts.py`是直接XYZ的共享点MLP+全局max逐点分类器，属于PointNet式小型影子模型，不是官方完整复现。只消费明确人工审核事件，校验源SHA，按会话分开train/test。没有两会话/两类别的有效标注时写BLOCKED，绝不自动用几何区域伪造标签。当前没有真实部位标签，未开始部位训练；`part_model_status.json`明确记录。训练后的新影子模型也未接管原模型/生产；逐帧页当前展示的骨架仍为几何区域估计。

## 展示与导出

- 页面9段独立选择、完整逐帧播放、模型切换、原始前景上下文、对象框、骨架、独立性与参照覆盖读数。
- “下一个人工已标帧”只导航已有标注；缺标不插值成真人。
- `output/<sid>/human_reference.npz`是已有人工人体点的全量导出，带frame_indices/source_indices/intensity；不是自动算法纯度证明。
- S9旧GT绑定失败，自动候选可看，人工参照/GT分数不生成。
- 当前截图ROI是待审核示意；S8在小ROI无候选而全场有支撑。不得扩大圈线掩盖错误，不可把小ROI套用所有旧会话当物理正确。

科学依据：直接点集合分类/分割路线参考[PointNet作者论文](https://openaccess.thecvf.com/content_cvpr_2017/html/Qi_PointNet_Deep_Learning_CVPR_2017_paper.html)。本轮RF与小型PointPartNet不宣称复现论文结果。

当前本机开发原型SUBMITTED，纯人体身份、部位/关节精度仍未闭合，设备/部署NOT_RUN。验收与结果位于 docs/human_capture/evidence/2026-10-13_hfus_pointset_01_r1。
