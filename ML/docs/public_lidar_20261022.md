# 2026-10-22 公开 LiDAR 数据下载与离线训练

用户明确要求“开始下载核对然后开始训练”，本轮按此授权开展独立离线实验。没有部署、采集、训练板端服务或替换既有模型。

## 数据与完整性

| 数据 | 本次实际取得 | 核对 |
|---|---|---|
| [MM-Fi 官方仓库](https://github.com/ybhbingo/MMFi_dataset)的 E01 | 10 人 × 27 动作 × 297 帧：80,190 帧 XYZ，270 份 `297×17×3` 关节标注 | 从作者原始 E01.zip 通过 HTTP Range 取出原 LiDAR 与 ground_truth.npy；80,460 个成员全部匹配原 ZIP 目录的 CRC，逐成员 SHA 留存；派生 ZIP SHA `c1de39e07689ebbac4d9eb9b60741fc0f5256a8c21b3c6dc78796f935573af17` |
| [Synthetic LiDAR Fall](https://zenodo.org/records/19597219) | 实际 900 条序列、65,487 CSV 文件；14 个 `(1)` 文件与对应原帧逐字节相同，不重复入组，实际训练 65,473 帧；451 条 fall / 449 条 nonfall；18 个上级动作目录 | 673,216,404 B，MD5 与作者 `520c0d719cbfe3bf3bbe343bc8328c90` 一致，ZIP CRC 通过；SHA `0e0675b94ef21c2a90d75738ba25926be75220e6915773019e87e5fafae37e31` |

MM-Fi 本次仅 E01，未取得 E02–E04，也未下载相机、毫米波或 WiFi 数据。所选原成员解压字节共 2,241,620,544 B，生成本地 ZIP 2,252,604,086 B；未取得远端原始 22.3 GB ZIP 的整包 SHA。Synthetic 下载内容与网页标称“1000 序列、各 60 帧”不符；不是按网页数字凑样本，实际序列长度为 40–133 帧。数据保存在 `data/downloads/public_lidar_20261022/`，不删除原包、不改已有会话。Synthetic 元数据许可为 CC-BY-4.0；MM-Fi 作者 DOI 记录许可标识为 other-open，原公告和元数据保留在证据目录，不把工具仓库许可当成数据许可。

## 训练与评估

模型输入只有 XYZ 点云，不使用关节真值、类别 ID、partID、强度、文件路径或帧数作为特征。每帧 19 个几何量，经完整序列的均值、标准差、分位数、差分和首尾变化汇成 114 维。绝对位置在序列内消除；不假定源数据物理帧率。复用已有 `lidata_load.parse_csv_bytes`，额外拒绝坏行和非有限坐标；所有入组序列均通过检查，没有靠跳过坏帧拼接时间差分。

两套模型分开训练，避免把 synthetic/real 数据来源变成 fall/nonfall 标签。CPU RandomForest：200 树、max_depth=16、min_samples_leaf=2、class_weight=balanced、random_state=42、n_jobs=4。未搜索超参数或以留出结果调模型。

| 任务 | 样本与切分 | 留出 accuracy | 宏平均 F1 |
|---|---|---:|---:|
| MM-Fi 27 动作分类 | 270 完整序列，按受试者 5 折；每折 8 人训练、2 人测试 | 0.662963 | 0.653919 |
| 合成 fall/nonfall 完整动作分类 | 900 完整序列，按 18 个上级动作目录分组 5 折 | 0.996667 | 0.996667 |

原始帧不随机拆到不同折。每个模型的重载预测与保存前一致；每个序列的留出预测、混淆矩阵、组清单均保留。另训练全量数据候选 `final_model.joblib`，其训练集自测不当成验证分数。最终模型输出在 `ML/models/public_lidar_20261022/{mmfi,synthetic}/`，旧 `rf_person_v1.joblib` / `rf_v0_lidata.joblib` 保留。

## 边界与离线回放

- MM-Fi 结果只证明 E01 的跨人员动作分类基线；没有跨环境评估，不是人体检测、逐帧姿态回归或跌倒检测成绩。
- Synthetic 按目录分组不能证明底层 Mixamo 动画独立；原始动作谱系 UNKNOWN。完整输入重复检查不能排除近重复和共享底层动画。序列 fall 标签不代表每帧都正在跌倒，跌倒起始时刻 UNKNOWN。
- 对历史 `gap_tail/person/target_points.npz` 的 388 帧已选目标，按 60 帧窗口 / 步长 15 进行 22 窗口离线推理；两套 5 折模型与完整训练候选均跑通。它是预提取目标上的模型回放，不是原始点云整链或板端实时测试。没有声称源/目标传感器坐标轴已完成跨域标定。
- 该输入没有可用于上述任务的独立真值。人体语义、IFW192S 跌倒准确率/召回、物理效果和板端性能全部 UNKNOWN；未启用 confirmed、未改现场版本。

## 复跑入口

在仓库根目录，使用新输出目录以保留本轮产物：

```powershell
python -B -W error ML/src/train_public_lidar.py --dataset mmfi --archive data/downloads/public_lidar_20261022/E01_lidar_gt.zip --output ML/models/public_lidar_repeat/mmfi
python -B -W error ML/src/train_public_lidar.py --dataset synthetic --archive "data/downloads/public_lidar_20261022/Dataset (Blender+LiDAR)1000poses.zip" --output ML/models/public_lidar_repeat/synthetic
python -B -W error -m unittest discover -s ML/src -p test_public_lidar.py -v
```

完整训练候选和离线回放入口分别为 `docs/evidence/2026-10-22_public_lidar_training/final_fit.py`、`ML/src/probe_public_lidar.py --help`。环境为 Python 3.12.10 / NumPy 1.26.4 / scikit-learn 1.9.0 / joblib 1.5.3，CPU；不宣称这些 joblib 可直接加载到板端 Python 3.8 环境。

机器证据：`docs/evidence/2026-10-22_public_lidar_training/`。新测试 5 项、已有适配器 6 项均 `-B -W error` 通过。首次编排进程关闭管道不完整产生 ResourceWarning，已保留记录并改为 Popen 上下文管理，生命周期复测通过；训练子进程本体均 exit=0。训练期间观察到其他工作对 5 个核心/测试文件的修改，保留并单列于 CONCURRENT_SOURCE_CHANGES.json，本轮未写这些文件。
