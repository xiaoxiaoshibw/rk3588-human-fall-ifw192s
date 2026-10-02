# HR-05 集中诊断：操作矩阵 → 函数映射

日期 2026-10-02；写码前一次性过。

## ponytail SKILL 声明

- 路径：`.claude/skills/ponytail`（session 内已挂上）。
- 关键取舍：
  1. SAVE 接口挂 `human_replay_lib.py:8901`，**不另起 8767 node 服务**——已有 Python server
     已有 threading/锁/JSON/静态路由，加一个 POST 端点最简。
  2. z 高度分位（2%/98%）**手写纯函数**，不引 numpy / math 库外依赖。
  3. 撤销栈 = 普通数组 + shift/pop（v1 无 redo），不写通用 Memento 类。
  4. 只引一个 vendor = TransformControls.js；不基于此再套 shell utility。
  5. 并发保护用 `<sid>/meta.json.tmp` 存在即锁（不建单独 `.lock` 文件——tmp 残留即锁信号，
     原子 rename 自然成立）。

## HR-01..04 既有函数锚点（grep 核实，不得改语义）

- `replay.js`：`apply_view_preset(name)` 349-375、`ls_get_raw(k,def)` 494、`ls_set(k,v)` 498、`reset_cam()` 338-341、`front_cam()` 342-345。
- `human_replay_lib.js`：`view_preset / measure_dist / measure_format / ray_ground_intersect / find_nearest_xy / LS_PREFIX`。新增一律 use new name，不 shadow。
- `human_replay_lib.test.js`：29 case 全保——追加 HR-05 case 只在文件尾部，不改既有判定。
- `human_replay_lib.py`：`Handler.do_GET/do_POST` 单入口、`/api/sessions / /api/board/* / /api/file` 白名单式路由。
- 锚点：points.bin sha256 = a4a24c19b886a56e4ddd26b8ab16d7ce5c2dbd9a49d25c18773646b41ec66f49。

## 新键位与既有键冲突对账

| 键 | HR-04 现状 | HR-05 用途（B 模式内） | 冲突? |
|----|------------|------------------------|-------|
| B | 未占用 | 切框选模式 | ❌ 独占 |
| V | 未占用 | 回查看模式 | ❌ 独占 |
| W / R / T | R=reset_cam ✕（HR-04 已用作 view reset）；T=front_cam ✕（HR-04 正视）；W=飞行前移 ✕ | README §5 W/R/T = gizmo move/rotate/scale | ⚠ 真冲突——**取舍：B 模式内 W/R/T 重新分发 gizmo；B 模式外仍然保留 HR-04 原义（R=复位、T=正视、W=飞行前）。** README §5 语义以 B 模式激活为门禁，不与 HR-04 快捷键矛盾（README 键位表的前提是编辑器场景；V/B 是「编辑器模式切换」的入口）。 |
| X / Y / Z | 未占用 | 轴约束 | ❌ 独占（B 模式 only） |
| Ctrl | 全局修饰键 | 捕捉步进 | ❌ 不冲突 |
| Ctrl+Z | 未占用 | undo | ❌ 独占 |
| Ctrl+C / Ctrl+V | 浏览器默认复制粘贴 | 编辑器复制粘贴 | ⚠ 阻止默认：ev.preventDefault()。 |
| Enter | 未占用 | 定稿 | ❌ 独占（B 模式 only） |
| Del | 未占用 | 删除选中 | ❌ 独占（B 模式 only） |
| Esc | HR-04 用于飞模式退出 | B 模式逐级退出 | ⚠ 先判断是否 fly.on（先让 fly_exit 吃掉 Esc）→ 再判断是否在 B 模式逐级退出——单入口按优先级链。 |
| 左键拖拽 | B 模式：画框；V 模式：轨道旋转（HR-02 TrackballControls） | 画框 | ⚠ B 模式要禁 controls.rotate，V 模式放行 |

飞行模式（S.fly.on）继续吃所有新键（HR-04 一致，HR-05 不例外）：飞行态按 B/V/W/R/T/X/Y/Z/Enter/Del/Esc 仍然走 fly_tick 通道，B 模式不在飞行态激活。

## 状态机（S 层的场景 / 模式 / gizmo / 选择）

```
S.mode ∈ {"view", "annotate"}            # B/V 切换
S.draw ∈ {idle, dragging(p0)}            # B 模式左键
S.selected ∈ annotation | null           # 当前选中的框（未定稿 或 已定稿）
S.gizmo_mode ∈ {"translate","rotate","scale"} | null   # TC mount 时
S.axis_constraint ∈ {"x","y","z"} | null # X/Y/Z 按住
S.snap.on ∈ bool                          # Ctrl 按住
S.undo ∈ {stack:[], capacity:20}
S.clipboard ∈ {label, size, yaw} | null
S.annotations ∈ Map<seq, box[]>           # 内存草稿；key=frame_seq
S.focus_annotation ∈ boolean              # 在面板 input 上（让 R 不吃键盘）
```

