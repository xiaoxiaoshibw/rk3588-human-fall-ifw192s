# 四区联合配平 / P02 v2 / SUBMITTED（作者自验）

用户要求截图中的四个区域全参与算法。本轮在原同一HTML更新三算法参数、四色区域点和逐区残差表，旧HTML与P02 v1表完整保留00。原3D annotator/SDK/driver/采集不改，1.14m实测高度另存不覆盖。ponytail与scientific-toolkit实际路径记录00。

## 冻结数据域

A91+C102共193帧，四个ROI按当前annotator定义各边2cm内缩；全部finite/nonzero source行、全高度，B不拟合。union内没有重复源行，row/session/region/frame/XYZ全存02_FROZEN_POINTS.npz。四区共**392196点**：#1=151861、#2=90803、#3=101948、#4=47584。按每个原始点等权（不是每区域等权）。先冻结，再估计，不按结果改ROI/裁尾/调门。

三估计器复用R2已读pure函数AST，只载函数定义，不运行其main/旧输出；RANSAC=861/seed20261001/.05，不精修自身inlier、不cap/offset gate；TLS covariance与SVD centered同点域，仍是同一最小二乘问题的两种实现，不当独立物理证据。

## source→display结果

| 方法 | pitch (°) | roll (°) | tz=d_S (m) | 全点 RMS (cm) | P95 (cm) |
|---|---:|---:|---:|---:|---:|
| TLS | 26.623261 | -1.394671 | 1.321900834 | 1.8921 | 3.7916 |
| SVD | 26.623261 | -1.394671 | 1.321900834 | 1.8921 | 3.7916 |
| RANSAC raw | 26.649914 | -2.135552 | 1.322681966 | 2.0218 | 3.8253 |

R=Rx(roll)@Ry(pitch)，active列向量innolidar→display，yaw/tx/ty=0；单位n、tz=d，不用d/nz。三方法最大normal差.74136°、offset差.00078113m，过原2°/.03m参考。四个区域在三方法共同拟合后的全点RMS/P95/support都过既有门。

TLS逐区RMS/P95（cm）：#1 2.063/4.216，#2 1.366/2.583，#3 1.873/3.560，#4 2.202/4.869。与旧单#3局部roll−5.8628°相比，联合模型以多个位置约束一个平面；单#3本身不再最小残差，但其他区域更一致。不能把这个改善叫仪器物理精度改善。

## 留一区诊断（独立于当折fit，非未见最终holdout）

每次只用其余三区fit同一个TLS plane，全点预测该区，没有裁尾/重选验证点。

| 留出区 | RMS/P95 (cm) | 结果 |
|---|---|---|
| #1 | 2.507 / 5.378 | FAIL（P95） |
| #2 | 1.906 / 3.432 | PASS |
| #3 | 2.695 / 5.159 | FAIL（P95） |
| #4 | 4.331 / 7.745 | FAIL（RMS/P95/support） |

这些FAIL在HTML用红色明确保留。**四区参与拟合可通过，并不证明三块可预测第四块或整个场地物理已标定。** 当前结果只交付用户要求的已知四区观测数据显示；不解释偏差原因是地板起伏/SDK特定函数，没有对应证据。

## frame spread / 物理边界

A逐帧source TLS：pitch26.62297±.01808°、roll−1.39537±.03436°、d1.321848±.000768m；C：26.62359±.01891°、−1.39399±.03385°、1.321950±.000798m。±为各态已曝光帧std，不是仪器/独立标定误差。min/max在07摘要。

当前plane观测距离与实测1.14m差约.181901m，物理datum/点云偏置仍未闭合；iPhone消费级anchor不提供精确误差界。无测距dist-.10/SDK改动，不升级physical_verified/runtime_eligible，P1-01 NO。

## 逐ID自验

| ID | 结果 | 证据 |
|---|---|---|
| P02-C | PASS（作者自验） | 02全部392196点source/row/session/region/frame保存；05全源行与实际bin精确对应，A/C91/102帧，B0点 |
| P02-D | PASS（作者自验） | 03同域三估计器、全点/逐区原门，source normal/d consensus；原函数SHA在00 |
| P02-E | PASS（离线数值与如实报告）；物理/外推BLOCKED | 03全部四折FAIL保留/193逐帧；05properR/Rn/signedZ/inverse，07spread；qualification false |
| S01 | PASS（作用范围与页面逻辑作者自验）；指定独审/实际browser NOT_RUN | 06九片段×三列、四色ROI、全点Z标量误差≤8.88e−16m、所有预览source样本不变、失败表可见；07PNG已查看；09终SHA |
| D01 | NOT_RUN | 不设备/采集/部署/网络/driver/生产外参 |

命令fit_four_regions.py、update_html.py均python -B -W error exit0；05独立全bin源行和转逆变换检查exit0，06 Node页面检查exit0。数据模式/本地数学验证，不冒称指定OpenCode独审或实际browser渲染。作用范围只有研究与用户指定HTML，不重复无关ROS回归。

07_HTML_BEFORE_METADATA_CLEANUP保留初次更新版本；最终HTML删掉上轮单#3模型的旧metrics，当前metadata与四区模型一致，旧数值只保留历史快照。旧manifest指其原版本；09指当前授权版本。回退可打开00旧HTML，不回滚其他共享文件。
