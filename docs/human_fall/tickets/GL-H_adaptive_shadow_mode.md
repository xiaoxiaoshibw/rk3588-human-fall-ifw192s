# GL-H：Real-Time Shadow Mode / 计划工单 v1

状态：WAIT_DEPENDENCY / WAIT_EXPLICIT_AUTHORIZATION / IMPLEMENTATION_NOT_RUN。本计划只列门，不启动设备连接/实时部署。前置F必需场景/独立验证与获审profile、G软件、目标硬件/OS/ROS/Python/NumPy及只读范围核验、用户后续具体授权。

来源：[最终计划§11–14](../ADAPTIVE_GROUND_LEVELING_FINAL_PLAN.md)、[接口契约§8](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)、[WORKFLOW](../WORKFLOW.md)。本文件唯一验收表v1。

## 目标与范围

新增独立shadow adapter/runner：订阅原raw点云，三任务共owned snapshot；只计算/新诊断输出，不替换主点云/标定/driver/正式配置/当前UI。比较current固定配平与adaptive，按实际设备测延迟、CPU、内存、队列/deadline、状态与false updates。

目标机不得由提示背景猜定；仓库当前ROS1/RK3588支持与用户其他硬件说明分开核。硬件/版本明确后冻结profile的frame_budget，null不能shadow/active。不得擅改网络、依赖、SDK或新增采集以完成测试。

## 唯一验收表 v1

| ID | 要求、触发/负例与预期 | 检查/证据入口 | 当前结果 |
|---|---|---|---|
| AGL-H-01 | 目标host/ROS/Python/NumPy/输入频率/time-domain与授权记录实际核验；只订阅，原主点云/配置/文件/driver字节保持 | authorized host inventory + before/after hashes | NOT_RUN |
| AGL-H-02 | 同FrameKey/domain三任务，最多1batch/1pending/3workers；结果乱序/慢算法不能混帧/晚提交；取消不谎称已停止running NumPy | injected timeouts/load/late-result trace | NOT_RUN |
| AGL-H-03 | serial/parallel与BLAS配置同输入公平对照；p50/p95/p99额外延迟、deadline misses、CPU/RSS/drop公开；批准预算满足候选P95≤min(50ms,实测period/2)、RSS≤128MiB或记录未满足不得PASS | target measurements/profile evidence | NOT_RUN |
| AGL-H-04 | 实时normal/遮挡/恢复/少点/断流行为与获审replay一致；资源不足→HOLD/GL_RESOURCE_LIMIT，过期不假fresh；实际GT/标签缺失分层 | authorized shadow logs/scenario results | NOT_RUN |
| AGL-H-05 | current vs adaptive同source对照；qualified/physical不自动开启，不能改旧latch/正式外参；停止shadow后原系统继续原样运行 | no-write/no-activation + stop/restart checks | NOT_RUN |
| AGL-H-S01 | 此单授权仅shadow，不授权GL-I/捕获/部署改主链；唯一writer、ponytail/diag/自验/停写/独审，设备证据真实 | authorization/scope/return | NOT_RUN |

## 交付与停止

目标机profile/性能数据、shadow运行ID、状态/fault日志、对照与影响范围、可停止手册；`evidence/<date>_agl_h_rN/`、`returns/GL-H.md`。有unknown/超预算/真实数据缺项仍BLOCKED，不自动进入I。
