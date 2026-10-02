# 支线任务汇编 REVIEW / 2026-10-02

范围：主线 GL-03 R2 之外的支线盘点/审查/归档提案。所有任务只读+单文件写入，未 commit/push/reset，未动 `docs/human_fall/` 任何既有文件、未动冻结资产（`config/default.yaml`/`geometry.yaml`）、未动 `src/CMakeLists.txt`（Windows 软链）、未 SSH。

ponytail 强度：full。每一任务先问"要不要做"，答案都是"修根因/补证据"而非新增框架。

---

## 总表

| ID | 任务 | 产物 | 状态 | 关键结论（详见对应文件） |
|---|---|---|---|---|
| T1 | 无板离线回放链路盘点 | [T1_replay_boundary.md](T1_replay_boundary.md) | ✅ | 链路大部分闭合；缺素材不缺工具；不补 bag→npz、不补 preview 离线模式 |
| T2 | publish_manager.cpp 用户 diff 最终审查 | [T2_driver_diff_review.md](T2_driver_diff_review.md) | ✅ | diff = HF-02 R2 最终态已验收修复；sha256 `1b3d5793…b787`（非 R1 `b9c4e706…`）；可随 HF-02 批入库；ROS2 NOT_RUN 在 body 注明 |
| T3 | 跌倒文献补 Lai 2026 | `文档/跌倒检测文献/README.md` + `manifest.json` 修订 | ✅ | CrossRef 元数据核实（J Biomech 202:113292）；Unpaywall `hybrid` OA / CC BY 4.0；无 API key 时 sciencedirect/api.elsevier 全 403/406，PDF 仍需人工/机构获取 |
| T4 | 10-1 数据集调研 README 补强 | [T4_dataset_survey.md](T4_dataset_survey.md) + `文档/10-1/数据集调研/README.md` 追加段 | ✅ | 6 篇数据集论文均不可直接用作本项目训练/评测集（LiveHPS/SLOPER4D 真值靠多 RGB+穿戴 IMU；LidarGait 是室外步态正交任务；MM-Fi 无跌倒类）；建议自采为主、借点数-距离先验校阈值 |
| T5 | open_webui.bat 运维通道盘点 | [T5_webui_ops.md](T5_webui_ops.md) | ✅ | bat 明文 `wel@192.168.3.125` 命中 ssh config `Host ldiar-wel 192.168.3.125`（双 pattern 同密钥），无认证漂移；与 slam-localization 容器常驻 8090/8765 兜底一致不冲突；板端 SSH 超时 → 通道 NOW BLOCKED（非配置错误） |
| T6 | 仓库卫生与分批入库提案 | [T6_repo_hygiene.md](T6_repo_hygiene.md) | ✅ | 根无 `.gitignore`，仅 `.git/info/exclude:/captures/`；`git add -A` 会吞 160M+（`文档/` 125M、`docs/evidence` 37M），提案 3 类底线规则 |

## 更正与核实（我手动复核，非 agent 原文转述）

1. **`文档/` 体量**：T2 复盘点时按"~55M"估算，T6 实测 **125M**（`du -sh`）。6 个 >5M 文件全在 `文档/`，最大 LiveHPS 数据集论文 38M（未入库、`文档/10-1/github/` 克隆占了 25M+）。
2. **gitignore 现状**：根 `.gitignore` 不存在；唯一生效规则是 `.git/info/exclude: /captures/`（`git check-ignore -v` 实测）。PDF/pyc/证据 jsonl 此前全无兜底，存在 `git add -A` 灾难风险。
3. **captures/ 与 returns/ 顶层**：`captures/` 在本地工作区**不存在**（CLAUDE.md 中"用于离线测试"是规划非现状）；根 `returns/` 是空目录，真实回传在 `docs/human_fall/returns/`。HF-02.md 开工快照 () 里 `captures/` 同样未列出。
4. **driver diff 归因升级**：T2 用 sha256 证实当前 `publish_manager.cpp` 是 HF-02 **R2** 最终态（非 R1），与 returns/HF-02.md 里 R1 记录的哈希属中间态——差异是 R2 返工产生的；diff 内容仅为行尾/哈希级，语义审查一致。
5. **driver 语法分支**：diff 第 4 hunk 删 `;ros_msg` 的位置位于 `#elif defined(POINT_TYPE_SOURCE)` 点循环，板上实测 `POINT_TYPE=XYZI_TIME` 不走该分支，属代码卫生/HEAD 语法修复，不改变板端行为。
6. **IMU 时间戳矛盾仍保留**：SDK `imu_types.hpp` 注释纳秒 vs 发布端按秒解释，本 diff 明确**不改单位**（与 CLAUDE.md 警告一致），仓储事实不变。

