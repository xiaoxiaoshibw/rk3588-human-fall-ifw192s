# HUMAN-UNIFY-R1 独立复核 R1

日期：2026-10-10（Asia/Shanghai）。审查者：Codex。结论：**REWORK_REQUIRED，软件验收 FAIL；算法资格 BLOCKED；生产资格 BLOCKED。**

本轮只审核用户粘贴的交付记录及当前共享工作树，不修生产代码、不提交、不启动设备任务。实际读取技能：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。没有派生代理或执行新的 OpenCode 任务。

## 基线与复核范围

- 当前 HEAD：`777296d`，前一提交 `347a5bf`；本轮开始时 human_core 与原 unify evidence 无 Git 修改。工作树包含大量其他任务的修改和未跟踪文件，保留。
- 读取 HF/GL WORKFLOW、HC/HR README、回传模板、全部六个核心实现文件、相关生产消费者/算法、测试及旧审计报告。
- 新证据只写当前目录；旧证据不重跑覆盖。`status_before.txt` 保存完整含 untracked 状态，`all_files.txt` 保存 Git tracked/untracked 清单；`source_sha_before.json` 保存核心/回放目录直属文件及原 unify evidence SHA。**本轮未全盘哈希 captures/二进制/其他支线，不能据此声称全库 SHA 冻结。**
- 当前 HC README 未链接 HUMAN-UNIFY 工单/唯一版本验收表，原始任务书没有随粘贴材料提供；现有报告仅引用“任务书 §11”等文本。因此本轮审查 ID 是缺陷索引，**不冒充原工单验收 ID**，正式全表验收 BLOCKED。
- `probe.js` 是审核专用复现工具；无需写入或修改原始会话。

## 真实执行结果

| 检查 | 结果 | 证据 |
|---|---|---|
| 原六套测试 | PASS，73 assertions / 6 suites，exit 0 | tests.txt |
| 单独性能测试 | PASS，3会话×3模式阈值9/9，exit 0 | perf.txt |
| 19生产文件 SHA | PASS，19/19匹配原快照 | probe_results.json |
| 9会话×5模式 manifest 文件 SHA | PASS，45/45匹配 | probe_results.json |
| 原生产 B 等价声明 | FAIL，有直接反例 | probe.js / probe_results.json |
| 设备、物理、部署、采集 | NOT_RUN | 未授权且未执行 |

性能本次 dynamic U3 P95=33.06ms，最大=43.16ms；本次最高 heapUsed=122.7MB。这里只确认本轮输出阈值，不证明固定耗时复现、总进程内存上限或板端性能。Buffer/TypedArray 外部内存没有纳入 heapUsed 门。

## 缺陷与返工要求

### R01 [P1] BASE_B 实际改变生产 B 语义

位置：`pc_apps/human_core/engine.js:204,250,281-287`；对照 `pc_apps/human_replay/detect_overlay.js:145-228,250-280`。

原 B 不先调用 pipe.denoise，簇中心取坐标排序中位数，关联 gate=1.0m、位置直更新、miss>15淘汰、同帧 claimed 保证一对一、age>=3出框。新 B 增加 A 去噪、改均值中心，并使用 pipe.Tracker 的 gate=.75m、EMA=.35、lost>8关闭、3/5票窗且无同帧 claimed。因此不能称“等价重写”。

直接调用生产 B 暴露的 `_test.associate` 与核心实际采用的 pipe.Tracker：

- 第一帧x=0，第二帧x=.9：原B保持ID1；核心产生ID1/ID2。
- 同一帧x=0、x=.2两簇：原B得到[1,2]；核心得到[1,1]。

多目标共用ID是继承A跟踪器产生的真实回归。原报告“1.0m/TTL15/一对一等价”与代码不符。应复用原B实现或忠实适配，然后建立逐帧候选、坐标、ID、确认、丢失/跳帧对拍；若有意改变算法，应另命名实验模式，不冒充基线。

### R02 [P1] BASE_B 去噪后点索引与 intensity 错位

位置：`engine.js:261,269`。

`pp` 是 clean 数组的点序号，但 intensity 从原始 `fc.xyzi[pp*4+3]` 获取。任意前置点被denoise删除后，RF几何坐标与强度不再属于同一点，可能改变RF概率和分类。`point_indices` 也错误声称这些clean索引是原始帧索引。

复现：原点0含NaN、intensity=999，后30个有效点intensity=10，去噪后RF首个强度实际999，预期10。应从clean读取强度并保留raw索引映射；对每次过滤/保留的索引契约一起修复。

### R03 [P1] 已配平输入的背景被再次配平

位置：`engine.js:135-144,175-184`，`runner.js:56,69`。

