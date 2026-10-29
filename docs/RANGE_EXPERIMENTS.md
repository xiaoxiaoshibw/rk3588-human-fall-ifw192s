# W2、同步与测量来源的联合离线入口

`tools/range_experiment.py` 将显式 W2 回放、已有同步审计和既有规则状态机连成独立实验。生产节点、页面、配置和 W1/W2 推理保持原样。它不采样、不补点、不拟合基线或模型，也不启用 HMM。

## 运行

从仓库根目录运行；输出必须为不存在的新目录，不能位于 session/data/captures 内。

```powershell
python -B -W error tools/range_experiment.py --session data/sessions/cap_20261018_110029 --replay-run docs/evidence/2026-10-23_range_sync_integration/verified/replay_386 --ground docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json --out docs/evidence/<new_run>
python -B -W error tools/range_experiment.py --session data/sessions/cap_20261023_215952 --out docs/evidence/<new_joint_run>
python -B -W error -m unittest discover -s tools -p test_range_experiment.py
```

第一条消费同源 W2 的 `CONFIG.json`、`SUMMARY.json`、`frames.jsonl`，用同一原生 192×256 方向表和 W1 参数复算组件。地面必须与该回放配置完全一致，包括缺省地面；输入、RAW 坐标、grid、epoch、地面与原始 provenance 都绑定 SHA。W2 的两个 CLI 和全部 core 源码清单必须完整且匹配，缺失或变化时标为 STALE，处理帧数为 0，不用新代码解释旧行。完整/单帧推理摘要、账本字节和配置摘要分别复核。

第二条只审计原始测量和同步来源；不因联合会话已有 51 帧就臆定为空场前缀，也不运行 W2/规则。`--limit N` 只用于此模式。W2 的因果前缀应先由原 CLI `--limit` 生成，再独立审计。

重查加 `--previous <old_directory>`。旧 SUMMARY 自身内容摘要也须完整；输入、工具、回放、地面、模式或 `[0,N)` 帧范围改变即 STALE。时钟质量统计始终覆盖整个原始会话，与实际审计帧范围分列。

可选 `--alignment <file.json>` 沿用 [SYNC_AUDIT.md](SYNC_AUDIT.md) 格式，另需 `source_binding` 精确包含五份源文件的 `{bytes,sha256}`，缺失文件用 null。该字段与输出 `SYNC_AUDIT.json.binding` 中 meta.json、points.bin、joint.json、camera_frames.jsonl、camera.mjpeg 五项相同。无此绑定记 UNBOUND，错配拒绝。本入口始终 `temporal_link_applied=false`，不借偏移把相机、另一会话或旧参考的点混入当前测量；RECORDED 也不代表物理同步通过。

## 输出与口径

- `SOURCE_ROWS.jsonl`：逐帧原始 offset/count/SHA、decode 拒绝分桶、重复回波行，以及 W2 当前组件并集/互斥归属、未分配组件行、目标行数。source_rows 只标识同帧来源，跨帧同一行号没有点身份含义。
- `RULE_BASELINE.jsonl`：相同当前目标 XYZ 进入既有 `rebuild_candidate`、`FeatureExtractor`、`FallStateMachine`。预测/歧义不携带实测行、特征或速度；不能进入稳定规则目标。无地面高度 unknown。无站姿基线，固定 `mode_verified=false,allow_confirmed=false`，不产确认事件。
- `SYNC_AUDIT.json`：保留独立工具的五源绑定与质量信息。纳秒时钟另以整数差分统计，避免浮点 epoch 舍入掩盖 1 ns 回退；不混 bag 时间和 header 时间。
- `SUMMARY.json`：有效分母、行数汇总、重复比例、规则状态、同源绑定、旧报告状态和摘要。空实测输出的重复比例为 null，不能写 0%；原始 decode 的 duplicate_rows 与输出重复是两种口径。

每帧原始行必须被 decode 有效行及五类拒绝完整且互斥地分割。输出只使用当前保留组件的真实行，每组件最多归属一轨；按轨重组不补回波。未选择 decoded/retained 行表示软件选择范围，不是物理丢点率，也不标注人体/家具。读取结束后再次核对全部输入、地面/provenance、工具和标定 SHA。

