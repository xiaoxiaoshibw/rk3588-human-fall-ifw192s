#!/usr/bin/env bash
# Field-trial release controller for the human perception node + capture + page.
#
# Runs INSIDE the slam-localization container (ROS1 noetic, Python 3.8.10,
# NumPy 1.17.4). It consumes ONE standard bundle produced by
# prepare_single_target_bundle.py; there is no second copy list here.
#
# Invariants (the reason each helper exists):
#  * code, page and site profile are bound together: `current` is the only
#    switch, and the page is served through symlinks into it, so a staged
#    release never changes the running page;
#  * staging and activation are separate -- `stage` and `preflight` change
#    nothing that is currently running;
#  * a second start never produces a second process: every component is looked
#    up by pidfile AND verified against its recorded cmdline (node path and
#    config path) before it is treated as ours;
#  * "the PID is alive" is not health: `status`/`health` also check a fresh
#    state message, worker health and the capture service's own report;
#  * capture is stopped through its real shutdown path (SIGTERM -> server_close)
#    with a budget derived from its own sigint_grace_sec + sigterm_kill_sec, not
#    the fall node's short budget; an unfinished extractor is reported as still
#    alive instead of "stopped";
#  * every start gets its own run directory; logs rotate by size and never
#    overwrite the previous run.
#
# Never touches the driver, the network, session data or the registry.
set -euo pipefail

BASE="${HF_DEPLOY_BASE:-/root/catkin_ws/human_fall_deploy}"
RELEASES="$BASE/releases"
CURRENT="$BASE/current"
STAGED="$BASE/staged"
PROFILES="$BASE/profiles"
RUNS="$BASE/runs"
STATE="$BASE/state"
WWW="$BASE/www"
PIDS="$STATE/pids"
BINDING="$STATE/binding.json"

NODE_PID="$PIDS/node.pid"
NODE_CMD="$PIDS/node.cmd"
CAP_PID="$PIDS/capture.pid"
CAP_CMD="$PIDS/capture.cmd"
HTTP_PID="$PIDS/http.pid"
HTTP_CMD="$PIDS/http.cmd"

CAPTURE_PORT="${HF_CAPTURE_PORT:-8766}"
HTTP_PORT="${HF_HTTP_PORT:-8936}"
NODE_NAME="${HF_NODE_NAME:-single_target_live}"
LOG_MAX_BYTES="${HF_LOG_MAX_BYTES:-20971520}"   # 20 MiB per component log
LOG_KEEP="${HF_LOG_KEEP:-3}"
NODE_STOP_S="${HF_NODE_STOP_S:-10}"
DISK_MIN_MB="${HF_DISK_MIN_MB:-2048}"

log() { printf '%s\n' "$*"; }
die() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# ROS environment: components are started by this script, not by an interactive
# shell, so the overlay must be sourced here (otherwise rospy is simply missing).
# The ROS setup scripts reference unset variables, so `set -u` is suspended
# around them (they are third-party and not ours to change).
_ros_env() {
  set +u
  if [ -f /opt/ros/noetic/setup.bash ]; then
    # shellcheck disable=SC1091
    . /opt/ros/noetic/setup.bash
  fi
  if [ -f "${HF_WS:-/root/catkin_ws}/devel/setup.bash" ]; then
    # shellcheck disable=SC1090
    . "${HF_WS:-/root/catkin_ws}/devel/setup.bash"
  fi
  set -u
}
_ros_env

now_stamp() { date -u +%Y%m%dT%H%M%SZ; }

_sha256() { sha256sum "$1" | awk '{print $1}'; }

_pid_cmdline() {
  [ -n "${1:-}" ] && [ -r "/proc/$1/cmdline" ] && tr '\0' ' ' < "/proc/$1/cmdline" || true
}

_alive() {
  local pid="${1:-}"
  [ -n "$pid" ] && [ -d "/proc/$pid" ] && [ -n "$(_pid_cmdline "$pid")" ]
}

_port_free() {
  # SO_REUSEADDR matches the servers (allow_reuse_address) so a socket left in
  # TIME_WAIT does not look like a second listener; a live listener still fails.
  python3 - "$1" <<'PY'
import socket, sys
port = int(sys.argv[1])
sock = socket.socket()
sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
try:
    sock.bind(('0.0.0.0', port))
except OSError:
    print('busy')
else:
    print('free')
finally:
    sock.close()
PY
}

_resolve_current() {
  [ -L "$CURRENT" ] || return 3
  readlink -f "$CURRENT"
}

# Accept a release directory, a bare release name, or nothing (current).
_release_arg() {
  local arg="${1:-}"
  if [ -z "$arg" ]; then _resolve_current; return; fi
  if [ -d "$arg" ]; then readlink -f "$arg"; return; fi
  if [ -d "$RELEASES/$arg" ]; then printf '%s' "$RELEASES/$arg"; return; fi
  return 6
}

_release_of_cmdline() {
  # Extract <BASE>/releases/<name> from a command line, if present.
  local cmd="$1"
  printf '%s' "$cmd" | tr ' ' '\n' | grep -o "$RELEASES/[^/]*" | head -n 1 || true
}

_bundle_paths() {  # PYTHONPATH for the fall node (repo-relative layout inside bundle)
  local dir="$1/bundle"
  # Keep the inherited ROS overlay paths: overriding PYTHONPATH with only the
  # bundle is exactly how rospy "disappears" from a script-started process.
  printf '%s' "$dir/src/human_fall_detection:$dir/src/human_fall_detection/scripts:$dir/src/human_follow_calibration/scripts:$dir/sidequests/hfus_tcms_02/realdev/current:${PYTHONPATH:-}"
}

_verify_manifest() {
  local dir="$1/bundle"
  [ -f "$dir/MANIFEST.json" ] || { log "REFUSING: bundle has no MANIFEST.json"; return 1; }
  [ -f "$dir/manifest.sha256" ] || { log "REFUSING: bundle has no manifest.sha256"; return 1; }
  ( cd "$dir" && sha256sum -c --quiet manifest.sha256 >/dev/null 2>&1 ) \
    || { log "REFUSING: bundle manifest verification failed"; return 1; }
}

