# CAM-HOT R1 相机助手视觉场景建模回传

## 本轮信息

- 工单 / 轮次 / 执行者 / 时间：CAM-HOT / R1 / Claude (claude-fable-5) / 2026-10-13
- 验证目的：相机助手视觉另一模态，验证 r02 f10 lidar target 是否纯人体；生成跨模态场景模型
- 验证表路径 / 版本 / SHA：`docs/human_capture/evidence/2026-10-13_cam_hot_r1/README.md`
- 执行方式 / 实际会话与模型：板上 `systemd cam-mjpeg` 8081 服务 + `curl /stream` 201 帧原流；Windows 本机 Python 3.12 （兼容 3.8 语法的脚本）+ Node v24
- 状态：SUBMITTED；视觉与场景建模 PASS（工具级）/ 生产验收 NOT_RUN / 独审 NOT_RUN / 不 ACCEPTED
- 起始 branch/HEAD：master/`026e06303f60ed1bbe4ddc4d037836db68da6d27`（同 HF-REAL-03，未动）
- ponytail SKILL.md 实际读取路径：`C:/Users/30680/.codex/skills/ponytail/SKILL.md`

## 验证关键结论

| 验证ID / 入口或转换 | synthetic/offline/device | 实际命令或源码进入位置 | PASS/FAIL/NOT_RUN/BLOCKED | 日志/样本与源 SHA |
|---|---|---|---|---|
| CAM01 服务状态与 curl | device (板上 8081) | `curl http://192.168.31.58:8081/stream` 8 秒捕 13,932,346 bytes / 201 帧 | PASS | 证据目录 cam_raw.bin |
| CAM02 f10 lidar target 纯人验证 | offline 跨模态 | 看 CAM_F0000.jpg 人手提裙摆/袋 ≈ lidar target 819 点 = PERSON_LEFT_ARM_OBJECT | PASS（独立模态） | F010_RECLASSIFIED.png + json |
| CAM03 场景建模 | offline + camera | scene_model.py 生成 9 objects + 走廊几何（宽估 1.7m，左墙 y=1.0 / 右墙 y=2.7） | PASS（工具）| SCENE_MODEL.png + json |
| CAM04 生产影响 | offline | 未动生产 / cam-mjpeg 服务配置 / r01-r03 源码 | PASS | 边界说明 |
| CAM05 独审 / GT / 设备 / 部署 / 生产 | device / deploy | NOT_RUN（不授权）| BLOCKED / NOT_RUN | 未启动 |

## 实际变更

| 文件 | 本轮用途 | 提交源码 SHA |
|---|---|---|
| docs/human_capture/evidence/2026-10-13_cam_hot_r1/README.md | 证据目录 README | 见文件夹清单 |
| docs/human_capture/evidence/2026-10-13_cam_hot_r1/{CAM_F0000,CAM_F0100,CAM_F0200}.jpg | 三帧实时相机捕获 | 见文件夹清单 |
| docs/human_capture/evidence/2026-10-13_cam_hot_r1/cam_raw.bin | 13.9MB MJPEG raw stream | 见文件夹清单 |
| docs/human_capture/evidence/2026-10-13_cam_hot_r1/{SCENE_MODEL.png,SCENE_MODEL.json} | 跨模态走廊场景模型 | 见文件夹清单 |
| docs/human_capture/evidence/2026-10-13_cam_hot_r1/{F010_RECLASSIFIED.png,F010_RECLASSIFIED.json} | f10 区域重分类对照 | 见文件夹清单 |
| sidequests/human_fusion_lab_next/real_fall/r03/scene_model.py | r03 工具新增（同 r03 中其他工具） | SHA 见 r03 ARTIFACTS_FINAL_SHA.json 更新版 |
| docs/human_capture/returns/CAM-HOT.md | 本 return | 本文件 |
| docs/human_capture/README.md | 顶部登记本单 | 见下文 |
| docs/sidequests/REVIEW.md | 登记本单（如需要） | — |

## 未闭合与限制

- 相机与 lidar 不同步（相机 = 实时于 2026-10-13 19:06 左右；lidar session 094333 = 早上录制）：
  - 携带裙摆/袋的人体活动模式对两次都合理
  - 但 CAM 不 forge 早期 lidar 逐帧逐点的相机证据
- 094302 / 215540 / 215623 / 215643 / 233658 没对应相机历史；CAM-HOT 不补造任何会话的相机证据
- 本单不触发 HF-REAL-02 RS04 FAIL 自动关闭；独审需在 HF-WORKFLOW 顶部日后登记介入
- 对 8081 服务只读； 相机在人物演示活动期间运行的隐私范围以用户授权活出
- 相机 anchors 的 x/y 坐标是由 scene 成像估计，不是经级外参融合； 不是专业 SLAM

## 交给 Codex 独立复审

- 视频实时相机证据与场景模型：`docs/human_capture/evidence/2026-10-13_cam_hot_r1/`
- 跨模态 f10 重分类与对象计数：F010_RECLASSIFIED.json （躯干 819 / 身体人手物品 57 / 未知 476）
- r03 源码变更：r03/scene_model.py（见 r03 ARTIFACTS_FINAL_SHA.json 更新版）
- 相机原始流：cam_raw.bin + CAM_F0000/0100/0200.jpg
- 当前工单下一步：独审决定是否关闭 RS04；是否授权 fusion v2 / online bg 修正；是否新采集带相机同步的 lidar 会话

Codex 读取共享工作区并对全表独立复审，集中反馈已有要求下的缺陷。派工遵循 WORKFLOW 当前约定；手动派工不授权自动启动实现 CLI 或下一单。
