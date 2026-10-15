"""把 PLANE-01 证据页面同步到总控制台子文件夹 `plane01_pages/`（只读源，幂等重写目标）。

用法（在 pc_apps/console 下）：
    python -B -W error sync_plane01_pages.py [--evidence ../../../docs/sidequests/evidence/2026-10-14_plane_track_r1]

内容：
  - HTML：09_DEMO_10HZ / 15_DEMO_FG / 19_3D_TRACK / 20_3D_TRACK_V2 / 22_3D_TRACK_V3（+ three r127 两个 vendor 文件）
  - 图：30_TBD_TRACK / 26_SHAPE_ALIGNED / 25_SHAPE_SILHOUETTE / 22_UNION_MOVING / 04_BACKGROUND / 06_TRACK_REAL / 18_DISLOCATION_EXPLAINED / 09_DEMO_SUMMARY
  - 视频：17_PLANE_FG_TRACK / 20_PLANE_FG_TRACK_V2
  - 生成 index.html（总入口，含每页说明与"准实时 P1 页需本机跑 rt_server.py"的提示）与 MANIFEST.json（源 SHA 记录）
"""
import argparse
import hashlib
import json
import shutil
from datetime import datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_EVIDENCE = HERE.parents[1] / "docs" / "sidequests" / "evidence" / "2026-10-14_plane_track_r1"

PAGES = [
    ("22_3D_TRACK_V3.html", "3D · 完整移动形态 + 体形框 + 航线（推荐）",
     "运动期全部瞬态点按帧着色 + 目标 OBB + 去拖影体形框 + 速度矢量 + 航线帧号"),
    ("20_3D_TRACK_V2.html", "3D v2 · 稳健核 + 去拖影体形框",
     "单链接聚类与稳健核中心校正后的目标与体形框"),
    ("19_3D_TRACK.html", "3D v1 · 体形框 + 航线（首版）",
     "目标点云 + PCA 有向包围盒 + 逐帧中心航线"),
    ("15_DEMO_FG.html", "去背景回放（房间已减掉）",
     "只保留自由空间移动目标，10 Hz 循环，含累计轨迹开关"),
    ("09_DEMO_10HZ.html", "10 Hz 准实时回放（含房间）",
     "按源帧真实节奏回放的原始会话视角，HUD 显示延迟/掉帧/目标状态"),
]
ASSETS = [
    ("30_TBD_TRACK.png", "P1 结果：低门槛候选 / TBD 命中帧 / 确认轨迹"),
    ("26_SHAPE_ALIGNED.png", "姿态归一化形状累积（长×宽×厚 + 投影）"),
    ("25_SHAPE_SILHOUETTE.png", "形状轮廓与剖面（2 cm 栅格）"),
    ("22_UNION_MOVING.png", "运动期全部瞬态点并集（含单帧同伴点）"),
    ("04_BACKGROUND.png", "空场配准后的泄漏可视化"),
    ("06_TRACK_REAL.png", "静止紧凑目标跟踪对照（6.5 m 吊装物）"),
    ("18_DISLOCATION_EXPLAINED.png", "\"脱位\"来源分解（帧内滚动 / 链式并簇）"),
    ("09_DEMO_SUMMARY.png", "四图总览"),
]
VIDEOS = [
    ("20_PLANE_FG_TRACK_V2.mp4", "去背景跟踪视频 v2（推荐）"),
    ("17_PLANE_FG_TRACK.mp4", "去背景跟踪视频 v1"),
]
VENDOR = ["three.min.js", "OrbitControls.js"]

