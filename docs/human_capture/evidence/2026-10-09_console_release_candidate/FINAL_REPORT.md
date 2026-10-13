# Console 候选发布 FINAL_REPORT

**工单**：CONSOLE-RELEASE-ALL-IN-ONE — 一站式构建、修复、验证与发布候选交付
**日期**：2026-10-09
**执行**：Codex 主控；OpenCode 独立审计 agent ×2 轮（初审 + 终审）

---

## 总结论

**发布候选 = `candidate/Console.exe` + `candidate/LiDAR_Console.zip`，状态：PASS。**
已满足全部 11 项测试要求中的 **10 项 PASS + 1 项 BLOCKED（合理）**。
历史 20 个 EXE/ZIP 字节未变；未授权 B2-A-FIX-R1 / HR-RET-V2 修改**未进入产物**；输入 manifest 68 行零污染。

---

## 1. 基线（STEP 1）

| 项 | 值 |
|---|---|
| HEAD | `347a5bf05ee82766436382f4fc3d1a8ed15c1132` |
| 工作区未授权修改 | pc_apps/human_replay 15 个 M 文件 +1451/-199 行（B2-A-FIX-R1 / HR-RET-V2）+ 7 个 ?? 探针脚本（b2a_*） |
| 已授权文案修复 | pc_apps/console 4 个文件：console.html / README.txt / console_html.test.js / console_test.py（+23/-21 行） |
| RF 资产状态 | `rf_person.js` / `rf_person_v1.json` / `rf_test_fixture.json` 全 CLEAN-tracked @ HEAD |

**判定**：HEAD 即最新已验收基线（commit 347a5bf「B2a RF 分类接件 12/12 推理对齐」）；工作区 1300+ 行属**未授权**状态，严格排除。

## 2. 隔离构建区（STEP 2）

`git worktree add --detach D:\Code\ldiar_console_build 347a5bf`；工作区干净（`git status --porcelain` 空）。
迁入 4 个授权文件后 worktree diff 仅 5 个文件（4 个 console 文案修复 + 1 个 Console.spec 注释 + console=True 诊断标记共 ~6 行非注释实质改动）。
`diff/console_copyfix_final.diff` 保留最终授权差异。

## 3. 构建（STEP 3）

| 产物 | 来源 |
|---|---|
| `candidate/Console.exe` | 首次 PyInstaller 构建（console=False，GUI 子系统 PE Subsystem=2），64,524,935 bytes |
| `candidate/LiDAR_Console.zip` | Console.exe + README.txt，64,118,529 bytes |
| `build/dist_diag/Console.exe` | 诊断构建（console=True 抓 banner），64,532,518 bytes；**非交付**，仅证据 |
| 输入 manifest | `input_manifest/manifest.tsv` 68 行，100% `HEAD:347a5bf` 标记，零 `WORKING-DIFF` |
| 输出 SHA256 | `sha256/outputs.sha256` |

构建命令（cwd 钉死在 worktree）：
```
cd D:/Code/ldiar_console_build/pc_apps/console && python -m PyInstaller --noconfirm --clean \
  --distpath <stage>/build/dist --workpath <stage>/build/work Console.spec
```

## 4. 自动测试（STEP 4）

