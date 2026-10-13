# -*- coding: utf-8 -*-
"""打包两侧配平算法代码为独立 zip（解压即得完整目录树）。

在本目录运行：
    python -B make_leveling_release.py

输出：D:\\Code\\ldiar\\captures\\dist_code\\LiDAR_Leveling_Code_20261007.zip
（写到 captures/dist_code/，与 console 发布物分离，避免和 LiDAR_Console.zip 混淆）

内容分两侧：
- pc_leveling/      总控制台「离线配平/算法验证」用的算法与页面（依赖仅 NumPy）
- board_core/       human_fall_detection 里的地面/配平 core（GL-N01/C01/AGL，板侧）
- 出处说明.txt      每侧原仓库路径 + 运行提示
"""
import os
import zipfile

ROOT = r"D:\Code\ldiar"
OUT_DIR = os.path.join(ROOT, "captures", "dist_code")
ZIP = os.path.join(OUT_DIR, "LiDAR_Leveling_Code_20261007.zip")

PC = os.path.join(ROOT, "pc_apps", "human_replay")
BOARD = os.path.join(ROOT, "src", "human_fall_detection")

# pc_apps/human_replay/ 下要收的文件（zip 内路径 pc_leveling/<同名>）
PC_FILES = [
    "leveling.py",
    "leveling_lib.py",
    "leveling_quality.py",
    "leveling.html",
    "leveling.js",
    "validation.py",
    "validation.html",
    "leveling_test.py",
    "leveling_auto_test.py",
    "validation_test.py",
    "floor_detector.py",
    "floor_roi.py",
    "floor_sheet.py",
    "floor_roi_test.py",
    "floor_sheet_test.py",
    "LEVELING_README.md",
]
# 包目录 leveling_estimators/ → pc_leveling/leveling_estimators/
PC_PKGS = ["leveling_estimators"]

# human_fall_detection/core 下配平相关 → board_core/<同名>
BOARD_CORE_FILES = [
    "ground.py",
    "nominal_leveling.py",
    "joint_leveling.py",
]
# 整包 → board_core/adaptive_ground/
BOARD_PKGS = ["core/adaptive_ground"]


def _add_pkg(z, pkg_abs, arc_prefix):
    for dirpath, dirnames, filenames in os.walk(pkg_abs):
        dirnames[:] = [d for d in dirnames if d != "__pycache__"]
        for fn in sorted(filenames):
            if fn.endswith((".pyc", ".pyo")):
                continue
            full = os.path.join(dirpath, fn)
            rel = os.path.relpath(full, pkg_abs).replace("\\", "/")
            z.write(full, "%s/%s" % (arc_prefix, rel))


def main():
    missing = [f for f in PC_FILES if not os.path.isfile(os.path.join(PC, f))]
    missing += [f for f in BOARD_CORE_FILES if not os.path.isfile(os.path.join(BOARD, "core", f))]
    if missing:
        raise SystemExit("缺少文件: %s" % ", ".join(missing))
    os.makedirs(OUT_DIR, exist_ok=True)
    with zipfile.ZipFile(ZIP, "w", zipfile.ZIP_DEFLATED) as z:
        for f in PC_FILES:
            z.write(os.path.join(PC, f), "pc_leveling/%s" % f)
        for pkg in PC_PKGS:
            _add_pkg(z, os.path.join(PC, pkg), "pc_leveling/%s" % pkg)
        for f in BOARD_CORE_FILES:
            z.write(os.path.join(BOARD, "core", f), "board_core/%s" % f)
        for pkg in BOARD_PKGS:
            _add_pkg(z, os.path.join(BOARD, pkg), "board_core/%s" % pkg.split("/")[-1])
        z.writestr("出处说明.txt", (
            "配平算法代码包 20261007\n"
            "====================\n\n"
            "pc_leveling/   <- D:\\Code\\ldiar\\pc_apps\\human_replay\\ 中的配平相关文件\n"
            "  总控制台「离线配平 + 算法验证」工作台算法。依赖：Python + NumPy。\n"
            "  - leveling.py 服务端任务编排（被 Console 内 human_replay_lib /api/leveling/* 调）\n"
            "  - leveling_lib.py 自动找 4 个地面 ROI（detect_ground_domain）\n"
            "  - floor_detector.py / floor_roi.py / floor_sheet.py 地面身份层不同代\n"
            "  - leveling_estimators/ TLS/SVD/RANSAC 三法平面估计\n"
            "  - leveling_quality.py 同域比较 + 一致性门\n"
            "  - leveling.html/js validation.py/html 页面\n"
            "  - *_test.py 单元测试：python -B -W error -m unittest <文件不含.py>\n"
            "  其余 human_replay 文件（fetch/回放/标注）不属于配平，未收。\n\n"
            "board_core/    <- D:\\Code\\ldiar\\src\\human_fall_detection\\core\\ 中的配平模块\n"
            "  板侧跌倒检测的地面/配平层，纯算法无 ROS 依赖。依赖：NumPy。\n"
            "  - ground.py HF-03 鲁棒地面拟合\n"
            "  - nominal_leveling.py GL-N01 名义参数配平（26deg / 1.1m）\n"
            "  - joint_leveling.py GL-C01 联合反解\n"
            "  - adaptive_ground/ AGL 自适应配平（estimators TLS/SVD/RANSAC、\n"
            "    controller/consensus/selection/temporal/transform/quality/contracts）\n"
            "  依赖 core/ 内 calibration/ground_diagnostics/ground_evidence/numeric\n"
            "  等同包其它模块；本包只收配平滑道，完整 human_fall_detection 见仓库。\n"
        ))
    print("生成 %s (%.1f KB)" % (ZIP, os.path.getsize(ZIP) / 1e3))
    with zipfile.ZipFile(ZIP) as z:
        assert z.testzip() is None
        print("zip 校验通过，%d 个文件" % len(z.namelist()))


if __name__ == "__main__":
    main()
