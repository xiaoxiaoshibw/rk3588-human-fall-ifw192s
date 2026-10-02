#!/usr/bin/env bash
# HF-09: stop ONLY this task's own synthetic verification processes.
#
# The production node runs the SAME install path, so matching the binary path
# alone is unsafe. Require the verify config marker (hf07_verify.yaml) or the
# explicit demo script, or an explicitly recorded PID; verify the full cmdline
# before killing. Never pkill by a broad pattern.
set -u

hf09_is_ours() {
  local pid="$1" cmd
  if [ -n "${HF09_EXTRA_PID:-}" ] && [ "$pid" = "$HF09_EXTRA_PID" ]; then
    return 0
  fi
  cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
  case "$cmd" in
    *hf07_verify.yaml*) return 0 ;;
    */tmp/hf11_live_demo.py*) return 0 ;;
  esac
  return 1
}

for pat in "hf07_verify.yaml" "/tmp/hf11_live_demo.py"; do
  pids="$(pgrep -f -- "$pat" || true)"
  [ -z "$pids" ] && { echo "no process for marker: $pat"; continue; }
  for pid in $pids; do
    cmd="$(tr '\0' ' ' < "/proc/$pid/cmdline" 2>/dev/null || true)"
    if hf09_is_ours "$pid"; then
      echo "stopping $pid: $cmd"
      kill "$pid"
      for _ in $(seq 1 25); do [ -d "/proc/$pid" ] || break; sleep 0.2; done
      [ -d "/proc/$pid" ] && { echo "SIGKILL $pid"; kill -9 "$pid"; }
    else
      echo "skip $pid (not a synthetic verify process): $cmd"
    fi
  done
done
echo "--- remaining human_fall related python ---"
ps -eo pid,args | grep -E "human_fall_node|hf11_live_demo" | grep -v grep || true
echo "--- driver still running ---"
ps -eo pid,args | grep "[i]nno_lidar_node" || true
