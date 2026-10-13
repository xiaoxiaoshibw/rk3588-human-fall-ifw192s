# HF-REAL-03 助手视觉排查三单回传

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HF-REAL-03 / R1 / Claude (claude-fable-5) / 2026-10-13
- 验收表路径 / 版本 / SHA（提交时记录）：docs/human_fall/evidence/2026-10-13_hf_real_03_r1/ACCEPTANCE_V1.md（版本 v1）
- 执行方式 / 实际会话与模型：本机 (Windows 11, Git Bash)；Claude Code + Python 3.12 + Node v24
- 状态：SUBMITTED。软件自验 PASS（工具层） / DATA_BAD（任务2）/ BLOCKED（215623/215643/233658 / GT / 设备 / 部署 / 独审）。尚未 ACCEPTED。
- 起始 branch/HEAD / 工作树 / 范围内用户差异 / 源码与配置 SHA 证据：master/026e06303f60ed1bbe4ddc4d037836db68da6d27；工作树起时含 267 项用户差异，本单未动；边界面 SHA 明细见 `SOURCE_AND_END_BOUNDARY.json` / `ARTIFACTS_FINAL_SHA.json`。
- ponytail SKILL.md 实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| f10 家具是否混入 (RS04) | r02 writer 保守上报；v2 target 实际无论如何未见家具残留 | HF-REAL-02 RS04 FAIL 位子、 r03 RS-C | 在 r03 视觉+ v1 过滤盒（证据级） | 未动 r02 源码 / 生产 / 模型 / GT; 家具盒进 r03 仅交付，不接生产 |
| 视觉盒本身的错 | 助手在 f10/f11 侧视图左下户看到的细窄极长静态簇猜为家具；实际那是人腿经过区 | r03 RS-C | vision_clean.py 输出作为证伪证据 | 404 点 100% 落在 HF-REAL-01 助手视觉人区内，盒子被拒 |
| 093958 配平 FAIL | 场景里几乎无可用地地面 patch，是采样与遮挡机制决 | RF02 二次用法 / 独审拿 | 快照 f5/f60/f115 记录行为性缺；判 DATA_BAD | 不接入追踪 / 不动 r02 配准 / 不降门 |
| 215540 站立人被吞 97.6% | build_static_map 的 occ_strong 门在 64 帧中任意持续占用体素必然被当背景；是行为性缺陷不是参数 | HR-W03 REWORK / fusion v2 参照 pipe 行为面 | r03 P 臂 mask 量化证据； 生产 pipe 未动 | 不授权 fusion v2 接生产 |
| 215623/215643/233658 数据不在 | 板上不存、本机 `captures/remote/` 仅有 215540；local raw .bag 不存在 | r03 RS-F； fusion v2 ab 不可重测 | 板上 ssh ls 只读验证 | DATA_BLOCKED，不假造 |
| f47/109/118 axis_ambiguous | 下滑后人体近接地水平姿态产生 PCA 异质 | r03 RS-I | 渲染 AMBIG_COMPARE.png 作为证据 | RS05 BLOCKED 保持，不为此启动骨架部署 |

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|----|---|---|---|
| sidequests/human_fusion_lab_next/real_fall/r03/render_f10.py | 渲染 r02 f9/f10/f11 前景点 + target bbox 对比 (助手视觉索引) | 新文件 | 见 ARTIFACTS_FINAL_SHA.json |
| sidequests/human_fusion_lab_next/real_fall/r03/vision_clean.py | 用视觉盒产生 process_v3.json （证伪证据） | 新文件 | 见 ARTIFACTS_FINAL_SHA.json |
| sidequests/human_fusion_lab_next/real_fall/r03/render_v3_compare.py | 渲染 v2 vs v3 对比 + f47/109/118 骨架检查图 | 新文件 | 见 ARTIFACTS_FINAL_SHA.json |
| sidequests/human_fusion_lab_next/real_fall/r03/examine_overlap_093958.py、examine_093958_v2.py、examine_093958_v3.py | 读 093958 leveling.json + 渲染 f5/f60/f115 | 新文件 | 见 ARTIFACTS_FINAL_SHA.json |
| sidequests/human_fusion_lab_next/real_fall/r03/probe_215540.js | 用 human_pipe_lib/registration JS 以 P 臂量化站立人在 0.55m 人区被吞比率 + mask 转 JSON | 新文件 | 见 ARTIFACTS_FINAL_SHA.json |
| sidequests/human_fusion_lab_next/real_fall/r03/render_215540_mask.py | 读 mask.json 渲染 PNG | 新文件 | 见 ARTIFACTS_FINAL_SHA.json |
| sidequests/human_fusion_lab_next/real_fall/r03/README.md | r03 清单 | 新文件 | 见 ARTIFACTS_FINAL_SHA.json |
| docs/human_fall/evidence/2026-10-13_hf_real_03_r1/ | 现在 ACTIVE； Acceptance + FINAL + out/* + SOURCE_AND_END_BOUNDARY.json + ARTIFACTS_FINAL_SHA.json | 新证据目录 | 见 ARTIFACTS_FINAL_SHA.json |
| docs/human_fall/returns/HF-REAL-03.md | 本 return | 新文件 | 见 ARTIFACTS_FINAL_SHA.json |
| docs/human_fall/WORKFLOW.md | 顶部登记本单 | 顶部追加 | 见 ARTIFACTS_FINAL_SHA.json |
| docs/human_fall/REVIEW_LOG.md | 登记本单 | 顶部追加 | 见 ARTIFACTS_FINAL_SHA.json |

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| RS-A 基线绑定 | offline | git rev-parse HEAD + status --porcelain | PASS | FINAL_ARTIFACT_SHA.json 详 |
| RS-B r03 隔离 | offline | 上下文件清单 | PASS | SOURCE_AND_END_BOUNDARY.json |
| RS-C f10 家具 | offline | vision_clean.py 跑 r02 foreground.bin/process_v2.json 产出 process_v3； examine_overlap_093958.py 定量 overlap | PASS (工具) / FAIL (视觉盒) | REMOVED_VS_PERSON_REGION.png; process_v3.json |
| RS-D 093958 | offline | examine_093958_v3.py 读 leveling.json + 渲 f5/f60/f115 | PASS (工具) / FAIL (数据) | 093958_SNAPSHOTS.png |
| RS-E 215540 P臂吞人按部位 | offline | probe_215540.js + render_215540_mask.py | PASS | 215540_P_MASK.png, 215540_frame_stats.json |
| RS-F 三段会话不在 | offline | 板上 ssh ls + 本机 ls | BLOCKED | 板上 47 段中 0 段为 2026-10-07 |
| RS-G 生产/GT/模型 untouched | offline | git status --porcelain 收口 | PASS | FINAL_ARTIFACT_SHA.json |
| RS-H 独审 / 设备 / 部署 / 生产 / GT | device / deploy | NOT_RUN （未授权） | BLOCKED / NOT_RUN | 未运行 |
| RS-I 骨架 3 帧 axis_ambiguous | offline | render_v3_compare.py 渲 AMBIG_COMPARE.png | PASS (借用) / BLOCKED (生产骨架) | AMBIG_COMPARE.png |

## 未闭合与限制

- 未满足的验收ID、复现条件和解除条件：
  - RS04 FAIL 关闭理由需独审重新审查； 本单 r03 仅是证据； 不代为关闭。
  - fusion v2 启动到生产未授权。
  - 093958 不接追踪。
  - axis_ambiguous 3 帧骨架不接生产。
- 契约允许的算法/证据限制：
  - 任务 1 证据仅依据 f9/f10/f11 三帧； 跳过骨干打印。
  - 任务 3 P 臂仅 64 帧人物区 (r=0.55m)；不展望整段会话外场。
- 范围外新需求及后续建议：
  - 助手视觉引入"场景邻居学 gradual localization"修订家具 vs 人腿的判断；
  - 调整人体主干固位置形以为 reserve 性；
  - 三段会话 (215623/215643/233658) 在别处提供再测定；
  - 独审是否关闭 RS04。
- 设备/物理未跑项：
  - 板上 fuse v2 的接入 / 设备上的 pipe 运行 / 性能验证 / 部署 / 与其他板端板只间相互作用 NOT_RUN。

## 交给Codex独立复审

- 现行验收表与本轮变更记录： `docs/human_fall/evidence/2026-10-13_hf_real_03_r1/ACCEPTANCE_V1.md`
- 根因诊断/完整入口检查证据： FINAL_REPORT.md + out/*
- 源码差异与 SHA 证据： SOURCE_AND_END_BOUNDARY.json + ARTIFACTS_FINAL_SHA.json
- 原始日志索引： out/* 名与文件读入最终会话过程.
- 当前工单下一步：独审是否关闭 RS04，fusion v2 接入生产授权是何时候开始由用户决定。

Codex 读取共享工作区并对全表独立复审，集中反馈已有要求下的缺陷。派工遵循 WORKFLOW 当前约定；手动派工不授权自动启动下一单。
