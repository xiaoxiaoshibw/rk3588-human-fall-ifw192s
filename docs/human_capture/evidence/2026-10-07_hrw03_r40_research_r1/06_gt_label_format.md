# 人工标签格式：最小补充，设计草案

机器生成的06_gt_tasks.json/CSV只有diagnostic UNKNOWN，不是human GT。下面结构是格式说明；本轮没有填入真人标签。真实文件必须由reviewer完成并填写source="human"；程序不得自动将diagnostic文件改成human。

1. 旧09_point_review.html实际导出保留现有kind/schema/全部绑定，31个points与155个非静态确认行的label/continuity逐项核。UNKNOWN允许但意味着未闭合。
2. 一个独立sidecar（建议kind hrw03_cluster_identity_review，schema1；本轮未发布为生产契约）补P/S分开标签和拓扑。顶层字段：source、reviewer、created_iso、session_id、source_session、reference_session、source_leveling、reference_leveling、artifact_id、evidence_sha256（01、03_r2、06_shadow）、review_notes。
3. clusters数组每项：frame、frame_seq、branch(P/S)、cluster_index、observed_track_id、cluster_semantic(PERSON/STATIC_OBJECT/MIXED/UNKNOWN)、real_person_ids（人工稳定ID，未知空数组）、visible_point_indices（frame-local原索引；不把区域语义套所有点）、human_point_indices、static_point_indices、unknown_point_indices、reason。
4. relations数组每项：frame、P_cluster、S_cluster、shared_point_indices（精确来源可机器绑定）、shared_semantic、P_only_semantic、S_only_semantic、same_real_person(YES/NO/UNKNOWN)、continuity(PRESERVED/FRAGMENTED/LOST/STATIC_NOT_HUMAN/UNKNOWN)、supporting_frames、reason。缺S可null；一个P→多个S各edge明确是否同一真人；多P→一个S分别标真人ID。不得用P/S track号相同代替真人身份。
5. point_semantics沿用FOOT_SHOE、LOWER_LEG、GROUND_RESIDUE、HUMAN_GROUND_MIXED、REGISTRATION_REFERENCE_MISMATCH、UNKNOWN。错配是跨帧/参考上下文判断，不自动从距离或高度推出。混合点不能据高低强拆。
6. 保持旧31损失cohort；人工可解释地面，但不能自动改T38-05总数、原验收表或gate。保留raw/frame-local index、ROS seq、全部SHA，不写captures或原evidence。

最小validator后续范围：身份/绑定/SHA、枚举与唯一键、cluster和point index在存档候选全集内、点子集互斥和覆盖、155行与12拓扑帧覆盖、真实ID/连续性不能矛盾、UNKNOWN不算闭合。它验证结构/一致性，不验证真人标签真伪。现有review_gt.js可先验证旧格式，不能代替上述sidecar检查。

执行优先31点7帧、24消失行、12拓扑帧（去重38帧），再覆盖155行97帧。原viewer缺的邻帧81/82/89/91/142只允许在新evidence派生viewer中补，旧viewer与历史输出不可覆盖。