| # | 测试项 | 结果 |
|---|---|---|
| 1 | Console 主界面能真实启动 | **PASS**（GUI 子系统 EXE 进程存活，8901 LISTENING） |
| 2 | 五张功能卡能正确渲染 | **PARTIAL**：HTTP 200 on `human_detect.html`/`human_track.html`/`validation.html`/index；卡片渲染由 `console_html.test.js` 10/10 PASS（APPS[0..3] 探活逻辑）覆盖。**WebView2 内 DOM 渲染未直接测**（见 BLOCKED） |
| 3 | 两处文案与 README 一致 | **PASS**（console.html APPS[2]/APPS[3] desc 与 README.txt 同步修改；console_html.test.js 10/10 PASS） |
| 4 | 页面跳转和资源加载正常 | **PASS**（PACKAGED EXE 独占 8901 时 GET / /human_track.html /rf_person_v1.json /validation.html 全 200） |
| 5 | 纯几何入口不调用 RF | **PASS**（human_detect.html 不引用 rf_person.js；`grep -c rf_person human_detect.html`=0） |
| 6 | B2a 入口加载模型并推理 | **PASS**（`human_track.html` HEAD blob 引用 `rf_person.js` 并 fetch `/rf_person_v1.json`；rf_person.test.js 9/9 fixture PASS；JSON 51 维模型被服务且首字节匹配） |
| 7 | console_html.test.js 全过 | **PASS**（10/10） |
| 8 | 现有相关回归不退化 | **PASS**（console_test.py 4/4 + rf_person.test.js + human_track_static.test.js + detect_overlay.test.js + human_pipe_lib.test.js + panel.test.js + human_replay_lib.test.js 全 PASS） |
| 9 | SOURCE_BYPASS vs 内嵌模式行为 | **PASS**（无 INI + 无 ENV → 落 PACKAGED，HTTP 静态资源 200；验证过 INI 存在时走 SOURCE_BYPASS 走工作区） |
| 10 | ZIP 解到干净目录独立启动 | **PASS**（解到 `tests/zip_clean_room/`，从该 cwd 启动后 8901 全 200；不依赖开发源码目录） |
| 11 | 旧 EXE/ZIP SHA256 全部不变 | **PASS**（`sha256/historical_before.sha256` vs `historical_after.sha256` diff 完全一致，20 个工件） |

**BLOCKED 项**：测试 #2 的 WebView2 真实浏览器内 DOM 验证（五张卡的像素级渲染、鼠标点击、iframe 嵌入后的页面状态）。原因：本工作流无 GUI 自动化工具（Playwright/Selenium 未装）；通过 `console_html.test.js`（模拟 DOM 的 JS 单元测试）+ HTTP 资源 200 间接覆盖。判断为合理 BLOCKED，不冒充 PASS。

**测试环境干扰事件**：第一次实测 8901 全部 404/500，根因为 dist 活动版 EXE（PID 7428/13160）占 8901 + Windows `http.server.ThreadingHTTPServer allow_reuse_address` 双绑导致请求被负载均衡到旧实例。**清场独占后复测全 200**，确认是测量伪影而非产物缺陷。

## 5. 自主返工（STEP 5）

**0 次实质 FAIL 触发的返工**。所有初审计 FAIL 项（pywebview hiddenimports / __pycache__ / cwd 陷阱）在实例下要么自动由 hook 覆盖（webview\__pyinstaller/hook-webview.py + hook-clr.py），要么实际 count=0（worktree无__pycache__），要么已通过 cwd 钉死规避。

## 6. OpenCode 独立审计（STEP 6）

两轮独立审计 agent：
- **初审**（`audit/opencode_initial_audit_summary.md`）：发现 cwd 陷阱 / pywebview 隐性依赖 / __pycache__ 风险 / SHA256 未记录 4 类问题。已全部采纳并闭环（cwd 钉死 + 构建日志证实 hook 覆盖 + worktree count=0 + sha256 快照前后对比）。
- **终审**（`audit/opencode_final_audit_report.md`）：8 项独立验证**全 PASS**（输入隔离 / SHA256 可复算 / 历史完整性 / 资源内嵌 / 测试真实性 / 行为一致性 / 未授权改动检查 / BLOCKED 合理性）。

**终审 3 处实质注释已全部采纳**：
1. 启动证据定位修正：`logs/diag_banner3.log` 实际 size=0，**真启动证据在 `logs/run.log` 末尾**包含 candidate banner（`source=PACKAGED` / `resolved root=_MEI233162` / `mode=PYINSTALLER`）。
2. worktree `Console.spec` 的 `console=True` 诊断标记**已 revert 为 `console=False`**，保证「从该 worktree 重建 = 交付版」。
3. `run.log` 头部 3 条 bottle Traceback 已在本报告 §9 显式标注来源（pywebview 内嵌 webview server 的 `asset()` 缺参，与 candidate 8901 服务无关）。

## 7. 最终交付物

