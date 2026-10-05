# GL-I06 R1 独审记录完整性复验 / 同项 / 作者继续停写

- 工单：GL-I06 R1；唯一验收表 `docs/human_fall/GLI06_ACCEPTANCE.md` v1（SHA256 `58983b71…ac847`，复验仍一致）。
- 角色：指定只读二审的完整性收口，**不是新算法里程碑**；不写作者研究/生产/配置/输入/旧证据，不改旧报告/旧脚本/旧输出，本轮只在 `opencode_review_01/revalidation_01/` 新建文件。
- 模型/库：`opencode-go/deepseek-v4.1-flash` / default DB，沿用当前会话；无 model/DB/auth/permission 变更、无服务失败自动重试。
- 原生 skill：`C:\Users\30680\.config\opencode\skills\ponytail\SKILL.md`（未扫描外部 Codex skill 目录）。
- 控制器历史记录：`25_review_history_final_01.json`（18 版本 + 49 执行 + latest_matches）；原始二期流 `22_second_review_01.jsonl`；会话 `26_review_session_01.json`；review 后基线 `27_after_review_baseline_01.json`。
- 运行约束：`PYTHONDONTWRITEBYTECODE=1`；无持久源码缓存；新脚本一律新文件名、新输出名，绝不覆盖。

## 1. 独审 write/edit 历史精确性（复验）

`reval_01_history_audit.py` → `01_history_audit_01.json`，exit 0。

- **版本构成**：18 个版本 = 10 次 write + 8 次 edit（与控制器一致）。
- **同路径就地编辑（workflow 失败）**：4 个文件共 8 次 edit：
  - `01_manifest_verify_01.py` 3 版本（2 edit）
  - `04_probe_a02_a03_a05_01.py` 3 版本（2 edit）
  - `06_probe_a06_validation_02.py` 4 版本（3 edit）
  - `08_probe_final_holdout_oracle_01.py` 2 版本（1 edit）
  这违反了派发要求“Each revision/output needs NEW number. Never overwrite anything.”——**记录为独审流程失败，不抹除、不伪装**。
- **内容哈希**：18/18 版本存储内容 SHA256 与记录一致；每个文件**最新版本 SHA 与实际文件字节全等**（`all_latest_match=True`）。
- **失败执行（保留）**：49 次命令中 5 次真实非零：
  - exec14/15 exit1：`01_manifest_verify_01.py` v1/v2（先后遇 Windows 坏 reparse-point `OSError`、随后 `sha256` 键缺失）；
  - exec31 exit1：`05_probe_a04_a06_a07_s01_01.py` 末尾打印 KeyError（输出 JSON 已先写出）；
  - exec35 exit1：`06_probe_a06_validation_02.py` v12 `ModuleNotFoundError: r0_01`（sys.path 未加）；
  - exec43 exit1：`08_probe_final_holdout_oracle_01.py` v15 文件名 seed 解析 `ValueError`。
  这些历史版本作为**不可变数据记录**保留，未在复验中当作新结果重跑。
- **历史物化**：18 个恢复版本各写成新不可变文件 `recovered_versions/<stem>/v<NN>_<sha12><ext>`（18 个），供审计追溯。
- 控制器 `executions[].source_revision_sha256` 字段为空；本复验按 event_ordinal 推断每次执行时该文件应有的版本并记录于 `01_history_audit_01.json`（未臆造哈希）。

**纠正旧报告**：`00_review.md` 写“均未覆盖旧文件”与原始流矛盾。旧报告**保持原样不改**，本报告更正为上述 8 次同路径 edit。

## 2. 作者 manifest / 冻结输入 before-after 复验

`reval_02_manifest_scope.py` → `02_manifest_scope_01.json`，exit 0。

