import hashlib
import json
import os
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
state = json.loads((OUT / "PRE_EDIT_STATE.json").read_text(encoding="utf-8"))
expected = {path: rec["sha256"] for path, rec in state["current_overlay"].items()}
gui = ROOT / "pc_apps/console/console_gui.py"
html = ROOT / "pc_apps/console/console.html"
spec = ROOT / "pc_apps/console/Console.spec"
backup_gui = OUT / "originals/console_gui.py"
backup_html = OUT / "originals/console.html"
backup_spec = OUT / "originals/Console.spec"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def normalize(path):
    return path.read_bytes().replace(b"\r\n", b"\n").decode("utf-8")


source = normalize(gui)
source = source.replace(
    "def _shell_url(port, fall_port=None, capture_port=None):",
    "def _shell_url(port, fall_port=None, capture_port=None, real_fall_port=None):",
    1,
)
source = source.replace(
    '    return url + ("&capture_port=%d" % capture_port if capture_port else "")',
    '    url += "&capture_port=%d" % capture_port if capture_port else ""\n'
    '    return url + ("&real_fall_port=%d" % real_fall_port if real_fall_port else "")',
    1,
)
fall_end = (
    "    threading.Thread(target=server.serve_forever, daemon=True).start()\n"
    "    return server.server_address[1]\n\n\n"
    "def _is_valid_source_dir(d):"
)
real_server = '''    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]


def _start_real_fall_server():
    """启动真实录制 r04 离线回放；缺少数据时不影响其他控制台入口。"""
    root = (os.path.dirname(os.path.dirname(_frozen_capture_root()))
            if getattr(sys, "frozen", False) else os.path.dirname(os.path.dirname(HERE)))
    source_dir = os.path.join(root, "sidequests", "human_fusion_lab_next", "real_fall", "r04")
    if not os.path.isfile(os.path.join(source_dir, "server.py")):
        return None
    sys.path.insert(0, source_dir)
    try:
        module = runpy.run_path(os.path.join(source_dir, "server.py"))
        server = module["ThreadingHTTPServer"](("127.0.0.1", 0), module["Handler"])
    except (OSError, ValueError, ImportError, KeyError) as exc:
        print("real fall replay unavailable: %s" % exc)
        return None
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server.server_address[1]


def _is_valid_source_dir(d):'''
assert source.count(fall_end) == 1
source = source.replace(fall_end, real_server, 1)
old_check = '''            report["replay_port"] = _start_replay_server()
            report["fall_port"] = _start_fall_server()
            if not report["fall_port"]:
                raise ValueError("fall replay did not start")
            with urllib.request.urlopen("http://127.0.0.1:%d/api/info" % report["fall_port"]) as response:
                info = json.load(response)
            report["sessions"] = info["sessions"]
            sid = report['sessions'][0]['session_id']
            with urllib.request.urlopen("http://127.0.0.1:%d/api/frame?sid=%s&fi=0&dataset=actions" % (report["fall_port"],sid)) as response:
                frame = json.load(response)
            report['dataset'] = info['dataset']
            report["alarm_frame"] = frame['frame_index']
            report['target_points'] = frame['body_3d'][0]['point_count']
            report["skeleton_nodes"] = len(frame['body_3d'][0]['skeleton']['nodes'])
            report['confirmed_fall'] = frame['posture']['confirmed']
            report["shell_url"] = _shell_url(report["replay_port"], report["fall_port"])
            report["ok"] = report['dataset'] == 'actions' and report['target_points'] > 0 and report["skeleton_nodes"] == 13 and not report['confirmed_fall']'''
new_check = '''            report["replay_port"] = _start_replay_server()
            report["fall_port"] = _start_fall_server()
            report["real_fall_port"] = _start_real_fall_server()
            if not report["fall_port"]:
                raise ValueError("pointset replay did not start")
            if not report["real_fall_port"]:
                raise ValueError("real fall replay did not start")
            with urllib.request.urlopen("http://127.0.0.1:%d/api/info" % report["fall_port"]) as response:
                info = json.load(response)
            report["sessions"] = info["sessions"]
            sid = report['sessions'][0]['session_id']
            with urllib.request.urlopen("http://127.0.0.1:%d/api/frame?sid=%s&fi=0&dataset=actions" % (report["fall_port"],sid)) as response:
                frame = json.load(response)
            report['dataset'] = info['dataset']
            report["alarm_frame"] = frame['frame_index']
            report['target_points'] = frame['body_3d'][0]['point_count']
            report["skeleton_nodes"] = len(frame['body_3d'][0]['skeleton']['nodes'])
            report['confirmed_fall'] = frame['posture']['confirmed']
            real_url = "http://127.0.0.1:%d" % report["real_fall_port"]
            with urllib.request.urlopen(real_url + "/api/info") as response:
                real_info = json.load(response)
            real_sid = "cap_20261013_094333"
            empty_sid = "cap_20261013_131958"
            with urllib.request.urlopen(real_url + "/api/frame?sid=%s&i=72" % real_sid) as response:
                real_frame = json.load(response)
            with urllib.request.urlopen(real_url + "/api/frame?sid=%s&i=0" % empty_sid) as response:
                empty_frame = json.load(response)
            events = real_info["sessions"][real_sid]["events"]
            nodes = real_frame["row"]["skeleton"]["nodes"]
            report["real_fall"] = {
                "frames": real_info["sessions"][real_sid]["frames"],
                "frame": real_frame["row"]["frame"],
                "target_points": len(real_frame["target"]),
                "valid_nodes": sum(1 for node in nodes.values() if node.get("valid")),
                "alert_active": real_frame["row"]["alert_active"],
                "event_count": len(events),
                "event_verified": events[0].get("verified") if events else None,
                "empty_observed": empty_frame["row"]["observed"],
                "empty_events": len(real_info["sessions"][empty_sid]["events"]),
            }
            report["shell_url"] = _shell_url(
                report["replay_port"], report["fall_port"],
                real_fall_port=report["real_fall_port"],
            )
            report["ok"] = (
                report['dataset'] == 'actions' and report['target_points'] > 0
                and report["skeleton_nodes"] == 13 and not report['confirmed_fall']
                and report["real_fall"]["frames"] == 164
                and report["real_fall"]["frame"] == 72
                and report["real_fall"]["valid_nodes"] == 13
                and report["real_fall"]["alert_active"]
                and report["real_fall"]["event_count"] == 1
                and report["real_fall"]["event_verified"] is False
                and not report["real_fall"]["empty_observed"]
                and report["real_fall"]["empty_events"] == 0
            )'''
