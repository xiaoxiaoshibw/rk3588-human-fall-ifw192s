## 2026-10-16 HFUS-INDOOR-DATA-QUAL-01 R1 / SUBMITTED（人审进行中，非ACCEPTED）

### 本轮信息

- 派发动作：用户 2026-10-16 指令「现在深度学习继续开发」；唯一拟验收=上一单审后包
  `sidequests/hfus_indoor_ai_test/reports/next_stage_20261015_r1/ACCEPTANCE_V2.md`（ND01–ND08，SHA 见
  其 R2 审查记录），执行范围含 NEXT_STAGE_PLAN_V2 与 AI_DEVELOPMENT_PROMPT_V2。
- 单 writer：本会话 Claude Code（Codex/OpenCode 分工沿用规则：OpenCode 审查留待 ND08，源码冻结后）。
  技能实际读取路径：`C:/Users/30680/.claude/skills/ponytail/SKILL.md`（本轮加载并记录）。
- 起点 master / HEAD `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`，dirty；基线
  `evidence/2026-10-16_hfus_indoor_data_qual_r1/BASELINE_R1.json`（47 相关源 SHA）、STATUS_BEFORE.txt、
  GIT_HEAD.txt。三 ZIP 本轮全量重算 SHA256=冻结清单逐字节一致（ZIP_SHA256.txt vs r7 manifest archives）。
  无 commit/push/reset/clean，无设备/采集/部署/下载训练数据/HR09/E1；旧 run r7/r4、ZIP、data、captures、
  demo 冻结 15 源、权重、EXE、历史证据未改（新文件全部在 qual_r01 与新证据目录）。
- 证据目录：`docs/human_capture/evidence/2026-10-16_hfus_indoor_data_qual_r1/`。

### ND02 集中诊断与根因

旧阻塞=末列语义(yaw vs ID)与 z 表示不可追溯。闭合路径：作者仓库精确版本 commit `275989e` blob SHA
寻址取证（raw.githubusercontent 被网络重置，改 api.github.com 原始 blob 成功，9 份上游件留证含
sha256）；作者 `crane_dataset.py`/`dataset_openpcd.py`/`ab3dmot_tracking.py`/README/已入库预测件五路
一致=**末列 yaw 度、绕+Z、GT 无 ID 列**；本地 526 框物理实测（ROTATION_GEOMETRY_R1.json：主轴集中
R=0.511/0.648、值域[0,356]全整数、相邻帧 Δv 恒零仅15.3%、z 残差+0.02/-0.001）独立支持同结论，
反证实例ID。矛盾如实保留：作者类要求≥8数值自相矛盾、openpcd/AB3DMOT 单位口径不一、导出器
`data/convert_json_to_txt.py` 未入库缺位。撤回上一轮“49 实例ID”读数。解释注册表
`INTERPRETATION_R1.json`（OD1-boxes/v1，适用=本三 ZIP 全部 526 框，不泛化）。

### ND03/ND06 交付

`sidequests/hfus_indoor_ai_test/qual_r01/`：`make_queue.py`（规则预注册、确定性）产出冻结队列
QUEUE_R1.json 24 帧（track 3 时间簇×4 + det training5/validation1/test6，覆盖 1–4 框、命名日期组
20251021/20251022/UNNAMED、最小支持 58 点框、最大支持 4795 点框）；`qual_server.py`+`index.html`+`app.js`
审核台：三栏完整房间（原始点云/旋转解释后 GT/未分类候选，复用生产显示变换 diag(1,-1,-1)与 vendor three），
每框 人体?/画对?/理由必填 + 完备性三态，追加式哈希链账本（reviews/ledger.jsonl，永不覆盖，AI 不代填），
启动核 r7 manifest/队列/三 ZIP/父 payload SHA，每请求成员 CRC+SHA 漂移即 409 清屏。入口
`start_qual.bat`。

### 逐条验收（ND01–ND08）

