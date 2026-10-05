# GL-A R1 独立只读独审结论

日期：2026-10-05（Asia/Shanghai）。审查者：OpenCode CLI 指定独审（模型自报 `opencode-go/deepseek-v4.1-flash`；defaultDB；session/stream ID 不可得，未编造）。
审查对象：GL-A R1 提交（[回传](../../returns/GL-A.md)，SUBMITTED/已停写）。
范围：唯一验收表 [`tickets/GL-A_adaptive_estimator_interface.md`](../../tickets/GL-A_adaptive_estimator_interface.md) v1（SHA256 `5f16e5d6…5fa9`，复核未变），ID AGL-A-01…05/S01。基线 `master/8676bb479d4ae35cf22075cfe70225cf2220572a`。
方式：只读独审；生产/测试/状态文档零写入，本文件是本轮唯一新增仓库文件；全部独立检查在 `%TEMP%\opencode\agl_a_review\` 下运行、只向 stdout 输出。
ponytail：本轮按 skill 加载（`C:\Users\30680\.config\opencode\skills\ponytail`）执行只读/最小检查；未新增依赖、未改仓库文件、未复跑作者测试冒充实测（另做独立 probe）。

## 1. 完整性与冻结（先固定）

- 8 个新源码/测试 + 唯一验收表 + 样例 manifest 现算 SHA256 与回传/30_scope_check 逐一相同（审查结束前复核，仍未变）：
  `contracts.py=d879a82a…d687`、`selection.py=b4d8147b…9476`、`estimators/{__init__,tls,svd,ransac}=b63e40ae…/76ee4869…/051045b7…/8d4cad60…`、包 `__init__.py=b9bca62a…c63d`、`tests/test_agl_a_estimators.py=e37499f0…0954`、工单 `=5f16e5d6…5fa9`、`20_sample_manifest.json=442b840b…2fb5`。
- 冻结依赖 12 个 blob `git hash-object` 与 `00_baseline.txt` 逐一相同（7 个 core 文件 + `test_joint_leveling.py` + 4 个 `leveling_estimators`）。
- HEAD 未变；`git status --porcelain` 现 259 行 = 基线 257 + 本轮两个新增未跟踪条目（`evidence/2026-10-05_agl_a_r1/`、`returns/GL-A.md`）；63 个已跟踪脏条目与本单无关（范围外历史差异），范围内无已跟踪文件新增修改。
- 独立回归：`python -B -W error -m unittest discover -s src/human_fall_detection/tests` → **Ran 463 / OK / exit 0**；AGL 专项 → **Ran 5 / OK / exit 0**（与作者记录一致，但仅作复现，不作独立验收）。
- 样例 manifest 用证据内脚本原样重生成，字节级一致 `442b840b…`；8 个新文件 `ast.parse(feature_version=(3,8))` 全过（板端 3.8 兼容静态检查）。

## 2. 逐条结论

**AGL-A-01 PASS** — 三适配器对同一 PointDomain 只读消费，输出 `domain_id/point_sha256/rows_sha256/weights_sha256/frame_key` 与 domain 一致、字段全集相同、`full_domain_residuals.point_count==len(domain.points)`、域数组调用前后逐字节不变；代码审查确认 TLS/SVD 无筛点/cap/ROI，RANSAC 仅契约允许的三点抽样但支持/残差对全域计算；三记录 `json.dumps(allow_nan=False)` 通过，`point_domain_reference` 为无数组 JSON 摘要。独立 probe（合成噪声面 + 60 离群点）全部复现。

**AGL-A-02 FAIL（需返工，映射 AGL-A-02）** — `canonical_plane` 只对法向除以 ‖n‖，offset 未同步除以 ‖n‖：
```python
from core.adaptive_ground.contracts import canonical_plane
n, d = canonical_plane([0.0, 0.0, 2.0], -2.64, (0.0, 0.0, 1.0))
# 输入平面 2z-2.64=0 → z=1.32；预期 n=(0,0,1), d=-1.32
# 实际 n=(0,0,1), d=-2.64 → 平面 z=2.64；n·p+d=-1.32
```
- 要求来源：契约 §1“归一化时 normal 和 offset 同除 norm，翻转符号时同时取负”；验收表 AGL-A-02“n/d 同步 normalize/flip”；且与作者 `00_diag.md` §0 自述“n/d 同除归一”直接矛盾。
- 触发/实际/预期：任意非单位法向（scale=2、1e-3、137 及翻转输入均复现）；预期 normalize 后的 (n,d) 表示同一平面，实际保留未除的 d，表示的平面被放大 ‖n‖ 倍。作者测试只用单位法向（`norm=1` 时 ÷1.0 精确，分支不可见），属此前漏测，非新要求。
- 根因/最小修复位置：`core/adaptive_ground/contracts.py` `canonical_plane`，符号翻转前加一行 `value = value / norm`；单位法向路径数值不变（÷1.0 精确），不影响 A-01/04/05 既有产物与冻结语义。
- 影响范围：现有三适配器均传入单位法向（eigh 特征向量 / 右奇异向量 / cross 归一化），故本轮对外记录暂不自洽受损；但该公有装配入口对非单位输入会产出“残差按错误平面计算且无报错”的记录，B+ 复用/外部调用有踩坑面。同类入口已查：`angles_from_normal` 内部自行归一（无 d 字段）、spatial_basis 强制单位向量、`assemble_estimate` 只经此一处归一化，无第二处同族缺陷。A-02 其余要求 PASS：独立 GT（10/26/45°、roll±10°、负 pitch）三法复现 <1e-6°、offset≈1.32、`Rn=e_z`、gauge `R[0][1]=0`、det=+1、单位法向翻转/⊥anchor/零范数拒均符合。

**AGL-A-03 PASS** — 负例矩阵独立加码（list 内 bool 元素、float `source_indices`、bool weights、NaN/Inf/string/empty/全零/错误形状/重复索引/负索引/same-ID 异内容/units/schema/跨帧 estimate×domain/跨配置）全部 raise；invalid 记录几何字段为 null、无 physical/runtime/transform/identity 字段；2 点 → `GL_LOW_POINT_COUNT`，共线 → 三法 `GL_DEGENERATE_GEOMETRY`；极窄条带 `ratio<0.01` 仍 `numerical_valid=true` 但 `valid=false`（拒绝权留 GL-B，符合契约）。

**AGL-A-04 PASS** — 独立合成 clean/noisy 面上 TLS−SVD 角差 ≤1e-3°、|Δd|≤1e-5 m；RANSAC 支持数/支持率与全域独立重算一致、分母 `full_domain_untruncated`、`hypothesis_count=iterations_requested=861`、`resource_complete` 明确；支持门不足 → invalid + `GL_RANSAC_INVALID` + 明确标注 diagnostic 假设（不伪 valid）；iterations>cap 配置期拒。记录语义："budget incomplete" 在 GL-A 内收敛为配置期 cap + 同步全量执行 + 审计字段；deadline/中断语义属 runner（契约 §3/§8，GL-E/H），本轮不存在未执行完整预算却 valid 的路径——按范围边界记录，不阻断。

**AGL-A-05 PASS** — caller 改源数组/改返回对象后输出逐位不变；重跑逐位相同；同内容 domain_id 相同、异内容新 ID 且 validate/估计原子拒；同 config 不同对象 `config_id` 相同，新 seed → 新 `config_id` 且双向跨用拒；调用顺序无关。非阻断观察见 §3。

**AGL-A-S01** — 作者侧流程项 PASS（ponytail 路径已记录、基线含 untracked、前置诊断/操作矩阵齐备、有效回归、源 SHA、停写）；“指定只读独审”=本文件，已执行。因 A-02 FAIL，整单软件门**不通过**。

## 3. 非阻断观察（不要求本轮返工，建议 B 前置加固）

- `region_codes` 有结构校验但无 SHA、未入 `domain_id`：单独改码可通过 `validate_point_domain`。A-01 只要求 point/row/weights 绑定，故不阻断；但 GL-B 一旦消费分区统计，建议先补 codes 内容绑定。
- `validate_plane_estimate(estimate, domain)` 交叉核验未比对 `sign_anchor` 与 `domain.spatial_basis.up_axis`（`domain_id` 已绑定 basis）；属完整性加固项。
- RANSAC 权重仅入诊断加权支持率，不参与抽点/计数（等权协议口径），与契约 §3 “共同全域计数”一致，记录备查。

## 4. 命令与退出码（本轮独审原始）

| 检查 | 命令 | 结果 |
|---|---|---|
| 候选 SHA | `Get-FileHash -Algorithm SHA256` ×10 | 与回传逐一相同 |
| 冻结 blob | `git hash-object` ×12 | 与 00_baseline.txt 逐一相同 |
| 全量回归 | `python -B -W error -m unittest discover -s src/human_fall_detection/tests` | Ran 463 / OK / exit 0 |
| AGL 专项 | `python -B -W error -m unittest discover -s src/human_fall_detection/tests -p "test_agl_a_estimators.py" -v` | Ran 5 / OK / exit 0 |
| manifest 复现 | 证据脚本重生成 + 字节比较 | `442b840b…2fb5` 一致 |
| 独立 probe | 临时脚本（P1 归一化、P2 GT、P3 绑定/JSON、P4 所有权/epoch、P5 拒收、P6 RANSAC、P7 manifest、P8 py3.8 AST） | P1 4 项 FAIL（根因如上）；其余全 PASS |

## 5. 最终

- **软件 FAIL ×1：AGL-A-02**（n/d 同步归一化未实现，一行根因；附可复现证据与最小修复位置）。返工范围仅此一项；同类入口已一次查完，无第二处。
- 其余软件条 AGL-A-01/03/04/05 PASS；A-02 的 GT/符号/gauge 子项 PASS。
- 设备/物理/部署/采集/运行期接入全部 NOT_RUN（本单范围外）；不因本次审查放行 GL-B。
- 整单未 ACCEPTED；REVIEW_LOG 收口由 Codex 按其流程追加。
