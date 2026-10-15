# HFUS-POINTSET-01 R1 当前交付

用户明确要求统一标注、小地面区、背景扣除、人体独立聚类评分、运动周边点混入分析、三维点集合方法、九会话人体动作与框/骨架展示。用户确认先做现有九段。本轮新隔离分支 `sidequests/human_fusion_lab_next/pointset/r01`；未替代D05/HF-REAL或生产。

## 交付入口

- 逐帧工作台 http://127.0.0.1:8941/ ，绑定localhost。
- 九会话独立展示 `sidequests/human_fusion_lab_next/pointset/r01/output/gallery.html`。
- 动作/会话目录 `ACTION_CATALOG.md` 与完整机器指标 `MEASURED_SUMMARY.json`。
- 每会话完整逐帧JSON、summary.json、action_report.json；有效标注会话另有人体人工参照全量NPZ。
- 统一格式、源点绑定、部位选点审核入口、PointNet式逐点监督训练器；无解剖标注时明确BLOCKED。

## 实测结论

Windows本机 Python3.12 / NumPy / scipy / scikit-learn / ONNXRuntime / Torch；不是板端性能证据。9段共2605帧完整运行。S1 304帧按mod3冻结FIT、CALIBRATION、HOLDOUT，背景匹配约5.5cm；101个留帧全场与ROI均无满足门限的候选簇，最多134个残留前景点，不称所有背景点被删净。

已有人工参照帧上最佳簇覆盖：近距走动98.3%，远距走动97.6%，走停98.7%，转身98.9%，遮挡97.1%，5m97.4%，静立99.9%。各会话已标帧数不同（258/99/11/6/71/12/53），不能把这些覆盖率推广到未标帧或真人准确率。

三维相较XY聚类降低未标身份点混入比例：近距走动12.0%→6.5%，走停7.8%→2.7%，转身7.0%→1.6%，遮挡49.5%→25.0%。未标身份不等于已确认家具；遮挡仍明显存在粘连/不完整参照，纯人体FAIL/BLOCKED保留。遮挡参照覆盖3D97.1%略低于XY97.7%，不声称3D在所有指标胜出。

新XYZ-RF与冻结PointNet在已知标签候选上比较，旧test的61个正候选XYZ-RF保留61，PointNet保留36；stress33个正候选保留29/21。候选评价没有有效负候选，无法给出候选特异度/全链误报率。S1的125个未参与分类器FIT的人工家具对象，RF没有预测为人，但这是同录制家具对象分类，不是新家具泛化。

S8小ROI无候选，但全场已有参照覆盖99.9%；说明截图视觉近似边界与所有旧会话不能直接统一使用。S9旧标注绑定失败，126帧自动候选与骨架预览可看，纯人体参照/评分BLOCKED。

“运动物体吸引周边点”没有当物理机制结论。当前单帧、不累计、不补点，将近背景比例、独立核心、其他簇间距、家具/他人参照重合、未标身份与碎片拆开记录；时窗拖影源头在本分支被避免，但硬件运动形变归因仍NOT_EVALUATED。

## 软件验证与边界

6个有意义检查：XYZ分离XY重叠对象、compact→raw索引、ROI/居中输入、倒地低高度支撑与轴歧义、审核scope/索引/SHA约束、逐点模型置换等变性。Windows `-B -W error` 全通过。

真实Edge检查9会话切换、逐帧/播放、自动/XY/人工模式、模型与视角、部位选点、缺审核人拒绝、错误绑定400、S9不伪造人工参照均通过。测试没有保存伪造人体/部位标注。九格展示检查9张图及旋转，无pageerror。截图见AUTOMATIC_PREVIEW.png、REFERENCE_PREVIEW.png、NINE_ACTIONS.png。

开始时19751个既有regular files包含ignored/untracked逐文件SHA基线；结束前全量复核0漂移/0缺失/0读取错误。该检查发生在追加本工单README索引之前；之后唯一既有文件的授权变更为docs/human_capture/README.md顶部入口，另保存新SHA。旧输入/GT/模型/生产均未改。无新依赖、采集、板端部署、Git写，独审NOT_RUN。

部位/解剖关节标签缺失：头部/躯干/四肢训练尚未运行，模型输出没有装成人工真值。当前骨架为有源点支撑的13个区域，不是可靠解剖骨架。身体纯度、部位/关节精度和多人身份GT尚未达到用户最终要求，不能以软件交付宣称已完成纯人体识别。

状态：软件原型SUBMITTED，未ACCEPTED；PS01/02/03/04/06/07/08软件检查PASS；PS05标注/训练器已实现，但真实训练与精度BLOCKED；GT01 BLOCKED，DEV01 NOT_RUN。完整状态见ACCEPTANCE_FINAL.json。

实际技能：C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/references/scientific-skills/scikit-learn/SKILL.md。参考[PointNet原始论文](https://openaccess.thecvf.com/content_cvpr_2017/html/Qi_PointNet_Deep_Learning_CVPR_2017_paper.html)的直接XYZ路线，未宣称复现其基准。