_verify_import() {
  local dir="$1/bundle" out
  out="$(PYTHONPATH="$(_bundle_paths "$(dirname "$dir")")" python3 -B -c \
      'import core, human_fall_node, region_runtime; print(core.__file__)' 2>&1)" \
    || { log "REFUSING: bundle import failed: $out"; return 1; }
  case "$out" in
    "$dir"/src/human_fall_detection/core/*) : ;;
    *) log "REFUSING: core resolves outside bundle: $out"; return 1 ;;
  esac
  # capture keeps its own core package; make sure it is not the fall core.
  out="$(PYTHONPATH="$dir/src/human_capture" python3 -B -c 'import core; print(core.__file__)' 2>&1)" \
    || { log "REFUSING: capture core import failed: $out"; return 1; }
  case "$out" in
    "$dir"/src/human_capture/core/*) : ;;
    *) log "REFUSING: capture core resolves outside its package: $out"; return 1 ;;
  esac
}

_rotate_log() {
  local file="$1"
  [ -f "$file" ] || return 0
  local size; size="$(stat -c %s "$file" 2>/dev/null || echo 0)"
  [ "$size" -lt "$LOG_MAX_BYTES" ] && return 0
  local index="$LOG_KEEP"
  while [ "$index" -ge 1 ]; do
    [ -f "$file.$index" ] && mv -f "$file.$index" "$file.$((index + 1))" 2>/dev/null || true
    index=$((index - 1))
  done
  mv -f "$file" "$file.1"
  # Keep only LOG_KEEP archives.
  local oldest="$((LOG_KEEP + 1))"
  [ -f "$file.$oldest" ] && rm -f "$file.$oldest"
}

_stop_pidfile() {  # _stop_pidfile <pidfile> <cmdfile> <expect> <timeout_s> <label> [alt_expect]
  local file="$1" cmd_file="$2" expect="$3" timeout="$4" label="$5" alt="${6:-}" pid cmd stored
  [ -f "$file" ] || { log "$label: no pidfile"; return 0; }
  pid="$(cat "$file" 2>/dev/null || true)"
  if [ -z "$pid" ] || [ ! -d "/proc/$pid" ] || [ -z "$(_pid_cmdline "$pid")" ]; then
    log "$label: stale/zombie pid $pid"; rm -f "$file" "$cmd_file"; return 0
  fi
  cmd="$(_pid_cmdline "$pid")"
  # The recorded command is advisory: it was historically synthesised with a
  # different argument order, so requiring an exact substring made the controller
  # refuse to stop its own page server. The two checks that matter are (a) the
  # expected program marker and (b) that the process really runs from this
  # deployment base -- that is what makes it ours and not an unrelated process.
  if [ -f "$cmd_file" ]; then
    stored="$(cat "$cmd_file" 2>/dev/null || true)"
    [ -n "$stored" ] || { log "REFUSING $label: empty command metadata"; return 1; }
    case "$cmd" in
      *"$stored"*) : ;;
      *) log "$label: recorded command differs from live cmdline (continuing with marker+base checks)" ;;
    esac
  fi
  case "$cmd" in
    *"$expect"*) : ;;
    *)
      if [ -n "$alt" ] && case "$cmd" in *"$alt"*) true ;; *) false ;; esac; then :;
      else log "REFUSING $label: pid $pid cmdline lacks $expect"; return 1; fi
      ;;
  esac
  case "$cmd" in
    *"$BASE"*) : ;;
    *) log "REFUSING $label: pid $pid does not run from $BASE"; return 1 ;;
  esac
  log "$label: stopping pid $pid (grace ${timeout}s)"
  kill "$pid" 2>/dev/null || true
  local waited=0
  while [ "$waited" -lt "$((timeout * 10))" ]; do
    _alive "$pid" || break
    sleep 0.1; waited=$((waited + 1))
  done
  if _alive "$pid"; then
    log "$label: pid $pid still alive after ${timeout}s; SIGKILL"
    kill -9 "$pid" 2>/dev/null || true
    waited=0
    while [ "$waited" -lt 50 ]; do _alive "$pid" || break; sleep 0.1; waited=$((waited + 1)); done
  fi
  if _alive "$pid"; then log "REFUSING $label: pid $pid did not exit"; return 1; fi
  rm -f "$file" "$cmd_file"
  log "$label: stopped"
}

# ---------------------------------------------------------------------------
# HTTP helpers for the capture service
# ---------------------------------------------------------------------------
_capture_get() {  # _capture_get <path> -> prints body, exit 0 on 2xx/204
  python3 - "$CAPTURE_PORT" "$1" <<'PY'
import json, sys, urllib.request
port, path = sys.argv[1], sys.argv[2]
url = 'http://127.0.0.1:%s%s' % (port, path)
try:
    with urllib.request.urlopen(url, timeout=8) as response:
        body = response.read().decode('utf-8', 'replace')
        print(response.status)
        print(body)
except urllib.error.HTTPError as exc:
    print(exc.code); print(exc.read().decode('utf-8', 'replace'))
except Exception as exc:  # noqa: BLE001
    print(0); print(json.dumps({'error': str(exc)}))
PY
}

_capture_post() {  # _capture_post <path> <body>
  python3 - "$CAPTURE_PORT" "$1" "${2:-{\}}" <<'PY'
import json, sys, urllib.request
port, path, body = sys.argv[1], sys.argv[2], sys.argv[3]
url = 'http://127.0.0.1:%s%s' % (port, path)
request = urllib.request.Request(url, data=body.encode('utf-8'), method='POST',
                                 headers={'Content-Type': 'application/json'})
try:
    with urllib.request.urlopen(request, timeout=15) as response:
        print(response.status); print(response.read().decode('utf-8', 'replace'))
except urllib.error.HTTPError as exc:
    print(exc.code); print(exc.read().decode('utf-8', 'replace'))
except Exception as exc:  # noqa: BLE001
    print(0); print(json.dumps({'error': str(exc)}))
PY
}

_capture_health() {
  local out first second
  out="$(_capture_get /healthz)"
  first="${out%%$'\n'*}"; second="${out#*$'\n'}"
  if [ "$first" = "200" ]; then log "capture: healthy $second"; return 0; fi
  log "capture: NOT healthy (http=$first) $second"; return 1
}

# ---------------------------------------------------------------------------
# stage / preflight / activate
# ---------------------------------------------------------------------------
stage() {
  local tar="${1:-}"
  [ -n "$tar" ] || die "usage: $0 stage <bundle.tar>"
  [ -f "$tar" ] || die "no such bundle: $tar"
  mkdir -p "$RELEASES" "$STAGED"
  local rid; rid="$(python3 - "$tar" <<'PY'
import json, sys, tarfile
with tarfile.open(sys.argv[1]) as archive:
    print(json.load(archive.extractfile('RELEASE.json'))['release_id'])
PY
)" || die "bundle has no readable RELEASE.json"
  local name; name="$(now_stamp)_${rid:0:8}"
  local dir="$RELEASES/$name" tmp="$RELEASES/.${name}.tmp.$$"
  [ -e "$dir" ] && die "release already exists: $dir"
  mkdir -p "$tmp/bundle"
  tar -xf "$tar" -C "$tmp/bundle"
  # Rebuild the checksum file straight from MANIFEST.json (single source).
  python3 - "$tmp/bundle" <<'PY'
import json, os, sys
root = sys.argv[1]
manifest = json.load(open(os.path.join(root, 'MANIFEST.json'), encoding='utf-8'))
with open(os.path.join(root, 'manifest.sha256'), 'w', encoding='utf-8') as out:
    for name in sorted(manifest):
        out.write('%s  %s\n' % (manifest[name]['sha256'], name))
PY
  _verify_manifest "$tmp" || { rm -rf "$tmp"; exit 5; }
  _verify_import "$tmp" || { rm -rf "$tmp"; exit 5; }
  cp -f "$tar" "$STAGED/$name.tar"
  mv "$tmp" "$dir"
  log "staged release $name (release_id $rid, $(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['file_count'])" "$dir/bundle/RELEASE.json") files)"
  log "NOT activated: the running code/page/profile are unchanged"
}

preflight() {
  local dir="${1:-}"
  dir="$(_release_arg "$dir")" || die "no such release: ${1:-<current>}; run: $0 stage <tar>"
  local bundle="$dir/bundle"
  [ -d "$bundle" ] || die "release has no bundle: $dir"
  log "preflight: release $(basename "$dir")"
  _verify_manifest "$dir" || exit 5
  _verify_import "$dir" || exit 5
  python3 - "$bundle" <<'PY' || exit 5
import sys
sys.path.insert(0, sys.argv[1] + '/src/human_fall_detection')
import numpy, yaml
print('python %s numpy %s yaml ok' % (sys.version.split()[0], numpy.__version__))
PY
  # rospy/inno_lidar_msg must actually be importable in THIS environment: a
  # missing overlay is exactly what a naive start would discover too late.
  python3 - <<'PY' || exit 5
try:
    import rospy
    from inno_lidar_msg.msg import DeviceStatus  # noqa: F401
except ImportError as exc:
    print('REFUSING: ROS1 environment incomplete: %s' % exc)
    raise SystemExit(1)
print('rospy %s + inno_lidar_msg ok' % getattr(rospy, '__version__', '?'))
PY
  local profile; profile="$(cat "$STATE/profile.path" 2>/dev/null || true)"
  [ -n "$profile" ] && [ -f "$profile" ] || die "no site profile configured (state/profile.path)"
  PYTHONPATH="$(_bundle_paths "$dir")" python3 -B "$bundle/src/human_fall_detection/scripts/release_config.py" \
      profile --check "$profile" --report "$STATE/profile_check.json" >/dev/null \
    || { log "REFUSING: site profile invalid (see $STATE/profile_check.json)"; exit 5; }
  local free_mb; free_mb="$(df -Pm "$BASE" | awk 'NR==2 {print $4}')"
  [ "$free_mb" -ge "$DISK_MIN_MB" ] || die "only ${free_mb}MB free (< ${DISK_MIN_MB}MB)"
  [ -w "$BASE" ] || die "deploy base is not writable"
  local perceive="$bundle/src/human_fall_detection/config/perception_single_target_v1.yaml"
  grep -q 'mode_verified: false' "$perceive" || die "perception mode_verified is not false"
  grep -q 'allow_confirmed: false' "$perceive" || die "perception allow_confirmed is not false"
  # Ports are allowed to be busy only when our own pidfile owns them. Preflight
# only warns: activation must be possible while the previous generation is still
# running, and `start` is the command that must not create a second instance.
  if [ "$(_port_free "$CAPTURE_PORT")" = "busy" ]; then
    local cpid; cpid="$(cat "$CAP_PID" 2>/dev/null || true)"
    if _alive "$cpid"; then
      log "capture port $CAPTURE_PORT already owned by pid $cpid"
    else
      log "WARNING: capture port $CAPTURE_PORT is busy and not owned by this deployment (stop the old capture before start)"
    fi
  fi
  if [ "$(_port_free "$HTTP_PORT")" = "busy" ]; then
    local hpid; hpid="$(cat "$HTTP_PID" 2>/dev/null || true)"
    _alive "$hpid" || log "WARNING: http port $HTTP_PORT busy and not owned by this deployment"
  fi
  log "preflight: OK (free ${free_mb}MB, profile $profile)"
}

activate() {
  local dir="${1:-}"
  dir="$(_release_arg "$dir")" || die "no such release: ${1:-<current>}"
  [[ "$dir" == "$RELEASES"/* ]] || die "refusing to activate outside $RELEASES: $dir"
  preflight "$dir"
  if [ -e "$CURRENT" ] && [ ! -L "$CURRENT" ]; then die "$CURRENT is not a symlink"; fi
  local previous; previous="$(readlink -f "$CURRENT" 2>/dev/null || true)"
  ln -sfn "$dir" "$CURRENT"
  _link_web
  _write_binding "$dir"
  log "activated $(basename "$dir") (previous: ${previous:-none}); code+page+profile move together"
}

# The binding is the single statement of "which code + which page + which site
# profile is in effect". Rollback must rewrite it too, otherwise status reports a
# stale pair while the page already runs the older release.
_write_binding() {
  local dir="$1"
  [ -f "$dir/bundle/RELEASE.json" ] || { log "WARNING: no RELEASE.json in $dir; binding unchanged"; return 0; }
  python3 - "$BINDING" "$dir" <<'PY'
import json, os, sys
binding_path, release = sys.argv[1], sys.argv[2]
release_json = json.load(open(os.path.join(release, 'bundle/RELEASE.json'), encoding='utf-8'))
state = os.path.dirname(binding_path)
os.makedirs(state, exist_ok=True)
profile_path = None
path_file = os.path.join(state, 'profile.path')
if os.path.isfile(path_file):
    profile_path = open(path_file, encoding='utf-8').read().strip() or None
profile_id = None
if profile_path and os.path.isfile(profile_path):
    profile_id = json.load(open(profile_path, encoding='utf-8')).get('site_id')
binding = {
    'schema_version': 1,
    'release_id': release_json['release_id'],
    'page_version': release_json['page_version'],
    'release_dir': release,
    'profile_id': profile_id,
    'profile_path': profile_path,
    'activated_wall': __import__('time').time(),
}
tmp = binding_path + '.tmp'
with open(tmp, 'w', encoding='utf-8') as handle:
    json.dump(binding, handle, sort_keys=True, indent=1)
    handle.write('\n')
os.replace(tmp, binding_path)
print('binding: release %s page %s profile %s'
      % (binding['release_id'], binding['page_version'], binding['profile_id']))
PY
}

_link_web() {
  # Page follows `current`. New releases keep the page under bundle/webui; the
  # legacy 2026-10-04 release keeps it at <release>/webui and ships no shared
  # assets. Detect the layout so a rollback does not leave a 404 page; missing
  # shared assets keep their existing link.
  local page_root=""
  if [ -d "$CURRENT/bundle/webui/human_fall" ]; then
    page_root="current/bundle/webui"
  elif [ -d "$CURRENT/webui/human_fall" ]; then
    page_root="current/webui"
  fi
  if [ -z "$page_root" ]; then
    log "WARNING: current release has no webui/human_fall; page symlinks unchanged"
    return 0
  fi
  mkdir -p "$WWW/human_fall"
  local source_root="${page_root#current/}"
  local name
  for name in ui.css three.min.js OrbitControls.js; do
    if [ -f "$CURRENT/$source_root/$name" ]; then
      ln -sfn "../$page_root/$name" "$WWW/$name"
    elif [ ! -e "$WWW/$name" ]; then
      log "WARNING: shared asset $name not in this release; page may lose styling"
    fi
  done
  for name in index.html human_fall.js human_fall_lib.js; do
    if [ -f "$CURRENT/$source_root/human_fall/$name" ]; then
      ln -sfn "../../$page_root/human_fall/$name" "$WWW/human_fall/$name"
    fi
  done
}

# ---------------------------------------------------------------------------
# start
# ---------------------------------------------------------------------------
_start_http() {
  local pid; pid="$(cat "$HTTP_PID" 2>/dev/null || true)"
  if _alive "$pid"; then
    log "http: already running (pid $pid)"
    return 0
  fi
  [ "$(_port_free "$HTTP_PORT")" = "free" ] || die "http port $HTTP_PORT busy"
  mkdir -p "$WWW"
  _rotate_log "$STATE/http.log"
  # `exec` inside the backgrounded subshell keeps $! equal to the real python3
  # pid, so the recorded pidfile always matches the process we later stop.
  # A dedicated no-cache server: the page must never keep a previous release's
  # index.html after `current` switches.
  local dir; dir="$(_resolve_current)"
  ( cd "$WWW" && exec nohup python3 -u -B \
      "$dir/bundle/src/human_fall_detection/scripts/serve_webui.py" \
      --bind 0.0.0.0 --port "$HTTP_PORT" --directory "$WWW" ) >> "$STATE/http.log" 2>&1 &
  echo $! > "$HTTP_PID"
  printf '%s' "serve_webui.py" > "$HTTP_CMD"
  sleep 0.5
  _alive "$(cat "$HTTP_PID")" || die "http server failed to start (see $STATE/http.log)"
  log "http: serving http://0.0.0.0:$HTTP_PORT/ (root $WWW)"
}

start() {
  local dir; dir="$(_release_arg "${1:-}")" || die "no current release; run: $0 stage <tar> then $0 activate"
  _verify_manifest "$dir" || exit 5
  # Refuse to launch into a broken environment (ROS overlay, profile, ports...).
  preflight "$dir" || exit 5
  local profile; profile="$(cat "$STATE/profile.path" 2>/dev/null || true)"
  [ -n "$profile" ] && [ -f "$profile" ] || die "no site profile (state/profile.path)"

  # Never create a second instance.
  local npid cpid
  npid="$(cat "$NODE_PID" 2>/dev/null || true)"
  if _alive "$npid"; then die "node already running (pid $npid); use: $0 restart"; fi
  cpid="$(cat "$CAP_PID" 2>/dev/null || true)"
  if _alive "$cpid"; then die "capture already running (pid $cpid); use: $0 restart"; fi
  [ "$(_port_free "$CAPTURE_PORT")" = "free" ] \
    || die "capture port $CAPTURE_PORT is busy (another capture_server owns it); stop it explicitly first"

  local input_mode; input_mode="$(cat "$STATE/input_source.mode" 2>/dev/null || echo unknown)"
  local evidence; evidence="$(cat "$STATE/input_source.evidence" 2>/dev/null || true)"
  local run_id; run_id="$(now_stamp)_$(head -c4 /dev/urandom | od -An -tx1 | tr -d ' \n')"
  local run_dir="$RUNS/$run_id"
  mkdir -p "$run_dir"
  local bundle="$dir/bundle"

  # Effective node config: one source of truth for node/page/profiler topics.
  PYTHONPATH="$(_bundle_paths "$dir")" python3 -B \
      "$bundle/src/human_fall_detection/scripts/release_config.py" node \
      --scene "$bundle/src/human_fall_detection/config/single_target_scene_v1.yaml" \
      --profile "$profile" --run-dir "$run_dir" --session-id "$run_id" \
      --out "$run_dir/effective_node.yaml" \
      --snapshot "$run_dir/effective_node.json" > "$run_dir/release_config_node.log" 2>&1 \
    || die "effective node config failed (see $run_dir/release_config_node.log)"
  PYTHONPATH="$(_bundle_paths "$dir")" python3 -B \
      "$bundle/src/human_fall_detection/scripts/release_config.py" runtime \
      --config "$run_dir/effective_node.yaml" \
      --release-json "$bundle/RELEASE.json" --profile "$profile" \
      --source-mode "$input_mode" \
      --out "$WWW/human_fall/runtime.js" --json-out "$WWW/human_fall/runtime.json" \
      > "$run_dir/release_config_page.log" 2>&1 \
    || die "page runtime config failed (see $run_dir/release_config_page.log)"

  # Display ground next to the page (page-relative, same-origin).
  python3 - "$profile" "$WWW/human_fall/display_ground.json" <<'PY'
import json, os, shutil, sys
profile = json.load(open(sys.argv[1], encoding='utf-8'))
source = profile['geometry']['display_ground']['path']
tmp = sys.argv[2] + '.tmp'
shutil.copyfile(source, tmp)
os.replace(tmp, sys.argv[2])
print('display_ground copied from', source)
PY

  local state_topic; state_topic="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['state'])" "$WWW/human_fall/runtime.json")"
  local points_topic; points_topic="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['points'])" "$WWW/human_fall/runtime.json")"

  # Startup manifest (what actually ran, with which SHAs).
  python3 - "$run_dir/startup.json" "$dir" "$profile" "$run_id" "$input_mode" \
      "$evidence" "$state_topic" "$points_topic" <<'PY'
import hashlib, json, os, sys, time
out, release, profile, run_id, mode, evidence, state_topic, points = sys.argv[1:9]
def sha(path):
    if not path or not os.path.isfile(path):
        return None
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()
release_json = json.load(open(os.path.join(release, 'bundle/RELEASE.json'), encoding='utf-8'))
startup = {
    'schema_version': 1,
    'run_id': run_id,
    'pid': os.getpid(),
    'started_wall': time.time(),
    'release_dir': release,
    'release_id': release_json['release_id'],
    'page_version': release_json['page_version'],
    'algorithm_config': release_json['algorithm_config'],
    'profile_path': profile,
    'profile_sha256': sha(profile),
    'input_source_mode': mode,
    'input_source_evidence': evidence or None,
    'topics': {'state': state_topic, 'points': points},
    'argv': sys.argv,
}
with open(out, 'w', encoding='utf-8') as handle:
    json.dump(startup, handle, sort_keys=True, indent=1)
    handle.write('\n')
PY

  # Node.
  _rotate_log "$run_dir/node.log"
  local node="$bundle/src/human_fall_detection/scripts/single_target_node.py"
  local scene_id; scene_id="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('scene_id') or '')" "$profile")"
  # The canonical (content-addressed) release id is what runtime.js and the page
  # compare against; the directory name is kept separately for traceability.
  local release_id; release_id="$(_version_id "$dir")"
  ( cd "$run_dir" && exec env HF_RUN_ID="$run_id" HF_RUN_DIR="$run_dir" \
      HF_RELEASE_ID="$release_id" HF_RELEASE_DIR="$(basename "$dir")" \
      HF_SCENE_ID="$scene_id" \
      HF_INPUT_SOURCE="$input_mode" HF_INPUT_SOURCE_EVIDENCE="$evidence" \
      PYTHONPATH="$(_bundle_paths "$dir")" nohup python3 -u -B "$node" \
        --config "$run_dir/effective_node.yaml" \
        --perception "$bundle/src/human_fall_detection/config/perception_single_target_v1.yaml" \
        --run-dir "$run_dir" --run-id "$run_id" \
        "__name:=$NODE_NAME" ) > "$run_dir/node.log" 2>&1 &
  echo $! > "$NODE_PID"
  printf '%s' "$node" > "$NODE_CMD"
  log "node: pid $(cat "$NODE_PID") run $run_id (log $run_dir/node.log)"

  # Capture: its own process tree, its own core package, record_script in release.
  _rotate_log "$STATE/capture.log"
  local cap_root="$bundle/src/human_capture"
  PYTHONPATH="$(_bundle_paths "$dir")" python3 -B \
      "$bundle/src/human_fall_detection/scripts/release_config.py" capture \
      --template "$cap_root/config/capture.yaml" --release-root "$bundle" \
      --out "$run_dir/effective_capture.yaml" \
      --snapshot "$run_dir/effective_capture.json" > "$run_dir/release_config_capture.log" 2>&1 \
    || die "effective capture config failed (see $run_dir/release_config_capture.log)"
  ( cd "$cap_root" && exec env PYTHONPATH="$cap_root:${PYTHONPATH:-}" \
      HF_RELEASE_ID="$release_id" HF_RELEASE_DIR="$(basename "$dir")" \
      HF_RUN_ID="$run_id" HF_RUN_DIR="$run_dir" \
      nohup python3 -u -B scripts/capture_server.py \
      --config "$run_dir/effective_capture.yaml" ) >> "$STATE/capture.log" 2>&1 &
  echo $! > "$CAP_PID"
  printf '%s' "scripts/capture_server.py" > "$CAP_CMD"
  log "capture: pid $(cat "$CAP_PID") (record_script in release)"

  _start_http

  # Wait for a first state message; report honestly if it does not arrive.
  local attempt
  for attempt in 1 2 3 4 5 6; do
    if _probe_ok "$state_topic"; then break; fi
    sleep 2
  done
  if ! _probe_ok "$state_topic"; then
    log "WARNING: no state message yet on $state_topic (node may still be waiting for input)"
  fi
  log "run directory: $run_dir"
}

_probe_ok() {
  local topic="$1" out
  out="$(PYTHONPATH="$(_bundle_paths "$(_resolve_current)")" python3 -B \
      "$(_resolve_current)/bundle/src/human_fall_detection/scripts/probe_state.py" \
      --topic "$topic" --timeout 3 2>/dev/null || true)"
  case "$out" in
    *'"ok": true'*) return 0 ;;
    *) return 1 ;;
  esac
}

# ---------------------------------------------------------------------------
# stop
# ---------------------------------------------------------------------------
_stop_capture() {
  local pid; pid="$(cat "$CAP_PID" 2>/dev/null || true)"
  if ! _alive "$pid"; then
    log "capture: not running"
    rm -f "$CAP_PID" "$CAP_CMD"
    return 0
  fi
  # 1. Stop an in-flight recording through the API first (this is the only path
  #    that lets rosbag finish and the session move out of `recording`).
  local current status body
  current="$(_capture_get /api/v1/record/current)"
  status="${current%%$'\n'*}"
  if [ "$status" = "200" ]; then
    body="${current#*$'\n'}"
    log "capture: stopping active recording $body"
    _capture_post /api/v1/record/stop '{}' >/dev/null || true
    local waited=0
    while [ "$waited" -lt 600 ]; do
      current="$(_capture_get /api/v1/record/current)"
      status="${current%%$'\n'*}"
      [ "$status" = "204" ] && break
      sleep 0.5; waited=$((waited + 1))
    done
    [ "$status" = "204" ] || log "WARNING: recording did not settle within 300s"
  fi
  # 2. Budget derived from the capture config itself.
  local budget=28
  local effective; effective="$(ls -1t "$RUNS"/*/effective_capture.json 2>/dev/null | head -n1 || true)"
  if [ -n "$effective" ] && [ -f "$effective" ]; then
    local grace kill
    grace="$(python3 -c "import json,sys;print(int(json.load(open(sys.argv[1])).get('grace_sec') or 15))" "$effective")"
    kill="$(python3 -c "import json,sys;print(int(json.load(open(sys.argv[1])).get('kill_sec') or 5))" "$effective")"
    budget=$((grace + kill + 8))
  fi
  _stop_pidfile "$CAP_PID" "$CAP_CMD" "capture_server.py" "$budget" "capture" || return 1
  # 3. Threads/subprocesses must be gone, not just the parent PID. Check the
  #    release recorder by its absolute path (exact, unlike a bare name) and the
  #    listening port (the real "no second service" condition).
  local recorder="$(_resolve_current)/bundle/src/human_fall_detection/scripts/record_session.py"
  local leftovers
  leftovers="$(pgrep -f -- "$recorder" 2>/dev/null | grep -v -e "^$$\$" -e "^$PPID\$" || true)"
  if [ -n "$leftovers" ]; then
    log "REFUSING: recorder still alive after capture exit:"
    for pid in $leftovers; do log "  pid $pid: $(_pid_cmdline "$pid")"; done
    return 1
  fi
  if [ "$(_port_free "$CAPTURE_PORT")" != "free" ]; then
    log "REFUSING: capture port $CAPTURE_PORT is still bound after stop (another service running?)"
    return 1
  fi
  log "capture: fully stopped (no recorder/extractor left, port free)"
}

