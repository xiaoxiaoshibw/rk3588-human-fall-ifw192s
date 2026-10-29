# FRESH-MAP-01 增量新鲜度占用图：灰度背景 + 新鲜度渐黑（M0+M1 数字先行）

> 本文件按 `docs/human_fall/RETURN_TEMPLATE.md`（工作流程v2）惯例追加；本单为 sidequests 支线，
> 证据在 `docs/sidequests/evidence/2026-10-15_fresh_map_r1/`，验收表 `00_ACCEPTANCE_V1.md`（v1，唯一现行版本）。

## r1 / 2026-10-15

- 工单 / 轮次 / 执行者 / 时间：FRESH-MAP-01 / r1 / Claude Code（本单唯一写作者）/ 2026-10-15（Asia/Shanghai）。
- 验收表路径 / 版本 / SHA：`docs/sidequests/evidence/2026-10-15_fresh_map_r1/00_ACCEPTANCE_V1.md`（v1，
  SHA256 前16 `31e815c0f6b78e85`；总表 `10_TABLE.csv` `6912560b07b2a478`；选定参数 `10_SELECT.json` `b2515244b3180705`）。
- 用户授权与范围：用户 2026-10-15 口头开单（"聚类聚不到人→实时分析：长期不动背景灰度化、
  运动物体打新鲜度标签、随静止渐黑；先设计看看能不能成"），计划模式批准后选定 **M0+M1 数字先行**，
  M2 浏览器目视页暂缓。判据跑前写死于 README §判据 + 验收表 v1，跑后只填数不改门。
- 执行方式 / 环境：Windows 本机 Node v24.14.0；离线 `captures/remote` 15 段本地会话；
  无板端登录/部署/网络操作；未 commit/push/reset/checkout/clean。
