# HFUS-TCMS-02-REALDEV-02-S02

## 本轮信息

- 工单/轮次/执行者/时间：HFUS-TCMS-02-REALDEV-02-S02 / r1 / 本会话 DSH agent（唯一实现 writer）/ 2026-10-17 20:05–20:40。
- 唯一验收：docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1/ACCEPTANCE_V1.md，SHA `9f18c0d4261f7a8a075d3f327897eea42e939b8a7a0ee6e8b6ea6564aab50caf`；协议 v4 SHA `3a9a78c6c734e8a214cb4b0caa5c1378ced57136f2d90f724e13073776ba10fc`。
- 执行方式/模型：本机 PowerShell、Python 3.12.10 / NumPy 1.26.4 / psutil 7.2.2、Node 24.14、真实 Edge 155 headless（CDP 鼠标事件）；模型按环境声明为 deepseek-flash，精确运行 ID 不可得，未切模型。
- 策略：RESEARCH=地面审核、距离图、候选平面；ENGINEERING=源绑定、输出护栏、回放/浏览器。
- 状态：**SUBMITTED，非 ACCEPTED，源码停写**。正式独立复审 NOT_RUN。
- 起始 branch/HEAD：master / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a`（由 BASELINE_GIT 记录），工作树原脏状态保留；34,271 文件逐 SHA 基线与最终保护见 PRESERVATION_SUMMARY。
- 页面：http://127.0.0.1:49689/?fi=0（只读 loopback 服务当前运行；重启后端口以 server.stdout 为准）。
- 实际 ponytail 路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`；scientific-toolkit：`C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 入口/消费者 | 修复/证据 | 保留行为 |
|---|---|---|---|---|
| G03 audit domain v1–v3 | 先在 u/v 矩形取全高度点，混入墙/家具；随后仍保留 v<0、u>2.2 污染片 | run.py 片统计、门 | v4 薄层 + 纯度 >0.9 核心；v1–v3 全部保留 | 旧失败 probe 不覆盖；选择偏差登记 |
| G04 旧先验与候选混同 | 旧 TLS 与本段平面接近但非同一 | CANDIDATES/VALIDATION | 旧先验单列 OLD_TLS，按同一门评估；VAL 2/3 失败 | 不宣布旧标定失效，不提升身份 |
| G02 距离图稀疏 | 1024×512 角分辨率细于单帧点间距 | DISTANCE_STATS、页面 | 同时报 1024×512 与 512×256，洞=UNKNOWN | 不插值、不当遮挡 |
| G11 点击与版本 | 视口过小、rect 与 clientWidth 差 1px、下采样 bin 空 | 页面点击/反查 | 1400×1000 viewport、rect 映射、±2 bin 吸附 | 真实鼠标事件；失败轮保留记录 |

## 实际变更

新增源码目录 `sidequests/hfus_tcms_02/realdev/r03/`（全部新文件，SHA 见 `SOURCE_SHA.json`）：`s2core.py`、`distance.py`、`planes.py`、`run.py`、`audit.py`–`audit4.py`、`bootstrap.py`、`baseline.py`、`preserve.py`、`report_data.py`、`resolution_compare.py`、`server.py`、`index.html`、`app.js`、`test_s2.py`、`browser_check.js`、`recon*.py`、`patch_count.py`、`purity_map.py`、`inspect_patches.py` 及诊断脚本。

新增证据目录 `docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s02_r1/`：协议 v1–v4、唯一验收、审核域 v1–v4、probe_r3–r7、full_r1、浏览器截图/结果、报告、命令记录、清单/封印。

旧 r01/r02、旧证据、生产源码、配置、模型、GT、data 全部只读；未做 Git 写、未部署/采集/训练。用户原有未提交差异保留。

## 逐条验收（S2 适用子集）

| ID | 作者自验 | 覆盖与边界 | 证据 |
|---|---|---|---|
| G01 | PASS（附注） | 源双 SHA 重核一致；data 零写；输出排他；旧资产只读；34,269/34,271 逐字节一致；WORKFLOW/REVIEW 两个追加面内容保留但 247/815 个历史 CRLF 行尾被归一化 | SOURCE_CHECK.json、BASELINE_FILES.jsonl、PRESERVATION_FINAL_SUMMARY.json |
| G02 | PASS | 1024×512 与 512×256、接缝/洞/碰撞、CSR 7,181,833 行、bin 点击反查 | DISTANCE_STATS.json、DISTANCE_RESOLUTION_COMPARISON.json、test_s2.py、BROWSER_RESULTS.json |
| G03 | PASS（限制：先验条件选片） | FIT/VAL 运行前冻结、空间分离、薄层 ±0.15m、纯度 91.9–99.7%、VAL 未参与拟合 | AUDIT_DOMAINS_V4.json、REPORT_DATA.json、run.py |
| G04 | PASS（限制：VAL 非独立真值） | C/D 两族提案、旧先验单列、FIT-only 排名、预登记门、失败保留 | PROPOSALS.json、CANDIDATES.json、VALIDATION.json |
| G10 | PASS | FIT 全 7,181,833 行入 CSR；50.04s / 峰值 0.95GiB / 输出 20.2MB；无标签指标不产出 | SUMMARY.json、DISTANCE_STATS.json |
| G11 | PASS（S2 范围） | 真实 Edge 6 帧：距离图/3D 同帧、点选 28B/双 XYZ、bin 反查、相机不变 | BROWSER_RESULTS.json、browser_f*.png |
| G12 | PASS | 命令/退出码/失败、源码/协议/输出 SHA、回传与独审交接；正式独审 NOT_RUN | COMMAND_RECORDS.md、MANIFEST.json、FINAL_SEAL.json |

回归：r03 9/9 合成契约；r02 14 项坐标契约 + 迟到/错版本 handler 契约 exit 0；旧 PREDEV/REALDEV 未改动、未重跑（本轮未触碰其代码路径，标 NOT_RUN 而非 PASS）。Python 全部 `-B -W error`。

## 关键结果

- **C3D_03**：FIT 4/4、VAL 3/3；VAL RMS 1.00/0.77/2.52cm，P95 1.99/1.53/3.12cm，支持率 1.000/1.000/0.960。
- **DIMG_01**：FIT 3/4、VAL 3/3；VAL RMS 1.07/0.77/2.59cm。
- 跨族：0.84° / 2.77cm，无冲突。
- **OLD_TLS**：FIT 2/4、VAL 1/3；对 C3D_03 方向差 1.82°、|d| 差 1.95cm；VAL_F/G RMS 3.89/3.90cm 超 3cm 门。
- 时序：VAL 78/78 帧、前缀 19/19 帧三片全 PASS。
- 距离图：37,700/524,288 占用（洞 92.81%），聚合 190.5 行/bin；单帧每 bin 至多 1 行。

## 未闭合与限制

- 审核片是**先验条件选择**；VAL 是空间留出但不是独立 D。地面身份仍 BLOCKED，不能升级 GEOMETRY_VALIDATED_LOCAL，不能据此报告物理高度或近地硬删。
- 旧先验 FAIL 只说明“不满足本轮 3cm 门”，不等于旧标定失效；也不能反向证明新候选就是真实地面。
- 距离图洞不是遮挡结论；无射线自由空间模型。
- S3/S4、人体返工、独立 D、设备/部署/采集/训练/HR09 均未授权；正式独立复审 NOT_RUN。
- 旧 PREDEV/REALDEV 套件未重跑（未受影响），不把“未跑”写成 PASS。
- 自身缺陷：追加 WORKFLOW/REVIEW 时文本模式把 247/815 个原 CRLF 行尾归一化为 LF；内容保留、非数据文件，但不再逐字节一致。已在 PRESERVATION_FINAL_SUMMARY 与 COMMAND_RECORDS 披露，未掩盖。

## 交给 Codex 独立复审

- 现行验收/协议/报告/审核域：ACCEPTANCE_V1、PROTOCOL_V4、REPORT、AUDIT_DOMAINS_V4、REPORT_DATA。
- 源码差异与 SHA：SOURCE_SHA.json、MANIFEST.json、FINAL_SEAL。
- 原始日志：probe_r3–r7、full_r1、server、浏览器、COMMAND_RECORDS。
- 下一步仅独审；本轮停止，不自动 S3/S4。