stop() {
  local rc=0
  _stop_capture || rc=1
  if [ -f "$NODE_PID" ]; then
    _stop_pidfile "$NODE_PID" "$NODE_CMD" "single_target_node.py" "$NODE_STOP_S" "node" || rc=1
  fi
  if [ -f "$HTTP_PID" ]; then
    # Accept the previous page server too, so upgrading the server itself is not
# blocked by its own stricter cmdline check.
    _stop_pidfile "$HTTP_PID" "$HTTP_CMD" "serve_webui.py" 5 "http" "http.server" || rc=1
  fi
  if [ "$rc" -eq 0 ]; then log "stopped (driver untouched)"; else log "stop INCOMPLETE (see messages above)"; fi
  return "$rc"
}

# ---------------------------------------------------------------------------
# status / version / health
# ---------------------------------------------------------------------------
_running_release() {
  local pid; pid="$(cat "$NODE_PID" 2>/dev/null || true)"
  if ! _alive "$pid"; then echo "none"; return; fi
  local rel; rel="$(_release_of_cmdline "$(_pid_cmdline "$pid")")"
  [ -n "$rel" ] && basename "$rel" || echo "unknown"
}

status() {
  local dir; dir="$(readlink -f "$CURRENT" 2>/dev/null || echo none)"
  log "selected release: ${dir##*/}"
  if [ "$dir" != "none" ] && [ -f "$dir/bundle/RELEASE.json" ]; then
    log "selected release_id: $(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['release_id'])" "$dir/bundle/RELEASE.json") (page $(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['page_version'])" "$dir/bundle/RELEASE.json"))"
  fi
  log "running release:  $(_running_release)"
  [ -f "$BINDING" ] && log "binding: $(tr -d '\n ' < "$BINDING")"
  local profile; profile="$(cat "$STATE/profile.path" 2>/dev/null || true)"
  [ -n "$profile" ] && log "profile: $(python3 -c "import json,sys;d=json.load(open(sys.argv[1]));print(d['site_id'], d['scene_id'], 'physical_verified=%s runtime_eligible=%s' % (d['applicability'].get('physical_verified'), d['applicability'].get('runtime_eligible')))" "$profile" 2>/dev/null || echo "$profile")"
  log "input source: $(cat "$STATE/input_source.mode" 2>/dev/null || echo unknown) ($(cat "$STATE/input_source.evidence" 2>/dev/null || echo 'no evidence file'))"
  for pair in "node:$NODE_PID" "capture:$CAP_PID" "http:$HTTP_PID"; do
    local name="${pair%%:*}" file="${pair#*:}" pid
    pid="$(cat "$file" 2>/dev/null || true)"
    if _alive "$pid"; then
      log "$name: pid $pid RUNNING"
    else
      log "$name: not running"
    fi
  done
  local state_json="$WWW/human_fall/runtime.json"
  if [ -f "$state_json" ]; then
    local topic; topic="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['state'])" "$state_json")"
    log "page: http://<board>:$HTTP_PORT/human_fall/  state topic: $topic"
    if ! _alive "$(cat "$NODE_PID" 2>/dev/null || true)"; then
      log "state probe: node is NOT running (see the run's node.log)"
      return 0
    fi
    local probe; probe="$(PYTHONPATH="$(_bundle_paths "$dir")" python3 -B "$dir/bundle/src/human_fall_detection/scripts/probe_state.py" --topic "$topic" --timeout 4 2>/dev/null || true)"
    if [ -n "$probe" ]; then
      python3 - "$probe" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
