# GL-E01 R1 独立复核 / Go Flash / defaultDB / 2026-10-04

验收：`docs/human_fall/GLE01_ACCEPTANCE.md` v1（唯一表）。角色：只读独立复核，单一 writer=Codex 已停写。本目录 `.../evidence/2026-10-04_mainline_evidence_r1/opencode_review_01/`。

- ponytail（native skill）路径：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（未读/扫/哈希任何外部 Codex skill）。
- 复核会话：`ses_efcf6b467ffewHbmcPqpeFNz16`（记录在 `13_second_review.jsonl`）；模型 `opencode-go/deepseek-v4.1-flash` variant default；default DB。前置无工具 probe：`ses_efcf87e44ffe89UlqShFg6s6PY`，exit0，probe_ok=true（`11_service_probe_meta.json`）。规范 CLI session/model/export 由 Codex 提供。
- 复核前 HEAD/branch 与提交一致：`cbd0be1c86a1051a9a5800dfb7263f842896e1e6`；提交基线 `10_submitted_baseline.json`。
- 未改动 model/DB/auth/config/permissions；未写板端、未起 ROS topic/service、未部署/采集/网络/driver 变更；未改任何 author/验收/状态/旧文件。

## 1. 复核范围、命令与真实退出码

| 命令 | 真实 exit | 结果文件 |
|---|---|---|
| `ssh -o BatchMode=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=8 ldiar-wel "hostname; id -un; docker ps ..."` | 0 | 复核内联 |
| `Get-Content -Raw 01_remote_raw_probe.py \| ssh ldiar-wel 'docker exec -i slam-localization python3 -B -'` | 0 | `01_remote_raw_probe.json`（stderr 仅 LZ4 非阻断警告） |
| `python -B 02b_local_chain_verify.py` | 0 | `02b_local_chain_verify.json` |
| `python -B 03_remote_timestamp_loss.py` 经同一 SSH | 0 | `03_remote_timestamp_loss.json` |
| `python -B 04_fixture_checks.py` | 0 | `04_fixture_checks.json` |
| `ssh ... 05_remote_context_probe.py` | 0 | `05_remote_context_probe.json` |
| `python -B 06_manifest_scope_check.py` | 0 | `06_manifest_scope_check.json` |
| `python -B 07_ast_and_boundaries.py` | 0 | `07_ast_and_boundaries.json` |
| `python -B 08_manifest_after_check.py` | 0 | `08_manifest_after_check.json` |
| （保留）`02_local_chain_verify.py` | 1 | 本复核自身 ROOT 深度笔误，未产出证据；按不可变规则新增 `02b`，不改 02 |

作者原始退出码（只读观测，未复跑）：01=0、02=0、03=0、**04=1（首版 bag_time 位级比较，历史失败保留）**、04b=0、05=0、06=0。03 LZ4 警告非阻断，未装依赖，原 bag 全量解码。

## 2. 来源 start/end SHA 与冻结

- 提交清单 SHA 复核前后一致：`361516413ca0ae172730ccd32c8ebc2babb6ac938d5ed39382c1b4bb93e5ab7f`（不变）。
- 清单 38 项逐条与磁盘实际 SHA 全匹配（`06` listed_match=true，无 mismatch）。
- 基线 scope：`00_before`→`10_submitted` 仅新增 33、改动 3（`DISPATCH.md/README.md/WORKFLOW.md` 状态入口由 08_submit 更新），无删除；`10_submitted`→现在 仅新增、0 改动、0 删除，新增均在证据目录/本复核目录。**生产源码/原 captures/NPZ/旧证据无改动。**
- 关键冻结资产 start=end：meta `675c23de…`、points.bin `b81797f9…`、NPZ `f12f48bd…`、`bag2session.py` `e3c3a62c…`、`capture_input.py` `56355e95…`、`GLE01_ACCEPTANCE.md` `860c7f50…`、`returns/GL-E01.md` `99559199…`（与清单一致）。
- Python 3.8 AST：16 个脚本全部按 3.8 语法解析通过；板端脚本 02/03/05 无 live-ROS/写板模式（仅 `run_cli.py` 本地 Popen，属本地编排，不在板端）。

## 3. 独立复核方法（不复跑作者脚本）

