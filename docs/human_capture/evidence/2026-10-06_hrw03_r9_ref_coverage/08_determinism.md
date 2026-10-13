# 08 · R9 确定性 / 守恒 / 复用等价门

## 1. 确定性（工单 §12）

同输入（两会话 `meta.json`/`points.bin` + `human_pipe_lib.js`/`human_replay_lib.js` + 冻结 ICP）运行 **5 次**：

- **5/5** digest = `ef6e1c2c191c6e30c7f1e82dac365ab976ba3a1decc3935eff979139d0f75259`（全等）。
- 说明：输出 JSON 含 `generated_utc` 时间戳字段 → 跨秒 run 的**全文** md5 会差（仅时间戳）；
  **digest 字段不含** `generated_utc`/绝对路径/耗时 → 语义内容逐比特确定。

### Digest 口径
- **不含**：`generated_utc` / 绝对路径 / 运行耗时；
- **含**：ticket / 各等价门计数 / station 类别计数与比例 / unique-voxel 计数 / C1 直方图与临阈计数 / 控制区分布 / 档位参数。

### 运行命令
```bash
node 03_ref_coverage_probe.py    # .py 是工单 data contract；Node 24 执行
```

## 2. 守恒（工单 §12）

| 检查 | 结果 |
|---|---|
| point 级 Σ(C0+C1+C2+C3+C4+C5+C6+C7) = 1035 | **PASS**（0+25+904+106+0+0+0+0） |
| unique-current-voxel 级独立守恒 Σ = 40（n_voxel） | **PASS** |
| obs-weighted 守恒 Σ = 1035（unique voxel × 组内点数） | **PASS** |
| 控制区每 region 类别分母 = 各自 n（757/917/597/1540），fracs 自洽 | **PASS** |
| 特殊：C2 occ≥0.5 = 904/904；C3 close_cell_occ≥0.5 = 106/106（预注册「应为 0」的隐藏 gate 未出现） | **PASS** |

## 3. 复用等价门（复用 E-1 冻结产物；**非新实验**）

| 门 | 期望 | 实测 | 结果 |
|---|---|---|---|
| ref builder 体素数 | 5286 | 5286 | **PASS** |
| universe（occ≥0.5） | 3707 | 3707 | **PASS** |
| online map 键数 | 1720 | 1720 | **PASS** |
| 站点残块 1875 点标签 STATIC/MOVABLE/UNRESOLVED/NO_REF_VOXEL | 0/0/840/1035 | 0/0/840/1035 | **PASS** |
| 站点残块标签序列 digest（f+label）与 E-1 比对 | 相等 | e1=r9=`3b5f8aded7c368a2` | **PASS** |
| `occ` 由原始整数位图重算 == `build_reference_map.obs` 逐键 | 0 mismatch | 0 | **PASS** |
| ref raw 点（工作空间内）落进 rawCell | ~100%（量化边界可邻格） | in=3,131,751 / outside=**0** | **PASS** |

## 4. SHA 登记

`04_raw_support_results.json.inputs` / `.transforms` 逐文件登记（含 `human_pipe_lib.js`/`human_replay_lib.js`
raw+canonical SHA、两会话 meta/points SHA256、两会话 TLS transform SHA、冻结 ICP euler/t/R_flat 明文），
任何 reviewer 可本地复算核验冻结条件。
