# OpenCode 初审摘要（工作区/基线审计）

**初审时间**：2026-10-09 工单 STEP 1 期间
**执行**：OpenCode 独立审计 agent（只读）

## 初审结论

| 项 | 初审判定 | 本工单闭环证据 |
|---|---|---|
| cwd 陷阱（spec datas 相对 cwd） | FAIL（潜在） | 构建命令 cwd 钉死在 `worktree/pc_apps/console`，见 `logs/build.log` 起始 |
| pywebview hiddenimports 缺失 | FAIL（潜在） | 构建日志显示 `hook-webview.py`（webview\__pyinstaller）+ `hook-clr.py` 自动处理 |
| human_replay `__pycache__` 被 datas 拷贝 | FAIL（潜在） | `git worktree add` 不展开 gitignored；实测 worktree count=0；grep 构建日志 `.pyc`=0；grep EXE 字节 `__pycache__`=0 |
| 历史 dist/Console.exe SHA256 未记录 | FAIL | `sha256/historical_before.sha256` 20 工件快照，构建前后 diff 完全一致 |

## 初审确认 PASS 项

- 验收边界：15 个 M 文件属 B2-A-FIX-R1/HR-RET-V2；RF 资产 CLEAN-tracked @ HEAD
- 基线 HEAD 完整覆盖 B2a 调用链（human_track.html HEAD blob 引用 rf_person.js + fetch /rf_person_v1.json）
- 授权差异仅 4 个 console 文件
