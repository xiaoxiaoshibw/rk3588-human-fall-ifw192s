# DET-01 四静止会话 CPU 试跑（2026-10-07）

当前交付：**SUBMITTED / CenterPoint BLOCKED；未 ACCEPTED**。唯一现行验收表 [v2](../../DET01_ACCEPTANCE_V2.md)。原开发在本会话暂停，实验分支 `codex/human-detector-models`，独立工作区 `C:/Users/30680/.codex/worktrees/human-detector-models/ldiar`，基线 HEAD `cfbb80c57508be1a0435fdb92260f698dc763934`。不 commit/push，不采集/部署。

## 实测结果

使用用户指定的四个静止会话，全部有效帧配平后推理，不做背景扣除。原始元数据核对：215607 是 **67** 帧，215623 是 **66** 帧，与用户表格这两行顺序相反；合计 **253** 帧，二进制大小一致。

| 会话后缀 | 帧 | TLS pitch/roll（度） | TLS t_z（m） | 全会话最高行人分数 | 分数≥0.3候选框数 | 分数≥0.5候选框数 | CPU秒/帧 |
|---|---:|---|---:|---:|---:|---:|---:|
| 215540 | 64 | 26.7646 / -1.1983 | 1.36490 | 0.4645 | 37 | 0 | 0.669 |
| 215607 | 67 | 26.6822 / -1.2222 | 1.36313 | 0.3593 | 17 | 0 | 0.660 |
| 215623 | 66 | 26.6434 / -1.2228 | 1.36209 | 0.3382 | 7 | 0 | 0.655 |
| 215643 | 56 | 27.4363 / -1.1741 | 1.38096 | 0.4691 | 42 | 0 | 0.640 |

计数是所有帧的候选框次数，同一个物体可能重复计数，**不是人数**；0.3/0.5 只是诊断分数刻度，不是经本数据标定的接受门。候选分数不是准确率。上游模型原阈值为 0.1，全部原输出保存在对应 predictions.json。CPU时间含体素化/网络/后处理，4线程，不含配平/加载/读文件；单次测量，不是性能验收。

PointPillars CPU 路径已实际运行，但当前只能证明“模型能产生候选框”，不能证明这些框对应真人。没有真人3D框 GT，Precision/Recall **NOT_RUN**；静止不等于无人。KITTI 示例产生9个 Pedestrian 候选，最高分约0.774，网络和权重加载有基本正向检查。室内俯视 IFW192S 与预训练 KITTI 存在采样、视点、强度及类别域差异；这是可能的解释，尚非经对照证明的根因。

![四会话配平后模型候选框](17_static_four_bev_r2.png)

图选各会话**最高行人分数所在帧**，属于有意选择的诊断视图，不代表平均效果。蓝色0.1–0.3，橙色≥0.3。为显示只保留 x=0–14m、y=±10m 并按3抽点，推理用完整有效点；图框不是GT。

## 配平与输入边界

复用当前分支既有 `leveling.run_job`、floor v3、四ROI、TLS/SVD/RANSAC、三个独立留帧门，不改任何门槛。四组各方法自身质量门通过，TLS各自P95约2.35–2.47cm。215540、215623、215643推荐TLS。**215607无推荐**：TLS与RANSAC offset差0.036866m，超过既有0.03m一致性门，pairwise FAIL原样保留。本支线显式采用自身质量通过的TLS做离线模型试验，不把它升级为三法一致或物理标定。

名义26°/0°/1.1m只用于既有地面搜索初值/测量参考；每个最终R/t由该会话拟合得到。所有物理/外参/运行时资格false，不把t_z当现场安装高度。源SHA、代码SHA、区域、holdout、原始失败、变换均保存在四组 leveling_report/transform.json；完整衍生数据保存在 `sidequests/human_detectors/artifacts/static_four_r2/leveling/`，不覆盖captures。

模型输入：28B每点正确取前四个float32 XYZI；**XYZ全零回波在平移前过滤**，每帧 `source_points/input_points/dropped_zero_xyz/in_model_range`记账。早期four_r1遗漏这一步，会制造原点假点堆，已保留为历史调试记录，不能用于最终结论；新增回归验证此缺陷。最终r2重新配平并重跑253帧。强度除以1023、地面系Z再偏移-1.73m均为明确实验适配假设，不是已核实的传感器强度响应或安装高度。未做参数搜索、训练或阈值降低来追求分数。