- 远端 01 **不导入**作者 02/03、`bag2session`/`capture_input`；按 `msg.fields` 现场推导 offset/datatype，并用与作者结构化 dtype 不同的**字节拼接**方式重建 canonical 28B。
- 独立计算：bag 文件 SHA（读前/读后）、逐帧 header/计数/offset/drop/bag_time、逐帧 canonical/XYZ hash、聚合 canonical/XYZ hash、原始序列化 `msg.data` 聚合 hash。
- 独立本地 02b：对本地 `points.bin` 逐 28B 行做逐帧切片哈希，与远端逐帧哈希比对；独立解析 NPZ（`np.load`，非工程 loader）。
- 独立 03：对原始 float64@18 逐点 cast 到 f32，实测全量最大绝对损失。
- 独立 04：手工构造 26B 序列化记录，验证 offset/datatype/小端/28B padding；重实现既定比较策略并注入错误头/别名/同数异内容。

## 4. 关键独立结果

- 原 bag：`/root/catkin_ws/captures_remote/cap_20261002_163621.bag`，size `114550423`，magic `#ROSBAG V2.0\n`，SHA `bbbc0c00122c68c9c71cd6a799e4ee977f839cc4904d733f9660998df0ebd378`，读前=读后=metadata 声明。
- 单一 PointCloud2 话题 `/innolidar_points`（89）；另 `/inno_imu` 2092、`/device_status` 89，与 meta 一致。
- 源布局：`x/y/z/intensity f32@0/4/8/12`、`ring u16@16`、`timestamp f64@18`、`point_step=26`、`is_bigendian=false`、`row_step=width*point_step`、`len(data)=height*row_step`。重实现校验拒绝错误 offset/datatype/大端。
- canonical 28B 独立重建：`canonical_bin_sha256 = b81797f9825792655e5930edeb39c15275eb64e01999984884da61d252c599ff`，**逐字节等于本地 `points.bin`**；`canonical_xyz_sha256 = a4ad287ea14edd1ba584dd24dce866d7c4eacdc7ce2594edb2ddb1eef1b51c27` 等于本地 XYZ 与 NPZ `points`。89 帧逐帧 canonical 与 XYZ hash 全匹配，4372400 点，丢点 0。
- 帧↔meta：89 帧 `seq/stamp_sec/stamp_nanosec/offset/count/drop` 精确相等；`bag_time_sec` 满足冻结策略 `round(to_sec,6)`（如帧0 raw `1790930182.1775572`→meta `1790930182.177557`；末帧 raw `1790930191.2586439`→meta `1790930191.258644`）。首版 04 失败正源于误作位级比较，属真实审计失败而非伪造。
- timestamp 量化：全量独立实测 `max_abs(f64→f32)=0.00781099998857826`（argmax raw `183462.492189`），等于作者报告；理论半 ULP≈`0.0078125`。**远大于旧注释 `1s 内 <0.1µs`（约 7.8e4 倍）**，该注释不被数据支持；单位/时钟同步未核。frame header secs/nsecs 为精确整数，不把逐点量化混作 header 丢精度。
- 录制上下文：`config.yaml` SHA `bd428a1e…`（mtime 2026-08-03）、启用六零（roll/pitch/yaw/x/y/z=0，use_status=true）；`/var/log/inno_lidar.log` SHA `32970556…`（mtime 2026-10-02T09:33:51Z，**晚于 bag mtime 08:36:31Z**）；`/tmp/lidar.log` 不存在；config 目录仅 `config.yaml` 一份，无带日期 archive。无录制进程/启动与 bag 的联合绑定 → unknown。
- NPZ 历史字段未改：`source.source_bag_hash_verified=false`、`provenance.physical_verified=false`，`source_bin_sha256/meta_sha256` 与实际一致，帧与远端一致。

## 5. 完整验收表（本复核逐条结果）

