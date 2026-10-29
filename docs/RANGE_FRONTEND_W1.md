# W1 距离图像前端

本地独立入口：`src/human_fall_detection/scripts/replay_range_frontend.py`。节点、控制台和默认生产配置不使用此路径；不产生人体标签、跟踪身份或跌倒事件。

## 测量契约

- 复用 `core.capture_input.ROW_DTYPE` 的 28 B 解码。使用驱动既有 `ifw192s_azimuth_192x256.csv`、`ifw192s_elevation_192x256.csv`，按 ring 内最近方位匹配并核验仰角，容差 0.02°；表内容及容差绑定 grid SHA。
- 原生表是 **192×256**，每条方向均由表给出。旧表征的 192×240 等角投影会碰撞不同射线，不能作为精确标定。零 XYZ 没有可恢复的 column，保留排除行；重复回波选最近有效距离，等距取最小帧内行。
- 每格保留实际 `source_rows`，提升直接读取原始 XYZ，绝不补点。全局数据行等于 `offset_points + source_rows`。
- header 的整数秒/纳秒用于帧间时间。导出点时间是绝对秒 float32，在该会话约有 15.625 ms 量化；`row_time_s` 只是已存储时间的逐行均值，不用于去畸变，也不能证明精确扫描档位。

## 背景、分量和边界

显式 `--empty-prefix-frames 50` 指定开发前缀。前 50 帧只预热，第 51 帧开始使用逐射线中位/MAD，门限 `max(0.04 m, 4σ)`，σ 下限 0.005 m。支持不足的背景格为 unknown；空场资格仅开发声明，没有独立空场 GT。没有默认的全段统计、未来回填或无人推断。

背景绑定会话、坐标、grid 和 epoch。低有效率时抑制当前帧；大片距离变化锁存失效，需要重新建立背景。它是保守软件保护，不保证识别所有传感器运动。更新 API 只接收显式冻结掩码，禁止学习未知格和前景；回放默认完全冻结背景。

去噪只删缺少深度相邻支撑的测量格，边缘单独记账。8 邻域连通采用对称门 `|Δr| ≤ max(0.05, 0.012 min(r₁,r₂))`，不跨视场边界；小于 15 点的分量保留来源并标记未保留。组件 semantic 始终 unknown。

`--merge-ground <ground.json>` 可启用保守 3D 合并：必须显式给出同源坐标下的地面，只检查两格内边界的真实点间隙及合并尺寸/点数，不跨大孔洞猜点。实测消融收益小且会扩张参考外成员，默认关闭。它无法替代 W2 的时序目标归属。

## 复现

在仓库根目录运行（输出目录必须不存在，禁止写入源数据目录）：

```powershell
python -B -W error src/human_fall_detection/scripts/replay_range_frontend.py --session data/sessions/cap_20261018_110029 --out docs/evidence/<new_directory> --empty-prefix-frames 50 --reference-run docs/evidence/2026-10-22_human_pointset/target_replay_final --save-arrays
python -B -W error -m unittest discover -s src/human_fall_detection/tests -p test_range_frontend.py
```

输出 `GRID.json`、冻结背景、逐帧来源/组件 JSONL、独立计时 JSONL 和 `SUMMARY.json`；`--save-arrays` 额外保存每帧 range/valid/source_rows/点与行时间/intensity/foreground/residual/denoised/edge/labels。edge 仅统计前景边缘，不是飞点真值。

参考运行必须绑定完全相同的原始输入 SHA。按旧行交集选择最佳分量**只用于离线诊断**，没有实现新的目标选择器。报告保留率、Jaccard 和分散度时均指旧参考行；人体保留率、人体 precision/recall、跌倒效果和板端性能仍 UNKNOWN。G1 的点数中位、分散度分位和性能预算分开核对，不能据此宣布人体效果达标。

本轮机器证据与可复现命令位于 `docs/evidence/2026-10-23_range_frontend/`。串行计时与写压缩数组的运行分列，PC 数字不等于板端结果。现有原始数据、历史证据、默认路径与设备保持原样。

## 2026-10-23 P0修补及W2离线实验

新证据`docs/evidence/2026-10-23_range_p0_w2/`，最终冻结源码结果在`verified/`。开工五个W1源文件与历史最终SHA相同；修后新增绑定/指标字段，新账本SHA `c7ad4134b09088505b5bfce229aabd31ac9745bdf95d065cd6b66ea92781d4b4`，不再用旧`6cb7da…`代指新序列化。386帧全部保存数组及旧字段逐值不变，旧SHA仅为前件。

f360逐行账本确认2263=2100主片旧行+121其他分量旧行+41去噪拒绝+1背景未知；121/2221是分散度，163/2263是主片未覆盖，2221/2263是union覆盖。背景未知row34145前缀仅4次观测；未作人体/家具标签。67“参考外新增行增加”和79“总点数增加”分开记录。

`--merge-ground`现在要求完整source binding及实际provenance字节/原平面核验，历史仅带frame/provenance的MERGE_GROUND.json会被拒绝。新实验使用派生BOUND_GROUND.json，未重拟合或改合并门。背景BACKGROUND.json绑定cache SHA、输入、RAW坐标、grid/方向表、参数和前缀整数时间范围。

新增decode/source lift/ledger/JSON/IO细分与直接指标测试。最终三轮无细分PC P95 8.934/8.934/12.882ms；本轮早期三次低于10ms及随后慢轮全部保留，无加速结论。G1a2402.5点代理PASS，G1b5.448% FAIL/语义UNRESOLVED，G1c稳定<10ms FAIL。见verified/G1_DISPOSITION.json。

W2的当前真实组件归组不翻绿原G1b；结果、使用方式与失败门见[RANGE_TRACKING_W2.md](RANGE_TRACKING_W2.md)。生产默认旧链保持。
