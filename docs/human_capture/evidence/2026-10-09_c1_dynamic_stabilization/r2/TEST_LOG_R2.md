# C1 R2 测试日志（任务7交付）
日期 2026-10-10；运行环境 Windows Node v24.14.0 / Python 3.12.10 numpy 1.26.4 sklearn 1.9.0

## JS 单测
```
[detect_overlay.test.js]
PASS: assoc: 断档 18 帧后回来, 新 track id
ALL PASS

[human_pipe_lib.test.js]

38 passed, 0 failed

[panel.test.js]
PASS O1/O5: local-first, offline click, timeout, recovery, selection, stale refresh, remote auto-sync+load, rename; R1 stuck-recover-retry; R2 recording elapsed
```

## Python 单测（human_replay discover）
```

----------------------------------------------------------------------
Ran 49 tests in 39.675s

FAILED (errors=1)
```

注：唯一 ERROR = leveling_auto_test 缺 captures/remote/cap_20261004_202456/meta.json（数据未下载，非代码缺陷，leveling 支线资产，与 C1 无关）。
