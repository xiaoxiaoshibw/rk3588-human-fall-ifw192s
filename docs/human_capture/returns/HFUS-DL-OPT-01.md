# HFUS-DL-OPT-01 回传

## 2026-10-16 R1 / PointNet 训练协议三缺陷修复（合成自验）/ SUBMITTED（真实效果 BLOCKED）

### 本轮信息

- 工单=HFUS-DL-OPT-01（深度学习优化，承接 HFUS-INDOOR-TRAIN-AI01 R2 审查发现 2）/ 轮次 R1 / 执行者=OpenCode opencode-go（MiMo-V2.6-Pro）/ 2026-10-16。
- 授权=用户「继续优化深度学习」+ 本轮选择「不补数据，先做合成自验」「只修三缺陷+公平重评」。
- 验收表 [ACCEPTANCE_D1.md](../evidence/2026-10-16_hfus_dl_opt_r1/ACCEPTANCE_D1.md) v1（DL01–DL08）；逐条 [RESULTS.md](../evidence/2026-10-16_hfus_dl_opt_r1/RESULTS.md)。
- 状态：软件自验 SUBMITTED；真实训练/真实效果/独立复审/设备物理均 NOT_RUN 或 BLOCKED，不宣布工单 ACCEPTED。
- 起点 master/c9c4ee421cb0c8a3e4590b8f5730828b093c759a，工作树 dirty（既有并行差异保留，未回滚）。
- ponytail SKILL.md 实际读取路径：`C:\Users\30680\.config\opencode\skills\ponytail`（skill 工具加载，full）。

### 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| DL03（R2 发现2-①）| 折循环前只建一次 PointNet/Adam，后 3 折验证样本已在折 0 训练中出现 | 旧 run_pointnet 全部 PointNet OOF 读数（T06/T07 判定）| `dl_fix01/pointnet_cv.py` `run_cv()` 每折 `init_model()+Adam`，`model_seen` 随重建清零 | `carry_state=True` 仅作旧缺陷对照 |
| DL04（R2 发现2-②）| pos_weight 用全量 25782/49≈526，而训练实为 6000 采样子集（≈121）| 旧 PointNet 损失权重、训练动态 | `pos_weight_from()` 取各训练折实际采样分布 | 与全局口径差异留证（合成 4 折 4.14–5.67 vs 5.0）|
| DL05（R2 发现2-③）| 后 3 折非有效 OOF，分数不可作同折公平对照 | 一切 PointNet vs RF 对比结论 | OOF 1:1 覆盖 + 当前模型对验证折零见断言 | 合成对照只证机制不冒充真实 |
| DL01 | 真实输入（三 ZIP/候选与标签账本/原训练器）自上一单起原路径缺失，原因未确认 | 真实训练、真实重评 | [MISSING_INPUTS.json](../evidence/2026-10-16_hfus_dl_opt_r1/MISSING_INPUTS.json) 实测入册 + 解除清单 | 不恢复/不重建/不下载 |

开发中测试抓出 2 处本轮实现自身缺陷（污染计数误用全局累计；计数时机先于模型重置）——均为新代码内部问题，修根因后通过，非旧缺陷复现失败。

### 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区别 | 提交源码SHA |
|---|---|---|---|
| `sidequests/hfus_indoor_ai_test/dl_fix01/pointnet_cv.py` | 新：TinyPointNet + 三缺陷修复的组折 OOF 协议 + 合成对照 main | 全新文件，不复刻旧训练器、不产真实成绩 | 0456816A281D40DBF87FF669DA7631050BCEA3655B66B2F4BDD317AB96268A0F |
| `sidequests/hfus_indoor_ai_test/dl_fix01/test_pointnet_cv.py` | 新：4 项合成断言（权重口径/折间重置/OOF 零见与覆盖/可学与确定性） | 同上 | D5D4DE870B5F806F3C212AFB8BCC28AEF869B1E1AEC1F54A62DA4509C22301AD |
| `docs/human_capture/evidence/2026-10-16_hfus_dl_opt_r1/` | 新：验收 v1、RESULTS、SYNTHETIC_RUN.json、TEST_OUTPUT.txt、MISSING_INPUTS.json | 证据新目录，不覆盖旧证据 | — |
| `docs/human_capture/README.md` / `returns/HFUS-DL-OPT-01.md` | 仅顶部追加本条索引 / 新回传 | 不改旧条目 | — |

未改生产/数据/模型/旧证据；无 Git 写、无下载、无采集部署。

### 逐条验收

