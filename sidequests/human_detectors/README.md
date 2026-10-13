# PointPillars / CenterPoint 人体检测实验分支

最新（2026-10-08）：[DET-06 独立复核](../docs/sidequests/evidence/2026-10-08_det06_review_r1/README.md) + [修复轮 r1](../docs/sidequests/evidence/2026-10-08_det06_fix_r1/README.md)。复核：74 行复算 0.0 差、KITTI 正控制 0.774；更正口径（测试集选点、FP 未含空场，合并/LOSO 重估）与标签伪影（人框 z_min 为模板掩膜截断）。修复：新输入臂 `subvox32`（柱内子体素抽样，只改选点）合并 FP 0.424 下 recall 45.8% vs zrank 33.3%、测试内 75% vs 58.3%；降密臂 zrank11 证伪"少点数"方向；人-家具判别仍未解决。`gt_eval_v2` 已冻结（z_min 0.10，仅 3D 报告口径）；[DET-07 预注册草案](../docs/sidequests/DET07_PLAN.md)已出（未授权执行）。76 次新诊断前向，不占 74 预算；未改权重/阈值。

最新（2026-10-08）：[DET-06 独立识别评估协议与基线评测](../../docs/sidequests/evidence/2026-10-08_det06_r1/README.md)，[预注册计划](../../docs/sidequests/DET06_PLAN.md)/[唯一验收v1](../../docs/sidequests/DET06_ACCEPTANCE.md)。第二人 C1 四段 + 新空场配平与工作区前景（旧前景等价 253/253）；24 帧人框经用户确认冻结 gt_eval_v1；基线 74 前向：同误报预算下 first32 recall 4.2%–25% vs z_rank32 58.3%–100%，空场/人形固定物 0.35–0.54 仍会响应，判别力问题依旧；SUBMITTED，未 ACCEPTED。

最新（2026-10-08）：[DET-05 人体点 GT 标注与纯人体柱采样隔离](../../docs/sidequests/evidence/2026-10-08_det05_r1/README.md)，[预注册计划](../../docs/sidequests/DET05_PLAN.md)/[唯一验收v1](../../docs/sidequests/DET05_ACCEPTANCE.md)。10 帧 13466 人体点经用户确认冻结 gt_v1；严格纯柱规则下每条目 1–6 根纯柱；仅纯柱内 first32→z_rank32：215540/32 位置分 0.056→0.147、GT 锚排名 148→7、首出含 GT 终框，215623/33 +0.016，其余 ±0.011 内或不可切换；单帧同人同场景，识别可用性未定。SUBMITTED，未 ACCEPTED。

最新（2026-10-08）：[DET-04同扫描背景删除与机制归因](../../docs/sidequests/evidence/2026-10-08_det04_r1/README.md)，[预注册计划](../../docs/sidequests/DET04_PLAN.md)/[唯一验收v1](../../docs/sidequests/DET04_ACCEPTANCE.md)。8次新前向：前三固定帧相交柱独留增分、加回预声明近地面柱降分，第四帧独留降分；背景存在性不能统一解释。审计旧context为B同扫描点按C/E源ID选取，无外来XYZI注入。506对描述相关、7负帧均覆盖改善却anchor负响应、三空场同anchor≥0.5全部保留；单一主因/识别可用性未定。SUBMITTED，未ACCEPTED，主线继续暂停。

最新（2026-10-08）：[DET-03低分因果排查报告](../../docs/sidequests/evidence/2026-10-08_det03_r1/README.md)，[先行计划](../../docs/sidequests/DET03_PLAN.md)/[本轮唯一验收v1](../../docs/sidequests/DET03_ACCEPTANCE.md)。完成506组同帧采样配对及局部/外部柱冻结实验；发现并修正本实验CPU NMS、位置包含和BEV绘图的yaw方向，与固定上游的顺时针KITTI ry一致。历史DET-01/02位置统计及图不回填，不能当修正后输出。先到32选点偏置与周围场景删除均有因果支持，但无人模板覆盖采样后出现≥0.5行人假阳性；单一主因及可用识别人方案尚未确定。实际上游ATen/GPU运行等价BLOCKED；host原kernel正文执行不冒充GPU逐值验证。主线继续暂停。

最新：2026-10-08已完成 [DET-02固定无人模板去背景对照](../../docs/sidequests/evidence/2026-10-07_det02_r1/README.md)，[先行计划](../../docs/sidequests/DET02_PLAN.md)/[本单唯一验收v1](../../docs/sidequests/DET02_ACCEPTANCE.md)。用户确认233658无人空场；54帧三法配平推荐TLS，固定reference图→四人体253帧×5输入对照。背景删除生效、定位邻域保留约99.7%，此权重前景化后仍低分。原主线保持暂停。

2026-10-07 最新补充：[人工定位种子逐帧对照 R2](../../docs/sidequests/evidence/2026-10-07_det01_r2/README.md)。用户确认四段同一真人站立/举手；真人定位点相关框分数全部<0.3，之前全场最高分来自别处。精确框、蒙太奇坐标绑定尚缺，不能报告P/R。旧R1结果保留历史，不回填。

