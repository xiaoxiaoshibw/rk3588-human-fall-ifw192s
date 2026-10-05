# P02-C/D/E 同点集估计器对照报告（r2）

2026-10-04（Asia/Shanghai）。承接 r1（`2026-10-04_p02_ground_r1/01_DIAG_AND_PROPOSAL.md`，仅 baseline+诊断，未执行）。用户指明 ROI = 当前 annotator.html 的 #3 VAL。只离线研究/独占新证据目录；未修改生产源码/配置/UI/驱动/旧证据/原始采集；无设备/采集/部署。

## 结果速览

| ID | 结果 | 依据 |
|---|---|---|
| P02-C | **作者自验 PASS（待独审）** | ROI 定义/源码 SHA/显示矩阵冻结于 01；A 91 帧 48075 行 + C 102 帧 53873 行，joint 101948 点，行级 SHA256 固定；B 仅因果核验（低位 528→413→527、抬高 0→249→0，恢复成立）；三会话 meta/bin SHA 与 p02_session_check_r1 fresh checks 全一致 |
| P02-D | **作者自验 PASS（待独审）** | RANSAC(861/.05/seed20261001) vs covariance-TLS vs centered-SVD 同一 float64 数组；pairwise 角差 0.427°/0.427°/0.000°，Δd 0.000262/0.000262/0.0m，全部 ≤2°/.03m 工程参考；全域 RMS≈0.0131m、P95≈0.0252m、MAD≈0.0091m、支持率≈1.0 |
| P02-E | **作者自验 PASS（research candidate）** | 03_CANDIDATE.json：pitch 1.9016°、roll −5.8628°、tz 0.00752m（annotator 显示系）；det(R)−1=0、正交误差 1.1e−16、R·n=[~0,~0,1]、groundZ 有符号残差 RMS/P95/MAD 与 TLS 全等；A/C 逐帧 TLS spread 与 state spread 见下 |
| S01 | PASS（自验） | 04_ORACLE.json：三个 frame0 struct.unpack 逐点标量与 NumPy stride 解码精确一致；输入首尾零漂移；产物 SHA 固定 |
| D01 | NOT_RUN | 无设备/新采集/部署/网络/driver/生产外参写入 |

状态：**SUBMITTED**。作者自验不冒称 OpenCode 独审/ACCEPTED；P1-01 仍 NO（仅评估离线放行条件，不授权下游执行）。

## P02-C 冻结选择（先于估计器声明）

- ROI 来源：`pc_apps/human_replay/annotator.html:76` 当前 `#3 VAL` = pick_04 近距区，显示系 X[1.30,1.78]、Y[−0.40,0.22]；annotator.html SHA 入 00_BASELINE。旧 v11 静态 PNG/JSON 的 #3（X[1.9,2.4]）是不同编号体系，**未复用**。
- 显示变换：R=Ry(+26°)、tz=+1.340m（annotator.html:69,87 buildMatrix），4×4 矩阵入 01_SELECTION。
- 选择规则（拟合前冻结）：A/C 全部帧 0..90 / 0..101；finite 且非全零源行；2cm 边界内缩（X[1.32,1.76]、Y[−0.38,0.20]，排除边界带，**非残差门**）；全高度保留（A z∈[−0.0396,0.0986]、C z∈[−0.0370,0.0968]）；B 不进拟合。
- 因果核验（01 `causal_check_B_vs_AC`）：低位窗逐帧 median 528→413→527，抬高窗 0→249→0。与 r1 诊断（630→502→631 / 0→250→0）窗口不同（r1 用全 ROI、r2 用内缩拟合窗），模式一致。
- 与用户原实验记录（窄区 median 257→154→257）不冲突：那是原实验自己的更窄 ROI（源行待另行绑定），本单冻结的是 annotator 当前 #3 VAL 定义。

## P02-D 同域对照（101948 点，joint SHA 固定）

| 估计器 | normal (拟合系) | d (m) | RMS | P95 | MAD | 支持率(.05m) |
|---|---|---|---:|---:|---:|---:|
| RANSAC raw | [−0.031942, −0.109484, 0.993475] | 0.007786 | 0.01339 | 0.02583 | 0.00932 | 1.0000 |
| TLS (cov-eigh) | [−0.033009, −0.102146, 0.994222] | 0.007524 | 0.01310 | 0.02522 | 0.00905 | 0.9999 |
| SVD (centered) | 同 TLS（逐位一致） | 0.007524 | 0.01310 | 0.02522 | 0.00905 | 0.9999 |

- RANSAC↔TLS/SVD 角差 0.427°、Δd 0.000262m；TLS↔SVD 逐位一致（同一正交最小二乘问题的两种数值实现，**不构成独立物理证据**，已写入 02 notes）。
- 无 offset gate、无各自 inlier 精修、无点 cap、无 ROI 切换；三法输入为同一 float64 数组（SHA 入 02）。
- 193 帧为已曝光训练/稳定性域，非未见 holdout（02 notes 明示）。

## P02-E research candidate（不接运行时）

- pose：pitch **1.9016°**、roll **−5.8628°**、tz **0.00752m**（yaw/tx/ty=0），R=Rx(roll)@Ry(pitch)，frame = annotator 显示系（数学世界系）。**该姿态是"把此局部平面在此系转平"的外参，不是雷达安装角**——annotator 的 26° 是用户对格校准的名义安装配平，若再叠加会把研究候选错标成安装测量（本轮开发中曾犯此错，已在注释/limits 固化教训）。
- 几何校验：det(R)−1=0、正交 max|err|=1.1e−16、R·n=[2.8e−18, 1.3e−17, 1.0]、groundZ 有符号残差 RMS 0.0131 / P95 0.0252 / MAD 0.0091m（与 TLS 全等，刚体不变性成立）。
- 逐帧 TLS（源行不删异常帧）：A pitch 1.8737°±0.2196（std）、roll −5.8485°±0.1293、d 6.75mm±5.84mm；C pitch 1.9318°±0.1801、roll −5.8763°±0.1396、d 8.35mm±4.86mm。
- A−C state spread：|Δpitch|=0.058°、|Δroll|=0.028°、|Δd|=1.60mm —— 两空场地态间一致，扰动实验未留下残余几何漂移。

## 限制与不做的事

- ROI 仅 0.46×0.58m 通道地面一条；roll≈−5.9°/pitch≈1.9° 是该**局部区域**在显示系的几何姿态（可能为真实局部坡度/不平），不能外推全场，也不能与 P02-B iPhone 水平 anchor 直接对齐（不同位置、不同量具、消费级精度）。
- 未做 d/nz、refit-RMS 或任何外参优化（验收表明令禁止）。
- 历史 1.315 vs 1.594 分歧按 context_r1 §5 判定点域不一致：本轮同域对照显示同点集上估计器间差异 ≤0.43°/0.26mm，**支持**该判定，但未复现旧 1.594 运行，不做最终闭合声明。
- 原实验窄 ROI（257→154→257 的源）尚未绑定；本单不替代该绑定，只交付 annotator #3 VAL 的完整同域链。

## 命令与退出码

| 命令 | exit |
|---|---:|
| `python -B -W error make_baseline.py` | 0 |
| `python -B -W error p02_same_domain_estimators.py` | 0（consensus PASS，joint 101948 点） |
| `python -B -W error oracle_check.py` | 0（scalar==numpy ×3，drift=0） |

环境：Windows Python 3.12.10 / NumPy 1.26.4（本地离线）。产物 SHA 见 04_ORACLE.json `output_file_sha256`；已读 ponytail（C:/Users/30680/.codex/skills/ponytail/SKILL.md）与 scientific-toolkit。
