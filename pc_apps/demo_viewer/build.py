"""Create compact local viewers from the existing, unmodified replay outputs."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
SOURCE = ROOT / 'docs/evidence/2026-10-28_demo_four_sessions'
SESSIONS = [('houdao', '向后倒地'), ('qiandao', '向前倒地'),
            ('huanmandiedao', '缓慢倒地'), ('jixiedaiwanyao', '系鞋带与弯腰')]


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('unexpected source page: ' + old[:70])
    return text.replace(old, new, 1)


def build():
    manifest = {}
    for name, title in SESSIONS:
        source = SOURCE / ('replay_' + name)
        html = (source / 'index.html').read_text(encoding='utf-8')
        frames = source / 'data/frames.js'
        summary = json.loads((source / 'SUMMARY.json').read_text(encoding='utf-8'))
        prefix = '../../docs/evidence/2026-10-28_demo_four_sessions/replay_' + name + '/'
        nav = ''.join('<a class="%s" href="%s.html">%s</a>' %
                      ('active' if key == name else '', key, label)
                      for key, label in SESSIONS)
        html = replace_once(html, '<div class="wrap">', '<div class="wrap"><nav class="sessions">' + nav + '</nav>')
        html = replace_once(html, '<header>', '<header><div class="eyebrow">LIDAR · 离线回放</div>')
        import re
        html, count = re.subn(r'<h1>.*?</h1>', '<h1>' + title + '</h1>', html, count=1)
        if count != 1:
            raise ValueError('missing page title')
        html, count = re.subn(r'<title>.*?</title>', '<title>' + title + ' · 离线演示</title>', html, count=1)
        if count != 1:
            raise ValueError('missing browser title')
        html = replace_once(html, '<span>① 点云（绿框 = 被跟踪的单个目标）</span>', '<span>雷达点云 · 目标候选</span>')
        html = replace_once(html, '<span>② 相机画面（同一时刻最近帧）</span>', '<span>对应相机画面</span>')
        html = replace_once(html, '<canvas id="cloud"', '<div class="views"><button id="view-default">立体</button><button id="view-front">正面</button><button id="view-side">侧面</button><button id="view-top">俯视</button></div><canvas id="cloud"')
        html = replace_once(html, '<script src="data/frames.js"></script>', '<script src="' + prefix + 'data/frames.js"></script>')
        html = replace_once(html, "var path = 'camera/c'", "var path = '" + prefix + "camera/c'")
        html = replace_once(html, '  var orbit = null;', '''  var orbit = null;
  [['view-default', VIEW0.yaw, VIEW0.pitch], ['view-front', 0, 0.05],
   ['view-side', Math.PI / 2, 0.05], ['view-top', -Math.PI / 2, 1.55]].forEach(function(v) {
    document.getElementById(v[0]).addEventListener('click', function () {
      view.yaw = v[1]; view.pitch = v[2]; drawScene(FRAMES[index]);
    });
  });''')
        html = replace_once(html, "alarmTitle.textContent = '无报警';", "alarmTitle.textContent = '未触发报警';")
        html = replace_once(html, "alarmText.innerHTML = 't = ' + f.t.toFixed(2) + ' s · 起于 ' + FRAMES[alarmFirst].t.toFixed(2) +\n        ' s · 原因 <code>' + (f.rs || []).join(', ') + '</code>';", "alarmText.textContent = 't = ' + f.t.toFixed(2) + ' s';")
        html = replace_once(html, "camNote.textContent = '相机帧 #' + f.cam[0] + ' · 接收时刻 - 雷达帧时刻 = ' +\n        (f.cam[1] >= 0 ? '+' : '') + f.cam[1].toFixed(3) + ' s';", "camNote.textContent = '相机帧 #' + f.cam[0] + ' · 时差 ' + (f.cam[1] >= 0 ? '+' : '') + f.cam[1].toFixed(3) + ' s';")
        html = replace_once(html, "return '未知';", "return '动作未知';")
        html = replace_once(html, '</style>', '''
  .sessions,.views{display:flex;gap:8px;flex-wrap:wrap}
  .sessions{margin-bottom:22px}.sessions a{color:#a9b9cc;text-decoration:none;padding:8px 13px;border:1px solid var(--line);border-radius:9px}
  .sessions a.active{color:#9df0bd;border-color:#317e55;background:#123322}
  .eyebrow{color:#7dd9a6;font-size:11px;letter-spacing:2px} header h1{font-size:28px;margin:4px 0 16px}
  .sub,.verdict,.notesbox,footer,.metrics,#chart,.panel-h[style],.chip:first-child,.chip:last-child{display:none}
  .views{padding:8px 12px}.views button{padding:5px 12px} .statebar{padding:0 12px 14px}
  .disclaimer{margin-top:14px;color:#93a1b5;font-size:12px}
  </style>''')
        html = replace_once(html, '</main>', '</main><div class="disclaimer">离线演示 · 目标为几何候选 · 相机按接收时间配对 · 地面尚未验证</div>')
        (HERE / (name + '.html')).write_text(html, encoding='utf-8')
        manifest[name] = dict(frames=summary['source']['frames'],
                              frame_data_sha256=hashlib.sha256(frames.read_bytes()).hexdigest(),
                              meta_sha256=summary['source']['meta_sha256'],
                              points_sha256=summary['source']['points_sha256'])
    (HERE / 'index.html').write_text('<!doctype html><meta charset="utf-8"><meta http-equiv="refresh" content="0; url=houdao.html"><a href="houdao.html">打开演示</a>', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    print(json.dumps(build(), ensure_ascii=False, indent=2))