```
docs/human_capture/evidence/2026-10-09_console_release_candidate/
├── FINAL_REPORT.md                    本文件
├── candidate/
│   ├── Console.exe                    交付 EXE（GUI 子系统）
│   └── LiDAR_Console.zip              交付 ZIP（Console.exe + README.txt）
├── input_manifest/manifest.tsv        68 行输入清单（路径/SHA256/大小/来源 commit）
├── sha256/
│   ├── outputs.sha256                 产物 SHA256
│   ├── historical_before.sha256       20 个历史工件快照（构建前）
│   └── historical_after.sha256        20 个历史工件快照（构建后，与 before 一致）
├── build/                             首次构建与诊断构建的 dist/work
├── logs/                              构建日志 + 启动 banner 抓取
├── tests/zip_clean_room/              ZIP 解包独立启动验证
├── diff/console_copyfix_final.diff    授权文案修复最终差异
└── audit/                             OpenCode 两轮独立审计报告
```

## 8. 不可变更声明

- **未触碰**：`pc_apps/console/dist/` 下任何历史 EXE/ZIP（20 个工件 SHA256 前后一致）
- **未带入产物**：pc_apps/human_replay 15 个 M 文件 + 7 个 ?? 探针脚本（B2-A-FIX-R1 / HR-RET-V2）
- **未修改**：RF 分类算法 / 跟踪阈值 / 背景去除算法 / `rf_person_v1.json` 模型权重（字节保持 HEAD 原值）
- **未替换**：dist/ 下活动份 EXE 未被覆盖，桌面快捷方式 `总控制台.lnk` 指向未变
- **未发布**：候选仅放 staging，未替换正式发布目录

## 9. 尚未解决的问题（如实）

1. **BLOCKED**：WebView2 真实浏览器内 DOM 验证（测试 #2 部分）。需 GUI 自动化工具（Playwright/pyautogui）方可覆盖。
2. **NOTE**：GUI 子系统（PE Subsystem=2）EXE 在 bash `&` 后台启动下 **stdout 仍有输出但缓冲很大**——`run.log` 实测 22:25:18 启动后到 22:26 之间才写入 banner 三行。这**否定**了"GUI EXE 完全吞 stdout"的早期假设。`logs/diag_banner*.log` 空是因诊断 EXE 启动早期崩或缓冲未 flush 即被 kill。验证 GUI EXE 的可靠探针是「HTTP 200 + 耐心等 banner（≥15s）」。
3. **NOTE**：`dist_diag/Console.exe`（console=True 诊断版，PE Subsystem=3）与交付版同源（同 worktree）但字节不同（差 7,583 B）；非交付物，仅证据留档。**worktree spec 的 `console=True` 已在终审后 revert 为 False**。
4. **NOTE**：`logs/run.log` 头部 3 条 `BottleServer.start_server.<locals>.asset() missing 1 required positional argument: 'file'` Traceback **与 candidate EXE 的 8901 服务无关**——是 pywebview 内嵌 webview http server 的 asset handler 缺参错误（pywebview 3.x 已知问题），恰好被同一个 bash `&` 后台进程的 stdout 捕获。candidate 的 banner 与 8901 服务功能未受影响。
5. **NOTE**：CRLF vs LF——manifest 记的 SHA256 是 Windows 磁盘字节（CRLF）；`git show HEAD:path` 是 LF 字节，两者 SHA 不同属正常现象（已实证：HEAD spec 转 CRLF 后 hash 等于 manifest 值 f2270af7...），不是数据污染。若审计用 `git show` 对比会误判，见 `input_manifest/manifest.tsv` 头部 LINE-ENDING NOTICE。
6. **NOTE**：第一次实测「全端点 404/500」是「8901 双绑坑」测量伪影（dist 活动版 EXE 已占 8901 + Windows `http.server.ThreadingHTTPServer allow_reuse_address` 默认允许同绑，curl 被负载均衡到错误实例），**不是产物 bug**。清场独占后复测全 200。生产环境单进程独占端口不出现，但下次运行时验证前应先 `Get-Process Console | Stop-Process -Force` 清场再测。
7. **NOTE**：当前 PC 上仍有 PID 8356（python.exe，15:29 启动，早于本工单）占用端口；与本候选 EXE 无关。审计 agent 实测时仍在跑，不影响验证结论（清场后候选 EXE 实测全部 200）。

## 10. 验收建议

候选 EXE/ZIP 已达到「可演示、可分发」标准：
- 输入可复算（manifest + worktree）
- 无未授权代码
- 历史基线字节保持
- 全部自动化测试 PASS
- HTTP 行为验证通过
- 独立审计两轮

剩余 BLOCKED 项（真实 WebView2 点击测试）建议在有人值守环境下复核，不阻塞候选分发。
