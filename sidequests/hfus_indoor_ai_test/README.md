# HFUS-INDOOR-AI-TEST-01

Windows CPU 室内 LiDAR 独立实验。只从用户三个 ZIP 流式读取，原始数据不写入、不复制、不重新解压。不是生产检测器，不解锁 HFUS E1 / HR09。

双击 `demo/start_demo.bat`（固定 `r7_20261015`，不会选择“最新”），或：

```powershell
python -B -W error sidequests/hfus_indoor_ai_test/demo/server.py --run r7_20261015
```

服务仅绑定127.0.0.1，自动选空闲端口，终端打印准确 `/indoor-ai/r7_20261015/` URL并打开浏览器，不停止其他占用端口的服务。需要本工作区及其原始三个ZIP，不是独立再分发数据包。初次启动核ZIP SHA；成员/产物/运行源码漂移拒绝。最终run引用其冻结父run的大型候选账本，二者均须保留。

三栏为完整源点云、待核验AABB代理框、实际未分类几何候选。相机同步；可切 det/track、帧、模型、俯视/侧视、播放暂停、显隐、全点模式和完整困难队列。默认每4源行显示1点，始终显示原始/显示点数。模型BLOCKED/UNTRAINED/NOT_RUN时预测为空；无人审、无可信人体置信度，不将框中点染成人体语义。

旋转/末列、完备性与独立采集组仍UNKNOWN。没有可信两类监督，RF和PointNet训练BLOCKED，神经网络启动0/optimizer_steps0。主IoU与P/R/F1、可信候选覆盖/碎片、逐点与空场指标不可评价。未分类聚类候选不能称“成功识别人”。代理诊断只供人工审阅，不能触发下一阶段性能规则。

检查：

```powershell
python -B -W error -m unittest discover -s sidequests/hfus_indoor_ai_test -p test_indoor.py
node sidequests/hfus_indoor_ai_test/demo/state.test.js
```

首屏run `r1_20261015`、前10帧真实候选预览 `r4preview_20261015`、完整数值父run `r4_20261015`、封存展示run `r5_20261015`。失败r2/r3保留；不清理原数据腾空间。唯一验收：`docs/human_capture/evidence/2026-10-15_hfus_indoor_ai_plan_r1/ACCEPTANCE_V2.md`。最终证据：`docs/human_capture/evidence/2026-10-15_hfus_indoor_ai_dev_r1_20261015/`。