- `19_manifest_01.json`：files 646/646、frozen_dependencies 2917/2917 有哈希项全匹配，0 mismatch；5 个非哈希项为 4 个已删 tracked 文件 + 1 个 Windows catkin reparse-point。
- `01_before_baseline` 对 `16_submission_baseline`：`changed=0`、`added_outside=0`。
- `01_before` 对 `27_after_review`（排除 run 根与 `returns/GL-I06.md`）：**protected changed=0、added_outside=0**——本次独审未改动任何生产/配置/输入/驱动/UI/HR/旧证据。
- manifest 自身 SHA 未变、验收表 SHA 未变（`manifest_self_unchanged=True`、`acceptance_unchanged=True`）。
- **Windows catkin reparse-point**：`src/CMakeLists.txt` 在 before/submission/after 记录完全一致（`unreadable_winerror=1920, lstat_mode=33206, size=0, attributes=1056`）。可读性失败仅为 Windows 表示形态，**不是**修改生产或降低验收的依据。

## 3. 新编号不可变复验（复验全部 A/Q 行与核心行为）

均为新脚本、新输出，未覆盖旧文件。

| 脚本 | 输出 | exit | 结果 |
|---|---|---|---|
| `reval_01_history_audit.py` | `01_history_audit_01.json` | 0 | 18 版本/8 edit/49 执行/5 失败；内容哈希 0 失败；latest=实际字节 |
| `reval_02_manifest_scope.py` | `02_manifest_scope_01.json` | 0 | manifest/frozen/before/after 全匹配；protected 前后 0 变化 |
| `reval_03_ledgers.py` | `03_ledgers_01.json` | 0 | 62 R0 + 186 K + 90 final，自写标量 oracle **0 失败** |
| `reval_04_contract.py` | `04_contract_01.json` | 0 | 合约/预算/重算/非法输入/gates **全 0 失败** |
| `reval_05_a06_a07_s01.py` | `05_a06_a07_s01_01.json` | 0 | A06/A07/S01 **0 失败**（含 AST3.8、写探针） |
| `reval_06_claims.py` | `06_claims_01.json` | 0 | 最差案例、多重性、命名、catkin 元数据、完整性失败计数复验 |

独立复验要点：
- **A01**：62 R0 的 source/FIT/settings/raw/sample SHA 与 186 K 台账一致；K1 W ≡ R0 W；fresh 重算（scene/replay SHA、原生 fitter↔replay、K1-3 W/counts、真实 WHAT_IF 一次转换）0 失败。
- **A02**：186 台账计数恒等式、逐 draw 分阶段、资源与收敛分列，0 失败。
- **A03/A05**：自写标量 oracle 对 62+186+90 的 full-W 与 stored-subset 域全等；best= max(W)；`candidate_budget=0` 时 full best=max(W)、stored best=None、强制 unresolved；gap→unresolved、无误闭合；tie/链/late/弱边界/预算 zero/one-short/exact/+1 全对；J 不改状态。
- **A04**：复现 0.827°/108 成员；真实不收敛（high_noise K2 `nonconverged=682/683`）强制 unresolved；注入 cycle/later 越界保留末有效见证、无静默回退；LO 缺口（`lo_budget=0`）单列。
- **A06**：非退化 147/147 变体有 3 个独立 `frame_group` 且非 FIT、含 `source_xyz_bounds`；退化 collinear/narrow_band/real_approved 共 39 变体空 W（无平面，区域打分无从定义）；区域索引与 FIT 不重叠、合成 240 行全覆盖；final 30 case/90 台账、seeds 1707/1719/1741、freeze SHA 绑定、freeze 早于首个 final。
- **A07**：每 K 3 次 active 计时、阶段齐全、独立子进程内存峰值；无 RK3588/端到端声明。
- **非法输入**：17 项全拒；`write_new` 拒覆盖、拒越目录。

## 4. 旧报告的具体更正（旧报告不改）

1. **“未覆盖旧文件”** → 更正为 8 次同路径 edit（见 §1）。
2. **A06 最差案例归属**（`reval_06_claims.py`）：
   - 开发**最差法向** = `wall_19_False` K1，`0.4118524776°` / offset `0.0115933474m`，状态 **seen_pairwise_closed**，其自身区域 RMS 最大 `0.0260081429m`。
   - 开发**最差独立区域 RMS** = `high_noise_19_True` K2，`0.0431167707m`（K1 `0.0431159289m`，region `v1`/`hold1`），状态 **unresolved**。
   - 因此旧报告“wall K1 以 0.412°/0.043m 且 closed”的合并表述不成立：`0.0431` 来自 high_noise 且为 unresolved。更正后仍保留“竞争 closed 不等于区域/物理质量”的限定：`wall_19_False` K1 确为 closed 而法向 0.412°。
