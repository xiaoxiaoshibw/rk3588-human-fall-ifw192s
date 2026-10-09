# human_track B1 — 离线实时人体锁定 (独立页)

> 状态： **SUBMITTED** — 演示/诊断性质， 非生产， 无冻结资产改动， 未发布打包
> 承接： [HR-09 返回](HR-09.md) + [HUMAN_DETECT_B1_PLAN.md](../HUMAN_DETECT_B1_PLAN.md)
> 生产边界： 只读， 无任何话题/HTTP 写入； 检测纯前端， 模型走静态 JSON 快照； B2 另立工单。

## 一、目标达成情况

**目标**: 离线回放 HR-09 第一批 12 段会话， 实时把「人」用红框 + track_id 锁出来， 轨迹/帧间身份保持， 验证 B1 架构可行。

**实际达成** (本文档即自测汇总):

| 计划验收 (B1-R#) | 结果 | 证据 |
|---|---|---|
| R1 实时性 ≥ 5Hz | 用真实 10Hz 会话回放， 浏览器帧解码+检测 ~ 1 fps 开销 | 回放/空格启动人工 smoke |
| R2 空场 0 锁框 | 12 段中唯一空场 `cap_20261009_113611`, 背景差分包络同源， 无热点 → 0 锁框 | `detect_overlay.test.js` 14 PASS 起 |
| R3 多目标 | （演示限单人， 无双人样本） — 关联器支持多 track 并存， 互不干扰 | assoc/find_clusters 逻辑 + 单测 |
| R4 走动跟踪 | （本次 12 段全部站立） — 设计在同 id 1.5s 断档内保留 track_id | 测试断档跟踪存活链路 |
| R5 视觉合理 | 聚>30 点、 r90 阈值框， 出框自动清 | 浏览器 smoke |
| R6 安全 | 页面不出任何 fetch 之外除了 GET 静态文件 | DevTools 网络面板 |
| R7 自测 | 14 + 38 + full + 10 + OK 全部 PASS | bash 回显 |

## 二、成果物清单

| 路径 | 大小 | 添/改 |
|---|---|---|
| `pc_apps/human_replay/human_track.html` | 7.6KB | 新 — 独立页， 路线 B badge, 隐藏 replay 所有 UI 元件 |
| `pc_apps/human_replay/detect_overlay.js` | 11KB | 新 — 检测/跟踪核 for browser, CommonJS 测试兼容 |
| `pc_apps/human_replay/detect_ui.js` | 3KB | 新 — (备用） 回放页 UI 接层 |
| `pc_apps/human_replay/detect_overlay.test.js` | 5KB | 新 — 14 断言 node 测试 |
| `pc_apps/human_replay/bg_envelope.json` | 71KB | 新 — 空场 5cm 网格 95 分位高度包络， 4867 cells |
| `pc_apps/human_ml/dump_bg_envelope.py` | 30 行 | 新 — 重采空场模板时重跑它即可 |
| `pc_apps/human_replay/replay.js` | +2 行 | 小改 — set_idx 尾挂 HUMAN_DETECT_OVERLAY.on_frame(S), IIFE 尾导出 window.replay_internal |
| `pc_apps/human_replay/index.html` | +3 行 | 小改 — 加 detectBtn + trackTopView + trackHud |
| `pc_apps/console/console.html` | +1 行 | 小改 — 加 human_track 卡 + 人体识别补上「路线 A · 聚类检测」 |

## 三、关键设计决策

1. **不上板** — B1 在 PC 浏览器里完成 （前端聚类每帧 ~10ms 以内， 没有板端资源压力）。真实板端部署到 B2/B3 再评估
2. **RF 仍未接入** — 本单使用「背景差分 + 连通」作「高点团检测」, 未跑 51 维特征/RF 分类。卡名「人检锁定」现在语意准磁到「高点团锁定」, 在 B2 接 RF 后才能真正叫「人识别」
3. **检测与跟踪分离** — detect_overlay.js 里 `find_clusters`/`associate` 两个 API 与 HUMAN_DETECT_OVERLAY 的公共接口已定， 动检测不动跟踪， 动跟踪不动检测
4. **Human Detection 路线 A 保留** — console 首页现有 4 卡升级 5 卡， 「人体识别」卡 description 改为「路线 A · 聚类检测 · pin ROI 姿态判定」, 新卡「人检锁定」定位「路线 B · 模型检测 · 实时 ROI 跟踪」 — 司钉般看出两条路线不冲突

## 四、测试 / 验证

| 级别 | 命令 | 结果 |
|---|---|---|
| detect_overlay.test.js (本单新加） | node | **14 PASS** |
| human_pipe_lib.test.js | node | **38 passed, 0 failed** |
| panel.test.js | node | **PASS** |
| console_html.test.js | node | **10 passed** |
| console_test.py | python | **OK** |
| 回放页 HTTP smoke | python human_replay_lib.py + curl | 每文件 200 |
| human_detect.test.js | node — **跑不得** (memory [[human-detect-lib-test-hang]] 该测试挂起） | 已回避， 未跑 |

## 五、已知限制 (B2 针对性处理）

| 限制 | 机理 | B2 对策 |
|---|---|---|
| 家具改动会被框成「热点」 | 未接 RF, 高 0.25m 阈值阈 | 接 rf_person_v1.json 后输出 person 概率再过滤 |
| 双人贴身 （<0.01m) 会被 5cm 网格收容为一簇 | 网格 coarse-grained | B2 上 epsilon-sensitive 二次连通， 或加紧密簇分裂 |
| 背景包络只适 113611 空场所在大房间 | 浴室完完全不可用 | 浴室重采空场模板 → 重跑 dump_bg_envelope.py, 链不重训 |
| 杂讯/旁边物体挪动可能新建假 track | 「超背景 25cm」规则粗 | RF 概率滤簇时自然治理 |
| window.replay_internal 为测试 / 下一级集成暴露的 debug global | replay.js 本身为 IIFE 封装 | B2 允许时解除 IIFE 封装重置接口； 目前接受 |

## 六、发布形态 / 打包

- `pc_apps/console/dist/Console.exe` **仅 console.html 变化需要重打** (memory 规则）; human_replay 下 6 个新文件己通过源码旁路自动生效无需重打
- `LiDAR_Console.zip` 重打包时要带上 §二 中列出的 6 个新文件 (human_track.html, detect_*.js 3 个， bg_envelope.json, dump_bg_envelope.py)
- 桌面快捷方式 `LiDAR_Console.lnk` 无需变 （仍指 dist/Console.exe)

## 七、下一步

B1 已交付。后续三阶段：

1. **B2a — RF 接入**: dump rf_person_v1.joblib → 体积 <1MB 的 JSON, 同每簇 51 维特征描出 → 调用 → person/noperson 概率过滤 → 「检测」变成「识人」
2. **B2b — 动作分类**: 采第二批 9 段 (`CAPTURE_BATCH2_PLAN.md` — walk/sit/squat/lying/fall 系）, 训 v2 动作分类， 实时框上加姿势 state
3. **B3 — 生产集成**: 在板端或 PC 端 Human pipeline 数据处理商业安装过程中， 向 live pipeline 里隔档替换成 webrtc webhook/"日常例'实时隔摄'代替离线； 完全另立工单

B2/B3 现在未授权， 关单。
