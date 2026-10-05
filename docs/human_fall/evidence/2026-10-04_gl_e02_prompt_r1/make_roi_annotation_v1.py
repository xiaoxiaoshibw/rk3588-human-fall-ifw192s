# -*- coding: utf-8 -*-
"""
GL-E02 field ROI 标注辅助 / 路径 A（纯照片叠加，无点云依赖）
=================================================================
输入 : scene_reference_01.png  (用户已确认现场真实图，见 PHOTO_EVIDENCE_01.json)
输出 : annotated_roi_v1.png    (本脚本一次生成，版本号在文件名里)

约束（遵守 GL-I06 CLOSEOUT / GL-E02 执行提示）:
- 只读原图，不修改原位文件
- 不 import numpy / matplotlib / 任何点云或 ground_* 模块
- 所有 ROI 像素框由人工依据照片语义指定，**不是**来自点云自动选择
- 标注仅作"现场贴贴纸参考",不声称任何物理精度,不替代正式 ROI evidence_pack
- 4 个 ROI 的 physical_description / 距离标尺均**由现场人测**生成,本图只标记相对位置
"""
import json
import os
from PIL import Image, ImageDraw, ImageFont

# ── 输入输出锚定本目录 ──────────────────────────────────────────
HERE = os.path.dirname(os.path.abspath(__file__))
SRC  = os.path.join(HERE, "scene_reference_01.png")
DST  = os.path.join(HERE, "annotated_roi_v5.png")
META = os.path.join(HERE, "annotated_roi_v5.meta.json")

# ── 4 个 ROI 像素框（人工读图指定,版本 v1）─────────────────────
# 图像尺寸 1568x882. 坐标均为像素.
# 选区原则 (FIELD_CHECKLIST §5.1):
#   - 直径 0.3~0.5 m 物理尺寸 → 像素框直径按透视近似 100~150 px
#   - 离最近障碍(桌腿/机箱/植物/镜) ≥ 0.3 m
#   - 4 个区两两相距 ≥ 1 m 物理距离
# 选区时**避开**:左黄桌桌腿区、右白桌下方箱体、中央桌/座椅投影、右上圆镜反射区
ROIS = [
    # ── v2: 4 个区都已自查避开桌腿/桌沿/镜面反射;改用纯英文标签避免字体问题 ──
    {
        "roi_id": "FIT_front_open",
        "kind":   "FIT",
        "color":  (46, 204, 113),      # green
        "bbox":   (660, 580, 860, 730),   # 中央桌前方木地板
        "label":  "FIT  #1",
        "approach": "Center front area; sticker Zone-FIT-01",
    },
    {
        "roi_id": "VAL_left_desk",
        "kind":   "VAL",
        "color":  (241, 196, 15),      # amber
        "bbox":   (90, 660, 260, 800),    # 远离左黄桌桌腿,桌腿"左侧"地板区
        "label":  "VAL-L  #2",
        "approach": "Leftmost floor, left of yellow desk legs; Zone-VAL-01",
    },
    {
        "roi_id": "VAL_right_walkway",
        "kind":   "VAL",
        "color":  (230, 126, 34),      # orange
        "bbox":   (1080, 700, 1260, 832),  # v5: 中央桌脚**右侧**纵向走道 (field correction)
        "label":  "VAL-R  #3",
        "approach": "Walkway floor right of center desk legs; Zone-VAL-02",
    },
    {
        "roi_id": "VAL_far_window",
        "kind":   "VAL",
        "color":  (155, 89, 182),      # purple
        "bbox":   (300, 600, 470, 720),   # 左黄桌和中央桌**之间**的走道(v4: 下移避开桌沿)
        "label":  "VAL-MID  #4",
        "approach": "Middle corridor between two desks, mid-distance; Zone-VAL-03",
    },
]

# 雷达指示位置(仅示意,非精确):拍摄者背后约 1-2 m
LIDAR_HINT = {
    "xy":   (784, 850),
    "text":  "LIDAR approx (tripod)",
    "color": (52, 152, 219),
}

