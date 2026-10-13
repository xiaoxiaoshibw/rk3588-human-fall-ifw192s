# HUMAN-FUSION Demo V1 启动与复现

当前入口：http://127.0.0.1:8791 。双击“启动Demo.cmd”打开现有服务；未运行时启动仓库研究Demo。

源码：D:/Code/ldiar/sidequests/human_fusion_lab 。Demo仅需要已有Node.js，无GPU或Python调用。训练依赖本机已验证的numpy/scikit-learn/xgboost/torch/onnx/onnxruntime/psutil。

手动启动：

```powershell
cd D:/Code/ldiar/sidequests/human_fusion_lab
node server.js 8791
```

默认XGBoost，菜单可选原RF、候选RF51/RF69、一对一跟踪实验。缺模型自动RF回退并显示原因。右侧点候选检查点集/GT距离，青色GT、紫色轨迹。拖动点云旋转、滚轮缩放，拖帧条重建前缀时序，最长会话可能等待数秒。未标区间明确UNKNOWN。

交付源码ZIP不复制原始录制。原始captures/remote保持只读。别处解压后指定数据仓库：

```powershell
$env:HF_REPO_ROOT='D:/Code/ldiar'
node server.js 8791
```

ZIP中的results/cap*.json是精简冻结GT展示记录；仓库原results还保留完整点集/特征/帧级结果。候选数据清单/SHA见DATASET_MANIFEST.json。复制lab到新研究目录或保留结果后，复现：

```powershell
python audit.py
node test_r5.js
node export.js
python train.py
node test_models.js
node evaluate.js
node attribution.js
node unique_tracker.js
```

当前工具会写自己的results/models，不修改生产或captures；如要保留本轮实验，先复制lab。训练第二路线的前缀/数据路径由HF_MODEL_PREFIX/HF_DATASET控制；失败静态路线只用于研究，正常菜单不开放。复制到其他目录执行研究工具时仍需核对脚本ROOT路径（Demo支持HF_REPO_ROOT）。

服务只绑定127.0.0.1，单用户、单活动会话；多页面同时控制可能重建状态，需要多用户时再分离实例。检测P95不含文件/网络JSON/Canvas开销。后台服务PID保存在lab/results/demo_server.pid；手动前台启动可Ctrl+C结束。有服务时直接打开入口，不重复启动。

当前缺项：S8只有53/523帧、S7只有12/251帧有效GT，S9绑定不符；未标区间、陌生人员/家具/新场景及RK3588/NPU性能UNKNOWN。研究SUBMITTED，未完成现场独立验收；详见REPORT.md。
