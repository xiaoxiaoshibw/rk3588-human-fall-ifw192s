# HFUS-D04 本地一键 Demo（`demo_d04.html`）

本页配合 `sidequests/human_fusion_lab_next/d04/demo_d04.html` 使用。
**完全静态**：`file://` 双击 或 `python -m http.server` 也可打开；不依赖 Node server、不访问外网。

## 三步跑起来

1. **复制 Demo 到本地任意目录**（也可以直接用仓库里的路径）。
   ```
   D:/Code/ldiar/sidequests/human_fusion_lab_next/d04/demo_d04.html
   ```
2. **双击用 Chrome/Edge 打开**（Firefox 不支持 `webkitdirectory`，请不要用）。
   页面打开后，按顺序点选三个目录：
   - **D04 证据根**：`docs/human_capture/evidence/2026-10-11_hfus_d04_r1/`
     - 该目录应含 `MANIFEST_DEMO.json` 和（或）`runs/<variant>/<mode>_cap_<sid>.jsonl`。
     - 各变体跑完后，只要把 `runs/<variant>/` 放在该根目录下即可被识别（也兼容免 `runs/` 层级的 `<variant>/<mode>_cap_<sid>.jsonl` 直接布局，变体目录名以 `d04_` 开头）。
   - **D03 证据根**：`docs/human_capture/evidence/2026-10-11_hfus_d03_r1/`
     - 提供旧版对照：页面自动识别其中的 `A_cap_<sid>.jsonl` / `B_cap_<sid>.jsonl`。
   - **captures/remote 根**：`captures/remote/`（或含 `<sid>/meta.json` + `<sid>/points.bin` 的任一父目录）
     - 用来按帧切片反查点云 xyz 渲染；未选时只画 GT/候选中心（无色点云）。
3. **看与导出**
   - 顶部下拉选 **会话 (sid)** / **变体 (variant)**，中间是逐帧 slider / 数字输入框。
   - 左列「跳到下一失败帧」按当前变体的 `strict.observed_confirmed.fn>0 || legacy.confirmed.fp>0` 顺序跳；A、B 按钮同理对照。
   - 中间/右侧点画云上**点击任一候选点**即把该候选整个 `raw_indices` 集合加入人工复核框；左下角按钮导出
     `D04_<variant>_MANUAL_DRAFT_f<idx>.json`（schema = `hfus-manual-input-draft-v1`，多加 `variant` 与 `frame_sha256` 字段，不改原 GT）。

## 变体来源

- **默认情况下本 demo 不带任何 D04 运行结果**：变体下拉框只会显示用户选中的 D04 证据根下真实跑出来的 `runs/<variant>` 目录（或 `<variant>=d04_*` 顶层目录）。
- D04 各变体跑完后，把
  ```
  docs/human_capture/evidence/2026-10-11_hfus_d04_r1/runs/<variant>/{A,B}_cap_<sid>.jsonl
  ```
  放到位即可；无需改 demo 代码。
- 同 sid 同时有 A/B ledger 时，本 demo 优先取 B（B 带 `bg` 归因字段）。

## MANIFEST_DEMO.json（样例，最小可用结构）

放在 D04 证据根下即可；demo 启动时读取用于顶部对账（未提供也能跑）：

```json
{
  "schema_version": "hfus-d04-demo-manifest-v1",
  "created_iso": "2026-10-11T22:00:00Z",
  "baseline_doc": "docs/human_capture/evidence/2026-10-11_hfus_d04_r1/BASELINE_D04.md",
  "baseline_shas_file": "docs/human_capture/evidence/2026-10-11_hfus_d04_r1/BASELINE_SHAS.json",
  "input_sha256": {
    "run_b.js": "…sha256…",
    "contracts/index_v1.js": "…sha256…",
    "contracts/strict_v2.js": "…sha256…",
    "eval/instrument.js": "…sha256…"
  },
  "variants": [
    {
      "name": "d04_base",
      "mode_ledgers": {
        "B": {
          "cap_20261010_175227": {
            "path": "runs/d04_base/B_cap_20261010_175227.jsonl",
            "sha256": "…sha256…",
            "frames": 304
          }
        }
      },
      "config_sha256": "…sha256…",
      "summary_path": "runs/d04_base/SUMMARY_d04_base.json"
    }
  ],
  "d03_ledgers_sha256": {
    "A_cap_20261010_175227.jsonl": "…sha256…",
    "B_cap_20261010_175227.jsonl": "…sha256…"
  },
  "captures_sha256": {
    "cap_20261010_175227": {
      "meta": "…sha256…",
      "points": "…sha256…"
    }
  }
}
```

## Demo 展示内容对照 BASELINE_D04「附带硬性约束」

| 要求 | 本 demo 对应 |
|---|---|
| (a) 九会话回放 | 会话下拉逐会话加载、Frame slider/播放按钮 |
| (b) 旧版与 D04 同帧对比 | 三栏：左=GT+变体、中=旧A+变体 Accepted 叠绿、右=旧B+变体 Accepted 叠绿（frame_index 精确对齐） |
| (c) 检测框/GT 可视化 | GT 点按 class 着色 + 中心虚线圆；候选中心标 id；Accepted 叠加高亮 |
| (d) 失败案例跳转 | 「跳到下一失败帧」按钮 + 完整失败帧列表（可点击） |
| (e) 分层显示 | 右下账本行：`foreground_count`/`unsupported_UNKNOWN`/`bare_b_points`/`chain_b_points`/`raw_components`/`strict`/`legacy` |
| (f) 人工复核导出 | 底部 DRAFT 下载，schema 复制 D02 `hfus-manual-input-draft-v1` 并加 `variant`+`frame_sha256`，不改 GT |

## 已知口径

- **判定「变体已接受」**：`candidate.prob >= 0.35 || decision ∈ {HUMAN_CANDIDATE, CONFIRMED_HUMAN}`（与 BASELINE 的 legacy 阈 0.35 + visible_candidates 语义一致；ledger 内 `visible_candidates` 字段若存在亦被用于着色）。
- **失败帧判定**：`strict.observed_confirmed.fn>0 || strict.observed_confirmed.fp>0 || strict.observed_confirmed.unmatched_unknown>0 || strict.accepted.fn>0 || strict.accepted.fp>0 || legacy.confirmed.fn>0 || legacy.confirmed.fp>0`。
- **点云渲染**：从 `captures/remote/<sid>/points.bin` 按 `meta.json.frames[frame_idx].offset_points/count_points` 以 `point_stride_bytes=28` 切片；为限制 SVG 节点，每窗格抽稀至 ≤6000 点，高分着色点（GT/候选/Accepted）不被抽稀。
- **file:// 兼容**：全部数据用 `<input type=file webkitdirectory>` 读入，不发起任何网络请求，浏览器私有目录选择权限即可。
- **GBK/UTF-8**：页面 `<meta charset="UTF-8">`；ledger 与 GT 一律按 UTF-8 解析（`File.text()` 默认 UTF-8）。

## 文件

- `demo_d04.html` — 单文件 demo（本目录）。
- `BUILD_DEMO.md` — 本说明（本目录）。
- 输入与证据均在 `docs/human_capture/evidence/2026-10-11_hfus_d04_r1/`、`docs/human_capture/evidence/2026-10-11_hfus_d03_r1/`、`captures/remote/`；本 demo 不动它们。
