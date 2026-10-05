# -*- coding: utf-8 -*-
"""
GL-E02 ROI 标注 v6 / 路径 A — 雷达视场真值
==================================================================
与 v1-v5 的根本差异:
  v1-v5 的参考图 (scene_reference_01.png) 不是来自雷达的视向 — 作废.
  v6   的参考图 (mirasim-att-4be22c9f.jpg) 是拍摄者站在雷达处的所见,
       雷达 x 轴正前 = 画面纵深方向,远端机器人就在 x 轴尽头.

雷达视锥∩地面 = 紫框(用户手绘,已知)
ROI 选区     = 紫框内部,沿画面纵深方向(=雷达 x 轴)分 4 个横条带,
              从近(画面下,雷达脚前)到远(画面上,远端机器人脚前).

每个 ROI 是横贯紫框的梯形横条,左右边缘严格落在紫框斜边上,
使用线性插值保证几何一致性.

不 import numpy/matplotlib,不动点云,不修改原图.
"""
import json
import os
from PIL import Image, ImageDraw, ImageFont

HERE  = os.path.dirname(os.path.abspath(__file__))
SRC   = r"C:/Users/30680/AppData/Local/Temp/mirasim-att-4be22c9f.jpg"
DST   = os.path.join(HERE, "annotated_roi_v6.png")
META  = os.path.join(HERE, "annotated_roi_v6.meta.json")

# ── 用户给的紫框 4 个角手工读数 (1086 x 610) ──────────────────
# "紫框梯形 = 雷达的点能照到的地面" (user said)
TRAPEZOID = {
    "TL": (320, 240),   # top-left     = 远端左
    "TR": (810, 240),   # top-right    = 远端右
    "BR": (990, 580),   # bottom-right = 近端右
    "BL": (80,  580),   # bottom-left  = 近端左
}

# ── 4 个 ROI 沿雷达 x 轴分带 ──────────────────────────────────
# 画面 y 越小 = 越远; 画面 y 越大 = 越近.
# 从近到远排序: ROI #1 = 近(FIT), ROI #4 = 远(VAL_far)
BANDS = [
    # (label_suffix_nickname, y_norm_start, y_norm_end, color, rgb)
    # y_norm 0.0 = 紫框上底边(远), 1.0 = 紫框下底边(近)
    {"rid":"VAL_far","label":"#4 VAL-FAR",  "y0":0.00, "y1":0.25, "color":(155, 89, 182), "phys":"~2.5-3.0 m from lidar"},
    {"rid":"VAL_mid_far","label":"#3 VAL-MID-FAR",  "y0":0.25, "y1":0.50, "color":(230, 126, 34),  "phys":"~1.8-2.2 m"},
    {"rid":"VAL_mid_near","label":"#2 VAL-MID-NEAR","y0":0.50, "y1":0.75, "color":(241, 196, 15),  "phys":"~1.2-1.5 m"},
    {"rid":"FIT_near","label":"#1 FIT-NEAR","y0":0.75, "y1":1.00, "color":(46, 204, 113), "phys":"~0.5-0.8 m (FIT)"},
]

def lerp(p, q, t):
    """线性插值 p->q 在 t 处的点."""
    return (int(p[0] + (q[0]-p[0]) * t),
            int(p[1] + (q[1]-p[1]) * t))

def band_quad(y0, y1):
    """给定纵向归一化区间 [y0,y1] (0=远, 1=近), 返回紫框内梯形 4 顶点.
    左斜边 = TL -> BL, 右斜边 = TR -> BR (顺序对应"远到近" = "y 0->1").
    """
    top_left     = lerp(TRAPEZOID["TL"], TRAPEZOID["BL"], y0)
    top_right    = lerp(TRAPEZOID["TR"], TRAPEZOID["BR"], y0)
    bot_right    = lerp(TRAPEZOID["TR"], TRAPEZOID["BR"], y1)
    bot_left     = lerp(TRAPEZOID["TL"], TRAPEZOID["BL"], y1)
    # 返回按绘制顺序: top-left -> top-right -> bot-right -> bot-left
    return [top_left, top_right, bot_right, bot_left]

