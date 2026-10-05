# HTML 算法配平选项 / SUBMITTED（作者自验）

用户明确目标是 `docs/human_fall/evidence/2026-10-04_p02_level_preview_r1/06_PREVIEW.html`，本轮仅编辑该离线页面；未编辑原3D annotator。用户指定修改覆盖该HTML的旧产物冻结，但旧版完整保留 `02_PREVIEW_BEFORE.html`、旧SHA与manifest保留历史。

新增醒目的“算法配平”按钮和 TLS / SVD / RANSAC 选择。使用既有同101948点源系n/d/Rx@Ry结果，不另拟合当前预览帧，不把B箱子点纳入标定。算法使用原始source→display完整R/t，不把显示系修正当安装角。

算法参数卡显示pitch、roll、Z平移、RMS/P95、点数与仅#3覆盖范围；手动annotator角度/平移可切回。算法模式不受无效/空白手动参数阻塞，手动模式拒绝空白、非法值。默认仍为annotator方式。实测1.14记录及所有源点/预览帧/既有模型数据不变。

| 当前已有验收ID | 本轮结果 |
|---|---|
| P02-C | 复用冻结点域；Node逐位核九片段source样本不变，未改变选择规则 |
| P02-D | 复用10同域三估计器，未改算法/门/原结果 |
| P02-E | PASS（页面算法变换作者自验）；三种R·n≈up、source Z全样本标量oracle误差≤6.66e−16m，TLS与上一版输出差≤1.33e−15m；物理/全场不晋级 |
| S01 | PASS（本轮页面逻辑/范围作者自验）；原annotator/模型证据不变、九片段×三估计器、button/切换/手动恢复/空白值/物理记录保护通过。实际browser与指定独审NOT_RUN |
| D01 | NOT_RUN；不设备/采集/部署/driver/正式外参 |

命令 `python -B -W error update_preview.py` exit0；`node check_algorithm_html.js`修正CRLF解析后exit0。非完整指定独审/ACCEPTED，P1 NO。只新增本轮更新器/检查器，ponytail实际路径C:/Users/30680/.codex/skills/ponytail/SKILL.md。

首次Node检查因备份CRLF而正则只接受LF，在验证前exit1。旧检查器与失败记录04保留。05_SCOPE_AND_RESULTS的test_exit_code=0是结果检查前提前记录的错误，**不是有效测试证据**，07新编号结果更正；不掩盖流程错误。目标更新正确，后续只修检查器解析，并完成全部检查。旧12_FINAL_MANIFEST等指更新前06的版本，新07指当前用户要求版本。

回退=打开02_PREVIEW_BEFORE.html；无需回滚用户其他文件。当前HTML入口不变，08旧检查器属于上一版证据，新检查器才覆盖新增DOM。
