# 外部跌倒检测项目借鉴对照（2026-10-23）

可以借鉴。当前收益最大的是**同步审计、采样质量记录、严格隔离的对照实验**；现有 W1、秒制几何和人员隔离已经覆盖不少参考思路，暂没有证据支持替换生产背景、聚类或事件算法。

本轮精读本地参考代码，与当前实现和执行计划逐项对照；GitHub 六个仓库的分支与 Git 对象另外在线核对。对应文件与远端提交逐份匹配，清单见 [SOURCE_MATCHES.json](evidence/2026-10-23_reference_adoption/SOURCE_MATCHES.json)。原 [SURVEY.md](../tmp_github_scan/SURVEY.md) 保留原样，本文件补充和纠正其中判断。搜索未找到同构项目不能证明路线新颖性，星数也不能证明工程成熟度或实际效果。

## 1. 借什么，放到哪里

| 来源 | 值得借鉴 | 本项目现状 | 采用判断 |
|---|---|---|---|
| fusion | 自动偏移、采用偏移、双路原始锚、残差来源、修改后审计失效 | 已有 offset/uncertainty、双路锚、困难负例、人员隔离协议；缺真实资料 | 优先补伴随记录的证据完整性，沿用现有协议与事件评测，不重建数据框架 |
| teguh | 原始点数、增删点数、重复率、确定性采样、人员分组和仅训练集归一化 | 已有来源行采样、按人互斥和实测几何 | 借审计字段；固定 N 只在未来模型适配器使用，不放到几何测量前 |
| lcfall | 独立空场工件、集中预处理参数、模块分离 | 旧链已有冻结体素，新 W1 已有逐射线中位/MAD及绑定 | 不另写背景体素原型；保留现有 W1，后续做 P0→W2 |
| mmfall | 正常 ADL 重建异常分与几何过程的组合实验 | 已有 geometry_gate/temporal_only 接口；无独立目标域训练/评测证据 | 未来有长时 ADL 再列挑战者，目前不加 HVRAE、不拟合 |
| DarkSZChao | 关联评分与处理/显示/存储分离 | 当前主线单目标、已有歧义拒绝和身份恢复 | 多人需求到来后借实验设计，不把其贪心矩阵当已验证多人解法 |
| RadmoX | 用简单规则衡量复杂状态机的增益 | 已有下降量、下降率、躺姿支持与秒制保持 | 复用已有规则做同输入对照，不移植其状态机 |

这张表是取舍，不表示已经实现同步审计工具、W2 或任何新模型。本轮只新增本说明及机器核对产物、更新状态和日志。

## 2. 参数和流程的实码纠偏

### teguh：保留地面高度，借采样审计，谨慎解释评测