规则旁路用于固定输入的软件对照。未供应站姿基线时高姿态可能保持 unknown；低姿态出生仍为 low_posture_unclassified。合成下降序列可进入 suspected，但 confirmed 始终禁用。这不是完整 W4/HMM 或真实跌倒评测。

## 2026-10-23 实际结果

最终证据 [complete/CHECKS.json](evidence/2026-10-23_range_sync_integration/complete/CHECKS.json)，命令/失败日志在父目录。合并来源为任务“开始跌倒检测借鉴开发”的独立同步工具与本会话已完成的 P0/W2；同一工作树整合，无 Git 合并操作。

| 审计 | 386 帧 | 780 帧 |
|---|---:|---:|
| 原始行 | 18,951,860 | 38,298,918 |
| decode 有效唯一行 | 14,361,073 | 29,049,839 |
| 当前实测轨来源行 | 639,627 | 912,064 |
| 保留组件未分配行 | 11,992 | 104,669 |
| 稳定目标帧 | 269 | 355 |
| 重复/外来/非法输出行 | 0 / 0 / 0 | 0 / 0 / 0 |
| 既有规则状态 | unknown 376，低姿态未分类 10 | unknown 780（无同源地面） |

386 新跑的纯推理 SHA `c8ad205a9b51c9f61a54f27c481e1e95fae59ffa26c356380a32e5f11bc64250` 与 P0/W2 最终证据相同；780 输入为既有最终回放，SHA `3b1652093f9632b2441f115b3c1f4c49e22da0e1a1932a7186a98b49cc953a3c`。120 帧前缀的推理、来源与规则逐帧相同。不是新的人体目标召回成绩。

215952 联合会话共 51 雷达/69 相机帧：2,546,816 原始行 = 1,890,889 有效唯一行 + 620,722 零/近距离拒绝 + 35,205 同 ray 重复回波行。重复回波不算造点或实际丢帧。当前 points.bin 71,310,848 字节完整，SHA `d4f7cc881c614af3ceeaf9ab81040833d4a9fdb049f49d7bc7b5d5340b9742c5`；原 joint.json 的 failed/下载错误照实保留。两次完整输出逐字节相同，重查 UNCHANGED。最大 header 间隔 0.207329 s 仅是时钟观测，真实采样丢帧 UNKNOWN。缺独立双路锚，物理同步偏移/误差 UNKNOWN。

新增 26、同步 11、核心 755、capture 69、联合 11 项测试通过，Python 均 `-B -W error`。本地隔离 Python 3.8.10/NumPy 1.17.4 下新增 26/同步 11 及完整 386 帧 CLI 通过，来源账本逐字节相同，规则数值最大差 `1.11e-15`，不是 ARM 板端测试。首次隔离环境 CLI 缺 tools 导入路径的失败已修，日志保留；源码清单缺项亦有直接回归。

38 个既有 W1/W2 源码/测试文件及原同步工具 SHA 保持。本轮没有新性能结论，审计开销不得替代算法计时。原 G1a PASS，G1b 5.448% FAIL，G1c 三轮未稳定小于 10 ms；原 G2 小于 15 ms 及候选 PC 20 ms 均未稳定通过。f360 尾部仍 UNRESOLVED，接受几何重组不使原 G1b 通过。

人体点级、真人身份、倒地/浴室效果、实际采样丢帧、物理同步及新链板端性能均 UNKNOWN。下一步可独立推进 CPU 尾延迟归因；真实同步/事件对照需要现存独立锚或 GT，当前不重复核查、不自动采集或拟合。

2026-10-24 已新增 [同款绿框/相机/曲线报警展示](RANGE_REPLAY_VIEW.md)：独立读取本审计及W2账本，逐帧绑定后输出可双击打开的HTML，不再次运行拟合或算法。原126帧历史样例可直接重绘，因果386/780使用自己的真实输入与相机缺失状态。