INDEX = """<!DOCTYPE html>
<html lang="zh"><head><meta charset="utf-8"><title>PLANE-01 小飞行目标证据页</title>
<style>
 body{{margin:0;background:#0f1115;color:#e7e8ea;font:13.5px/1.6 "Segoe UI","Microsoft YaHei UI",sans-serif}}
 #w{{max-width:1000px;margin:0 auto;padding:32px 24px 48px}}
 h1{{font-size:19px;margin:0 0 4px}} .sub{{color:#8b9098;font-size:12px;margin-bottom:22px}}
 h2{{font-size:14px;color:#9fd1ff;margin:26px 0 8px;font-weight:600}}
 a.item{{display:block;padding:10px 12px;border:1px solid #26282d;border-radius:6px;margin:6px 0;
        text-decoration:none;color:inherit;background:#171921}}
 a.item:hover{{background:#1e2129;border-color:#34373e}}
 .n{{font-weight:600}} .d{{color:#8b9098;font-size:12px}}
 .note{{color:#8b9098;font-size:12px;border-left:2px solid #34373e;padding-left:10px;margin-top:22px}}
 code{{background:#171921;padding:1px 5px;border-radius:4px}}
</style></head><body><div id="w">
<h1>PLANE-01 · 小飞行目标（纸飞机）证据页</h1>
<div class="sub">cap_20261014_164522 / cap_20261014_221808 · 去背景 → 检测 → 跟踪 → 形状与规则分 · 本页由总控制台内嵌服务提供</div>
<h2>3D 与回放页</h2>
{pages}
<h2>指标图</h2>
{assets}
<h2>视频</h2>
{videos}
<div class="note">
 数据与完整证据在仓库 <code>docs/sidequests/evidence/2026-10-14_plane_track_r1/</code>（本页是其中可交互部分的副本）。
 <br>准实时 P1 演示（低门槛 + TBD + KF/M-N，10 Hz）需本机运行
 <code>python -B -W error sidequests/plane_track/r01/rt_server.py --port 8973</code> 后访问 <code>http://127.0.0.1:8973/</code>；
 本控制台不代为启动该开发服务。
 <br>生成时间 {stamp}；源证据 SHA 见同目录 <code>MANIFEST.json</code>。
</div>
</div></body></html>
"""


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def item_html(name, title, desc):
    return '<a class="item" href="%s"><span class="n">%s</span><br><span class="d">%s</span></a>' % (name, title, desc)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence", default=str(DEFAULT_EVIDENCE))
    args = parser.parse_args()
    source = Path(args.evidence)
    if not (source / "22_3D_TRACK_V3.html").is_file():
        raise SystemExit("evidence dir not found or incomplete: %s" % source)
    target = HERE / "plane01_pages"
    target.mkdir(exist_ok=True)
    copied, manifest = [], {}
    for name, _title, _desc in PAGES:
        shutil.copy2(source / name, target / name)
        copied.append(name)
    for name in VENDOR:
        shutil.copy2(source / name, target / name)
        copied.append(name)
    for name, _desc in ASSETS:
        shutil.copy2(source / name, target / name)
        copied.append(name)
    for name, _desc in VIDEOS:
        shutil.copy2(source / name, target / name)
        copied.append(name)
    for name in copied:
        manifest[name] = {"source": str(source / name), "sha256": sha256(source / name),
                          "bytes": (target / name).stat().st_size}
    index = INDEX.format(pages="\n".join(item_html(n, t, d) for n, t, d in PAGES),
                         assets="\n".join(item_html(n, n, d) for n, d in ASSETS),
                         videos="\n".join(item_html(n, n, d) for n, d in VIDEOS),
                         stamp=datetime.now().strftime("%Y-%m-%d %H:%M"))
    (target / "index.html").write_text(index, encoding="utf8")
    payload = {"generated_iso": datetime.now().isoformat(timespec="seconds"),
               "evidence_dir": str(source), "files": manifest,
               "note": "由 sync_plane01_pages.py 生成；重跑即刷新（只读源证据，不修改证据目录）"}
    (target / "MANIFEST.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
                                          encoding="utf8")
    print(json.dumps({"target": str(target), "files": len(copied) + 2,
                      "bytes": sum(f["bytes"] for f in manifest.values())}, ensure_ascii=False))


if __name__ == "__main__":
    main()