- 起始 branch/HEAD：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`（工作树本就脏并含本单新增；
  结束时 `git status --porcelain` 40 条，全部为本单新增件与既有历史脏项）。
- 状态：**SUBMITTED / 未 ACCEPTED**；生产/板端/设备结论 NOT_RUN（本单不涉）。
- 验收摘要（详见验收表）：T01 PASS（单测 15/15）｜T02/T03 PASS（静立存活 0.979~1.000，≥95% 门）｜
  T04 PASS（复活 0~1 帧，first_fire 口径）｜T05 PASS（evconf3 组：干净空场 0 假发火）｜
  **T06 FAIL-边缘**（fresh_update 均值 2.45~8.01ms，30/44 ≤5ms；F3>15ms 未触发）｜
  T07 已记录（BASE_A 对照 0.41~0.77；97~98% 吞没口径 **NOT_RUN**——本地无长静立 S8，fetch 属另行授权）｜
  T08 NOT_OBSERVED（E4"全程静立被 warmup 吞"边界未在本地素材复现）｜T09 未停线（F2 现象在案：
  噪声空场 P0 组假簇 77% 过几何门，选定 evconf3 组降为 0）｜T10/T11 PASS。
  结论：方向可行，可晋级 M2 另单；遗留 = S8 复现、221808 噪声归属、S4 扁平化优化。
- 机理与实现决策（关键三条）：
  1. 事件判据最终形态：非 ref 格发过事件后只认位移门（新占用不再逐帧续亮）——"静止新物体
     亮一次→渐黑→永久 GHOST"是用户要的语义；走回头路旧格不重亮但以 GHOST 身份留在候选集，
     新位置照常发火。`move_tol(0.12) ≥ 单格半对角(≈0.118)`：单格内位移门几乎不可达，已如实
     登记为标定项而非缺陷。
  2. HOT 期冻结慢参考/occ EMA（防复刻在线硬背景"EMA 吃静立者"机理），单测以白盒断言数值冻结。
  3. GHOST 不设 TTL、无删除权：候选=HOT∪GHOST∪live 锚点半径；空轨迹无当帧点自然不膨胀
     （候选按当帧点过滤）。锚点语义逐项照搬 engine.js retention 常量，未改值。
- 实际变更（全部新增，零主线改动）：
  `sidequests/fresh_map/r01/`：`fresh_lib.js` `cf31a07b27c94e8a`、`fresh_lib.test.js` `95bea706ed3a672e`、
  `run_fresh.js` `7362f9c41047d0af`、`collect.js` `a4c1bc9facb47b31`、`run_grid.sh` `c2a2b39bfd6e2264`、
  `README.md` `83f9a78bab9a533f`（前16 位 SHA256）。
  `docs/sidequests/evidence/2026-10-15_fresh_map_r1/`：验收表 + `10_TABLE.csv` + `10_SELECT.json` +
  `grid/<sid>__<tag>/`×44（各含 per-frame CSV/JSON/survival_curve/manifest，manifest 冻结源码 5 件与
  输入 points/meta SHA）+ `11_run_grid.log`。本回传文件。
  只读消费：`human_pipe_lib.js`（build_reference_map/key_bg/voxelize/cluster/classify/常量）、
  `human_core/{data_loader,leveling}.js`、`engine.js` retention 常量（仅照搬语义）、`captures/remote/*`。
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.claude\skills\ponytail\SKILL.md`（本会话开头经
  Skill 工具加载，逐轮生效）。使用路径：先复用仓库既有件（pipe 参考图 builder/体素键/聚类/retention
  常量、data_loader、leveling REF_RT、runner 证据纪律），平台原生仅 Node stdlib，零新依赖；
  新写最小集 = 1 个纯函数 lib + 1 个单测 + 1 个 CLI + 1 个聚合 + 1 个网格脚本；
  过程按 ladder 两次删码（去 ghost_ttl 复杂度、去候选双循环残骸）。
- 数据契约核对：会话 28B/点 `[x,y,z,i,ring,ts]`（28B 实态，`docs/human_capture/README.md` §2 示例 16B
  为旧文档，沿 PLANE-01 登记口径不改）；dt 一律 `bag_time_sec` 真实秒；配平 REF_RT（同 runner 缺省）；
  跨日 ref 错配（221808↔10-13 报告 +69% 残余）由"永不硬删+ever_event"消化，只影响配色不影响留存。
- 下一步（未授权，仅记录）：板侧 S8 长静立复现口径；221808 假发火噪声归属审计。

## r2 / 2026-10-15（M2 浏览器目视，用户"能看看效果嘛"触发）

- 工单 / 轮次 / 执行者 / 时间：FRESH-MAP-01 / r2 / Claude Code / 2026-10-15（Asia/Shanghai）。
- 验收表：`docs/sidequests/evidence/2026-10-15_fresh_map_m2_r1/00_ACCEPTANCE_V1.md`（M2-v1，追加于 r1 表之后，
  r1 表不改动不覆盖）。
- 起始基线：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`；未 commit/push/deploy/capture。
- 交付（全新增，算法零漂移：fresh_lib.js SHA `cf31a07b27c94e8a` 与 r1 冻结一致）：
  `sidequests/fresh_map/r01/fresh_overlay.js 21ee140383e2364a`（挂 replay.js HUMAN_DETECT_OVERLAY 钩子
  契约的薄 UI 适配器：notify_session/reset/attach_color/set_leveled_in_s/on_frame + session_gen 代际守卫）、
  `fresh.html 6475ae7772dd943d`（结构复刻 index.html，脚本表换 fresh 件，加「空场参考」目录选择器 + FRESH 计数条）、
  `fresh_overlay.test.js ae5238b0abba49b3`（合成会话走真管线 3/3）、
  `docs/sidequests/evidence/2026-10-15_fresh_map_m2_r1/10_REALDATA_REPLAY.txt fcc6da368d404195`
  （真实会话 082623×221808 全帧重放打点：f1 fired=158→f145 HOT 峰值 701→f173 起 fired=0、GHOST 单调至 646、
  f260 微动位移门重触发 fired=7 回亮、锚点 8/8 live，与 M1 口径一致）。
- 判定：V01/V02/V03/V05/V06 PASS；**V04 目视 NOT_RUN**（待用户实看，操作说明在 10_REALDATA_REPLAY.txt 末尾）。
- 追加件（用户"帮我打开web/帮我选好啊"）：`serve_fresh.py`（stdlib ThreadingHTTPServer，127.0.0.1:8791，
  /api/file 白名单 sid 正则 + meta.json/points.bin 双名 + normpath 前缀校验，路径穿越实测 404；
  其它 /api 404 → replay 默认配平兜底）；fresh.html 自动载默认 空场=221808+主会话=082623 即开即播，
  工具条加「会话」下拉切会话免对话框；`?sid=/?ref=` 可覆盖。
- 已知口径差：file:// 打开时 replay 的 /api/leveling fetch 失败 → 3D 渲染保持原始传感系（视觉略歪），
  但 overlay 逻辑坐标自乘 REF_RT，新鲜度行为与数字不受影响；经 8901/自带服务加载时渲染亦配平。
- ponytail 使用路径：本轮 = 复用 replay.js 钩子与 human_replay_lib 现成着色面（只写 colorBuf，不新建
  three.js 场景），新增仅 1 适配器 + 1 页 + 1 测试；调试中删掉 1 个不可达防御分支；未加依赖未改主线。
- 状态：**SUBMITTED**；目视 V04 由用户实看后回填。

## r3 / 2026-10-15（目视缺陷根因修复：move_tol 与 ref 支撑卡体素对角边界）

- 工单 / 轮次 / 执行者 / 时间：FRESH-MAP-01 / r3 / Claude Code / 2026-10-15（Asia/Shanghai）。
- 触发：用户目视反馈"除了人，前面和旁边还这么亮"+"背景没变黑"。
- 验收表：无新表；修复记录与回归数字 = `docs/sidequests/evidence/2026-10-15_fresh_map_r3/00_FIXNOTE_V1.md`
  （grid/ 四跑含 manifest SHA）。r1/r2 冻结件一字未动。
- 根因与修复（两条，详见 FIXNOTE）：位移门 0.12 → 0.15（>点距格内质心最大 0.122，杜绝稀疏家具
  格内跳变永久 HOT）；ref 支撑加同格成员判定（跨天配准误差 ≤半格不再误判家具为 GHOST）。
  另 r2 配色：背景 0.30 灰→0.055 近黑（用户"灰度化"视觉预期）。
- 回归：082623 全量 surv 0.9932→1.0（站立段 fired 347→342 保留真运动）；111738 空场 12.5→9.4/min；
  E3 复活 1 帧不变；单测 15/15+3/3。M1 冻结选组 evconf3 未重跑（残余发火只降不升，方向安全）。
- 变更文件：`fresh_lib.js`（两行语义+注释）、`fresh_overlay.js`/`fresh.html`/`fresh_overlay.test.js`
  （配色与断言）。ponytail 路径：根因在共享常量处一次修，不逐调用点打补丁；未新增文件/依赖。
- 状态：**SUBMITTED**；V04 目视回填待用户刷新复看（等 ≥15s 首波褪尽，家具应沉底）。

## r4 / 2026-10-15（目视二批评 → 证据/对象两层：人形认领门进渲染）

- 工单 / 轮次 / 执行者 / 时间：FRESH-MAP-01 / r4 / Claude Code / 2026-10-15（Asia/Shanghai）。
- 触发：用户第二张截图（t=22.7s 人静止、HUD 锚点 4/5、桌面前缘整片亮白）+"近距离点本来就多、
  震动明显请不要把他们当成人、借你的视觉自己评判"。
- 自我评判（如实）：r2/r3 渲染把"体素发火"与"对象"画成同一亮度，传感器振动毛刺冒充人，
  违背本支线"几何分不清人 vs 家具"的自持原则；且演示页漏挂 M1 冻结选组（conf=2 非 3）。均判为缺陷。
- 修复（全部现成件，零新数学）：锚点入口加 `classify_human` 几何门（身高/宽高/半径/直立度四门，
  pipe 现成）——只有过门簇进 FreshMemory；渲染两层：亮白/亮青蓝=live 人形锚点半径内（对象），
  淡青=未认领 HOT（证据，随 f 沉暗），暗蓝=未认领 GHOST，近黑=背景；演示页挂 ev_confirm=3。
- 验收：`fresh_overlay.test.js` **5/5**（新增"evconf3 时序：刚发火不亮白"与"矮趴桌角簇永不亮白/
  永不进锚点"）；真实会话 082623 全帧重放：站立段锚点 1/1（桌角全灭）、认领数 4-5→0-1，
  记录 `docs/sidequests/evidence/2026-10-15_fresh_map_r4/10_REALDATA_CLAIM.txt`。
- 遗留（登记不粉饰）：① 卧倒者不过站姿人形门 → 渐黑后无亮色（低姿认领属 fall 状态机语义，另单）；
  ② f260 一例振动柱簇误认领（发生率 ~1/会话；收紧门留标定单）；③ 近距淡青证据雾是传感器真响，
  设计行为。fresh_lib 本轮零改动（SHA 不变 cf31a07b→r3 版），改仅 overlay/test/html/README。
- 变更文件：`fresh_overlay.js`（SEL+claims 门+_paint 两层）、`fresh_overlay.test.js`（5 用例）、
  `fresh.html`（图例）、`README.md`（M2 节重写）。ponytail 路径：判定权收回到现成几何门一处，
  不新写家具判别器；删码 1 函数（F_mem_live）。
- 状态：**SUBMITTED**；目视 V04 待用户刷新复看回填。

## 2026-10-16 浏览器效果只读复核

用户要求测试8791当前效果。新证据：docs/sidequests/evidence/2026-10-16_fresh_map_visual_review_r1/REPORT.md及f0/f60/f200/f240截图。站立人物高亮实际生效；f200零锚点、低姿目标近乎不可见；f240中央低团块重亮，但其振动归因UNKNOWN。M2-v1本次V01/V02 PASS（6/6、16/16），V03–V06 NOT_RUN（V04仅四帧抽查未完成整项）；设备/物理NOT_RUN。未修改源码/数据或既有证据，无提交部署采集。浏览器技能与方法、起始HEAD、初次cwd测试失败均见报告。

## r5 / 2026-10-16（Codex：已认领人物的低姿身份保持）

- 授权：用户在视觉复核及“先补已认领人物躺下后的身份保持”建议后要求继续。Codex单writer，仅本机演示支线；状态SUBMITTED，非ACCEPTED。
- 唯一验收v1：docs/sidequests/evidence/2026-10-16_fresh_map_low_pose_r1/ACCEPTANCE_V1.md；完整回传/根因/限制：同目录REPORT.md。
- 起始master/c9c4ee421cb0c8a3e4590b8f5730828b093c759a，dirty保留。四文件前态副本及diff/SHA齐全；全Git可见路径扫描跨越编辑，非原子前态，不宣称整树冻结。
- 实际技能：C:/Users/30680/.codex/skills/ponytail/SKILL.md。复用现有聚类/几何门/FreshMemory/颜色缓冲，只改sidequests/fresh_map/r01的overlay/test/html/README；依赖/原数据不改。
- 根因：站姿门丢失低姿，旧锚点20帧后不显示/30帧后删除。低姿只续接2秒/20帧内0.4m唯一已确认身份；须当前非参考活动证据充分，且相对先前站姿重心与高度都下降≥0.25m。低姿不得新建身份，不扩大背景染色圆盘。
- 自验LP01–LP07 PASS（具体子项与限制见报告），LP08设备/物理/真实跌倒语义/泛化NOT_RUN。合成8/8+核心16/16，三会话753帧前后输入SHA相同。082623 f109–237认领染色20/129→129/129，f200锚点0→1、认领点0→1419；f60计数保持。浏览器f60/f200实际截图齐全。
- 首轮低姿方案使111738空场亮起162→182帧，失败结果保留；加入真实下降条件后，两空场逐帧锚点摘要与颜色分类计数均与旧版相同。111738旧版已严重误认领162/186帧（最多7锚点），本轮未修复；221808保持0/272。不能宣称误认领问题已解决。
- 原8791服务失去监听后，用既有serve_fresh.py隐藏启动恢复（PID30216），最终页面停在f200。无其他服务停止、数据写/清理、Git提交推送、训练、采集或设备部署。独立复审NOT_RUN；后续应查参考匹配与旧站姿假锚点。
