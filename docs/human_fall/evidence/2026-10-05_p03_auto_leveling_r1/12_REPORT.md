# P03 R1 回放自动配平 · 作者自验报告（SUBMITTED）

2026-10-05。范围 `pc_apps/human_replay/{leveling.py,leveling.js,LEVELING_README.md,leveling.html,replay.js,leveling_test.py}` + 新建 `leveling_lib.py / leveling_auto_test.py` + 证据目录 + P03* 三件套 + tickets/INDEX 一行。ponytail skill 实际读取路径：`C:\Users\30680\.claude\skills\ponytail\SKILL.md`。Console exe 不重打包；GL-A~I 未启动；GL-W01 手动 UI/语义不变。

## 设计与 00_diag 落地

- `leveling_lib.detect_ground_domain(points, nominal_pitch_deg, nominal_roll_deg, anchor)`：RANSAC 861/seed20261001/0.08 找主面（复用 `leveling_estimators.ransac`），n_z≥.85 / d∈[.8,1.8] / support≥.3 门；主面内点投 display 系，1m XY 网格贪心取点数 top-4 互不重叠格 → 4 个 ROI。
- `leveling.py` 只在两处增分支：
  1. `validate_request` 接受精简 auto 请求 `{pitch_deg, roll_deg, physical_height_m, mode:"auto"}`（`regions`/`ground_confirmed`/`basis` 不再前端必填）；旧 6 字段路径语义字节级保持。
  2. `run_job` 在 freeze_domain 前 `{**config, regions: detect(...).regions, auto_candidate, ground_confirmed: True, basis: "auto: ..."}` 喂给同一冻结/留帧/一致性门，不复制 GLW01 任何一段管线。
  3. `handle` 新增 `GET /api/leveling/leveled_latest?sid=` 返回最近 ready job 的 TLS transform.json；走 mtime 排序，同名 sid 才认。
- `leveling.html/leveling.js` 加一个 id=runAuto 按钮，不占用 confirmed/basis 启用条件；payload 是精简 auto 模式；结果共用 showReport 同张 consensus/方法表展示。
- `replay.js` 在 `__load_session_sid` 配平注入点（行 199 与 build_geometry 之间）调用 leveled_latest 并在 `S.buf_f32` 一次性应用 R/t —— build_geometry/compute_range/paint_colours/snap_nearest/pick_point/bbox 全链生效；失败静默回落原样渲染（不阻塞回放）。
- 通过 leveling_test.py 的 `_replay_auto_e2e` 子段（覆盖 `POST auto → ready → leveled_latest 200 transform ≈ pitch26/roll-1 → leveled_latest?sid=nonexistent → 404`）。

## 三既有 session（P03-A 数值证据，与 R2 联合值对照）

| sid | detect pitch / roll / d (m) | support | 与 R2 TLS Δpitch / Δroll / Δd |
|---|---|---|---|
| cap_20261004_202456 | 26.9265° / −1.2585° / 1.33222 | 0.3190 | **0.3033°** / 0.1362° / 0.01032 m |
| cap_20261004_203349 | 26.9459° / −0.8432° / 1.34130 | 0.3105 | **0.3226°** / 0.5514° / 0.01939 m |

`Δpitch < 1.5°` 两 session 都过 P03-A 门。

## P03 类型 C 必然结果：detect 出的 ROI 在新场地 GLW01 质量门 FAIL（如实保留）

跨 R3「6 对互预测 FAIL」的平复地：detect 的 1m 网格 ROI 同时覆盖 R3 #3 区（27.9°）与 #4 区（23.9°），同一 ROI 跨两块非共面地，TLS/SVD/RANSAC 全报告 `GL_FULL_DOMAIN_QUALITY + GL_REGION_QUALITY + GL_HOLDOUT_QUALITY`，consensus=NO_RECOMMENDATION。**detect 本身工作正常**（找到主面、给出 4 个 ROI、写 report）；**质量门如实反映 R3 结论文本**——不是 detect 错，是 GLW01 的"4 个 ROI 须各自 PASS"这一过门条件跟 detect 大网格 ROI 的「跨主导面」形态冲突。**不裁数据、不降门、不为过门调阈值**。

意义：auto 模式在「与旧四区手动大致同语义的单块主地」会话会 PASS 质量门（就 GLW01 R2 那三个 job 做过的那样），在 R3 类型 C 的非共面会话能出 NO_RECOMMENDATION 诊断报告，**作为「玩家可以试、不行你早知道」的诚实结果**。

## 截图证据（headless chrome 8902）

- `10_leveling_auto_button.png` — 配平页新增"自动配平 · 算法找地面区域"按钮（4 个 ROI 输入框右侧）
- `11_replay_auto_leveled.png` — replay 自动应用（来自既有 manual GLW01 job 27f870c6 的）TLS transform：左半非配平时点云并未水平，**整个 91 帧 4470632 点场景被奠成水平网格**；meta line 仍是 raw frame_id（这正是 manual job 的"显示配平"语义的保守保留）。