assert source.count(old_check) == 1
source = source.replace(old_check, new_check, 1)
source = source.replace(
    '    fall_port = _start_fall_server()\n    capture_server, recorder = _start_joint_capture_server()',
    '    fall_port = _start_fall_server()\n'
    '    real_fall_port = _start_real_fall_server()\n'
    '    capture_server, recorder = _start_joint_capture_server()',
    1,
)
source = source.replace(
    '        _shell_url(replay_port, fall_port, capture_server.server_port),',
    '        _shell_url(replay_port, fall_port, capture_server.server_port,\n'
    '                   real_fall_port=real_fall_port),',
    1,
)

page = normalize(html)
page = page.replace(
    'const fallBase = Number.isInteger(fallPort) && fallPort > 0 && fallPort <= 65535 ? "http://127.0.0.1:" + fallPort : null;',
    'const fallBase = Number.isInteger(fallPort) && fallPort > 0 && fallPort <= 65535 ? "http://127.0.0.1:" + fallPort : null;\n'
    'const realFallPort = Number(new URLSearchParams(location.search).get("real_fall_port"));\n'
    'const realFallBase = Number.isInteger(realFallPort) && realFallPort > 0 && realFallPort <= 65535 ? "http://127.0.0.1:" + realFallPort : null;',
    1,
)
old_card = '''  {name:"骨架与倒地检测", desc:"八段动作 · 中央人体 / 点支撑骨架 / 倒地姿态候选", icon:svg('<circle cx="12" cy="4" r="2"/><path d="M12 6v8m-6-5 6 2 6-2m-6 5-5 7m5-7 5 7"/>'), url:fallBase ? fallBase + "/" : "about:blank",
   unavailable:fallBase ? null : "当前工作区的真人回放数据未就绪，请在原工作区重新打开总控制台"},'''
new_card = old_card + '''
  {name:"真人倒地回放", desc:"真实录制 · 点支撑粗部位 / 未确认原型告警", icon:svg('<circle cx="12" cy="4" r="2"/><path d="M12 6v8m-6-5 6 2 6-2m-6 5-5 7m5-7 5 7"/>'), url:realFallBase ? realFallBase + "/" : "about:blank",
   unavailable:realFallBase ? null : "真实倒地回放数据未就绪，请从原工作区重新打开总控制台"},'''
assert page.count(old_card) == 1
page = page.replace(old_card, new_card, 1)
page = page.replace(
    '<link rel="icon" href="console_icon.png" type="image/png">',
    '<link rel="icon" href="console_icon.ico" type="image/x-icon">',
    1,
)

build_spec = normalize(spec)
build_spec = build_spec.replace(
    "datas=[('console.html', '.'), ('joint_capture.html', '.'), ('console_icon.png', '.'),",
    "datas=[('console.html', '.'), ('joint_capture.html', '.'), ('console_icon.ico', '.'),",
    1,
)
assert "('console_icon.png', '.')" not in build_spec

contents = {gui: source.encode("utf-8").replace(b"\n", b"\r\n"),
            html: page.encode("utf-8").replace(b"\n", b"\r\n"),
            spec: build_spec.encode("utf-8").replace(b"\n", b"\r\n")}
assert sha(gui) == expected["pc_apps/console/console_gui.py"]
assert sha(html) == expected["pc_apps/console/console.html"]
assert sha(spec) == expected["pc_apps/console/Console.spec"]
temps = {}
for path, data in contents.items():
    temp = path.with_name(path.name + ".hf-console-02.tmp")
    if temp.exists():
        raise FileExistsError(str(temp))
    temp.write_bytes(data)
    temps[path] = temp

applied = []
try:
    for path, temp in temps.items():
        os.replace(str(temp), str(path))
        applied.append(path)
except Exception:
    for path in applied:
        backup = backup_gui if path == gui else backup_html if path == html else backup_spec
        restore = path.with_name(path.name + ".hf-console-02-restore.tmp")
        shutil.copyfile(str(backup), str(restore))
        os.replace(str(restore), str(path))
    raise
finally:
    for temp in temps.values():
        if temp.exists():
            temp.unlink()

print(json.dumps({str(path.relative_to(ROOT)): sha(path) for path in contents}, indent=2))