| 验收ID / 入口 | synthetic/offline/device | 实际命令 | 状态/退出码 | 日志/样本 |
|---|---|---|---|---|
| DL01 输入门 | offline | 原路径实测 + `dir /s /b` 全盘 + worktree/回收站核对 | PASS（缺件如实入册）| MISSING_INPUTS.json |
| DL02 独立新码 | offline | `git status` 对照 | PASS | 本回传"实际变更" |
| DL03 折间重置 | synthetic | `python -B -W error -m unittest discover -s sidequests/hfus_indoor_ai_test/dl_fix01` | PASS / exit 0 | TEST_OUTPUT.txt |
| DL04 pos_weight | synthetic | 同上 + pointnet_cv.py main | PASS / exit 0 | TEST_OUTPUT.txt、SYNTHETIC_RUN.json |
| DL05 OOF 公平 | synthetic | 同上 | PASS / exit 0 | prev_seen_in_val 固定[0,0,0,0] vs 对照[0,32,32,32] |
| DL06 合成自验 | synthetic | `python -B -W error .../pointnet_cv.py` | PASS / exit 0 | SYNTHETIC_RUN.json |
| DL07 测试 | synthetic | 同上单测（4 tests OK）| PASS / exit 0 | TEST_OUTPUT.txt |
| DL08 真实重评/独审 | — | — | NOT_RUN/BLOCKED | 解除清单=MISSING_INPUTS.json |

### 未闭合与限制

- 真实训练、真实 P/R、真实错误回放 BLOCKED：解除需三 ZIP 回到 `ML/data/`（原名+SHA 见 MISSING_INPUTS）或用户授权重下；候选/标签账本与 run4 划分缺失时相应步骤单独 BLOCKED，不以重算冒充冻结件。
- 合成结论只证协议机制（无泄漏、权重口径正确），不证明 PointNet 路线成败；旧「FAIL 确证」依 R2 已记不成立，本单不重写历史。
- 独立复审 NOT_RUN（指定复审者 opencode-go/deepseek-v4.1-flash 未派发）；设备/物理/板端/部署/采集 NOT_RUN。
- 后续：输入补齐后按 DL04/DL05 协议重训重评（真实成绩允许下降）；再谈调参/架构/算力。

### 交给独立复审

- 现行验收表：ACCEPTANCE_D1.md v1；本轮变更记录：本回传 + RESULTS.md。
- 源码差异与 SHA：见"实际变更"；原始日志：TEST_OUTPUT.txt、SYNTHETIC_RUN.json。
- 当前工单下一步：等用户补齐输入（或授权重下）后启动真实重评；在此之前不启动 PointNet 调参/采集。

## 2026-10-16 R2 / 深度学习开发封存 / SEALED

- 用户指令：「算了先暂停深度学习开发，之后再说先封存」。
- 处置：HFUS-INDOOR 侧链深度学习（PointNet）开发自本条起**封存停写**。R1 全部工件（`sidequests/hfus_indoor_ai_test/dl_fix01/` 源码、`evidence/2026-10-16_hfus_dl_opt_r1/`、缺件清单）原样留仓备对照，不删除、不改动、不重算、不补数。
- 状态：SEALED（冻结于 R1 SUBMITTED；DL08 真实效果/独立复审维持 BLOCKED/NOT_RUN，历史判定一律不重写）。
- 解除条件：① 用户明确恢复口令（如「继续深度学习」）；② 真实效果另需三 ZIP 回 `ML/data/`（或用户授权重下），见 [MISSING_INPUTS.json](../evidence/2026-10-16_hfus_dl_opt_r1/MISSING_INPUTS.json) unblock。恢复时从 DL01 输入门重新核起，不沿用任何未验证结论。
- 本轮无代码/数据/模型/Git 写；不接管其他主线。RF-EVAL（EV01–EV14）维持「计划已交、未开工」，本封存既不启动也不取消它。

## 2026-10-16 R3 / 合成输出删除（用户指令）/ DELETED

- 用户指令：「产生的数据删掉」，经确认范围=**只删合成输出三件**，代码与文档记录保留。
- 已删清单（删除前 sid/bytes/sha256 记录，删除于同日）：
  - `evidence/2026-10-16_hfus_dl_opt_r1/SYNTHETIC_RUN.json` 2178B sha256 `5DDEEC54EED6B40C90EBA8D5C48CF5B5EE2DD4ED18E93ADE06576D7D520359FA`
  - `evidence/2026-10-16_hfus_dl_opt_r1/SYNTHETIC_RUN.stderr.txt` 0B sha256 `E3B0C44298FC1C149AFBF4C8996FB92427AE41E4649B934CA495991B7852B855`
  - `evidence/2026-10-16_hfus_dl_opt_r1/TEST_OUTPUT.txt` 1828B sha256 `AE44DA79021D84CAF30B8F4B36CB2669C8DEB8DF4A13707C570FEDA54EA8911D`
- 保留：`dl_fix01/` 两源码、ACCEPTANCE_D1/RESULTS/MISSING_INPUTS、本回传、README 条目。RESULTS.md 内指向上述三件的链接失效，其引述数值仍以表内文字为准（如需复现可按 DL07 命令重跑，属新生成、不回填旧记录）。
- 未触碰 `data/` 数据根目录及任何旧证据/旧资产。
