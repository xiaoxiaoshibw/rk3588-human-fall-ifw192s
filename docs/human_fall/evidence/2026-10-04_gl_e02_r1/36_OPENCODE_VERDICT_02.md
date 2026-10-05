# GL-E02 R1 指定独审（read-only）— 最终结论

- 模型/会话：opencode-go/deepseek-v4.1-flash / default DB。本次由 root 以新编号 33 流承接。三源码 STOPPED 不变。
- 只读边界：仅用 read/bash stdout；未 write/edit/patch，未重定向入文件，未新建 checker，未改动 source/tests/config/drafts/文档/旧证据；未调用 prepare_packet（无必要），未运行设备/采集/部署/拟合/IRLS。

## 一、独立复核（非仅重跑作者断言）

1. **28 manifest 全文件流式 SHA（75 项）**：0 mismatch；`acceptance` SHA `331fe4…4792` 匹配；HEAD `cbd0be1…`、branch `master` 匹配。（首轮因 `'GLE02_ACCEPTANCE.md v1'` 尾注路径报错，去尾注后匹配。）
2. **保护基线 before/after**：01(3896 文件) 与 27(3970) 对磁盘逐文件重算——`changed_vs_01=0`、`changed_vs_27=0`、`A vs B 值差异=0`；`missing=0`；仅 `src/CMakeLists.txt` 为 Windows 断链（lstat 保留，符合约定）。onlyB=74 全部为本单新 evidence（含三新码 + 四 packet + 源 .txt）与 3 个外部照片注释文件。
3. **外部新增 3 文件**：26 已如实登记为 `outside_scope_added`（`annotated_roi_v6.*`、`make_roi_annotation_v6.py`），mtime 15:47–15:48、size 明显异于 v1(1.44MB vs 0.73MB)，判定为本轮外部工具产物；未回滚、未计入生产码/人工源行，已按指令单列上报。
4. **当前输入/产物**：20_real_request_03 `request_id` 重算一致且=`packet_id`；npz/chain/audit/photo/photo_record 引用 SHA 全对；`load_adapted` 得 89 帧 / 4,372,400 点 / frame=`innolidar` / units=`m` / 窗口 `[1790930182.177557, 1790930191.258644]`，与 `expected_source` 全匹配；packet_03 与 packet_04 五 JSON 逐 byte 相等。
5. **对抗性临时 fixture**（临时目录外 repo，未写原输入）：选择内容改而 request_id 未改→拒（同ID异内容）；选择改后 request_id 更新但 selection_id 陈旧→拒；`world_up` frame 不符→拒；disabled 但 R≠I→拒；det=−1 非真旋转→拒；enabled 真旋转（R·Rᵀ=I, det=1）→接受；重复 code_refs→拒；`photo_recording_binding.installation_unchanged=False`→拒；unknown 值带非空 binding→拒；output==RUN_ROOT→拒；父目录不存在→拒；validation 与 fit 同帧组→拒；height known 但 origin_definition unknown→拒；known up 无完整录制绑定仍 unknown。**作者未预置真旋转接受用例，我独立确认其正确通过。**
6. **套件**：`test_ground_evidence_input.py` 15/15 PASS；全 fall 回归 438 PASS；follow 2 PASS。**02 首版 `02_checks_01.log` 真实 FAIL（E01 fixture "ab"*32 写成同值未改内容，assertRaises 未触发）在 02_checks_01_meta exit=1 保留**，作者说明属检查 fixture 缺陷、改 "ef"*32 后原断言不降级——source_01→02 的 diff 证明确为 fixture 修复而非降低要求。3.8 语法：三文件 `ast.parse(feature_version=(3,8))` OK，仅用 stdlib（copy/datetime/hashlib/json/math/pathlib/argparse/sys/tempfile/unittest/numpy）。

## 二、逐条结论（不含测试总数替代）

