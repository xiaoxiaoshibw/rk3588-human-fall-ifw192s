# 复审任务： HUMAN-UNIFY-R1 R1-R2 (fix 复核）

你第一轮给了 REWORK + 4 FAIL:
1. 03/04 报告与落盘数据失同步 （文档说 U3 confirmed=0, 实测 25/5/12)
2. 04 U3 描述误"= BASE_B + REF"
3. 06 性能数字不可复现
4. PSEUDO_LABEL 未在 schema.gt_attestation 检测

你另外注意：
5. 01 文件列表 ~10 模块， 实际 7 文件
6. BASE_B inline 实现而非 require detect_overlay

本轮已修复：
- 01 重写为实际 7 文件列表 + 明确解释 BASE_B 是 detect_overlay 语义的等价重写 （未 require, 但语义对应） — 参见 01 "审计说明"
- 03/04 全部重写， confirmed=25/5/12 与落盘一致； U3 ≠ BASE_B 已显式说明
- 06 §2 重写： 明确数字是稳态 P50/P95, 单帧分解有 JIT warm-up ±30%
- schema.gt_attestation 现在检查 ai_labels.json → 返回 PSEUDO_LABEL; 新 PASS test_schema
- runner 落盘 prf.level 现在是 PSEUDO_LABEL （对 HR09 会话）

验证命令 （和第一轮同）:

```bash
cd /d/Code/ldiar

# 1) 复跑测试 — 应 6/6
node --max-old-space-size=2048 pc_apps/human_core/run_all_tests.js 2>&1 | tail -5

# 2) 关键数字对照
python - <<'EOF'
import json
for sid,mode,expected in [
    ('cap_20261009_113611','U3',{'frames_with_person_cand':203,'n_tracks_confirmed':12}),
    ('cap_20261007_154007','U3',{'frames_with_person_cand':83,'n_tracks_confirmed':25}),
    ('cap_20261009_114641','U3',{'frames_with_person_cand':177,'n_tracks_confirmed':5}),
]:
    p=f'docs/human_capture/evidence/2026-10-10_human_unify_r1/runs/{sid}/{sid}__{mode}.json'
    d=json.load(open(p,encoding='utf-8'))
    s=d['session_summary']
    ok = all(s[k]==v for k,v in expected.items())
    print(sid, mode, 'match=', ok, s)
EOF

# 3) PSEUDO_LABEL 在落盘 json 中存在
grep -l "PSEUDO_LABEL" docs/human_capture/evidence/2026-10-10_human_unify_r1/runs/cap_20261009_114641/*.json

# 4) 01 与实际文件数目对照
ls pc_apps/human_core/*.js | wc -l   # 应 13 (7 代码 + 6 test)
sed -n '5,20p' docs/human_capture/evidence/2026-10-10_human_unify_r1/01_ARCHITECTURE_PLAN.md

# 5) 04 中 "U3 ≠ BASE_B + REF" 段落
grep -A 3 "U3 ≠ BASE_B" docs/human_capture/evidence/2026-10-10_human_unify_r1/04_AB_COMPARISON.md

# 6) 06 §2 重写
sed -n '10,20p' docs/human_capture/evidence/2026-10-10_human_unify_r1/06_PERFORMANCE_REPORT.md
```

## 输出

把复审结果写到 `docs/human_capture/evidence/2026-10-10_human_unify_r1/07_review_findings_r2.md`:
- 每项第一轮 FAIL 是 FIXED / PARTIAL / NOT_FIXED
- 终审： SHIP | REWORK | REJECT

不要相信我报告里的数字， 全部自己复算。
