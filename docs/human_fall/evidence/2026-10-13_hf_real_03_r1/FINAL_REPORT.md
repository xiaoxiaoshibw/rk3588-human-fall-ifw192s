# HF-REAL-03 R1 助手视觉排查三单 / SUBMITTED，未 ACCEPTED

2026-10-13。用户授权"三项一起做"+"开发啊"后启动；上一单 HF-REAL-02 R1 提出 f10 家具污染、HF-REAL-01 R1 提出 093958 配平 FAIL、HR-W03 长期 REWORK 由 P 臂吞人导致，本单在隔离 r03 下由助手视觉运行排查，不修改 r01/r02 源码、不修改生产模型 GT、不部署、不采集、不 commit/push。

ponytail SKILL.md 实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`。

## 基线绑定

- HEAD `026e06303f60ed1bbe4ddc4d037836db68da6d27`，分支 master；工作树起时已含 267 项用户末期差异，本单不动 git。
- 写入范围：本单源码 `sidequests/human_fusion_lab_next/real_fall/r03/`、证据 `docs/human_fall/evidence/2026-10-13_hf_real_03_r1/`、returns/HF-REAL-03.md 追加、WORKFLOW.md 顶部登记、REVIEW_LOG.md 登记。
- 出网动作唯一：ssh `ls /mnt/captures/captures_remote/`（只读检查板上是否还有2026-10-07会话档案），板上状况未变。

## 任务 1：f10 家具污染 — 视觉盒未剔除 target，落入人腿位是帮手错误

**暴露**：r02 process_v2 f10 target bbox min=(1.478,1.411,0.101) / max=(2.317,2.060,1.673)。FINAL_REPORT 称"f10 家具条带混入 target 组件"。我渲染 f9/f10/f11 的 top+side 视图后，在 f10/f11 top 视图左下读到一个细长静态簇（x≈1.46-1.55, y≈1.39-1.50），主张此为"家具"。

**反例**：v3 过滤盒 [1.40,1.35,0.00]-[1.60,1.55,2.50] 应用后：
- f9/f10/f11 target 剔除量 = 0（v2 target 本身不含盒内点）
- 总剔除 404 点全部位于 f18-f23（t=1.86s-2.38s），因为人物左腿迈过盒内
- 404 点 100% 落在 HF-REAL-01 视觉人区 XY[1.4,2.6]×[1.25,2.2] 内（REMOVED_VS_PERSON_REGION.png）

**结论1**：r02 的 v2 站姿区域 .50m 裁剪加上最近邻组件关联已经把家具挡在 target 之外；FINAL_REPORT 中"f10 仍有家具残留"是 writer 保守的诊断，本单指定独审需要在证据里重新审查 RS04 FAIL 是否能关闭。

**结论2**：我提出的盒位被证明是错误的"家具"猜测（实际上那是人腿经过区），因此**该盒只是本单证据，不会接入任何生产路径**；v3 process 文件仅记录盒子本身在此场景中错误。r02 v2 target 留在生产入口未动。

**f10 大 bbox 的另一可能成因**：人左肩抓取的連衣裙/背包带代替 target 联通路径，被 v2 站姿带保留下来，不是独立静态家具条。视觉上此与 bbox 几何形态一致，但无法定量分辨，登记为助手视觉推断，不是 GT。

## 任务 2：093958 配平 FAIL — DATA_BAD，不是拟合能救

**机读结果**（r1 证据 leveling.json）：
- 120 帧、12.33s
- TLS / SVD：pitch 24.0054746° / roll 0.9988871°（两法收敛到同一局部解，pitch 一致到 float 精度）
- RANSAC：pitch 23.84° / roll -0.37°
- pairwise 三对全 PASS（角度差 < 1.4°，offset_gap < 0.03m）
- 每法自身 holdout FAIL；recommended=None、runtime_eligible=False、physical_verified=False

**视觉根本因素**：093958_SNAPSHOTS.png f5/f60/f115 side view 全都看不到"地斜带"；top view 也无地面网格残留。情景里地面采样严重不足、但被大量遮挡物主导，只占少数。

**结论**：不是拟合超参数、不是 n 选择问题；**场景本身几乎没有可用的地面 patch**可供同域门定义。建议：
- 该段全本单级别判定 DATA_BAD / NOT_RESCUABLE。
- 不接入追踪；不做分级重采样或降门营救；不做 r02 型场景参考平面追加。

## 任务 3：215540 P 臂吞人按部位画像 — 站立人躯干/腿/肩/头全部被 overwhelmingly 删除

**在 P 臂口径（仅在线静态背景，self-reference，与 fusion_v2_ab 同 PIPE 同 voxel 参数）**，64 帧人区点（center [2.10,-0.57]，r=0.55m，z∈[0.10,2.30]）剔除如下：

| band | survived | removed | survive% |
|---|---|---|---|
| legs      | 941   | 31,313  | 2.92% |
| torso     | 1,081 | 57,297  | 1.85% |
| shoulders | 612   | 18,341  | 3.23% |
| head      | 140   | 5,952   | 2.30% |
| **合计**  | **2,774** | **112,903** | **2.40%** |

**mask 图**（215540_P_MASK.png）：side view 一般人形主干从 legs 到 head 全部是红色删除；幸存点零星分布在人形外围（如融合产生的组路径噪点），与人体不重合。

**机制（行为性缺陷，不是调参）**： PIPE.bg_occ_strong 门要求体素在 >= 0.85×n_frames 出现 >= hit_min 点命中；站立人主体每帧同位置产生命中，必然被认作背景。这不是把门降低能修，是 build_static_map 对"高保留持续点"的定义错此场景。

**fusion v2 内存恢复机制**：fusion_v2_ab (2026-10-08) 与 HR-W03 锁定的 fusion v2 union=v2 是依靠**参考层（真实空场，配准后）**：空场不含此人 → online 命中无时 -> 保留。 任何由本段 leveled 无 233658 点可参照 场合下，本段仅可 P 臂。

**范围限制 / DATA_BLOCKED**：

- `cap_20261007_215623`、`cap_20261007_215643`、`cap_20261007_233658` 板端 `ls captures_remote/` 仅返回 215540 一项目；板上 47 段总览中无任何 2026-10-07 会话； 本机 `captures/remote/` 同样只含 215540（leveled transform 与 registration JSON 已在；无法以当前原始点重新跑 fusion v2 A/B；落在 HR 直派分支接受）。
- fusion v2 另行社区的打点（HR-RET-V2 increment1 已验证为默认不被任何现有路径调用）不动 — 不受影响。

## axis_ambiguous 3 帧（f47/f109/f118）

AMBIG_COMPARE.png 显示 target 在 f47/f109/f118 已进入下滑阶段 (f72 起 prototype_fall_alert) — 人物主体近接地水平，形轴同水平姿态主轴同向，PCA 出现异质结不等于骨架无效。r02 RS05 BLOCKED 保持，本单不为这 3 帧关闭 BLOCKED。

## 逐条自验 v1

| ID | 状态 | 证据 |
|---|---|---|
| RS-A | PASS | 起点 HEAD/分支/工作树数量已量； ponytail 实际读取路径在上 |
| RS-B | PASS | r03 源码 + 证据目录列表见下； r01/r02 源未变 |
| RS-C | PASS（工具）/ FAIL（视觉盒被拒） | v3 404 全落人区； 盒被证明错 -> 不接生产 |
| RS-D | PASS（工具）/ FAIL（数据） | 读 leveling.json + 帧快照； 判 DATA_BAD |
| RS-E | PASS | legs/torso/shoulders/head 分别量化吞人率； mask PNG 现 |
| RS-F | BLOCKED | 板上 ssh 与本机均无 215623/215643/233658 原始点 |
| RS-G | PASS | 无 commit/push/reset/clean； 无生产/模型/GT/captures 修改 |
| RS-H | BLOCKED / NOT_RUN | 独审 NOT_RUN； 设备 / 部署 / 生产 / GT NOT_RUN； |
| RS-I | PASS（借用）/ BLOCKED（骨架） | AMBIG_COMPARE.png 关闭在 3 帧轴歧义可能为下滑姿态物理机制 |

## 交付物

- `sidequests/human_fusion_lab_next/real_fall/r03/`：render_f10.py、vision_clean.py、render_v3_compare.py、examine_overlap_093958.py、examine_093958_v2.py、examine_093958_v3.py、probe_215540.js、render_215540_mask.py、README.md
- `docs/human_fall/evidence/2026-10-13_hf_real_03_r1/`： ACCEPTANCE_V1.md、FINAL_REPORT.md、out/*.png/.json/.svg、 SOURCE_AND_END_BOUNDARY.json、 ARTIFACTS_FINAL_SHA.json
- `docs/human_fall/returns/HF-REAL-03.md`： 采取措施
- `docs/human_fall/WORKFLOW.md`： 顶部记录
- `docs/human_fall/REVIEW_LOG.md`： 登记

## 后续（未授权，不是建议授权者）

- HF-REAL-02 RS04 FAIL 的关闭： 需由指定独审根据 v3 vs 人区重叠 0 录取； 本单不能代为关闭；
- fusion v2 启动到生产： 依旧未授权；
- 093958：不投入追踪亦不重新采集；
- axis_ambiguous 3 帧： 骨架不接生产，再但因物理下滑机制不应改轴；
- 不生产部署、不调整模型/GT、不采 git。

