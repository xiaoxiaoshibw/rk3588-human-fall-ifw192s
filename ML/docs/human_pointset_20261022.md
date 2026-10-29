# 人体附近点集实验：坐标审计与本地接口

本轮接续“继续设计开发”，只开展离线软件实现与验证，没有启动新的实验训练、模型/数据下载或设备操作。证据位于 `docs/evidence/2026-10-22_human_pointset/`。

## 发现与解释边界

原计划不能直接用 `ground_truth.npy` 包络裁剪 LiDAR。预先固定每环境首位受试者 S01/S11/S21/S31 的 A01/A12/A27 共 12 条完整序列，按照作者 loader 的 `frame001 → GT[0]` 对应关系读取。3,564 帧在原始坐标下用关节 AABB 外扩 0.25 裁剪，全部得到 0 点。这个结果证明所检查输入无法直接共用坐标，不能说明人体附近没有 LiDAR 回波，也没有估计真实外参。

作者[论文 §3.1–3.2](https://ar5iv.labs.arxiv.org/html/2305.10345)把 RGB 相机中心定义为世界原点，说明 LiDAR/mmWave 使用右手坐标；所检查的论文与 [官方 loader](https://github.com/ybhbingo/MMFi_dataset/blob/main/mmfi_lib/mmfi.py)未提供可直接用于当前关节到 LiDAR 的完整数值变换。loader 对 LiDAR 直接读取 float64 XYZ，没有施加这一步变换。不要把右手系等同于相同轴向与原点，也不要从点数最大化反求一个“已验证”标定。

上一轮跨环境时人员也同时变化，环境几何依赖是合理假设，尚非由受控消融建立的唯一因果解释。E04 已反复用于观察，后续结果应称探索性复测，不能重新称为未见的独立测试环境。

## 已实现的输入契约

- `ML/src/human_pointset.py`：显式 proper rigid 4×4 变换，列向量约定 `lidar = R @ joints + t`；输入单位必须已一致。逐帧关节包络固定外扩，不用未来帧、不自动平移/轴交换/尺度拟合。裁剪保留原始行索引。
- `ML/src/prepare_human_pointset.py`：原包只读；检查 ZIP 名称唯一、帧号从 1 连续、关节精确 `(T,17,3)`、有限值与 XYZ 字节数，逐帧记录成员/关节 SHA、GT 索引和裁剪行。消费成员由 zipfile 校验 CRC；同时绑定整包 SHA。
- 审计模式允许未经核实的恒等变换，但不产出训练缓存。`--prepare` 要求外参 manifest 声明 `verified`、单位 `m`，并绑定现有校验证据文件的 SHA。该声明和文件绑定本身不等于软件证明物理标定正确，证据内容仍必须真正支持相应环境。任何帧少于 10 点都会保留失败记录、阻止整份缓存发布，不丢困难帧、不填假点、不退回整场景。
- 合格缓存保持现有 `{E01/S01/A01: float32[T,256,3]}` NPZ 接口；采样沿用冻结基线的原始成员名 SHA seed，足够时无放回、不足 256 时才重复已有行。没有新增中心/尺度归一化或网络结构，方便后续单因素比较。
- `TargetPointCache`：推理侧只接现有跟踪结果的实测锁定目标行，不用关节 GT、不另选最大簇。换身份/epoch/动作代际/选择版本/标定、重复/倒退时间、超过 0.5 秒断档、非法点行、空或预测目标均清历史。足 30 帧才输出窗口，最多保存 30×256×3 点；窗口为副本。返回原始采样行可重建输入。

外参 manifest 格式如下，实际研究中必须换成有来源且适用于相应环境的值；这里不提供“看似对齐”的示例矩阵：

```text
joint_to_lidar: 4×4 matrix
units: m
status: verified
evidence:
  path: relative/path/to/existing_calibration_evidence.json
  sha256: exact SHA-256 of that file
```

## 实际验证

`python -B -W error -m unittest discover -s ML/src -p test_*.py` 共 19 项通过，其中新增 5 项覆盖裁剪边界/变换、采样复现、生命周期/非法行、错帧/坏关节、完整 ZIP→缓存及空裁剪禁止回退。原 ML 14 项保持通过。合成外参只用于测试，未赋予真实数据物理资格。

`ML/src/replay_human_pointset.py` 对 `cap_20261018_110029` 从原始 points.bin 读取、解码并核对行，再执行现有完整 ReplayPipeline；保留原开发 harness 前 50 帧为空的假设。先原链，后在相同输入上加入旁路。386 帧中 258 帧实测目标进入缓存、229 个窗口可推理；完整 result/baseline 摘要相同：`6aa6629066956d9949e4188d8c31b1ea69ed6214d0b4a112b1c8924359a21017`。逐帧采样来源、窗口 SHA、概率与身份绑定保存在 `target_replay_final/target_frames.jsonl`，早一轮回放保留在 `target_replay/`。

本次只使用冻结的整场景 v2 fold 0 权重检查目标点接口，不是人体裁剪模型，也没有跨传感器轴校准。概率不是有效动作标签，不能据此判断识别恢复。PC 推理时间仅为旁路调用计时，含首次调用，非完整链实时或板端性能结论。生产核心和页面没有变化。

复现入口：

```powershell
python -B -W error ML/src/prepare_human_pointset.py --archive data/downloads/public_lidar_20261022/E01_lidar_gt.zip --sequences E01/S01/A01 E01/S01/A12 E01/S01/A27 --output docs/evidence/<new-run>/E01
python -B -W error ML/src/replay_human_pointset.py --session data/sessions/cap_20261018_110029 --checkpoint ML/models/deep_lidar_20261022_v2/fold_0.pt --output docs/evidence/<new-run>/target_replay
```

所有输出目录必须新建，已有证据不会覆盖。

## 接下来的实验顺序

1. 取得并核实关节→LiDAR 的外参、单位、环境适用范围与帧对应。当前未解决；不要把猜轴/点数最大化当校准真值。
2. 先审计所有拟入组帧的裁剪覆盖/不足与来源，再生成新缓存。固定几何参数，不按 E04 分类结果调裁剪范围。
3. 将两个问题分开：同模型“整场景训练/整场景测试”对“GT 裁剪训练/GT 裁剪测试”是 oracle 诊断；测试期 GT 裁剪会携带姿态信息，不代表 GT-free 性能。不能只改训练输入、再把未经控制的测试输入差异解释为几何消融效果。
4. 独立考察无 GT 提取器在公开数据上的输入差异，再用 IFW192S 现成跟踪点做外部接口/分布测试。不同传感器与人员、环境共同变化，不能直接计算缺真值的准确率。
5. 新实验训练须遵守仓库明确授权边界；授权后沿用 v2 的固定人员折、256 点、30 帧/步长 10、40 轮与原优化器，写新模型目录，冻结后做探索性跨环境复测。多环境对照固定原 24 轮，不混用预算；有必要时再单独做尺度归一化。

IFW192S 动作/跌倒、点级人体真值、跨传感器对齐及板端性能继续 UNKNOWN。没有用本轮接口通过推翻上一轮泛化失败。
