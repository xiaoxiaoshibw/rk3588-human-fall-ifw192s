# 2026-10-10 本地分组提交审计

用户明确授权：“分析一下哪些可以提交先提交了”。起始 master / HEAD `777296d707dbc0d6fe9684cad2a7500affbf3342`，已领先 origin/master 15 个提交，实际 index 为空。Codex 使用 ponytail：`C:\Users\30680\.codex\skills\ponytail\SKILL.md`。本轮不派新的实现者或独立审核者，不启动新算法开发。

## 可以先提交的两组

1. **HC/HR HTTP 会话下载与同步/改名**：板端白名单 GET/HEAD 文件下载及限速、浏览器下载链接；PC 以 HTTP 替代 SSH 别名/密钥依赖，失败回退与 transferred 只读复制；同步状态、人工恢复入口、点行同步后自动载入、本地别名及录制状态显示。14 个源码/测试/配置文件，具体路径与 SHA 见 candidates.json 的 group_a。
2. **Console 启动与本地会话入口**：Windows 独占监听、占用端口回退与异常传播；统一默认最新/合法深链/非法回退/空列表/API 失败提示，剔除不完整会话；打包参考源码清单及现有板端地址断言同步。第二组增加 12 个文件，与第一组累计 26 个。只收录入口补丁，不带一键配平弹层、GT 首页卡片或 B2 跟踪改动。

两组均是源码版本保存；第二组依赖第一组。发布 EXE/ZIP 继续按既有 .gitignore 保留在本机。第三组仅收录本次审计记录和相关既有工具链交付证据；历史记录原文不重写、不回填。

## 暂留工作区的内容与原因

| 范围 | 暂不提交原因 |
|---|---|
| HUMAN-UNIFY-R1 / human_core | 功能返工已有独审，但性能门仍 FAIL、冻结门 BLOCKED；不把研究版本提交成完成或生产接管 |
| HR-RET-V2 / human_pipe_lib / detect_ui | 缺独立复审与真实开启且 VALID 端到端；需要按该单完整收口 |
| detect_overlay / replay / RF 与 B2 shadow 探针 | 与当前 RF 并发修改和后续研究混合，需锁定具体 SHA 与范围后再独立提交 |
| GT 工作台/gt_store/预标与导出工具 | 建议生成依赖未提交的 human_core FUSION；工作台还列有 partial 项，不能与本次入口补丁混作独立完成 |
| human_detect 一键配平弹层 | 不是会话入口补丁本身，仍留在工作区；本轮未为它补做独立验证 |
| RF 优化、SEM、骨架、其他研究/计划与 sidequests | 各自存在 NOT_RUN/BLOCKED 或属于独立支线，需要按工单归档，未混入工具链提交 |
| make_leveling_release.py / validation 微调 / pelican_bike.html | 与本次两组闭合范围无直接关系，留待各自检查 |
| 大体积证据/点云/训练或 GT 派生产物 | 23.8GB 基线包含大量重复点云、ZIP 和逐点 JSONL；本次不整目录 git add、不删除任何文件 |

## 拆分与验证

使用临时独立 index，从初始 HEAD 生成 group_a/group_b 两棵候选树；通过 git archive 在忽略的 `tmp_commit_audit_20261010_r1/` 下生成隔离测试目录。隔离目录仅含各自候选 Git 树内文件，因此未提交源码无法隐式满足测试依赖。未在原工作树执行 checkout/reset 或生产文件替换。

混合文件的拆分：human_replay_lib.py 排除 GT GET/POST 路由及分发函数；console.html 排除 GT 卡片；human_detect.js/html 从 HEAD 只提取会话选择相关修改；human_track.html 只提取会话选择与提示，保留 HEAD 的检测按钮/算法行为。本次拆分后源码与已发布 EXE 的完整源码集合不同，旧 EXE 端到端证据不作为候选源码实测。

每组在其隔离副本执行：

```text
python -B -W error -m unittest discover -s src/human_capture/tests
cd pc_apps/human_replay
python -B -W error -m unittest fetch_lib_test sessions_test
node panel.test.js
node human_replay_lib.test.js
node human_detect_lib.test.js
node human_pipe_lib.test.js
cd webui/human_capture
node capture_lib.test.js
```

第二组另外执行：

```text
cd pc_apps/human_replay
node session_selection.test.js
python -B -W error -m unittest session_selection_test
cd pc_apps/console
node console_html.test.js
python -B -W error console_test.py
```

18 次套件执行全部退出 0。其中每组 capture 45 项、fetch/sessions 17 项，第二组 Console Python 5 项、会话索引 Python 1 项、选择器 Node 12 组、Console Node 10 组；数量只作执行记录。所有页面相对 script 依赖已核查，未缺文件。两棵树的 capture 包通过 `ast.parse(..., feature_version=(3,8))`；本机 Python 3.12 运行，未宣称 NumPy 1.17.4/板端 Python 3.8 实机兼容已经验证。

逐项判定见唯一 `../../COMMIT_AUDIT_20261010_ACCEPTANCE.md v1`；本次来源 SHA、实际命令/退出码、依赖核查、源码保留及提交 SHA 分别见 baseline.json、tests.json、dependency-check.json、source-preservation.json、commits.json。完整初始 dirty diff 与候选补丁留在本地同目录，未作为正式源码重复入库。

原工单状态保持，设备/物理/部署/采集/候选 EXE 构建和启动均 NOT_RUN。历史板端部署及 EXE 发布证据仅作既有交付记录归档，不延伸为本次验收。

## 已生成的源码提交

- `3038a9ccfd7b8e9f732f7f25254812475ba4f9e0` — HC/HR：改用 HTTP 下载会话并完善同步与本地改名
- `90d55b06bed4a52d59184634e7341b54b1f643a5` — Console：修复独占端口并统一本地会话选择入口

归档完整性备注：源码候选与本轮新文档的 `git diff --check` 均通过；历史验收表末尾空行、原始审核包/日志和 unified patch 的空白被原样保留，整份历史归档的空白检查退出 2（FAIL），见 quality.json / archive-whitespace.log。未通过重写旧证据来消除这些格式告警。

最终范围补记：提交源码仍与隔离测试的 group_b 树一致；额外全工作区 SHA 核对发现范围外 `pc_apps/human_replay/gt_annotator.js` 自基线后更新，本任务未写入该文件。全工作区冻结 **BLOCKED**，见 final-scope.json；外部修改原样保留。验收表 v1 当前文件 SHA256：`5c82555553fbc967a0eac3c1c07fbc38c49e6032039146fc432886fd9c6fd564`。
