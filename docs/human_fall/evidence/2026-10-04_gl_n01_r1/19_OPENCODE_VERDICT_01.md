## GL-N01 R1 只读独审结论

独立复算（未复用作者断言）：model_id 重算一致；对 3,699,085 个真实有效点用独立标量公式 `[c·x+s·z, y, −s·x+c·z+h]` 对拍，最大差 **3.55e-15 m**；源原点→(0,0,1.1)，逆变换残差 2.2e-16；89 帧 source_rows/输出行/统计一行不差。作者 02/05/08 数字可复现。

| ID | 结果 | 独立证据 |
|---|---|---|
| N01 | PASS | `nominal_leveling.py:28-31,58-68`；独立标量 GT/原点/多角多高/逆，max 3.55e-15 |
| N02 | PASS | 类型/范围门 `:21-27`；52 项独立 bool/str/NaN/inf/越界/单位/frame/schema 全拒；py3.8 AST=true |
| N03 | PASS | `_identity:14-17`+全量 JSON 重比 `:46-55`；pitch/height/frame 变参即新 ID；已有 out 拒（10 日志 exit2 + 我 4 例 exit2、零落盘） |
| N04 | PASS | `load_adapted` 只读；4372400→3699085 有效/0 非finite/673315 零；source_rows==独立 mask；逐帧 first:last 对应 0 失配；输入源/输出未改 |
| N05 | PASS（离线产物/静态图/软件逻辑；真实浏览器 NOT_RUN/BLOCKED，未升级 mock） | 五产物齐；07 PNG 实看低位带旋正后近水平仍略低于 z0，未回填；view.html payload 89×2000、JS 公式=标量式、导出/预览标签分明、无 support/ground.valid |
| N06 | PASS | `physical/extrinsics/runtime=false`；`validate_known_transform`/`validate_geometry_calibration` 拒；`resolve_reference_transform`→`reference_calibration_invalid`；全库无运行时消费者 |
| S01 | PASS | 仅 3 新源码路径；基线 4010 文件仅 2 个允许计划文档变动，无冻结改动；manifest 40/40 SHA 匹配；回归 445/2 OK |
| P01 | BLOCKED | 地板身份/误差/SDK 绑定未独立核；frame5 名义 z 最小 −0.593（低于 z0）未自动修正 |
| D01 | NOT_RUN | 无设备/采集/网络/部署/生产/IRLS；scope 无 driver/webui/config 改动 |
| Q01 | PASS | 02 输入/来源/frame/单位/finite 负例 + 我独立复核 |
| Q02 | PASS | 同内容 ID/caller 改/变参新 ID/已有 out/受保护路径，均有拒绝证据 |
| Q03 | PASS | 0/±/90°、不同高、逆变换、无 SDK 二次旋转；轴假设显式 |
| Q04 | PASS | 全量源行/零/非finite/分组对拍；仅显示抽样不改保存点；残差仍存在 |
| Q05 | PASS | nominal 可算术使用、不晋级 verified/runtime，冻结消费者拒 |
| Q06 | PASS | 提交/冻结 SHA/停写/原始 exit/new number/17 probe PROBE_OK exit0/本次指定只读独审均在 |

**Consolidated failures:** 无（无 FAIL、无返工项）。
**非阻断观察：** (1) “代码 SHA”绑定在工单 manifest 层而非单次 `input_manifest.json`，N04 仍成立；(2) N05 真实浏览器渲染仍 NOT_RUN/BLOCKED，未冒充通过。
**SHA/范围复核：** 结束点 3 个新源码 SHA 与 manifest 全等（`nominal_leveling bb8685…`、`level_capture_nominal 5c16dc…`、`test_nominal_leveling 4fd3ec…`）；基线保护文件 0 变更；`src/CMakeLists.txt` 为已知 Windows catkin 软链，与基线一致。

**最终：SUBMITTED / no-rework**（未声明 ACCEPTED，未启动下一阶段；P01 保持独立物理 BLOCKED，D01 NOT_RUN）。