## CenterPoint

准备的配置为 MMDetection3D v1.4.0 `centerpoint_pillar02_second_secfpn_head-circlenms_8xb4-cyclic-20e_nus-3d`，含 pedestrian，选择 pillar 路径避免把稀疏卷积作为必要条件。初次运行在导入处失败：`ModuleNotFoundError: No module named 'mmdet3d'`，见 [19_centerpoint_BLOCKED.txt](19_centerpoint_BLOCKED.txt)。CPU MMCV2.1二进制下载尝试见 [12_mmcv_cpu_download.log](12_mmcv_cpu_download.log)，当前Python3.12未找到可用分发包；此前下载站HTTPS探测也出现SSLEOFError。未改全局环境，未下载CenterPoint权重，未执行前向；四会话CenterPoint均 **BLOCKED**，没有模型间效果排名。

恢复条件：准备隔离的兼容 Python/PyTorch/MMCV/MMDetection3D CPU 算子环境，并取得对应 checkpoint。适配器会导出 XYZI+relative sweep time（单帧为0），不把ring或绝对设备戳当time-lag；不要在缺乏跨帧配准时拼10帧伪装nuScenes多sweep输入。不声明CenterPoint算法本身不能CPU推理。

## 验收与证据

| ID | 作者自验 | 证据与边界 |
|---|---|---|
| A01 | PASS（本会话隔离/基线记录） | 00_baseline.json记5127文件含未跟踪SHA；16_original_preservation.json记录原树4文件外部SHA差异，本会话没有写原树，不声称全树静止 |
| A02 | PASS | 14_tests_zero_xyz_r2.log，16B/28B、非法输入/长度/帧号检查 |
| A03 | PASS（离线单方法配平） | 四份leveling_report/transform；215607三法一致性FAIL未改，物理NOT_RUN |
| A04 | PASS（推理执行） | summary.json，四份完整predictions，18上游commit/hash，20 KITTI示例 |
| A05 | BLOCKED | 12下载日志 / 19导入错误；CenterPoint网络未跑 |
| A06 | PASS（输出来源契约） | source=model，无人工GT、无Precision/Recall、无背景扣除；识別准确性NOT_RUN |
| A07 | PASS（CPU单元/示例）；GPU等价NOT_RUN | 7项 `-B -W error` 检查通过，KITTI示例真实前向；未做GPU逐值对照 |
| D01 | NOT_RUN | 无设备、采集、部署、物理验证授权 |

PointPillars源码来自MIT仓库zhulf0804，使用该仓库自身权重而非声称OpenMMLab官方权重；两者骨干相似不能互换checkpoint。CPU仅替换体素化/NMS，并给上游meshgrid显式indexing；严格checkpoint加载、上游SHA验证。来源：[上游实现](https://github.com/zhulf0804/PointPillars/tree/620e6b0d07e4cb37b7b0114f26b934e8be92a0ba)、[CenterPoint模型配置](https://github.com/open-mmlab/mmdetection3d/blob/v1.4.0/configs/centerpoint/metafile.yml)。

主要命令：

```powershell
python -B -W error -m unittest discover -s sidequests/human_detectors -p test_experiment.py -v
python -B -W error sidequests/human_detectors/batch_static.py --data-root D:/Code/ldiar/captures/remote --out sidequests/human_detectors/artifacts/static_four_r2
python -B -W error sidequests/human_detectors/plot_static.py --results sidequests/human_detectors/artifacts/static_four_r2 --data-root D:/Code/ldiar/captures/remote --out docs/sidequests/evidence/2026-10-07_det01_r1/17_static_four_bev_r2.png
```

以上测试、r2 batch、绘图实际退出码0；batch逐会话无BLOCKED，记录在15日志。早期CenterPoint直接运行退出1；pip探测封装脚本最终exit0，但下载步骤明确报无匹配分发，不能冒称安装成功。文件hash在22_submission_sha.json。原仓库master/HEAD保留，本会话不续原开发；观察到fetch_lib_test.py、panel.js、panel.test.js、sessions_test.py在原工作树另有SHA变化，来源未确定，原样保留并记录，不回滚。
