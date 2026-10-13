# 实际人工审阅任务（GT仍空）

用户2026-10-09明确回复“无”。本轮没有真实human sidecar，identity_gt/node_review均为空，336候选簇全部未审；骨架试验不得由Codex截图判断升级PERSON。

启动本地只读入口：`python -B -W error -X utf8 docs/human_capture/evidence/2026-10-09_hrskeleton_offline_r1/serve_review.py`，打开 http://127.0.0.1:8883/review.html 。仅127.0.0.1；本轮测试服务已停止。Ctrl+C结束。

优先最小任务是两个开发段各3个连续实际帧：114205 ordinal112/113/114（入口frame=0/1/2）、114254 ordinal125/126/127（frame=20/21/22）。需逐帧检查全部完整簇，不预设哪个是人。member ID为sid/branch/ordinal/ci，原row、global、完整成员/原28B/坐标SHA均在帧JSON。确认为人时填写实际reviewer、同一person_id/track_epoch和真实连续性；家具STATIC_OBJECT、混合MIXED、无法确认UNKNOWN，不裁人体子集。

再标每节点VISIBLE/INVISIBLE/UNCERTAIN；VISIBLE须框选或输入可见区域的原row，理由明确。头/手不清楚保留UNCERTAIN，确认真实头区域才用HEAD_CONFIRMED。至少一个真实可见躯干正例和缺失/拒绝对照；不用把100帧全标完才满足最小B门，剩余未审必须保留。

全部336待审成员、完整receipt及定位URL见gt_pending.json；全部120分支行（含20无簇）见frame_index.csv。三个投影完整显示成员，不暗中裁XY柱；红点原始无效XYZ不能作为区域支撑。

导出后在新获授权证据轮复制工具/重新核输入，运行bind_inputs.js validate <实际sidecar路径>。标签校验只核绑定，不能证明人工真的观察或标签正确。工具当前支持逐簇保存/sidecar导出和导入；真实人工输出未执行。不要在本轮已交付evidence内覆盖产物。