def load_font(size=22):
    """Windows 自动找 CJK 字体,失败退回默认."""
    candidates = [
        r"C:\Windows\Fonts\msyh.ttc",     # 微软雅黑
        r"C:\Windows\Fonts\msyhl.ttc",
        r"C:\Windows\Fonts\simhei.ttf",   # 黑体
        r"C:\Windows\Fonts\simsun.ttc",   # 宋体
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                return ImageFont.truetype(p, size)
            except Exception:
                pass
    return ImageFont.load_default()

def draw_one(draw, roi, font_big, font_sm):
    x1, y1, x2, y2 = roi["bbox"]
    c = roi["color"]
    # 半透明填充
    overlay_color = c + (60,)
    # 通过单独 RGBA 层叠加
    return x1, y1, x2, y2, c, overlay_color

def main():
    im = Image.open(SRC).convert("RGB")
    W, H = im.size
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    dd = ImageDraw.Draw(im)

    font_big = load_font(28)
    font_sm  = load_font(20)

    # 雷达位置标记
    lx, ly = LIDAR_HINT["xy"]
    od.ellipse([lx-14, ly-14, lx+14, ly+14], outline=LIDAR_HINT["color"]+(220,), width=4)
    od.ellipse([lx-5,  ly-5,  lx+5,  ly+5 ], fill=  LIDAR_HINT["color"]+(220,))
    od.text((lx+18, ly-14), LIDAR_HINT["text"], font=font_sm, fill=LIDAR_HINT["color"]+(255,))

    # 4 个 ROI
    for i, roi in enumerate(ROIS, 1):
        x1, y1, x2, y2 = roi["bbox"]
        c = roi["color"]
        # 填充 + 加粗边框
        od.rectangle([x1, y1, x2, y2], fill=c+(50,), outline=c+(255,), width=5)
        # 角标十字(目标感)
        cx, cy = (x1+x2)//2, (y1+y2)//2
        od.line([cx-12, cy, cx+12, cy], fill=c+(255,), width=3)
        od.line([cx, cy-12, cx, cy+12], fill=c+(255,), width=3)
        # 编号牌(色块+数字)
        tag_x, tag_y = x1, y1 - 36
        od.rectangle([tag_x, tag_y, tag_x+120, tag_y+30], fill=c+(230,))
        od.text((tag_x+8, tag_y+2), f"#{i} {roi['roi_id']}", font=font_sm, fill=(255,255,255,255))

    # 合成
    out = Image.alpha_composite(im.convert("RGBA"), overlay).convert("RGB")

    # 重新拿一张 draw 用于在所有 ROI 之下加一行说明文字
    dd = ImageDraw.Draw(out)
    # 顶部说明
    dd.rectangle([0, 0, W, 46], fill=(33, 33, 33))
    dd.text((10, 6),
            "GL-E02 Path A  v5  |  FIT=#1 green  VAL=#2/#3/#4  "
            "sticker IDs: Zone-FIT-01 / Zone-VAL-01..03  (v5 field-corrected #3)",
            font=font_sm, fill=(255, 255, 255))

    # 每个 ROI 框下方追加 approach 提示
    for roi in ROIS:
        x1, y1, x2, y2 = roi["bbox"]
        c = roi["color"]
        dd.rectangle([x1, y2+2, x1+560, y2+28], fill=(20,20,20))
        dd.text((x1+6, y2+5),
                f">> {roi['label']}  {roi['approach']}",
                font=font_sm, fill=c)

    out.save(DST, "PNG", optimize=True)

    # 元数据(JSON 与 checklist §8 字段对齐,只覆盖"视觉辅助"声明)
    meta = {
        "schema_version": "1.0",
        "kind": "gle02_roi_visual_annotation_pathA",
        "version": "v1",
        "source_image": "scene_reference_01.png",
        "source_image_sha256": "b080a67e2fb63d8c2688230f3aa7dd0ce48e0e2e049bc82cb149c74ece7394d0",
        "user_scene_confirmation": "user_confirmed",
        "physical_verified": False,
        "ai_estimated_pixel_regions": True,
        "purpose": "现场贴 Zone-FIT-01 / Zone-VAL-01..03 贴纸时的视觉辅助",
        "not_a_substitute_for": [
            "激光测距仪 3 次重复测量 origin_to_floor_m",
            "现场 ROI physical_description 文字描述",
            "measurement_record.json 的 roi_list 字段绑定",
            "GL-E02 E 项正式 evidence_pack",
        ],
        "roi_regions": [
            {
                "roi_id": r["roi_id"],
                "kind": r["kind"],
                "bbox_pixels": list(r["bbox"]),
                "label": r["label"],
                "approach_hint": r["approach"],
                "selection_basis": "scene_reference_01.png human-interpretation only",
                "selection_made_by": "AI (path A, visual annotation helper)",
                "physical_verified": False,
            } for r in ROIS
        ],
        "lidar_position_hint": {
            "xy_pixels": list(LIDAR_HINT["xy"]),
            "note": "approximate; verify on site",
        },
        "version_history": [
            {"v": "v1", "issue": "VAL-1/VAL-3 clips desk legs; CJK font fallback corrupted text"},
            {"v": "v2", "issue": "VAL-FAR overlaps back-wall non-floor band; VAL-L hugs desk leg"},
            {"v": "v3", "issue": "VAL-MID top edge rides center-desk bottom lip (not floor)"},
            {"v": "v4", "issue": "USER-FIELD-CORRECTION: 'VAL-R under round mirror' was wrong — "
                                "that orange circle was actually the center-desk support structure, "
                                "and the real right-side area is cluttered storage under the white desk"},
            {"v": "v5", "fix": "VAL-R moved to long corridor floor between center desk and right white desk, "
                               "based on user's on-site spatial knowledge"},
        ],
        "user_corrections_log": [
            {
                "/" : "v4->v5",
                "said_by": "user",
                "said": "橙色区域是桌子下面堆放杂物的地方",
                "ai_response": "accepted; VAL-R bbox moved to (1080,700,1260,832)",
                "physical_verified": False,
                "note": "field correction — user judgment overrides AI pixel choice for path-A helper"
            }
        ],
        "field_actions_required": [
            "现场确认 4 个 bbox 对应物理位置均满足 §5.1 净空/间距条件",
            "任何一条不满足 → 现场改贴位置,**不要**回来让我改像素框",
            "贴完贴纸后续 FIELD_CHECKLIST §5.3 表 + §6.2 激光测距",
        ],
    }
    with open(META, "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

    print("OK")
    print("OUT:", DST)
    print("META:", META)
    print("size:", out.size)

if __name__ == "__main__":
    main()
