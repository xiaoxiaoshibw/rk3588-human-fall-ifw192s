# HR-W03 收口：只读审计与预注册假设（2026-10-07）

本轮唯一 writer：Codex；用户附件明确授权阶段 A–F，仅统计修复可以修改生产源码。未进入 registration R3.9 生产接入或 W04–W09。证据目录名字 r39_closeout 表示本次收口轮，不表示 R3.9 已授权。

已完整加载用户指定入口、R38 工单/回传/最终提交、R3 shadow JSON 和四个生产链源码。R38 JSON 包含完整 P/S 逐帧输出，读取时用 JSON.parse 解析全部内容，避免把 24MB 点云结构打印成不可读日志。唯一现行验收表仍是 `../2026-10-07_hrw03_r37_productionization/06_test_matrix.md` v1，不复制或放宽其门。当前授权优先于旧记录的停写要求，仅扩展至本轮指定审计/统计返工。

ponytail 实读：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（full）。复用现有 PL 函数和 Three.js r127/OrbitControls；纯 Node stdlib 诊断，无新依赖。原始会话、历史证据、leveling、registration 数学、所有 PIPE 参数只读。

## A1：31 点来源审计方法

沿用 R3.6 clean frames/centers 与 R38 r3 全高度 cohort。P 前景（cleanup 前）在 r≤0.6 人窗内，变换并 float32 舍入后不在 S 前景中的点，才计作旧 31 点。通过原 leveled 全帧四元组匹配保留 frame-local 原始 point index 和 session global index、ROS seq、时间戳；重合四元组保留全部来源，禁止默默假定唯一。

逐点重放 S denoise → workspace → reference matcher → registered-online matcher → cleanup。分别保存每个过滤的 membership 和反事实未注册 reference 查询、两种 online map 匹配。最近 voxel 形心距离为全图最近距离；生产 matcher 决策仅用原 3×3×3 邻域/0.12 严格球门，最近形心不一定是第一个删除命中。保存两个身份/距离，避免混淆。

H1：变换发生在 workspace 裁剪之前，低带点可能跨过 z=0.10 被裁剪，不能统称 reference 吞人。

H2：参考图近地体素可能匹配人体脚腿或地面残余；z<0.3 本身不提供 ground GT。所有未经人工语义确认的点标 UNKNOWN。

H3：registered online map 在新坐标网格重建，体素分箱/占用和形心可能变化。独立记录 reference/online 双命中，不以顺序掩盖。

## B：可标注证据

每个相关 clean frame 的全量局部 cloud（无抽稀）附 P/S foreground 与 cleanup 后状态、生产候选 cluster/track 归属。P 与 S 在同一个 source leveled 坐标展示，S 原注册坐标另存。被吸收点单独红色，保留候选绿色，其他背景灰色。点级标签默认为 UNKNOWN；人工导出的 `source:"human"` 派生 JSON 不写 captures 原件。补充 confirmation 变化局部 frame，给全部变化行可追溯。

## C：confirmation attribution

先严格复现 R38 的历史 green/purple/missed 行集合，再用原始 point index 交集建立跨分支 cluster 对应，而非用 track id 相等或单纯 0.75m 质心门充当身份。标签记录原字段：旧 green=track_confirmed；旧 purple=joint==CONFIRMED_HUMAN，后一名称并非 UI 紫色 HUMAN_CANDIDATE。保留旧命名便于对账，明确语义。

保存全部几何、分类理由、时间票、清理前后原始点集合；分裂/合并是 overlap graph 的候选拓扑事实，不自动等同真人身份。静态期望仅引用已登记 WD01 金标区域并核 reference 删除支撑；其余候选 gain/loss 不冒称 TP/FP/FN。关键身份、遮挡、混合点仍可 UNKNOWN。

## D：已定位测量 bug 与最小方案（未先改算法）

BUG-R39-M01：`pc_apps/human_replay/human_pipe_lib.js:pipeline_frame` 中 `clusters_after - clusters_before` 对对象数组相减，非空簇产生 NaN；`clusters_before_cleanup/after_cleanup` 又把数组作为数量输出。唯一生产显示调用者 `human_detect.js` 字符串拼接也受影响；R38 shadow 因 delta!==0 把非有限数计为异常。其症状不证明真的 split。

最小 reproduction：三相邻 XY cells 各两点，形成一个保留簇；before/after 数组均 length=1，delta 为 NaN。方案：delta 用 `.length` 相减，两个 count 字段返回 `.length`，聚类数组仍原样喂 feature/Tracker。属于本輪测量修复范围。先保存 reproduction 和 regression，后改三行；逐帧比较所有非诊断字段、fg/cleanup 和历史 digest 投影，证明行为不变。

注意 artifact code binding 含整个 PL 文件 SHA。三行修复会使旧 artifact 当前 loader STALE（METHOD_STALE/REFMAP_DRIFT），不能重写/放宽绑定。完整 shadow 用旧绑定代码/输入的只读归档 sandbox 验证载入，再用修复后的 PL 离线比较；报告当前 loader 的 SAFE 行为，不能把历史 DEGRADED 冒称当前可消费。

## E：gate 诊断方法

冻结 R/t、cf/rf fineStatic 0.06、reference normals 0.10、最后 sc.inlier=0.08、keep=0.60 和 50% gate。分母 source fine samples；分子是经过 normal support 和残差排序截断后的 keep 数，并非所有可匹配点。量化 raw coverage、invalid normal、trim 丢弃、缺 reference coverage、距离分布、XY/azimuth/FOV support，诊断不重拟合，不执行调参或换解。

动态污染/遮挡/FOV 的物理成因仅有可见表面支持时作候选解释，不能把单对会话相关性当确证。禁止自拟有效样本数/置信区间证明过门，禁止 gate 修改。

## F：重跑与判定

全 165 帧 + 同输入第二跑，背景/安全/拓扑/confirmation/registration 均保留。每次运行使用新文件名，stdout/stderr/exit 单独保存。基线覆盖含未跟踪文件；原证据和源数据 SHA 收尾复核。若 gate 未过或脚腿语义仍 UNKNOWN，最终保持 REWORK_REQUIRED；GT 子问题 BLOCKED，明确需标帧/点/簇/track 与重跑命令。设备/物理/部署/采集和 W04–W09 NOT_RUN。
