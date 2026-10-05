# PA-01 R1：intensity只读统计 + 缓慢滑倒兜底离线验收 / 2026-10-02

本次由用户手动派发OpenCode，Codex收到回传后独立复审，不自动启动或重试。工作目录D:/Code/ldiar，模型DeepSeek V4.1 Flash，记录实际provider/model/session。可新建PA-01会话。你是唯一生产写入者，写入期间Codex与只读审查不并行改源码/测试/文档。开工核对实际HEAD/工作树（参考49eb7581，可能有外部变化），webui/dist、src/CMakeLists.txt等用户差异保留，不归因、不回滚。只本单，不GL04/联网板端/部署/采集/commit/push/reset。

动机（背景只读，不引用为验收依据）：产品方案文档指出①反射率/强度是一级降噪特征但HF链intensity字段从未被使用②`slow_slide`是fall_state自认限制但`allow_confirmed`路径从未有测试。本单把这两件做成可逆小步：只做只读统计与离线测试，不改任何运行时行为。

读 `src/human_fall_detection/core/` 下 sensor_quality.py / node_runtime.py `_sensor_quality` / fall_state.py / tests/test_hf06_fall_state.py，和 docs/human_fall/RETURN_TEMPLATE.md，按ponytail最小实现。先集中诊断到 `evidence/2026-10-02_pa01_r1/00_diag.md`（两任务的落点、调用者、缺检查），再实现。

## 任务A intensity只读统计

现状：点云含intensity字段，core/全链不使用、不统计；`is_dense=False`存在x=y=z=0,intensity=954类无效点。本任务**只统计、不过滤、不改变任何现有行为**。

A1. 在sensor_quality.py新增纯函数（如`intensity_report(samples_or_summary)`）：输入有限样本或汇总统计，输出`{"available":bool,"count":N,"invalid_count":N,"min":float,"median":float,"max":float,"mean":float}`；不可用输入→`available:false`且数值字段为None（有限JSON，无NaN/inf）；非有限值计入invalid_count且不进统计；空样本→available:false。单位/量纲未知，字段是原始设备值，报告不得换算或断言物理含义。

A2. node_runtime.py `_sensor_quality`增加可选`frame_intensity_stats`字段：仅当scene帧记录确实携带每点intensity（`lengths.get("intensity")`为真）时计算；点云表示不含intensity时该块`available:false`。预算有限：4.9万点全量统计可用抽样（如固定步长），抽样须记录`sampled:N/total:M`，**统计口径在必填注释/文档里说清**。默认永远计算（无配置门控），因为只读统计不影响行为；若你发现计算成本在Python3.8下不可接受，改为默认关闭的`human_fall.yaml`配置项并在诊断里给出理由。

A3. 不新增过滤阈值、不改lidar_candidates/pipeline/tracking的任何判断路径；不申报"水雾/反射率"语义，本单数据只作后续定阈依据。

## 任务B 缓慢滑倒兜底离线验收用例

现状：`fall_state.py` LIMITATIONS含`slow_slide_may_not_reach_descent_threshold`；`_classify`中confirmed门要求`confirmed_enabled and baseline_ready and low_duration>=confirmed_min_low_duration_s`；现有测试只覆盖快倒路径。本任务**只新增测试，不改fall_state.py**。

B1. 在test_hf06_fall_state.py新增用例：用`_machine(mode_verified=True, allow_confirmed=True)`与现有`_feed`夹具，构造**低于`descending_min_rate_m_s`(0.35)速率**的质心缓慢下降（如2→4秒内从1.6m渐变到<0.7m，每步rate/drop均不触发descending门），随后保持低矮静止`>=confirmed_min_low_duration_s`(3s)。断言：全程不出现STATE_DESCENDING；缓慢下降期从STATE_UPRIGHT进入STATE_LOW（`low_posture_without_confirmed_descent`或同义）；且slow-slide已知限制语义保持诚实。

B2. 关键验收点：缓慢滑倒**缺descent_seen**，按当前`_classify`逻辑应停在STATE_LOW而**不能**到达STATE_SUSPECTED/CONFIRMED。你的测试必须忠实断言当前实现的真实行为：若B1序列最终到不了confirmed，就断言到STATE_LOW并在测试docstring/诊断里明确写出"slow_slide兜底在当前状态机中不可达，需后续契约级改动"——**不允许为让测试好看而修改生产状态机**，本单只把该不可达性固化为显式验收证据，消除"自认限制但无测试"的空白。

B3. 负例可选：同序列在默认门（双false）下行为不变（现为STATE_LOW上限）。

## 回归与回传

- `python3 -B -W error -m unittest discover -s src/human_fall_detection/tests -v` 全绿（Python3.8/NumPy1.17兼容；新代码不得用新语法/stdlib）。
- 现有HF01-09/GL01-03用例不允许退化；冻结配置（default.yaml/geometry.yaml）、driver、webui、原始数据、历史证据不改。
- 变更范围限：core/sensor_quality.py、core/node_runtime.py、tests/test_hf06_fall_state.py、（如有必要）config/human_fall.yaml新增只读统计配置项、evidence/2026-10-02_pa01_r1/、回传文件。新增配置项必须保持默认行为与现状一致。
- 正式回传唯一绝对路径 `D:/Code/ldiar/docs/human_fall/returns/PA-01.md`（新建），末尾追加OpenCode PA-01 R1，按RETURN_TEMPLATE逐条（A1/A2/A3、B1/B2）给证据：命令、退出码、源码SHA、scope、NOT_RUN项（设备/真实上板全部NOT_RUN）。不自判总体PASS；完成后停止写入。
