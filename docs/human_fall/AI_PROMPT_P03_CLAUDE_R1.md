# P03 R1 回放自动配平（Claude Code 开发提示词）

2026-10-05。用户在 P02 R3（类型 C、6 对互预测 FAIL）之后明确：跌倒项目不愿继续打磨配平，**回放页选择会话时算法自动配平，算法放 8901 服务侧**。写前必读：本提示词、`P03_ACCEPTANCE.md` v1、`pc_apps/human_replay/LEVELING_README.md`、`leveling.py`、`leveling.js`、`leveling_estimators/{ransac,svd,tls}.py`、`replay.js`、`docs/human_fall/RETURN_TEMPLATE.md`。生产 writer 只有你（Claude Code），Codex 编排/独审角色按 WORKFLOW 当前约定不变。

## 0. 范围（硬边界）

只改/新建 `pc_apps/human_replay/` 内：

- 新建 `leveling_lib.py`（纯函数 `detect_ground_domain`，stdlib+NumPy，无新库）；
- 改 `leveling.py`：加 auto 分支接受「无 regions 的 auto 请求」，**不删/不改** DEFAULT `regions` 必填=4 的人工确认路径语义；
- 轻调 `leveling.js`：auto 提交/结果的入口与显示（仍走既有「确认后才允许下载/消费」的 STOP，不绕过 ground_confirm STOP）；
- 改 `replay.js`：`__load_session_sid` 侧申请/复用 transform，把 R=Rx(roll)@Ry(pitch)+t=[0,0,d] 一次性在 CPU 应用到 points buffer 后渲染；无 transform 的旧对话显示名义或原样不破坏；
- 必要时 `human_replay_lib.test.js` 增补纯函数测试；
- 新建 `leveling_auto_test.py`（unittest，stdlib+NumPy）。

不改：`driver/webui/annotator.html/captures/*/旧证据/console exe/生产外参`。不设备/采集/部署/网络/commit/push/reset。Console exe 内嵌 human_replay 不重打包。console-app-facts 双 html 同改原则适用于本单（如有 index.html/console 双页面引用新入口，一并改）。

## 1. 设计约束（R2/R3 先验，不能违反）

- **禁止把 R2 联合值复制进代码**：26.623°/−1.395°/1.3219m 只作 P03-D 的比较锚点写在证据 JSON，不是代码常量。
- **候选门固定**：n_z≥.85（朝上传感器视角）、d∈[.8,1.8]m、内点阈值 .08m（比 leveling 的 .05 松一档，允许 auto 容错；明示在 README 差异点）。支持率必须如实公开，不拿"最大平面=全场地面"。
- **ROI 生成**：凸包栅格近似（1m 单元，占格≥30 点），连通域取 top-K（K∈[3,8]），每区转 `[xmin,xmax,ymin,ymax]` 且每边≥5cm、互不重叠；若最终 K<3 → `ground_auto_candidate_invalid` 显式失败（不递补、不收缩）。
- **对 leveling.py 的修改只允许附加分支**：`config.mode == "auto"` 时忽略 `regions=4` 必检、由 `detect_ground_domain` 现算；`mode` 缺省=旧路径保持字节级行为。
- **留帧/几何门/两两一致性**全部复用 leveling.py 现有实现，不复制——detect 输出 ROI 直接喂给既有 `run_job` 的同一冻结/拟合/评估管线。
- **输出契约**：`status: research_display`、`physical_verified=false`、`extrinsics_verified=false`、`runtime_eligible=false`；1.14m 实测继续另存不绑定。

## 2. 必做执行

1. **00_diag.md**（先于代码）：`validate_request`/`run_job`/`freeze_domain`/三法/留帧/一致性/导出/transform 在 `replay.js` 的每个消费点逐函数行号映射 auto 模式会触碰哪些、不改哪些；显式声明不绕开 ground_confirmed STOP。
2. `detect_ground_domain(points)`：入参 finite/nonzero/float64，本函数内纯 NumPy，def detect 返回 `{'regions': [...], 'candidate': {'normal','offset','support_fraction','points_in_band','basis'}}` 或抛 `ValueError('ground_auto_candidate_invalid: <具体reason>')`；ponytail：能一步向量化的别写循环。
3. leveling job 的 auto 分支中记录 detect 输出与三法 pitch/roll/d；**与 R2 联合 TLS（26.623261°/−1.394671°/1.321900834m，从 `evidence/2026-10-04_p02_four_roi_r1/03_RESULTS.json` 读，不手输）在 cap_20261004_202456/_203349 上 pitch 差 <1.5°**，做不到 → P03-A 如实 FAIL，不裁数据/不降阈值。
4. 在三既有 session 上跑 auto：cap_20261004_202456、cap_20261004_203349、第三个从本地 `captures/remote/` 任选并在证据里说明；输出 transform 写 `captures/leveled/<job_id>/transform.json`，同 GLW01 schema（见 LEVELING_README.md），行序/元数据保持。
5. replay.js 消费：先 `HEAD /api/leveling/…` 或拉列表查 transform；存在→应用；不存在→原样渲染+一处小字提示；**不让旧明文会话自动配平改视觉**（用户确认才消费）。
6. 回归：`python -B -W error -m unittest discover -s pc_apps/human_replay -p leveling_test.py -v` 与 `node human_replay_lib.test.js` 不退；新增 `leveling_auto_test.py` 至少覆盖三 session PASS 路 + 3 个负路径（候选门不满足/连通域<3/网格空）+非法请求显式拒绝。
7. 完成停写 → `evidence/2026-10-05_p03_auto_leveling_r1/` 报告、SHA manifest、命令/退出码、ponytail 声明。

## 3. 验收（P03 v1）

固定 ID：**P03-A/B/C/D/E + S01 + D01**，见 `P03_ACCEPTANCE.md`。状态只 SUBMITTED/BLOCKED，逐条 PASS/FAIL/NOT_RUN；指定独审与真实 browser NOT_RUN 不冒称。

## 4. 失败处理

3 个负路径任一未显式拒绝 → REWORK；三 session 候选 pitch 与 R2 锚点差任一 ≥1.5° → P03-A 保留 FAIL 继续交付（不停工），报告当作诊断证据。service 只读性失效（旧 leveling 触发了 auto 代码路径）→ 立即回滚自身改动块，研讨后重发。

结束停写，回传 + evidence 路径 + 未闭合 ID。
