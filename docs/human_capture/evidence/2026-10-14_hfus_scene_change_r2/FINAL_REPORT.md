# 冻结场景新增点提取与抗抖动（2026-10-14）

当前 HFUS-SCENE-CHANGE-01：SUBMITTED / 软件自验通过；人体身份与物理资格不报 ACCEPTED。

按用户确认的 D:/Code/ldiar 人体融合页面开发。聚类前使用已冻结的真实空场，不从含人动作录制更新背景。原 R1 聚类半径、最小点数、ROI 与候选资格保持原值；没有训练或替换模型。

## 实现

传统三维几何：冻结背景局部 PCA 平面、KD-tree 近邻、静态近背景锚点的六自由度小幅刚体拟合，再生成当前新增点的独立三维连通簇。局部表面匹配有实测邻域半径，不能把无限地板/桌面平面延伸去删人。使用现有 NumPy/SciPy 与原三维聚类，不引入 PCL 绑定。

补偿幅度以空场 CAL 帧估计，加现有体素半边长度的量化余量；动作/HOLDOUT 不参与标定。退化、支持不足、越界或静态残差恶化时明确拒绝补偿。补偿前后任一解释可匹配冻结背景的源行都不能晋升为新增点，两种解释的分歧保存在 pose_ambiguous_indices，身份 UNKNOWN。没有整片近地保留或固定高度删除整个人；仍复用原观察域高度界限。

这是一条固定传感器单帧刚体扰动的隔离离线管线，未建模帧内扫描畸变。没有证明小幅拟合等于传感器真实物理位姿，也没有跨场景、人体完整性或家具身份准确率验收。

## 实测

- Windows / Python 3.12 / NumPy 1.26.4；当前运行 694.32 秒，是整段离线工程运行时间，不是实时性能或 Jetson 证据。
- 八段 1,934 动作帧全部有几何目标候选；空场 32 个独立留帧 0 个目标候选。候选数量与逐帧覆盖不等于识别准确率。
- 前景残余 4,945,525 → 4,791,433（减少 3.116%）；这是混合点观测数量，不是家具污染率。
- 目标成员总数 3,672,529 → 3,659,895；不能把减少的成员全判成家具或噪声。
- 1,966 帧源行边界/互斥/目标属于新增点/显示坐标刚体回算/粗节点源点支撑全部通过；在当前有效域内，补偿前已匹配背景的点被晋升为新增点：0。
- Edge 实际原页面源码：九会话、方案切换、站立/仰卧截图、跳帧、源行回查、切回 R1 通过，pageerror 0。
- 12 项相关 Python 检查通过；node --check app.js 通过。合成抗抖动检查明确是 SYNTHETIC，不替代真实身份 GT。

| 会话 | 帧 | 新目标帧 | 原前景点 | 新前景点 |
|---|---:|---:|---:|---:|
| cap_20261013_083254 | 225 | 225 | 476693 | 461204 |
| cap_20261013_083218 | 231 | 231 | 546717 | 531142 |
| cap_20261013_083120 | 247 | 247 | 629906 | 611678 |
| cap_20261013_083044 | 251 | 251 | 816532 | 797575 |
| cap_20261013_082906 | 175 | 175 | 437647 | 422566 |
| cap_20261013_082829 | 183 | 183 | 466124 | 451625 |
| cap_20261013_082717 | 327 | 327 | 832020 | 804550 |
| cap_20261013_082623 | 295 | 295 | 736869 | 708153 |
| cap_20261013_131958 | 32 | 0 | 3017 | 2940 |

## 失败与修正

第一版只在补偿后坐标做背景匹配，虽然平面残差下降，却把部分原匹配背景边缘推成新增前景；不采纳。完整第一轮 1,966 帧产物保留在 action_research_scenechange。采用双姿态背景解释后重新全跑，当前产物 action_research_scenechange_guarded。

首次浏览器检查用 inner_text 读取折叠 details 内的源行 JSON 得到空字符串，JSONDecodeError；API 返回实际正确，改 text_content 后完整重新验证。首轮 SOURCE_CHECK/截图/BROWSER_FAILURE 在 ../2026-10-14_hfus_scene_change_r1/ 保留。另一次误用 test_contract.py 模式没有发现测试，退出 1；实际相关测试文件后续执行通过，不把 0 tests 当验证。

## 复现与产物

从 D:/Code/ldiar 的 PowerShell 执行；--out 必须使用尚不存在的新目录，不覆盖旧证据：

```powershell
$env:OPENBLAS_NUM_THREADS='1'
$env:OMP_NUM_THREADS='1'
$env:MKL_NUM_THREADS='1'
python -B -W error sidequests/human_fusion_lab_next/pointset/r01/research_scene_change.py --out 新的独占目录
python -B -W error sidequests/human_fusion_lab_next/pointset/r01/check_scene_change.py --out 新的检查证据目录
python -B -W error sidequests/human_fusion_lab_next/pointset/r01/server.py --port 8954
```

检查器读取当前 action_research_scenechange_guarded；其他新实验目录应另行绑定，不覆盖当前运行。服务仅 127.0.0.1。新方案深链：http://127.0.0.1:8954/?dataset=actions&variant=scene_change&fi=0；仍是原 pointset/r01 页面，R1/R2/R3/retention 历史输出与默认 R1 选择保留。当前控制台已启动的旧进程不重启；本机对照服务不替换旧 EXE。

当前逐帧全部新增/背景匹配/歧义/目标源行及 R/t：sidequests/human_fusion_lab_next/pointset/r01/action_research_scenechange_guarded/<sid>/<fi>.json。输入 SHA、配置、环境、代码 SHA、命令与保护范围核验见该目录 SUMMARY.json / CALIBRATION.json；完整本版源码副本及 SHA 在 source_snapshot/。原始 XYZ 与完整 28 字节记录保持于只读 captures；源行 API 返回原始 XYZ、变换后 XYZ 与未改 opaque 字节，可按 row index 回查 intensity/ring/设备时间。

原 core.py/actions.py/config.yaml/config_actions.yaml、冻结背景、全部九份录制 SHA 核验保持；没有训练、采集、部署、Git 提交/推送或修改 GT。没有宣称整棵同时被其他会话修改的仓库冻结。

实际技能：C:/Users/30680/.codex/skills/ponytail/SKILL.md；C:/Users/30680/.codex/skills/scientific-toolkit-skill/SKILL.md。

当前剩余边界：人体/家具完整身份 UNKNOWN；贴地接触处双解释歧义不当人体 GT；空间 ROI 与单候选几何资格仍是原 R1 的限制。当前保留新方案为可复查对照，没有因点数减少晋级默认。