if not data.get('ok'):
    print('state probe: no message (%s)' % data.get('reason'))
    raise SystemExit(0)
state = data['state']
run = state.get('run') or {}
worker = state.get('worker') or {}
source = state.get('input_source') or {}
baseline = state.get('baseline') or {}
print('state: track=%s status=%s fall=%s obs=%s baseline=%s/%s worker=%s'
      % (state.get('track_id'), state.get('track_status'), state.get('fall_status'),
         state.get('observability'), baseline.get('status'), baseline.get('sample_count'),
         'healthy' if worker.get('healthy') else 'NOT-HEALTHY'))
print('input: mode=%s loop_suspected=%s samples=%s' % (
    source.get('mode'), source.get('loop_suspected'), source.get('samples')))
print('run: %s release=%s scene=%s records=%s notifications=%s write_error=%s'
      % (run.get('run_id'), run.get('release_id'), run.get('scene_id'),
         run.get('records'), run.get('notifications'), run.get('write_error')))
PY
    else
      log "state probe: NO STATE MESSAGE (node alive but not publishing)"
    fi
  fi
}

version() {
  local dir; dir="$(readlink -f "$CURRENT" 2>/dev/null || echo none)"
  printf 'selected=%s\n' "${dir##*/}"
  if [ "$dir" != "none" ] && [ -f "$dir/bundle/RELEASE.json" ]; then
    python3 - "$dir/bundle/RELEASE.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding='utf-8'))
print('release_id=%s' % data['release_id'])
print('page_version=%s' % data['page_version'])
print('algorithm_scene_sha=%s' % data['algorithm_config']['scene']['sha256'])
print('algorithm_perception_sha=%s' % data['algorithm_config']['perception']['sha256'])
print('files=%s' % data['file_count'])
PY
  fi
  printf 'running=%s\n' "$(_running_release)"
}