## 操作矩阵（每 R 条 → 函数映射）

| # | R 项 | 触发 | 守门 | 行为 → 函数 |
|---|------|------|------|------------|
| M1 | B 切框选 | keydown KeyB | 非 fly.on | `mode_set("annotate")`：HUD 显「框选」、controls.enableRotate=false、cursor=crosshair |
| M2 | V 回查看 | keydown KeyV | 非 fly.on；**画框拖动中 → cancel** | `mode_set("view")`：HUD 显「查看」、controls.enableRotate=true、cursor=default |
| M3 | 画框 start | mousedown btn0 | S.mode=annotate 且 ray 打地面返回 p0 | `draw_start(p0)`：临时 div + hud |
| M4 | 画框 drag | mousemove | S.draw=dragging | `draw_update(p1)`：z=0 平面求 p1 → 更新 div |
| M5 | 画框 end | mouseup btn0 | S.draw=dragging 且矩形 ≥ 0.1m² | `draw_finish(p0, p1)`：bbox_from_ground_rect → 未定稿框 wireframe 红 → S.annotations[seq].push → S.selected=新 → TC mount (translate) → undo.push({op:"add", ...}) |
| M6 | 画框太小 | mouseup btn0 | 矩形 < 0.1m² | 取消，不入 undo |
| M7 | W/R/T gs | keydown KeyW/R/T | S.mode=annotate 且 S.selected | `gizmo_mode_set("translate"|"rotate"|"scale")`；TC reattach |
| M8 | W/R/T 冲突 | keydown KeyW/R/T | S.mode=view | 仍走 fly_tick / reset_cam / front_cam（HR-04 语义保值） |
| M9 | 轴约束 | keydown KeyX/Y/Z | S.mode=annotate 且 TC mount 且拖动中 | `axis_constrain("x"|"y"|"z")`：TC.showX/Y/Z 临时禁；keyup 恢复 |
| M10 | 捕捉 | Ctrl keydown/keyup | 拖动中 | `snap_on(true|false)`：TC.translationSnap/rotationSnap/scaleSnap 更新 |
| M11 | 面板输入 | change on 8 input | input 位于面板，不带 focus 锁键 | `annotation_set_field(selected.id, field, value)`：validate → 通过则写 → TC/几何同步，入 undo；不通过 → 面板回滚原值 |
| M12 | 面板并发 | gizmo 拖动中 | 面板 input 失焦禁用？ | 面板 input 置 readonly；gizmo 拖动 → 面板同步更新 |
| M13 | Ctrl+Z | keydown ctrl+z | 栈非空 且 无面板 input focus | `undo_perform()`：pop top entry，按 entry.op 逆执行 |
| M14 | Ctrl+C 复制 | keydown ctrl+c | S.selected 且 无面板 focus | `S.clipboard = annotation_clone_for_copy(selected)`（不含 id/frame） |
| M15 | Ctrl+V 粘贴 | keydown ctrl+v | S.mode=annotate 且 clipboard 非空 | `annotation_paste()`：new_id() → frame=当前 seq → annotations[seq].push → undo.push({op:"add"}) → 选中 |
| M16 | Enter 定稿 | keydown Enter | S.mode=annotate 且 S.selected | `annotation_finalize(selected.id)`：fixed=true，颜色变更，TC detach，undo.push({op:"finalize"}) |
| M17 | Del 删除 | keydown Delete | S.mode=annotate 且 S.selected | `if (window.confirm("删除选定标注?"))` → annotations[seq] 移除 → undo.push({op:"del", backup:{...}}) |
| M18 | Esc 逐级 | keydown Escape | HR-04 fly.on 先吃；否则 S.mode=annotate | `esc_step()`：gizmo detach → 取消选中 → mode_set("view") 分级 |
| M19 | 切帧守卫 | slider input / ←→ / 空格 | S.annotations[S.frames[S.idx].seq] 有未定稿框 | `if (!window.confirm("未保存，确定离开?")) return`；确认则丢弃未定稿 |
| M20 | LS 草稿 | 每次 annotation 变更 | 非正在回放 | `draft_save(sid, annotations)` → `ls_set("annotations."+sid, JSON.stringify(annotations))` |
| M21 | LS 恢复 | 会话载入 | exists | `draft_load(sid)` → S.annotations 填充 → 重渲 |
| M22 | 保存按钮 | click 保存按钮 | 有已定稿框 exist 或有 del 操作 | `save_annotations(sid)`：annotation_serialize(S.annotations,"finalize-only") → POST /api/save_annotations → on ok 清草稿 → 刷新 meta → 重渲 |
| M23 | 并发锁 | 服务端 tmp 存在 |  | save → 409 → HUD 错误 |
| M24 | 失败回滚 | service 写中途失败 |  | meta.json.bak restore → 返 err |
| M25 | 快照 | 保存后 |  | S.annotations[seq]=已定稿 default |

