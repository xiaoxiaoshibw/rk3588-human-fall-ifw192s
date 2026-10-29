# annotator_v2 架构说明

规范（2026-10-24 十～十五节）的落地。模块按职责拆分、边界单向依赖：
`ui → viewport2d/viewport3d/timeline/algorithm/annotation/session/storage → domain`。
渲染模块不读写文件、不调标注存储；存储模块不依赖 React/Canvas/Three。

## 坐标系与单位（所有标注字段共用的契约）

- 世界坐标：**传感器原始坐标**（IFW192S 设备系，x 前 / y 左 / z 上），单位米。
  `AnnotationDoc.coordinateFrame = "sensor-IFW192S-raw"`。
  注意：旧 gt_workbench/1 是 leveled 坐标系，导入 v1 时必须人工核对（见 storage）。
- 帧：`meta.json frames[]` 下标（0 起）；源时间 `stamp_sec + stamp_nanosec/1e9`
  （设备秒，time_domain=device_stamp_s_unanchored）。播放时钟按此推进，
  暂停/逐帧/标注始终落在真实源帧上，不造帧、不改时间戳。
- 俯瞰 2D：北向上（y+ 屏幕向上）、x+ 向右；`viewport2d/transform.ts` 是唯一换算点。

## 模块与职责

| 模块 | 文件 | 职责 | 不做 |
|---|---|---|---|
| domain | `src/domain/` | 人物/框/区间/建议等可序列化类型 + 纯几何（拖框规范化、命中优先级柄>体>背景、缩放钳制、框内统计、显示抽稀）+ 文档校验 | 无 IO、无 UI 依赖 |
| session | `src/session/` | meta 解析（边界校验）、帧加载（LRU 24 帧上限、在途去重、预取±1/+4、代次 generation 防过期）、Worker 解码（28B 小端结构 → Float32Array，transferable） | 不解析标注、不渲染 |
| annotation | `src/annotation/ops.ts` | 编辑操作（Op 命令模式 + 逆操作）与撤销栈；拖动=预览+结束一次提交 | 不碰指针/DOM |
| storage | `src/storage/` | gt_annotate/2 序列化/解析（字段级校验）、v1(gt_workbench/1) 只读迁移导入、保存（baseVersion 冲突 409）、导出下载 | 不依赖 React/Canvas |
| viewport2d | `src/viewport2d/` | 坐标变换、双层画布渲染（底图=点云仅帧/视图变化重绘；覆盖层=框/柄/预览，rAF 合并）、DOM 无关指针交互状态机 | 不读写文件；不直接改标注（经 commitOp 回调） |
| viewport3d | `src/viewport3d/threeView.ts` | 与 2D 共享同一份 DecodedFrame；预分配缓冲（drawRange 控制）、关闭即 stop+dispose、可注入渲染器测试 | 不加 React 依赖 |
| timeline | `src/timeline/clock.ts` | 播放时钟（源时间戳为纲、倍速重锚、结束自停）、时间轴像素换算 | 不管理帧加载 |
| ui | `src/ui/` | React 组件（工具栏/人物列表/属性面板/时间轴/两个视口）与装配 | 高频指针状态不进 React（refs + 局部控制器） |
| algorithm | `src/algorithm/` | 适配器接口（id@version+paramsHash）、宿主（generation 校验丢弃过期、显式采用/拒绝）；内置演示聚类适配器 | 建议不自动进人工标注 |
| server | `server.py` | 静态 dist/ + `/api/sessions` + meta/帧切片 + GT 原子保存（tmp+os.replace，版本冲突 409） | 不做算法/标注逻辑 |

## 四类状态（谁拥有、谁改）

1. **会话/帧状态**：React state（sessionId/meta/frameIndex/playing）+ `SessionLoader` 实例（ref）。
   帧切换 → loader 取帧（代次校验）→ `frameRef` 单一引用 → `frameEpoch` 通知 2D/3D 消费同一份。
2. **持久标注**：`AnnotationDoc`（React state）+ `UndoHistory`（ref）。所有修改经
   `commitOp(op)` → 撤销栈 → setDoc；拖动期间只改控制器预览。