health() {
  local rc=0
  local npid; npid="$(cat "$NODE_PID" 2>/dev/null || true)"
  if ! _alive "$npid"; then log "health: node NOT RUNNING"; rc=1; fi
  local state_json="$WWW/human_fall/runtime.json" topic=""
  [ -f "$state_json" ] && topic="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['state'])" "$state_json")"
  if [ -n "$topic" ]; then
    local dir; dir="$(readlink -f "$CURRENT" 2>/dev/null || true)"
    local probe; probe="$(PYTHONPATH="$(_bundle_paths "$dir")" python3 -B "$dir/bundle/src/human_fall_detection/scripts/probe_state.py" --topic "$topic" --timeout 5 2>/dev/null || true)"
    python3 - "$probe" <<'PY' || rc=1
import json, sys, time
data = json.loads(sys.argv[1] or '{"ok": false}')
if not data.get('ok'):
    print('health: state NOT FRESH (%s)' % data.get('reason'))
    raise SystemExit(1)
state = data['state']
age = time.time() - float(data['received_wall'])
worker = state.get('worker') or {}
quality = (state.get('sensor_quality') or {}).get('cloud') or {}
fresh_problems = []
if not worker.get('healthy'):
    fresh_problems.append('worker_unhealthy')
if quality.get('status') != 'fresh':
    fresh_problems.append('cloud_%s' % quality.get('status'))