## 服务端 `/api/save_annotations` 处理流程（Python）

```
def _api_save_annotations(self):
    body = self._body()
    sid = body.get("sid","")                 # ^cap_[0-9_]+$
    anns = body.get("annotations",[])        # list of dicts per README §2

    meta_path = os.path.join(C.DEST_ROOT, sid, "meta.json")
    tmp_path  = meta_path + ".tmp"
    bak_path  = meta_path + ".bak"

    if not sid_valid or not os.path.isfile(meta_path): 400/404
    if os.path.exists(tmp_path): return 409 conflict

    old_meta = json.load(meta_path)                          # 备份旧内容
    FROZEN = ["format","format_version","session_id","sensor","time_domain",
              "duration_sec","frame_rate_hz_measured","topics","point_layout",
              "point_file","frames","extraction"]
    for k in FROZEN:
        if k not in old_meta: fail("frozen field missing")

    # 校验 annotations 基本 schema（id/source/frame_seq/box.center/size/yaw 有限数）
    for a in anns: 验证 box 数 (annotation_validate_box 端口到 py)
    新meta = old_meta.copy(); 新meta["human_annotations"] = anns

    try:
        with open(tmp_path, "w") → json.dump(新meta) → flush → os.fsync
        os.replace(tmp_path, meta_path)      # Windows 原子
    except OSError as exc:
        尝试恢复：若 tmp 残余 → remove；若 meta 已写成半截 → os.replace(meta.bak,meta)
        raise 500

    sha = sha256(meta_path).hexdigest()
    return self._json({"ok":true,"count":len(anns),"sha256":sha})
```

并发保护键 = tmp_path 存在；Windows os.replace 自身是原子；锁不消失的概率与 tmp 残留概率相等，符合 ponytail（不另建 .lock file）。

## 已知坑

- TrackballControls 在左键 rotate 已绑；B 模式后退让 controls.enableRotate=false，依赖 TrackballControls.enabled 仍是 true（移动监听器仍留在；否则切 B 后滚轮/平移也死）。
- TransformControls mount 到 S.scene 时要把 object 传进去：`new THREE.TransformControls(S.camera, S.renderer.domElement)`；切相机时（HR-04 apply_view_preset）要重建 TC 或 setCamera——HR-05 在 apply_view_preset 尾部加一个`if (S.tc) S.tc.camera = newCam`（读代码看 TC 是否有这字段；没有就 detach+new）。
- TC 拖动会跟 TrackballControls 左键抢事件：TC 拖中禁 Trackball（TC 自带 `dragging-changed` event → set S.controls.enabled = !e.value）。
- 面板 focus 期间全局键盘 dispatcher 要 skip（否则 input 里按 'w' 就触发了 gizmo 切换）。
- localStorage 的 annotations 只在会话载入后写；切会话会清理 S.annotations。

## 副作用对照表（必须显式）

| 操作 | 改场景 | 改 S.annotations | 改 undo 栈 | 改 localStorage | 改 meta.json |
|------|--------|------------------|------------|-----------------|--------------|
| B/V 切换 | ✗ | ✗ | ✗ | ✗ | ✗ |
| 画框结束 | 加临时 mesh | + 1 未定稿 | push(op:"add") | ✗ | ✗ |
| TC 拖动 end | object pos/rot/scale | in-place 修改 | push(op:"edit") | ✗ | ✗ |
| 面板改字 | object + scene | in-place | push(op:"edit") | ✗ | ✗ |
| Ctrl+C | ✗ | ✗ | ✗ | ✗ (内存 clipboard) | ✗ |
| Ctrl+V | 加 mesh | +1 未定稿 | push(op:"add") | ✗ | ✗ |
| Enter | object 颜色变 | in-place (fixed:true) | push(op:"finalize") | ✗ | ✗ |
| Del | object 移除 | -1 | push(op:"del") | ✗ | ✗ |
| Esc lv3 | ✗ | ✗ (状态变) | ✗ | ✗ | ✗ |
| 切帧守卫 | ✗ | 若确认丢弃：-未定稿 | ✗ | ✗ | ✗ |
| LS 草稿 | 每次变更后 | ✗ | ✗ | ✓ annotations 字段 | ✗ |
| Save 按钮 | ✗ | 全部 fixed | ✗ | ✗ 清草稿 | ✓ meta.human_annotations |
