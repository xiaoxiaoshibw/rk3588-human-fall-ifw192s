# 显式离线逐帧运行时

2026-10-25新增共享结果：软件核验通过、原始输入/源码未变及实际消费序列复跑一致后，运行目录生成 `analysis.json`（`range_fall_analysis/1`）。它保留RAW米制目标框、真实来源行、源时间、轨迹代次、规则状态、疑似区间以及meta/points/config/source SHA，供Qt应用和Web标注台读取。三份原始账本的SHA写入SUMMARY，未完成/被修改的运行不能导出。有限前缀与丢帧运行如实标记，确认告警保持关闭。`analysis.py`也提供只读注册与逐帧源SHA/包围框核验；它不改变W1/W2或跌倒门限。

`core/range_runtime.py` 消费当前 packed frame，复用原生192×256方向表、冻结射线背景、去噪、组件、RangeTracker、FeatureExtractor 与 FallStateMachine。生产默认仍使用旧链。没有地面或站姿/模型拟合、设备调用、自动确认事件。

## 入口

在仓库根目录运行；输出必须为新目录，不得位于原始数据目录。

```powershell
# 全帧确定性运行；386会话使用其既有绑定地面
python -B -W error pc_apps/range_fall/runtime_replay.py --session data/sessions/cap_20261018_110029 --empty-prefix-frames 50 --ground docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json --out docs/evidence/<new_run>

# 同一会话按源时钟节奏到达，单工作线程、size-1 latest队列；只在PC本地提供页面
python -B -W error pc_apps/range_fall/runtime_replay.py --session data/sessions/cap_20261018_110029 --empty-prefix-frames 50 --ground docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json --paced --serve 8940 --out docs/evidence/<new_paced_run>

# 780会话不使用其它会话地面，高度UNKNOWN
python -B -W error pc_apps/range_fall/runtime_replay.py --session data/sessions/cap_20261017_113516 --empty-prefix-frames 50 --out docs/evidence/<new_780_run>
```

页面为 <http://127.0.0.1:8940/>，使用同一 `replay_template.html`。CLI打印实际端口；回放结束默认继续提供当前页面，Ctrl+C结束本地服务。`--exit-after-replay` 用于有界CLI验证。`--speed`改变本地到达节奏，`--processing-delay-s`只注入处理落后，不冒称算法耗时。

`--limit 120`可核对因果前缀。全帧模式可用 `--compare-run <W2目录> --compare-rules <range_experiment目录>`逐帧对照旧账本；该模式重新核对输入/配置、旧来源文件及账本摘要，不把历史运行重新认证成包含新增源码的完整审计。源节奏模式只核对实际消费序列，不拿丢帧运行与全帧结果强求相等。

`--no-detail`只关decode/组件内部细分计时，用于量计时器开销；`--legacy-display`只切回既有显示抽样器，用于单因素对照。两者不改变检测、关联或规则参数。默认显示器以字节记录去重代替结构化三列排序，保持体素首次来源行、原始行顺序、固定种子二次抽样和输出坐标逐值相同。

## 时序、来源和显示

- 算法不读取未来帧。背景只由明确声明的连续起始前缀建立；前缀丢帧后不把其后任意帧重新宣称为空场。时钟重复/回退/断档或来源/标定改变后停用背景，须创建新的显式绑定会话。Tracker按原契约重置，规则历史按代次、目标和观测缺口隔离。
- 队列跳过源帧时显式调用既有特征的观测缺口机制；即使两次处理间隔小于0.3s，也不跨跳过帧累计低位时长或拟合下降。该新增策略与全帧无丢弃输入无差异；不能要求它与“省略缺帧通知”的旧规则旁路在丢帧输入上相等。
- source_rows只表示同帧真实来源行。跨帧关联复用射线/运动补偿空间支撑。保留所有当前组件行审计；不补点。预测/歧义不输出当前测量目标、绿框或测量特征。无绑定地面时高度UNKNOWN；PCA退化沿用axis_valid=false。低姿态出生保持未分类候选。
- 左侧点云/绿框、右侧相机近邻、下方高度曲线/状态色条/时间轴、报警条沿用现有形态。绘制抽样不参与算法，框和指标使用全部当前目标测量。相机只用于预览；超出0.20s显示预算或加载失败时隐藏，物理同步UNKNOWN。
- 服务和浏览器各最多缓存240帧。暂停或选中历史帧时保留该帧，缓存淘汰不把它覆盖成最新帧；恢复跟随才跳到最新。跳帧只渲染，算法继续按实际消费序列运行。跨目标、代次、回退/重复时钟和观测缺口断开曲线/报警区间。
- `replay.html`和`data/frames.js`保存最后最多240个发布帧，可离线复看；完整算法及显示账本另存，不为跳帧重算算法。386/780没有同源相机，不借用126帧样例或其他会话图片。

