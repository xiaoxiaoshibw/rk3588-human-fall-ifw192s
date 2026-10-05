# GL-C01 冻结源行联合反解pitch/roll/tz / 唯一验收 v1

2026-10-04 当前GL-C01小点：SUBMITTED / STOPPED。作者联合反解与必要自验完成；C01–C07/Q01–Q05为自验结果，真实独立验证质量FAIL；S01/Q06指定独审阶段NOT_RUN，P01 BLOCKED，D01 NOT_RUN。用户明确“这一个小点做完先停下来”，本轮不派新的probe/独审/后续开发。[收口](evidence/2026-10-04_gl_c01_r1/20_CLOSEOUT_01.md)。判据v1保持，未独立验收/ACCEPTED。

| ID | 要求 / 反例 / 预期 | 检查入口 | 结果 |
|---|---|---|---|
| C01 | R=Rx(roll)@Ry(pitch)，第三行=n_source；从单FIT的TLS n/d联合求pitch=atan2(-nx,nz)、roll=asin(ny)、tz=d；正向/逆向/已知GT/退化严格 | pure solver与scalar oracle | PASS（作者自验，未独审） |
| C02 | FIT单source frame；3个validation frame_group互异且不同FIT；先源行冻结，换参数不按新rectangle重选、不pool所有框/帧进FIT | frozen selector/gate/ID | PASS（作者自验，未独审） |
| C03 | typed kind/schema/unit/from-to/source/model/row identity；bool/string/NaN/alias/重复/跨组/越界/caller/sameID内容变更拒；新ID新输出 | 集中tests/CLI | PASS（作者自验，未独审） |
| C04 | 同一个FIT平面对3个验证组全选定点计算正交RMS/P95/support，沿用20/.03/.05/.8；失败如实FAIL；每区自拟合只诊断不能替代共同平面验证 | frozen settings+known divergent regions | PASS（作者自验；实际质量FAIL保留） |
| C05 | 正交残差在同一刚体before/after下不变；采样/支持/行数不偷偷改变。vertical OLS与orthogonal口径分开，不将剩余误差断言真实地板起伏/物理下限 | metamorphic invariance/图/实际统计 | PASS（作者自验，未独审） |
| C06 | 初始名义参数和数据估计分开，roll与地面坡度不可辨；kind=joint_ground_level_estimate、physical/extrinsics/runtime/candidate=false；即使质量PASS也不等于原fitter搜索/竞争PASS | 冻结资格消费者拒 | PASS（作者自验，未独审） |
| C07 | 99帧原local meta/bin实际SHA严格adapter，不移植89帧来源链verified；用户pick XY作为源行候选，全部高度保留，不按待受验Z/residual筛validation；外部trim/门改动只审计不采用 | source provenance/selection/基础审计 | PASS（作者自验，未独审） |
| S01 | ≤3新源码、stdlib+NumPy/Python3.8；先diag/全treeSHA→自验/manifest/return→停写→指定只读独审；B/N01及冻结数学/配置/UI/driver/旧evidence保持 | scope/regression/model/session | NOT_RUN（用户要求完成小点后停；未派独审） |
| P01 | 源行真实地面标签/独立安装与精度测量、99bag原链未独立核；物理BLOCKED不阻数据反解；用户75cm参考作为独立诊断不调参过门 | 人工/物理层 | BLOCKED |
| D01 | 不设备/新采集/部署/网络/生产接入/IRLS | scope | NOT_RUN |
| Q01 | 输入/schema/unit/frame/finite/empty/degenerate → C01/C03 | 合成tests | PASS（作者自验，未独审） |
| Q02 | 同ID内容/caller/source更换/model变更/已有out/保护目录 → C02/C03/C07 | 身份组合 | PASS（作者自验，未独审） |
| Q03 | 同帧/跨帧pool/alias/重复/越界/invalid源行/重新选rectangle → C02/C07 | selector反例 | PASS（作者自验，未独审） |
| Q04 | clean/noisy/parallel-offset/table污染/line × 同FIT平面val全部残差/局部自fit → C01/C04/C05 | GT与full-point真实 | PASS（作者自验，未独审） |
| Q05 | 成功估计/质量FAIL/全部字段 × candidate/physical/runtime禁晋级 → C06/P01 | producer/consumer | PASS（作者自验，未独审） |
| Q06 | 旧来源/参数/检查/证据冻结/首尾SHA/停写/probe/指定模型/不可变输出 → S01 | controller | NOT_RUN（用户要求完成小点后停；未派独审） |

本单数值估计/报告不是GL01 constrained fitter正式candidate，不跳过它的搜索竞争/完整性门；当前89/99数据均已曝光，不能作为未见最终物理holdout。数据平面反解不要求独立instrument先到位，但必须保留模型与测量的区别。
