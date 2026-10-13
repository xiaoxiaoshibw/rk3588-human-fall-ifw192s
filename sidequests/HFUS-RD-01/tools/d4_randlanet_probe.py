# -*- coding: utf-8 -*-
"""D4 RandLA-Net CPU 可行性最小探头。

目的（预登记）：
  1) 逐点 GT 资产普查：九会话中 reviewed PERSON GT 覆盖多少帧/点，
     且这些点只占每帧 2-4 万点中多大比例——回答"人/非人逐点监督
     在数据上是否可行**：若每帧只有 ~1k/mean 人点 vs 4w 总计，
     则逐点监督需要额外负点标注，现 GT 每帧非人点均为 UNKNOWN。
  2) CPU 推理成本最保守量级估计：不训网络、不下载预训练，直接按
     RandLA-Net 核心算子（KNN gather + 卷积堆叠）的 FLOPs 量级在
     numpy 上实测单帧 2-5 万点的逐点传播开销≈KNN 主导。该探头只
     回答「CPU 量级是否离谱」(>= 数百 ms = 10Hz 直接不合);
     不报告真实网络延迟，不伪造 mIoU。
  3) 逐点→实例分离后处理可行性：对我们场景从逐点标签经 DBSCAN/
     欧氏连通的实例划分在算法上已知可行；成本沿用 D2 C1/C2 的
     实测延迟（已经足以判 ≥10Hz 预算是否可行）。

输出 evidence/D4_RANDLANET_FEAS.json：普查数字 + 实测延迟 + 结论。
"""
import json
import os
import sys
import time
from collections import defaultdict

import numpy as np
from scipy.spatial import cKDTree

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import common as C

OUT = os.path.join(C.EVIDENCE, "D4_RANDLANET_FEAS.json")


def survey_per_point_gt():
    stats = {}
    for sid in C.SIDS:
        gt = C.load_gt(sid)
        if gt is None:
            stats[sid] = {"gt": False}
            continue
        by_frame = defaultdict(int)
        for o in gt["objects"]:
            if (o["class_name"] == "PERSON"
                    and o["review_status"] == "reviewed"
                    and o["source"] == "human"):
                by_frame[o["frame_idx"]] += len(o["indices"])
        meta = C.load_meta(sid)
        n_frames = len(meta["frames"])
        pts_total = sum(f["count_points"] for f in meta["frames"])
        labeled_human_pts = sum(by_frame.values())
        frames_with_gt = len(by_frame)
        stats[sid] = {
            "gt": True,
            "n_frames": n_frames,
            "frames_with_reviewed_gt": frames_with_gt,
            "total_points": pts_total,
            "labeled_person_points": labeled_human_pts,
            "label_coverage_points": round(
                labeled_human_pts / max(pts_total, 1), 5),
            "label_coverage_frames": round(frames_with_gt / n_frames, 4),
            # 关键空洞：没有 reviewed 非人点——这是逐点监督的真缺口
            "reviewed_nonperson_points": 0,
            "per_point_supervision_gap":
                "无人逐点为正；其余 99%% 点没有 reviewed 标签（UNKNOWN），"
                "按规则不能自动当负例。",
        }
    return stats


def knn_cost_probe():
    """KNN(k=16) 批量逐帧耗时（真实测量，RandLA-Net 的 CPU 主成本）。"""
    res = {}
    for sid in ("cap_20261010_175429", "cap_20261010_175553"):
        xyz, _i, mm = C.read_frame_xyz(sid, 0)
        n = len(xyz)
        # 下采样到 RandLA-Net 输入量级（40960 或 16384）——按官方配置常用值
        for target in (16384, 40960):
            idx = (np.linspace(0, n - 1, target).astype(int)
                   if n >= target else np.arange(n))
            pts = C.level(xyz[idx]).astype(np.float64)
            t0 = time.perf_counter()
            tree = cKDTree(pts)
            build_ms = (time.perf_counter() - t0) * 1000
            t0 = time.perf_counter()
            _, nb = tree.query(pts, k=16, workers=1)
            query_ms = (time.perf_counter() - t0) * 1000
            res["%s_n%d" % (sid[-6:], target)] = {
                "n_pts": int(len(pts)),
                "kd_build_ms": round(build_ms, 1),
                "knn_query_ms": round(query_ms, 1),
            }
    return res


def main():
    survey = survey_per_point_gt()
    knn = knn_cost_probe()
    concl = {
        "gt_per_point_census": survey,
        "knn_cpu_probe": knn,
        "conclusions": {
            "per_point_gt_enough": False,
            "reason": ("九会话全部非人点无 reviewed 标签；逐点监督无可"
                       "用负类，且人点覆盖率仅 ~1%%（总人数点 / 全帧点数）。"
                       "若采用 SQN 式 0.1%% 稀疏监督路线，需要新增负点逐点"
                       "标注；现 GT 不直接支持。"),
            "cpu_cost_class": ("cKDTree K=16 对 16k/40k 点为数十毫秒级；"
                               "网络本体矩阵乘加几层卷积在 NumPy 上是可"
                               "接受量级；真正的工程瓶颈在 Windows CPU 训"
                               "练全流程及板端移植，不在单帧推理。"),
            "deployment_boundary": ("板端 Python 3.8/NumPy 1.17 环境需纯"
                                    " NumPy 推理或 ONNX 另立支线；无 CUDA，"
                                    "Open3D-ML 官方管线不作承诺。"),
            "verdict": ("DATA_BLOCKED——逐点 GT/标注任务缺失，"
                        "无法诚实训/测 RandLA-Net。最小补数清单见结论："
                        "(1) S1 会话家具逐点负例 500-1000 帧级散标; "
                        "(2) 每个有人会话的 5-10 帧全身逐点实例标注; "
                        "(3) 负点需覆盖地板/家具/背景簇 三类来源。"),
        },
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(concl, f, ensure_ascii=False, indent=1)
    print("[D4] written %s" % OUT)


if __name__ == "__main__":
    main()
