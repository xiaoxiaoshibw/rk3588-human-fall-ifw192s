#!/usr/bin/env bash
# FRESH-MAP r01 M1 全网格：默认组 + τ{4,16} + ev_hit3 + ev_confirm3。
# 每个 (session,group) 一个全新 outdir（拒覆盖纪律）。日志 → grid.log
set -u
cd "$(dirname "$0")"
ROOT=../../..
EV=$ROOT/docs/sidequests/evidence/2026-10-15_fresh_map_r1/grid
mkdir -p "$EV"
NODE="node --max-old-space-size=2048 run_fresh.js"
CAP=$ROOT/captures/remote
REF221808=$CAP/cap_20261014_221808
REF111738=$CAP/cap_20261015_111738

run() { # run <sid> <tag> <outdir> extra args...
  local sid=$1 tag=$2 out=$3; shift 3
  $NODE --session "$CAP/$sid" --outdir "$out" --tag "$tag" "$@" || echo "ERROR $sid $tag"
}

# E1 静立存活（ref=外部空场 221808；P0 加 BASE_A 对照）
declare -A E1WIN=( [cap_20261013_082623]=20:140 [cap_20261013_082717]=20:170
  [cap_20261013_083044]=10:120 [cap_20261013_083120]=10:120
  [cap_20261013_083218]=10:110 [cap_20261013_083254]=10:110 )
for sid in "${!E1WIN[@]}"; do
  w=${E1WIN[$sid]}
  run "$sid" P0 "$EV/${sid}__P0" --ref-session "$REF221808" --pset-window "$w" --compare-base-a
  run "$sid" tau4 "$EV/${sid}__tau4" --ref-session "$REF221808" --pset-window "$w" --tau 4
  run "$sid" tau16 "$EV/${sid}__tau16" --ref-session "$REF221808" --pset-window "$w" --tau 16
  run "$sid" evhit3 "$EV/${sid}__evhit3" --ref-session "$REF221808" --pset-window "$w" --ev-hit-min 3
  run "$sid" evconf3 "$EV/${sid}__evconf3" --ref-session "$REF221808" --pset-window "$w" --ev-confirm 3
done

# E2 空场误亮（自 warmup 40；×5 组）
for sid in cap_20261014_221808 cap_20261015_111738; do
  run "$sid" P0 "$EV/${sid}__E2_P0"
  run "$sid" tau4 "$EV/${sid}__E2_tau4" --tau 4
  run "$sid" tau16 "$EV/${sid}__E2_tau16" --tau 16
  run "$sid" evhit3 "$EV/${sid}__E2_evhit3" --ev-hit-min 3
  run "$sid" evconf3 "$EV/${sid}__E2_evconf3" --ev-confirm 3
done

# E3 复活延迟（运动目标；ref=同天已配准空场）
run cap_20261015_142416 P0 "$EV/cap_20261015_142416__E3_P0" --ref-session "$REF111738" --revive-from 100 --warmup 20
run cap_20261015_142511 P0 "$EV/cap_20261015_142511__E3_P0" --ref-session "$REF111738" --revive-from 8 --warmup 4

# E4 阴性对照（全程静立被 warmup 吞进参考图；预期 pset≈0，不进成功判据）
run cap_20261013_082829 P0 "$EV/cap_20261013_082829__E4_P0" --pset-window 100:150
run cap_20261013_082906 P0 "$EV/cap_20261013_082906__E4_P0" --pset-window 100:150

echo GRID_DONE
