# HUMAN-UNIFY-R1 R2 返工 · 补充独立只读复审报告（独审 02）

复审者：opencode，指定 `opencode-go/deepseek-v4.1-flash` / plan / default DB（`run_opencode_review_02.py:6,16` 与 `opencode_probe_02.txt` 真实 `PROBE_OK`/`REAL_EXIT=0` 佐证）。日期 2026-10-10；基线 `master` / HEAD `777296d`。已加载 `ponytail`（full）。

只读声明：未改任何源码/数据/配置/文档/证据，未 commit/push/设备/部署/采集/网络，未启动其他 agent。仅读文件、跑 `run_all_tests.js`（仅写系统临时目录 scratch）、跑 stdout-only `node -e` 探针。未自行重跑长矩阵/对拍。

## 实际命令与退出码
- `node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js` → schema13+data_loader16+engine_smoke9+replay_contract11+edge_cases14+model_compat12+**rework21** = **96 断言，7/7，EXIT=0**（与 `tests_03.txt` 一致）。
- `node -e` 核对 `submitted_source_sha_02.json` → human_core **16/16 MATCH**；`engine.js=ff5f0c36…`、`runner.js=c3d48e17…`、`data_loader.js=014feb8b…`。
- `node -e` 隔离探针 → `host human_pipe_lib after U1 = undefined`；两实例 `PIPE` 互异 `true`；`track_lost_max 8 8`。
- `node -e` 漂移探针（模拟 rf 依赖 SHA 变化）→ `THREW: 实现文件在运行期间改变，拒绝生成证据`。
- `node -e` 各 runs manifest 自校验 → `runs_01 45/45`、`runs_02 15/15`、`runs_03 45/45`，CSV 错配 0。当前 `rf_person.js=99b02c72…`（= `current_rf_baseline_03.txt`，本会话内稳定）。

## 新加固逐点判定
| 加固点 | 判定 | 依据 |
|---|---|---|
| 1 `load_production` 不缓存可变源码 + globalThis 隔离 | **PASS** | `engine.js:14-19` 每次 `vm.compileFunction` 传 `["module","globalThis"]` 并以 `{}` 调用；探针证实 host 全局不被写、实例闭包隔离；`human_pipe_lib.js:849` 的 `globalThis.human_pipe_lib=` 只落到一次性对象 |
| 2 loader 按实际读取字节算 SHA | **PASS** | `data_loader.js:91-118` 单次读 `meta_blob`/`blob` 并对同一 buffer 求 `points_sha256/meta_sha256`，不再回读文件 |
| 3 runner mode 前后/跨 mode 实现与输入 SHA 守卫 | **PASS** | `runner.js:24,38,39,49,52`；运行期实现或输入变化即抛错拒生成证据（`test_rework.js:24` + 本探针） |
| 4 parity/perf 起止 SHA 核对 | **PASS** | `test_baseline_parity.js:5,57`、`test_perf.js:8,76` 均冻结起始并核对结束 |

结论：**四处加固实现正确，未破坏原修复**。96/96 通过且含 R01–R08；post-guard `parity_04.json` 9 会话 A/B 全 PASS，其 `source_sha256` 与当前 core+rf（99b02c72）完全一致。

## 逐 ID（软件，本轮）
- **R01–R08：PASS**（本轮复现，无软件 FAIL）。
- **S01：待核定**。`runs_03` 45 JSON+45 CSV 齐备、自洽，`run_meta.source_sha256` = 当前 core+rf；但无对应聚合 summary，最终 manifest 复现性由编排者判，**不预判 PASS**。
- **S02：BLOCKED**。范围外 `pc_apps/human_replay/rf_person.js` 变化（`78c4ce66→…→99b02c72`）使全树冻结不成立，**不能洗成整树 PASS**；仅可确认当前 core 范围 16/16 无未授权改动。
- **Q01：PASS**（probe_02 真实 `PROBE_OK`/exit0，CLI 参数为指定模型+plan）。
- **D01：NOT_RUN**。

## 缺陷与残余风险（file:line）
- 非阻断、极窄 TOCTOU：`runner.js:52`（main 每 mode 前校验）与 `runner.js:24`（run_mode 内部起始捕获）之间存在微秒级窗口，若生产文件恰在此期间改写，本 mode 的 end-check 可能自洽而漏检；实际行为是**下一 mode 中止整批**（`matrix_02` 仅 3 会话即为此机制触发）。触发概率极低，建议编排者知悉即可，不影响本轮判定。
- `perf_02` **NOT_RUN**：当前依赖的性能未重跑（符合“负载结束后另跑”）。

## 总判
新加固正确且未回归旧修复，`pc_apps/human_core` 范围内 **R01–R08 仍无软件 FAIL**，可交下一轮验收。**不给总体 ACCEPTED**；算法资格/生产资格 **BLOCKED**；S02 全树冻结 **BLOCKED**；`perf_02` **NOT_RUN**；设备/物理/部署/采集 **NOT_RUN**。未编辑任何文件，报告仅本 stdout。