def load_font(size=20):
    """Windows CJK 字体尝试,失败用默认."""
    for p in (r"C:\Windows\Fonts\msyh.ttc",
              r"C:\Windows\Fonts\simhei.ttf",
              r"C:\Windows\Fonts\simsun.ttc"):
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def main():
    im = Image.open(SRC).convert("RGB")
    W, H = im.size
    print("size:", W, H)

    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)

    # 紫框本身描黑边, 让它在图上**依然可见** (原图紫线会被半透明填充覆盖)
    tl, tr, br, bl = (TRAPEZOID[k] for k in ("TL","TR","BR","BL"))
    od.line([tl, tr], fill=(255, 0, 255, 255), width=3)
    od.line([tr, br], fill=(255, 0, 255, 255), width=3)
    od.line([br, bl], fill=(255, 0, 255, 255), width=3)
    od.line([bl, tl], fill=(255, 0, 255, 255), width=3)

    # 4 个 ROI 带
    font_big = load_font(26)
    font_sm  = load_font(18)

    for b in BANDS:
        quad = band_quad(b["y0"], b["y1"])
        # 半透明填充
        fill_c = b["color"] + (110,)
        od.polygon(quad, fill=fill_c, outline=b["color"]+(255,))
        # 标签在每带**垂直中心**, 写在**带的左侧中央**
        cx = sum(p[0] for p in quad) // 4
        cy = sum(p[1] for p in quad) // 4
        # 文字背景
        text = b["label"]
        tw = od.textlength(text, font=font_big)
        th = 30
        od.rectangle([cx - tw//2 - 8, cy - th//2 - 4, cx + tw//2 + 8, cy + th//2 + 4],
                     fill=(20, 20, 20, 220), outline=b["color"]+(255,), width=2)
        od.text((cx - tw//2, cy - th//2), text, font=font_big, fill=b["color"]+(255,))

    out = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")

    # 顶部说明
    dd = ImageDraw.Draw(out)
    dd.rectangle([0, 0, W, 40], fill=(33, 33, 33))
    dd.text((10, 6),
            "GL-E02 Path A v6  |  LIDAR FOV ground footprint (magenta trapezoid)  |  "
            "ROIs along lidar +x  |  #1 near FIT -> #4 far VAL",
            font=font_sm, fill=(255, 255, 255))

    # 终点标注(雷达/机器人)
    dd.text((10, H - 30), "near  = lidar at bottom (foremost)",
            font=font_sm, fill=(255, 255, 255))
    dd.text((W // 2 - 30, 50), "far = robot in front",
            font=font_sm, fill=(255, 255, 255))

    out.save(DST, "PNG", optimize=True)

    # 元数据
    meta = {
        "schema_version": "1.0",
        "kind": "gle02_roi_visual_annotation_pathA",
        "version": "v6",
        "source_image": "mirasim-att-4be22c9f.jpg",
        "source_path": SRC,
        "source_size": [W, H],
        "user_scene_confirmation": "user_confirmed",
        "physical_verified": False,
        "previous_versions_obsolete": ["v1", "v2", "v3", "v4", "v5"],
        "reason_for_obsolescence":
            "Prior versions used scene_reference_01.png which is not a lidar-view image. "
            "v6 uses a user-supplied image taken AT the lidar position, with user-drawn "
            "magenta trapezoid marking the lidar ground footprint. This is the correct "
            "geometric basis for ROI selection.",
        "rrapezoid_corners_pixels": TRAPEZOID,
        "trapezoid_meaning": "lidar FOV intersection with ground (user-drawn)",
        "roi_axis": "lidar +x (depth direction in image)",
        "roi_bands": [
            {
                "roi_id": b["rid"],
                "label": b["label"],
                "physical_distance_from_lidar": b["phys"],
                "y_norm_range": [b["y0"], b["y1"]],
                "color": list(b["color"]),
                "quad_pixels": band_quad(b["y0"], b["y1"]),
            } for b in BANDS
        ],
        "constraints_satisfied": {
            "all_rois_within_trapezoid": True,
            "rois_do_not_overlap": True,
            "roi_axis_along_lidar_x": True,
            "four_independent_distances": True,
        },
        "field_actions_required": [
            "Confirm the 4 color bands are all clean wood floor at field",
            "Place stickers Zone-FIT-01 (#1), Zone-VAL-01 (#2), Zone-VAL-02 (#3), Zone-VAL-03 (#4)",
            "Laser rangefinder: lidar origin -> each sticker center x3",
            "Photograph each sticker location with this annotated image as backdrop",
        ],
        "version_history": [
            {"v": "v1-v5", "issue": "Entire geometry wrong - based on non-lidar-view image"},
            {"v": "v6", "fix": "Use real lidar-view image, ROI along lidar x-axis, "
                                "strictly inside user-drawn ground footprint trapezoid"},
        ],
    }
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("OUT:", DST)
    print("META:", META)

if __name__ == "__main__":
    main()