## 机器产物与计时范围

`CONFIG.json`绑定来源、地面/provenance、完整当前源码与参数、解释器/NumPy/线程环境。`frames.jsonl`为W2输出，`RULE_BASELINE.jsonl`为规则输出，`SOURCE_ROWS.jsonl`为当前组件/行归属核验，`display.jsonl`为完整显示输出。`ARRIVALS.jsonl`逐输入记录scheduled/arrival/enqueued/started/completed/published单调时钟及明确的processed/dropped处置；丢弃帧的处理/发布时钟为null。`CONSUMED.json`记录实际消费序列，并从初始状态单独重放核对。

completed表示逐帧运行时返回（含该帧必要的背景初始化）；published表示之后完成来源检查、显示准备和缓冲输出，结果进入本地发布缓存。二者不能混用。`skipped_input_frames_before_current`记录当前消费帧之前跳过的输入数，缺测通知不构成补造测量。

`timings.jsonl`保存逐帧原值；`SUMMARY.json`分别提供预热及非预热的n/P50/P95/P99/max（NumPy默认线性分位）。decode含原有子阶段；components内嵌source_lift；tracking内嵌features。`algorithm_ms`保留W1+W2范围，`event_chain_ms`增加推理摘要和既有规则几何/时序特征/状态，`loop_ms`增加当前读盘、来源审计、显示准备、JSON、缓冲写及本地发布缓存更新。阶段是嵌套范围，不能相加P95。背景初始化、RSS采样/计时账本记录、最终flush、启动/终检SHA及消费序列复核另列或在CLI墙钟中，不能冒充原G1/G2计时。

queue_age/replay_frame_age/replay_backlog均为本地离线回放的单调时钟量，不是设备端到端延迟。publish指结果进入本地有界缓存，不含浏览器网络/解码/绘制。真实设备端到端延迟、新链板端性能、人体/身份/真实跌倒/浴室效果均UNKNOWN；confirmed始终关闭。原G1a结果保留，G1b5.448%及f360语义UNRESOLVED不变；原G1c<10ms、G2<15ms须继续按原范围报告，PC20ms/板端30ms只是候选预算。

到达/排队/发布使用本地`perf_counter`单调高分辨率时钟，其实现/分辨率在CONFIG中记录。初始pilot的排队时钟使用`time.monotonic`（Windows粒度较粗），这些原值独立保留；正式三轮统一采用高分辨率时钟，阶段算法计时始终使用perf_counter。

本轮实测与失败日志统一在 `docs/evidence/2026-10-24_range_runtime/`，最终结果见其CHECKS和PERFORMANCE文件。

## 2026-10-24 实测结果

环境为本机AMD64、Python3.12.10/NumPy1.26.4、Balanced电源方案，线程环境变量保持继承值并逐运行记录。以下每格为三轮独立进程的P95（ms），不挑最快轮，不相加阶段P95。

| 范围 | 386帧 | 780帧 |
|---|---|---|
| 原CLI W1基线 | 14.095 / 15.051 / 12.565 | 14.310 / 12.614 / 13.574 |
| 原CLI W1+W2含特征基线 | 23.153 / 24.821 / 21.472 | 33.683 / 29.454 / 35.226 |
| 新运行时W1 | 12.206 / 12.121 / 11.597 | 11.011 / 10.793 / 11.318 |
| 新运行时W1+W2含特征 | 21.640 / 21.771 / 20.205 | 27.162 / 26.905 / 28.367 |
| 新运行时含规则事件层 | 24.741 / 24.236 / 23.041 | 28.682 / 28.992 / 30.754 |
| 新运行时含读取/来源核验/显示/JSON/IO/本地发布 | 79.712 / 75.412 / 79.426 | 77.071 / 77.551 / 81.500 |

W1/W2原算法源码保持；不同入口额外计时和负载差异不解释成人体效果或算法改进。原G1c<10ms、G2<15ms均FAIL，候选PC20ms也未通过；G1a原PASS、G1b5.448% FAIL和f360语义UNRESOLVED保留，板端预算UNKNOWN。

