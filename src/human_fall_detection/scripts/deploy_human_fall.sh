#!/usr/bin/env bash
# HF-09 rollback-capable deploy/start/stop for the live human_fall node + page.
#
# Runs INSIDE the slam-localization container, with a ROS env already sourced
# (rospy / inno_lidar_msg come from the existing devel overlay). Each release
# stores an IMMUTABLE Python code bundle (core/scripts/config + a copy of the
# frozen point-cloud decoder) and the start/profile commands load `core` and the
# node ONLY from that bundle; the mutable devel working tree is never imported.
#
# Versions are kept under $BASE/releases/<utc>; rollback repoints symlinks and
# never deletes a release. Stopping kills only the exact recorded PID after
# verifying its full cmdline (node path AND config path); a mismatch refuses and
# exits non-zero, so no second node is ever started. The driver, the old
# homepage and the network are never touched.
set -euo pipefail

BASE="${HF_DEPLOY_BASE:-/root/catkin_ws/human_fall_deploy}"
RELEASES="$BASE/releases"
CURRENT="$BASE/current"
PID_DIR="$BASE/pids"
WEBUI_ROOT="/root/catkin_ws/webui"
WEBUI_LINK="$WEBUI_ROOT/human_fall"
WS="${HF_WS:-/root/catkin_ws/hf07_verify_ws}"
PKG_SRC="$WS/src/human_fall_detection"
HFC_SRC="${HF_HFC_SRC:-$WS/src/human_follow_calibration}"
NODE_PID="$PID_DIR/human_fall_node.pid"
NODE_CMD="$PID_DIR/human_fall_node.cmd"
PROFILE_PID="$PID_DIR/profile.pid"
PROFILE_CMD="$PID_DIR/profile.cmd"

log() { printf '%s\n' "$*"; }

_resolve_current() {
  [ -L "$CURRENT" ] || { log "no current release; run: $0 release"; exit 3; }
  readlink -f "$CURRENT"
}

_pid_cmdline() {
  [ -n "${1:-}" ] && [ -r "/proc/$1/cmdline" ] && tr '\0' ' ' < "/proc/$1/cmdline" || true
}

_bundle_pythonpath() {
  printf '%s' "$1/bundle:$1/bundle/scripts:$1/bundle/human_follow_calibration/scripts:${PYTHONPATH:-}"
}

# Fail unless the bundle files match the recorded manifest (manifest itself and
# pycache are excluded when it is generated, so its content is stable).
_verify_manifest() {
  local dir="$1"
  [ -f "$dir/bundle/manifest.sha256" ] || { log "REFUSING: no bundle manifest"; return 1; }
  ( cd "$dir/bundle" && sha256sum -c manifest.sha256 >/dev/null 2>&1 ) \
    || { log "REFUSING: bundle manifest check failed"; return 1; }
}

