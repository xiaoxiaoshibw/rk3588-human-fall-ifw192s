# Coordinate evidence and physical boundaries

| Evidence | Time / scope | Supports | Does not support |
|---|---|---|---|
| Approved draft (manifest in 11_submission_manifest.json) | reviewed 2026-10-03; original bytes frozen | up [0.438371,0,0.898794], height [1.2,1.7], four fixed boxes are approved inputs | no newly measured extrinsic or ground identity |
| 163621 source meta/binary/NPZ | bag window 2026-10-02 16:36:22.177557–16:36:31.258644 +08:00; meta creation 16:47:45 is extraction | canonical source row/frame lineage, 89 source frames | meta lacks recording-bound driver/config/extrinsic identity; original bag/layout proof B01 remains missing |
| GL-I03 research_01/31_EVIDENCE_AND_NEXT_STEPS.md | old runtime 2026-09-30, H_runtime_config_log SHA c82804d9c096ac06d9bbf57f20e31b693188f0396d540c4784589da4c9971015; K_container_env_logs SHA f6a4a0cefe2da6460c649bacd8c0e4169046c838d6aced40e9de5e40c77e5a27 | SDK extrinsic enabled with six zeros at that historical time | does not establish six zeros for the 2026-10-02 recording |
| Local XYZ chain, examined in prior source evidence | publisher SDK XYZ -> bag2session -> capture_input canonical decode | local adapter does not silently flip X | SDK may have already applied recording-time extrinsic |
| Diagnostic frozen/PCA normal | same approved single FIT frame; WHAT_IF labels | reproducible geometric orientation and residual observations | model normal is neither a measured world up nor proof of ground identity |

Conditional rotation: right-handed column vectors with active R=Ry(+theta) mapping source vectors to world vectors. R*source_Z describes source Z in world. World up [0,0,1] expressed in source is R.T*world_Z=[-sin(theta),0,cos(theta)]. Passive world->source coordinate change is inverse R. At 90 degrees the two expressions are [+1,0,0] and [-1,0,0]. Only a measured, recording-bound from/to rotation allows this conditional calculation to identify an actual prior. CLI stores both the 90 degree hand fixture and conditional 26 degree illustration; neither is a measurement or a draft correction.

Reported actual approved fit returns ground_degenerate although replay shows angle rejection, not an SVD collapse. Both WHAT_IF inputs remain competition_unresolved. Native validation never ran in these three real fits. Posthoc holdout and 356 box-frame statistics do run, on all selected points, without residual-based selection. High/low residual tails are geometric labels only. Frame median standard deviations reproduce 0.311/0.435/0.951/0.543 mm and do not establish robot immobility or tail identity.

B01/B02 remain BLOCKED. D01/D02 remain NOT_RUN. No calibration/ground_derived artifact, deployment, capture or device change.
