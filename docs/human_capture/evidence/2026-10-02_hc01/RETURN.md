# HC-01 return — capture_server 骨架与 REST 契约

工单：../../tickets/HC-01.md · 日期 2026-10-02 · 分支 master

## 交付物

```
src/human_capture/
  __init__.py  package.xml  CMakeLists.txt
  core/__init__.py  core/session_store.py
  scripts/capture_server.py
  config/capture.yaml  launch/human_capture.launch
  tests/test_hc01_health.py  test_hc01_sessions.py  test_hc01_persistence.py
docs/human_capture/README.md  tickets/HC-01.md
```

## 验收逐条

| ID | 结论 | 证据 |
|----|------|------|
| H1 健康 | **PASS** | 本目录 smoke：`/healthz` 200 `{ok,service,version}` |
| H2 状态 | **PASS** | smoke：`/status` 返 `disk_free_mb/sessions_total/recording=false/uptime`；`ros` 如实 `"unknown"`（HC-02 才接探测，未伪造 up） |
| H3 会话生命周期 | **PASS** | 单测 TestCrud/TestStateMachine + smoke：POST→GET→PATCH 合法迁移 200、非法迁移 409 `bad_transition`、不存在 404 `not_found` |
| H4 持久化 | **PASS** | 单测：kill 后重开会话仍在（`test_reopen_keeps_sessions`）；JSON 损坏/结构非法均抛 StoreError 拒绝启动 |
| H5 原子写并发 | **PASS** | 4 线程×50 轮竞争迁移，落盘无撕裂/无 `.sessions.*.tmp` 残留、最终 JSON 可解析、无 crash；并发下合法 409 不计失败（竞争是设计行为） |
| H6 只读边界 | **PASS** | 代码走查：全程无 rosnode kill/rostopic pub/subprocess 起驱动；唯一文件写是 sessions.json/其 tmp/其 lock |
| H7 测试全绿 | **PASS** | `python3 -B -W error -m unittest discover -s src/human_capture/tests -v` → `Ran 26 tests OK`（4.2s） |

## 实测摘要

- `/healthz` → `{"ok": true, "service": "human_capture", "version": "0.1.0"}`
- `/api/v1/status` → `{"ros": "unknown", "disk_free_mb": 373447, ..., "recording": false}`
- PATCH `recording→ready` → 409 `非法迁移 recording -> ready`（契约要求必须先经 extracting）
- PATCH `recording→extracting` → 200，GET 单条状态已迁移
- 未匹配路由 → 404 `no_route`

## 设计落点（未在票里明说、实现时定死）

- 会话 id 白名单字符集（`A-Za-z0-9_.-` ≤128），堵住路径注入与坏 key。
- PATCH `extra` 字段有白名单（`PATCHABLE_EXTRA`），防任意键污染登记表——实测 `injected_key` 被丢弃、白名单键保留。
- sessions.json 原子写 = 同目录 `mkstemp`+`fsync`+`os.replace`；POSIX 下额外加 `.lock` 文件 fcntl 排他锁，跨进程（如手工修复脚本）与多 HTTP 线程都安全。
- `PATCH` 仅带 extra（无 state）时走 upsert 替换、不动状态机，`state` 字段回显当前值。

## 已知边界（留给后续单）

- `ros` 探测、rosbag 录制起停、FIFO 清理、bag→bin 抽取均不在本单（HC-02/03）。
- `/status` 的 `disk_free_mb` 取 `staging_parent` 所在盘；staging 目录不存在时父目录统计（HC-02 建目录后可换更精确位点，但语义不变）。
- 未做鉴权（D2 冻结）。

## 单测运行实录

见同目录 `unittest_output.txt`（26 绿）。