| ID | 结果 | 复核依据 |
|---|---|---|
| A01 | **PASS** | 远端 01：指定原路径存在、size/magic、SHA 读前后一致且=meta 声明；SHA guard 拒绝不符输入；替代 captures 路径不存在（作者 02），非只信声明 |
| A02 | **PASS** | 远端 01 现场字段推导 + 04 手拍：offset/datatype/count/endian/point_step/row_step 全对；89 帧 header/点数/offset/drop/序号/bag_time(round6) 与 meta 全一致；错误布局/别名被拒 |
| A03 | **PASS** | 远端 01 canonical 完整 bytes=本地 bin；02b 逐帧 bytes/XYZ=bin 且=NPZ；同数异内容/篡改/帧 alias 负例通过；`source_bag_hash_verified=false` 历史字段未改 |
| A04 | **PASS** | 远端 03 实测最大量化误差 `0.007811`（对应 raw≈183460–183462）；04 浮点负例；显式 `units/sync=false`、不沿用未验证微秒精度、header 时间精确 |
| A05 | **PASS** | 独立远端 05 + 作者 05：仅指定 config/两日志/同目录名索引；SHA/mtime/摘录齐全；无录制窗口联合绑定，如实 unknown |
| S01 | **PASS** | 全树 baseline/scope 无越界；板端只读命令、无话题/写配置/采集；Python3.8 AST；停写后 fresh probe 已做、指定模型独立二审即本记录；start/end SHA 前后一致 |
| B01 | **PASS（仅来源链）** | A01–A03 独立通过，记原 bag→bin→NPZ 来源链 PASS；**不等于**地面/人体/单位/安装标定物理 PASS |
| B02 | **BLOCKED** | 录制外参/source-world-up/点云原点高度/四 box 地面身份无独立证据；当前 config/保留日志无联合绑定，保持 unknown |
| D01 | **NOT_RUN** | 未运行跌倒算法/性能/安装测量/部署/新采集；板端只读文件取证≠设备性能验证 |
| D02 | **BLOCKED** | 真实 DPR-only 浏览器环境当前无控制接口（仅 viewport w,h）；旧 GL04 V04/C12/M03 仍 NOT_RUN，不以 JS/CSS 替代 |
| Q01 | **PASS** | 正确 SHA/路径实测匹配；错 SHA 守卫、同数异内容/错 header 负例通过（未伪造实体 foreign bag，见 §6 限制） |
| Q02 | **PASS** | 原字段/offset/count/endian/rowstep/全帧时间离线手拍与远端一致 |
| Q03 | **PASS** | 89 帧映射/alias/乱序/header 变化/本地 bin 篡改/NPZ 身份负例全拒；一致帧全匹配 |
| Q04 | **PASS** | 逐点 f64→f32 有损量化显式输出误差；非 finite 处理明确；单位未核；header 原时间独立精确 |
| Q05 | **PASS** | 当前 config/旧日志与录制窗口绑定缺失被如实列出；physics 保持 unknown（B02 BLOCKED） |
| Q06 | **PASS** | 只读取证、无板端日志写入、提交 SHA/停写/probe/独立二审/冻结不变均核验 |

无 FAIL 条目。

## 6. 失败/限制与要求溯源

- **无验收 FAIL**。作者 04 首版 exit1 为真实审计失败（bag_time 位级比较），已保留原始 traceback 并以既定 `round(to_sec,6)` 策略修正（04b exit0）；未放宽任何数值精度门，header 始终整数精确。
- **可记录流程观察**：修正后仍复用 `04_local_chain_audit.py` 文件名、无独立 `04b*.py`；因首版在写 JSON 前即 raise，未发生证据覆盖（`04_local_chain_audit.json` 为 04b 成功产物，`04_local_chain_audit.txt` 为首版失败）。对交付无数据完整性影响，建议后续修订检查器一律新编号。
- 未证：物理单位/时钟同步；未伪造实体 foreign bag（“错误/外国 bag 拒”以 SHA guard + 手拍错误内容负例佐证）。
- Q01–Q05 均由本轮新增独立证据支撑，非复跑作者脚本；作者回归与测试数量不作完成定义。

## 7. 分层结论与 B01 来源可更新性