## 已落地的最小动作（在授权内）

- 新建 `D:\Code\ldiar\.gitignore`：只挡 `__pycache__/`、`*.pyc`、`文档/10-1/github/`、`/captures/`+`*.bag`/`*.pcap`/`*.db3`。**没**采纳 `*.pdf`——会挡死文献归档且不能覆盖已入库 PDF。
- `git add` 批量暂存（未 commit、未 push）：支线产物 + 文献修订 + driver diff + human_follow_calibration + webui + docs + 文档，共千余文件、+15.7万行；唯一 `M` = `publish_manager.cpp`；`src/CMakeLists.txt` 经 pathspec `:(exclude)` 排除；`git diff --cached --name-only | grep` 复核无禁项。
  - **边界更正**：`src/human_fall_detection/`（GL-03 主线包，R1/R2 CLI 正在写入）**不暂存**，已用 `git restore --staged` 撤销——它属于 Codex 主线工单，归档由主线验收后处理，磁盘代码未动。
- 文献 README/manifest 用 Edit 按事实定点修订（CrossRef/Unpaywall/443 实测），未重写已有条目。

## 阻塞与外部依赖

- 板端 192.168.3.125:22 SSH **现在超时**（`BatchMode=yes, ConnectTimeout=5` exit 255，9:00 与 14:00 两次复核一致）。所以：
  - T5 通道"启动板端 8090/8765"现在不能用（bat 兜底路径也死）——属网络/板端状态而非配置问题。
  - T1 缺的 `captures/*.pcap|*.bag` 素材拿不到，bag→npz 转换器现在写是无输入臆测。
  - GL-03 R2 的 D01/真机复审同步 BLOCKED。
- 板端恢复后一次性解锁：open_webui.bat 直接可用；按 CLAUDE.md `deploy_human_fall.sh` 部署；把真 bag 取回触发 T1 回放链路。

## 主线 GL-03 R2 观察（未接管写入；供 Codex 入口）

- 主线 CLI（OpenCode `deepseek-v4.1-flash`, `ses_f050597efffec…`）已在 `docs/human_fall/evidence/2026-10-02_gl03_r2/` 完成 R2 修复：根因覆盖 G03 资格门控（`build_snapshot` 旧高度链 + `node._ground_valid` 的 source-frame 资格）与 O01 诊断方法（z 统计带→按候选 n/d 的显式 `abs(n·p+d)<=0.05` 成员/连接消融）。
- R2 独立 9 方法、GL03 28/28、fall 全套 **全 PASS、无 FAIL/exit1**；CLI 日志以 *"Now run the full suite again"* 结束，**returns/GL-03.md 尚未追加 R2 块**——仍处 R1 状态。
- 因此 GL-03 R2 当前 = 修复完成且已自验、**尚未正式 SUBMITTED**。建议 Codex 直接接手，用 R2 evidence 里的 `11_codex_r2_checks.txt`（9 方法 PASS）+ `12_gl03_suite.txt` 复跑后立即出 R2 评审，不要再发返工。

## 给用户的决策入口（均无默认授权）

1. `.gitignore` 上述最小集是否接受；如还有要加（比如 `*.ipynb checkpoint`），告诉我。
2. 当前 1111 文件暂存是否保留、拆批、还是补一个起手 `commit`（msg 由你定、我不 push）。
3. 是否把 R2 催收给 Codex（只给入口提示，不发起派工）。

—— 以上即汇编。支线内无一处为了过审而修改冻结资产、contract 或 driver 语义。
