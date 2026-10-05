# GL-A R1 实现前集中诊断与操作矩阵映射

日期：2026-10-05。范围：新包 `core/adaptive_ground/{contracts.py, selection.py, estimators/{__init__,tls,svd,ransac}.py}` 与 `tests/test_agl_a_estimators.py`；不修改任何冻结文件（基线见 00_baseline.txt）。
设计来源：[ADAPTIVE_GROUND_LEVELING_CONTRACT §1–3](../ADAPTIVE_GROUND_LEVELING_CONTRACT.md)、[GL-A 工单](../../tickets/GL-A_adaptive_estimator_interface.md)。

## 0. 数值语义与复用边界（先对源，再写代码）

| 估计器 | 复用对象（只读） | 本包实现语义 |
|---|---|---|
| TLS | `ground_diagnostics.pca_plane`（协方差 eigh）与 `pc_apps/human_replay/leveling_estimators/tls.py` | 加权协方差 eigh，最小特征向量为法向（等权=P02 同值） |
| SVD | `ground.py` 的“中心化薄 SVD”（`full_matrices=False`）与工作台 `svd.py` | 加权中心化薄 SVD，最后右奇异向量为法向（等权=P02 同值） |
| RANSAC | `ground.py` 有界 raw RANSAC 参数（861/hard cap 2000/seed20261001）与工作台 `ransac.py` | 原始假设（不精修），`rng.randint(0,N,3)` 有放回抽样、支持数+中位数 tie-break、固定 seed 每次新建 RandomState |
| 法向/角度 | `joint_leveling.joint_rotation` 的 Rx@Ry 约定；`ground_diagnostics.residual_stats` 全域残差 | n/d 同除归一、按 domain.spatial_basis.up_axis 定号（`|dot|<1e-6` 判歧义）；pitch=atan2(-nx,nz)、roll=asin(ny) |
| 严格校验 | `ground_evidence.{keys,text,number,require,digest}`、`numeric.strict_numeric_array` | 复用，不新造第二套 |

边界（本轮不越过）：不做 quality 评分/门槛（GL-B）、不做 consensus（GL-C）、不做时间状态机（GL-D）、不接 runtime/显示（GL-G/H/I）。GL-A 数值有效只置 `numerical_valid=true`；`valid=false、quality_status=NOT_EVALUATED、confidence=0、reason=GL_QUALITY_NOT_EVALUATED`——不因后续模块未实现而伪造高 confidence 或应用资格。

## 1. 入口与赋值顺序

### 1.1 `selection.build_point_domain`（PointDomain 构建）
1. 校验 `frame_key`（8 字段类型）、`selector{selector_id,version}`、`config_id`（`agl-config:` 前缀）、`source_provenance`、`spatial_basis{up_axis,provenance,version}`（单位向量 ≤1e-6）。
2. `points`：len 保护 → `strict_numeric_array((N,3))`，bool/string/NaN/Inf/形状错 **先拒**。
3. `source_indices`（可选）：int64、长度=N、非负、严格递增（唯一）；`weights`（可选）：float64、长度=N、全正有限；`region_codes`（可选）：int64、长度=N。
4. 预筛 `keep = any(points != 0)`（输入已保证 finite）：记录 `input_row_count/kept_row_count/dropped_zero_count/height_or_residual_trim=false`；`kept==0` → ValueError（原子失败，无半成品）。
5. 深拷贝/连续化数组；SHA256(points/rows/weights bytes) → `domain_id = "agl-domain:"+digest(绑定字段)`（内容寻址）。
6. 返回全新 dict；数组是独立副本（调用者后续改动源数组不影响 domain）。

### 1.2 `selection.validate_point_domain`（消费前重核）
按字段全集 → 类型 → 形状/长度 → 重算三 SHA/domain_id/预筛不变量。任一失配 raise（“同 ID 不同内容”检测）；不做部分修复、不回写。

### 1.3 `contracts.resolve_estimator_config`
全集 6 键 → bool/string/NaN 拒 → 数值域：`threshold>0`、`min_inliers≥3`、`frac∈(0,1]`、`iterations≥1`、`cap≤2000`、`iterations≤cap`、`seed≥0` int（bool 拒）→ 规范化 → `config_id=digest`（内容寻址）。**不设默认值**：缺键/未知键直接拒（计划 §10 profile 仍 DRAFT，不落运行 YAML）。

### 1.4 `estimators/*.estimate_*`
1. resolve config → config_id；2. `validate_point_domain`；3. `require domain["config_id"]==config_id`（配置 epoch 绑定；不匹配即拒，不允许跨配置复用）；4. 数值核（见 §0）；5. 数据不足/退化 → invalid 记录（null 几何 + 原因），结构损坏 → raise；6. 有解 → `canonical_plane`（up_axis 定号）→ 角度 → `residual_stats` 全域分母 → 装配记录（deepcopy frame_key；输出不含 domain 数组引用）。

## 2. 操作矩阵逐行映射（工单“先诊断的操作矩阵”）