| ID | 结果 | 依据（函数/检查/证据） |
|---|---|---|
| E01 | **PASS** | `prepare_packet` 先逐文件 `sha256_file`==ref（含 prepare 前/后两次 1<<20 分块）；`load_adapted` 以实际源重算 canonical manifest；跨核 bag/meta/bin/npz/xyz 与 chain/audit 帧级一致；`read_bound_json` 强制解析快照 SHA 等于绑定 ref（source_04 新增）。旧 NPZ 未回填、未改。 |
| E02 | **PASS** | 严格 `keys`/`kind==ground_evidence_request`/`schema==1`/`units=="m"`/finite/`allow_nan=False`；`expected_source` 与运行时派生 binding 严格 digest 比对（source/window/run/config/code）；当前/9-30 上下文不晋级，run/config 缺省→unknown。 |
| E03 | **PASS(software)** | `check_measurement`：方法白名单（含 `fit_plane_offset`/`PCA` 被拒）、单位/量纲、`optical_window`≠`point_origin`、height≥0、真旋转校验、disabled 必 I、from/to 方向、uncertainty≥0；unknown 值/binding 必 null；known 观察与 `recording_eligibility`（unknown vs cited_pending_review）分离。照片仅作 known 观察、不自动赋物理资格。 |
| E04 | **PASS(software)** | `check_selection` 复用冻结 `gate_selection`：fit + ≥3 validation、互异 ID、`source_sha256==bin`、仅 `independent_manual_source_rows`、rows 严格 int/唯一/越界、帧互斥、人工 confirmation person/time/basis/landmarks/refs；显式逐行映射 `pooled_row/source_row/ordinal/seq`。不按 FIT 残差筛 holdout。真实 selection=null，不造 source 行。 |
| E05 | **PASS** | 仅五输出 JSON；packet 固定 `physical_verified/extrinsics_verified/candidate_eligible/runtime_eligible=false`、`review_status=pending`；缺料稳定输出 unknown/待补 gaps 而非拒合法 pending；未知晋级字段被 `keys` 严格拒。 |
| E06 | **PASS** | `request_id`/`selection_id` 内容寻址、无缓存；`read_snapshot` 单次读取保 SHA/解析一致；输出必须在 RUN_ROOT 下新子目录、`resolve()==absolute` 防穿越/符号链接、`target.exists()` 独占、输入包含关系拒绝、父目录须已存在；同内容 packet_03/04 逐 byte 相等，已有 out exit2。 |
| S01 | **PASS(process)** | fresh 全树 before/after SHA 零漂移；三新代码路径 SHA 记录；相关回归 438+2 PASS；真实 exit/model/session/manifest 齐备；作者已停写、按 29 派工独审。Python3.8 仅 AST，非板端 3.8.10/NumPy1.17.4 实测（已如实声明）。 |
| P01 | **BLOCKED** | 照片真实/参考视向 user_confirmed、`07_user_reply` “刚刚拍摄”均为 known 观察并保留，但 SDK/up/原点/源行/安装连续性 unknown；不推断 26°、PCA up、拟合 d≈1.33m。17 缺口表 + packet_03 measurement/selection=null。不因 E 软件 PASS 闭合。 |
| D01 | **NOT_RUN** | 无设备算法/新录制/部署/网络/driver 配置改动（未执行，符合本单）。 |
| Q01 | **PASS** | 缺/坏 schema/NaN/单位/非有限/错误数值类型/缺文件均拒；合法 pending 正例存在。 |
| Q02 | **PASS** | 同内容复跑/同 ID 异内容/new ID/caller 原地改/已存在 out/受保护目录全组合（含我独立真旋转与 selection_id 陈旧用例）。 |
| Q03 | **PASS** | 当前 config/旧日志仅观察不晋级；run/config/窗口/code 错绑定拒。 |
| Q04 | **PASS** | 下视≠测角；PCA/fit_offset 方法拒；窗口≠原点；from/to 逆向拒；单位/负 height/非单位 up 拒。 |
| Q05 | **PASS** | fit/三互异 validation 正例；跨组/同组/duplicate/alias/越界/bool 索引/残差方法/缺人工依据拒；缺身份→null 待补。 |
| Q06 | **PASS** | 全字段齐全仍 pending/false 不晋级；真实无源映射仍 pending 且保留照片确认；未知晋级字段拒。 |
| Q07 | **PASS(本次)** | 由本次独审承接：新编号 CLI 流、只读、无重写旧输出；probe 31 exit0（session ses_efa163ab…）。**说明：此 ID 仅本次审查可闭合，不代表已 ACCEPTED。** |

## 三、边界与诚实性
- 软件 PASS 与物理 P01 BLOCKED 分离；无 candidate/physical/runtime 资格，即使字段填满仍 false。
- 02 首版 fixture FAIL 已如实保留（未隐藏）；三源码修订 source_01→04 逐版 diff 核实为新增边界检查（高安全系数方向，非降级）。
- 32_readonly_review_01 首轮 exit0 但以 `tool-calls` 结束、无最终判定：旧证据完整保留，未据其报 PASS；本轮为唯一实际判定。

## 四、总判定

**R1 软件条目（E01–E06、Q01–Q07、S01）PASS；P01 BLOCKED；D01 NOT_RUN。整体 SUBMITTED（软件部分待收口），未 ACCEPTED。**

**无需返工（no required changes）**：未发现契约违反、无保护资产漂移、无越权写入。

*落实建议（非缺陷、非本单范围）*：若要把“深拷贝/无共用引用”显式固化，可在 `packet = deepcopy(outputs["pending_evidence_packet.json"])` 前加断言，或对函数入口 `request` 也 `deepcopy`；该点已由 `digest(request)` 首行提供保护，当前无可复现缺陷。另有外部 3 文件为范围外产物，已如实单列、不回滚。

整体：**SUBMITTED**。