# ML — 机器学习预留区

后续实验顺序与已完成的因果前缀/目标域标签盘点见 [下一步计划](docs/NEXT_STEPS.md)。优先短窗口训练，其次独立环境验证，再进入有来源绑定的 IFW192S 评估和本地部署候选。

> 2026-10-22 更新：用户明确要求公开数据下载、核对与训练，本轮独立离线基线已启用并完成。数据位于 `data/downloads/public_lidar_20261022/`，模型位于 `ML/models/public_lidar_20261022/`，结果与限制见 [公开数据训练记录](docs/public_lidar_20261022.md)。这不替代原 HR-09 自采方案，也未部署到板端。下文为此前预留/封存状态记录。

> 2026-10-22 晚更新：深度基线修正后 E01 窗口 89.22%/序列 95.56%，但冻结后跨环境（E02/E03/E04）塌缩到 11.14%/4.61%/3.95%，三环境重训后 E04 仍 4.01%；详见 [深度 v2 记录](docs/deep_lidar_v2_20261022.md) 与 `docs/evidence/2026-10-22_deep_lidar_v2/`。下一优先是人体点集与尺度/背景归一化，而不是继续堆整场景数据。

**状态：预留（dormant）。** 现阶段 HF 主线是几何/状态机方法（`src/human_fall_detection/`），不依赖任何学习模型。本目录只为将来"规则法天花板到了、转学习法"那一天留好位置，**当前不入任何主线/支线构建**。

## 这里有什么

| 路径 | 内容 | 进 git? |
|---|---|---|
| `LI-DATA/` | Blender+LiDAR 合成的「跌倒 500 / 非跌倒 500」点云数据集（约 643MB，65,487 帧 CSV）。字段含逐点真值 `categoryID/partID`、干净+加噪双份坐标。 | ❌ 已 gitignore |
| `data/` | 训练数据落地区（除 LI-DATA 外的派生集/切分） | 按文件定 |
| `src/` | 未来模型/训练/推理代码 | ✅ |
| `docs/` | 数据集说明、实验记录、模型卡 | ✅ |
| `notebooks/` | 探索性分析 | ✅（不含大数据） |
| `models/` | 训练产物（权重） | ❌ 建议 ignore |

## LI-DATA 速览

- **标签**：`Fall Data 500 poses/`（10 个 PoseSet，含撞击类）vs `No Fall Data 500 poses/`（Walking/Running/Squat/Sitting/Standing/Pushing/Drinking/LeftTurn/Stretching）—— 深蹲/坐立正是几何法最难的 hard negative。
- **CSV 字段**：`categoryID;partID;X;Y;Z;distance;X/Y/Z_noise;distance_noise;intensity;red;green;blue`。
- **与本仓库雷达的差异**（重要）：虚拟雷达贴地（z≈0），IFW192S 是高装俯视；扫描模式/密度/噪声模型都不同。**不能直接喂给 HF 几何链**，价值仅在监督学习的 fall/non-fall 二分类料。

## 已知适配器

`sidequests/lidata_adapter/` 已有一个"LI-DATA → fall_replay 可读 npz"的转换器 + 渲染器（详其 README）。它把 LI-DATA 接到主线**回放可视化**用，结论是「喂不进跌倒判定主链路」——几何配置差异，非 bug。若走 ML 路线，该转换器可作数据加载的起点参考。

## 启用条件（防提前动工）

满足以下任一再动 `src/` / `notebooks/`：
1. HF 主线几何链验收收官，且实测发现有学习法才能解的系统性漏检/误检类别；
2. 用户明确拍板立项 ML 支线（开工单，走 `docs/sidequests/` 流程）。

在那之前本目录只放数据与文档，不写模型代码。

---

**2026-10-03 HR-09 已立案并同日封存** → `docs/human_capture/tickets/HR-09.md`。

该工单定义了 ML 在本仓库**唯一**被允许的正路：用 IFW192S 自采+AI 判读的姿势数据重训 RF（代码零改动复用 `pc_apps/human_ml/`）。封存前状态：`models/rf_v0_lidata.joblib`（域内 acc=0.999、跨域全误判 fall）+ `docs/hf_v0_report.md` + 6 段 `captures/remote/<sid>/ml_labels.json` 全部留仓备对照。**激活口令 = 「开工 HR-09」**，接到口令的实例须按工单 §三 先核定采集。
