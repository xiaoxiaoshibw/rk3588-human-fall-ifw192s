# W2 显式离线跟踪实验（2026-10-23）

已实现 `core/range_tracker.py`、`range_features.py` 与 `scripts/replay_range_tracking.py`。输入是 W1 原生192×256 RangeFrame；生产节点、页面、控制台和配置没有接入此入口。

```powershell
python -B -W error src/human_fall_detection/scripts/replay_range_tracking.py --frontend range_v1 --session data/sessions/cap_20261018_110029 --empty-prefix-frames 50 --ground docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json --out docs/evidence/<new_directory>
python -B -W error -m unittest discover -s src/human_fall_detection/tests -p "test_range*.py"
```

不提供 `--ground` 时仍可跟踪，高度为unknown。显式地面必须通过meta/points、RAW坐标、grid/方向表、epoch和原始provenance字节SHA校验；不能将主会话地面用于780帧的另一会话。没有进行地面或模型拟合。

## 已验证的软件行为

- source_rows仅表示当前帧行；跨帧使用ray支撑和运动补偿空间支撑。预测仅保留位置状态，来源行为空、实测特征为空。
- 因果`[x,y,vx,vy]`为RAW坐标米/秒；初始关联门`0.5+2.5*dt`，三次有效观测出生，未观测超过1.5s删除。重复/倒退时钟、超过2s断档、输入/grid/有效地面变化重置代次。
- 一对一匹配；近并列、竞争及无支撑的几何竞争者保持unknown。目标评分只用新链点数、距离和稳定轨，不读旧参考。低姿态可出生，不产生跌倒事件。
- 碎片归组复用既有`support_composition.evaluate`默认门，核对历史支撑、当前实测间隙、包络、刚体残差和竞争。不修改W1合并规则，只并当前真实组件行，不补回波。
- 几何复用`rebuild_candidate`；无效/未绑定地面高度unknown；PCA退化`axis_valid=false`。PCA是源坐标无向主轴，不是已验证人体轴；地面误差和visible_ratio缺可信分母则null+原因。
- 完整账本SHA包含诊断；`inference_output_sha256`单独绑定纯推理。是否提供旧参考，386帧纯推理SHA完全一致。

## 实际结果与边界

最终证据`docs/evidence/2026-10-23_range_p0_w2/verified/`，失败和中间版本保留在父目录。核心755/capture69/标定2通过；本地Python3.8.10/NumPy1.17.4的45项定向测试和386帧完整对照通过，最大数值差8.88e-15（无向PCA允许符号等价），不是ARM性能。

386/780各三轮账本确定，120帧前缀与完整运行逐字段一致。独立原始XYZ审计覆盖386帧639627、780帧912064个实测轨来源行，当前组件并集、互斥归属、bbox/质心/高度和预测空测量通过。

f360以f359实测支撑将组件23+17归组为当前2308行=2221旧参考行+87参考外行。包含完整187行碎片，没有读旧参考挑入121行。原41个去噪拒绝和1个背景未知行仍未存活。归组是几何实验，语义尾部仍UNRESOLVED，原W1 G1b仍FAIL。

旧参考258帧中新链有目标256帧（99.2248%）；同帧诊断组件行数加权交集99.9512%，f372/373交集仍未达97%，全帧交集门FAIL。它们是旧参考代理，不是人体召回或真人身份成绩。

780的730个非预热帧中，W1有retained组件378帧/无352帧；W2有目标355帧/空375帧，16次软件目标输出从有到无。逐帧原因、歧义和归组另存账本，完整运行不算效果通过。

| 最终三轮PC P95 | 386帧 | 780帧 |
|---|---|---|
| W1+W2，含特征，ms | 23.521 / 18.952 / 22.025 | 27.600 / 21.895 / 23.771 |
| 加读取/诊断/JSON/缓冲写的循环，ms | 33.682 / 26.212 / 31.055 | 30.987 / 24.345 / 26.802 |

保留逐帧原值及n/P50/P95/P99/max；循环不含计时记录器、最终flush、启动SHA和背景拟合，CLI墙钟另列。更早同输入且纯推理摘要一致的慢轮（386帧P95 29.667/167.496/22.903ms）保留，不挑最快轮。原G2<15ms与候选PC≤20ms均未稳定通过，外部PC负载波动归因未解，阶段P95不相加。

人体点级precision/recall、真人ID切换率、倒地/浴室效果、物理资格和板端性能UNKNOWN。下一步是CPU整链尾延迟归因及独立目标/身份/事件真值；本轮停止在离线实验，不自动采集、拟合或操作设备。

后续同工作树整合新增 [RANGE_EXPERIMENTS.md](RANGE_EXPERIMENTS.md)：独立消费 W2 已绑定回放，复算当前组件并集并联接既有同步审计/规则旁路。386/780 的 1,551,691 实测来源行、120 因果前缀和纯推理 SHA 再核对通过；W1/W2 源码未改，原 G1/G2 失败保持。证据 `docs/evidence/2026-10-23_range_sync_integration/complete/`。
