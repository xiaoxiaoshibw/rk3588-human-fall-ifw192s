## 场景验收表 v2（本轮唯一当前表）

| ID | 要求 | 自验结果 / 证据 |
|---|---|---|
| R2-01 | 原源码、隔离补丁、旧 dist 与证据 SHA，备份后集成 | PASS：baseline.json、backup/、integrated-source.patch、final-scope.json |
| R2-02 | 无 sid 默认最新；稳定排序与半成品排除 | PASS：最终 Node 12 组；真实 EXE 两页加载最新；Python 两种本地接口排除 meta-only 等输入 |
| R2-03 | 合法旧 sid 与合法剪辑 sid 保留 | PASS：打包实例旧 203349 两页；安装 dist 的真实 clip 深链；不把缺 meta 的旧固定 sid 当有效样本 |
| R2-04 | 非法/不可用 sid 提示与回退 | PASS：两页真实 EXE 非法深链；Node 缺失/空 sid 回归 |
| R2-05 | 空列表与 API 失败清晰结束 | PASS：通过 localhost 故障代理，仅把列表响应替换为空或 HTTP 503；HTML/JS/其他资产均来自最终 EXE；两页禁用下拉并显示清晰提示 |
| R2-06 | 配平中会话仍可发现，不依赖 TLS 完成 | PASS（入口条件）：在隔离真实数据副本的新 EXE 上 POST 配平，实测 job=running 时本地列表仍包含该 sid；leveling-in-progress.json |
| R2-07 | 真实构建、更新 dist 与测试版产物 | PASS：PyInstaller 最终退出 0；make_release 退出 0；ZIP 内 EXE 与源码 SHA 一致 |
| R2-08 | 新 EXE 真正启动、链接与数据一致 | PASS：compiled GUI 与最终源码的字节码/常量结构相同；14 个静态/源文件 SHA 一致；独占端口、无固定 sid、浏览器真实加载 |
| R2-09 | B2/RF/算法/阈值保护与相关回归 | PASS：16 套集成回归；最终选择 12 组、Console 5 项；冻结资产 SHA 不变 |
| R2-10 | 独立 OpenCode 审核与反馈处理 | PASS（审核执行与闭环记录）：本轮所有审核调用返回；意见、返工、自验与处理依据均保存。未将模型退出码当成无缺陷结论 |
| R2-11 | 原服务、生产原始数据及板端保护 | PASS：原 Python PID 8356 / 8901 始终保留；原始会话输入 SHA 不变；板端零操作；配平产物只写隔离副本目录 |
| R2-12 | 证据、回滚与报告 | PASS：交付目录、仓库 evidence/returns、验收表 SHA 与备份清单 |

R2-05 是明确的故障注入测试，不声称生产目录真的被清空或生产 API 自然返回 503。R2-06 使用软件测试数值 config（pitch=0、roll=0、height=1.0），**不是现场安装角/高度确认**。任务随后 `failed: floor_not_found`，说明这组测试配置未找到假定地面；未修改阈值来制造成功，也不把它称为配平质量通过。它验证 raw 完整会话在 running 状态仍被发现；两页实际解析加载另有 UI 证据，但没有把该 UI 加载时刻称为任务仍处于 running。本轮没有现场识别精度、地面物理校准或板端采集结论。

本地最新有效会话仍为 181716；远端是否有更晚会话未查询，也没有 fetch、重新采集或操作板端状态。旧固定 `cap_20261002_223757` 当前缺 meta.json，无法作为有效显式深链测试输入。

