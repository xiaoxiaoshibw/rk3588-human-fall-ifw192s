# 反例驱动文献核查 / 2026-10-04

关联03_minimal_counterexample_01.md，A04/Q03。只作为方法依据；不移植论文门槛/速度/传感器高度。

| URL / 版本 / 读取情况 | 适用前提与采用/否定理由 |
|---|---|
| https://cmp.felk.cvut.cz/~matas/papers/chum-dagm03.pdf / Chum-Matas-Kittler, DAGM 2003；直接open Internal Error，search同作者PDF提供摘要，未声称全文 | 最小无外点样本不一定支持全部内点的前提与本例一致。借鉴精炼方向，摘要不支持本项目固定轮数已收敛。 |
| https://www.bmva-archive.org.uk/bmvc/2012/BMVC/paper095/paper095.pdf / Lebeda-Matas-Chum, BMVC 2012；11页官方全文已读 | 采用同随机样本对照、局部最小二乘、精度/耗时取舍与截断平方诊断思想。其best-so-far触发、阈值缩放、随机内点子集及图像参数不适用于本单完整W契约，因此不照搬；保持原门、全部合格seed及同sampled域。 |
| https://pointclouds.org/documentation/sac__model__perpendicular__plane_8hpp_source.html / PCL 1.15.1-dev 官方源码，isModelValid行93–120 | 用户axis与角度门决定模型资格；不提供实际up。每轮重查项目有向normal/height门，不能复制PCL无向夹角去猜安装。 |

候选解释：一次TLS成员偏斜可由重新内点选择改善；另一方面完整W中少量见证竞争不等于多物理地面。固定K=2/3测试前者，不用小J/只优化best删除后者。当前IRLS条件未触发，不引入权重模块。最终是否采用必须同输入结果决定。
