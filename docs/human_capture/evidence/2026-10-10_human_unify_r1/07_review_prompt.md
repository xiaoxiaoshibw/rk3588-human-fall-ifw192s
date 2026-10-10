# HUMAN-UNIFY-R1 独立审计任务

仓库： D:\Code\ldiar (Windows 路径， git bash 用正斜杠）

任务： 你是独立审计员。审计本轮 HUMAN-UNIFY-R1 是否实心交付：

1. **是否形成真实的公共核心， 而非把 A/B 算法包装到同一接口** — 重点看 `pc_apps/human_core/` 的 engine.js 是真复用 human_pipe_lib.js (BASE_A) 还是 stub。
2. **是否保持生产文件不变** — 看 `git status` 中 pc_apps/human_replay/ 是否被本轮修改 （应该没有； 有一些用户其它任务的 M 改动是 2026-10-09 留下来的， 与本轮无关）。
3. **人工 GT 和伪标签混用** — 检查引擎是否有把 ai_labels.json 当 HUMAN_VERIFIED 使用的代码 （应该没有； 我们在 schema.gt_attestation 和 runner.js 明确标记 PSEUDO)。
4. **数据泄漏** — 训练/验证 split 是否按段而非按帧？（目前一个 model fit 情况: rf_person_v1 训练在 HR09 / 验证在新会话， 没有交叉）
5. **轨迹状态污染** — begin_session 是否全面重置 tracker/retention/seen_frames?
6. **原始点到候选映射错误** — 28B 解析： data_loader.js 的帧切片 （offset_points*28 起， count_points*28 长） 是否正确？测试 test_data_loader 是否覆盖？
7. **不公平 A/B 配置** — BASE_A vs U1 应完全等价 （实测观察是）; BASE_B 与 U3 的差异仅为REF_envelope + rf51? （实测并非如此 — U3 不该用 REF)
8. **统计指标与原始数据一致** — 用 `python -c` 或 node 复算关键数字： 113611 空场 frames, 114641 帧数， U3 confirmed。是否对得上落盘 json?
9. **性能数据有实测依据** — test_perf.js 是否真跑还是编数字？(读代码）
10. **统一核心能否在隔离环境复现** — 试运行 `node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js`, 是否 6 suite PASS?

## 重点数字必须复算

- 空场 113611 BASE_A frames_with_furniture_cand=203
- 154007 BASE_B confirmed=6
- 114641 U3 confirmed=5

## 验证命令清单

```bash
cd /d/Code/ldiar

# 1) 公共核心不引用外部 stub
grep -E "throw.*not implemented|TODO|FIXME" pc_apps/human_core/*.js

# 2) 生产文件 mtime 不应是今天
stat -c '%y %n' pc_apps/human_replay/human_pipe_lib.js pc_apps/human_replay/detect_overlay.js pc_apps/human_replay/rf_person.js pc_apps/human_replay/rf_person_v1.json 2>/dev/null || ls -la pc_apps/human_replay/human_pipe_lib.js pc_apps/human_replay/detect_overlay.js pc_apps/human_replay/rf_person.js pc_apps/human_replay/rf_person_v1.json

# 3) human_core 快照
find pc_apps/human_core -name "*.js" -newer pc_apps/human_replay/human_pipe_lib.js 2>/dev/null

# 4) 数据 SHA 是否一致落盘
head -50 docs/human_capture/evidence/2026-10-10_human_unify_r1/02_source_sha/prod_sha256.json

# 5) ai_labels.json 是否只在允许的地方被读
grep -rn "ai_labels" pc_apps/human_core/ 2>/dev/null  # 应无结果

# 6) 复跑测试
node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js 2>&1 | tail -8

# 7) 复算关键数字
python - <<'EOF'
import json
for sid,mode,field,expected in [
    ('cap_20261009_113611','BASE_A','frames_with_furniture_cand',203),
    ('cap_20261007_154007','BASE_B','n_tracks_confirmed',6),
    ('cap_20261009_114641','U3','n_tracks_confirmed',5),
]:
    p=f'docs/human_capture/evidence/2026-10-10_human_unify_r1/runs/{sid}/{sid}__{mode}.json'
    d=json.load(open(p,encoding='utf-8'))
    v=d['session_summary'][field]
    ok = 'OK' if v==expected else 'MISMATCH'
    print(f'{sid} {mode} {field}={v} expected={expected} [{ok}]')
EOF
```

## 输出要求

请交付一份审计报告 `07_review_findings.md` 到当前目录， 列出：
- VERIFIED （审计员自己跑过且符合）
- PLAUSIBLE （代码逻辑合理但未跑过）
- FAIL （失实或证据与报告不符）
- 如果有 FAIL, 给出具体文件/行/复算命令
- 末尾给一个总评： SHIP | REWORK | REJECT

不要相信我给你的数字， 每个都要自己复算或跑命令。