3. **暂态交互**：`InteractionController`（ref，DOM 无关状态机：drawPending/drawing/moving/
   resizing/panning/maybeEmptyClick）。切帧/切工具/失焦/pointercancel → interrupt 清理。
4. **视图设置**：`ViewTransform`（ref，平移/缩放不触发 React 渲染；底图重绘经 rAF 合并）。

## 数据流

```
meta.json ──server(切片)──> ArrayBuffer ──Worker(解码,转移)──> DecodedFrame(LRU≤24)
                                              │(同一引用)
                    ┌─────────────────────────┼──────────────────┐
                viewport2d 底图            viewport3d            属性面板统计
PointerEvents ─> InteractionController ─预览─> 覆盖层(rAF)
                     └─pointerUp─> Op(addBox/updateBox/composite) ─> UndoHistory ─> AnnotationDoc
AlgorithmAdapter.run(ctx{generation}) ─> Suggestion[]（过期丢弃）─> doc.suggestions（pending）
                                        └─用户「采用」─> composite(addBox origin=adopted + 状态accepted)
AnnotationDoc ──GtClient(baseVersion)──> server.py 原子写 gt_store_v2/<sid>/draft.json
```

## 格式与版本

- `gt_annotate/2`：persons/boxes(轴对齐俯瞰矩形+z范围)/intervals(闭区间)/suggestions
  （与人工标注分开存储；status pending/accepted/rejected；采用回填 adoptedRef）；
  `sampleFrames` 为可选新增字段（稀疏标注帧清单，旧文档缺失按空表解析，不升版本）。
- 校验规则见 `domain/validation.ts`（同人同帧至多一框、zMax>zMin、帧域、人物引用等）；
  解析边界 `storage/gtFormat.ts` 逐字段校验，坏文档整体拒绝。
- 不兼容变更：升 `formatVersion` + 显式迁移函数；不静默改旧字段含义。
- v1 导入：`importV1Doc` 只读转换（PERSON+track_id → 外接矩形框），坐标系差异写入 warnings。

## 常见修改入口

- **改 UI/加按钮**：`src/ui/Toolbar.tsx`（或对应面板）+ `App.tsx` 装配；业务语义尽量下沉到
  `annotation/ops.ts` 保持可撤销。
- **改后端接口/存储**：`server.py`（端点/原子写/冲突）+ `src/storage/client.ts`（调用）+
  `src/storage/gtFormat.ts`（格式/版本）；跑 `test_server.py` 与 `tests/storage.test.ts`。
- **改存储格式**：`src/domain/types.ts`（类型）→ `gtFormat.ts`（序列化/校验/迁移）→
  `validation.ts`（规则）；升版本号，加迁移测试。
- **接入算法**：实现 `AlgorithmAdapter`（`src/algorithm/types.ts`），在 `App.tsx` 换掉
  `makeDemoClusterAdapter()`；结果自动带 id@version/paramsHash/帧绑定，采用流程不变。
- **改交互**：`src/viewport2d/interaction.ts`（状态机，纯逻辑可测）+ `ui/Viewport2D.tsx`（DOM 接线）。
  反例回归在 `tests/interaction.test.ts`。

## 已知边界（如实）

- 帧加载 p50≈60ms（本机）与 10Hz 帧间隔接近；1.37 MB/帧的长会话仍受本机网络/磁盘影响。暂停时切帧 80 ms 去抖、预取停手 150 ms，避免拖时间轴时请求风暴；播放时即时取帧并预取。
- 2D 底图已改为离屏 `ImageData`（24 级 z 色板）一次 `drawImage`，49,119 点/498×543 实测 P50 2.7 ms（旧逐点 `fillStyle+fillRect` P50 49.8 ms）；统计/命中/保存仍用完整数组。
- 后台/被遮挡视图 rAF 冻结时底图不重绘、播放随之暂停（对标注工具可接受）；桌面截图需可视窗口。
- 780 帧真实会话已实测加载、逐帧去抖、落框和滚轮，完整播放/长时稳定性未单独验证。
- CE3（拖动中切帧/失焦）为状态机单测 + 接线代码覆盖；浏览器内无法原子注入"真实拖动中切帧"。
- `maxExtentM>2.2m` 的结构（墙面）不会被演示聚类提议。
