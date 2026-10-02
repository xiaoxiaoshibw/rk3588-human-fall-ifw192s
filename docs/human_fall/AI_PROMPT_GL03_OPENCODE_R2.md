# GL03 R2：源frame资格与真实数据诊断收口 / 2026-10-02

继续原会话/指定Flash；你仍唯一生产写入者。R1新增几何、optional兼容、选择缓存、预测参考框已由Codex独立8方法+300回归+GL02 12/2通过，不重做。只修以下已有G03/O01要求的缺口，不GL04/部署/联网/采集/commit/push/reset，不改旧证据/独立断言。

1. **G03上游资格未门控**：虽foreign frame的GDID空，新框unavailable，build_snapshot仍用innolidar平面给other_lidar点height_m、ground_relative_available=True/ground_valid=True；节点也valid+locked，且允许旧快照新选择。新框一层失效不足以关闭旧高度链。真实负例已加入R1独立脚本test_G03_foreign_frame_cannot_enable_legacy_height_or_live_measurements；正常源/恢复仍要通过。共享source-frame guard在高度/ground计算之前应用，节点process、required request gate、status_state都同意失效，不泄漏有效观测/新请求；保留原始seq/stamp/epoch和原始点云诊断，不以异常杀worker。无derived source-only也不能对不同frame应用plane；合法legacy行为保持。缓存同ID重放原义不改。
2. **O01方法错名/证据不足**：R1 60_o01_explore.py将median raw-Z±3MAD（厚1.474m、删除78.7%）叫suspected plane ablation。这不是倾斜地面平面支持消融，不能据它推断地面桥接不成立。保留原60/61/62，R2新增诊断，引用GL00 r1/14_current_planes.json中的未核验候选n/d作明确hypothesis，按abs(n·p+d)<=0.05等已记录阈值做成员/连接消融。比较每对必须同输入、采样、range/config和投影基底；注明pool行索引不是原帧索引、跨47帧；ROI仅2个截断帧。给组件成员数/最大组件/AABB/少量sample行ID或digest，不向会话倒全量CSV/数组。可引用生产候选连接实现以免独立复制错误，但不得提升地面trust/身份、物理flags或猜人体/机器人。无完整帧/可信真值继续BLOCKED；不为框缩小强加分离算法。
3. 上轮把回传写到了根returns/GL-03.md，Codex已纠正到**D:/Code/ldiar/docs/human_fall/returns/GL-03.md**，R2仅在这个绝对路径末尾追加。不能再造第二回传目录。准确分列G06条件未满足/真实分割BLOCKED，O01探索证据范围及D01 NOT_RUN。软件几何通过不代表现场大框已修复。

先读GL03_ACCEPTANCE v1、R1独立脚本和这张任务，当前frame链/诊断源码按需片段；不全量注入旧历史。集中诊断到evidence/2026-10-02_gl03_r2/00_diag.md，再最小修复。允许lidar_candidates、必要node_runtime/相关有效回归、R2诊断和canonical回传；保留前轮2生产文件行为及新回归，其他冻结资产原数据保持。

先9方法独立脚本→受影响GL03/fall完整回归→GL02 12+2；follow/UI如SHA不变引用本轮CodexR1对应证据。记录真实exit、完整当前/新增source SHA、数据SHA、实际模型/session，不自判PASS。日志全部仓库证据路径，不用env TEMP；每段read输出<=必要片段、测试只摘要/失败，接近120k停清楚检查点。完成SUBMITTED后停止写入。