| 1×源节奏三轮 | 386帧 | 780帧 |
|---|---|---|
| 处理 / 丢弃 | 384/2、384/2、383/3 | 778/2、778/2、778/2 |
| 本地排队P95 ms | 0.153 / 0.155 / 0.168 | 0.161 / 0.166 / 0.169 |
| 本地发布帧龄P95 ms | 79.345 / 82.553 / 81.605 | 71.796 / 71.293 / 71.835 |
| 非预热工作集峰值MiB | 130.40 / 130.93 / 130.20 | 144.70 / 144.20 / 144.09 |

工作集数值为逐帧发布后的采样最大值，不是背景初始化内部瞬时内存峰值；原始逐帧值全部保留。

全部消费序列从初始状态单独重放，差异为0。各轮frame50/51在背景初始化期间被覆盖；首轮386的frame49背景初始化281.472ms、发布帧龄326.891ms。386第三轮另丢frame309：前一帧308输出IO162.179ms，使循环达到227.721ms，事件链本身18.923ms；底层IO阻塞成因UNKNOWN。不能用小排队P95或非预热帧龄掩盖这两个尾延迟来源。

全帧386/780三轮与原绑定W2/规则/来源归属账本的新增差异为0，纯推理摘要保持`c8ad205a…` / `3b165209…`，120前缀逐字段相同。源节奏386第三轮与全帧有2帧W2、11帧规则派生输出差异，来自实际跳过frame309及连续观测历史重开；它对自己的消费序列重放仍一致，不称改进。其余五轮在实际消费帧上的W2/规则与全帧相同。注入220ms处理落后的120帧运行处理76、丢弃44，全部记账且消费序列重放一致。

120帧单因素显示控制中，绘制准备P95由41.680降至14.988ms，全部显示点、框、指标和状态逐值相同；386/780整段优化前后的显示账本也完全相同。来源审计仍保留完整检查，profile定位其Python逐行类型校验为后续CPU热点。关闭内部细分计时的控制运行输出相同，单次时间差受负载影响，不冒充精确计时器成本。

最终核心762项（含52项range）、新增离线入口7项、页面JS17项通过；既有审计26和展示15项通过。Python均`-B -W error`。本地Python3.8.10/NumPy1.17.4实际运行52项range、7项入口及386/780完整CLI。测量/状态数值最大差8.88e-15（PCA轴允许符号等价）。780的f716、g0_t0094、组件44/57/60组合在两版NumPy下刚体RMS/平移范数差0.008672/0.134862m，两边均因`no_supported_fragment`拒绝；原W2的3.8完整CLI逐帧推理与新运行时3.8完全相同，证明是既有诊断漂移。完整数值一致性因此记FAIL，不能写成全字段兼容通过；目标行、特征、归属和规则状态通过。

HTTP端到端接收120/120帧。浏览器实际观察源帧48持续更新；暂停在60后缓存已到110，画面仍保持60，恢复跳至119，显示2884实测点、绿框和1.13m中位高度；同源相机缺失如实显示。页面标签保留，当前本地会话地址记录在`HTTP_URL.txt`，进程号在`HTTP_CHECK.json`。两个缓存均有240帧上限；有限会话内存观测不外推1h/24h。

初始基线可能与测试重叠，保留但排除，正式采用`serial_baseline_*`。初次Windows ctypes句柄类型、cProfile相对`__file__`和核验脚本编码名错误的日志均保留；修复后相关测试/入口通过。全工作树基线为含未跟踪非忽略文件的区间SHA快照，模板另有改前SHA，原W1/W2清单38项逐份保持。没有对会话运行地面RANSAC、站姿基线或模型拟合；完整回归中既有合成地面夹具单列，不冒充实测拟合。未改数据/junction、历史证据、ML、设备或Git。

## 2026-10-27 离线对比收敛到同一运行时

`pc_apps/range_fall/session_compare.py` 不再自带前景/跟踪/特征/状态装配，改为 `core.range_runtime.RangeRuntime` + `core.range_offline` 的显式离线输入：`QuantileBackground`（整段逐射线 p98、只认更近回波、`non_causal=True`、`runtimeEligible=False`）和 `fit_declared_plane`（`offline_only=True/runtime_eligible=False/physical_verified=False`）。

`RangeRuntime(background=...)` 必须同时满足：`non_causal=True`、有 `declaration`、绑定（session/坐标/grid）匹配，且不能与 `empty_prefix_frames` 同时给；否则拒绝。已声明的离线背景不因时间断档被重学（在线前缀背景仍然断档失效），来源/标定改变仍停用。前缀模式默认 config 不变，386 帧逐帧决策/规则与改前 0 差异；同一 `analysis.json` 经 ROS 消息替身服务 386/386 0 差异。整段对比仍是整段 p98 非因果输入，页面/SUMMARY 明确声明，不能安装到在线引擎。