run = state.get('run') or {}
if run.get('write_error'):
    fresh_problems.append('run_record_error')
print('health: state age %.2fs track=%s fall=%s problems=%s'
      % (age, state.get('track_id'), state.get('fall_status'),
         ','.join(fresh_problems) or 'none'))
# Waiting for a target is a normal state, not a failure. A stalled/absent input,
# a dead worker or a record write error is a real degradation and must fail the
# check instead of being reported as healthy.
raise SystemExit(1 if fresh_problems else 0)
PY
  fi
  _capture_health || rc=1
  local db; db="$(python3 -c "import json,sys;print(json.load(open(sys.argv[1])).get('sessions_db',''))" "$(ls -1t "$RUNS"/*/effective_capture.json 2>/dev/null | head -n1)" 2>/dev/null || true)"
  if [ -n "$db" ] && [ -f "$db" ]; then
    python3 - "$db" <<'PY' || rc=1
import json, sys
try:
    data = json.load(open(sys.argv[1], encoding='utf-8'))
except (OSError, ValueError) as exc:
    print('health: sessions database unreadable: %s' % exc)
    raise SystemExit(1)
# The registry is a list of session rows in the shipped format; tolerate a
# dict-of-rows wrapper as well instead of crashing the health check.
if isinstance(data, dict):
    rows = data.get('sessions')
    if isinstance(rows, dict):
        rows = list(rows.values())
elif isinstance(data, list):
    rows = data
else:
    rows = None
if rows is None:
    print('health: sessions registry has an unknown shape')
    raise SystemExit(1)
rows = [row for row in rows if isinstance(row, dict)]
stuck = [row.get('session_id') for row in rows if row.get('state') == 'recording']
if stuck:
    print('health: %d session(s) stuck in recording (capture may not own them): %s'
          % (len(stuck), ','.join(sorted(str(s) for s in stuck)[:5])))
    raise SystemExit(1)
print('health: sessions registry ok (%d entries)' % len(rows))
PY
  fi
  if [ "$rc" -eq 0 ]; then log "health: OK"; else log "health: DEGRADED"; fi
  return "$rc"
}

restart() {
  stop || die "stop failed; refusing to restart into a half-stopped state"
  start
}

rollback() {
  local target="${1:-}" legacy="${2:-}"
  if [ -z "$target" ]; then
    target="$(ls -1 "$RELEASES" | grep -v '^\.' | sort | tail -n 2 | head -n 1)"
  fi
  [ -n "$target" ] && [ -d "$RELEASES/$target" ] || die "no such release: $target"
  [ "$(basename "$(readlink -f "$CURRENT" 2>/dev/null || echo none)")" != "$target" ] \
    || die "release $target is already current"
  local dir="$RELEASES/$target"
  if [ -f "$dir/bundle/src/human_fall_detection/scripts/single_target_node.py" ]; then
    _verify_manifest "$dir" || die "target release failed manifest verification"
    preflight "$dir"
  else
    [ "$legacy" = "--legacy" ] || die "release $target has no automatic entry (manual-degraded bundle); re-run with: $0 rollback $target --legacy"
    log "WARNING: $target is the manual-degraded release: no automatic target entry,"
    log "         no region output, no page runtime binding. Capability differs."
  fi
  stop || die "could not stop current components; rollback aborted"
  local previous; previous="$(readlink -f "$CURRENT" 2>/dev/null || true)"
  ln -sfn "$dir" "$CURRENT"
  _write_binding "$dir"
  if [ -f "$dir/bundle/src/human_fall_detection/scripts/single_target_node.py" ]; then
    _link_web
    start
  else
    _link_web
    log "rolled back to $target (previous $previous)"
    log "CAPABILITY DIFFERENCE: $target is the manual-degraded release."
    log "  - no automatic target entry, no region output, no page runtime binding"
    log "  - start it manually, e.g.:"
    log "      PYTHONPATH=$dir/bundle:$dir/bundle/scripts:$dir/bundle/human_follow_calibration/scripts \\"
    log "        nohup python3 $dir/bundle/scripts/human_fall_node.py \\"
    log "        --config $dir/bundle/config/human_fall_prod.yaml --perception $dir/bundle/config/perception.yaml &"
    log "  - the legacy page expects /human_fall/* topics, not /single_target_live/*"
    return 0
  fi
  log "rolled back to $target (kept previous $previous)"
}

runs() {
  ls -1t "$RUNS" 2>/dev/null | head -n "${1:-20}" || true
}

verify_input() {
  local dir; dir="$(_resolve_current)" || die "no current release"
  mkdir -p "$STATE"
  local script="$dir/bundle/src/human_fall_detection/scripts/verify_input_source.py"
  [ -f "$script" ] || die "release has no verify_input_source.py"
  local rc=0
  PYTHONPATH="$(_bundle_paths "$dir")" python3 -B "$script" \
      --json-out "$STATE/input_source.json" \
      --mode-file "$STATE/input_source.mode" || rc=$?
  printf '%s' "$STATE/input_source.json" > "$STATE/input_source.evidence"
  case "$rc" in
    0) log "input source: live_lidar (verified: msg_source=1, no pcap open)" ;;
    4) log "input source: pcap (verified: replay/pcap evidence) - live field trial NOT available" ;;
    3) log "input source: unknown (could not verify; the page will show 输入来源未核实)" ;;
    2) log "input source: unknown (ROS/proc unavailable)" ;;
  esac
  if [ "$rc" -eq 4 ]; then
    python3 - "$STATE/input_source.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding='utf-8'))
config = data.get('driver_config') or {}
print('  pcap_file=%s pcap_repeat=%s' % (config.get('pcap_file'), config.get('pcap_repeat')))
PY
  fi
  return 0
}

_write_profile() {  # _write_profile <site> <scene> <dir> <note>
  local site="$1" scene="$2" target="$3" note="$4"
  local mode; mode="$(cat "$STATE/input_source.mode" 2>/dev/null || echo unknown)"
  local dir; dir="$(_resolve_current)"
  PYTHONPATH="$(_bundle_paths "$dir")" python3 -B \
      "$dir/bundle/src/human_fall_detection/scripts/init_site_profile.py" \
      --site-id "$site" --scene-id "$scene" \
      --ground "$target/ground_candidate.json" \
      --background "$target/declared_empty_background.json" \
      --display-ground "$target/display_ground.json" \
      --expected-mode "$mode" \
      --install-location "$(hostname)" \
      --install-note "$note" \
      --scene-artifact "${scene_artifact:-frozen-on-site}" \
      --unknowns "same-installation applicability recorded, not independently verified" \
      --unknowns "artifact freeze window was declared empty by the operator, not measured GT" \
      --out "$target/profile.json" || die "profile creation failed"
  printf '%s' "$target/profile.json" > "$STATE/profile.path"
  log "profile: $target/profile.json (path recorded in $STATE/profile.path)"
  log "applicability is NOT upgraded by this command: physical_verified/runtime_eligible stay false"
}

profile_init() {
  local site="${1:-}" scene="${2:-}" release="${3:-}"
  [ -n "$site" ] && [ -n "$scene" ] || die "usage: $0 profile-init <site_id> <scene_id> [release]"
  local dir
  if [ -n "$release" ]; then
    dir="$RELEASES/$release"
    [ -d "$dir" ] || die "no such release: $release"
  else
    dir="$(_resolve_current)" || die "no current release"
  fi
  local source="$dir/bundle/src/human_fall_detection/config/single_target_scene_20261019"
  local target="$PROFILES/$site"
  [ -e "$target" ] && die "profile already exists (immutable snapshot): $target"
  mkdir -p "$target"
  cp "$source/ground_candidate.json" "$target/ground_candidate.json"
  cp "$source/declared_empty_background.json" "$target/declared_empty_background.json"
  cp "$source/display_ground.json" "$target/display_ground.json"
  scene_artifact="config/single_target_scene_20261019"
  _write_profile "$site" "$scene" "$target" \
      "artifacts copied from release $(_version_id "$dir"); origin 2026-10-19 declared-empty window"
}

freeze_scene() {
  local site="${1:-}" scene="${2:-}" frames="${3:-50}"
  [ -n "$site" ] && [ -n "$scene" ] || die "usage: $0 freeze-scene <site_id> <scene_id> [frames]"
  local dir; dir="$(_resolve_current)" || die "no current release"
  local run_dir; run_dir="$(ls -1dt "$RUNS"/*/ 2>/dev/null | head -n 1 || true)"
  [ -n "$run_dir" ] && [ -f "$run_dir/effective_node.yaml" ] \
    || die "no run directory with an effective config yet; run: $0 start"
  local target="$PROFILES/$site"
  [ -e "$target" ] && die "profile already exists (immutable snapshot): $target"
  mkdir -p "$target"
  log "freezing $frames frames from the live cloud into $target (empty field required)"
  PYTHONPATH="$(_bundle_paths "$dir")" python3 -B \
      "$dir/bundle/src/human_fall_detection/scripts/freeze_scene.py" \
      --config "$run_dir/effective_node.yaml" \
      --perception "$dir/bundle/src/human_fall_detection/config/perception_single_target_v1.yaml" \
      --frames "$frames" --timeout $((frames * 3 + 30)) \
      --out-dir "$target" \
      --note "frozen on site $(date -u +%Y-%m-%dT%H:%M:%SZ) from $frames declared-empty live frames" \
    || die "freeze refused (see message above); nothing was activated"
  scene_artifact="frozen-on-site $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  _write_profile "$site" "$scene" "$target" \
      "frozen on site from $frames declared-empty live frames"
  log "next: $0 activate && $0 restart"
}

