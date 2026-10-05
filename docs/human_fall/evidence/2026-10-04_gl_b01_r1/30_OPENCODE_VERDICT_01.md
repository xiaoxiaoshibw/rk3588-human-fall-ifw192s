I'll start by exploring the repository structure to locate all the relevant files for this review.

Let me run independent adversarial probes beyond the author's tests using transient synthetic fixtures.

开

Ponytail: 使用 root 提供的已读文本（SHA `1316a2f3f95741d2300b116fe0c2d81ce4a9568656ed0a62643f54aaf09957f2`）；未调用原生 skill 工具，因为那会触发外部目录读取（该文本已内联提供）。全程只读，未写入仓库任何文件；所有检查经 `python -c`/stdin、只向 stdout 输出。

# GL-B01 R1 独立只读复审结论

范围：`GLB01_ACCEPTANCE.md` v1，ID R01–R06/S01/P01/D01/Q01–Q06。基线 `master/cbd0be1`。

## 完整性事实（先固定）
- 3 新源码 SHA 未变：`core/ground_region_review.py=02382a31…37c0`、`scripts/review_ground_regions.py=47100a09…3c80`、`tests/test_ground_region_review.py=ecdb0657…58d6`；与 `22_manifest_01.json`、`21/26 scope`、`returns/GL-B01.md` 一致。
- `22_manifest_01.json` 全部 62 项现算 SHA 全匹配（bad 0/missing 0）。
- `26_scope_02.json` 现算：4130 项中仅 2 项漂移，`pc_apps/human_replay/annotator.html`（外部并发，1286ad62→8069296e，root 未写）、以及 `.../__pycache__/evaluate_gli02_candidate.cpython-312.pyc`（本次复审跑回归重新生成的临时字节码）；`src/CMakeLists.txt` 在 Windows 为断链符号链接（MISS，已知表示）。冻结 GL/math/config/UI 无漂移，`protected_changed=[]`。
- 源身份：`cap_20261002_163621`/89 帧/4372400 点，`bin=b81797…`、`xyz=a4ad28…`、window `[1790930182.177557,1790930191.258644]`；模型 `26.0°/1.1m`，`R=R_y(+26)`、`t=(0,0,+1.1)`、`status=nominal`、phys/extr/runtime=false。与外部 v8/v11 `cap233210/99帧`、`R_y(-)`、负 Z 平移无关，未被移植。

## 逐 ID

**R01 PASS** — `review_binding`（`core/ground_region_review.py:14`）绑定 source_id/bin/xyz/frame/units/model_id/window；`validate_review_plan:27` 以 `digest(plan.binding)==digest(review_binding)` 拒异源/异窗/异模型。CLI `review_ground_regions.py:51-56` 校验 NPZ 与 nominal-run `npz_sha256/model_id/source/declared/source_xyz`、窗口一致，旧 draft `legacy_source` 逐键绑定（:57-65）。独立复算：NPZ manifest 89 帧、cap_163621；`test_cli_pending_foreign_identity…` 以 `bin_sha256` 伪造拒。plan_id 为内容 ID（`:23`），改内容保留旧 ID 即拒。

**R02 PASS** — plan `keys` 仅允许 `x/y` footprint 键（`:42-43`，无 `z_*`），`select_group_region` 按 nominal XY 全高度取行（`:93-97`），`selection_method="nominal_XY_footprint_all_heights"`（`:102`）。`validate_review_plan:47-56` 要求每区 `frame_group` 属 manifest 且互异、恰一个 FIT、≥4 区。独立复算：FIT/val 4 组 `ordinal 5/6/7/8`、`seq 1979443-46`，行 1084/752/436/687，与 `scene_rows.csv` 顺序完全一致；`gate_selection` 成员门 PASS（`PASS_source_membership_only_not_ground_identity`）。合成反例：z 键、重复组、双/零 FIT、跨组越界均拒。

**R03 PASS** — CSV 头含 `region_id/pooled_row/source_row/ordinal/seq/frame_group/source*/nominal*`，2959 行，`source_row=pooled-组起点`、ord/seq/xyz 全可溯；`identity` 全为 `unreviewed_scene_member`（`:109`），`ground_identity=unknown/confirmation=pending`（`:103`）。显示采样 `np.linspace(...2000)`（`:96`）仅影响 HTML 样本，CSV 全量；HTML payload 最大 diff 与源行集合由 `13_oracle` 与我的复算一致（见 R02）。

**R04 PASS** — `height_observations:60` 标 `domain=all_selected_scene_points_not_ground_error`、`histogram.usage=scene_distribution_only_no_ground_selection`、XY 网格 `z_q10/q50/q90`；`legacy_box_diagnostics:119` 用 `pca_plane`（posthoc，非 RANSAC/fitter），origin `PCA_all_legacy_ROI_scene_rows_not_installation_measurement`、`physical_ground_error=false`。真实值独立复算：legacy FIT 1214、全点 median −0.229656、offset_nominal +0.239822、tilt 0.316781°；legacy v1/v2/v3 tilt 2.0017/57.4858/7.4646°。合成 clean/slope/line/empty 覆盖，模型对象未被修改。无资格晋级/参数替换。