建背景无条件应用配置或硬编码ref R/T；tick对meta.leveling或already_leveled输入直接通过。同一leveled输入会在两个坐标系中建背景和提取前景。

复现输入(2,0,1)，meta.leveling存在：tick点坐标保持(2,0,1)，背景坐标变为(2.236063,-.000141,1.375883)。应给背景入口和tick共同的坐标状态/变换契约，并验证已配平/raw/显式R/T路径。`FrameContext.leveling`目前未消费；CLI `--leveling`被解析但未使用也应修正。

### R04 [P2] 换会话只重置tracker，没有清报告

位置：`engine.js:118-129,196,506`。

begin_session未清report_rows。复现one会话处理1帧，再切two处理1帧：report.session_id='two'，rows同时含['one','two']。循环也累计旧行，污染每会话统计。tick亦未验证fc.session_id是否与引擎当前会话一致；旧会话回调可写入新tracker。

应明确会话级report与跨会话日志的区别；当前会话报告清空，拒绝/忽略过时代际输入。现有会话切换测试只检查track数，未覆盖输出隔离。

### R05 [P2] 跟踪配置没有传递到实际跟踪器

位置：`engine.js:54-60,124,287,428`；`runner.js:47`。

cfg的track_lost_max/track_gate_xy_m/ema_alpha/confirm参数被记录但实际tracker读pipe.PIPE全局常量。复现设置track_lost_max=30，9次未关联后track仍关闭（实际PIPE=8）。U6长寿命实验与BASE模式会记录不同配置，却执行同一跟踪规则。

应使用实例级有效配置，或对尚不支持的配置显式拒绝；不得只写入manifest。background/classifier/candidates等选项也需核查实际分派，不能由配置字段存在推断功能已交付。

### R06 [P2] 懒加载忽略short read，截断文件被补零

位置：`data_loader.js:123-130`。

fs.readSync返回读取字节数未检查；Buffer.alloc未读部分为0。元数据声明1点/28B但points.bin仅4B：iter_frames_lazy.next成功返回[0,0,0,0]，没有报错。损坏数据因此变成看似有效点云，eager/lazy契约不一致。

应统一完整元数据/文件尺寸/帧边界检查、精确读取与异常关闭文件句柄。对count_points使用`|0`也不能替代非负整数校验。

### R07 [P1] “家具帧=0”不是家具免疫证据

位置：`engine.js:488-495`、`runner.js:83-85`、原`FINAL_REPORT.md:95-100`。

代码把所有未被接受为人类的候选归入n_furn；所以该量是拒绝候选数，完全没有人工家具身份。一个家具若被RF误判为人，恰好不会进入furn计数。BASE_B的0不能证明无家具误报。

反例来自已有落盘：空场U3为person_frames=203、furniture_frames=0、最终confirmed tracks=12。原报告却写“空场203家具帧”，表中ff=0。原报告又把203135的46个拒绝候选帧称RF误报，方向颠倒。

应改名accepted/rejected candidate frames。可基于可靠空场语义报告空场假人输出；有人会话的家具误报必须有独立GT。不能把会话级任意候选统计用于真人漏检归因；缺坐标级GT时“动态真人主要死于CLASSIFIER”也只能是待验证假设。

## 其他未闭合项

- U2保留功能已作者承认未实现可用状态；append点未去重，所有Candidate仍标FG、raw point_indices为空，无法审核retained/merged来源，不能算完整候选契约交付。
- 跳帧测试`test_replay_contract.js:95,170,178`用了`length>=0`/`t(true)`；仅证明不崩溃，不能证明跳帧期间lost计数、时间确认或轨迹稳定。
- 原独审R2明确REWORK且未见修后第三次独审。FINAL自行宣布“PASS（条件性）”无从替代审计闭合。
- 当前`05_REGRESSION_REPORT.md:54`仍保留“REF envelope注入U3”，与04的禁止混用建议冲突；性能报告“16.9比9.8更快”、U3无3/5窗、memmap来源等描述也与代码不符。
- 原提交只保存19个生产SHA；不能据此推断用户全部dirty/untracked资产都未改。提交真实存在，但原始用户任务书未提供，无法核定当时commit/记忆写入是否有明确授权；本轮不做历史回退。

## 收口

保留本轮73测试PASS、性能9/9PASS、19源SHA/45结果SHA匹配这些有效记录。它们不能覆盖上述实现缺陷，也不证明与生产等价。修复R01–R07并补对应行为断言/独立对拍后，**生成新轮次证据**，对唯一验收表逐ID独审；不要覆盖旧runs或把自验总数当验收。

本轮不授权自动返工、提交、人工采集、模型切换、上板或部署。
