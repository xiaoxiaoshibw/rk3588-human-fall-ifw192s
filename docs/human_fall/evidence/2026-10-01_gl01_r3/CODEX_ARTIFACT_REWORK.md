# GL-01 产物加载器独立复审 REWORK / 2026-10-01

同session ses_f091fc094ffejMiiPuJRmuRoFU；已压缩恢复，后续保持短输出。R3独立codex_boundaries.py 6/6通过，但新增codex_artifact_checks.py 6方法10失败（41_*），仍不放行GL-02。

仅完善validate_constrained_ground及必要CLI无效产物诊断/相关测试。完整保持旧validator行为、原失败脚本不改弱；新证据R4，回传追加原轮次。

必须拒绝声明valid的以下损坏：fit_frame_group缺失/与任一validation group相同；RMS/p95负值/布尔/非数值；support_fraction不在[0,1]；n与声明up_axis夹角超过settings门槛；d在height interval之外；fit_support_indices不是严格整数/布尔/越界/重复；input_point_count缺失非法，索引>=count；iterations为0或不足协议预算/越过cap。上轴存储须单位（不能加载时静默normalize掩盖损坏）；区域索引也需上限/累计holdout cap校验。禁止只检查一个统计上限或信任passed:true。

合法invalid/orientation_unverified诊断记录可保存，不能因competition_truncated而擦掉失败原因/证据；对“valid”才执行必须成功的物理几何/独立性门槛，非valid仍严格校验存在的字段类型/范围，但不要求通过。

常规生成器原样证据不反复重跑覆写：本轮只必要回归/独立加载器反例与有效/失败CLI记录，核对两端新ground.py SHA并跑板端隔离回归。记录新的源文件哈希、所有退出码与本轮回传。已有231/236及API/打包失败保留；禁止新采集/部署/GL02。真实物理仍BLOCKED，窗口1.1m/机器人1.4m测量定义已提供，不重复说缺参考物定义。
