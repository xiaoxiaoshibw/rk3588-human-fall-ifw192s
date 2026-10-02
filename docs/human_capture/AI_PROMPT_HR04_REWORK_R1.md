# HR-04 rework R1 — 验收后修复（3 项）

> 背景：HR-04（`pc_apps/human_replay/` 导航层）已交付，node 层验收 28 lib 测试 + 24 smoke 全绿、points.bin sha256 锚一致。Codex 代码验收发现 3 个问题，本单 rework。
> 工作目录 `D:\Code\ldiar`。**只允许动下列 5 个文件**，其余一律不碰；不 commit、不 push。

```
pc_apps/human_replay/human_replay_lib.js
pc_apps/human_replay/replay.js
pc_apps/human_replay/human_replay_lib.test.js
docs/human_capture/evidence/2026-10-02_hr04/01_smoke.js
docs/human_capture/returns/HR-04.md
```

## 问题 1（必修 BUG）：front 视图预设方向反了

`human_replay_lib.js:150` 现状：

```js
front:  { pos: [12, 0, 1.5],     tgt: [0, 0, 1.5],    up: [0, 0, 1], proj: "ortho" },
```

相机放在雷达**前方** 12m 回望雷达原点（画面里雷达对着你）。背离两处契约：

- README §5：`1` = 前视（驾驶第二视角）；
- HR-02 既有 `VIEW_FRONT = { pos: [-6,0,1.6], tgt:[5,0,1.0] }`（`replay.js:332`，T 键/frontBtn 在用）——雷达**后方** 6m、人眼高 1.6m、朝 +X 看。

**1 键必须与 T 键同向，只差投影模式**（ortho vs persp），否则同屏双语义。

修为（与 VIEW_FRONT 完全同位）：

```js
front:  { pos: [-6, 0, 1.6],     tgt: [5, 0, 1.0],    up: [0, 0, 1], proj: "ortho" },
```

注意：`ray_ground_intersect` 对 front 水平视线返回 null 是**正确行为**（01_smoke.js 已用向下分量方向覆盖，不要因此把 front 改回望向）。

同步改断言：

- `human_replay_lib.test.js` 的 `view_preset` case：现有 `L.view_preset("front").pos[1]===0` 保留，**追加** `L.view_preset("front").pos[0] < 0`（雷达后方）。
- `01_smoke.js`：
  - `t("front: proj=ortho 且 x 正向", ... p_front.pos[0] > 8)` → 改 `p_front.pos[0] < 0`；
  - `t("front: 相机高 1.5m（人眼级）", ...pos[2] === 1.5)` → 改 `=== 1.6`。

## 问题 2：死字段 `S.measure.sprites`

`replay.js:31`：

```js
measure: { p1: null, line: null, sprites: [] },  // M 标尺状态
```

全文件无一处读写 `sprites`（标尺 Sprite 挂在 `measure.line` Group 里，由 `measure_clear_line_only` 统一移除）。删字段，保持 `{ p1: null, line: null }`。

## 问题 3：视图预设未按 00_diag 持久化

`00_diag.md`「存储与持久化」表声明视图预设写 `localStorage["human_replay.view_preset"]`，实现只做了 aux_×4 / ref_×4。补齐（与 diag 一致，不缩水设计）：

1. `replay.js` 现有 `ls_get` 是布尔化的（`v === "1"`），视图名是字符串——新增：

```js
function ls_get_raw(k, def) {
    try { var v = localStorage.getItem(L.LS_PREFIX + k); return v == null ? def : v; }
    catch (e) { return def; }
}
```

2. `apply_view_preset(name)` 尾部（`S.view_name = name;` 之后）加 `ls_set("view_preset", name)`——`ls_set` 现签名 `(k, v)` 里写 `v ? "1" : "0"`，会把字符串真值化成 "1"，**必须同步修 ls_set 或直接 `localStorage.setItem(L.LS_PREFIX + "view_preset", name)`**。推荐后者，一行，不动 aux/refs 的布尔语义。
3. 启动恢复：`setup_scene()` 末尾现在调 `reset_cam()`，改为：

```js
(function () {
    var v = ls_get_raw("view_preset", "home");
    try { apply_view_preset(v); } catch (e) { apply_view_preset("home"); }
})();
```

（`apply_view_preset` 对未知名由 `L.view_preset` 抛错，try/catch 兜底回 home；home ≡ VIEW_RESET。）

注意副作用：`apply_view_preset` 尾部写 LS 意味着启动恢复路径也会重写一次同值，无害，不做去抖。

## 验收门槛（全绿才算完）

1. `cd pc_apps/human_replay && node human_replay_lib.test.js` → all tests passed（front 断言更新后条数 28→29）。
2. `node docs/human_capture/evidence/2026-10-02_hr04/01_smoke.js` → all 24 tests passed（其中 front 两条断言按上表改写）。
3. smoke 自带 R10 锚：`points.bin` sha256 必须仍是 `a4a24c19…49`，meta.json 不动。
4. `grep -n "sprites" pc_apps/human_replay/replay.js` → 无输出。
5. `grep -n "view_preset" pc_apps/human_replay/replay.js` → 能看到 ls_set/ls_get_raw 各一处。

## 回传更新

`docs/human_capture/returns/HR-04.md` 追加一节「rework R1（2026-10-02）」：列 3 项修复的 diff 摘要 + 上述 5 条门槛的实测输出；并如实记一句「00_diag.md 正交预设数学表 front 行相机 pos 写错（(12,0,1.5) 是回望位），本轮回传以 rework 后的 lib 为准」——diag 是历史文档不改，错标留在原地。