# Fail unless the bundle's core is the one Python actually imports.
_verify_bundle_import() {
  local dir="$1" core_file
  core_file="$(PYTHONPATH="$(_bundle_pythonpath "$dir")" python3 -c 'import core; print(core.__file__)' 2>/dev/null || true)"
  case "$core_file" in
    "$dir"/bundle/core/*) log "bundle core OK: $core_file" ;;
    *) log "REFUSING: core resolves outside release bundle: ${core_file:-<none>}"; return 1 ;;
  esac
}

_kill_pidfile() {
  local file="$1" cmd_file="$2" expect_node="$3" expect_cfg="$4" pid cmd stored
  [ -f "$file" ] || { log "no pidfile $file"; return 0; }
  pid="$(cat "$file" 2>/dev/null || true)"
  # A zombie still has /proc/<pid> but an empty cmdline (container PID 1 does not
  # reap orphans), so treat an empty cmdline as already stopped.
  if [ -z "$pid" ] || [ ! -d "/proc/$pid" ] || [ -z "$(_pid_cmdline "$pid")" ]; then
    log "stale/zombie pid $pid in $file"; rm -f "$file" "$cmd_file"; return 0
  fi
  cmd="$(_pid_cmdline "$pid")"
  if [ -f "$cmd_file" ]; then
    stored="$(cat "$cmd_file" 2>/dev/null || true)"
    expect_node="${stored%%|*}"; expect_cfg="${stored##*|}"
    if [ -z "$expect_node" ] || [ -z "$expect_cfg" ]; then
      log "REFUSING: incomplete command metadata in $cmd_file"; return 1
    fi
  fi
  case "$cmd" in
    *"$expect_node"*"$expect_cfg"*)
      log "stopping pid $pid"; kill "$pid"
      for _ in $(seq 1 25); do [ -z "$(_pid_cmdline "$pid")" ] && break; sleep 0.2; done
      if [ -n "$(_pid_cmdline "$pid")" ]; then
        log "pid $pid still alive; SIGKILL"; kill -9 "$pid"
        for _ in $(seq 1 15); do [ -z "$(_pid_cmdline "$pid")" ] && break; sleep 0.2; done
      fi
      if [ -n "$(_pid_cmdline "$pid")" ]; then log "REFUSING: pid $pid did not exit"; return 1; fi ;;
    *) log "REFUSING to kill pid $pid: cmdline does not match node+config"; return 1 ;;
  esac
  rm -f "$file" "$cmd_file"
}

_stop_node() { _kill_pidfile "$NODE_PID" "$NODE_CMD" "$1/bundle/scripts/human_fall_node.py" "$1/bundle/config/human_fall_prod.yaml"; }

release() {
  local stamp; stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  local dir="$RELEASES/$stamp" tmp="$RELEASES/.${stamp}.tmp.$$"
  local webui_src="${WEBUI_SRC:-$BASE/src/webui/human_fall}"
  [ -d "$webui_src" ] || { log "missing page source dir $webui_src"; exit 7; }
  if [ -e "$CURRENT" ] && [ ! -L "$CURRENT" ]; then log "REFUSING: $CURRENT is not a symlink"; exit 4; fi
  if [ -e "$WEBUI_LINK" ] && [ ! -L "$WEBUI_LINK" ]; then log "REFUSING: $WEBUI_LINK is not a symlink"; exit 4; fi
  mkdir -p "$tmp/bundle" "$tmp/webui"
  mkdir -p "$tmp/bundle/core" "$tmp/bundle/scripts" "$tmp/bundle/config" \
           "$tmp/bundle/human_follow_calibration/scripts"
  cp -a "$PKG_SRC"/core/*.py "$tmp/bundle/core/"
  cp -a "$PKG_SRC"/scripts/*.py "$tmp/bundle/scripts/"
  cp -a "$PKG_SRC"/config/*.yaml "$tmp/bundle/config/"
  if [ -f "$HFC_SRC/scripts/calibrate_human_follow.py" ]; then
    cp -a "$HFC_SRC"/scripts/*.py "$tmp/bundle/human_follow_calibration/scripts/"
  else
    log "REFUSING: frozen decoder not found at $HFC_SRC/scripts"; rm -rf "$tmp"; exit 7
  fi
  cp -a "$webui_src" "$tmp/webui/human_fall"
  ( cd "$tmp/bundle" && find . -type f -not -name 'manifest.sha256' \
      -not -path '*__pycache__*' -not -name '*.pyc' -print0 \
      | sort -z | xargs -0 sha256sum ) > "$tmp/bundle/manifest.sha256"
  ( cd "$PKG_SRC" && find . -type f -not -path '*__pycache__*' -print0 \
      | sort -z | xargs -0 sha256sum ) > "$tmp/source.sha256"
  if ! _verify_bundle_import "$tmp"; then rm -rf "$tmp"; exit 5; fi
  mv "$tmp" "$dir"
  ln -sfn "$dir" "$CURRENT"
  ln -sfn "$dir/webui/human_fall" "$WEBUI_LINK"
  log "released $dir (current -> $stamp); bundle core+scripts+config+decoder stored"
}

start() {
  local dir; dir="$(_resolve_current)"
  [ -f "$dir/bundle/scripts/human_fall_node.py" ] || { log "release has no code bundle (legacy); refusing"; exit 5; }
  _verify_manifest "$dir" || exit 5
  _verify_bundle_import "$dir" >/dev/null || { log "bundle import check failed; not starting"; exit 5; }
  mkdir -p "$PID_DIR"
  _stop_node "$dir" || { log "existing node not stopped; refusing to start a second"; exit 1; }
  local node="$dir/bundle/scripts/human_fall_node.py"
  local cfg="$dir/bundle/config/human_fall_prod.yaml"
  local perc="$dir/bundle/config/perception.yaml"
  PYTHONPATH="$(_bundle_pythonpath "$dir")" nohup setsid python3 "$node" \
    --config "$cfg" --perception "$perc" > "$dir/run.log" 2>&1 &
  echo $! > "$NODE_PID"
  printf '%s|%s' "$node" "$cfg" > "$NODE_CMD"
  log "started human_fall_node pid $(cat "$NODE_PID") from bundle $(basename "$dir")"
}

profile() {
  local dir; dir="$(_resolve_current)"; local duration="${1:-1800}"
  [ -f "$dir/bundle/scripts/profile_pipeline.py" ] || { log "release has no bundle profiler"; exit 5; }
  _verify_manifest "$dir" || exit 5
  local pid; pid="$(cat "$NODE_PID" 2>/dev/null || echo 0)"
  mkdir -p "$PID_DIR"
  # Refuse a duplicate observer so two processes never write the same JSONL.
  local old; old="$(cat "$PROFILE_PID" 2>/dev/null || true)"
  if [ -n "$old" ] && [ -d "/proc/$old" ] && [ -n "$(_pid_cmdline "$old")" ]; then
    log "REFUSING: a profiler is already running (pid $old)"; exit 1
  fi
  local script="$dir/bundle/scripts/profile_pipeline.py" rows="$dir/profile_rows.jsonl"
  PYTHONPATH="$(_bundle_pythonpath "$dir")" nohup setsid python3 \
    "$script" \
    --duration "$duration" --note-pid "${pid:-0}" --label "live" \
    --mode "human_fall_prod.yaml (ground=unavailable, confirmed-off) bundle=$(basename "$dir")" \
    --output "$rows" --summary "$dir/profile_summary.json" \
    > "$dir/profile.log" 2>&1 &
  echo $! > "$PROFILE_PID"
  printf '%s|%s' "$script" "$rows" > "$PROFILE_CMD"
  log "profiling pid $(cat "$PROFILE_PID") for ${duration}s -> $dir/profile_summary.json"
}

stop() {
  _kill_pidfile "$PROFILE_PID" "$PROFILE_CMD" "profile_pipeline.py" "" || return 1
  local dir; dir="$(_resolve_current 2>/dev/null || true)"
  if [ -n "$dir" ]; then _stop_node "$dir" || return 1; fi
  log "stopped (driver untouched)"
}

status() {
  local dir; dir="$(_resolve_current 2>/dev/null || echo none)"
  log "current release: $dir"
  for pair in "node:$NODE_PID" "profile:$PROFILE_PID"; do
    local name="${pair%%:*}" file="${pair#*:}" pid
    pid="$(cat "$file" 2>/dev/null || true)"
    if [ -n "$pid" ] && [ -d "/proc/$pid" ] && [ -n "$(_pid_cmdline "$pid")" ]; then
      log "$name pid $pid RUNNING: $(_pid_cmdline "$pid")"
    else
      log "$name not running"
    fi
  done
  log "page: $WEBUI_LINK -> $(readlink -f "$WEBUI_LINK" 2>/dev/null || echo none)"
}

rollback() {
  local target="${1:-}"
  if [ -z "$target" ]; then
    target="$(ls -1 "$RELEASES" | grep -v '^\.' | sort | tail -n 2 | head -n 1)"
  fi
  [ -n "$target" ] && [ -d "$RELEASES/$target" ] || { log "no such release: $target"; exit 6; }
  if [ ! -f "$RELEASES/$target/bundle/scripts/human_fall_node.py" ]; then
    log "REFUSING code rollback: release $target has no immutable code bundle"; exit 6
  fi
  if [ -e "$CURRENT" ] && [ ! -L "$CURRENT" ]; then log "REFUSING: $CURRENT is not a symlink"; exit 4; fi
  if [ -e "$WEBUI_LINK" ] && [ ! -L "$WEBUI_LINK" ]; then log "REFUSING: $WEBUI_LINK is not a symlink"; exit 4; fi
  local prev; prev="$(readlink -f "$CURRENT" 2>/dev/null || true)"
  if ! stop; then log "REFUSING rollback: could not stop current node cleanly"; exit 1; fi
  ln -sfn "$RELEASES/$target" "$CURRENT"
  ln -sfn "$RELEASES/$target/webui/human_fall" "$WEBUI_LINK"
  log "rolled back to $target (kept previous $prev)"
  start
}

case "${1:-}" in
  release) shift; release "$@" ;;
  start) shift; start "$@" ;;
  profile) shift; profile "$@" ;;
  stop) shift; stop "$@" ;;
  status) shift; status "$@" ;;
  rollback) shift; rollback "$@" ;;
  *) log "usage: $0 {release|start|profile [secs]|stop|status|rollback [release]}"; exit 2 ;;
esac
