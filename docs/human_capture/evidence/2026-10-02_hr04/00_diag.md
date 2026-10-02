# HR-04 集中诊断：操作矩阵 → 函数映射

日期 2026-10-02；写码前一次性过。

## 现状锚点（grep 核实）

- 相机引擎：`TrackballControls`（HR-02 起）；并行一轮加了 `front_cam`/`VIEW_FRONT`、`reset_cam`/`VIEW_RESET`、R/T 键、`frontBtn`/`resetBtn` 按钮 —— 与 README §5 的 7/1/3/0 不完全同构（README 要的是顶/前/侧/透）。
- **飞行相机已是既成事实**（`fly_enter/_exit/_tick/_on_mouse` + `flyHud`）——README §5 F/WASD/ZC 已落地，HR-04 不重做。
- 现网无：正交投影切换、坐标读数、P 键拾取、标尺、人形/门框、细格/原点三轴独立开关。
- localStorage 未用于任何现有开关（loopChk/lutSel 都是会话内状态），HR-04 开始引入——钥匙串前缀 `human_replay.`。
- HR-03 剪辑面板：独立元素 `trimBox/trimToggle`，键盘事件不互通，不冲突。

## 键位冲突对账（新引入 7/1/3/0/Home/P/M 与既有键的关系）

| 键 | 现状 | HR-04 用途 | 冲突? |
|----|------|-----------|-------|
| 7/1/3/0 | 未占用 | 正交预设顶/前/侧/透 | ❌ 独占 |
| Home | 未占用 | 归位到 VIEW_RESET | ❌ 独占 |
| P | 未占用 | 快照最近点 | ❌ 独占 |
| M | 未占用 | 标尺开始/结束/清除 | ❌ 独占 |
| B/V | 未占用 | README §5 标B=框选 V=查看（HR-05） | **本单不引入** |
| F/R/T/WASD/Q/E/空格/←→ | 已占用（飞行/复位/正视/移动/旋转/播/帧） | 不动 | — |

飞行模式下（S.fly.on）所有按键走 fly_tick 通道，HR-04 新键若要在飞行态生效需要专门分支——**决定：飞行态不启用 7/1/3/0/P/M/Home**（语义错位——7/1/3/0 切投影对轨道有意义对飞行无意义；飞行时 R 已有复位）。

## 操作矩阵（每 R 条 → 函数）

| # | R 项 | 触发 | 守门 | 行为 |
|---|------|------|------|------|
| M1 | R1 正交 7 | keydown Digit7 | `S.frames` 已载入 | `set_view_preset('top')`：`S.camera` 换成 `THREE.OrthographicCamera` 俯视 z=+10m，up=(0,1ISO?...)——见下约束 |
| M2 | R1 正交 1 | keydown Digit1 | 同上 | 前视 XZ 平面，相机 z≈1.6m 高、y=-10m，看向 +X |
| M3 | R1 正交 3 | keydown Digit3 | 同上 | 侧视 YZ 平面，相机 x=+10m，看向 -Y |
| M4 | R1 正交 0 | keydown Digit0 | 同上 | 复位到 VIEW_RESET 透视 62° |
| M5 | R2 Home | keydown Home | `S.frames` 已载入 | 等价于 M4（视角 reset） |
| M6 | R3 鼠标坐标 | mousemove（HUD 常开） | `S.camera/S.renderer` 已建立 | 逆投影 NDC→z=0 平面：`raycaster.setFromCamera + intersect plane z=0` → 显示 `(x,y,0)`；`#coordHud` 左下角常显;数据点位移到右上 |
| M7 | R4 P 快照 | keydown KeyP（S.idx 停住更精确，但按了下来也能用） | `S.frames` 已载入；lung&geary 点云 | raycaster.setFromCamera→沿 ray 与 z=0 交点为中心；brute-force O(N) 扫当前帧找最近点（OD 平方欧氏，不管 z）→ 状态栏 `(x,y,z,i)` |
| M8 | R5 标尺 M*1 | keydown KeyM | 当前无 measure 标记 | "起第一尺"：记录鼠标当前地面投影点为 p1，HUD 提示 "移动鼠标选终点" |
| M9 | R5 标尺 M*2 | 再次 keydown KeyM | 必有 p1 | 记录 p2，`measure_line_add(p1, p2)`：Line + 2 Sphere + Sprite（toFixed(2)m），HUD 显距离；状态=已存尺，再按则清 |
| M10 | R5 标尺 M*3+ | 已存在尺再按 M | 必有 | `measure_clear()` 清场景，状态=无尺，回到 M8 |
| M11 | R6 参照物（4 种 checkbox） | toolbar change | 无依赖 | `reference_add(name)`：standing_1p8=Box(0.5,0.4,1.8) @ 原点；lying_1p8=Box(1.8,0.5,0.4)；door_2p1= 2柱+1梁;door_1p7= 同构 hs。半透明 `MeshBasicMaterial({transparent:true, opacity:0.25, wireframe:true})` |
| M12 | R6 站立人形拖动 | 左键按下+人形 mesh 被 raycast 到 | 参照已加载 | mousedown → 记 drag_person_active；mousemove 沿 z=0 平面拖（不解锁 controls）；mouseup → 释放。拖拽中禁 controls.rotate |
| M13 | R7 4 checkbox | toolbar change | 无依赖 | `aux_set(kind, on)`：grid_1m（S.grid）、grid_0p1（S.grid_fine）、axes（S.axesHelper）、origin（S.originBall）→ `visible=on`。初始化读 localStorage `human_replay.aux_*` |
| M14 | R8 键位不回归 | 全部回归用例 | — | 已有 Q/E/F/R/T/←→/空格 不动，Replay 中默认所有新键在飞行态被忽略 |

