"""R7 运行中的冻结 Console.exe 行为探针（不靠字符串搜索判断代码是否打进 exe）。

思路：R8 新增了 GET /api/camera（会话无相机录像时回 `没有这个会话的相机视频`），
通用未命中路由回 `not found`；两个文案不同，所以「路由存在与否」可以在运行中的
exe 上直接观测。纯 stdlib；只读 GET。
"""
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXE = HERE.parents[3] / 'pc_apps' / 'console' / 'dist' / 'Console.exe'


def console_pids():
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq Console.exe', '/FO', 'CSV'],
                         capture_output=True).stdout.decode('gbk', 'replace')
    return [int(m.group(1)) for m in re.finditer(r'"Console\.exe","(\d+)"', out)]


def listen_ports(pids):
    out = subprocess.run(['netstat', '-ano', '-p', 'TCP'],
                         capture_output=True).stdout.decode('gbk', 'replace')
    ports = set()
    for line in out.splitlines():
        m = re.match(r'\s+TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)', line)
        if m and int(m.group(2)) in pids:
            ports.add(int(m.group(1)))
    return sorted(ports)


def get(url):
    try:
        with urllib.request.urlopen(url, timeout=4) as resp:
            return resp.status, resp.read().decode('utf-8', 'replace')
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode('utf-8', 'replace')


lines = ['运行中的冻结 Console.exe 行为探针（不是字符串搜索）']
if EXE.is_file():
    import hashlib
    lines.append('exe: %s  %dB  sha256=%s' % (EXE, EXE.stat().st_size,
                                              hashlib.sha256(EXE.read_bytes()).hexdigest().upper()))
pids = console_pids()
lines.append('console pids: %s' % (pids or 'NONE'))
if not pids:
    lines.append('结论：Console.exe 未在运行，探针 NOT_RUN')
    (HERE / 'RUNNING_EXE_PROBE.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('\n'.join(lines))
    sys.exit(1)

joint = None
for port in listen_ports(pids):
    status, body = get('http://127.0.0.1:%d/api/status' % port)
    if status == 200 and 'output_root' in body:
        joint = port
        lines.append('joint service port = %d' % port)
        lines.append('  /api/status = %s' % body.strip())
        break
if not joint:
    lines.append('结论：没找到本机联合录制服务端口')
else:
    for q in ('sid=cap_20261015_142730', 'sid=../etc', 'sid='):
        status, body = get('http://127.0.0.1:%d/api/camera?%s' % (joint, q))
        lines.append('GET /api/camera?%s -> %d %s' % (q, status, body.strip()))
    status, body = get('http://127.0.0.1:%d/api/bogus' % joint)
    lines.append('GET /api/bogus（通用 404 对照）-> %d %s' % (status, body.strip()))
    status, page = get('http://127.0.0.1:%d/' % joint)
    lines.append('page contains R7 文案(“不会再拉第二遍”) = %s' % ('不会再拉第二遍' in page))
    lines.append('page contains R8 文案(“camera_frames.jsonl”) = %s' % ('camera_frames.jsonl' in page))
    camera_route = '没有这个会话的相机视频' in get('http://127.0.0.1:%d/api/camera?sid=x' % joint)[1]
    lines.append('结论：/api/camera 路由%s在运行中的冻结 exe 内（通用未命中路由回 not found）'
                 % ('存在' if camera_route else '**不存在**'))
(HERE / 'RUNNING_EXE_PROBE.txt').write_text('\n'.join(lines) + '\n', encoding='utf-8')
print('\n'.join(lines))