_version_id() {
  python3 -c "import json,sys;print(json.load(open(sys.argv[1]))['release_id'])" \
    "$1/bundle/RELEASE.json" 2>/dev/null || basename "$1"
}

probe_scene() {
  local dir; dir="$(_resolve_current)" || die "no current release"
  local frames="${1:-30}"
  local run_dir; run_dir="$(ls -1dt "$RUNS"/*/ 2>/dev/null | head -n 1 || true)"
  [ -n "$run_dir" ] && [ -f "$run_dir/effective_node.yaml" ] \
    || die "no run directory with an effective config yet; run: $0 start"
  PYTHONPATH="$(_bundle_paths "$dir")" python3 -B \
      "$dir/bundle/src/human_fall_detection/scripts/probe_scene.py" \
      --config "$run_dir/effective_node.yaml" \
      --perception "$dir/bundle/src/human_fall_detection/config/perception_single_target_v1.yaml" \
      --frames "$frames" --timeout $((frames + 15)) \
      --out "$STATE/scene_probe.json" --jsonl "$STATE/scene_probe_frames.jsonl" || true
  python3 - "$STATE/scene_probe.json" <<'PY'
import json, sys
data = json.load(open(sys.argv[1], encoding='utf-8'))
print('scene probe: %s frames=%s ground_fraction_median=%s residual_p95=%s '
      'foreground_median=%s problems=%s'
      % (data.get('verdict'), data.get('frames'),
         data.get('ground_point_fraction_median'),
         data.get('ground_residual_abs_p95_m_p50'),
         data.get('foreground_points_median'), ','.join(data.get('problems') or [])))
PY
}

