# CL2-09C 等价优化与范围

Codex 唯一 writer；已读取 ponytail C:/Users/30680/.codex/skills/ponytail/SKILL.md。修改只在本目录的隔离 candidate/floor_sheet.py。新 variant cl209c_exact_roi_search_v1，基线为 CL2-09B 的完整 candidate；baseline/floor_sheet.py 与其逐 SHA 相同。其他 runtime 文件保持 09B 的字节，生产路径不接入。

## 根因、入口和实现

入口为 floor_sheet._roi_metrics；其唯一运行时调用者 detect_floor_regions_v2 再被 floor_roi.detect_floor_regions_v3 消费。原成功路径、旧选择、describe、条件数 SVD 的输入与输出、v1/v2/v3 路由均保留原代码。只有原失败后的完整四区搜索实现改变，15cm selector 和身份、purity、TLS 未改。

09B 在每个四元组重新取点、计算叉积和六个 hypot。基准近共线输入中多数四元组可证明共线，但仍经过 NumPy 小数组创建和 reduction。排序和单个 SVD 自身不是主要瓶颈。第一版只有距离表和间距剪枝，41 项回归通过但提升有限；其源码 candidate_r1_floor_sheet.py 与剖析/测试原日志保存。最终版进一步复用首对的共线关系。

1. 每个候选对仅计算一次与原代码相同的整数差及 float(np.hypot(...))，保留原浮点舍入，O(n²) 内存。
2. 按 a<b<c<d 嵌套索引，顺序与 itertools.combinations 完全相同。部分组合的最小间距是完整四区最小间距的上界；若部分已经小于原间距门或不优于 winner_sep，所有后续扩展不可能获胜。
3. 首对 (a,b) 固定时复用原整数叉积，原共线 iff c 与 d 都在其直线上。c 在直线上时，只迭代按索引升序的非共线 d；否则完整遍历剩余 d。不改变共线判定或增加误差 epsilon。
4. 每个保留的完整四元组仍调用原 describe，原独立计数、条件数 SVD 和门控完全不变。没有 batch SVD 或以协方差近似替代 SVD，避免阈值附近的数值漂移。SVD 调用数不声称减少。

winner_sep 仅在完整 describe 通过后更新；严格 > 才取代赢家，稳定并列仍为原排序中最早项。已无解时返回原 previous 完整字典。没有搜索 cap、超时中断、候选截断或未搜索即无解的规则。最坏复杂度仍 O(n⁴)，仅减少重复工作和可证明无效的分支，不宣称所有 100 候选都满足某个绝对时限。

## 证据边界

41 项 = 冻结 35 项 + 6 项新差分检查。差分以 09B 完整枚举实现为 oracle，用 assertEqual 比较完整 dict，而不是仅成功标志/近似数值。覆盖小集、大集、非共线无解、共线、重复、阈值相邻、对称并列、平移、反序及 caller ownership。运行命令含 -B -W error；最终源码 SHA 绑定 05_regression_03_command.json。Python3.8 语法检查通过；板端 Python3.8/NumPy1.17 实际运行 NOT_RUN。

首轮唯一失败为沙箱 WinError10013 阻止既有 127.0.0.1 HTTP 测试；后续使用同断言和本机临时服务，测试禁止板端调用。05_regression 原错误与 02/03 成功均保留。CLI 首次版本查询的 Git Bash 进程启动失败也保留，实际成功版本/帮助/模型为 *_02 日志。

03_profile_03.json 对 60 候选有解与非共线无解做分项插桩：迭代 next、hypot、min、np.all、SVD、排序。min 是包含 generator/hypot 的 inclusive 时间；np.all 同时包含旧共线与独立性检查，不能冒称纯间距检查。循环体和标量门控剩余耗时未独立计时，插桩含计数开销，不把各项时间相加，也不当真实基准。

04_benchmark.json 才是无插桩真实性能：25/60/100，同输入同进程、基线/候选交替顺序各三次，逐轮完整 dict 相同，保留全部原始样本并以中位数比较。首样本只是该输入的首次函数调用，不是冷 OS 或冷 BLAS 进程。benchmark.py 的剖析分支在正式基准进程已加载脚本后补充了 min 分项；正式基准分支、输入、运行中候选源码没有改动。该事实保留，最终源码 SHA 绑定 JSON 与 command。

121647 从原 bin 和冻结拟合平面重新构造 11 个 clean cells，原/09B/09C 选择与四 ROI 相同。最终候选用该 clean-key 结果再绑定 SHA。ordinal72/ROI2 P95=0.05029186936019117m，50mm 门控仍 FAIL，有效 TLS BLOCKED；没有重新求解 TLS、替代真实数据导出或物理原因推断。

本地性能优化完成不等于生产时延验收或 CL2-10 许可。生产接入 BLOCKED；设备、物理、B2/B3、采集 NOT_RUN。此次独审仅 09B→09C 差异及证据，不重复 CL2-07～09A。