## 正交预设数学（要对得上的具体数）

雷达 z-up，x-forward，y-left。雷达原点 (0,0,0)。

| preset | 看哪 | 相机 pos | 相机 up | 投影 | 视野 |
|--------|------|---------|---------|------|------|
| top (7) | -Z（俯视 XY） | `(5, 0, 15)` | `(1, 0, 0)`（x 朝上屏幕） | OrthographicCamera left=-10 right=10 top=-7 bottom=7 | ~20×14m 地块 |
| front (1) | +X 看 -X 回雷达（前视 XZ） | `(12, 0, 1.5)` | `(0, 0, 1)`（z 朝上屏幕） | 同上 | 跟 VIEW_FRONT 同语义，但投影改 Ortho |
| side (3) | +Y 侧视（看 YZ 平面，即雷达右侧向左看） | `(0, 12, 1.5)` | `(0, 0, 1)` | 同上 | Y 屏幕横轴 |
| persp (0) | 同 VIEW_RESET | `(-3.5, -4, 2.8)` tgt=(2.5,0,0.6) | `(0,0,1)` | PerspectiveCamera fov=62 | 原 HR-02 默认 |

**正交视野选择** 20m×14m 是经验值（驾驶雷达 scan 主要能量集中在 ±10m 宽、±7m 深），不可硬编码死 —— 用 meta.total_points 范围（points.bin 的 x/y/z min/max）自适应。pony：v1 固定尺寸 20×14 就够，之后不够再改。

## P 键拾取对账（跟 R3 坐标读数区分）

- mousemove 持续显示（R3）= 光标到 z=0 平面的逆投影，**不扫点云**；开销 O(1)。
- P 键快照（R4）= 光标 → 平面 z=0 交点 → **brute-force 扫当前帧找最近点**；O(N=300k)；按一下 ~5-10ms，可接受；快照在 frameInfo 旁边的状态栏。
- 都是 ground-plane 辅助工具，跟 HR-05 的"框选点云"目的完全不同——HR-04 不动 BufferGeometry 查询加速。

## 存储与持久化

| 数据 | 位置 | 持久化 | 说明 |
|------|------|--------|------|
| 4 checkbox | localStorage `human_replay.aux_{grid,grid_fine,axes,origin}` | 跨会话 | 由工具栏 change 事件写入，load 时初始化 |
| 视图预设 | localStorage `human_replay.view_preset` | 跨会话 | 7/1/3/0/Home 都在一行 |
| 标尺 | 内存（即将被 HR-05 view_state 收编） | 不持久 | M 按一下清仓 |
| 人形位置 | 内存 | 不持久 | 拖了重置也无所谓（参照物不是数据） |
| 参照物开关 | localStorage `human_replay.ref_*` | 跨会话 | 类同 aux |

## 已知坑（提前列出）

- 正交切换后 `controls.target` 保持；正交 fov 无意义，但 TrackballControls.zoom 在 OrthoCamera 上靠修改 `camera.zoom`，而不是距离——v1 简化用 camera.zoom=固定值 1，不做鼠标滚轮缩放同步（v2 才补）。
- TrackballControls 不感知投影模式，切 camera 后要 `controls.object = newCam; controls.update()`；直接把 S.camera 属性替换、把 controls.object 同步过去即可。
- 飞行模式吃指针锁，与正交 7/1/3/0 无冲突（**飞行态不启用新键**——那本来也不在飞行体验语义里）。
- 拖拽人形要跟 controls.rotate 冲突：用 `drag_person` flag 临时 `S.controls.enabled=false`，mouseup 才放。