*说明：11 号效果图应用的 transform 来源是历史 **manual** GLW01 job，因为本轮 auto job `ef5df1eb` 如上所见出 NO_RECOMMENDATION、没有导出 transform。auto 按钮→ready→leveled_latest→replay 的链路**已在 leveling_test.py 的端到端子段验证 pass**，截图只替代性地展示「配平后的视觉差异」，不冒称是 auto 直产。*

## 复回归

- `python -B -W error -m unittest leveling_test -v`：4 tests 全过（含新增 `_replay_auto_e2e` HTTP 子段：auto POST → ready → leveled_latest transform 数值断言 → 不存在 sid 404）。
- `python -B -W error -m unittest leveling_auto_test -v`：5 tests 全过（synthetic 4 区 ROI + 三负路径 [主面上 n_z<.85 / d>1.8 / 连通域<4] + 二 session R2 锚点对照 <1.5°）。
- `node human_replay_lib.test.js`：45 tests 全过。
- GL-W01 手动工作流在 auto 分支下行为不变化（原 4 tests 仍过）。

## 逐 ID

| ID | 结果 | 证据 |
|---|---|---|
| P03-A | PASS（作者自验，detect 值 <1.5°） | leveling_auto_test.py `RealSessionAnchorTest` + 本报告数值表 |
| P03-B | PASS（作者自验） | leveling_auto_test.py 三负路径 assertRaisesRegex |
| P03-C | PASS（作者自验） | leveling_test.py `_replay_auto_e2e` 走 auto→leveled_latest→replay 链路；replay.js fetch 不阻塞旧 bag；旧手动 UI 未变 |
| P03-D | PASS（作者自验） | AUTO_ANCHOR 行打印每次测试展示 Δpitch/Δroll/Δd |
| P03-E | PASS（作者自验） | 原 4 leveling_test + 45 human_replay_lib tests 均过 |
| S01 | PASS（范围/页面/逻辑作者自验） | ponytail 声明已写；请求/SHA/控制台不打包；指定独审与真实 browser NOT_RUN |
| D01 | NOT_RUN | 不设备/commit/console 重打包 |

## 未闭合

- **auto 模式下 detect 的 1m 网格 ROI 跨非共面块**是 R3 类型 C 的显性化。后续选项：(a) 接受 auto 不推全场地、由用户手动细化；(b) 按 R3 模型 I 输出**分区平面集**而不是单平面；(c) 把 detect 网格从 1m 缩到 0.5m 并加保一致性过滤。**都不在本单范围**，本单保持原始判定语义。
- 真实 browser 回放（file:// fetch 拒绝；console exe 未重打包）NOT_RUN。
- 独审待 Codex 指定。

## 复审记录（2026-10-05 作者对抗性自审，非指定独审）

复审用 `code-review` 类别对本轮 P03 diff 排位核对（作者=复审者同一 Claude Code，不构成指定独审）。发现 2 个真缺陷 + 1 个披露不足，均已修复并回归通过：

- **DEFECT-1（坐标语义错位，根因修复）** `leveling_lib.detect_ground_domain` 原先把 ROI bbox 算在**估计 display 系**（candidate R），而 `freeze_domain` 按**名义 display 系**解释 regions，破坏 GL-W01「regions 在名义系」契约（0.3°≈2cm 漂移）。修复：网格化改用 `rotation(nominal_pitch_deg, nominal_roll_deg)`，与下游字节级一致。修复后真实 session ROI/候选平面数值与修复前一致（巧合接近），锚点对照 Δpitch 不变。
- **DEFECT-2（完整性降级+死代码）** `GET /api/leveling/leveled_latest` 原先算 `sha(report_file)` 未使用（死变量）且绕过 `artifact_path` 直接读 transform.json、不核 manifest SHA。修复：该路由现在 (a) 只认 `recommended=="tls"`（三法一致推荐），(b) 用 manifest 的 `report_sha256` 与 `artifacts.tls["transform.json"]` 逐文件核对 SHA，改动过即跳过该 job，(c) 全部核对不过返回 404，与既有产物通道完整性对齐。
- **DISCLOSURE-3（披露补充）** detect 用**全部帧**（含 3 个留出帧）选 ROI；与人工路径语义一致（人画布也看全部帧画 ROI，holdout 只护 plane 拟合而非 ROI 选择），非缺陷但此处补明。
- 复核无害项：`validate_request` 双 keyset 布尔边界（manual 6 键 / auto 4 键且 mode=="auto"）各组合正确；replay 注入点在 `build_geometry` 之前；标注/剪辑已删（commit 73447d1），无坐标回写污染面；`_synthetic_points` 在真实 session 测试不调用。

修复后回归：`leveling_test` 4 过、`leveling_auto_test` 5 过（含真实 session 锚点对照 Δpitch 0.30°/0.32°）、`human_replay_lib.test.js` 45 过。修复涉及的文件 SHA 在 `14_MANIFEST.json`/`13_SHA.txt` 为本节所述最终版本，非修复前版本。

## SHA

见 `14_MANIFEST.json`（13_SHA.txt 为修订后最终 SHA）。
