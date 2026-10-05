# human_pcl — PC 侧 PCL 炼丹房

HR-06 落地的最小独立环境。**不动板端，不动 GL，不动 HR-01..05**。

## 干啥用

PC 上跑 PCL 干两件事（不是现在马上要做，是准备好了可以做）：
1. **离线 ground 拟合**：从会话的 `points.bin` 推 R/t（雷达系 → 地面系），写回 `meta.json.ground_local` —— 与 GL-02 板端结果对账
2. **离线 candidate 自动生成**：region growing / Euclidean clustering，产默认人形框，PC 回放器（HR-05）只需人工微调

板端永远 NumPy only（CLAUDE.md 硬约束）——PC 这边放开。

## 环境（一次性装）

```bat
pc_apps\human_pcl\setup_env.bat
```

幂等，新建或升级均可。装到 `C:\Users\30680\miniconda3\envs\human_pcl\`：
- python=3.9（python-pcl 的 wheel 只到 py39）
- python-pcl 0.3.0rc1（conda-forge）
- pcl 1.15.1（conda-forge C++ 库）
- numpy

## demo 跑通冒烟

```bat
C:\Users\30680\miniconda3\envs\human_pcl\python.exe pc_apps\human_pcl\demo_ground_fit.py
```

期望三行输出（末行 <1.0 为 PASS）：
```
法向量:  n_fit=(a, b, c)  n_true=(0.4588, 0.6117, -0.6428)
内点数:  900 / 1000  (期望≈900,含平面真点)
夹角:  0.xxx deg  (PASS 若 < 1.0)
```

## 边界 / 不做什么

- 不接 GL-02 ground_local 契约（归 GL-04 主线，OpenCode 推进）
- 不接真实会话（HR-07 立项才接）
- 不写 pybind11（后续要 C++ 自卷扩 PCL 时再单独立项）
- 不进 PATH、不动 base pyqt、不动系统 Python

## 下一单指向

HR-06 ≺ **HR-07（待立）**：把 `demo_ground_fit.py` 升级成 `fit_ground.py <sid>`，读真会话、输出 R/t、写回 `meta.json`，与 GL-02 板端产物对照。
