# P02 C/D/E 离线确认点集与同域求解 / 唯一验收 v1

2026-10-04 当前HTML更新：用户指定同一06_PREVIEW.html，已加“算法配平”按钮及TLS/SVD/RANSAC选择；S01/E页面逻辑作者自验通过，实际browser/指定独审NOT_RUN，物理全场/P1不晋级。[本轮](evidence/2026-10-04_p02_html_algorithm_r1/06_CLOSEOUT.md)。旧HTML完整版本保留，旧manifest指旧版。
2026-10-04 当前：离线预览 SUBMITTED（作者自验，未指定独审/ACCEPTED）。默认参考annotator Ry(+26°)+Z1.340，#3局部修正另作对照；实测1.14保持，P1 NO。[预览/本轮结果](evidence/2026-10-04_p02_level_preview_r1/11_REPORT.md)。下方R2为历史过程结果。
2026-10-04：用户指明 annotator 的 #3 VAL，承接本次上下文恢复任务。只离线研究/独占新证据，不修改 GL-C01 既有表、生产/配置/UI/设备。初始状态均 NOT_RUN，运行后按固定ID记录，不以测试总数验收。Codex作者结果不是OpenCode独审/ACCEPTED。

| ID | 冻结要求 / 负例 / 证据 | 结果 |
|---|---|---|
| P02-C | 当前annotator #3的定义/源码SHA/显示矩阵冻结；A/C全部帧finite非零源行，2cm边界内缩，全高度，无拟合Z/residual过滤；B只因果核验，meta/bin/row/pointSHA一致 | PASS（离线作者自验）— 新04完整冻结A/C源点/行号/session/frame；原源行SHA不变 |
| P02-D | 同一个P02-C输入给raw RANSAC/covariance TLS/centered SVD；无offset gate/独立inlier精修/换ROI；统一n符号；全域RMS/P95/MAD、支持、pair angle/Δd、estimator pose spread；2°/.03m作为复用工程一致性参考，不声称物理精度 | PASS（数值子项/沿用R2同域搜索）— 新10回source三estimator差≤.427021°/.000738511m；本轮未独立重跑RANSAC |
| P02-E | 仅C/D成立后输出research candidate，R=Rx(roll)@Ry(pitch)、active列向量source→ground、yaw/tx/ty=0、tz=d；Rn=up、properR、groundZ=signedres/刚体不变性；A/C逐帧TLS pitch/roll/d range/std、state spread、消费级水平anchor限制；不使用d/nz/refitRMS优化 | PASS（离线source数值模型）；物理/全场BLOCKED— 新01 source→display模型与10逐帧spread；不覆盖1.14m、不接runtime |
| S01 | 新research脚本/检查/产物的SHA、baseline、源点标量核验、输入首尾不变、旧证据/源码保护；已读ponytail；不冒称独审；当前kind不接runtime | PASS（作者自验范围/数值/页面逻辑）；独审/真实browser NOT_RUN— 新09保护SHA、08控件检查、PNG实看 |
| D01 | 无设备、新采集、部署、网络、driver/生产外参写入 | NOT_RUN |

2026-10-04 R2 状态：**SUBMITTED**（Codex 作者自验；独审未指定，整单未 ACCEPTED；P1-01 NO）。证据 [2026-10-04_p02_ground_r2](evidence/2026-10-04_p02_ground_r2/05_REPORT.md)，回传 [returns/P02.md](returns/P02.md)。R1 目录（baseline+诊断未执行）与 context/session_check 证据保留。

RANSAC=861固定seed20261001、阈值.05m，直接三点假设在全冻结点集评分，按最大支持/最小全域median选择；不在自己的inlier子集精修。采样是RANSAC估计机制，不是另造confirmed输入域。TLS与SVD是同一最小二乘问题的不同数值实现。193帧已曝光训练/稳定性域，不当未见holdout；P1-01仅评估用户要求的离线放行条件，不授权下游执行。

本单先保存唯一冻结选择，再拟合。无点集重新选择/删失败帧/门调宽。比较若FAIL保留结果，E NOT_RUN且P1 NO。
