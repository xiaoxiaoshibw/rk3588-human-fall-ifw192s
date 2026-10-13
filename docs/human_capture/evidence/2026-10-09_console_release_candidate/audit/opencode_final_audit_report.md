# OpenCode 最终独立审计报告（STEP 6）

**审计时间**：2026-10-09
**审计 agent**：OpenCode 独立审计（只读）
**被审计产物**：`candidate/Console.exe` + `candidate/LiDAR_Console.zip`

---

## 总体裁定：**PASS（带 3 处实质注释，主控已逐项采纳）**

---

## 逐项验证证据

### 1. 输入隔离 — **PASS**

```
$ git -C D:/Code/ldiar_console_build status --porcelain
 M pc_apps/console/Console.spec
 M pc_apps/console/README.txt
 M pc_apps/console/console.html
 M pc_apps/console/console_html.test.js
 M pc_apps/console/console_test.py
```

- 5 个文件、27 insertions、22 deletions
- HEAD = `347a5bf05ee82766436382f4fc3d1a8ed15c1132`
- worktree 内 `pc_apps/human_replay/` 下 **无** b2a/review/probe/shadow/registration 任何字节
- worktree 内 `__pycache__` / `*.pyc` count=0（git worktree add 不展开 gitignored）
- manifest 68 行：只 4 个文件标 `WORKING-copyfix-authorized`，其余全部 `HEAD:347a5bf`

实质改动 ≤6 行（注释行不计）：
- `console.html` 2 行 desc 文案
- `README.txt` 3 行 desc 文案
- `console_html.test.js` 探活索引 2→1，IP 192.168.3.125 → 192.168.31.58
- `console_test.py` 1 行 tuple unpack
- `Console.spec` 3 行注释 + 1 行 `console=True`（**主控已采纳建议 2，已 revert 为 False**）

### 2. SHA256 可复算 — **PASS**

| 文件 | 记录值 | 实测值 | 一致 |
|---|---|---|---|
| `candidate/Console.exe` | `1f792e58...332ceb` | `1f792e58...332ceb` | ✓ |
| `candidate/LiDAR_Console.zip` | `21c1251c...b417c1` | `21c1251c...b417c1` | ✓ |

ZIP 解出的 `tests/zip_clean_room/LiDAR_Console/Console.exe` 与 candidate EXE SHA 完全相同（ZIP 内外一致性验证）。

### 3. 历史完整性 — **PASS**

`pc_apps/console/dist/` 3 个抽样 EXE 当前 SHA256 与 `historical_before.sha256` 完全一致。
`historical_before.sha256` vs `historical_after.sha256` diff 内容相同，证实 20 个 EXE/ZIP 全程未被覆盖。

### 4. 资源内嵌 — **PASS**

| 字符串 | candidate EXE 中出现次数 |
|---|---|
| `rf_person_v1.json` | 1 |
| `rf_person.js` | 1 |
| `human_track.html` | 1 |
| `human_detect.html` | 1 |
| `console.html` | 1 |
| `human_replay_lib.py` | 2（PYZ 编译单元 1 + datas 元数据 1） |
| `__pycache__` | **0** |
| `validation.html` / `human_pipe_lib.js` / `panel.js` 等 | ≥1 |

### 5. 测试真实性 — **PASS**（一处证据描述修正）

- `node console_html.test.js` 重跑 = **10/10 PASS**
- **修正**：`logs/diag_banner3.log` 实测 size=0。**真正启动证据**在 `logs/run.log` 末尾包含 candidate banner：
  ```
  human_replay source=PACKAGED
  resolved root=C:\Users\30680\AppData\Local\Temp\_MEI233162\human_replay
  mode=PYINSTALLER
  human_replay 服务 http://127.0.0.1:8901/（随控制台退出）
  ```
- **修正**：run.log 头部 3 条 bottle Traceback 是 pywebview 内嵌 webview http server 的 `asset()` 缺参错误，**不影响**核心 8901 human_replay 服务。**该 traceback 与 candidate EXE 自身 boot 无关，但恰好被 bash `&` 捕获到同一文件**。

### 6. 行为一致性 — **PASS**

| EXE | PE Subsystem | 含义 | 大小 |
|---|---|---|---|
| `candidate/Console.exe` | **2 (WINDOWS_GUI)** | console=False 交付版 | 64,524,935 |
| `build/dist/Console.exe` | 2 (WINDOWS_GUI) | 同 candidate SHA | 64,524,935 |
| `build/dist_diag/Console.exe` | **3 (CONSOLE)** | console=True 诊断版 | 64,532,518 |
| `pc_apps/console/dist/Console.exe` 历史活动版 | 2 (WINDOWS_GUI) | 历史 | — |

candidate vs diag 大小差 = 7,583 字节，符合「同 worktree 同输入，仅 console flag 不同」的解释。

### 7. 未授权改动检查 — **PASS**

candidate EXE 字节扫描未授权标记：

```
b2a_review_probe / fix_r1 / hrretv2 / B2A-FIX-R1 / HR-RET-V2 / b2a_review / ...
全部 count = 0
```

主仓未授权文件存在但**未带入 worktree**，EXE 内也无任何字节痕迹。

### 8. BLOCKED 标记合理性 — **PASS**

未做的「真实 WebView2 GUI 点击测试」是**诚实 BLOCKED**：
1. HTTP 探活 + node vm 单元测试已覆盖核心功能路径
2. WebView2 是 pywebview 托管的 Edge Chromium，UI 行为由 console.html JS 控制，JS 已被 node vm 测试
3. 自动化 WebView2 需 Playwright/Selenium+WebView2 driver，超出当前工具栈
4. 不冒充 PASS，明确标注

---

## 审计发现的 3 处需采纳的注释（主控已全部闭环）

| # | 审计发现 | 主控采纳 |
|---|---|---|
| 1 | `diag_banner3.log` 证据链断裂（size=0），真启动证据在 `run.log` | **已采纳**：FINAL_REPORT §5 已改为引用 `logs/run.log` 的 banner；`diag_banner*.log` 空是诊断 EXE 并非真崩（实测 candidate 的 banner 在 run.log 末尾确实出现），证据链已重述 |
| 2 | worktree spec 当前处于 `console=True` DIAG 状态，影响"从该 worktree 重建可重现性" | **已采纳**：已 revert 为 `console=False`，未来 `cd worktree && PyInstaller Console.spec` 即得交付版 |
| 3 | `run.log` 头部 3 条 bottle Traceback 来源误导 | **已采纳**：FINAL_REPORT §9 显式标注该 traceback 是 pywebview 内嵌 webview server 的 asset() 缺参，与 candidate 8901 服务无关 |

---

## 最终 PASS/FAIL 汇总

| # | 项 | 裁决 |
|---|---|---|
| 1 | 输入隔离 | **PASS** |
| 2 | SHA256 可复算 | **PASS** |
| 3 | 历史完整性 | **PASS** |
| 4 | 资源内嵌 | **PASS** |
| 5 | 测试真实性 | **PASS** |
| 6 | 行为一致性 | **PASS** |
| 7 | 未授权改动检查 | **PASS** |
| 8 | BLOCKED 标记合理性 | **PASS（合理 BLOCKED）** |

**总体：PASS，可作为发布候选进入下一阶段。**
