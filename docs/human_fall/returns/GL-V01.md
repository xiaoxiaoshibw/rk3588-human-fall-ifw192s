# GL-V01 回传 / R2 / Codex + Luka 补记 / 2026-10-05

依据 [WORKFLOW.md](../WORKFLOW.md) 与 [GLV01_ACCEPTANCE.md](../GLV01_ACCEPTANCE.md) v2。R1 的「数值 PASS 即地面完成」判断已撤回，R2 以自动地面识别替代手选四区，手选记录只作独立对照。

## 本轮信息

- 工单 / 轮次 / 执行者：GL-V01 / R2 / Codex（主写）+ Luka（仅收口：锁文件处置与旧镜像同步，不改算法、不改验收结论）/ 2026-10-05。
- 状态：**SUBMITTED**（算法自验完成、源码停写）；外部独审 NOT_RUN，设备/物理真值 NOT_RUN，整体**未 ACCEPTED**。
- R2 提交：[evidence/2026-10-05_gl_v01_r2/15_SUBMISSION.md](../evidence/2026-10-05_gl_v01_r2/15_SUBMISSION.md)；收口附记：[21_closeout_luka.md](../evidence/2026-10-05_gl_v01_r2/21_closeout_luka.md)。

## R2 做了什么（相对 R1）

| 项 | R1（已撤回部分）| R2 |
|---|---|---|
| 地面来源 | 用户手选四 ROI，算法只对其做平面拟合 PASS | 新增 `floor_detector.py`：从 FIT 点云发现最低近水平连通面 + 四分区自动选格，不读人工 ROI |
| 排除桌面/人体 | 未做（R1 大框按 1m 网格密度取） | 完整 XY 格高度参与厚度/局部法向/障碍门，混入高处点的格整格拒绝 |
| 手选四区角色 | 定义算法输入 | 仅作独立后置对照（202456 自动 vs 手选：角差 1.586310°、offset 差 0.005015 m），数值用于核对，不参与检测 |
| 旧数值候选 | 残留可触发预览/下载 | 显式降级为「待确认地面」诊断，不再自动衍生下载/自动应用 |

## 指定场景的实际自动地面（数据见 [20_target_plane_summary.json](../evidence/2026-10-05_gl_v01_r2/20_target_plane_summary.json)，唯一真值是 [04_auto_results.json](../evidence/2026-10-05_gl_v01_r2/04_auto_results.json)）

- cap_20261004_203349：前方 1.25–2.5 m、右侧 0.25 m 到左侧 0.75 m 带内；z ≈ −1.29…−1.38 m（名义指示）。
- cap_20261004_203135：前方 1.0–2.5 m、右侧 0.75 m 到中线；z ≈ −1.25…−1.40 m。pitch 28.60°、roll −1.48°，offset 1.4024 m。
- cap_20261004_202456：前方 1.25–2.5 m、右 0.25 m 到左 0.75 m 带；z ≈ −1.24…−1.38 m。pitch 25.45°、roll −1.38°，offset 1.2677 m。

「z / offset 名义值」全部来自算法候选的 normal/offset 解算，只是点云一致性，不等于真实安装高已物理核验（D01 NOT_RUN）。

## 收口新增事实（不改验收判断）

- 桌面快捷方式 → R2 exe 已确认（13b）。
- `dist/Console.exe` 与 `dist/hr02_offline/Console.exe` 在 R1 时未同步，本已停 R1 旧实例后由 Luka 同步为 R2 SHA C8F34A5E…；`LiDAR_Console.zip` 发布包同；原 R1 zip 保留为 18_LiDAR_Console_v2.zip.before（详见 18_console_sync.json）。
- 桌面 `LiDAR_Console_20261005.zip` 来源未在仓库中找到，保持不动。
- `dist/gl_v01/`、`dist/gl_w01/` 按 GL-W01 附记保持历史版本。
- SOURCES/captures/meta/bin/旧产物在收口中没有再触碰。
