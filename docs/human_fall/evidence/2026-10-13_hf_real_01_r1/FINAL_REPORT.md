# HF-REAL-01 R1 / 真实会话首版 / SUBMITTED

2026-10-13。用户要求先配平去背景，再借助视觉分析、实现真人追踪倒地首版。Codex唯一writer，隔离源码 sidequests/human_fusion_lab_next/real_fall/r01/，原数据/生产/模型/GT/旧证据未改。

可操作回放：http://127.0.0.1:8929/ 。实际服务工具session25679，本机前台托管，不部署。README给出重启命令。

## 结果

094333共164帧/16.900秒，28B点布局、225554812字节经已有source校验。自动配平同域TLS/SVD/RANSAC全部质量与留帧通过，recommended=tls；pitch25.945995°/roll1.303450°/tz1.147883m，fit116754点、P95 .025833m。数字是离线平面结果，不是独立物理外参标定。

093958 TLS/SVD区域与holdout失败，RANSAC有效但整体NO_RECOMMENDATION，不降低旧门、不选单法冒称配平通过。本版只消费094333。094302不在本地，未访问设备或自行下载。

先实际看配平多视角，后去背景，再看前景多视角及真实浏览器。背景只用f0–9且排除XY[1.4,2.6]×[1.25,2.2]的视觉疑似人体区；不是人工确认空场。复用原pipe参考图/有界前景匹配，493579前景点与所有源行索引保存。被排除区残留家具直线带仍可见，没有藏掉。用整个会话静态建图会吞掉倒地静止人体，故本版本未采用。

视觉推断：约4–5秒降低，5.6–11秒低位，12秒后抬升，13.5秒附近重新高位。未把这些时间写进算法。初始种子(2.2,1.6)m由助手视觉指定，不能叫自动识别人。f0–9 UNKNOWN启动校准，f10–163 154帧全部有同一ID的候选组件关联；这个数字只是关联输出覆盖，非人工身份准确率。最近邻3D组件不受站姿人体分类门影响，低位仍关联；长失联拒绝静默换人。

原FeatureExtractor/FallStateMachine只读复用，mode_verified/allow_confirmed仍false。状态首次upright f15/1.56s；低姿态f42/4.37s；suspected f57/5.91s；recovering f122/12.65s；最后upright。独立明确标为未验证prototype_fall_alert的规则，在suspected且P90<=.65m/Z全范围<=.75m连续1.5s后，f72/7.460271s生成一次。f72为1701目标点/P90 .394m；恢复高位P90约1.43m。没有把该事件写成生产confirmed或人类确认的真实意外跌倒。

## 验收 v1 逐项自验

| ID | 状态 | 证据 / 限定 |
|---|---|---|
| RF01 | PASS | BASELINE_BEFORE：master/026e06303f60ed1bbe4ddc4d037836db68da6d27，19201文件tracked/untracked/ignored实际SHA，errors/drift空；非原子，.git内部和symlink目标排除。prepare调用原source验证两会话格式/大小/时间与SHA |
| RF02 | PASS(094333) / FAIL(093958) | 各*_leveling.json三法/区域/留帧原结果完整；失败未降门，093958未接追踪 |
| RF03 | PASS（启动参考试验） | foreground.json/BIN/source_rows；背景身份未确认限制公开；独立source row审计164帧493579点，max误差<2e-6m，不用全段自吸收 |
| RF04 | PASS（助手视觉分析） | VISUAL_REVIEW、实际多视角contact sheets与真实浏览器截图；不冒称人工GT/每帧视觉确认 |
| RF05 | PASS（开发会话输出） | tracking_v1：154测量帧；视觉初始化/低位保持ID/UNKNOWN明示；真人连续身份精度仍BLOCKED |
| RF06 | PASS（未验证原型） | f72一次prototype事件，最后恢复upright；core confirmed一直false，seek读取固定结果；不报告泛化或意外跌倒准确率 |
| RF07 | PASS（本机限定） | verify 2 tests exit0/全foreground源行audit；HF06 20 tests -B -W error exit0（含原未知/状态边界）；Node syntax exit0；3.8 AST检查PASS；实际Edge WebGL操作与4非法HTTP400；browser_r2控制台无error；加载依赖/输入/SHA结束核验81项、已有baseline文件零SHA变化；不是第二次全树原子冻结 |
| RF08 | NOT_RUN / BLOCKED | 未派独立未参与作者审核NOT_RUN；人工身份/姿态GT与跨场景泛化BLOCKED；设备/物理/板端性能/部署NOT_RUN。非ACCEPTED |

## 命令、失败与边界

`python -B -W error .../prepare.py cap_20261013_094333 cap_20261013_093958` exit0（093958数值FAIL不等进程失败）；`node --max-old-space-size=2048 .../foreground.js` exit0；`python -B -W error .../track.py` exit0；`python -B -W error .../verify.py` exit0，VERIFY.log；原HF06回归HF06_REGRESSION.log exit0；browser_check.py第二轮exit0，browser_r2/BROWSER_CHECK.json。

初次render脚本命名inspect.py遮蔽标准库inspect而exit1，已改名render_views.py，原失败工具输出保留；无图像/结果假称成功。CUA无法初始化（kernel assets路径缺失），改实际headless Edge Chromium检查自建网页，不使用原工具假截图。第一次浏览器因favicon404记FAIL，BROWSER_CHECK.json/errors与当轮截图保留；新server补favicon204，第二轮单独browser_r2所有UI/console通过。自己的旧服务session49114已Ctrl+C停止，当前25679运行。open_in_codex回放页面返回queued，未假称原生窗口已显示。

源及证据SHA见SOURCE_AND_END_BOUNDARY.json；全树写前扫描非原子且耗时，准备的新文件可能入初始扫描，不宣称原子冻结。实际只写本新源码/本证据以及接下来新return/WORKFLOW/REVIEW_LOG授权记录；没有git写/采集/部署或改GT/模型/原captures。后写记录另ARTIFACTS_FINAL_SHA.json，未计入先前结束快照。

背景问题待用户提供同安装位置空场；如果确认雷达/家具变化，应新版本重建参考并完整回放。本版不等同替换D05/生产识别；主动躺下、坐蹲、遮挡、多人与家具接触仍需独立会话。没有将当前两段作为合格测试集报告准确率。独立审核未完成。

ponytail实际读取路径：C:/Users/30680/.codex/skills/ponytail/SKILL.md。