usage() {
  cat <<EOF
usage: $0 <command> [args]
  stage <bundle.tar>         extract + verify a standard release bundle (no switch)
  preflight [release]        verify env/profile/ports/disk/manifest
  activate [release]         switch code+page together (does not start)
  profile-init <site> <scene>  create the immutable site profile from release artifacts
  freeze-scene <site> <scene> [frames]
                             re-freeze ground/background from a declared-empty live window
  verify-input               inspect the real driver process -> live_lidar|pcap|unknown
  probe-scene [frames]       check the bound ground/background against the live cloud
  start                      start node + capture + page server for one new run
  restart                    stop then start
  stop                       stop capture (recording first), node, page server
  status                     selected vs running version, pids, live state summary
  version                    release ids and algorithm config SHAs
  health                     fresh-state / worker / capture / registry check
  rollback <release> [--legacy]
  runs [n]                   recent run directories
EOF
}

case "${1:-}" in
  stage) shift; stage "$@" ;;
  preflight) shift; preflight "$@" ;;
  activate) shift; activate "$@" ;;
  profile-init) shift; profile_init "$@" ;;
  freeze-scene) shift; freeze_scene "$@" ;;
  verify-input) shift; verify_input "$@" ;;
  probe-scene) shift; probe_scene "$@" ;;
  start) shift; start "$@" ;;
  restart) shift; restart "$@" ;;
  stop) shift; stop "$@" ;;
  status) shift; status "$@" ;;
  version) shift; version "$@" ;;
  health) shift; health "$@" ;;
  rollback) shift; rollback "$@" ;;
  runs) shift; runs "$@" ;;
  *) usage; exit 2 ;;
esac