| 组合 | 入口/触发 | 赋值顺序与检查 | 保护/拒绝行为 | 保留行为/证据 |
|---|---|---|---|---|
| startup × 无输入 | `build_point_domain(empty)` | §1.1-2/4 | ValueError；无半成品 dict | 无全局状态，可重试 |
| startup × 合法 schema | build+三估计 | §1.1→1.4 | 记录 `numerical_valid=true`、quality NOT_EVALUATED、valid=false、confidence 0 | 无自动启用/无物理标记 |
| 同内容 reload | `validate_point_domain` | §1.2 重算 SHA/ID | 通过 | 结果与首次逐位相同（§1.4 纯函数） |
| 同 ID 不同内容 | 原地改数组/count/schema 后 validate/estimate | §1.2 SHA/ID 失配 | raise；三估计全部拒绝；不修复不回写 | 旧记录只读保留 |
| 新 ID 配置 | `resolve_estimator_config(c')` + 新 domain | §1.3/1.4-3 | 新 `config_id`；旧 domain×新 config → raise；无缓存无跨配置复用 | 旧输出不失效（无状态） |
| caller 原地改 array/结果 | build 后改源数组；改返回 estimate | §1.1-5 deepcopy；装配 deepcopy；输出不含共享数组 | domain/est2 不受影响，与 est1 逐位相同 | — |
| wrong frame/domain/units | validate/build/`validate_plane_estimate` | §1.1-1/1.2；estimate×domain 交叉校验 | raise（units≠m、frame 混用、domain_id 不匹配） | — |
| bool/string/NaN/Inf/empty/越界/重复 | 构造/校验/估计路径 | §1.1-2/3、§1.2、§1.3 | 结构错 raise；RANSAC 全退化→invalid 记录 | 失败不产出几何字段 |
| 缺点 | estimate | N<3 | invalid `GL_LOW_POINT_COUNT`；normal/offset/角度=null | confidence 0、reasons 明确 |
| 共线（秩亏） | estimate | λ2/λ3(加权)<1e-12 或 λ2≤0 / s1/s0<1e-6 | TLS/SVD/RANSAC invalid `GL_DEGENERATE_GEOMETRY` | 记录 eigenvalue_ratio |
| 极窄（有展开但比值小） | estimate | 只记录 ratio | `numerical_valid` 可为 true；窄带/覆盖门由 GL-B 按 profile 拒（本轮不越权） | ratio 字段留给 B |
| 法向翻转 | `canonical_plane` | dot(anchor) 定号；`|dot|<1e-6`→raise；范数=0→raise | n、d 同步翻转；角度只由规范 n 导出 | R 第三行=n、Rn=e_z（A-02 断言） |
| RANSAC budget | resolve/estimate | iterations≤cap；`hypothesis_count=iterations` 实际执行数；support<max(min_inliers, ceil(frac·N))→invalid | 超 cap→配置期 ValueError；不伪 valid；invalid 带 `diagnostic_hypothesis`（明确标注不可应用） | `iterations_requested/resource_complete` 审计字段 |
| 各结果到达顺序 | 任意顺序调用三估计 | 每调用独立；RANSAC 每次新 RandomState | 与顺序无关、逐位相等 | 无跨调用状态 |

## 3. 已知决策与例外（写清边界，避免复审歧义）

- **权重**：domain 携带逐点权重（默认全 1）；估计器按权重拟合（等权时与 P02/工作台逐位同值）。支持率/残差计数按点计（协议口径），另记录加权支持率仅供诊断。
- **“缺点”门槛**：数值层只要求 N≥3；`min_inliers/min_inlier_fraction` 在 GL-A 只用于 RANSAC 假设支持门；TLS/SVD 的接受门属于 GL-B 质量层（分层保留）。
- **不复制 GL-01 协议 floor（100/0.2）为配置下限**：那些是旧 constrained fitter 的协议 floor；AGLF 的门槛 profile 在 GL-F 冻结。GL-A 配置做结构域校验 + 与 GL-01 同默认值语义（861/2000/20261001/0.05），不冒充已批准 profile。
- **极窄/覆盖率/窄带**：GL-A 输出 `eigenvalue_ratio` 与全域残差字段，拒绝权归 GL-B；本轮不把低 RMS 线状域判为通过（numerical_valid≠质量通过）。
- **配置绑定**：domain 构建时绑定 config_id；估计器拒绝 domain/config 不匹配的组合（防止跨配置复用历史/结果）。
- **解耦**：所有 estimate 记录保证 JSON 可序列化（`allow_nan=False`），domain 另有 JSON-safe 摘要 `point_domain_reference`；核心包无 UI/文件/ROS 依赖。总控制台算法工作台的最终展示（后续 GL-G/P 单）只消费版本化摘要/工件，不反向依赖本包内部数组。
- **不实现的调用者**：`ground.py` 旧默认/资格语义、`pc_apps` 工作台代码、WebUI、P02 冻结数据与旧证据均不修改；工作台 `leveling_estimators` 仅作数值语义参照。
