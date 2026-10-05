# GL-W01 本地离线配平工作台验收 v1

2026-10-05 用户明确要求本地 Web UI 对既有录制运行协议对照、三算法筛选并生成配平数据。Codex 为本单唯一 writer。本单是 P02 静态离线工作台集成，不冒充尚未实施的 AGL 时间控制器/在线接管。

| ID | 要求与可观察预期 | 反例与证据 | 当前结果 |
|---|---|---|---|
| W01 | 总控制台和回放页可进入离线配平；仅访问本地会话，无板端请求；会话/参数/区域变更清理旧结果 | 页面真实浏览器、JS 检查 | PASS（作者自验） |
| W02 | 用户确认先验仅用于区域显示与方向锚点；区域冻结为独立 source rows；无高度/残差裁剪，同域三估计器 | 数据域NPZ与哈希；重复区域/未知身份拒绝 | PASS（作者自验） |
| W03 | TLS covariance、centered SVD、861/seed20261001 raw RANSAC；全域/逐区域 RMS≤.03m、P95≤.05m、支持率≥.8、每区≥20；线状退化拒绝；3帧独立 holdout 不进fit | 合成真值/坏域/独立留帧检查 | PASS（作者自验） |
| W04 | 公开三种方法通过/拒绝原因与两两2°/.03m一致性；TLS/SVD同族，冲突不二票压RANSAC；仅三种都有效且一致才推荐 | 鲁棒冲突、TLS/SVD数值自检 | PASS（作者自验） |
| W05 | 每个通过离线几何门的方法产生新points.bin/meta.json/transform.json/ZIP；R=Rx(roll)Ry(pitch), t=[0,0,d]；帧/源行/非XYZ字节保持；无效源XYZ保留且计数；无覆盖原录制 | roundtrip/非XYZ逐字节/原SHA/下载检查 | PASS（作者自验） |
| W06 | schema/有限值/尺寸/源指纹/路径/输出ID严格验证；一任务写入、状态轮询、重载失效、失败无可下载半成品、结果目录不可复用；bound artifacts/hash/version | startup/reload/sameID-newcontent/newID/mutation/badinput/失败并发矩阵 | PASS（作者自验） |
| S01 | ponytail、写前诊断/包含untracked的baseline、相关回归、提交后停写；独审结果如实记录 | 本轮evidence/return/review | BLOCKED（指定独审服务；其他步骤已完成） |
| P01 | 输出display_only，physical/extrinsics/runtime flags=false；测量参考和数值tz独立；已曝光录制与holdout不宣称独立物理标定 | metadata/report/UI | PASS（作者自验） |
| D01 | 无设备/部署/采集/driver/network变更 | 范围核对 | NOT_RUN |

协议依据：P02_ACCEPTANCE.md、P02四ROI研究已公布原门、ADAPTIVE_GROUND_LEVELING_CONTRACT.md §1/3/5/7。新增静态profile包含明确退化门 λ2/λ3≥.01 和二维跨度≥.1m；不修改历史门/结果。拒绝覆盖旧数据，不输出旧geometry_calibration消息。自验PASS不等于独立验收/ACCEPTED。