3. **精确合并多重性**（不得用未验证公式）：
   - 三个全同签名的实测：`produced=3`、`W 长度=3`、`witnesses=1`、`retained=1`、`merged_exact=2`、`unstored=0`；trace 动作 `[retained_witness, merged_exact, merged_exact]`。
   - 恒等式：`produced = retained + merged_exact + unstored`；`len(W)=produced`；`len(witnesses)=retained`。仅此，不写“retained+2×merged”之类泛化式。
4. **validation 命名**：`region_id = v0/v1/v2`，`frame_group = hold0/hold1/hold2`，三组互异且均非 `fit`。

## 5. 结论（算法判定与完整性判定分开）

**算法判定**（对 GLI06_ACCEPTANCE v1）：

| ID | 判定 | 依据 |
|---|---|---|
| A01 | PASS | 清单/冻结 SHA 全匹配；62 R0 与 K 台账身份一致；K1≡R0；fresh 重算复现 |
| A02 | PASS | 186 台账计数恒等式、逐 draw 分阶段、资源/收敛分列 |
| A03 | PASS | 独立标量 oracle 全覆盖 0 失败；多重性/预算/ties/链/late；best=max(W) |
| A04 | PASS | 0.827° 反例复现；真实不收敛强制 unresolved；注入 gate 无静默回退 |
| A05 | PASS | full-W/J/覆盖/非法输入；鲁棒权重 NOT_RUN（无混杂尾部证据，条件不适用） |
| A06 | PASS（附限制） | 非退化 3 独立验证组全行打分；final 合成 30 案；退化空 W 区域打分无从定义 |
| A07 | PASS | 3 重复计时/阶段/内存峰值；无板端/端到端声明 |
| S01 | PASS（软件，见下） | 不可覆盖/新编号在本轮以 revalidation 落实；指定 Go Flash/default DB probe+二审在场 |
| B01 | BLOCKED | physical=false、ground_valid=false；真实 up/高度/身份未核 |
| D01 | NOT_RUN | 无采集/部署/设备/production 接入；桌面离线 |
| Q01 | PASS | 身份/输入/不可覆盖/无缓存 |
| Q02 | PASS | 三类×tie/链/late×预算 zero/one-short/exact/+1 |
| Q03 | PASS | K1-3 收敛/资源分列；真实非收敛；注入非经验 TLS |
| Q04 | PASS（鲁棒 NOT_RUN） | J 仅诊断；鲁棒条件未触发 |
| Q05 | PASS（真实最终留出 NOT_RUN） | 硬场景/seed/置换/固定 source/真实 WHAT_IF/验证独立；物理留出因 B01 未跑 |
| Q06 | PASS（软件，见下） | 成本/否定/冻结/停写；probe 与指定二审在场 |

**完整性判定**：
- 第一轮独审存在**流程失败**：8 次同路径就地 edit、5 次非零退出、以及 `00_review.md` 的错误“未覆盖”陈述。旧报告与旧脚本全部保留，未删改。
- 失败已由控制器 `25_review_history_final_01.json` 精确保留（18 版本 + 49 执行），本轮将全部恢复版本物化为新不可变文件，并以**新编号不可变脚本/输出**重跑全部 A/Q 行与作者 manifest/frozen 前后核对，结果与第一轮数值一致、0 失败。
- 据此，S01/Q06 的“软件完整性”条件满足并闭合；**旧报告中未经复验的 S01/Q06 说法在当时不被接受，现由本轮复验闭合**。任何真实作者算法 FAIL 仍为 FAIL（本轮未发现），不代改作者代码。
- 物理/设备未变：B01 物理 BLOCKED、D01 设备 NOT_RUN；软件 PASS 不等于物理资质。

**SECOND_REVIEW_SUBMITTED / STOPPED**