参考：[提交 ca2c03a](https://github.com/teguh43ananda/Lidar-Based-Fall-Detection/tree/ca2c03a21aed50262826ad134400a1948d376d2f)。以下 cell 从 0 开始，行号是 cell 内代码行号。

- `3.Ground Correction & ROI Filtering Analysis/Trial_GC25ZT008.ipynb` cell 0/5：固定旋转 25°，逐帧以全部清洁点旋转后 Z 的 1% 分位估地面，`Z_level=Z_corr-p1`，之后 ROI，再去除低于 0.08 m 的点。这不是单位尺度归一化。地面在视野中时可保留离地高度；地面消失、点集随目标一起下移时可能抵消真实下降。整片点下移 0.6 m 的独立算例中，该表示保持相同，见机器核对 JSON。继续沿用 [fall_geometry.py](../ML/src/fall_geometry.py) 的合格绑定地面 `n·p+d`，不把逐帧地面重估插入事件测量。
- `5. Bootstrap Resampling/256.ipynb` cell 5/6：点多时从离质心最近的原始点开始 FPS；点少时保留原点并有放回补足。`n_original_points/n_added/n_removed/duplicate_ratio` 有参考价值，重复行不增加实测几何。FPS 未屏蔽已选索引，4 个相同点取 3 点会返回 `[0,0,0]`，而降采样分支重复率硬写 0。未来适配器应分别保存真实唯一来源数和重复权重，不能只记输出 N。
- `D.DBSCAN Dataset/Summary/dbscan_apply_config.json` 为 `eps=.2/min_samples=10/min_cluster_points=20`。调参取最大合法簇并奖励主簇占比，没有人体点级 GT，可能把家具合入主簇。我们的 [perception.yaml](../src/human_fall_detection/config/perception.yaml) 中 0.08 m 体素、0.25 m 水平聚类格与三维 DBSCAN eps 语义不同，不能逐数替换。
- `7.Training DGCNN GRU/Trial1.ipynb` cell 1/5/6/13/14 确有 12 名开发人员、5 名测试人员、按 subject 分组、仅训练集 fit scaler；但该 notebook 取 6 折生成器的第一折，HPO 跳过并恢复旧记录。最终测试入口只用 Controlled Room，不能概括为已完成两房间外部泛化验证。
- `4.DBSCAN/Tuning.ipynb` cell 2/7/9/11/12 把开发和两个测试房间的 manifest 纳入全局预处理选参，存在测试分布参与调参的隔离风险。20 帧、stride=2 的窗口继承整段动作标签，也不等于事件起始/接触真值。人员划分之外，还要冻结预处理选择和完整事件分母。

已有 [human_pointset.py](../ML/src/human_pointset.py) 和 [train_event_model.py](../ML/src/train_event_model.py) 覆盖来源采样与人员互斥，当前不需要复制 notebook 或新增训练链。

### lcfall：背景本来就是 NumPy，48 帧也不是跟踪器

参考：[背景累计](https://github.com/sht621/lcfall-ros2/blob/1045622acfc78a32cd364ff42957a5abe1abc768/src/lcfall_ros2/lcfall_ros2/capture_background.py#L184)。本段相对路径从 `src/lcfall_ros2/lcfall_ros2/` 起算。

- `capture_background.py:184–215` 每个点给体素计数，没有每帧去重。因此单帧 5 点就可满足 `min_hits=5`，不是在 5 帧出现。200 帧仅计 ROI 非空的成功消息。`utils/background_subtraction.py` 已是 NumPy 体素化与集合查询，没有需要移植的 GPU 背景内核。
- `utils/lidar_preprocessing.py:183–217` 在全部前景上随机抽 256 点，不足重复、空云填零；没有目标关联、稳定种子或来源行。几何分位数和高度应从已关联的真实点计算，不能先随机采样、重复再测量。
- `utils/ring_buffer.py` 和 `lidar_inference_node.py` 缓存消息数组，未按每帧时间、身份、标定和断档重置。48 是消息数量，不能直接保证 4.8 s，更不能解决 W2 的碎片归属。
- `utils/tensor_utils.py:37–38` 对全窗口统一减参考质心/缩放，部分全零空帧也被平移为非零点团；独立调用实际函数已复现。保留本项目 observed/mask 与缺测不积累事件证据的契约。
- ROI z 范围是旋转后传感器原点坐标，预处理没有地面拟合或安装平移；不能把 `[-.8,1]` 当离地高度门。

现有 [range_background.py](../src/human_fall_detection/core/range_background.py) 已按逐射线观测次数、中位/MAD、未知和失效处理；[range_components.py](../src/human_fall_detection/core/range_components.py) 保留标定栅格来源行。借模块组织即可，重做体素链会重复已有功能。

### fusion：借审计账本，保留本项目的人员与事件口径

参考：[同步实现](https://github.com/zahyravaldez/fusion-fall-detection-dataset/blob/55d35a1d6cdf5db44421a0cc38363554e57a5c06/fall_detection/dataset/synchronization.py)、[taxonomy](https://github.com/zahyravaldez/fusion-fall-detection-dataset/blob/55d35a1d6cdf5db44421a0cc38363554e57a5c06/configs/taxonomy.yaml)。

- `fall_detection/dataset/schema.py:82–105`、`sync_audit.py` 分别保存自动偏移、采用偏移、锚原始时间、残差和来源；`synchronization.py:200–240` 在参考流/锚/偏移改变后使旧审计失效。这是最值得补到现有伴随记录的部分。
- 该实现使用常数偏移；校正同一个锚后 residual 置零，不是独立测得全段同步误差。主机接收时间也不自动等于传感器采样时间。若要报告漂移，需要不同于拟合锚的前后独立检查点和误差来源。
- 当前 taxonomy 实为 **19 类（7 fall、12 ADL）**，不是 18；`lie_down` 没指定 `end_phase`，加载默认 `person_upright`，导出 settled 后姿态会因此错写直立，已用实际 `phase_for_time` 函数复现。动作、姿态、事件三者应分开记录。`fail_fall` 更不能按名字直接写负例。
- `splits.py:12–38` 默认按类别/run 分配，没有 subject 互斥。质量失败/未批准片段还会在导出跳过；不照搬为我们的评测准入，以免排除失败尝试或引入审批流程。
- README 说明仓库仅合成样例，另外支持包为单次真实假人例；不能当新增人体数据或目标域成绩。

[FALL_CAPTURE_PROTOCOL.md](FALL_CAPTURE_PROTOCOL.md) 已有困难负例、双路物理锚、offset/uncertainty、人员留出，旧调研中“缺协议”的说法过时。值得补充的伴随记录内容是：会话/视频 SHA、参考时钟与符号约定、自动建议和最终采用偏移、双路锚原始时间、不确定度如何获得、独立检查锚、修改后的失效状态。它们是后续工具设计输入，缺证据填 UNKNOWN，不给旧会话回填猜测值。

### mmfall、RadmoX、DarkSZChao：借对照思想，检查因果与身份

- [mmfall](https://github.com/radar-lab/mmfall/blob/da8fa193d5641cdc2eca7f36498d1fd6e382f621/src/mmfall.ipynb) cell 1 使用 10×64×4（含 Doppler）；不足点的统计补偿会改变实际坐标，不能用于我们的几何测量。其下降判定在中心前后各 10 帧内找约 0.6 m 下降和异常尖峰，10 Hz 时需要未来约 1 s；输入窗口还包含标记时间之后的点。顺序 80/20 划分有重叠帧，未按人隔离，`fpr` 实际是误报个数而无小时分母。正常 ADL 异常检测值得未来比较，“正例少就比监督更稳”当前没有 IFW 对照证据。
- [RadmoX](https://github.com/sean821111/RadmoX/blob/bb8383387b7d1022b5b6a80ec37a4594a2d552ea/PC3_ex3_pyqtgraph_xyz_playback_final.py#L536) 的 −0.4 是 posZ 差分（假定帧周期 .05 s），不是 Doppler；3 s 是报警后的维持/复位，并非低位持续确认。state1/2 中两个独立 if 还可能覆盖刚设的报警状态，多 tid 共享缓存可能跨人求速度。保留“简单规则作基线”的思想，复用 [fall_state.py](../src/human_fall_detection/core/fall_state.py) 和既有秒制几何做公平对照。
- [DarkSZChao](https://github.com/DarkSZChao/MMWave-radar-human-tracking-and-fall-detection/blob/ca348ced388deb92d6c0c18b20f472fca28ce2af/library/human_tracking.py#L34) 把多帧候选堆入评分矩阵，以 float16 分数反复取最大值、删除相邻簇和对应轨迹列，是贪心关联。它没有提供交叉身份正确性的证明，不能用矩阵名称推断为校准概率或最优匹配。多人时先保留歧义与漏配，不为借鉴而改当前单目标锁定。

## 3. 对现有开发顺序的影响

1. 继续 [执行计划](FALL_DETECTION_EXECUTION_PLAN_2026-10-23.md) 的 P0：f360 逐行归因、绑定/指标核对与受控计时，再做显式离线 W2。参考项目没有提供足以绕过这些问题的替代实现。
2. W2/未来模型适配器沿用完整真实点、来源行、秒制、同目标绑定和缺测 mask；若确需固定 N，再增加真实点数/重复/删点审计。当前不新增适配器。
3. 数据侧借 fusion 的同步审计内容，沿用已定义的困难负例和人员划分；真实事件与长时 ADL 缺失仍是资料问题，不能靠新 schema 或公开分数补齐。
4. 有独立事件/负例暴露后，用同输入、同人员划分、同事件匹配器比较既有规则、HMM/时序模式，再判断是否需要异常检测；不凭结构复杂或仓库星数选模型。

本轮未复制第三方生产代码、未改算法/配置/ML/原始数据/现场服务，也未训练或部署。六份参考共 210 个文件与远端提交一致；独立算例及最终 63 项相关测试（22 前端、7 绑定契约、34 状态机）通过，见 [CHECKS.json](evidence/2026-10-23_reference_adoption/CHECKS.json)。

验证期间检测到 5 个 W1 源码/测试文件有本会话之外的变化，写入来源 UNKNOWN，已保留且单列 SHA。首次沿用历史完整账本 SHA 的断言失败也已保留。最终重跑期间盘点的 378 个现有源码文本 SHA 稳定；386 帧与历史账本全部原有字段逐值相同，10 个新增 comparison 字段使完整账本 SHA 变为 `c7ad4134b09088505b5bfce229aabd31ac9745bdf95d065cd6b66ea92781d4b4`，不能再写“历史完整 SHA 相同”。新账本两次运行一致，本轮不认领这些源码变更，也不将其视为 P0/G1 完成。

回放共同字段一致只证明该软件对照；目标域人体/跌倒效果和新链板端性能仍 UNKNOWN，原 G1 尾部/延迟失败未被本轮改变。
