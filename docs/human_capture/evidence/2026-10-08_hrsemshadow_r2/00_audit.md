# Phase 0 只读审计与最小返工计划

日期：2026-10-08，Asia/Shanghai。单 writer：本聊天 Codex。生产接入仍未授权。

先读 AGENTS.md、HC README、原工单、唯一表 v1、R1 REVIEW/return、原 finish.py/review_template.html/shadow.js/negatives.js、独立审核脚本与相关契约。实读 ponytail：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。审计前仅新增本目录的原样 record.py 和只读基线记录，没有修改实现。

起始 master / cfbb80c57508be1a0435fdb92260f698dc763934；完整基线 6140 条路径、43,283,465,274 字节，包含 tracked/untracked、ignored captures、HC evidence、console dist，缺失路径/符号链接单列。见 00_baseline.json / 00_dirty.patch。唯一表 SHA 3b5b83da5a83c460bc7590011034647f77272be70d1f92f7c2ddb9c0bd8498dd，工单 SHA f9e9e4f705c2ed571d495f7164341bead7e768106eb48458ce40f474f4e819d6。

## 实际缺陷与数据流

`shadow.clusterFrame()` 从 cleanup 簇提取 rows，member_sha256 是 canonical JSON(rows) 的 SHA，**不是成员内容 SHA**；xyz_sha256 才绑定变换后的坐标。原始源 meta/bin SHA 在 pass3/binding.json；global row=meta.frames[ordinal].offset_points+row，点布局28字节。`finish.prepare()` 从这些文件制作 template/bundle；`review_template.html` 的 indexfile/loadraw 入口只核源 meta/bin，未核外部 index 的 digest、身份或 row 哈希，直接显示 c.rows 并复制 c.member_sha256。save 导出该声明 SHA。`finish.check_gt()` 仅与可替换 template 的同名字段比对，未从 raw 重算 rows/坐标，也未绑定显示身份与票据。R1 review_index_challenge.json 以 row0 替换1029成员但保留原 SHA，gt_challenge.json 证实接受。这与 R1 README 自验 SEM-12 PASS 矛盾，支持独立 REVIEW 的 FAIL。

权威清单：R1 pass3/clusters.jsonl，冻结 digest adc603b5783bee4d71cd38b7341f30dcbe563d9a3464d5bffa6d26ce609d6eee；经 R1 独立 raw 全帧重算支持，R2 继续重算。可信源 binding digest 2f0f3aaaf6b6c62aedcf5b02de30539da13cc0afce324d7dc4fba44ccdb26416。不能把待审对象提交的新 manifest 或内部 SHA 当权威。R2 校验器的源码常量固定这些摘要和路径；候选 sidecar 无权指定基准。工具源码/页面本身属于受保护交付物，任意替换工具及其源码常量超出本地校验器信任边界，必须由交付 SHA 检出。内容校验不证明人工标签真值或人确实观察过某画面。

票链：pass3/votes.jsonl 按 sid/mode/ordinal/seq 记录 reference.assigned.ci 与机器身份；R2 receipt 同时绑定 review_id、vote_member_id、票帧内容摘要，核对应簇 ci 确实在 assigned 中，仍不升级机器身份为真人 GT。

## 分类与阻断

| 项目 | 分类 | 原因/解除条件 |
|---|---|---|
| SEM-12 | 实现缺陷 | 未绑定外部索引和实际内容；需固定独立权威 digest、源路径、rows/XYZ、显示和票据身份，正负实际验证 |
| WD02 | 验收规范歧义 | shadow.level 对 report.code_hashes 做历史生成源码==当前硬断言；SEM v1 要求绑定而未明示相等，registration.levelingBinding 不做这项；需裁定，不删除断言或重写历史 |
| SEM-05/08 | 证据不足 + 已证实目标上界不足 | 人工全帧GT未闭合；任意HUMAN帧13/244、1/195，上界已低于95%，补GT不会自动通过 |
| SEM-06 | 证据不足 | 269/271结构代理非身份命中；非ROI成员/家具混入未审，gate WARN |
| SEM-07 | 证据不足 | 281/281结构代理；185+5及全部边缘成员身份未知，91.92%为区域口径 |
| SEM-10 | 证据不足 + 依赖项阻断 | WD01区域P4/WS12 HUMAN需GT；箱子64 UNKNOWN，low_bar64空输入、格栅无绑定资产NOT_RUN；WD02契约阻断 |
| 真实浏览器UI | 验证依赖 | R1工具访问失败，R2尝试获准浏览器入口，失败保持BLOCKED |

## 文件级最小修改计划（实施前记录）

仅新增 R2 evidence：review_binding.js（固定权威文件与raw内容重建、receipt验证）、build_review.js（复用原页面/34案例生成R2交付）、review_template.html（复用原UI，索引digest/row/内容绑定、失败清空可审状态）、sem12.test.js（七类负例与正例、独立预期）。原 finish.py 和所有 R1 assets 不改，R2成为修复后入口，旧入口明确废弃为历史。

只读审核工具复制到R2，改输出路径/当前基线文件名，不改算法；重算全帧/成员/票、旧可用负例与冻结样本，重跑PL/replay/registration必要回归。新增WD02只读诊断，不调用绕过H.level的处理路径。旧WD01绑定审阅入口缺口登记，本轮不伪造GT或扩展算法。

新增本轮七份报告与完整SHA/log/逐ID表；return末尾追加，原字节前缀复核。无阈值、人体检测/分类/跟踪/背景/Registration生产修改，无采集部署、commit/push、清理或重签。形成报告后进入Phase1；不以报告齐全或工具exit0判算法目标PASS。
