# C1.5 人工真值 (GT) 标注规范 v1

> 日期 2026-10-10。目的: 为动态人体识别的 FN/FP/Track 指标提供**人工真值**, 并与 AI 自动标签严格分层。
> 铁律 (用户授权): **不伪造 GT**。凡不是逐帧看图确认的, 一律不写人工真值, 只写 `confidence:"auto"` 或 `UNCERTAIN`。

## 1. 标签分层 (不可混淆)

| 层 | 字段 | 含义 | 可否当评测 GT |
|---|---|---|---|
| 生产 track 输出 | (runtime) | 算法判定 | 否 (被评对象) |
| AI 自动标签 | `confidence:"auto"` | auto_person_label.py 判读 | **仅作参考**, 非金标 |
| **人工真值** | `source:"human"` | 逐帧看图确认 | **是** (唯一金标) |
| AI 辅助 + 人工确认 | `source:"human"`, `assist:"ai_triage"` | AI 预筛、人核对 | 是 (人工负最终责任) |

下游任何 recall/precision 数字, 分子分母的 GT 必须只取 `source:"human"`。

## 2. 标注单元与判据 (可证伪)

基础单元 = **(session, frame) 的人形簇存在性 + 身份连续性**。

**判为真人的 3 个独立判据 (全满足才标 person, 缺一项 → UNCERTAIN):**
1. 顶视: 直径 < 0.6m 紧凑圆簇。
2. 侧视: 同位置窄竖条从地面 (z≈-0.2) 贯穿到 ≥1.5m (z 带全色谱递变: 蓝脚→青→绿→黄头)。
3. 时序: 跨帧位置连续 (步幅与帧率自洽), 非闪现/跳变。

**反例 (判 NOT person):** 宽 >1m 平顶块 (柜/桌)、半高截断、仅高强度近场反射弧、无 z 贯穿的离散点。

**场景标签 (per-frame):** `empty` / `person_stand` / `person_walk` / `person_turn` / `person_occluded` / `person_far` / `person_still_after_walk` / `uncertain`。
**运动判定:** 相邻确认人形簇质心位移 ≥0.3m/s 等效 (按帧率折算) → `person_walk`; <该值且非首现 → `stand/still`。

**身份连续性 (track):** 同一物理人在连续帧的人形簇, 位移自洽者 = 同一 GT person-id (如 `P1`)。移动超过单帧可信步幅、或消失后远处重现 → 新 id 或标 `reentry`。

## 3. 标注工作流 (AI 辅助, 人工终判)

1. `render_person_label.py` 渲每帧 top/side PNG。
2. AI triage (如本会话 vision 判读) 给**候选** per-frame 类, 仅作 `assist`。
3. **人工 (或可审计的 vision 复核) 逐帧看图**, 把候选改成 `source:"human"` 或打回 `uncertain`。
4. 不确定帧: 标 `uncertain`, **不计入** recall/precision 分母, 单独报 UNCERTAIN 比例。
5. GT 写**派生文件** `<sid>/gt_v1.json`, 不动 meta.json / ai_labels.json; 保留原始 SHA。

## 4. gt_v1.json 契约 (每会话)

```json
{
  "session_id": "cap_...",
  "gt_version": "v1",
  "labelled_by": "vision_assisted_review_v1",
  "source": "human",
  "frames": {
    "0": {"scene": "empty"},
    "54": {"scene": "person_walk", "persons": [{"gid": "P1", "cx": 0.86, "cy": 0.64, "conf": "high"}]},
    "...": {}
  },
  "qc": {"n_frames": 0, "n_person_frames": 0, "n_uncertain": 0, "reviewer": "..."}
}
```
`cx/cy` = 人形簇**人工确认**的簇质心 (来自渲染图对应的簇层, 非凭空点选)。`conf`: high/medium; medium/uncertain 帧进 QC 复核。

## 5. 现有真人 GT 资产盘点 (2026-10-10, 基于 vision 对照校准判读, assist 级)

| 会话 | 帧数 | 内容 | 置信 | 用途 |
|---|---|---|---|---|
| cap_20261007_143945 | 108 | 真人慢走 (跨度~2.4m) + 停留 | 高 (assist) | **动态 GT** (需逐帧哈希) |
| cap_20261007_154007 | 83 | 真人横移 ~1.6m → 站定 | 高 (assist) | **动态 GT** (需逐帧哈希) |
| cap_20261008_114340 | 281 | 静态真人站立 (0.29m 呼吸) | 高 (assist) | still/retention GT |
| cap_20261008_114254 | 271 | 静态真人站立 (0.22m) | 高 (assist) | still/retention GT |
| cap_20261009_121622 等 11 段 | 915+ | auto 标 stand, 无人确 | auto 级 | 参考非金标 |
| cap_20261009_121622 f50 对照 | — | 真人站立 (vision 校准) | 高 | 判读基准 |
| cap_20261009_113611 | 203 | 空场 (无人) | 高 | 空场 FP 基准 |

> **诚实边界**: 上表"高置信"目前来自 **AI vision 判读 + 对照校准**, 尚属 `assist` 级。要升级为正式 `source:"human"` 金标, 需逐帧哈希渲染 + 人工 (或二次独立 vision) 逐帧确认。本规范明确此落差, 不把 assist 冒称人工金标。

## 6. 场景覆盖缺口 (目标 6 六类)

现有可用: 走动(143945/154007)、停走后静立(154007/114340/114254)、远距离(?待距离标注)、遮挡(部分, 待逐帧)。
**缺:** 明确转身、完全遮挡后重现、>2.5m 远距离、多人交叉、坐/蹲/弯腰/躺/跌倒、步速变化。
→ 由 C15_CAPTURE_ANNOTATION_PLAN.md 采集方案补齐。

## 7. 治理
- 每次 GT 修订 bump `gt_version` 并记录 diff; 旧版留档不删。
- 评测脚本只读 `gt_v1.json` 的 `source:"human"` 帧; `assist`/`auto` 帧必须显式排除或标注。
- 评审员 (OpenCode) 独立抽看 PNG vs gt_v1.json, 核对一致性。
