# HFUS-TCMS-02-REALDEV-02-S03 回传（本段几何配平）

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：HFUS-TCMS-02-REALDEV-02-S03 / r1 / 本会话 DSH agent（唯一实现 writer）/ 2026-10-17 20:55–21:40 (+08:00)。
- 验收表路径 / 版本 / SHA：`docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1/ACCEPTANCE_V1.md` v1 / `7672c20a8da998257c709be5136f1e0e9b634bf7a6beb2286b2511bd068fcc2f`。
- 执行方式 / 实际会话与模型：本机离线单会话、单一 writer；模型按运行环境声明为 deepseek-flash，精确运行 ID 不可得，未切换模型。
- 状态：**SUBMITTED**（作者自验 G05/G06/G07/G10/G11/G12 PASS，G08/G09 NOT_RUN；正式独立复审 NOT_RUN）。软件自验通过不构成 ACCEPTED；设备/物理/地面身份/独立 D/人体效果仍 BLOCKED/NOT_RUN。
- 起始 branch / HEAD / 工作树 / 范围外用户差异：`master` / `c9c4ee421cb0c8a3e4590b8f5730828b093c759a` / 树本就 dirty（`git status` 24,889 行）/ 本轮 34,408 个 tracked+untracked 文件逐字节复核 **差异 0**（`PRESERVATION.json`），`data/` 只读且前后 SHA 一致。
- ponytail SKILL.md 实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`（同时按需读取 `C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md`）。
- 策略：ENGINEERING（坐标接线、M0 重建、回放、浏览器）+ RESEARCH（新验证域与失败解释）；本轮不新求解地面平面。

## 集中诊断与根因覆盖

| 缺陷/验收ID | 根因 | 受影响入口、消费者与状态转换 | 修复位置 | 保留行为 |
|---|---|---|---|---|
| G10/时间门自验（C14） | `frames_all_pass` 对 `{片: {帧: 统计}}` 按片迭代，等于统计“有多少片全帧通过”而不是“多少帧三片全通过” | `run.py` 的 271 前资格判定与 `online_state`；会把 3/78 当成时间通过率 | `run.py` 改为按帧透视（`frames_all_pass`/`frame_pass`） | `RUN_BUG1/` 原样保留（qualified=false），修正后新目录 `RUN/` |
| G06.1 支持 CSR（C17） | 把 `support_global`（全局源行）误当 surface id 做范围检查 | `objects.py` 的同系自检 | 改为 `indptr` 单调 + `indptr[-1]==len(support)` + 行号落在源总行数 | `OBJECTS_CHECK_FAIL1.json` 保留 |
| G07.1 域不重叠（C10） | 域行存的是帧内行号而非全局行号，跨片比对产生假重叠/假不重叠 | 域冻结、与 S2 的源行互斥判定 | `domains.py` 同时写全局行与局部行，互斥检查用全局行 | 首次失败已记录，npz 在修正后写出并由 resume 分支逐数组核对 |
| G11 双视图同源行（C24–C27） | 真实鼠标事件坐标被量化到整数像素，密集点区 1 px 抖动会选到相邻行；RAW 视图定心与共享尺度不一致 | 页面拾取与双视图对照 | 页面 `pickIndex` 要求两视图内均最近且 ≥3 px 分离；两视图各自定心、共享 m/px | `BROWSER_RESULTS_ATTEMPT1/2/3` + `diag_pick.json` 保留 |
| T0 登记（C01） | `ROOT=HERE.parents[4]` 多退一层 | 所有路径常量 | `s3core.py` 改为 `parents[3]` | 首轮失败无文件写出 |

语义变化记录：协议 v1→v2 **只**改域选择约束（0.05 m 间隙 → 精确不重叠 + 0.1 m 锚点 + 纯度 0.85 下限/0.9 目标），原因是 FIT-only 探针证明 0.05 m 间隙下不存在可用的高纯度格；**验证门、M0 参数、应用链参数一律未改**，且修订发生在任何域冻结与任何真实 M0/回放之前。v1 只用于登记与基线。

## 实际变更

| 文件 | 本轮用途与修改 | 与用户原差异的区分 | 提交源码SHA |
|---|---|---|---|
| `sidequests/hfus_tcms_02/realdev/r04/s3core.py` | 新工单根、严格源绑定、排他写、r01 纯函数装载 | 全新目录，不改 r01/r02/r03 | `3953ada1…6522` |
| `…/r04/transform.py` | C3D_03 → `S3_LOCAL` 变换构造、`Transform` 适配器、守恒/拒绝检查 | 新增 | `6d08d4f3…2587` |
| `…/r04/domains.py` | FIT-only 先验条件域选择与冻结 | 新增 | `651f3131…4e7c` |
| `…/r04/build_m0.py` | 新坐标 FIT-only M0（0.05 主 / 0.13 敏感性） | 新增 | `6740cc4f…6ba09` |
| `…/r04/run.py` | 780 帧应用链重跑 + 新域验证 + 因果状态 | 新增 | `2a553f2a…e10` |
| `…/r04/qualify.py` | 单独写几何资格记录，R/t 不变 | 新增 | `d159494c…de4f` |
| `…/r04/objects.py` | 对象同系/CSR/框/合成适配器检查 | 新增 | `c39f80e1…6db5` |
| `…/r04/server.py`、`index.html`、`app.js`、`browser_check.js`、`diag_pick.js` | 只读同帧双视图页面与真实 Edge 检查 | 新增 | `407cc992…ccc2`、`df7f257a…2703`、`adc92338…e4`、`2027f9a9…941e`、`50324930…f593` |
| `…/r04/bootstrap.py`、`revise_protocol.py`、`append_docs.py`、`preserve.py`、`seal.py`、`tests/test_s3.py` | 登记/协议修订/二进制 LF 追加/基线复核/封存/单测 | 新增 | 见 `FINAL_SEAL.json` 的 `source_code` |
| `docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1/**` | 协议、验收、变换、域、M0、逐帧日志、验证、对象、浏览器、失败保留、报告、交接、MANIFEST/SEAL | 全新证据目录，不覆盖任何旧证据 | 见 `MANIFEST.json` |

输入输出、单位/坐标：输入 RAW/innolidar（米，设备未锚定）；输出一次 `S3_LOCAL/f0533fd8…ab8d`；无效/零点只保留原值不参与变换；24 位尾字节全段 opaque。阈值：r01 `DEFAULTS` 原样（0.13 m 分量体素、0.26 m 邻域、1.25 m 关联、0.5 m 生长、2.4 m 范围、0.7 s TTL、min_points 3、max_gap 2 s），M0 0.05 m/tau 0.08/≥20 观测/≥5 帧/≥1.0 s。未授权不 commit/push/reset。

## 逐条验收

| 验收ID / 入口或转换 | synthetic/offline/device | 实际命令或源码审查位置 | PASS/FAIL/NOT_RUN/BLOCKED及退出码 | 日志/样本与对应源SHA |
|---|---|---|---|---|
| G05.1 变换由 C3D_03 唯一确定、artifact 字段齐全 | offline | `transform.py` build/check；`TRANSFORM_S3.json` | PASS（`transform.py check` exit 0） | `TRANSFORM/TRANSFORM_S3.json` `8699429b…e3de`；CANDIDATES `04219a3c…5673` |
| G05.2 正交/det/往返/float32 | offline | `TRANSFORM_CHECK`、`TRANSFORM_RECHECK` | PASS（2.2e-16 / 1.0 / 6.5e-15 m / 1.06e-6 m；recheck matches=true） | `TRANSFORM_CHECK.json` `7f68eb74…c592` |
| G05.3 z=n·p+d 恒等 | offline | 同上 | PASS（3.6e-15 m，0 行越界） | 同上 |
| G05.4 无效/零点保留原位与 28B | offline + browser | `check_points` 9 帧 + `/api/point` | PASS（`invalid_bytes_identical=true`；fi=0 row=0 返回原 28B 与 [0,0,0]） | `TRANSFORM_CHECK`、`BROWSER_RESULTS` `3378fa4f…2080` |
| G05.5 六类拒绝 | synthetic | `tests/test_s3.py::test_rejects` | PASS（13 tests exit 0） | `COMMAND_RECORDS.md` C21 |
| G06.1 点/M0/候选同系，M0 只用 FIT 行 | offline | `M0.json`、`OBJECTS_CHECK.json` | PASS（支持行 7,181,833 = FIT 有效行；面中心=支持行均值 ≤1e-9 m） | `M0/M0.json` `9bb0f111…1c41` |
| G06.2 速度/协方差/八角框；真实缺失 NOT_RUN | synthetic | `tests/test_s3.py`、`OBJECTS_CHECK.json` | PASS（合成）；真实速度/协方差 **NOT_RUN** | 同上 |
| G06.3 版本变更即新 run、不复用身份 | offline | `frames.jsonl` track 全 `UNCONFIRMED`、0 reset | PASS | `RUN/frames.jsonl` `6997ff36…3411` |
| G06.4 因果 0–192/193–270/271、离线预览分字段 | offline + browser | `RUN/VERIFICATION.json`、`/api/state`、页面 | PASS（qualified 首真 fi=271；状态计数 193/78/509） | `VERIFICATION.json` `b8f6b82f…c7dd` |
| G06.5 原阈值原样、不调用 r01 写入口 | offline | `run.py`、`CODE_AT_START.json` | PASS（`DEFAULTS` 未改；写入口替换为本项排他写） | `RUN/CODE_AT_START.json` |
| G07.1 新域与 S2 七片零重叠 | offline | `S3_DOMAINS.json` `s2_row_overlap`、几何 0.02 m 边界采样 | PASS | `DOMAINS/S3_DOMAINS.json` `8cdceb00…4c81` |
| G07.2 只用 FIT、历史先验纯度、无候选自筛 | offline | `domains.py`、`S3_DOMAINS.json` 的 `selection_data/selection_bias` | PASS（第三片 0.8950 已如实登记） | 同上 |
| G07.3 空间门 3/3 | offline | `VERIFICATION.spatial` | PASS（RMS 2.19/1.86/1.83 cm；P95 4.01/1.89/2.99；支持 98.9/97.3/98.7%） | `VERIFICATION.json` |
| G07.4 时间 78/78 + 前缀 19/19 | offline | `VERIFICATION.temporal/prefix` | PASS（100% / 100%） | 同上 |
| G07.5 271 起 GEOMETRY_VALIDATED_LOCAL；失败包机制 | offline | `VERIFICATION.state_from_271`、`TRANSFORM_QUALIFICATION.json` | PASS（本轮无失败门，未生成失败包） | `TRANSFORM_QUALIFICATION.json` `c2c15591…67f4` |
| G07.6 噪声参照、分层 flags | offline | `VERIFICATION.noise_reference`、`ground` | PASS（σ 0.6–0.8 mm；identity/physical/runtime=false） | 同上 |
| G10.1 780 帧分母/守恒 | offline | `FRAME_CONSERVATION.json` | PASS（38,298,918 / 29,049,839 / 9,249,079） | `RUN/FRAME_CONSERVATION.json` `480855bd…ab92` |
| G10.2 预算 | offline | `PERFORMANCE.json` | PASS（122.1 s / 1.17 GiB / 226 MiB ≤ 2400 s / 2 GiB / 3 GiB） | `PERFORMANCE.json` `fa74f97e…fae6` |
| G10.3 任意行（含无效）源查询 | offline + browser | `/api/point`、页面按钮 | PASS（56 hex + 双 XYZ + source_row + 源 SHA） | `BROWSER_RESULTS.json` |
| G10.4 无标签指标 null | offline | `RUN/EVALUATION.json` | PASS | 同上 |
| G11.1 真实 Edge 同帧双视图/版本/状态 | device(browser) | `browser_check.js`（CDP 1500×1100，真实鼠标） | PASS（Edg/155.0.4283.62） | `BROWSER_RESULTS.json` + 13 PNG |
| G11.2 13 帧状态与 M0 可用时刻 | device(browser) | 同上 | PASS（0/192 RAW → 193/270 预览 → 271+ 验证） | 同上 |
| G11.3 点选 56 hex/双 XYZ/相机不变/无效行 | device(browser) | 同上 | PASS（13/13 两视图同源行；camera_invariant_all=true） | 同上 |
| G12.1 源码/协议/输出 SHA | offline | `MANIFEST.json`、`FINAL_SEAL.json` | PASS | `FINAL_SEAL.sha256` |
| G12.2 命令/退出码/失败；范围外差异 0 | offline | `COMMAND_RECORDS.md`、`PRESERVATION.json` | PASS（34,408 文件 0 变化） | `PRESERVATION.json` |
| G12.3 回传 + 二进制 LF 追加 | offline | `append_docs.py`、`DOCUMENT_APPEND.json` | PASS（原字节作为后缀/前缀完整保留，CRLF=0） | `DOCUMENT_APPEND.json` |
| G12.4 自验/只读助手/正式独审分开 | — | 本回传 + `HANDOFF.md` | 自验 PASS；只读助手无（本轮未派）；正式独审 **NOT_RUN** | `HANDOFF.md` |
| G08 / G09 | — | — | **NOT_RUN**（留 S4） | — |

回归与契约：`python -B -W error -m unittest discover -s sidequests/hfus_tcms_02/realdev/r04/tests -p "test_s3.py"` → 13 tests OK (exit 0)；`transform.py check` → exit 0（重算与冻结检查一致）；`run.py` → exit 0（122.1 s）；`objects.py` → exit 0。失败与返工全部保留（见 `COMMAND_RECORDS.md` §2）。旧证据/旧门/配置/模型/GT/data 未被写入。

## 未闭合与限制

- 未满足的验收 ID：G08、G09（NOT_RUN，留 S4：人体/尾段返工、A/B/C/D 公平比较与 GT 指标）。
- 契约允许的算法/证据限制：
  - 全段 development_seen/dev-tainted；S2 的 VAL 已曝光；S3 新域仍是**先验条件选择**，不是独立真值，**不称独立验证**；无独立 D。
  - 第三片 S3V_J 纯度 0.8950 < 0.9 目标（S2 七片已占满 >0.9 核心，0.4×0.4 m 且不重叠的高纯度片最多 2 个）；本轮未据此移动任何门。
  - 前缀降级路径（前缀失败→271 起撤销）由 v2 规则覆盖，但本轮 19/19 通过，**无实例**。
  - 速度/完整协方差的真实资产不存在 → NOT_RUN，只用合成适配器。
  - 页面/服务只在本机 loopback 只读预览（`http://127.0.0.1:49721/`，pid 42664）；不是生产/在线资格。
- 范围外新需求及后续建议：S4（f430–439 与尾段逐级漏点、近地/接触保留、A/B/C/D 与消融）、S5（全段交付与正式独审）须另行派发。
- 设备/物理未跑项：设备读数、物理安装高度/外参、采集/部署/训练/HR09/驱动/网络全部 NOT_RUN。

## 交给 Codex 独立复审

- 现行验收表与本轮变更记录：`ACCEPTANCE_V1.md`（`7672c20a…fc2f`）、`PROTOCOL_V1`→`PROTOCOL_V2`（`76f9bf88…f8101` → `4c6550ae…e14`）、本回传、`REPORT.md`（`8d86c65b…67d6`）。
- 根因诊断/完整入口检查证据：`COMMAND_RECORDS.md`（C01–C28，含 `RUN_BUG1/`、`OBJECTS_CHECK_FAIL1.json`、浏览器 attempt1–4、`diag_pick.json`）。
- 源码差异与 SHA 证据：`MANIFEST.json` 的 `source_code` 与 `FINAL_SEAL.json` 的 `source_code_sha`；源码在 `sidequests/hfus_tcms_02/realdev/r04/`（全新目录，未改 r01/r02/r03 与任何生产/配置）。
- 原始日志索引：`RUN/frames.jsonl`（780 行）、`RUN/frames/*.npz`（逐帧 ledger）、`BROWSER/browser_check.log` 与 13 张 PNG、`BROWSER/server.stdout`、`DOMAINS/s3_domains.png`、`TRANSFORM/TRANSFORM_CHECK.json`。
- 当前工单下一步：只做只读独立复审；S3 完成或失败即停写，本轮已 SUBMITTED，不自动进入 S4/S5，不自动宣布 ACCEPTED。

复审入口：`docs/human_fall/evidence/2026-10-17_hfus_tcms_02_s03_r1/HANDOFF.md`。