- **来源链层 PASS**：原 bag 身份/layout/帧/完整字节/XYZ/NPZ 来源与既有 meta/bin/NPZ 全量一致（A01–A03、B01）。这是**文件与来源身份**证明。
- **物理层 BLOCKED/NOT_RUN**：录制外参、source→world、原点高度、ROI 地面身份（B02）与设备跌倒性能（D01）、真实 DPR（D02）均无新证据。
- **主线上游 B01 来源可在新状态更新而不重写旧证据**：建议在 `WORKFLOW.md`/`README.md` 新增一条“GL-E01 R1 来源链独立复核 PASS（原 bag→bin→NPZ，物理仍 BLOCKED）”，引用本目录；保留 `real_candidate.adapted.npz` 内 `source_bag_hash_verified=false` 与旧 GL-I05 记录为历史，仅以新 sidecar（作者 03/04 + 本复核）补充证明。**禁止**回填旧 NPZ/旧状态、重算旧哈希或追改历史。

## 8. 本复核证据清单（sha256，00_review.md 外）

```
ce2acf2a0efa169569b6aa311d457ada2253e8c8ac73b84f97097bb638461133  01_remote_raw_probe.json
151e859baafb4710d3c7c8735e4f6168c0ea4e1753df1209353ea32005051c15  01_remote_raw_probe.py
19a63ab899a1a9648360109b2d96ed98aba431b2d8bae7930a4389c56d3bf706  01_remote_raw_probe.stderr.txt
13bf7b3039c63bf5a50491fa3cfd8eb4e699d1ba1436315aef9cbe5711530354  01_remote_raw_probe_exit.txt
a0288d2e0978b1d3ba7f60f09c54dd64702407be01bdce4f7f96309f0ba51be8  02_local_chain_verify.py   (retained, exit1 path bug)
84e0edd42692cef4a36dd14b00c8582221d15c5ef5d4f2beea97851df4689f45  02b_local_chain_verify.json
5ccbf48f89b78f2b5f65e99f6667530b882165f77d1401ea119773208fa4d6e8  02b_local_chain_verify.py
c3e84c4943ffaa91579de71229ee70381125fcc8b99dd4055f7cc2fd0d6e8ce4  03_remote_timestamp_loss.json
bb140ce0835d6e706e972885a874e7b15bc258959f88c786cbd1fbea542ae470  03_remote_timestamp_loss.py
19a63ab899a1a9648360109b2d96ed98aba431b2d8bae7930a4389c56d3bf706  03_remote_timestamp_loss.stderr.txt
13bf7b3039c63bf5a50491fa3cfd8eb4e699d1ba1436315aef9cbe5711530354  03_remote_timestamp_loss_exit.txt
40608e551d314310b4ba85fa831e81ef58ea03da72f109f8d884c6262019dd57  04_fixture_checks.json
749e644624ef0246211151786e287b1d1e9c5b65eae2b007394bb2a3d169cb47  04_fixture_checks.py
577646da51ec9b293b61d5129ae3baac985df991bc73707a0e2ff8fc0fb68f4b  05_remote_context_probe.json
251be20487fbd17fbcc6a0880a7b01b73ddf5a03db827a81b4698aace7bc6148  05_remote_context_probe.py
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  05_remote_context_probe.stderr.txt
13bf7b3039c63bf5a50491fa3cfd8eb4e699d1ba1436315aef9cbe5711530354  05_remote_context_probe_exit.txt
f0a7134ecd803a4c8894e256373c930095d040c2912fc3d46ca8207b85f3bfe6  06_manifest_scope_check.json
38eec8075bda97a9133349a545b981133afe998a38e1a6c62adf82fa18183ac5  06_manifest_scope_check.py
e2b42831aea777d17c0242c62d5717592a416a24caa478812b8e82249dfd2e80  07_ast_and_boundaries.json
2fc88f24ed7f3cf32944339a64464103e807288de041ffa3c08c1c7f4082b9da  07_ast_and_boundaries.py
33065e1d2be81ecd1990ed6aab37560bdc482106c8782f1238ae50bdb959c961  08_manifest_after_check.json
2c2153af9e12075f2eeaeb2c97a5d24166f19dd4b53cc02739b8ecbe2f746692  08_manifest_after_check.py
```

## 9. 状态

复核完成，**STOPPED**：不提交、不改 author 代码/状态、不宣布整单 ACCEPTED。软件来源链 A01–A05/S01/B01/Q01–Q06 通过；B02 BLOCKED、D01 NOT_RUN、D02 BLOCKED。GL-I05 既有软件 PASS 不变；无生产集成/标定/candidate 产出。
