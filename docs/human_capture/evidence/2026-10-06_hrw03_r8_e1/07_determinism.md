# 07 · E-1 确定性 / 守恒检查

## 1. 确定性（工单 §11）

同输入（`meta.json` / `points.bin` 各会话 2 份 + `human_pipe_lib.js` / `human_replay_lib.js` + 冻结 ICP 参数）运行 **20 次**：

- **19/20** digest `5468d27f23449f29…`（60 字符前缀一致，完整 SHA 见 `04_voxel_results.json.digest`）；
- **1/20** Windows 文件系统锁错误（错误码 `-4094 / UNKNOWN`，IO 层，不是算法不确定性）重跑后即得同一 digest。

### Digest 口径

- **不含**：`generated_utc` / 绝对路径 / 运行耗时；
- **含**：`ticket` / universe 数 / `label` 总数 / region 表（vx/point-weighted）/ 站点残块点标签分布 / icp_frozen 公开登记。

### 运行命令

```bash
node 03_e1_probe.py    # = node 03_e1_probe.py（.py 是工单 data contract；Node 执行）
```

## 2. 守恒（工单 §10）

| 检查 | 结果 |
|---|---|
| universe 标签互斥：STATIC + MOVABLE + UNRESOLVED = 3707（= universe） | **PASS** |
| 每帧可见性位图长度 = 165（current）/ 102（reference），无越界写入 | **PASS** |
| universe voxel 键集合 = ref occ≥0.5 键集合（与 `PL.reference_static_keys(ref, 0.5)` 完全同式，**0 mismatch**） | **PASS** |
| 在线 tier 复刻（hits/occ 阈值/邻域） vs 生产 `PL.build_static_map` 逐键（tier 命中集合 + hits 数；0 mismatch） | **PASS** |
| reference 体素计数 = 5286（与 R3.1/r7 等价门复核一致） | **PASS** |
| 站点残块点集 1875 个互斥标签（STATIC+MOVABLE+UNRESOLVED+NO_REF_VOXEL = 1875） | **PASS** |
| `mismatch_4bytes` / unknown 类标签用量 = 0（出现即判 FAIL） | **PASS** |

## 3. Digest 稳定性语义

digest 只在以下任一**语义输入**变化时才会改变：

- 会话点云内容；
- `human_pipe_lib.js` / `human_replay_lib.js` 内容（matcher/builder 语义）；
- 冻结 ICP 参数；
- 判断规则源码（本脚本）。

时间戳、绝对路径、运行时长**不参与** digest → 20 次运行结果可等价比较。

## 4. SHA 登记

`04_voxel_results.json.inputs` 逐文件登记：
- `pc_apps/human_replay/human_pipe_lib.js` / `human_replay_lib.js`（同时给 raw + canonical 两种 SHA，canonical = CRLF→LF 归一）；
- `captures/remote/cap_2026100?_*/meta.json` 与 `points.bin` SHA256；
- `captures/leveled/<job>/tls/transform.json` 的 SHA。

这些登记使任何 reviewer 都能本地复算与核验冻结条件。