|ID|结果|实际/证据|
|---|---|---|
|ND01|PASS|本派发段；单writer；三ZIP全量重核=冻结；BASELINE_R1 47源；预算内（CPU<15min、新增字节<<128MiB、零下载零解压整包——仅拉9个小文本上游件）|
|ND02|PASS|可追溯定义闭合（作者多读取器+同源预测件+本地几何实测）；未解决=导出器本体缺位与作者单位口径矛盾已列明；未把未知旋转归零，AABB代理在 qual 页改按 yaw 显示|
|ND03|BLOCKED|审核台已交付可用；真实人工审核 0 条（待用户在本机队列实审≥20帧；ledger 首笔为真实人工记录）|
|ND04|BLOCKED|精确重复2组(含det_000≡track_113、det_070≡track_180)、track传感器时钟3簇、det命名2日期+UNNAMED已记账；作者无录制/会话/人员元数据、时间簇不构成独立组→可信独立采集组0，拟test=0|
|ND05|BLOCKED|资格门依赖 ND03；正/负计数脚本待人工审核产生后运行，现 可信P0/N0/U=全部候选；无两类监督不启动训练依赖（本轮训练0/模型0）|
|ND06|PASS(软件)/真实浏览器待用户首用|state 校验+HTTP 冒烟（HTTP_SMOKE_R1.json：队列24、track_107 全点字节=points×12、SHA漂移409、空审核者409、自检200仅入临时账本、真实账本未建）；快切/清屏/绑定继承生产模式；“实际浏览器”记录=用户实审会话（本单不冒称）|
|ND07|PASS|`test_qual.py` 2项 `-B -W error` exit0（13 非法用例逐错误类型拒、合法入账+哈希链）；node --check app.js exit0；旧资产保护：r7/r4/ZIP/demo/learn 未写，三 ZIP SHA 重核一致|
|ND08|NOT_RUN|指定 OpenCode 只读审查待源码冻结与人审轮结束后进行；不以 probe 冒称审查 PASS|

### 未闭合与下一步

1. **等真实人工**：用户在审核台完成 ≥20 帧（预算≤120min）：每框 人体/非人体/不确定+框正确性+理由、
   完备性三态。审核者填真实姓名；AI 代填无效。
2. 人审入账后：跑 P/N/U 资格计数与正/负候选门（ND05），更新本 return R2 段。
3. ND08：冻结 SHA → opencode-go/deepseek-v4.1-flash 只读审查（先 ≤55s probe）。
4. 本单不解锁训练/E1/HR09；独立组 0 时效果评估持续 BLOCKED。


## 2026-10-16 R2 / SUBMITTED(ND03 按唯一验收 FAIL/BLOCKED;AI 替代轨已授权)

用户指令「继续开发,不依赖真人,真人不如AI大模型」→ AI 视觉判读经授权入账(`post_ai_reviews.py`,24 帧/53 框全 `reviewer_kind=AI` 署名,追加式哈希链 ledger.jsonl,终 sha 见 SOURCE_FREEZE_FINAL)。ND 逐条终态:
ND01 PASS;ND02 PASS+勘误(mod-90 边界/track frac_integer=0.9957,原文不删、追加勘误段);
ND03 **FAIL/BLOCKED 按原文**(无真人、无真实二审)——AI 替代轨交付 50 HUMAN/3 UNCERTAIN/0 NONHUMAN+完备性建议,全部标 AI-labeled;
ND04 BLOCKED(独立组 0,同 R1);ND05 **QUALIFIED conditional**(BEV 匹配+AMENDMENT_A1 事后登记:R1 3D 保留 P=8/BLOCKED,BEV 后 B0 P29/B1 P20/N≥7188 过 20/20 门;负类依赖 AI 完备门,记 conditional,缓解证据组折 FP=3/25782);
ND06 软件 PASS+浏览器=用户后续实审台使用;ND07 PASS(test_qual 2 项含合法 AI 正向用例、smoke HTTP、ledger 链独立可验);
ND08 完成:OpenCode 只读 R1/R2/R3 三轮(READONLY_REVISE×3;R1 11 finding/R2 记账失实 4/R3 剩 2 均修,处方与复算见 train_ai01 目录 REVIEW_R*_RESOLUTION;实际工具 read/grep/shell-只读,session export 证模型)。
本单不训练;训练另单 HFUS-INDOOR-TRAIN-AI01(域内 RF P0.955/R0.724@B0 组折;PN FAIL)。无 Git 写/设备/采集/部署;旧资产零变化(ledger 为唯一新增写路径)。