2026-10-07 用户暂停原开发，另开 `codex/human-detector-models`。原工作树 `D:/Code/ldiar` 保留；本实验位于独立 Codex worktree，仅离线文件操作。用户指定本机 CPU 和四个静止会话：215540、215607、215623、215643，检测前配平。这里的静止描述不构成“无人”GT，静止人仍可检测，因此不做背景扣除。

本单独立于 HF/GL、HC/HR 主线；不激活 dormant `ML/`，不启动 HR-09，不接 ROS/生产 UI。唯一现行 [DET-01 v2 验收表](../../docs/sidequests/DET01_ACCEPTANCE_V2.md)，[结果和限制](../../docs/sidequests/evidence/2026-10-07_det01_r1/README.md)，[回传](../../docs/sidequests/returns/DET-01.md)。v1、203349 抽帧、four_r1 是历史调试记录。

## PointPillars CPU

复用 [zhulf0804/PointPillars](https://github.com/zhulf0804/PointPillars) 的模型/anchor 源码和该仓库自身 KITTI 三分类权重（Pedestrian、Cyclist、Car），commit 固定为 `620e6b0d07e4cb37b7b0114f26b934e8be92a0ba`，MIT LICENSE 与文件 SHA 保存在 `artifacts/upstream/provenance.json`。不把它称为 OpenMMLab 官方 checkpoint。

本机已安装 Python 3.12.10、PyTorch 2.12.0+cpu、NumPy、Shapely；不改全局环境。`cpu_pointpillars.py` 复用上游 class/function 的 AST，避开训练/可视化/CUDA imports；仅替换 hard voxelization、旋转 polygon IoU NMS，旧 meshgrid 加 `indexing=ij`。全 checkpoint 严格加载，启动时复核上游 SHA。仅推理，不提供训练。GPU 逐值等价尚未验证，CPU 时间包括体素化/网络/后处理，不含读取、配平、模型加载。

```powershell
python -B -W error -m unittest discover -s sidequests/human_detectors -p test_experiment.py -v
python -B -W error sidequests/human_detectors/batch_static.py --data-root D:/Code/ldiar/captures/remote --out sidequests/human_detectors/artifacts/static_four_new
```

每次输出必须是新目录，不覆盖。默认强度除数 1023 是实验输入归一化假设（该传感器观测接近 1000），可用 `--intensity-divisor` 对照；不是已标定的强度响应。配平后模型 Z 再偏移 -1.73m，用于 KITTI 模型视点假设，不冒充机器人安装高度。源 XYZ=0 在变换前过滤并记账，16B/28B 解码、非法数据、旋转/强度、CPU ops 有检查。

四组均调用工作区既有 `leveling.run_job` 的 auto/floor v3 路径，不改算法或门槛，独立留帧、TLS/SVD/RANSAC报告和完整配平数据保存于新输出目录。26°/0°/1.1m 只作为已有软件的名义搜索初值/参考，结果来自各自拟合；物理、外参、生产资格均 false。单方法 TLS 有效但三法冲突时仅用作本支线实验，不升级为推荐。

## CenterPoint CPU

选用 [MMDetection3D v1.4.0 的 CenterPoint pillar02 + circle NMS](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/configs/centerpoint/metafile.yml)，其中包含 pedestrian 任务。它使用 5D 输入 XYZI + 相对 sweep 时间；单帧导出第5列为零，不把 ring/设备绝对时间当时间差，也不未经配准叠帧。其权重的训练域是 nuScenes、多 sweep，与当前静止室内单 sweep 存在输入差异。

```powershell
python -B -W error sidequests/human_detectors/experiment.py export --session D:/Code/ldiar/captures/remote/cap_20261007_215540 --transform sidequests/human_detectors/artifacts/static_four_r2/leveling/cap_20261007_215540/tls/transform.json --frames 0,20,40 --model-z -1.73 --intensity-divisor 1023 --out sidequests/human_detectors/artifacts/centerpoint_inputs_new
python -B -W error sidequests/human_detectors/experiment.py run --model centerpoint --input sidequests/human_detectors/artifacts/centerpoint_inputs_new --out sidequests/human_detectors/artifacts/centerpoint_new
```

当前 `mmdet3d` 缺失，MMCV 2.1.0 对本机 Python 3.12 的二进制下载未找到可用包（原始错误在证据目录）。未执行 CenterPoint 网络前向、未下载它的权重、未生成比较成绩，状态 BLOCKED。后续需隔离的兼容 Python/MMCV/MMDetection3D CPU 算子环境；不将缺依赖说成该模型天生不能 CPU 推理。

模型输出统一 `source=model`。人标空缺时只报告候选分数/耗时，不报告 Precision/Recall，不写回人工标注。全部大二进制及权重在被忽略的 `artifacts/` 中；可审计摘要和日志在 `docs/sidequests/evidence/`。