**R05 PASS（软件）** — pending 路径 `selection:null`、`missing=[human-confirmed …]`（`review_ground_regions.py:74-77`）；人工消费 `validate_confirmed_rows:145` 先从 source/model/plan **重算权威 rows**（`:149`），`digest` 守卫拒 caller 改观察报告（`:151`），行集必须 `⊆` 提议 footprint（`:165`），每区 `confirmation.status=="user_confirmed"`（`:166-167`），再走 E02 `check_selection`（person/time-zone/basis/landmarks/evidence_refs/selection_method）。独立反例：partial、空行、残差法、伪造 person/landmark、caller 改 footprint/binding、缺/换区、fit 槽用 validation id 全部拒；合法合成正例仍 `physical/candidate=false`。

**R06 PASS** — 输出限本工单目录、目标不存在、父目录存在、无 symlink、目标不包含输入（`review_ground_regions.py:27-28,42`）；`start_sha` 快照与解析一致（`:43-50`），结束再核 source meta/bin 尾 SHA（`:78-81`）。`16_reproducibility` 两版本语义输出 byte 相等（review_01/02 五文件哈希一致），`15_existing_out_negative` exit2。26/1.1 模型与旧 draft 未被改写。

**S01 PASS（作者阶段+本轮独审）** — 恰 3 新源码，仅 stdlib+NumPy，`ast.parse(feature_version=(3,8))` 三文件全通过；`00_diag/01_before/21/26/22` 齐备；`08` 8/`09` 453/`05` 2 全 exit0（我独立复跑：453 与 8 及 2 均 OK）；`20/return` 后停写；`28_probe` `PROBE_OK`/exit0/model=`opencode-go/deepseek-v4.1-flash`/defaultDB/session。`29_review_01.jsonl` 为本轮复审 root 捕获流。

**P01 BLOCKED（按设计，且必须计入用户语义确认）** — `17` 绑定 `figure_sha=8c21fc18…`（实际 12.png 同哈希）、plan/binding（=review_02 与 plan）完全一致，语义"低位连续带=现场木地板 / VAL_side 上层≈0.6m=工作台"，范围明确 `not exhaustive per-source-row annotation`；`all_footprint_rows_are_ground=false`、`confirmed_source_row_sets=null`、`physical_verified=false`。`18` 为索引。`24` 显式 0.75m（method/uncertainty 未给）；`25` 为独立 posthoc 层诊断：我用 CSV 复算最大相邻 Z gap `0.543291…`（≥20% 两侧），lower/upper=468/219、median −0.214725/+0.612913、差 `0.827637…`，与 25 逐位一致，且 25 无 FIT 残差、不导出标签行、只与 0.75 比较并声明非物理精度接受。剩余具体源行集合/独立精度/SDK 旧 run 复核未完成，故 BLOCKED——不是因为用户未给参数或无场景信息。

**D01 NOT_RUN** — 三源码仅 import stdlib+NumPy+冻结 core；无设备/采集/部署/网络/生产/IRLS；PCA 为观察量，不产生标定或 `ground.valid`。

**Q01 PASS** — kind/schema/cell_m 类型与范围（`:31,37`）、unit/frame/from-to（`:34`）、source/window/model 绑定、NaN（`number` 拒非有限）、空 region 稳定 pending（`:62-63,110`）。

**Q02 PASS** — same-ID 异内容/`plan_id` 重算、caller 改 plan/observation、新 plan/新 model、同路径异内容（`load_adapted` 全量核对）、已有 out、保护路径/越界/符号链接全拒。

**Q03 PASS** — 独立帧组、重复/alias、跨组 indices、越界、zero/Inf 剔除计数、全部高度保留（VAL_side 上/下层同存，FIT_near 含 z>0）。2959 行独立对拍 0 失败。

**Q04 PASS** — clean/斜/offset/桌面混杂(真实 VAL_side 双层)/line/empty × 全 region stats/PCA/非测量解释；各域独立标注，观察不回填 height。

**Q05 PASS** — pending/partial/伪确认/残差筛选 × reviewed eligibility 全拒；`validate_confirmed_rows` 从源重算，caller 不能扩 footprint；17 语义确认不冒充逐行 ready。

**Q06 PASS（控制器证据）** — 起始/最终全树 SHA（`01/21/26`）、3 源码首尾 SHA、原命令 exit（08/09/10/15）、停写、fresh probe、model/defaultDB/session、新编号产物（`22` manifest、`28` probe、`29` review 流）齐备且一致。

## 未决/非阻断观察
- `annotator.html` 在 `26_scope_02` 之后又被外部并发改动（1286ad62→8069296e）；root 未写、26 已如实登记、不归因 GL-B01。
- `15` 的现有-out 负例命中通用提示 "new output must be inside this work item"（`:27` 条件并列），拒止行为正确但文案把"已存在"与"越界"混同，属可选文案改进，不影响 R06。
- 本次复审跑回归重生成 1 个 `__pycache__` pyc（忽略域），非源码漂移。
- 真实浏览器仍 NOT_RUN/BLOCKED（既有 file URL 限制）；12.png 目视 + `19` 离线 node mock 逻辑不等价于 browser PASS。

## 最终
无软件 FAIL。P01 按设计 BLOCKED（用户场景语义确认已计入）、D01 NOT_RUN、真实浏览器 NOT_RUN/BLOCKED。所需返工：无。

**SUBMITTED / no-rework**（非 ACCEPTED）。